import json
import os
import zipfile
from pathlib import Path

import pytest

try:
    import log_archiving
except ModuleNotFoundError:
    log_archiving = None


@pytest.fixture
def archive_environment(tmp_path):
    assert log_archiving is not None, "The safe archive engine has not been implemented"
    logs = tmp_path / "logs"
    logs.mkdir()
    archives = logs / "archive"
    backgrounds = tmp_path / "backgrounds"
    backgrounds.mkdir()
    messages = []
    manager = log_archiving.ArchiveManager(
        logs, archives, diagnostic=messages.append, background_dir=backgrounds
    )
    return manager, logs, archives, backgrounds, messages


def write_log(logs, name="zx-slm-tool-01.log", content=b"retired log\n"):
    path = logs / name
    path.write_bytes(content)
    return path


def zip_paths(archives):
    return sorted(archives.glob("*.zip"))


def manifests(archives):
    return sorted(archives.glob(".batch-*.json"))


def test_runtime_archives_compressed_logs_before_removal(archive_environment):
    manager, logs, archives, _, _ = archive_environment
    source = write_log(logs, content=b"retired log\n" * 100)
    assert manager.archive_runtime([str(source)]) is True
    assert not source.exists()
    with zipfile.ZipFile(zip_paths(archives)[0]) as result:
        assert result.read("zx-slm-tool-01.log") == b"retired log\n" * 100
        assert result.getinfo("zx-slm-tool-01.log").compress_type == zipfile.ZIP_DEFLATED
        assert result.testzip() is None
    assert manifests(archives) == []


@pytest.mark.parametrize("name", [
    "zx-slm-tool.log", "zx-slm-tool-WARNING.log", "zx-slm-tool-ERROR.log",
    "other-01.log", "zx-slm-tool-00.log", "zx-slm-tool-01.log.bak",
])
def test_runtime_rejects_active_or_unrecognized_files(archive_environment, name):
    manager, logs, archives, _, _ = archive_environment
    source = write_log(logs, name)
    assert manager.archive_runtime([str(source)]) is False
    assert source.read_bytes() == b"retired log\n"
    assert zip_paths(archives) == []


def test_runtime_rejects_files_outside_log_root(archive_environment):
    manager, _, archives, backgrounds, _ = archive_environment
    source = write_log(backgrounds)
    assert manager.archive_runtime([str(source)]) is False
    assert source.exists()
    assert zip_paths(archives) == []


@pytest.mark.parametrize("failure", ["compression", "crc", "publication"])
def test_failed_archive_never_deletes_source(archive_environment, monkeypatch, failure):
    manager, logs, archives, _, messages = archive_environment
    source = write_log(logs)
    if failure == "compression":
        def fail_write(*args, **kwargs):
            raise OSError("disk unavailable")
        monkeypatch.setattr(zipfile.ZipFile, "write", fail_write)
    elif failure == "crc":
        monkeypatch.setattr(zipfile.ZipFile, "testzip", lambda self: "corrupt.log")
    else:
        def fail_link(*args, **kwargs):
            raise OSError("hard links unavailable")
        monkeypatch.setattr(os, "link", fail_link)
    assert manager.archive_runtime([str(source)]) is False
    assert source.read_bytes() == b"retired log\n"
    assert zip_paths(archives) == []
    assert messages


def test_source_unlink_failure_retries_existing_zip(archive_environment, monkeypatch):
    manager, logs, archives, _, _ = archive_environment
    source = write_log(logs)
    real_unlink = os.unlink

    def locked_unlink(path, *args, **kwargs):
        if Path(path) == source:
            raise PermissionError("source is locked")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(os, "unlink", locked_unlink)
        assert manager.archive_runtime([str(source)]) is False
    assert source.exists()
    original_zips = zip_paths(archives)
    assert len(original_zips) == 1
    assert len(manifests(archives)) == 1
    assert manager.archive_runtime([str(source)]) is True
    assert not source.exists()
    assert zip_paths(archives) == original_zips
    assert manifests(archives) == []


def test_published_zip_recovers_if_manifest_update_failed(archive_environment, monkeypatch):
    manager, logs, archives, _, _ = archive_environment
    source = write_log(logs)
    real_write = manager._write_manifest

    def fail_published_update(batch):
        if batch["state"] == "published":
            raise OSError("manifest update interrupted")
        return real_write(batch)

    with monkeypatch.context() as patcher:
        patcher.setattr(manager, "_write_manifest", fail_published_update)
        assert manager.archive_runtime([str(source)]) is False
    assert source.exists()
    assert len(zip_paths(archives)) == 1
    assert json.loads(manifests(archives)[0].read_text())["state"] == "prepared"
    replacement = log_archiving.ArchiveManager(logs, archives, diagnostic=lambda text: None)
    assert replacement.recover() is True
    assert not source.exists()
    assert len(zip_paths(archives)) == 1
    assert manifests(archives) == []


@pytest.mark.parametrize("preserve_metadata", [False, True])
def test_changed_source_is_retained_even_when_size_and_mtime_match(
    archive_environment, monkeypatch, preserve_metadata
):
    manager, logs, archives, _, _ = archive_environment
    source = write_log(logs, content=b"original")
    original_stat = source.stat()
    publish = manager._publish_zip

    def publish_then_change(temporary, final):
        publish(temporary, final)
        source.write_bytes(b"modified" if preserve_metadata else b"changed and longer")
        if preserve_metadata:
            os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    monkeypatch.setattr(manager, "_publish_zip", publish_then_change)
    assert manager.archive_runtime([str(source)]) is False
    assert source.exists()
    assert len(zip_paths(archives)) == 1
    assert manifests(archives) == []
    monkeypatch.setattr(manager, "_publish_zip", publish)
    assert manager.archive_runtime([str(source)]) is True
    assert not source.exists()
    assert len(zip_paths(archives)) == 2


def test_separate_batches_never_overwrite_archives(archive_environment, monkeypatch):
    manager, logs, archives, _, _ = archive_environment
    monkeypatch.setattr(log_archiving.time, "strftime", lambda *args: "same-time")
    first = write_log(logs, content=b"first")
    assert manager.archive_runtime([str(first)]) is True
    second = write_log(logs, content=b"second")
    assert manager.archive_runtime([str(second)]) is True
    assert len(zip_paths(archives)) == 2
    contents = []
    for archive in zip_paths(archives):
        with zipfile.ZipFile(archive) as result:
            contents.append(result.read("zx-slm-tool-01.log"))
    assert sorted(contents) == [b"first", b"second"]


def test_startup_archives_only_strict_log_families(archive_environment):
    manager, logs, archives, _, _ = archive_environment
    names = ["zx-slm-tool.log", "zx-slm-tool-WARNING.log", "zx-slm-tool-ERROR.log",
             "zx-slm-tool-01.log", "zx-slm-tool-WARNING-02.log", "zx-slm-tool-ERROR-03.log"]
    for name in names:
        write_log(logs, name, name.encode())
    ignored = write_log(logs, "other.log")
    assert manager.archive_startup_logs() is True
    assert ignored.exists()
    assert all(not (logs / name).exists() for name in names)
    with zipfile.ZipFile(zip_paths(archives)[0]) as result:
        assert sorted(result.namelist()) == sorted(names)


def test_runtime_recovery_never_processes_startup_log_batch(archive_environment, monkeypatch):
    manager, logs, archives, _, _ = archive_environment
    source = write_log(logs, "zx-slm-tool.log")
    real_unlink = os.unlink

    def locked_unlink(path, *args, **kwargs):
        if Path(path) == source:
            raise PermissionError("locked")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(os, "unlink", locked_unlink)
        assert manager.archive_startup_logs() is False
    assert manager.recover(startup=False) is True
    assert source.exists()
    assert manifests(archives)
    assert manager.recover(startup=True) is True
    assert not source.exists()


def test_runtime_does_not_rearchive_sources_claimed_by_pending_startup(archive_environment, monkeypatch):
    manager, logs, archives, _, _ = archive_environment
    source = write_log(logs)
    real_unlink = os.unlink

    def locked_unlink(path, *args, **kwargs):
        if Path(path) == source:
            raise PermissionError("locked")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(os, "unlink", locked_unlink)
        assert manager.archive_startup_logs() is False
    assert manager.archive_runtime([str(source)]) is False
    assert source.exists()
    assert len(zip_paths(archives)) == 1


def test_changed_active_log_recovery_keeps_new_log_and_finishes_old_batch(archive_environment, monkeypatch):
    manager, logs, archives, _, _ = archive_environment
    source = write_log(logs, "zx-slm-tool.log", b"old process")
    real_unlink = os.unlink

    def locked_unlink(path, *args, **kwargs):
        if Path(path) == source:
            raise PermissionError("locked")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(os, "unlink", locked_unlink)
        assert manager.archive_startup_logs() is False
    source.write_bytes(b"new process")
    assert manager.recover(startup=True) is False
    assert source.read_bytes() == b"new process"
    assert manifests(archives) == []
    assert manager.archive_startup_logs() is True
    assert len(zip_paths(archives)) == 2


def test_prepublication_stale_log_batch_is_retired_without_removing_current_log(
    archive_environment, monkeypatch
):
    manager, logs, archives, _, _ = archive_environment
    source = write_log(logs, "zx-slm-tool.log", b"old process")

    def fail_write(*args, **kwargs):
        raise OSError("startup compression interrupted")

    with monkeypatch.context() as patcher:
        patcher.setattr(zipfile.ZipFile, "write", fail_write)
        assert manager.archive_startup_logs() is False
    source.write_bytes(b"old process\nnew activity")
    assert manager.recover(startup=True) is False
    assert source.read_bytes() == b"old process\nnew activity"
    assert manifests(archives) == []
    assert zip_paths(archives) == []
    assert list(archives.glob(".*.zip.tmp")) == []
    assert manager.archive_startup_logs() is True
    assert not source.exists()
    with zipfile.ZipFile(zip_paths(archives)[0]) as result:
        assert result.read("zx-slm-tool.log") == b"old process\nnew activity"


def test_prepublication_stale_background_batch_keeps_root_for_next_attempt(
    archive_environment, monkeypatch
):
    manager, _, archives, backgrounds, _ = archive_environment
    image = backgrounds / "picture.bin"
    image.write_bytes(b"old image")

    def fail_write(*args, **kwargs):
        raise OSError("startup compression interrupted")

    with monkeypatch.context() as patcher:
        patcher.setattr(zipfile.ZipFile, "write", fail_write)
        assert manager.archive_startup_background(str(backgrounds)) is False
    image.write_bytes(b"new image")
    assert manager.archive_startup_background(str(backgrounds)) is False
    assert image.read_bytes() == b"new image"
    assert manager.background_reset_completed is False
    assert manifests(archives) == []
    assert zip_paths(archives) == []
    assert manager.archive_startup_background(str(backgrounds)) is True
    assert list(backgrounds.iterdir()) == []
    with zipfile.ZipFile(zip_paths(archives)[0]) as result:
        assert result.read("backgrounds/picture.bin") == b"new image"


@pytest.mark.parametrize("stalled_state", ["published", "staging"])
def test_published_background_batch_retires_changed_root_before_staging(
    archive_environment, monkeypatch, stalled_state
):
    manager, _, archives, backgrounds, _ = archive_environment
    image = backgrounds / "picture.bin"
    image.write_bytes(b"old image")
    real_rename = os.rename
    real_write_manifest = manager._write_manifest

    def blocked_rename(source, target, *args, **kwargs):
        if Path(source) == backgrounds:
            raise PermissionError("background directory locked")
        return real_rename(source, target, *args, **kwargs)

    def blocked_staging_manifest(batch):
        if batch["state"] == "staging":
            raise OSError("staging manifest interrupted")
        return real_write_manifest(batch)

    with monkeypatch.context() as patcher:
        if stalled_state == "staging":
            patcher.setattr(os, "rename", blocked_rename)
        else:
            patcher.setattr(manager, "_write_manifest", blocked_staging_manifest)
        assert manager.archive_startup_background(str(backgrounds)) is False
    assert json.loads(manifests(archives)[0].read_text())["state"] == stalled_state
    assert list(backgrounds.parent.glob(".backgrounds.archive-*")) == []
    image.write_bytes(b"new image")
    state = backgrounds / "background_state.json"
    state.write_bytes(b"new identity bindings")
    assert manager.archive_startup_background(str(backgrounds)) is False
    assert manager.background_reset_completed is False
    assert image.read_bytes() == b"new image"
    assert state.read_bytes() == b"new identity bindings"
    assert manifests(archives) == []
    assert len(zip_paths(archives)) == 1
    assert manager.archive_startup_background(str(backgrounds)) is True
    assert list(backgrounds.iterdir()) == []
    assert len(zip_paths(archives)) == 2
    archived_contents = []
    for archive in zip_paths(archives):
        with zipfile.ZipFile(archive) as result:
            archived_contents.append(result.read("backgrounds/picture.bin"))
    assert sorted(archived_contents) == [b"new image", b"old image"]


def test_background_startup_archives_whole_tree_then_resets_root(archive_environment):
    manager, _, archives, backgrounds, _ = archive_environment
    (backgrounds / "nested").mkdir()
    (backgrounds / "empty-dir").mkdir()
    (backgrounds / "nested" / "picture.bin").write_bytes(b"image bytes")
    (backgrounds / "zero.bin").touch()
    assert manager.archive_startup_background(str(backgrounds)) is True
    assert backgrounds.is_dir()
    assert list(backgrounds.iterdir()) == []
    with zipfile.ZipFile(zip_paths(archives)[0]) as result:
        assert result.read("backgrounds/nested/picture.bin") == b"image bytes"
        assert result.read("backgrounds/zero.bin") == b""
        assert "backgrounds/empty-dir/" in result.namelist()
    assert manifests(archives) == []


def test_background_compression_failure_preserves_original_tree(archive_environment, monkeypatch):
    manager, _, archives, backgrounds, _ = archive_environment
    (backgrounds / "picture.bin").write_bytes(b"image bytes")

    def fail_write(*args, **kwargs):
        raise OSError("full disk")

    monkeypatch.setattr(zipfile.ZipFile, "write", fail_write)
    assert manager.archive_startup_background(str(backgrounds)) is False
    assert (backgrounds / "picture.bin").read_bytes() == b"image bytes"
    assert zip_paths(archives) == []


def test_unreadable_background_subtree_is_not_reset(archive_environment, monkeypatch):
    manager, _, archives, backgrounds, _ = archive_environment
    nested = backgrounds / "nested"
    nested.mkdir()
    (nested / "picture.bin").write_bytes(b"image bytes")
    real_scandir = os.scandir

    def fail_scan(path):
        if Path(path) == nested:
            raise PermissionError("unreadable directory")
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", fail_scan)
    assert manager.archive_startup_background(str(backgrounds)) is False
    assert (nested / "picture.bin").read_bytes() == b"image bytes"
    assert zip_paths(archives) == []


def test_failed_background_recovery_does_not_block_startup_logs(archive_environment, monkeypatch):
    manager, logs, archives, backgrounds, _ = archive_environment
    image = backgrounds / "picture.bin"
    image.write_bytes(b"image bytes")

    def fail_write(*args, **kwargs):
        raise OSError("background preparation interrupted")

    with monkeypatch.context() as patcher:
        patcher.setattr(zipfile.ZipFile, "write", fail_write)
        assert manager.archive_startup_background(str(backgrounds)) is False
    image.write_bytes(b"changed image")
    source = write_log(logs, "zx-slm-tool.log")
    assert manager.archive_startup_logs() is True
    assert not source.exists()
    assert image.read_bytes() == b"changed image"
    assert len(zip_paths(archives)) == 1


def test_failed_log_recovery_does_not_block_background_reset(archive_environment, monkeypatch):
    manager, logs, archives, backgrounds, _ = archive_environment
    source = write_log(logs)

    def fail_write(*args, **kwargs):
        raise OSError("log preparation interrupted")

    with monkeypatch.context() as patcher:
        patcher.setattr(zipfile.ZipFile, "write", fail_write)
        assert manager.archive_startup_logs() is False
    source.write_bytes(b"changed log")
    (backgrounds / "picture.bin").write_bytes(b"image bytes")
    assert manager.archive_startup_background(str(backgrounds)) is True
    assert source.read_bytes() == b"changed log"
    assert list(backgrounds.iterdir()) == []
    assert len(zip_paths(archives)) == 1


def test_background_pending_cleanup_only_runs_at_startup(archive_environment, monkeypatch):
    manager, logs, archives, backgrounds, _ = archive_environment
    (backgrounds / "picture.bin").write_bytes(b"image bytes")
    real_unlink = os.unlink

    def locked_stage(path, *args, **kwargs):
        if Path(path).name == "picture.bin":
            raise PermissionError("locked image")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(os, "unlink", locked_stage)
        assert manager.archive_startup_background(str(backgrounds)) is False
    assert backgrounds.is_dir() and list(backgrounds.iterdir()) == []
    stage = list(backgrounds.parent.glob(".backgrounds.archive-*"))
    assert len(stage) == 1
    assert manager.recover(startup=False) is True
    assert (stage[0] / "picture.bin").exists()
    fresh = log_archiving.ArchiveManager(
        logs, archives, background_dir=backgrounds, diagnostic=lambda text: None
    )
    assert fresh.recover(startup=True) is True
    assert not stage[0].exists()
    assert len(zip_paths(archives)) == 1


def test_background_reset_flag_survives_pending_staging_cleanup(archive_environment, monkeypatch):
    manager, _, archives, backgrounds, _ = archive_environment
    source = backgrounds / "picture.bin"
    source.write_bytes(b"image bytes")
    real_unlink = os.unlink

    def locked_stage_file(path, *args, **kwargs):
        if Path(path).name == source.name:
            raise PermissionError("staging file locked")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(os, "unlink", locked_stage_file)
        assert manager.archive_startup_background(str(backgrounds)) is False
    assert manager.background_reset_completed is True
    assert backgrounds.is_dir() and list(backgrounds.iterdir()) == []
    assert manifests(archives)


def test_old_pending_reset_does_not_mark_new_background_contents_as_backed_up(
    archive_environment, monkeypatch
):
    manager, logs, archives, backgrounds, _ = archive_environment
    (backgrounds / "old.bin").write_bytes(b"old image")
    real_unlink = os.unlink

    def locked_stage_file(path, *args, **kwargs):
        if Path(path).name == "old.bin":
            raise PermissionError("staging file locked")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(os, "unlink", locked_stage_file)
        assert manager.archive_startup_background(str(backgrounds)) is False
    (backgrounds / "new.bin").write_bytes(b"new image")
    (backgrounds / "background_state.json").write_bytes(b"new identity bindings")
    fresh = log_archiving.ArchiveManager(
        logs, archives, background_dir=backgrounds, diagnostic=lambda text: None
    )
    with monkeypatch.context() as patcher:
        patcher.setattr(os, "unlink", locked_stage_file)
        assert fresh.archive_startup_background(str(backgrounds)) is False
    assert fresh.background_reset_completed is False
    assert (backgrounds / "new.bin").read_bytes() == b"new image"
    assert (backgrounds / "background_state.json").read_bytes() == b"new identity bindings"


def test_background_crash_after_staging_recreates_original_root(archive_environment, monkeypatch):
    manager, logs, archives, backgrounds, _ = archive_environment
    (backgrounds / "picture.bin").write_bytes(b"image bytes")
    real_mkdir = os.mkdir

    def fail_new_root(path, *args, **kwargs):
        if Path(path) == backgrounds and not backgrounds.exists():
            raise PermissionError("interrupted creating new root")
        return real_mkdir(path, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(os, "mkdir", fail_new_root)
        assert manager.archive_startup_background(str(backgrounds)) is False
    assert not backgrounds.exists()
    batch = json.loads(manifests(archives)[0].read_text())
    assert batch["state"] == "staging"
    fresh = log_archiving.ArchiveManager(
        logs, archives, background_dir=backgrounds, diagnostic=lambda text: None
    )
    assert fresh.recover(startup=True) is True
    assert backgrounds.is_dir() and list(backgrounds.iterdir()) == []


def test_background_recovery_requires_explicitly_configured_root(archive_environment, monkeypatch):
    manager, logs, archives, backgrounds, _ = archive_environment
    (backgrounds / "picture.bin").write_bytes(b"image bytes")
    real_unlink = os.unlink

    def locked_stage(path, *args, **kwargs):
        if Path(path).name == "picture.bin":
            raise PermissionError("locked image")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(os, "unlink", locked_stage)
        assert manager.archive_startup_background(str(backgrounds)) is False
    fresh = log_archiving.ArchiveManager(logs, archives, diagnostic=lambda text: None)
    assert fresh.recover(startup=True) is False
    assert manifests(archives)
    assert list(backgrounds.parent.glob(".backgrounds.archive-*/picture.bin"))


def test_background_rejects_archive_inside_source(archive_environment):
    _, logs, _, backgrounds, _ = archive_environment
    manager = log_archiving.ArchiveManager(
        logs, backgrounds / "archive", background_dir=backgrounds, diagnostic=lambda text: None
    )
    (backgrounds / "picture.bin").write_bytes(b"safe")
    assert manager.archive_startup_background(str(backgrounds)) is False
    assert (backgrounds / "picture.bin").read_bytes() == b"safe"


def test_quota_zero_is_unlimited_and_newest_oversize_is_retained(archive_environment):
    manager, _, archives, _, _ = archive_environment
    archives.mkdir(parents=True, exist_ok=True)
    first, second = archives / "old.zip", archives / "new.zip"
    first.write_bytes(b"first archive")
    second.write_bytes(b"newest archive")
    os.utime(first, (100, 100))
    os.utime(second, (200, 200))
    manager.max_size_mb = 0
    manager.cleanup()
    assert first.exists() and second.exists()
    manager.max_size_mb = 0.000001
    manager.cleanup()
    assert not first.exists()
    assert second.read_bytes() == b"newest archive"


def test_quota_protects_zip_for_unfinished_transaction(archive_environment, monkeypatch):
    manager, logs, archives, _, _ = archive_environment
    source = write_log(logs)
    real_unlink = os.unlink

    def locked_log(path, *args, **kwargs):
        if Path(path) == source:
            raise PermissionError("locked log")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(os, "unlink", locked_log)
        assert manager.archive_runtime([str(source)]) is False
    protected = zip_paths(archives)[0]
    newest = archives / "newer.zip"
    newest.write_bytes(b"newer")
    os.utime(newest, (protected.stat().st_mtime + 10,) * 2)
    manager.max_size_mb = 0.000001
    manager.cleanup()
    assert protected.exists() and newest.exists()


def test_malformed_manifest_cannot_delete_escaping_source(archive_environment):
    manager, logs, archives, _, _ = archive_environment
    source = write_log(logs, content=b"kept")
    assert manager.archive_runtime([str(source)]) is True
    archives.mkdir(parents=True, exist_ok=True)
    outside = logs.parent / "private.txt"
    outside.write_bytes(b"private")
    (archives / ".batch-forged.json").write_text(json.dumps({
        "version": 1, "id": "forged", "kind": "runtime", "state": "published",
        "zip_name": zip_paths(archives)[0].name,
        "entries": [{"path": "../private.txt", "size": 7, "mtime_ns": outside.stat().st_mtime_ns,
                     "sha256": "0" * 64}],
    }))
    assert manager.recover() is False
    assert outside.read_bytes() == b"private"


def test_symlink_sources_are_rejected(archive_environment):
    manager, logs, archives, _, _ = archive_environment
    target = logs.parent / "private.txt"
    target.write_bytes(b"private")
    link = logs / "zx-slm-tool-01.log"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symbolic links is unavailable")
    assert manager.archive_runtime([str(link)]) is False
    assert link.is_symlink() and target.read_bytes() == b"private"
    assert zip_paths(archives) == []


def test_move_no_replace_preserves_existing_target(tmp_path):
    assert log_archiving is not None, "The safe archive engine has not been implemented"
    source, target = tmp_path / "source.log", tmp_path / "target.log"
    source.write_bytes(b"source")
    target.write_bytes(b"existing")
    with pytest.raises(OSError):
        log_archiving.move_no_replace(source, target)
    assert source.read_bytes() == b"source"
    assert target.read_bytes() == b"existing"


def test_move_no_replace_moves_without_losing_contents(tmp_path):
    assert log_archiving is not None, "The safe archive engine has not been implemented"
    source, target = tmp_path / "source.log", tmp_path / "target.log"
    source.write_bytes(b"source")
    log_archiving.move_no_replace(source, target)
    assert not source.exists()
    assert target.read_bytes() == b"source"


@pytest.mark.skipif(os.name == "nt", reason="POSIX hard-link fallback")
def test_move_no_replace_rolls_back_if_source_unlink_fails(tmp_path, monkeypatch):
    assert log_archiving is not None, "The safe archive engine has not been implemented"
    source, target = tmp_path / "source.log", tmp_path / "target.log"
    source.write_bytes(b"source")
    real_unlink = os.unlink

    def fail_source(path, *args, **kwargs):
        if Path(path) == source:
            raise PermissionError("source locked")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", fail_source)
    with pytest.raises(OSError):
        log_archiving.move_no_replace(source, target)
    assert source.read_bytes() == b"source"
    assert not target.exists()
