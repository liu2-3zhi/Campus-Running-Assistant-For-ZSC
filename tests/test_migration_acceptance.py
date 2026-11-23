from pathlib import Path

import pytest
from persistence.engine import DatabaseSettings
from tools.test_storage_migration import run_test


def test_acceptance_rejects_sqlite_target_inside_source_before_writing(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    target = source / 'target.sqlite3'
    with pytest.raises(ValueError, match='outside'):
        run_test(source, DatabaseSettings(root=source, sqlite_path=target))
    assert not target.exists()


def test_invalid_source_cannot_reset_mysql(tmp_path, monkeypatch):
    from persistence import mysql_backup
    source = tmp_path / 'source'
    (source / 'payment_orders').mkdir(parents=True)
    (source / 'payment_orders/a.json').write_text('{"amount":"1.234"}', encoding='utf-8')
    def forbidden(*args, **kwargs):
        pytest.fail('Backup/reset/connection must not run before complete SQLite source preflight')
    monkeypatch.setattr(mysql_backup, 'backup_database', forbidden)
    settings = DatabaseSettings(backend='mysql', root=tmp_path, user='test', database='test')
    with pytest.raises(RuntimeError):
        run_test(source, settings, reset=True, backup_dir=tmp_path / 'backup', connection_factory=forbidden)


def test_invalid_target_prefix_cannot_reset_mysql(tmp_path):
    from persistence.engine import DatabaseConfigurationError
    source = tmp_path / 'source'
    source.mkdir()
    def forbidden():
        pytest.fail('Invalid destination schema must be rejected before connecting/resetting')
    settings = DatabaseSettings(backend='mysql', root=tmp_path, user='test', database='test', table_prefix='p' * 40)
    with pytest.raises(DatabaseConfigurationError, match='identifier limit'):
        run_test(source, settings, reset=True, backup_dir=tmp_path / 'backup', connection_factory=forbidden)
