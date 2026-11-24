"""Business-key schema for a separate v4 migration target."""
import time

from sqlalchemy import (
    JSON, BigInteger, Boolean, CheckConstraint, Column, ForeignKey, Index,
    Integer, MetaData, String, Table, Text, inspect, text,
)
from sqlalchemy.dialects.mysql import VARBINARY
from sqlalchemy.types import TypeDecorator

from .engine import DatabaseError
from .schema_v4_access import add_access_tables
from .schema_v4_finance import add_finance_tables
from .schema_v4_operations import add_operation_tables


SCHEMA_VERSION = '4'


class ExactIdentifier(TypeDecorator):
    """Compare identifiers byte-for-byte on both supported engines."""

    impl = String
    cache_ok = True

    def __init__(self, length):
        self.length = length
        super().__init__(length=length)

    def load_dialect_impl(self, dialect):
        if dialect.name in ('mysql', 'mariadb'):
            return dialect.type_descriptor(VARBINARY(self.length * 4))
        return dialect.type_descriptor(String(self.length, collation='BINARY'))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, str) or len(value) > self.length or '\x00' in value:
            raise ValueError(f'Identity must be text of at most {self.length} characters without NUL')
        if dialect.name in ('mysql', 'mariadb'):
            return value.encode('utf-8')
        return value

    def process_result_value(self, value, dialect):
        return value.decode('utf-8') if isinstance(value, bytes) else value


def make_schema_v4():
    metadata = MetaData()
    id_type = BigInteger().with_variant(Integer(), 'sqlite')
    identifier = ExactIdentifier
    options = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}

    Table('schema_migrations', metadata,
        Column('version', Integer, primary_key=True, autoincrement=False),
        Column('applied_at_ms', BigInteger, nullable=False),
        **options)

    Table('school_accounts', metadata,
        Column('id', id_type, primary_key=True),
        Column('school_username', identifier(255), nullable=False, unique=True),
        Column('tag', Text),
        **options)

    system_accounts = Table('system_accounts', metadata,
        Column('id', id_type, primary_key=True),
        Column('auth_username', identifier(200), nullable=False, unique=True),
        Column('password_hash', Text, nullable=False),
        Column('permission_group_id', id_type, ForeignKey('permission_groups.id', ondelete='RESTRICT')),
        Column('phone', String(32)),
        Column('nickname', String(200)),
        Column('avatar_url', Text),
        Column('banned', Boolean, nullable=False, server_default=text('0')),
        Column('available_runs', BigInteger, nullable=False, server_default=text('0')),
        Column('max_sessions', Integer),
        Column('two_factor_enabled', Boolean, nullable=False, server_default=text('0')),
        Column('two_factor_secret', Text),
        Column('last_used_school_account_id', id_type, ForeignKey('school_accounts.id', ondelete='SET NULL')),
        Column('theme', String(64)),
        Column('theme_config', JSON),
        Column('account_cancellation', JSON),
        Column('created_at_ms', BigInteger),
        Column('last_login_at_ms', BigInteger),
        Column('last_login_ip', String(45)),
        Column('last_login_city', String(200)),
        Column('revision', BigInteger, nullable=False, server_default=text('1')),
        CheckConstraint('available_runs >= -1', name='ck_system_accounts_available_runs'),
        **options)
    Index('ix_system_accounts_phone', system_accounts.c.phone)

    links = Table('account_school_links', metadata,
        Column('system_account_id', id_type, ForeignKey('system_accounts.id', ondelete='CASCADE'), primary_key=True),
        Column('school_account_id', id_type, ForeignKey('school_accounts.id', ondelete='CASCADE'), primary_key=True),
        Column('password', Text),
        Column('device_ua', Text),
        Column('revision', BigInteger, nullable=False, server_default=text('1')),
        **options)
    Index('ix_account_school_links_school', links.c.school_account_id)

    Table('school_account_information', metadata,
        Column('school_account_id', id_type, ForeignKey('school_accounts.id', ondelete='CASCADE'), primary_key=True),
        Column('user_info', JSON),
        Column('department_info', JSON),
        Column('updated_at_ms', BigInteger),
        **options)

    Table('school_account_settings', metadata,
        Column('school_account_id', id_type, ForeignKey('school_accounts.id', ondelete='CASCADE'), primary_key=True),
        Column('run_parameters', JSON),
        Column('device_parameters', JSON),
        Column('account_options', JSON),
        Column('defaults', JSON),
        Column('completed_count', BigInteger),
        Column('overdue_count', BigInteger),
        Column('revision', BigInteger, nullable=False, server_default=text('1')),
        **options)

    Table('school_account_legacy_credentials', metadata,
        Column('school_account_id', id_type, ForeignKey('school_accounts.id', ondelete='CASCADE'), primary_key=True),
        Column('password', Text, nullable=False),
        Column('device_ua', Text),
        **options)

    for add_tables in (add_access_tables, add_finance_tables, add_operation_tables):
        add_tables(metadata, id_type=id_type, identifier=identifier, table_options=options)
    return metadata


def create_schema_v4(connection):
    """Create v4 in an empty target without declaring it ready for runtime."""
    inspector = inspect(connection)
    if inspector.get_table_names() or inspector.get_view_names():
        raise DatabaseError('v4 schema creation requires a separate, empty database')
    metadata = make_schema_v4()
    metadata.create_all(connection, checkfirst=False)
    connection.execute(metadata.tables['schema_migrations'].insert(), {
        'version': int(SCHEMA_VERSION), 'applied_at_ms': time.time_ns() // 1_000_000,
    })
    return metadata
