"""Optional real MySQL checks; every case owns and removes unique test tables."""
import os
import uuid

import pytest

from business_storage import (MySQLDocumentStore, StorageSettings, ConflictError,
                              StorageError, StorageConfigurationError)
from storage_migration import export_documents, VerificationError
from business_storage import StoragePolicy


@pytest.fixture
def live_store(tmp_path):
    port = os.environ.get('STORAGE_IO_TEST_MYSQL_PORT')
    if not port:
        pytest.skip('Set STORAGE_IO_TEST_MYSQL_PORT to use an isolated MySQL test database')
    settings = StorageSettings.from_env({
        'APP_STORAGE_BACKEND': 'mysql',
        'MYSQL_HOST': os.environ.get('STORAGE_IO_TEST_MYSQL_HOST', '127.0.0.1'),
        'MYSQL_PORT': port,
        'MYSQL_USER': os.environ.get('STORAGE_IO_TEST_MYSQL_USER', 'root'),
        'MYSQL_PASSWORD': os.environ.get('STORAGE_IO_TEST_MYSQL_PASSWORD', ''),
        'MYSQL_DATABASE': os.environ.get('STORAGE_IO_TEST_MYSQL_DATABASE', 'storage_test'),
        'MYSQL_TABLE_PREFIX': 'core_' + uuid.uuid4().hex[:16] + '_',
    }, root=tmp_path)
    store = MySQLDocumentStore(settings)
    store.init_schema()
    yield store
    connection = store._connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TABLE {store._documents}')
            cursor.execute(f'DROP TABLE {store._metadata}')
        connection.commit()
    finally:
        connection.close()


def test_real_store_ready_is_explicit_and_can_be_revoked(live_store):
    with pytest.raises(StorageConfigurationError):
        live_store.check_ready()
    live_store.mark_ready()
    live_store.check_ready()
    live_store.mark_pending()
    with pytest.raises(StorageConfigurationError):
        live_store.check_ready()


def test_real_store_cas_and_literal_prefix_preserve_data(live_store):
    first = live_store.put('settings', "key_'%_.json", '中文🙂'.encode(), expected_revision=0)
    live_store.put('settings', 'key_x.json', b'other')
    assert live_store.get('settings', first.key).content == '中文🙂'.encode()
    second = live_store.put('settings', first.key, b'changed', expected_revision=first.revision)
    assert second.revision == first.revision + 1
    assert second.mtime_ns > first.mtime_ns
    with pytest.raises(ConflictError):
        live_store.put('settings', first.key, b'lost-update', expected_revision=first.revision)
    assert live_store.get('settings', first.key).content == b'changed'
    assert [item.key for item in live_store.list('settings', "key_'%_")] == [first.key]


def test_real_transaction_rolls_back_all_documents(live_store):
    with pytest.raises(ValueError):
        with live_store.transaction():
            live_store.put('settings', 'a.json', b'{}')
            live_store.put('settings', 'b.json', b'{}')
            raise ValueError('abort')
    assert live_store.list('settings') == []


def test_real_nested_caught_failure_cannot_commit_partial_transaction(live_store):
    with pytest.raises(StorageError):
        with live_store.transaction():
            live_store.put('settings', 'a.json', b'{}')
            try:
                with live_store.transaction():
                    raise ValueError('nested failure')
            except ValueError:
                pass
    assert live_store.list('settings') == []


def test_real_export_rejects_content_that_does_not_match_stored_checksum(live_store, tmp_path):
    live_store.put('settings', 'messages.json', b'[]')
    live_store.mark_ready()
    connection = live_store._connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(f'UPDATE {live_store._documents} SET content=%s', (b'["changed"]',))
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(VerificationError):
        export_documents(StoragePolicy(tmp_path), live_store, tmp_path / 'export')
    assert not (tmp_path / 'export').exists()
