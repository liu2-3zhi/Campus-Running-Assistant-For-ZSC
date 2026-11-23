"""Verified backups before an explicitly authorized MySQL maintenance reset.

Callers supply a dedicated DBAPI connection; no connections or credentials are
created here. InnoDB tables with acyclic in-database foreign keys are supported.
Other object types fail closed. Application writers must be stopped first.

DDL commits implicitly: failure can leave a partially cleared database. The
backup stays intact, FK enforcement stays ON, and databases/accounts are never
dropped. Full target-database privileges are required to prove object inventory.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import uuid


class BackupError(RuntimeError):
    """Proceeding cannot be proved safe; messages contain no record bodies."""


FORMAT = 'python-running-mysql-backup'
VERSION = 2
DATABASE_PRIVILEGES = frozenset({
    'ALTER', 'ALTER ROUTINE', 'CREATE', 'CREATE ROUTINE',
    'CREATE TEMPORARY TABLES', 'CREATE VIEW', 'DELETE', 'DROP', 'EVENT',
    'EXECUTE', 'INDEX', 'INSERT', 'LOCK TABLES', 'REFERENCES', 'SELECT',
    'SHOW VIEW', 'TRIGGER', 'UPDATE',
})
COLUMN_METADATA_FIELDS = (
    'COLUMN_NAME', 'ORDINAL_POSITION', 'COLUMN_TYPE', 'IS_NULLABLE',
    'COLUMN_DEFAULT', 'EXTRA', 'GENERATION_EXPRESSION',
    'CHARACTER_SET_NAME', 'COLLATION_NAME',
)
SCHEMA_FIELDS = ('name', 'engine', 'ddl', 'columns', 'column_metadata', 'writable_columns')
SESSION_FIELDS = ('time_zone', 'sql_mode', 'character_set_client', 'collation_connection')


def encode_value(value):
    if value is None:
        return ['null']
    if isinstance(value, bool):
        return ['bool', value]
    if isinstance(value, int):
        return ['int', str(value)]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise BackupError('Nonfinite database numbers are unsupported')
        return ['float', value.hex()]
    if isinstance(value, str):
        return ['str', value]
    if isinstance(value, (bytes, bytearray, memoryview)):
        return ['bytes', base64.b64encode(bytes(value)).decode('ascii')]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise BackupError('Nonfinite database decimals are unsupported')
        return ['decimal', str(value)]
    if isinstance(value, datetime):
        return ['datetime', value.isoformat(timespec='microseconds')]
    if isinstance(value, date):
        return ['date', value.isoformat()]
    if isinstance(value, time):
        return ['time', value.isoformat(timespec='microseconds')]
    if isinstance(value, timedelta):
        return ['timedelta_us', str((value.days * 86400 + value.seconds) * 1000000 + value.microseconds)]
    raise BackupError('Unsupported database value type')


def decode_value(value):
    if not isinstance(value, list) or not value or not isinstance(value[0], str):
        raise BackupError('Invalid backup value encoding')
    tag = value[0]
    if tag == 'null' and len(value) == 1:
        return None
    if len(value) != 2:
        raise BackupError('Invalid backup value encoding')
    raw = value[1]
    try:
        if tag == 'bool' and isinstance(raw, bool):
            return raw
        if tag == 'str' and isinstance(raw, str):
            return raw
        if not isinstance(raw, str):
            raise ValueError('Invalid scalar')
        if tag == 'int':
            return int(raw)
        if tag == 'float':
            number = float.fromhex(raw)
            if not math.isfinite(number):
                raise ValueError('Nonfinite number')
            return number
        if tag == 'bytes':
            return base64.b64decode(raw, validate=True)
        if tag == 'decimal':
            number = Decimal(raw)
            if not number.is_finite():
                raise ValueError('Nonfinite decimal')
            return number
        if tag == 'datetime':
            return datetime.fromisoformat(raw)
        if tag == 'date':
            return date.fromisoformat(raw)
        if tag == 'time':
            return time.fromisoformat(raw)
        if tag == 'timedelta_us':
            return timedelta(microseconds=int(raw))
    except Exception:
        raise BackupError('Invalid backup scalar encoding') from None
    raise BackupError('Unsupported backup value encoding')


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def _digest(value):
    return hashlib.sha256(_json(value)).hexdigest()


def _quote(value):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise BackupError('Invalid database identifier')
    return chr(96) + value.replace(chr(96), chr(96) * 2) + chr(96)


def _qualified(database, name):
    return _quote(database) + '.' + _quote(name)


def _guard_target(connection, expected_database):
    _quote(expected_database)
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE()')
        row = cursor.fetchone()
    if row is None or row[0] != expected_database:
        raise BackupError('Selected database does not exactly match the authorized target')


def _guard_visibility(connection, database):
    # Empty information_schema results are insufficient without full visibility.
    with connection.cursor() as cursor:
        cursor.execute('SHOW GRANTS FOR CURRENT_USER')
        grants = [str(row[0]) for row in cursor.fetchall()]
    if any(grant.upper().startswith('REVOKE ') for grant in grants):
        raise BackupError('Partial privilege revocations prevent a complete object inventory')
    tick = chr(96)
    pattern = r'^GRANT\s+(.+?)\s+ON\s+(' + tick + '(?:' + tick * 2 + '|[^' + tick + '])*' + tick + r'|\*)\.\*\s+TO\s'
    for grant in grants:
        match = re.match(pattern, grant, re.I)
        if not match:
            continue
        privileges, scope = match.groups()
        # MySQL 8.4 may enumerate static privileges instead of rendering ALL.
        explicit = {re.sub(r'\s+', ' ', value.strip()).upper()
                    for value in privileges.split(',')}
        if (privileges.strip().upper() != 'ALL PRIVILEGES'
                and not DATABASE_PRIVILEGES.issubset(explicit)):
            continue
        global_scope = scope == '*'
        scope = scope[1:-1].replace(tick * 2, tick) if scope.startswith(tick) else scope
        scope = scope.replace('\\_', '_').replace('\\%', '%')
        if scope == database or global_scope:
            return
    raise BackupError('Full target-database privileges are required for complete object inventory')


@contextmanager
def _session_settings(connection, requested=None):
    with connection.cursor() as cursor:
        cursor.execute('SELECT @@SESSION.time_zone,@@SESSION.sql_mode,'
                       '@@SESSION.character_set_client,@@SESSION.collation_connection')
        row = cursor.fetchone()
    if row is None or len(row) != len(SESSION_FIELDS):
        raise BackupError('Database session semantics could not be read completely')
    previous = dict(zip(SESSION_FIELDS, row))
    effective = dict(previous if requested is None else requested)
    effective['time_zone'] = '+00:00'
    # These MariaDB compatibility modes deliberately omit parts of SHOW CREATE.
    omitted_ddl = {'NO_TABLE_OPTIONS', 'NO_FIELD_OPTIONS', 'NO_KEY_OPTIONS'}
    effective['sql_mode'] = ','.join(mode for mode in str(effective['sql_mode']).split(',')
                                     if mode.upper() not in omitted_ddl)
    if set(effective) != set(SESSION_FIELDS) or not all(isinstance(value, str) for value in effective.values()):
        raise BackupError('Database session semantics are invalid')
    try:
        with connection.cursor() as cursor:
            for field in SESSION_FIELDS:
                cursor.execute('SET SESSION ' + field + ' = %s', (effective[field],))
        yield effective
    finally:
        with connection.cursor() as cursor:
            for field in reversed(SESSION_FIELDS):
                cursor.execute('SET SESSION ' + field + ' = %s', (previous[field],))


def _is_generated(column):
    expression = column['GENERATION_EXPRESSION']
    extra = str(column['EXTRA'] or '').upper().split()
    return (expression is not None and str(expression).strip() != '') or (
        'GENERATED' in extra and any(kind in extra for kind in ('VIRTUAL', 'STORED', 'PERSISTENT')))


def _column_metadata(cursor, database, name):
    cursor.execute('SELECT ' + ','.join(COLUMN_METADATA_FIELDS)
                   + ' FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s '
                     'ORDER BY ORDINAL_POSITION', (database, name))
    rows = cursor.fetchall()
    if not rows or any(len(row) != len(COLUMN_METADATA_FIELDS) for row in rows):
        raise BackupError('Complete table column metadata is required, including invisible columns')
    columns = [dict(zip(COLUMN_METADATA_FIELDS, row)) for row in rows]
    names = []
    for position, column in enumerate(columns, 1):
        _quote(column['COLUMN_NAME'])
        if column['ORDINAL_POSITION'] != position:
            raise BackupError('Column metadata is incomplete or out of order')
        names.append(column['COLUMN_NAME'])
    if len(names) != len(set(names)):
        raise BackupError('Column metadata contains duplicate identities')
    return columns


def _drop_order(snapshot):
    names = {table['name'] for table in snapshot['tables']}
    dependents = {name: set() for name in names}
    for child, _constraint, _database, parent in snapshot['foreign_keys']:
        if child not in names or parent not in names:
            raise BackupError('An unlisted foreign-key dependency prevents safe deletion')
        dependents[parent].add(child)
    result, remaining = [], set(names)
    while remaining:
        ready = sorted(name for name in remaining if not (dependents[name] & remaining))
        if not ready:
            raise BackupError('Cyclic foreign keys require a separate reviewed reset procedure')
        result.extend(ready)
        remaining.difference_update(ready)
    return result


def _inventory(connection, database):
    with connection.cursor() as cursor:
        cursor.execute('SELECT TABLE_NAME,TABLE_TYPE,ENGINE FROM information_schema.TABLES '
                       'WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME', (database,))
        tables = [{'name': r[0], 'type': r[1], 'engine': r[2]} for r in cursor.fetchall()]
        for table in tables:
            _quote(table['name'])
            if table['type'] != 'BASE TABLE' or str(table['engine']).upper() != 'INNODB':
                raise BackupError('Unsupported database object or non-InnoDB table; reset refused')
        for sql in (
            'SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s ORDER BY TRIGGER_NAME',
            'SELECT ROUTINE_NAME,ROUTINE_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s ORDER BY ROUTINE_NAME',
            'SELECT EVENT_NAME FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s ORDER BY EVENT_NAME',
        ):
            cursor.execute(sql, (database,))
            if cursor.fetchall():
                raise BackupError('Views, triggers, routines or events need a supported full-object backup; reset refused')
        cursor.execute('SELECT TABLE_NAME,CONSTRAINT_NAME,REFERENCED_TABLE_SCHEMA,REFERENCED_TABLE_NAME '
                       'FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s '
                       'AND REFERENCED_TABLE_NAME IS NOT NULL ORDER BY TABLE_NAME,CONSTRAINT_NAME,ORDINAL_POSITION', (database,))
        foreign_keys = sorted(set(tuple(row) for row in cursor.fetchall()))
        if any(row[2] != database for row in foreign_keys):
            raise BackupError('Cross-database foreign keys prevent an isolated reset')
        cursor.execute('SELECT TABLE_NAME,CONSTRAINT_NAME,REFERENCED_TABLE_SCHEMA,REFERENCED_TABLE_NAME '
                       'FROM information_schema.KEY_COLUMN_USAGE WHERE REFERENCED_TABLE_SCHEMA=%s '
                       'AND TABLE_SCHEMA <> %s ORDER BY TABLE_SCHEMA,TABLE_NAME,CONSTRAINT_NAME', (database, database))
        if cursor.fetchall():
            raise BackupError('Another database references this target; reset refused')
    result = {'tables': sorted(tables, key=lambda table: table['name']),
              'foreign_keys': [list(row) for row in foreign_keys],
              'views': [], 'triggers': [], 'routines': [], 'events': []}
    _drop_order(result)
    return result


@contextmanager
def _table_locks(connection, database, names, mode):
    locked = False
    try:
        if names:
            with connection.cursor() as cursor:
                cursor.execute('LOCK TABLES ' + ','.join(_qualified(database, name) + ' ' + mode for name in names))
            locked = True
        yield
    finally:
        if locked:
            with connection.cursor() as cursor:
                cursor.execute('UNLOCK TABLES')


def _snapshot(connection, database):
    inventory = _inventory(connection, database)
    tables = []
    with connection.cursor() as cursor:
        for table in inventory['tables']:
            name = table['name']
            cursor.execute('SHOW CREATE TABLE ' + _qualified(database, name))
            ddl_row = cursor.fetchone()
            if not ddl_row or len(ddl_row) < 2 or not isinstance(ddl_row[1], str):
                raise BackupError('Table DDL could not be read completely')
            column_metadata = _column_metadata(cursor, database, name)
            columns = [column['COLUMN_NAME'] for column in column_metadata]
            cursor.execute('SELECT ' + ','.join(_quote(column) for column in columns)
                           + ' FROM ' + _qualified(database, name))
            selected = [column[0] for column in cursor.description or ()]
            rows = [[encode_value(cell) for cell in row] for row in cursor.fetchall()]
            if selected != columns or any(len(row) != len(columns) for row in rows):
                raise BackupError('Table columns or rows could not be read completely')
            rows.sort(key=_json)
            schema = {'name': name, 'engine': table['engine'], 'ddl': ddl_row[1], 'columns': columns,
                      'column_metadata': column_metadata,
                      'writable_columns': [column['COLUMN_NAME'] for column in column_metadata if not _is_generated(column)]}
            tables.append({**schema, 'rows': rows, 'schema_sha256': _digest(schema), 'rows_sha256': _digest(rows)})
    return {**inventory, 'tables': tables}


def _read_backup(path, database):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise BackupError('A complete existing regular backup file is required')
    try:
        content = json.loads(path.read_text(encoding='utf-8'))
        if content['format'] != FORMAT or content['version'] != VERSION or content['database'] != database:
            raise BackupError('Backup format or exact target does not match')
        semantics = content['session_semantics']
        if (set(semantics) != set(SESSION_FIELDS) or semantics['time_zone'] != '+00:00'
                or not all(isinstance(value, str) for value in semantics.values())):
            raise BackupError('Backup session semantics must explicitly preserve UTC timestamps')
        without_manifest = {key: value for key, value in content.items() if key != 'manifest_sha256'}
        if _digest(without_manifest) != content['manifest_sha256'] or _digest(content['snapshot']) != content['snapshot_sha256']:
            raise BackupError('Backup integrity verification failed')
        snapshot = content['snapshot']
        if any(snapshot[key] for key in ('views', 'triggers', 'routines', 'events')):
            raise BackupError('Unsupported database objects in backup')
        names = [table['name'] for table in snapshot['tables']]
        if len(names) != len(set(names)):
            raise BackupError('Duplicate table identities in backup')
        for table in snapshot['tables']:
            _quote(table['name'])
            schema = {key: table[key] for key in SCHEMA_FIELDS}
            if str(table['engine']).upper() != 'INNODB' or _digest(schema) != table['schema_sha256'] or _digest(table['rows']) != table['rows_sha256']:
                raise BackupError('Backup schema or row hash verification failed')
            if not table['columns'] or len(table['columns']) != len(set(table['columns'])):
                raise BackupError('Invalid backup column identities')
            metadata = table['column_metadata']
            if (len(metadata) != len(table['columns'])
                    or any(set(column) != set(COLUMN_METADATA_FIELDS) for column in metadata)
                    or [column['COLUMN_NAME'] for column in metadata] != table['columns']
                    or [column['ORDINAL_POSITION'] for column in metadata] != list(range(1, len(metadata) + 1))
                    or table['writable_columns'] != [column['COLUMN_NAME'] for column in metadata if not _is_generated(column)]):
                raise BackupError('Backup column metadata or generated-column restoration mapping is incomplete')
            for row in table['rows']:
                if len(row) != len(table['columns']):
                    raise BackupError('Incomplete backup row')
                for cell in row:
                    decode_value(cell)
        if any(row[2] != database for row in snapshot['foreign_keys']):
            raise BackupError('Cross-database foreign key in backup')
        _drop_order(snapshot)
        return content
    except BackupError:
        raise
    except Exception:
        raise BackupError('Backup file is incomplete or malformed') from None


def _backup_database_in_session(connection, output_dir, expected_database, semantics):
    """Back up all supported objects, fsync, re-read and independently hash."""
    _guard_target(connection, expected_database)
    try:
        _guard_visibility(connection, expected_database)
        inventory = _inventory(connection, expected_database)
        names = [table['name'] for table in inventory['tables']]
        with _table_locks(connection, expected_database, names, 'READ'):
            _guard_target(connection, expected_database)
            snapshot = _snapshot(connection, expected_database)
            if [table['name'] for table in snapshot['tables']] != names or snapshot['foreign_keys'] != inventory['foreign_keys']:
                raise BackupError('Database objects changed during backup preparation')
            content = {'format': FORMAT, 'version': VERSION, 'database': expected_database,
                       'session_semantics': semantics,
                       'captured_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                       'snapshot': snapshot, 'snapshot_sha256': _digest(snapshot)}
            content['manifest_sha256'] = _digest(content)
            directory = Path(output_dir).resolve()
            repository = Path(__file__).resolve().parents[1]
            if directory == repository or repository in directory.parents:
                raise BackupError('Sensitive database backups must be outside the repository')
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / ('mysql_backup_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                                + '_' + uuid.uuid4().hex[:12] + '.json')
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as output:
                output.write(_json(content))
                output.flush()
                os.fsync(output.fileno())
            verified = _read_backup(path, expected_database)
            if verified['snapshot_sha256'] != _digest(snapshot):
                raise BackupError('Written backup differs from the captured database')
        return path
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError('Database backup failed (' + type(exc).__name__ + '); reset is forbidden') from None


def _reset_database_in_session(connection, backup_path, expected_database):
    """Compare a verified backup to locked live data before child-first DROP.

    FK enforcement stays ON, including against otherwise invisible cross-schema
    dependencies. Restore its previous session value in finally. DDL can only be
    restored from the retained backup, not rolled back by a transaction.
    """
    _guard_target(connection, expected_database)
    verified = _read_backup(backup_path, expected_database)
    _guard_visibility(connection, expected_database)
    names = [table['name'] for table in verified['snapshot']['tables']]
    dropped = []
    try:
        with _table_locks(connection, expected_database, names, 'WRITE'):
            _guard_target(connection, expected_database)
            current = _snapshot(connection, expected_database)
            if _digest(current) != verified['snapshot_sha256']:
                raise BackupError('Current database differs from verified backup; no DROP was attempted')
            with connection.cursor() as cursor:
                cursor.execute('SELECT @@SESSION.FOREIGN_KEY_CHECKS')
                previous = int(cursor.fetchone()[0])
                try:
                    cursor.execute('SET SESSION FOREIGN_KEY_CHECKS = %s', (1,))
                    for name in _drop_order(current):
                        cursor.execute('DROP TABLE ' + _qualified(expected_database, name))
                        dropped.append(name)
                finally:
                    cursor.execute('SET SESSION FOREIGN_KEY_CHECKS = %s', (previous,))
            remaining = _inventory(connection, expected_database)
            if remaining['tables']:
                raise BackupError('DDL cleanup is incomplete; the verified backup is retained')
        return {'ok': True, 'dropped_tables': len(dropped), 'dropped_table_names': dropped,
                'backup_verified': True, 'database_preserved': True, 'database_account_preserved': True}
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError('Database reset DDL failed (' + type(exc).__name__
                          + '); cleanup may be partial and the verified backup is retained') from None


def backup_database(connection, output_dir, expected_database):
    """Capture every column, including invisible/generated values, in UTC.

    Restore sessions using session_semantics and INSERT only writable_columns;
    generated-column values remain in rows exclusively for integrity checks.
    """
    _guard_target(connection, expected_database)
    try:
        with _session_settings(connection) as semantics:
            return _backup_database_in_session(connection, output_dir, expected_database, semantics)
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError('Database backup session failed (' + type(exc).__name__ + '); reset is forbidden') from None


def reset_database(connection, backup_path, expected_database):
    """Verify locked data under backup session semantics before target-only DDL."""
    _guard_target(connection, expected_database)
    content = _read_backup(backup_path, expected_database)
    try:
        with _session_settings(connection, content['session_semantics']):
            return _reset_database_in_session(connection, backup_path, expected_database)
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError('Database reset DDL/session failed (' + type(exc).__name__
                          + '); cleanup may be partial and the verified backup is retained') from None
