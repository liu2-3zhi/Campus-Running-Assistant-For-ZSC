"""Settings, content, and operational tables for the v4 relational schema."""

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Float, ForeignKey, Index, Integer, JSON,
    Numeric, Table, Text,
)
from sqlalchemy.dialects.mysql import LONGTEXT


def add_operation_tables(metadata, *, id_type, identifier, table_options):
    text = Text().with_variant(LONGTEXT(), 'mysql', 'mariadb')
    numeric = Float(53).with_variant(Numeric(65, 30), 'mysql', 'mariadb')
    json = JSON(none_as_null=True)

    settings = Table(
        'system_settings', metadata,
        Column('scope', identifier(128), primary_key=True),
        Column('setting_key', identifier(255), primary_key=True),
        Column('value_kind', identifier(16), nullable=False),
        Column('value_text', text),
        Column('value_json', json),
        # Empty strings are stored as text. JSON.NULL represents an explicit JSON null.
        CheckConstraint(
            "(value_kind = 'text' AND value_text IS NOT NULL AND value_json IS NULL) OR "
            "(value_kind = 'json' AND value_text IS NULL AND value_json IS NOT NULL)",
            name='ck_system_settings_value',
        ),
        **table_options,
    )

    sms = Table(
        'sms_records', metadata,
        Column('record_key', identifier(128), primary_key=True),
        Column('system_account_id', id_type, ForeignKey('system_accounts.id', ondelete='SET NULL')),
        Column('auth_username', identifier(200)),
        Column('username', identifier(200)),
        Column('session_id', identifier(64)),
        Column('phone', identifier(64)),
        Column('scene', identifier(64)),
        Column('status', identifier(32)),
        Column('provider', identifier(64)),
        Column('response_code', identifier(64)),
        Column('response_message', text),
        Column('source', identifier(64)),
        Column('ip', identifier(64)),
        Column('timestamp', numeric),
        Column('datetime', identifier(48)),
        **table_options,
    )
    Index('ix_sms_records_timestamp', sms.c.timestamp)
    Index('ix_sms_records_datetime', sms.c.datetime, sms.c.timestamp)
    Index('ix_sms_records_phone', sms.c.phone, sms.c.timestamp)
    Index('ix_sms_records_username', sms.c.auth_username, sms.c.timestamp)
    Index('ix_sms_records_scene_status', sms.c.scene, sms.c.status, sms.c.timestamp)

    messages = Table(
        'messages', metadata,
        Column('message_id', identifier(64), primary_key=True),
        Column('system_account_id', id_type, ForeignKey('system_accounts.id', ondelete='SET NULL')),
        Column('auth_username', identifier(200)),
        Column('content', text, nullable=False),
        Column('nickname', text),
        Column('email', text),
        Column('is_guest', Boolean),
        Column('timestamp', numeric),
        Column('ip', identifier(64)),
        **table_options,
    )
    Index('ix_messages_timestamp', messages.c.timestamp)
    Index('ix_messages_username', messages.c.auth_username, messages.c.timestamp)

    reminders = Table(
        'reminders', metadata,
        Column('reminder_id', identifier(64), primary_key=True),
        Column('title', text, nullable=False),
        Column('message', text, nullable=False),
        Column('start_time', identifier(16)),
        Column('end_time', identifier(16)),
        Column('enabled', Boolean),
        Column('allow_guest_view', Boolean),
        Column('created_at', numeric),
        Column('updated_at', numeric),
        **table_options,
    )
    Index('ix_reminders_enabled_window', reminders.c.enabled, reminders.c.start_time, reminders.c.end_time)

    tasks = Table(
        'background_tasks', metadata,
        # The task manager stores one current snapshot per session.
        Column('session_id', identifier(64),
               ForeignKey('account_sessions.session_id', ondelete='CASCADE'), primary_key=True),
        Column('execution_id', identifier(64)),
        Column('status', identifier(32)),
        Column('map_provider', identifier(64)),
        Column('auto_generate', Boolean),
        Column('start_time', numeric),
        Column('last_update', numeric),
        Column('total_tasks', Integer),
        Column('completed_tasks', Integer),
        Column('current_task_index', Integer),
        Column('progress_percent', numeric),
        Column('current_task_progress', numeric),
        Column('processed_points', Integer),
        Column('total_points', Integer),
        Column('task_indices', json),
        Column('details', json),
        **table_options,
    )
    Index('ix_background_tasks_execution', tasks.c.execution_id)
    Index('ix_background_tasks_status_update', tasks.c.status, tasks.c.last_update)

    image_state = Table(
        'background_image_state', metadata,
        Column('id', Integer, primary_key=True, autoincrement=False),
        Column('schema_version', Integer),
        Column('next_revision', id_type),
        Column('assignments', json),
        Column('bundles', json),
        Column('identity_bindings', json),
        Column('guest_bindings', json),
        Column('auth_claims', json),
        CheckConstraint('id = 1', name='ck_background_image_state_singleton'),
        **table_options,
    )

    archives = Table(
        'deleted_account_archives', metadata,
        Column('archive_id', identifier(64), primary_key=True),
        Column('auth_username', identifier(200)),
        Column('deleted_at', identifier(48)),
        Column('legacy_archive_id', identifier(255)),
        Column('source_namespace', identifier(64)),
        Column('source_key', text),
        Column('snapshot', json, nullable=False),
        **table_options,
    )
    Index('ix_deleted_account_archives_username', archives.c.auth_username, archives.c.deleted_at)
    Index('ix_deleted_account_archives_deleted_at', archives.c.deleted_at)

    return {
        table.name: table
        for table in (settings, sms, messages, reminders, tasks, image_state, archives)
    }
