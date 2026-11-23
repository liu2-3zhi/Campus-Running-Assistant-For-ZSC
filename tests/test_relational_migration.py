import json
from pathlib import Path

import pytest
from sqlalchemy import text

from storage_migration import import_documents, verify_documents, export_documents


@pytest.fixture
def setup(tmp_path):
    from business_storage import StoragePolicy
    from persistence.engine import DatabaseSettings
    from persistence.store import RelationalStore
    source = tmp_path / 'source'
    (source / 'system_accounts').mkdir(parents=True)
    (source / 'system_accounts/user.json').write_text('{ "auth_username" : "user", "group": "user" }\n', encoding='utf-8')
    store = RelationalStore(DatabaseSettings(root=tmp_path / 'db'))
    store.init_schema()
    yield source, StoragePolicy(source), store
    store.database.dispose()


def test_normalized_import_compares_semantics_and_retains_source_digest(setup, tmp_path):
    import hashlib
    source, policy, store = setup
    original = (source / 'system_accounts/user.json').read_bytes()
    first = import_documents(policy, store)
    assert first.verification.ok and first.imported == 1
    saved = store.get('system_accounts', 'user.json')
    assert saved.content != original
    assert saved.source_sha256 == hashlib.sha256(original).hexdigest()
    assert verify_documents(policy, store).ok
    assert import_documents(policy, store).unchanged == 1
    assert (source / 'system_accounts/user.json').read_bytes() == original
    result = export_documents(policy, store, tmp_path / 'export')
    assert result.exported == 1
    assert json.loads((tmp_path / 'export/system_accounts/user.json').read_bytes()) == json.loads(original)


def test_direct_column_corruption_is_detected_by_saved_checksum(setup):
    source, policy, store = setup
    import_documents(policy, store)
    with store.database.connection() as connection:
        connection.execute(text("UPDATE app_users SET auth_username='changed'"))
    saved = store.get('system_accounts', 'user.json')
    assert json.loads(saved.content)['auth_username'] == 'changed'
    assert not verify_documents(policy, store).ok


def test_legacy_store_source_is_read_only_and_semantically_verified(setup):
    from storage_migration import import_legacy_store
    from tests.test_storage_migration import MemoryStore
    _, _, target = setup
    legacy = MemoryStore()
    legacy.ready = True
    legacy.put('system_accounts', 'user.json', b'{ "auth_username" : "user" }')
    before = legacy.documents.copy()
    result = import_legacy_store(legacy, target)
    assert result.verification.ok
    assert legacy.documents == before
    assert json.loads(target.get('system_accounts', 'user.json').content) == {'auth_username': 'user'}
