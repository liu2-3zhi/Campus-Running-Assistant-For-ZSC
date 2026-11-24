"""Permission, session, and authentication token tables for schema v4."""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, Float, ForeignKey, Index, JSON, Numeric, Table, Text


def add_access_tables(metadata, *, id_type, identifier, table_options):
    # Preserve subsecond lifecycle values when migrating across database engines.
    epoch = Float(53).with_variant(Numeric(65, 30), "mysql", "mariadb")
    revision = BigInteger()

    Table(
        "permission_groups", metadata,
        Column("id", id_type, primary_key=True, autoincrement=True),
        Column("name", identifier(200), nullable=False, unique=True),
        Column("display_name", Text),
        Column("is_system", Boolean, nullable=False, server_default="0"),
        **table_options,
    )
    Table(
        "group_permissions", metadata,
        Column("permission_group_id", id_type, ForeignKey("permission_groups.id", ondelete="CASCADE"),
               primary_key=True),
        Column("permission", identifier(200), primary_key=True),
        Column("enabled", Boolean, nullable=False),
        **table_options,
    )
    Table(
        "account_permission_overrides", metadata,
        Column("system_account_id", id_type, ForeignKey("system_accounts.id", ondelete="CASCADE"),
               primary_key=True),
        Column("permission", identifier(200), primary_key=True),
        Column("enabled", Boolean, nullable=False),
        **table_options,
    )
    Table(
        "account_sessions", metadata,
        Column("session_id", identifier(64), primary_key=True),
        Column("system_account_id", id_type, ForeignKey("system_accounts.id", ondelete="CASCADE")),
        Column("auth_group_at_login", identifier(200)),
        Column("created_at", epoch, nullable=False),
        Column("last_accessed", epoch, nullable=False),
        Column("last_saved", epoch, nullable=False),
        Column("is_guest", Boolean, nullable=False, server_default="0"),
        Column("is_authenticated", Boolean, nullable=False, server_default="0"),
        Column("school_account_logged_in", Boolean, nullable=False, server_default="0"),
        Column("is_multi_account_mode", Boolean, nullable=False, server_default="0"),
        Column("is_offline_mode", Boolean, nullable=False, server_default="0"),
        Column("device_ua", Text),
        Column("snapshot", JSON, nullable=False),
        Column("revision", revision, nullable=False, server_default="1"),
        Index("ix_account_sessions_owner_activity", "system_account_id", "last_accessed"),
        Index("ix_account_sessions_last_accessed", "last_accessed"),
        **table_options,
    )

    # System tokens serve every session owned by the account. Guest tokens
    # follow the live session lifetime independently of its persisted snapshot.
    for table_name, scope in (
        ("system_account_tokens",
         Column("system_account_id", id_type, ForeignKey("system_accounts.id", ondelete="CASCADE"),
                primary_key=True, autoincrement=False)),
        ("guest_session_tokens", Column("session_id", identifier(64), primary_key=True)),
    ):
        Table(
            table_name, metadata,
            scope,
            Column("token_hash", identifier(64), nullable=False, unique=True),
            Column("token_value", Text, nullable=False),
            Column("created_at", epoch, nullable=False),
            Column("last_activity", epoch, nullable=False),
            Column("expires_at", epoch, nullable=False),
            Column("revision", revision, nullable=False, server_default="1"),
            Index(f"ix_{table_name}_expires_at", "expires_at"),
            **table_options,
        )
