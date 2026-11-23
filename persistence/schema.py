"""Versioned relational schema shared by SQLite and MySQL."""
from __future__ import annotations

import hashlib
from sqlalchemy import (BigInteger, Boolean, Column, Computed, Float, ForeignKey, Index,
                        Integer, JSON, MetaData, Numeric, String, Table, Text)
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import ColumnElement

SCHEMA_VERSION = '2'


class FullValueDigest(ColumnElement):
    type = String(64)
    inherit_cache = False

    def __init__(self, columns):
        self.columns = tuple(columns)


def _digest_expression(element, compiler, function, **kw):
    names = [compiler.process(column, **kw) for column in element.columns]
    nulls = ' OR '.join(name + ' IS NULL' for name in names)
    values = 'json_array(' + ','.join(names) + ')'
    digest = 'sha2(' + values + ',256)' if function == 'mysql' else 'application_sha256(' + values + ')'
    return 'CASE WHEN ' + nulls + ' THEN NULL ELSE ' + digest + ' END'


@compiles(FullValueDigest, 'sqlite')
def _sqlite_digest(element, compiler, **kw):
    return _digest_expression(element, compiler, 'sqlite', **kw)


@compiles(FullValueDigest, 'mysql')
def _mysql_digest(element, compiler, **kw):
    return _digest_expression(element, compiler, 'mysql', **kw)


def declarations():
    from . import identity, domains
    tables = {}
    indexes = []
    for module in (identity, domains):
        for name, fields in module.TABLES.items():
            if name in tables:
                raise ValueError('Duplicate domain table: ' + name)
            tables[name] = fields
        indexes.extend(getattr(module, 'INDEXES', []))
    tables['compatibility_values'] = {'path': 'text', 'value': 'json'}
    return tables, indexes


def make_schema(prefix='app_'):
    definitions, indexes = declarations()
    if any(len(prefix + name) > 64 for name in definitions):
        from .engine import DatabaseConfigurationError
        raise DatabaseConfigurationError('Table prefix exceeds the relational schema identifier limit')
    metadata = MetaData()
    # Identifiers are compared byte-for-byte on both database engines.
    identifier = String(64).with_variant(mysql.VARCHAR(64, collation='ascii_bin', charset='ascii'), 'mysql')
    label = String(128).with_variant(mysql.VARCHAR(128, collation='utf8mb4_bin'), 'mysql')
    long_text = Text().with_variant(mysql.LONGTEXT(collation='utf8mb4_bin'), 'mysql')
    registry = Table(prefix + 'document_registry', metadata,
        Column('document_id', identifier, primary_key=True),
        Column('namespace', label, nullable=False, index=True),
        Column('record_key', long_text, nullable=False),
        Column('format', String(16), nullable=False),
        Column('layout', JSON, nullable=False),
        Column('entity_tables', JSON, nullable=False),
        Column('revision', BigInteger, nullable=False),
        Column('mtime_ns', BigInteger, nullable=False),
        Column('content_sha256', String(64), nullable=False),
        Column('source_sha256', String(64)),
        mysql_charset='utf8mb4', mysql_engine='InnoDB')
    meta = Table(prefix + 'schema_meta', metadata,
        Column('meta_key', String(64), primary_key=True),
        Column('meta_value', String(256), nullable=False),
        mysql_charset='utf8mb4', mysql_engine='InnoDB')
    entities = {}
    # Timestamps/progress are decimal numerics. Sending an approximate DOUBLE
    # literal to MySQL can change the last binary digit even at precision 53.
    numeric = Float(53).with_variant(Numeric(65, 30), 'mysql').with_variant(Numeric(65, 30), 'mariadb')
    kinds = {'text': long_text, 'int': BigInteger, 'money': BigInteger, 'float': numeric, 'bool': Boolean, 'json': JSON}
    for name, fields in definitions.items():
        entities[name] = Table(prefix + name, metadata,
            Column('row_id', identifier, primary_key=True),
            Column('document_id', identifier, ForeignKey(registry.c.document_id, ondelete='CASCADE'), nullable=False, index=True),
            Column('ordinal', Integer, nullable=False),
            Column('extra', JSON, nullable=False), Column('fields', JSON, nullable=False),
            *(Column(field, kinds[kind]) for field, kind in fields.items()),
            mysql_charset='utf8mb4', mysql_engine='InnoDB')
    for name, columns, unique in indexes:
        table = entities[name]
        suffix = hashlib.sha256((name + ':'.join(columns)).encode()).hexdigest()[:12]
        lengths = {column: 191 for column in columns if definitions[name][column] == 'text'}
        if unique:
            # A prefix index cannot enforce full identifier uniqueness. The
            # generated digest changes on direct SQL updates as well as API
            # writes, without truncating case-sensitive identifiers.
            name = '_uq_' + suffix
            table.append_column(Column(name, identifier, Computed(FullValueDigest([table.c[column] for column in columns]), persisted=True)))
            Index(prefix + 'ix_' + suffix, table.c[name], unique=True)
        else:
            Index(prefix + 'ix_' + suffix, *(table.c[column] for column in columns), mysql_length=lengths or None)
    return metadata, registry, meta, entities, definitions
