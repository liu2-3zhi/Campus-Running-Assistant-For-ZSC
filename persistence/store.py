"""Transactional domain rows behind the transitional document I/O API.

This adapter stores neither legacy file bodies nor a second authoritative
document database. The registry records only identity, shape and revisions.
"""
from __future__ import annotations

import configparser
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import io
import json
import secrets
import threading
import time
from functools import wraps

from sqlalchemy import delete, insert, select, update, inspect, event, func, literal, case
from sqlalchemy.exc import IntegrityError, DBAPIError

from .codec import Builder, decode_tree
from .engine import Database, DatabaseError
from .schema import SCHEMA_VERSION, make_schema

ANY_REVISION = object()


def _safe_database(operation):
    @wraps(operation)
    def guarded(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except IntegrityError:
            from business_storage import ConflictError
            raise ConflictError('Database entity uniqueness conflict; no partial write committed') from None
        except DBAPIError as exc:
            raise DatabaseError(f'Database operation failed ({type(exc).__name__}); file fallback is disabled') from None
    return guarded


@dataclass(frozen=True)
class StoredDocument:
    namespace: str
    key: str
    content: bytes
    mtime_ns: int
    revision: int
    content_sha256: str
    source_sha256: str | None = None

    @property
    def digest(self):
        return self.content_sha256


def parse_content(key, content):
    text = content.decode('utf-8-sig')
    if key.lower().endswith('.ini'):
        parser = configparser.RawConfigParser(strict=False)
        parser.optionxform = str
        parser.read_string(text)
        # SectionProxy includes inherited DEFAULT entries; copying it would
        # silently turn inheritance into permanent per-section overrides.
        value = {section: dict(parser._sections[section]) for section in parser.sections()}
        if parser.defaults():
            value['DEFAULT'] = dict(parser.defaults())
        return 'ini', value
    if key.lower().endswith('.txt'):
        return 'text', text
    return 'json', json.loads(text, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def render_content(format, value, *, canonical=False):
    if canonical:
        # Native MySQL JSON sorts object keys on disk. Hash the same stable
        # representation on both engines without changing the v2 reader.
        def ordered(item):
            if isinstance(item, dict):
                return {key: ordered(item[key]) for key in sorted(item)}
            if isinstance(item, list):
                return [ordered(child) for child in item]
            return item
        value = ordered(value)
    if format == 'text':
        return value.encode('utf-8')
    if format == 'json':
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    parser.read_dict(value)
    handle = io.StringIO()
    parser.write(handle)
    return handle.getvalue().encode('utf-8')


class RelationalStore:
    normalized = True

    def __init__(self, settings, connection_factory=None, *, schema_version=SCHEMA_VERSION):
        self.settings = settings
        self.schema_version = str(schema_version)
        self.database = Database(settings, connection_factory)
        self._school_cache_generation = secrets.token_hex(16)
        self._school_cache_lock = threading.Lock()
        if settings.backend == 'sqlite':
            @event.listens_for(self.database.engine, 'connect')
            def register_digest(connection, _record):
                connection.create_function('application_sha256', 1,
                    lambda value: hashlib.sha256(value.encode('utf-8')).hexdigest() if value is not None else None, deterministic=True)
        self.metadata, self.registry, self.meta, self.entities, self.definitions = make_schema(
            settings.table_prefix, schema_version=self.schema_version)

    def school_cache_generation(self):
        # Never put a transaction's uncommitted view into Redis or process memory.
        if self.database.in_transaction():
            return None
        with self._school_cache_lock:
            return self._school_cache_generation

    def _advance_school_cache_generation(self):
        with self._school_cache_lock:
            self._school_cache_generation = secrets.token_hex(16)

    @_safe_database
    def init_schema(self, ready=False, *, allow_legacy=False):
        # create_all never upgrades an incompatible existing schema.
        with self.database.connection() as connection:
            names = set(inspect(connection).get_table_names())
            if self.settings.table_prefix + 'documents' in names and not allow_legacy:
                raise DatabaseError('Legacy schema v1 exists; run an explicit migration')
            if self.schema_version == SCHEMA_VERSION and self.meta.name not in names and not allow_legacy:
                legacy = {name for name in names if name.endswith('schema_meta') or name.endswith('storage_meta')}
                if legacy:
                    raise DatabaseError('Legacy database tables exist; run an explicit migration before creating schema v3')
            if self.meta.name in names:
                version = connection.execute(select(self.meta.c.meta_value).where(self.meta.c.meta_key == 'schema_version')).scalar_one_or_none()
                if version not in (None, self.schema_version):
                    raise DatabaseError('Unsupported database schema version; run an explicit migration')
            self.metadata.create_all(connection)
            current = dict(connection.execute(select(self.meta.c.meta_key, self.meta.c.meta_value)).all())
            if not current:
                connection.execute(insert(self.meta), [{'meta_key': 'schema_version', 'meta_value': self.schema_version},
                    {'meta_key': 'ready', 'meta_value': '1' if ready else '0'}])

    @_safe_database
    def _set_meta(self, key, value):
        with self.database.connection() as connection:
            existing = connection.execute(select(self.meta.c.meta_key).where(self.meta.c.meta_key == key).with_for_update()).scalar_one_or_none()
            if existing is None:
                raise DatabaseError('Schema metadata is incomplete; initialize an explicit migration first')
            # MySQL without CLIENT_FOUND_ROWS reports 0 for an unchanged
            # value. That does not mean the row is missing.
            connection.execute(update(self.meta).where(self.meta.c.meta_key == key).values(meta_value=value))

    def mark_pending(self):
        self._set_meta('ready', '0')

    def mark_ready(self):
        self._set_meta('ready', '1')

    def check_ready(self):
        try:
            with self.database.connection() as connection:
                values = dict(connection.execute(select(self.meta.c.meta_key, self.meta.c.meta_value)).all())
            if values.get('schema_version') != self.schema_version or values.get('ready') != '1':
                raise DatabaseError('Database schema is incompatible or migration is incomplete')
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError(f'Database is not initialized ({type(exc).__name__}); run tools/migrate_storage.py init/import') from None
        return True

    @contextmanager
    def transaction(self):
        try:
            with self.database.transaction():
                yield self
        except DBAPIError as exc:
            raise DatabaseError(f'Database transaction failed ({type(exc).__name__})') from None

    @staticmethod
    def _identity(namespace, key):
        if not isinstance(namespace, str) or not namespace or not isinstance(key, str) or not key:
            raise DatabaseError('Invalid storage identity')
        if '\x00' in namespace or '\x00' in key:
            raise DatabaseError('Invalid storage identity')
        return hashlib.sha256((namespace + '\x00' + key).encode()).hexdigest()

    @staticmethod
    def _valid_school_account_name(value):
        return isinstance(value, str) and len(value) >= 4 and value.isascii() and value.isdigit()

    def _has_non_whitespace_text(self, expression):
        # Keep password values inside the database predicate. This is Python's
        # Unicode whitespace set, matching the prior str.strip() eligibility
        # check without projecting any secret into Python. SQLite TRIM accepts
        # a character set; MySQL's TRIM removes a whole string, so use REPLACE
        # there instead. Avoiding nested calls on SQLite prevents parser stack
        # overflow on older SQLite builds.
        whitespace = ('\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\u00a0\u1680'
                      '\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007'
                      '\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000')
        normalized = func.coalesce(expression, literal(''))
        if self.settings.backend == 'sqlite':
            normalized = func.trim(normalized, whitespace)
        else:
            for character in whitespace:
                normalized = func.replace(normalized, character, '')
        return func.length(normalized) > 0

    def _root_school_binding(self):
        key = self.registry.c.record_key
        return (self.registry.c.namespace == 'school_accounts') & (
            key.startswith('user_accounts/', autoescape=True)) & (
            key.endswith('.json', autoescape=True)) & (
            func.instr(func.substr(key, len('user_accounts/') + 1), '/') == 0)

    @staticmethod
    def _binding_credentials(row):
        """Decode only the two mapped credential fields, never an account doc."""
        if row is None:
            return None
        password, device_ua, *metadata = row
        # The four possible mapped binding fields are password, overdue,
        # completed and UA. Only their source/column/type metadata is projected;
        # stored representation strings (including old stats) are never read.
        fields = [dict(zip(('source', 'column', 'type'), metadata[index:index + 3]))
                  for index in range(0, len(metadata), 3) if metadata[index] is not None]
        if any(info.get('source') == 'value' and info.get('column') == 'legacy_value'
               for info in fields):
            return None
        if any(info.get('source') == 'value' for info in fields):
            return {'password': password, 'ua': None}

        def value(source, raw):
            info = next((item for item in fields if item.get('source') == source), None)
            if info is None or raw is None:
                return None
            kind = info.get('type')
            if kind == 'int':
                return int(raw)
            if kind == 'float':
                return float(raw)
            if kind == 'bool':
                return str(raw).lower() not in ('false', '0', 'no', 'off', '')
            return raw

        return {'password': value('password', password), 'ua': value('ua', device_ua)}

    @_safe_database
    def get_school_account_credentials(self, owner_username, school_username, *, include_all=False):
        """Read one target's credentials; callers own the include_all permission.

        A valid owned dictionary/string binding wins even if its password is
        blank. An administrator's fallback follows root binding record-key
        order, then the target's global Config/System fields. Each query filters
        the school first; unrelated school credentials and stats are not read.
        """
        if self.schema_version != SCHEMA_VERSION:
            raise DatabaseError('School account projections require relational schema v3')
        if (not isinstance(owner_username, str) or not owner_username or owner_username == 'guest'
                or not self._valid_school_account_name(school_username)):
            return None

        links = self.entities['account_school_links']
        root_binding = self._root_school_binding()
        metadata = [links.c.fields[index][name].as_string()
                    for index in range(4) for name in ('source', 'column', 'type')]
        binding = select(links.c.password, links.c.device_ua, *metadata).join(
            self.registry, links.c.document_id == self.registry.c.document_id).where(
                links.c.school_username == school_username, root_binding)
        own = binding.where(links.c.owner_username == owner_username).order_by(
            self.registry.c.record_key, links.c.ordinal).limit(1)
        with self.database.connection() as connection:
            credentials = self._binding_credentials(connection.execute(own).first())
            if credentials is not None or not include_all:
                return credentials

            # Scalar null/list/bool bindings are not dictionaries or passwords.
            # Mapped password types let SQL skip false/zero dictionary values
            # just as the old bool(password) eligibility check did.
            source_column = func.coalesce(links.c.fields[0]['column'].as_string(), '')
            password_type = func.coalesce(links.c.fields[0]['type'].as_string(), '')
            usable = self._has_non_whitespace_text(links.c.password) & (
                source_column != 'legacy_value') & case((
                    password_type.in_(('int', 'float', 'bool')),
                    func.lower(links.c.password).not_in(('0', '0.0', '-0.0', 'false')),
                ), else_=True)
            shared = binding.where(links.c.owner_username != owner_username, usable).order_by(
                self.registry.c.record_key, links.c.ordinal).limit(1)
            credentials = self._binding_credentials(connection.execute(shared).first())
            if credentials is not None:
                return credentials

            schools = self.entities['school_accounts']
            password = func.coalesce(
                schools.c.configuration['password'].as_string(),
                schools.c.configuration['Password'].as_string(),
                schools.c.defaults['password'].as_string(),
                schools.c.defaults['Password'].as_string())
            ua = case((func.lower(func.json_type(schools.c.system_parameters)) == 'object',
                func.coalesce(schools.c.system_parameters['ua'].as_string(),
                    schools.c.system_parameters['UA'].as_string(),
                    schools.c.defaults['ua'].as_string(), schools.c.defaults['UA'].as_string())),
                else_=None)
            legacy = select(password, ua).where(
                schools.c.school_username == school_username,
                schools.c.source_key == school_username + '.ini',
                func.lower(func.json_type(schools.c.configuration)) == 'object',
                self._has_non_whitespace_text(password)).limit(1)
            row = connection.execute(legacy).first()
            return {'password': row[0], 'ua': row[1]} if row is not None else None

    @_safe_database
    def list_school_account_names(self, owner_username, *, include_all=False):
        """Project account picker names without rebuilding or returning secrets.

        Owned links are included regardless of password so an account with a
        missing credential remains selectable for manual repair. When
        ``include_all`` is enabled, other owners' nonblank-password links and
        root-level global school configurations with a nonblank Password are
        also included. Results are unique and sorted.
        """
        if self.schema_version != SCHEMA_VERSION:
            raise DatabaseError('School account projections require relational schema v3')
        if not isinstance(owner_username, str) or not owner_username or owner_username == 'guest':
            return []

        links = self.entities['account_school_links']
        root_binding = self._root_school_binding()
        own = select(links.c.school_username.label('school_username')).join(
            self.registry, links.c.document_id == self.registry.c.document_id).where(
            links.c.owner_username == owner_username, root_binding)
        if include_all:
            has_password = self._has_non_whitespace_text(links.c.password)
            shared = select(links.c.school_username.label('school_username')).join(
                self.registry, links.c.document_id == self.registry.c.document_id).where(
                links.c.owner_username != owner_username, root_binding, has_password)

            schools = self.entities['school_accounts']
            password = func.coalesce(
                schools.c.configuration['password'].as_string(),
                schools.c.configuration['Password'].as_string(),
                schools.c.defaults['password'].as_string(),
                schools.c.defaults['Password'].as_string(),
            )
            global_config = select(schools.c.school_username.label('school_username')).where(
                schools.c.source_key.not_like('%/%'),
                func.lower(func.json_type(schools.c.configuration)) == 'object',
                self._has_non_whitespace_text(password),
            )
            names_query = own.union(shared, global_config).order_by('school_username')
        else:
            names_query = own.distinct().order_by('school_username')

        with self.database.connection() as connection:
            rows = connection.execute(names_query).scalars()
            return sorted({name for name in rows if self._valid_school_account_name(name)})

    @staticmethod
    def _statistic_integer(value):
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(str(value).strip())
        except (TypeError, ValueError, OverflowError):
            return None

    @_safe_database
    def get_school_account_stats(self, school_usernames):
        """Read only the two shared stats keys using bounded SQL projections.

        INI [stats] values override matching DEFAULT values. Missing, malformed
        or invalid accounts return zero counts, matching the existing reader.
        This method does not read user-bound credentials or reconstruct a
        compatibility document. Queries are split into groups of 400 names.
        """
        if self.schema_version != SCHEMA_VERSION:
            raise DatabaseError('School account projections require relational schema v3')
        names = list(dict.fromkeys(
            value for value in school_usernames
            if self._valid_school_account_name(value)
        ))
        result = {name: {'overdue_count': 0, 'completed_count': 0} for name in names}
        if not names:
            return result

        schools = self.entities['school_accounts']
        has_stats_section = func.lower(func.json_type(schools.c.statistics)) == 'object'
        projections = (
            schools.c.school_username,
            case((has_stats_section, func.coalesce(
                schools.c.statistics['overdue_count'].as_string(),
                schools.c.defaults['overdue_count'].as_string(), literal('0'))), else_='0'),
            case((has_stats_section, func.coalesce(
                schools.c.statistics['completed_count'].as_string(),
                schools.c.defaults['completed_count'].as_string(), literal('0'))), else_='0'),
        )
        with self.database.connection() as connection:
            for offset in range(0, len(names), 400):
                batch = names[offset:offset + 400]
                query = select(*projections).where(schools.c.school_username.in_(batch))
                for school, overdue, completed in connection.execute(query):
                    parsed = tuple(self._statistic_integer(value) for value in (overdue, completed))
                    # The legacy ConfigParser reader treats either malformed
                    # stats option as a failed stats section and returns zeros.
                    if None not in parsed:
                        result[school] = {'overdue_count': parsed[0], 'completed_count': parsed[1]}
        return result

    def _encode(self, namespace, key, document_id, content):
        from . import identity, domains
        format, value = parse_content(key, content)
        if self.schema_version == '2':
            builder = Builder(document_id, self.definitions)
        else:
            from .codec_v3 import BusinessBuilder
            builder = BusinessBuilder(document_id, self.definitions)
        builder.owner_aliases = dict(getattr(self, 'migration_owner_aliases', {}))
        if namespace == 'school_accounts' and key.startswith('user_accounts/') and not builder.owner_aliases:
            from .validation import aliases_from_usernames
            table = self.entities['users' if self.schema_version == '2' else 'system_accounts']
            with self.database.connection() as connection:
                builder.owner_aliases = aliases_from_usernames(connection.execute(select(table.c.auth_username)).scalars())
        if self.schema_version == '2':
            tree = identity.encode(builder, namespace, key, value)
            if tree is None:
                tree = domains.encode(builder, namespace, key, value)
        else:
            from .codec_v3 import encode
            tree = encode(builder, namespace, key, value)
        if tree is None:
            def leaves(item, path):
                if isinstance(item, dict):
                    return {name: leaves(child, path + '/' + name) for name, child in item.items()}
                if isinstance(item, list):
                    return [leaves(child, path + '/' + str(index)) for index, child in enumerate(item)]
                return builder.scalar('compatibility_values', item, path=path)
            tree = leaves(value, '')
        layout = builder.finish(tree)
        rebuilt = decode_tree(layout, builder.rows)
        if rebuilt != value:
            raise DatabaseError('Domain codec changed source values')
        canonical = render_content(format, rebuilt, canonical=self.schema_version != '2')
        return format, layout, builder.rows, canonical

    def _documents(self, connection, records):
        records = list(records)
        if not records:
            return []
        ids = [record['document_id'] for record in records]
        tables = set(name for record in records for name in record['entity_tables'])
        grouped = {document_id: {} for document_id in ids}
        for name in sorted(tables):
            if name not in self.entities:
                raise DatabaseError('Unknown stored entity table')
            for row in connection.execute(select(self.entities[name]).where(self.entities[name].c.document_id.in_(ids))).mappings():
                grouped[row['document_id']].setdefault(name, []).append(dict(row))
        result = []
        for row in records:
            content = render_content(row['format'], decode_tree(row['layout'], grouped[row['document_id']]),
                                     canonical=self.schema_version != '2')
            # Typed columns are authoritative: SQL updates intentionally change
            # the reconstructed content. The stored digest records the last
            # compatibility write, and verification may flag out-of-band edits.
            result.append(StoredDocument(row['namespace'], row['record_key'], content, row['mtime_ns'], row['revision'],
                                         row['content_sha256'], row['source_sha256']))
        return result

    @_safe_database
    def get(self, namespace, key):
        identity = self._identity(namespace, key)
        with self.database.connection() as connection:
            rows = connection.execute(select(self.registry).where(self.registry.c.document_id == identity)).mappings()
            result = self._documents(connection, rows)
            return result[0] if result else None

    @_safe_database
    def exists(self, namespace, key):
        """Test document identity without loading its layout or domain rows."""
        identity = self._identity(namespace, key)
        with self.database.connection() as connection:
            return connection.execute(select(self.registry.c.document_id).where(
                self.registry.c.document_id == identity)).first() is not None

    @_safe_database
    def keys(self, namespace, prefix=''):
        """List logical paths without reconstructing business documents."""
        with self.database.connection() as connection:
            keys = connection.execute(select(self.registry.c.record_key).where(
                self.registry.c.namespace == namespace).order_by(self.registry.c.record_key)).scalars()
            # Literal matching preserves '%' and '_' in legacy file names.
            return [key for key in keys if key.startswith(prefix)]

    @_safe_database
    def versions(self, namespace, prefix=''):
        """Read compatibility-write versions in one metadata-only query.

        Direct SQL domain updates intentionally do not change these registry
        versions; callers caching rendered values must also refresh periodically.
        """
        with self.database.connection() as connection:
            rows = connection.execute(select(self.registry.c.record_key,
                self.registry.c.mtime_ns, self.registry.c.revision,
                self.registry.c.content_sha256).where(
                self.registry.c.namespace == namespace).order_by(self.registry.c.record_key))
            return [tuple(row) for row in rows if row[0].startswith(prefix)]

    @_safe_database
    def list(self, namespace, prefix=''):
        with self.database.connection() as connection:
            records = connection.execute(select(self.registry).where(self.registry.c.namespace == namespace).order_by(self.registry.c.record_key)).mappings()
            # Python comparison preserves literal '%' and '_' prefix semantics.
            return self._documents(connection, (row for row in records if row['record_key'].startswith(prefix)))

    @_safe_database
    def namespaces(self):
        with self.database.connection() as connection:
            return list(connection.execute(select(self.registry.c.namespace).distinct().order_by(self.registry.c.namespace)).scalars())

    @_safe_database
    def create_many(self, entries):
        """Insert one migration batch atomically, without per-document queries."""
        from collections import defaultdict
        records, entities = [], defaultdict(list)
        for entry in entries:
            document_id = self._identity(entry.namespace, entry.key)
            format, layout, rows, canonical = self._encode(entry.namespace, entry.key, document_id, entry.content)
            records.append(dict(document_id=document_id, namespace=entry.namespace, record_key=entry.key,
                format=format, layout=layout, entity_tables=sorted(rows), revision=1, mtime_ns=entry.mtime_ns,
                content_sha256=hashlib.sha256(canonical).hexdigest(), source_sha256=entry.digest))
            for name, values in rows.items():
                defaults = {field: None for field in self.definitions[name]}
                entities[name].extend(dict(defaults, **row) for row in values)
        if not records:
            return 0
        with self.database.connection() as connection:
            connection.execute(insert(self.registry), records)
            for name, values in entities.items():
                if values:
                    connection.execute(insert(self.entities[name]), values)
            if any(row['namespace'] == 'school_accounts' for row in records):
                self.database.on_commit(self._advance_school_cache_generation)
        return len(records)

    @_safe_database
    def put(self, namespace, key, content, *, mtime_ns=None, expected_revision=ANY_REVISION, create_only=False, source_sha256=None):
        from business_storage import ConflictError
        document_id = self._identity(namespace, key)
        if not isinstance(content, bytes):
            content = bytes(content)
        format, layout, rows, canonical = self._encode(namespace, key, document_id, content)
        digest = hashlib.sha256(canonical).hexdigest()
        try:
            with self.database.connection() as connection:
                existing = connection.execute(select(self.registry).where(self.registry.c.document_id == document_id).with_for_update()).mappings().one_or_none()
                if existing is not None and (create_only or (expected_revision is not ANY_REVISION and expected_revision != existing['revision'])):
                    raise ConflictError('Storage document revision conflict')
                if existing is None and expected_revision is not ANY_REVISION and expected_revision not in (None, 0):
                    raise ConflictError('Storage document no longer exists')
                revision = existing['revision'] + 1 if existing else 1
                stamp = time.time_ns() if mtime_ns is None else mtime_ns
                if existing:
                    connection.execute(delete(self.registry).where(self.registry.c.document_id == document_id))
                connection.execute(insert(self.registry).values(document_id=document_id,namespace=namespace,record_key=key,format=format,
                    layout=layout,entity_tables=sorted(rows),revision=revision,mtime_ns=stamp,content_sha256=digest,source_sha256=source_sha256))
                for name, values in rows.items():
                    # Heterogeneous optional fields must not be dropped by an
                    # executemany statement derived from the first row.
                    columns = self.definitions[name]
                    normalized = [dict({field: None for field in columns}, **row) for row in values]
                    if normalized:
                        connection.execute(insert(self.entities[name]), normalized)
                if namespace == 'school_accounts':
                    self.database.on_commit(self._advance_school_cache_generation)
        except IntegrityError:
            raise ConflictError('Database entity uniqueness conflict; no partial write committed') from None
        return StoredDocument(namespace, key, canonical, stamp, revision, digest, source_sha256)

    @_safe_database
    def delete(self, namespace, key, *, expected_revision=ANY_REVISION):
        from business_storage import ConflictError
        document_id = self._identity(namespace, key)
        with self.database.connection() as connection:
            row = connection.execute(select(self.registry.c.revision).where(self.registry.c.document_id == document_id).with_for_update()).one_or_none()
            if row is None:
                return False
            if expected_revision is not ANY_REVISION and expected_revision != row[0]:
                raise ConflictError('Storage document revision conflict')
            connection.execute(delete(self.registry).where(self.registry.c.document_id == document_id))
            if namespace == 'school_accounts':
                self.database.on_commit(self._advance_school_cache_generation)
            return True
