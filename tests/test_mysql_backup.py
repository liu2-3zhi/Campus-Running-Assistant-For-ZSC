"""No network: destructive backup/reset behavior is checked with a DBAPI fake."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import copy
import importlib
import json
import re

import pytest


DATABASE_PRIVILEGES = (
    'ALTER', 'ALTER ROUTINE', 'CREATE', 'CREATE ROUTINE',
    'CREATE TEMPORARY TABLES', 'CREATE VIEW', 'DELETE', 'DROP', 'EVENT',
    'EXECUTE', 'INDEX', 'INSERT', 'LOCK TABLES', 'REFERENCES', 'SELECT',
    'SHOW VIEW', 'TRIGGER', 'UPDATE',
)


class FakeConnection:
    def __init__(self, database='target'):
        self.database = database
        self.tables = {
            'app_documents': {'engine': 'InnoDB', 'type': 'BASE TABLE',
                'ddl': 'CREATE TABLE app_documents (id INT PRIMARY KEY, content LONGBLOB)',
                'columns': ['id', 'content', 'amount', 'created'],
                'rows': [(1, b'\x00\xff', Decimal('1.20'), datetime(2026, 1, 2, 3, 4, 5, 6))]},
            'app_storage_meta': {'engine': 'InnoDB', 'type': 'BASE TABLE',
                'ddl': 'CREATE TABLE app_storage_meta (k TEXT,v TEXT)',
                'columns': ['k', 'v'], 'rows': [('schema_version', '1'), ('ready', '1')]},
        }
        self.objects = {'triggers': [], 'routines': [], 'events': []}
        self.foreign_keys = []
        self.external_foreign_keys = []
        self.operations = []
        self.foreign_key_checks = 1
        self.grants = ['GRANT ALL PRIVILEGES ON '+self.quote(database)+'.* TO synthetic']
        self.fail_drop = None
        self.on_write_lock = None
        self.session = {'time_zone': 'SYSTEM', 'sql_mode': 'STRICT_TRANS_TABLES',
                        'character_set_client': 'utf8mb4', 'collation_connection': 'utf8mb4_unicode_ci'}

    @staticmethod
    def quote(value):
        return chr(96) + value.replace(chr(96), chr(96)*2) + chr(96)

    def cursor(self):
        return FakeCursor(self)


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = []
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=()):
        connection = self.connection
        normalized = ' '.join(sql.upper().split())
        connection.operations.append((sql, params))
        self.description = None
        if normalized == 'SELECT DATABASE()':
            self.result = [(connection.database,)]
        elif normalized.startswith('SHOW GRANTS'):
            self.result = [(grant,) for grant in connection.grants]
        elif 'INFORMATION_SCHEMA.TABLES' in normalized:
            self.result = [(name, table['type'], table['engine']) for name, table in sorted(connection.tables.items())]
        elif 'INFORMATION_SCHEMA.TRIGGERS' in normalized:
            self.result = [(name,) for name in connection.objects['triggers']]
        elif 'INFORMATION_SCHEMA.ROUTINES' in normalized:
            self.result = [(name, 'PROCEDURE') for name in connection.objects['routines']]
        elif 'INFORMATION_SCHEMA.EVENTS' in normalized:
            self.result = [(name,) for name in connection.objects['events']]
        elif 'INFORMATION_SCHEMA.KEY_COLUMN_USAGE' in normalized:
            self.result = (connection.external_foreign_keys if 'TABLE_SCHEMA <>' in normalized
                           else connection.foreign_keys)
        elif 'INFORMATION_SCHEMA.COLUMNS' in normalized:
            table = connection.tables[params[1]]
            self.result = [(
                name, position + 1, metadata.get('COLUMN_TYPE', 'text'),
                metadata.get('IS_NULLABLE', 'YES'), metadata.get('COLUMN_DEFAULT'),
                metadata.get('EXTRA', ''), metadata.get('GENERATION_EXPRESSION', ''),
                metadata.get('CHARACTER_SET_NAME'), metadata.get('COLLATION_NAME'),
            ) for position, name in enumerate(table['columns'])
                for metadata in [table.get('metadata', {}).get(name, {})]]
        elif normalized.startswith('SHOW CREATE TABLE'):
            name = self.table_name(sql)
            self.result = [(name, connection.tables[name]['ddl'])]
        elif normalized.startswith('SELECT * FROM'):
            table = connection.tables[self.table_name(sql)]
            positions = [i for i, column in enumerate(table['columns'])
                         if 'INVISIBLE' not in table.get('metadata', {}).get(column, {}).get('EXTRA', '')]
            self.description = [(table['columns'][i], None, None, None, None, None, None) for i in positions]
            self.result = [tuple(self.display_value(table, row, i) for i in positions)
                           for row in copy.deepcopy(table['rows'])]
        elif normalized.startswith('SELECT ') and ' FROM ' in normalized and chr(96) in sql:
            table = connection.tables[self.table_name(sql)]
            quoted_columns = re.findall(chr(96)+r'((?:'+chr(96)*2+r'|[^'+chr(96)+r'])*)'+chr(96), sql.split(' FROM ', 1)[0])
            columns = [column.replace(chr(96)*2, chr(96)) for column in quoted_columns]
            positions = [table['columns'].index(column) for column in columns]
            self.description = [(column, None, None, None, None, None, None) for column in columns]
            self.result = [tuple(self.display_value(table, row, i) for i in positions)
                           for row in copy.deepcopy(table['rows'])]
        elif normalized.startswith('SELECT @@SESSION.TIME_ZONE'):
            self.result = [tuple(connection.session[name] for name in (
                'time_zone', 'sql_mode', 'character_set_client', 'collation_connection'))]
        elif normalized.startswith('SET SESSION ') and 'FOREIGN_KEY_CHECKS' not in normalized:
            name = sql.split()[2]
            connection.session[name] = params[0]
            self.result = []
        elif normalized.startswith('SELECT @@SESSION.FOREIGN_KEY_CHECKS'):
            self.result = [(connection.foreign_key_checks,)]
        elif normalized.startswith('SET SESSION FOREIGN_KEY_CHECKS'):
            connection.foreign_key_checks = int(params[0])
            self.result = []
        elif normalized.startswith('LOCK TABLES'):
            if ' WRITE' in normalized and connection.on_write_lock:
                connection.on_write_lock(connection)
            self.result = []
        elif normalized == 'UNLOCK TABLES':
            self.result = []
        elif normalized.startswith('DROP TABLE'):
            name = self.table_name(sql)
            if connection.fail_drop == name:
                raise RuntimeError('Synthetic DROP failure')
            assert connection.foreign_key_checks == 1
            del connection.tables[name]
            connection.foreign_keys = [row for row in connection.foreign_keys if row[0] != name]
            self.result = []
        else:
            raise AssertionError('Unexpected SQL in fake: '+sql)

    @staticmethod
    def table_name(sql):
        names = re.findall(chr(96)+r'((?:'+chr(96)*2+r'|[^'+chr(96)+r'])*)'+chr(96), sql)
        assert len(names) >= 2, sql
        return names[-1].replace(chr(96)*2, chr(96))

    def display_value(self, table, row, position):
        value = row[position]
        column = table['columns'][position]
        metadata = table.get('metadata', {}).get(column, {})
        if isinstance(value, datetime) and metadata.get('COLUMN_TYPE') == 'timestamp':
            zone = self.connection.session['time_zone']
            if zone not in {'SYSTEM', '+00:00'}:
                sign = -1 if zone[0] == '-' else 1
                hours, minutes = map(int, zone[1:].split(':'))
                value += sign * timedelta(hours=hours, minutes=minutes)
        return value

    def fetchall(self):
        return self.result

    def fetchone(self):
        return self.result[0] if self.result else None


@pytest.fixture
def api():
    return importlib.import_module('persistence.mysql_backup')


def drops(connection):
    return [sql for sql, _ in connection.operations if sql.upper().startswith('DROP ')]


@pytest.mark.parametrize('scope', ['target', '*'])
def test_explicit_complete_database_privileges_allow_backup_and_reset(api, tmp_path, scope):
    connection = FakeConnection()
    scope_sql = '*' if scope == '*' else connection.quote(scope)
    privileges = ', '.join(DATABASE_PRIVILEGES + ('CREATE ROLE', 'DROP ROLE'))
    connection.grants = ['GRANT '+privileges+' ON '+scope_sql+'.* TO synthetic WITH GRANT OPTION']

    path = api.backup_database(connection, tmp_path, 'target')
    result = api.reset_database(connection, path, 'target')

    assert not connection.tables
    assert len(drops(connection)) == 2
    assert result

@pytest.mark.parametrize('missing', DATABASE_PRIVILEGES)
def test_explicit_database_privileges_missing_any_required_permission_are_rejected(api, tmp_path, missing):
    connection = FakeConnection()
    privileges = ', '.join(value for value in DATABASE_PRIVILEGES if value != missing)
    connection.grants = ['GRANT '+privileges+' ON '+connection.quote('target')+'.* TO synthetic']

    with pytest.raises(api.BackupError):
        api.backup_database(connection, tmp_path/'backup', 'target')

    assert not drops(connection)
    assert not (tmp_path/'backup').exists()

@pytest.mark.parametrize('scope', ['other', 'target_table'])
def test_explicit_full_permissions_on_another_schema_do_not_authorize_target(api, tmp_path, scope):
    connection = FakeConnection()
    connection.grants = ['GRANT '+', '.join(DATABASE_PRIVILEGES)+' ON '+connection.quote(scope)+'.* TO synthetic']

    with pytest.raises(api.BackupError):
        api.backup_database(connection, tmp_path/'backup', 'target')

    assert not drops(connection)

def test_explicit_full_table_permissions_do_not_prove_database_inventory_visibility(api, tmp_path):
    connection = FakeConnection()
    connection.grants = ['GRANT '+', '.join(DATABASE_PRIVILEGES)+' ON '
                         +connection.quote('target')+'.'+connection.quote('app_documents')+' TO synthetic']

    with pytest.raises(api.BackupError):
        api.backup_database(connection, tmp_path/'backup', 'target')

    assert not drops(connection)

def test_partial_revoke_rejects_otherwise_complete_explicit_global_grant(api, tmp_path):
    connection = FakeConnection()
    connection.grants = ['GRANT '+', '.join(DATABASE_PRIVILEGES)+' ON *.* TO synthetic',
                         'REVOKE SELECT ON '+connection.quote('target')+'.* FROM synthetic']

    with pytest.raises(api.BackupError):
        api.backup_database(connection, tmp_path/'backup', 'target')

    assert not drops(connection)

def test_literal_asterisk_schema_is_not_a_global_grant(api, tmp_path):
    connection = FakeConnection()
    connection.grants = ['GRANT '+', '.join(DATABASE_PRIVILEGES)+' ON '
                         +connection.quote('*')+'.* TO synthetic']

    with pytest.raises(api.BackupError):
        api.backup_database(connection, tmp_path/'backup', 'target')

    assert not drops(connection)


def test_complete_explicit_grant_still_requires_full_supported_object_inventory(api, tmp_path):
    connection = FakeConnection()
    connection.grants = ['GRANT '+', '.join(DATABASE_PRIVILEGES)+' ON *.* TO synthetic']
    connection.objects['triggers'] = ['synthetic_trigger']

    with pytest.raises(api.BackupError):
        api.backup_database(connection, tmp_path/'backup', 'target')

    assert not drops(connection)
    assert not (tmp_path/'backup').exists()


def test_wrong_database_is_rejected_before_backup_or_reset(api, tmp_path):
    connection = FakeConnection('other')
    with pytest.raises(api.BackupError):
        api.backup_database(connection, tmp_path/'backup', 'target')
    with pytest.raises(api.BackupError):
        api.reset_database(connection, tmp_path/'missing.json', 'target')
    assert not drops(connection)
    assert not (tmp_path/'backup').exists()


def test_backup_serializes_full_ddl_and_binary_decimal_datetime_values(api, tmp_path):
    connection = FakeConnection()
    path = api.backup_database(connection, tmp_path, 'target')
    value = json.loads(path.read_text(encoding='utf-8'))
    assert value['database'] == 'target'
    assert len(value['snapshot']['tables']) == 2
    table = next(t for t in value['snapshot']['tables'] if t['name'] == 'app_documents')
    assert table['ddl'] == connection.tables['app_documents']['ddl']
    assert table['rows'][0][1] == ['bytes', 'AP8=']
    assert table['rows'][0][2] == ['decimal', '1.20']
    assert table['rows'][0][3] == ['datetime', '2026-01-02T03:04:05.000006']
    assert len(value['manifest_sha256']) == 64
    assert len(table['schema_sha256']) == 64
    assert len(table['rows_sha256']) == 64
    assert not drops(connection)


def test_backup_explicitly_selects_invisible_columns_and_keeps_their_metadata(api, tmp_path):
    connection = FakeConnection()
    table = connection.tables['app_documents']
    table['metadata'] = {'content': {'EXTRA': 'INVISIBLE', 'COLUMN_TYPE': 'longblob',
                                    'IS_NULLABLE': 'NO', 'COLUMN_DEFAULT': 'synthetic'}}
    path = api.backup_database(connection, tmp_path, 'target')
    snapshot = json.loads(path.read_text())['snapshot']
    backed_up = next(item for item in snapshot['tables'] if item['name'] == 'app_documents')
    assert backed_up['columns'] == ['id', 'content', 'amount', 'created']
    assert backed_up['rows'][0][1] == ['bytes', 'AP8=']
    metadata = backed_up['column_metadata'][1]
    assert metadata['COLUMN_NAME'] == 'content'
    assert metadata['COLUMN_TYPE'] == 'longblob'
    assert metadata['IS_NULLABLE'] == 'NO'
    assert metadata['COLUMN_DEFAULT'] == 'synthetic'
    assert metadata['EXTRA'] == 'INVISIBLE'
    assert 'content' in backed_up['writable_columns']
    assert not any(sql.upper().startswith('SELECT * FROM') for sql, _ in connection.operations)
    connection.tables['app_documents']['rows'][0] = (1, b'changed hidden value', Decimal('1.20'),
                                                     datetime(2026, 1, 2, 3, 4, 5, 6))
    with pytest.raises(api.BackupError):
        api.reset_database(connection, path, 'target')
    assert not drops(connection)


def test_generated_values_are_verified_but_excluded_from_writable_columns(api, tmp_path):
    connection = FakeConnection()
    table = connection.tables['app_documents']
    table['columns'] = ['id', 'source', 'virtual_result', 'stored_result']
    table['rows'] = [(1, 2, 4, 6)]
    table['metadata'] = {
        'virtual_result': {'EXTRA': 'VIRTUAL GENERATED', 'GENERATION_EXPRESSION': 'source * 2'},
        'stored_result': {'EXTRA': 'STORED GENERATED INVISIBLE', 'GENERATION_EXPRESSION': 'source * 3'},
    }
    path = api.backup_database(connection, tmp_path, 'target')
    snapshot = json.loads(path.read_text())['snapshot']
    backed_up = next(item for item in snapshot['tables'] if item['name'] == 'app_documents')
    assert backed_up['writable_columns'] == ['id', 'source']
    assert backed_up['rows'][0] == [['int', '1'], ['int', '2'], ['int', '4'], ['int', '6']]
    assert backed_up['column_metadata'][2]['GENERATION_EXPRESSION'] == 'source * 2'
    assert backed_up['column_metadata'][3]['EXTRA'] == 'STORED GENERATED INVISIBLE'
    result = api.reset_database(connection, path, 'target')
    assert result['ok'] is True


def test_backup_uses_utc_for_timestamp_and_restores_session_settings(api, tmp_path):
    connection = FakeConnection()
    connection.session['time_zone'] = '+08:00'
    connection.tables['app_documents']['metadata'] = {'created': {'COLUMN_TYPE': 'timestamp'}}
    previous = dict(connection.session)
    path = api.backup_database(connection, tmp_path, 'target')
    content = json.loads(path.read_text())
    table = next(table for table in content['snapshot']['tables'] if table['name'] == 'app_documents')
    assert table['rows'][0][3] == ['datetime', '2026-01-02T03:04:05.000006']
    assert content['session_semantics']['time_zone'] == '+00:00'
    assert content['session_semantics']['sql_mode'] == 'STRICT_TRANS_TABLES'
    assert content['session_semantics']['character_set_client'] == 'utf8mb4'
    assert content['session_semantics']['collation_connection'] == 'utf8mb4_unicode_ci'
    assert connection.session == previous


def test_reset_can_compare_a_backup_from_a_different_session_timezone(api, tmp_path):
    connection = FakeConnection()
    connection.session['time_zone'] = '+08:00'
    connection.tables['app_documents']['metadata'] = {'created': {'COLUMN_TYPE': 'timestamp'}}
    path = api.backup_database(connection, tmp_path, 'target')
    connection.session.update(time_zone='-05:00', sql_mode='NO_BACKSLASH_ESCAPES')
    previous = dict(connection.session)
    assert api.reset_database(connection, path, 'target')['ok'] is True
    assert connection.session == previous


def test_backup_failure_restores_session_timezone(api, tmp_path):
    connection = FakeConnection()
    connection.session['time_zone'] = '+08:00'
    previous = dict(connection.session)
    connection.objects['events'] = ['unsupported']
    with pytest.raises(api.BackupError):
        api.backup_database(connection, tmp_path, 'target')
    assert connection.session == previous


def test_reset_ddl_failure_restores_session_timezone(api, tmp_path):
    connection = FakeConnection()
    path = api.backup_database(connection, tmp_path, 'target')
    connection.session['time_zone'] = '+09:30'
    previous = dict(connection.session)
    connection.fail_drop = 'app_storage_meta'
    with pytest.raises(api.BackupError):
        api.reset_database(connection, path, 'target')
    assert connection.session == previous


def test_reset_requires_existing_verified_backup(api, tmp_path):
    connection = FakeConnection()
    with pytest.raises(api.BackupError):
        api.reset_database(connection, tmp_path/'absent.json', 'target')
    assert not drops(connection)


def test_reset_rejects_tampered_backup_without_dropping(api, tmp_path):
    connection = FakeConnection()
    path = api.backup_database(connection, tmp_path, 'target')
    data = json.loads(path.read_text())
    data['snapshot']['tables'][0]['rows'][0][0] = ['int', '999']
    path.write_text(json.dumps(data))
    with pytest.raises(api.BackupError):
        api.reset_database(connection, path, 'target')
    assert not drops(connection)


@pytest.mark.parametrize('change', ['rows', 'ddl', 'new_table', 'under_lock'])
def test_reset_rejects_any_change_since_backup(api, tmp_path, change):
    connection = FakeConnection()
    path = api.backup_database(connection, tmp_path, 'target')
    if change == 'rows':
        connection.tables['app_storage_meta']['rows'].append(('new', 'value'))
    elif change == 'ddl':
        connection.tables['app_storage_meta']['ddl'] += ' COMMENT synthetic'
    elif change == 'new_table':
        connection.tables['new_table'] = copy.deepcopy(connection.tables['app_storage_meta'])
    else:
        connection.on_write_lock = lambda c: c.tables['app_storage_meta']['rows'].append(('new', 'value'))
    with pytest.raises(api.BackupError):
        api.reset_database(connection, path, 'target')
    assert not drops(connection)
    assert connection.foreign_key_checks == 1


@pytest.mark.parametrize('kind', ['view', 'trigger', 'routine', 'event', 'nontransactional', 'external_fk', 'cycle'])
def test_unhandled_objects_or_unsafe_dependencies_fail_closed(api, tmp_path, kind):
    connection = FakeConnection()
    if kind == 'view':
        connection.tables['app_documents']['type'] = 'VIEW'
    elif kind == 'nontransactional':
        connection.tables['app_documents']['engine'] = 'MyISAM'
    elif kind == 'external_fk':
        connection.external_foreign_keys = [('external_table', 'fk', 'target', 'app_documents')]
    elif kind == 'cycle':
        connection.foreign_keys = [('app_documents', 'fk1', 'target', 'app_storage_meta'),
                                   ('app_storage_meta', 'fk2', 'target', 'app_documents')]
    else:
        connection.objects[{'trigger': 'triggers', 'routine': 'routines', 'event': 'events'}[kind]] = ['synthetic']
    with pytest.raises(api.BackupError):
        api.backup_database(connection, tmp_path, 'target')
    assert not drops(connection)


def test_reset_drops_internal_fk_children_before_parents_and_keeps_fk_checks(api, tmp_path):
    connection = FakeConnection()
    connection.foreign_keys = [('app_documents', 'fk_docs_meta', 'target', 'app_storage_meta')]
    path = api.backup_database(connection, tmp_path, 'target')
    result = api.reset_database(connection, path, 'target')
    assert result['ok'] is True
    assert connection.tables == {}
    assert [FakeCursor.table_name(sql) for sql in drops(connection)] == ['app_documents', 'app_storage_meta']
    assert connection.foreign_key_checks == 1
    assert all('DROP DATABASE' not in sql.upper() and 'DROP USER' not in sql.upper() for sql, _ in connection.operations)
    assert any(sql.upper().startswith('LOCK TABLES') and ' WRITE' in sql.upper() for sql, _ in connection.operations)


def test_reset_restores_fk_checks_and_unlocks_after_partial_ddl_failure(api, tmp_path):
    connection = FakeConnection()
    path = api.backup_database(connection, tmp_path, 'target')
    connection.foreign_key_checks = 0
    connection.fail_drop = 'app_storage_meta'
    with pytest.raises(api.BackupError, match='DDL'):
        api.reset_database(connection, path, 'target')
    assert connection.foreign_key_checks == 0
    lock_operations = [sql for sql, _ in connection.operations
                       if sql.upper().startswith('LOCK TABLES') or sql.upper() == 'UNLOCK TABLES']
    assert lock_operations[-1] == 'UNLOCK TABLES'
    assert path.is_file()


def test_inventory_requires_full_target_database_visibility(api, tmp_path):
    connection = FakeConnection()
    connection.grants = ['GRANT SELECT, INSERT ON '+connection.quote('target')+'.* TO synthetic']
    with pytest.raises(api.BackupError):
        api.backup_database(connection, tmp_path, 'target')
    assert not drops(connection)


def test_serialized_value_tags_round_trip_without_losing_decimal_or_time(api):
    values = [None, False, True, 2**70, -12, 0.125, 'NA', b'\x00\x01', bytearray(b'abc'),
              Decimal('1.200'), date(2026, 1, 2), datetime(2026, 1, 2, 3, 4, 5, 6),
              time(3, 4, 5, 6), timedelta(days=-2, seconds=3, microseconds=4)]
    for value in values:
        restored = api.decode_value(api.encode_value(value))
        assert restored == value
