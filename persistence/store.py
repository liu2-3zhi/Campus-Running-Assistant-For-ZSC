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
import time
from functools import wraps

from sqlalchemy import delete, insert, select, update, inspect, event
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


def render_content(format, value):
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

    def __init__(self, settings, connection_factory=None):
        self.settings = settings
        self.database = Database(settings, connection_factory)
        if settings.backend == 'sqlite':
            @event.listens_for(self.database.engine, 'connect')
            def register_digest(connection, _record):
                connection.create_function('application_sha256', 1,
                    lambda value: hashlib.sha256(value.encode('utf-8')).hexdigest() if value is not None else None, deterministic=True)
        self.metadata, self.registry, self.meta, self.entities, self.definitions = make_schema(settings.table_prefix)

    @_safe_database
    def init_schema(self, ready=False):
        # create_all never upgrades an incompatible existing schema.
        with self.database.connection() as connection:
            names = set(inspect(connection).get_table_names())
            if self.settings.table_prefix + 'documents' in names:
                raise DatabaseError('Legacy schema v1 exists; export it before initializing relational schema v2')
            if self.meta.name in names:
                version = connection.execute(select(self.meta.c.meta_value).where(self.meta.c.meta_key == 'schema_version')).scalar_one_or_none()
                if version not in (None, SCHEMA_VERSION):
                    raise DatabaseError('Unsupported database schema version; run an explicit migration')
            self.metadata.create_all(connection)
            current = dict(connection.execute(select(self.meta.c.meta_key, self.meta.c.meta_value)).all())
            if not current:
                connection.execute(insert(self.meta), [{'meta_key': 'schema_version', 'meta_value': SCHEMA_VERSION},
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
            if values.get('schema_version') != SCHEMA_VERSION or values.get('ready') != '1':
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

    def _encode(self, namespace, key, document_id, content):
        from . import identity, domains
        format, value = parse_content(key, content)
        builder = Builder(document_id, self.definitions)
        builder.owner_aliases = dict(getattr(self, 'migration_owner_aliases', {}))
        if namespace == 'school_accounts' and key.startswith('user_accounts/') and not builder.owner_aliases:
            from .validation import aliases_from_usernames
            table = self.entities['users']
            with self.database.connection() as connection:
                builder.owner_aliases = aliases_from_usernames(connection.execute(select(table.c.auth_username)).scalars())
        tree = identity.encode(builder, namespace, key, value)
        if tree is None:
            tree = domains.encode(builder, namespace, key, value)
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
        canonical = render_content(format, rebuilt)
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
            content = render_content(row['format'], decode_tree(row['layout'], grouped[row['document_id']]))
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
            return True
