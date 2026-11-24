"""Offline upgrades must preserve semantics and constrain destructive cleanup."""
from dataclasses import replace
import os
import uuid
import json

import pytest
from sqlalchemy import delete, event, inspect, text, update
from sqlalchemy.exc import OperationalError

import storage_migration as migration
from business_storage import StoragePolicy
from persistence.engine import DatabaseError
from persistence.engine import DatabaseSettings
from persistence.store import RelationalStore
from test_storage_migration import MemoryStore


class LegacyRelationalSource(MemoryStore):
    def __init__(self):
        super().__init__()
        self.ready = True
        self.broken = {}

    def keys(self, namespace, prefix=''):
        return sorted(key for ns, key in self.documents if ns == namespace and key.startswith(prefix))

    def get(self, namespace, key):
        if (namespace, key) in self.broken:
            raise self.broken[namespace, key]
        return super().get(namespace, key)


def test_v3_cli_rejects_a_target_table_prefix_before_opening_database(tmp_path, monkeypatch):
    monkeypatch.setenv('MYSQL_TABLE_PREFIX', 'app_')
    opened = []
    def factory(settings):
        opened.append(settings)
        raise AssertionError('a prefixed v3 destination must not be opened')
    assert migration.main(['--root', str(tmp_path), '--backend', 'sqlite', 'import', '--stopped'],
                          store_factory=factory) == 2
    assert opened == []


def source_with_values():
    source = LegacyRelationalSource()
    source.put('settings', 'messages.json', b'{"bool":true,"int":1,"string":"001","null":null}')
    source.put('sessions', 'healthy.json', b'{"session_id":"session-ok"}')
    return source


def test_upgrade_reads_current_typed_values_instead_of_rejecting_old_rendered_digest():
    source = source_with_values()
    identity = 'settings', 'messages.json'
    # A legitimate direct SQL update changes typed fields without changing the
    # v2 compatibility-write checksum. The rendered current value is authority.
    source.documents[identity] = replace(source.documents[identity], digest='old-last-write-digest')
    target = MemoryStore()
    result = migration.import_relational_store(source, target)
    assert result.imported == 2
    assert result.verification.ok
    assert migration.verify_relational_store(source, target).ok
    value = json.loads(target.get(*identity).content)
    assert type(value['bool']) is bool and type(value['int']) is int
    assert value['string'] == '001' and value['null'] is None
    assert source.documents[identity].digest == 'old-last-write-digest'


def test_v2_json_key_order_changes_do_not_count_as_business_data_changes():
    class ReorderedSource(LegacyRelationalSource):
        reads = 0
        def get(self, namespace, key):
            document = super().get(namespace, key)
            if document is None:
                return None
            self.reads += 1
            content = b'{"a":true,"b":1}' if self.reads % 2 else b'{"b":1,"a":true}'
            return replace(document, content=content)
    source = ReorderedSource()
    source.put('settings', 'messages.json', b'{"a":true,"b":1}')
    target = MemoryStore()
    result = migration.import_relational_store(source, target)
    assert result.verification.ok
    assert migration.verify_relational_store(source, target).ok


def test_corrupt_session_index_is_never_skipped_as_an_ordinary_session():
    source = LegacyRelationalSource()
    source.put('sessions', '_index.json', b'{}')
    source.broken['sessions', '_index.json'] = ValueError('Missing stored entity reference')
    with pytest.raises(migration.MigrationError):
        migration.import_relational_store(source, MemoryStore(), skip_corrupt_sessions=True)


def test_corrupt_session_blocks_upgrade_without_explicit_skip():
    source = source_with_values()
    source.broken['sessions', 'healthy.json'] = ValueError('Missing stored entity reference')
    target = MemoryStore()
    with pytest.raises(migration.MigrationError, match='sessions/healthy.json'):
        migration.import_relational_store(source, target)
    assert target.documents == {} and not target.ready


def test_explicit_corrupt_session_skip_keeps_other_data_and_reports_location():
    source = source_with_values()
    source.broken['sessions', 'healthy.json'] = ValueError('Missing stored entity reference')
    target = MemoryStore()
    result = migration.import_relational_store(source, target, skip_corrupt_sessions=True)
    assert result.verification.ok and result.imported == 1
    assert set(target.documents) == {('settings', 'messages.json')}
    assert any(issue['code'] == 'skipped_corrupt_session' and issue['key'] == 'healthy.json'
               for issue in result.issues)


def test_relational_source_change_during_import_prevents_ready_marker():
    source = source_with_values()
    class ChangingTarget(MemoryStore):
        changed = False
        def put(self, *args, **kwargs):
            document = super().put(*args, **kwargs)
            if not self.changed:
                self.changed = True
                identity = 'settings', 'messages.json'
                source.documents[identity] = replace(source.documents[identity], content=b'{"changed":true}')
            return document
    target = ChangingTarget()
    with pytest.raises(migration.VerificationError):
        migration.import_relational_store(source, target)
    assert not target.ready


@pytest.mark.parametrize('namespace', ['system_accounts', 'payment_orders', 'sessions'])
def test_skip_corrupt_sessions_never_swallows_database_errors_or_account_and_order_corruption(namespace):
    source = LegacyRelationalSource()
    source.put(namespace, 'record.json', b'{}')
    failure = DatabaseError('connection unavailable') if namespace == 'sessions' else ValueError('Missing stored entity reference')
    source.broken[namespace, 'record.json'] = failure
    target = MemoryStore()
    with pytest.raises((DatabaseError, migration.MigrationError)):
        migration.import_relational_store(source, target, skip_corrupt_sessions=True)
    assert target.documents == {}


def test_removing_verified_sources_only_deletes_managed_business_files(tmp_path):
    accounts = tmp_path / 'school_accounts'
    accounts.mkdir()
    source = accounts / '10001.ini'
    source.write_bytes(b'[Config]\nUsername=10001\n')
    image = accounts / 'avatar.png'
    image.write_bytes(b'image')
    logs = tmp_path / 'logs'
    logs.mkdir()
    audit = logs / 'audit.json'
    audit.write_text('outside business scope', encoding='utf-8')
    policy = StoragePolicy(tmp_path, {})
    target = MemoryStore()
    result = migration.import_documents(policy, target, remove_source=True)
    assert result.verification.ok
    assert not source.exists()
    assert image.read_bytes() == b'image' and audit.exists()
    assert target.get('school_accounts', '10001.ini') is not None
    assert not list(tmp_path.rglob('*.bak'))


def test_source_removal_rechecks_all_files_before_deleting_any(tmp_path):
    folder = tmp_path / 'school_accounts'
    folder.mkdir()
    first, last = folder / 'a.json', folder / 'z.json'
    first.write_text('{}', encoding='utf-8')
    last.write_text('{}', encoding='utf-8')
    policy = StoragePolicy(tmp_path, {})
    target = MemoryStore()
    migration.import_documents(policy, target)
    plan = migration.build_plan(policy)
    last.write_text('[]', encoding='utf-8')
    with pytest.raises(migration.VerificationError):
        migration.remove_source_files(policy, target, plan)
    assert first.exists() and last.exists()


def test_source_removal_refuses_configured_paths_outside_root(tmp_path):
    root, outside = tmp_path / 'app', tmp_path / 'external'
    root.mkdir(); outside.mkdir()
    path = outside / '10001.ini'
    path.write_bytes(b'[Config]\nUsername=10001\n')
    policy = StoragePolicy(root, {'System': {'school_accounts_dir': str(outside)}})
    target = MemoryStore()
    migration.import_documents(policy, target)
    with pytest.raises(migration.MigrationError, match='root'):
        migration.remove_source_files(policy, target)
    assert path.exists()


def test_source_removal_refuses_files_replaced_with_symlinks(tmp_path):
    accounts = tmp_path / 'school_accounts'
    accounts.mkdir()
    path, outside = accounts / 'a.json', tmp_path / 'outside.json'
    path.write_bytes(b'{}'); outside.write_bytes(b'{}')
    policy = StoragePolicy(tmp_path, {})
    target = MemoryStore()
    migration.import_documents(policy, target)
    plan = migration.build_plan(policy)
    path.unlink()
    try:
        path.symlink_to(outside)
    except OSError:
        pytest.skip('symlink creation unavailable')
    with pytest.raises(migration.MigrationError):
        migration.remove_source_files(policy, target, plan)
    assert path.is_symlink() and outside.exists()


def test_failed_import_never_removes_source(tmp_path):
    folder = tmp_path / 'school_accounts'
    folder.mkdir()
    path = folder / 'a.json'
    path.write_bytes(b'{}')
    target = MemoryStore(); target.fail_key = 'a.json'
    with pytest.raises(RuntimeError):
        migration.import_documents(StoragePolicy(tmp_path, {}), target, remove_source=True)
    assert path.read_bytes() == b'{}'


def test_cli_exposes_relational_upgrade_and_explicit_cleanup_flags():
    args = migration._parser().parse_args(['--source', 'relational-v2', '--source-backend', 'sqlite',
        '--source-sqlite-path', 'legacy.sqlite3', '--legacy-table-prefix', 'app_',
        'import', '--stopped', '--skip-corrupt-sessions', '--drop-legacy'])
    assert args.source == 'relational-v2' and args.drop_legacy and args.skip_corrupt_sessions
    args = migration._parser().parse_args(['import', '--stopped', '--remove-source'])
    assert args.remove_source


def test_sms_log_uses_database_config_after_source_config_is_removed(tmp_path):
    config = {'Logging': {'log_dir': 'custom-logs'}}
    configs = tmp_path / 'configs'; configs.mkdir()
    path = configs / 'config.json'; path.write_text(json.dumps(config), encoding='utf-8')
    logs = tmp_path / 'custom-logs'; logs.mkdir()
    sms = logs / 'sms_history.jsonl'
    sms.write_text('{"phone":"fixture-phone","status":"success"}\n', encoding='utf-8')
    policy = StoragePolicy(tmp_path, config)
    path.unlink()
    plan = migration.build_plan(policy)
    assert len(plan.entries) == 1
    assert plan.entries[0].namespace == 'sms_records'
    assert plan.entries[0].path == sms


def test_sms_duplicates_remain_distinct_and_cleanup_preserves_original_log(tmp_path):
    logs = tmp_path / 'logs'; logs.mkdir()
    sms = logs / 'sms_history.jsonl'
    payload = {'phone': 'fixture-phone', 'content': 'historical-message', 'success': True}
    line = json.dumps(payload) + '\n'
    sms.write_text(line * 2, encoding='utf-8')
    policy = StoragePolicy(tmp_path, {})
    target = MemoryStore()
    result = migration.import_documents(policy, target, remove_source=True)
    assert result.imported == 2 and result.verification.ok
    assert target.namespaces() == ['sms_records']
    assert len(target.documents) == 2
    assert all(json.loads(record.content) == payload for record in target.documents.values())
    assert sms.read_text(encoding='utf-8') == line * 2


def test_sms_database_records_export_and_reimport_with_stable_keys_and_types(tmp_path):
    source = MemoryStore(); source.ready = True
    content = b'{"phone":"fixture-phone","success":true,"attempt":1,"provider_result":null}'
    source.put('sms_records', 'fixture-message.json', content)
    root = tmp_path / 'source'; root.mkdir()
    target = tmp_path / 'export'
    result = migration.export_documents(StoragePolicy(root, {}), source, target)
    assert result.exported == 1
    assert (target / 'sms_records/fixture-message.json').read_bytes() == content
    restored = MemoryStore()
    migration.import_documents(StoragePolicy(target, {}), restored)
    assert restored.get('sms_records', 'fixture-message.json').content == content


def test_invalid_sms_history_aborts_before_constructing_destination(tmp_path, capsys):
    logs = tmp_path / 'logs'; logs.mkdir()
    sms = logs / 'sms_history.jsonl'
    sms.write_text('{"phone":"fixture-phone"}\ninvalid\n', encoding='utf-8')
    def forbidden(settings):
        raise AssertionError('source must be validated before opening the destination')
    result = migration.main(['--root', str(tmp_path), '--backend', 'sqlite', 'import', '--stopped'],
                            store_factory=forbidden)
    assert result == 2
    assert 'AssertionError' not in capsys.readouterr().err
    assert sms.is_file()
    assert not (tmp_path / 'data').exists()


@pytest.fixture
def legacy_v2(tmp_path, monkeypatch):
    monkeypatch.delenv('MYSQL_TABLE_PREFIX', raising=False)
    monkeypatch.delenv('APP_STORAGE_BACKEND', raising=False)
    settings = DatabaseSettings(root=tmp_path, table_prefix='app_')
    store = RelationalStore(settings, schema_version='2')
    store.init_schema(ready=True)
    store.put('system_accounts', 'owner.json', b'{"auth_username":"owner","nickname":"before","group":"user"}')
    store.put('school_accounts', 'user_accounts/owner.json', b'{"10001":{"password":"fixture","ua":"owner-UA"}}')
    with store.database.connection() as connection:
        connection.execute(update(store.entities['users']).values(nickname='updated-from-SQL'))
        connection.execute(text('CREATE TABLE unrelated_notes (note VARCHAR(64))'))
    monkeypatch.setenv('SQLITE_DATABASE_PATH', str(settings.sqlite_path))
    yield store
    store.database.dispose()


@pytest.mark.parametrize('drop', [False, True])
def test_real_same_file_v2_to_v3_upgrade_keeps_typed_values_and_only_drops_selected_schema(legacy_v2, tmp_path, capsys, drop):
    source = legacy_v2
    argv = ['--root', str(tmp_path), '--backend', 'sqlite', '--source', 'relational-v2',
            '--source-backend', 'sqlite', '--source-sqlite-path', str(source.settings.sqlite_path),
            'import', '--stopped']
    if drop:
        argv.append('--drop-legacy')
    assert migration.main(argv) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary['imported'] == 2 and summary['legacy_tables_removed'] is drop
    target = RelationalStore(replace(source.settings, table_prefix=''))
    try:
        target.check_ready()
        user = json.loads(target.get('system_accounts', 'owner.json').content)
        assert user['nickname'] == 'updated-from-SQL'
        binding = json.loads(target.get('school_accounts', 'user_accounts/owner.json').content)
        assert binding['10001']['ua'] == 'owner-UA'
        names = set(inspect(target.database.engine).get_table_names())
        assert 'unrelated_notes' in names
        assert ('app_schema_meta' not in names) is drop
        if not drop:
            source.check_ready()
            assert migration.verify_relational_store(source, target).ok
    finally:
        target.database.dispose()


def test_real_v2_corrupt_session_can_be_skipped_without_poisoning_source_transaction(legacy_v2):
    source = legacy_v2
    source.put('sessions', 'broken-session.json', json.dumps({
        'session_id': '11111111-1111-4111-8111-111111111111',
        'auth_username': 'owner', 'created_at': 1.0, 'params': {'fixture': True},
    }).encode())
    identity = source._identity('sessions', 'broken-session.json')
    with source.database.connection() as connection:
        connection.execute(delete(source.entities['sessions']).where(
            source.entities['sessions'].c.document_id == identity))

    target = RelationalStore(replace(source.settings, table_prefix=''))
    try:
        target.init_schema(allow_legacy=True)
        result = migration.import_relational_store(source, target, skip_corrupt_sessions=True)
        assert result.verification.ok
        assert result.imported == 2
        assert result.issues == ({'severity': 'warning', 'code': 'skipped_corrupt_session',
                                  'namespace': 'sessions', 'key': 'broken-session.json'},)
        source.check_ready()
        assert target.get('sessions', 'broken-session.json') is None
        assert json.loads(target.get('system_accounts', 'owner.json').content)['auth_username'] == 'owner'
    finally:
        target.database.dispose()


def test_real_v2_corrupt_session_aborts_without_explicit_skip(legacy_v2):
    source = legacy_v2
    source.put('sessions', 'broken-session.json', b'{"session_id":"fixture-session"}')
    identity = source._identity('sessions', 'broken-session.json')
    with source.database.connection() as connection:
        connection.execute(delete(source.entities['sessions']).where(
            source.entities['sessions'].c.document_id == identity))
    with pytest.raises(migration.MigrationError, match='sessions/broken-session.json'):
        migration._relational_plan(source)
    source.check_ready()


def test_local_mysql_v2_corrupt_session_skip_uses_one_unpoisoned_snapshot(tmp_path):
    port = os.environ.get('STORAGE_IO_TEST_MYSQL_PORT')
    if not port:
        pytest.skip('set STORAGE_IO_TEST_MYSQL_PORT for local isolated MySQL coverage')
    import pymysql
    suffix = uuid.uuid4().hex[:12]
    database_name = 'upgrade_' + suffix
    host = os.environ.get('STORAGE_IO_TEST_MYSQL_HOST', '127.0.0.1')
    if host not in {'127.0.0.1', 'localhost', '::1'}:
        pytest.skip('the isolated upgrade integration test only uses a local MySQL server')
    user = os.environ.get('STORAGE_IO_TEST_MYSQL_USER', 'root')
    password = os.environ.get('STORAGE_IO_TEST_MYSQL_PASSWORD', '')
    port = int(port)
    admin = pymysql.connect(host=host, port=port, user=user, password=password, autocommit=True)
    admin.cursor().execute(f'CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4')
    from persistence.engine import DatabaseSettings
    try:
        settings = DatabaseSettings(backend='mysql', root=tmp_path, host=host, port=port,
            user=user, password=password, database=database_name, table_prefix='legacy_' + suffix[:6] + '_')
        source = RelationalStore(settings, schema_version='2')
        target = RelationalStore(replace(settings, table_prefix=''))
        try:
            source.init_schema(ready=True)
            source.put('system_accounts', 'owner.json', b'{"auth_username":"owner"}')
            key = 'broken-session.json'
            source.put('sessions', key, b'{"session_id":"11111111-1111-4111-8111-111111111111", "params":{"x":1}}')
            with source.database.connection() as connection:
                connection.execute(delete(source.entities['sessions']).where(
                    source.entities['sessions'].c.document_id == source._identity('sessions', key)))
            target.init_schema(allow_legacy=True)
            result = migration.import_relational_store(source, target, skip_corrupt_sessions=True)
            assert result.imported == 1 and result.verification.ok
            assert result.issues[0]['code'] == 'skipped_corrupt_session'
            source.check_ready()
            assert target.get('sessions', key) is None
        finally:
            target.database.dispose()
            source.database.dispose()
    finally:
        admin.cursor().execute(f'DROP DATABASE `{database_name}`')
        admin.close()


def test_real_v2_database_query_failure_is_never_treated_as_a_corrupt_session(legacy_v2):
    source = legacy_v2
    def unavailable(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('SELECT') and source.registry.name in statement:
            raise OperationalError('SELECT synthetic', {}, RuntimeError('synthetic database unavailable'))
    event.listen(source.database.engine, 'before_cursor_execute', unavailable)
    try:
        with pytest.raises(DatabaseError):
            migration._relational_plan(source, skip_corrupt_sessions=True)
    finally:
        event.remove(source.database.engine, 'before_cursor_execute', unavailable)
    source.check_ready()


def test_real_upgrade_rejects_same_database_overlapping_table_names(tmp_path, monkeypatch, capsys):
    settings = DatabaseSettings(root=tmp_path)
    source = RelationalStore(settings, schema_version='2')
    try:
        source.init_schema(ready=True)
        source.put('settings', 'messages.json', b'[]')
        monkeypatch.setenv('SQLITE_DATABASE_PATH', str(settings.sqlite_path))
        monkeypatch.delenv('MYSQL_TABLE_PREFIX', raising=False)
        before = set(inspect(source.database.engine).get_table_names())
        result = migration.main(['--root', str(tmp_path), '--backend', 'sqlite', '--source', 'relational-v2',
            '--legacy-table-prefix', '', 'import', '--stopped'])
        assert result == 2
        assert '表名重叠' in capsys.readouterr().err
        assert set(inspect(source.database.engine).get_table_names()) == before
        source.check_ready()
    finally:
        source.database.dispose()


def test_legacy_tables_remain_when_fresh_destination_verification_fails(legacy_v2):
    source = legacy_v2
    target = RelationalStore(replace(source.settings, table_prefix=''))
    try:
        target.init_schema(allow_legacy=True)
        migration.import_relational_store(source, target)
        target.put('system_accounts', 'owner.json', b'{"auth_username":"owner","nickname":"different","group":"user"}')
        with pytest.raises(migration.VerificationError):
            migration.drop_legacy_schema(source, target)
        names = set(inspect(source.database.engine).get_table_names())
        assert set(source.metadata.tables) <= names
        source.check_ready()
    finally:
        target.database.dispose()


def test_real_file_import_initializes_sqlite_and_cleans_only_verified_inputs(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('SQLITE_DATABASE_PATH', raising=False)
    monkeypatch.delenv('MYSQL_TABLE_PREFIX', raising=False)
    configs = tmp_path / 'configs'; configs.mkdir()
    config = {'System': {'school_accounts_dir': 'custom-accounts'}, 'Logging': {'log_dir': 'custom-logs'}}
    config_path = configs / 'config.json'; config_path.write_text(json.dumps(config), encoding='utf-8')
    accounts = tmp_path / 'custom-accounts'; accounts.mkdir()
    account_path = accounts / '10001.ini'; account_path.write_bytes(b'[Config]\nUsername=10001\n')
    image = accounts / 'avatar.png'; image.write_bytes(b'image')
    logs = tmp_path / 'custom-logs'; logs.mkdir()
    sms = logs / 'sms_history.jsonl'; sms.write_text('{"phone":"fixture-phone","status":"success"}\n', encoding='utf-8')
    audit = logs / 'audit.json'; audit.write_text('retain audit log', encoding='utf-8')
    assert migration.main(['--root', str(tmp_path), '--backend', 'sqlite', 'import', '--stopped', '--remove-source']) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary['imported'] == 3 and summary['source_removed'] is True
    assert not account_path.exists() and not config_path.exists()
    assert image.exists() and sms.exists() and audit.exists()
    assert (tmp_path / 'data/application.sqlite3').is_file()
    assert migration.main(['--root', str(tmp_path), '--backend', 'sqlite', 'verify', '--database-only']) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary['scope'] == 'database-only' and summary['database_records'] == 3
    assert not list(tmp_path.rglob('*.bak'))
