import contextlib
import io
import json
import logging
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import main
import log_archiving


def emit(handler, message):
    handler.emit(logging.LogRecord("archive-test", logging.INFO, __file__, 1, message, (), None))


def archived_lines(directory):
    lines = []
    for path in Path(directory).glob("*.zip"):
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith(".log"):
                    lines.extend(archive.read(name).decode("utf-8").splitlines())
    return lines


class TestLogArchivingIntegration(unittest.TestCase):
    @contextlib.contextmanager
    def workspace(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as resources:
            self.resources = resources
            yield Path(directory)

    def make_handler(self, path, **kwargs):
        handler = main.CustomLogHandler(str(path), max_bytes=1, **kwargs)
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.resources.callback(handler.close)
        return handler

    def test_eleventh_backup_is_archived_before_source_is_removed(self):
        with self.workspace() as root, contextlib.redirect_stdout(io.StringIO()):
            handler = self.make_handler(root / "zx-slm-tool.log")
            for index in range(12):
                emit(handler, f"record-{index:03d}")
            self.assertEqual(archived_lines(root / "archive"), ["record-000"])
            self.assertEqual(
                sorted(p.name for p in root.glob("zx-slm-tool-*.log")),
                [f"zx-slm-tool-{index:02d}.log" for index in range(2, 12)],
            )

    def test_195_rollovers_preserve_every_record(self):
        with self.workspace() as root, contextlib.redirect_stdout(io.StringIO()):
            handler = self.make_handler(root / "zx-slm-tool.log")
            expected = [f"record-{index:03d}" for index in range(196)]
            for message in expected:
                emit(handler, message)
            handler.flush()
            actual = archived_lines(root / "archive")
            for path in root.glob("*.log"):
                actual.extend(path.read_text(encoding="utf-8").splitlines())
            self.assertCountEqual(actual, expected)
            self.assertEqual(len(actual), len(expected))
            self.assertEqual(
                sorted(p.name for p in root.glob("zx-slm-tool-*.log")),
                [f"zx-slm-tool-{index}.log" for index in range(186, 196)],
            )

    def test_failed_archiving_keeps_sources_and_retries_without_another_rollover(self):
        with self.workspace() as root, contextlib.redirect_stdout(io.StringIO()):
            handler = self.make_handler(root / "zx-slm-tool.log", backup_count=1)
            manager = Mock()
            manager.archive_runtime.return_value = False
            manager.recover.return_value = True
            handler.archive_manager = manager
            with patch("main.time.monotonic", return_value=100):
                for index in range(3):
                    emit(handler, f"record-{index}")
            self.assertTrue((root / "zx-slm-tool-01.log").exists())
            self.assertTrue((root / "zx-slm-tool-02.log").exists())
            handler.max_bytes = 10000
            with patch("main.time.monotonic", return_value=101):
                emit(handler, "during-backoff")
            self.assertEqual(manager.archive_runtime.call_count, 1)
            manager.archive_runtime.return_value = True
            with patch("main.time.monotonic", return_value=103):
                emit(handler, "after-backoff")
            self.assertEqual(manager.archive_runtime.call_count, 2)
            self.assertIn("after-backoff", (root / "zx-slm-tool.log").read_text(encoding="utf-8"))

    def test_runtime_archiving_does_not_touch_other_active_logs_or_backgrounds(self):
        with self.workspace() as root, contextlib.redirect_stdout(io.StringIO()):
            untouched = [root / "zx-slm-tool-WARNING.log", root / "zx-slm-tool-ERROR.log"]
            background = root / "random_background_image"
            background.mkdir()
            untouched.append(background / "background_state.json")
            for path in untouched:
                path.write_text("sentinel", encoding="utf-8")
            before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in untouched}
            handler = self.make_handler(root / "zx-slm-tool.log", backup_count=1)
            for index in range(5):
                emit(handler, f"record-{index}")
            self.assertEqual(
                {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in untouched}, before
            )
            self.assertEqual(len(archived_lines(root / "archive")), 3)

    def test_legacy_one_digit_backups_are_archived(self):
        with self.workspace() as root, contextlib.redirect_stdout(io.StringIO()):
            (root / "zx-slm-tool-1.log").write_text("legacy\n", encoding="utf-8")
            handler = self.make_handler(root / "zx-slm-tool.log", backup_count=1)
            emit(handler, "current")
            emit(handler, "next")
            self.assertEqual(archived_lines(root / "archive"), ["legacy"])
            self.assertTrue((root / "zx-slm-tool-02.log").exists())

    def test_rotation_collision_preserves_both_existing_and_current_records(self):
        with self.workspace() as root, contextlib.redirect_stdout(io.StringIO()):
            handler = self.make_handler(root / "zx-slm-tool.log")
            emit(handler, "first")
            collision = root / "zx-slm-tool-01.log"
            collision.write_text("preexisting\n", encoding="utf-8")
            with patch.object(handler, "_next_backup_path", return_value=str(collision)):
                emit(handler, "second")
            self.assertEqual(collision.read_text(encoding="utf-8"), "preexisting\n")
            self.assertEqual((root / "zx-slm-tool.log").read_text(encoding="utf-8"), "first\nsecond\n")

    def test_all_three_handlers_archive_their_own_histories(self):
        with self.workspace() as root, contextlib.redirect_stdout(io.StringIO()):
            manager = main.ArchiveManager(root, root / "archive", max_size_mb=0)
            expected = []
            for prefix in ("zx-slm-tool", "zx-slm-tool-WARNING", "zx-slm-tool-ERROR"):
                handler = self.make_handler(root / f"{prefix}.log", backup_count=1, archive_manager=manager)
                for index in range(4):
                    message = f"{prefix}:{index}"
                    expected.append(message)
                    emit(handler, message)
            actual = archived_lines(root / "archive")
            for path in root.glob("*.log"):
                actual.extend(path.read_text(encoding="utf-8").splitlines())
            self.assertCountEqual(actual, expected)

    def test_failed_current_record_write_does_not_start_archiving(self):
        with self.workspace() as root, contextlib.redirect_stdout(io.StringIO()):
            handler = self.make_handler(root / "zx-slm-tool.log", backup_count=1)
            for index in (1, 2):
                (root / f"zx-slm-tool-{index:02d}.log").write_text("history\n", encoding="utf-8")
            handler.archive_manager = Mock()
            with patch.object(handler.stream, "write", side_effect=OSError("write failed")), patch(
                "logging.raiseExceptions", False
            ):
                emit(handler, "unwritten")
            handler.archive_manager.archive_runtime.assert_not_called()

    def test_archive_retry_has_its_own_capped_exponential_backoff(self):
        with self.workspace() as root, contextlib.redirect_stdout(io.StringIO()):
            handler = self.make_handler(root / "zx-slm-tool.log", backup_count=1)
            handler.max_bytes = 100000
            for index in (1, 2):
                (root / f"zx-slm-tool-{index:02d}.log").write_text("history\n", encoding="utf-8")
            handler.archive_manager = Mock()
            handler.archive_manager.archive_runtime.return_value = False
            timestamp = 100
            for attempt, delay in enumerate((2, 4, 8, 16, 32, 60, 60), start=1):
                with patch("main.time.monotonic", return_value=timestamp):
                    emit(handler, "retry")
                self.assertEqual(handler.archive_manager.archive_runtime.call_count, attempt)
                self.assertEqual(handler.archive_retry_at, timestamp + delay)
                self.assertEqual(handler.rollover_failure_count, 0)
                with patch("main.time.monotonic", return_value=timestamp + delay - 0.1):
                    emit(handler, "waiting")
                self.assertEqual(handler.archive_manager.archive_runtime.call_count, attempt)
                timestamp += delay


class TestLoggingStartupArchive(unittest.TestCase):
    @contextlib.contextmanager
    def isolated_logging(self, root):
        config = {"Logging": {"log_dir": str(root / "logs"), "archive_dir": str(root / "archives"),
                              "archive_max_size_mb": "0", "log_rotation_size_mb": "10"}}
        root.joinpath("config.json").write_text(json.dumps(config), encoding="utf-8")
        logger = logging.getLogger()
        previous_handlers, previous_level = list(logger.handlers), logger.level
        with patch.object(main, "CONFIG_JSON_FILE", str(root / "config.json")), patch.object(
            main, "RANDOM_BACKGROUND_IMAGE_DIR", str(root / "backgrounds")
        ), patch.object(
            main, "_logging_configured", False, create=True
        ), patch.object(main, "_logging_archive_manager", None, create=True), patch.object(
            main, "_log_buffer", []
        ), patch.object(main, "_BACKGROUND_SELECTION_STATE", {}), patch.object(
            main, "_install_global_exception_logging"
        ), patch.object(main, "log_dir", None, create=True), patch.object(
            main, "archive_dir", None, create=True
        ), contextlib.chdir(root), contextlib.redirect_stdout(io.StringIO()):
            logger.handlers = []
            try:
                yield
            finally:
                for handler in logger.handlers:
                    handler.close()
                logger.handlers, logger.level = previous_handlers, previous_level

    def test_startup_archives_previous_files_resets_backgrounds_only_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logs, backgrounds = root / "logs", root / "backgrounds"
            logs.mkdir()
            backgrounds.mkdir()
            for name in ("zx-slm-tool.log", "zx-slm-tool-WARNING.log", "zx-slm-tool-ERROR.log", "zx-slm-tool-195.log"):
                (logs / name).write_text(f"old-{name}\n", encoding="utf-8")
            (backgrounds / "pc_old.jpg").write_bytes(b"old-image")
            store = main.BackgroundStateStore(str(backgrounds))
            bundle = store.create_bundle("/theme-assets/random_background_image/pc_old.jpg", "", "previous-run")
            store.bind_identity("user:old", bundle["bundle_id"], "previous-run")
            store.bind_guest_session("old-guest", bundle["bundle_id"], "previous-run")
            store.set_auth_claim("old-auth", bundle["bundle_id"], "2099-01-01T00:00:00+00:00")
            (backgrounds / "index.json").write_text(json.dumps({"session_bindings": {
                "legacy-session": {"pc": {"image_url": "/old.jpg"}}
            }}), encoding="utf-8")
            with self.isolated_logging(root):
                main._BACKGROUND_SELECTION_STATE["old"] = "pc_old.jpg"
                main.setup_logging()
                self.assertFalse((backgrounds / "pc_old.jpg").exists())
                self.assertEqual(store.load(), main._empty_background_state())
                index = json.loads((backgrounds / "index.json").read_text(encoding="utf-8"))
                self.assertEqual(index["session_bindings"], {})
                self.assertEqual(main._BACKGROUND_SELECTION_STATE, {})
                entries = []
                for path in (root / "archives").glob("*.zip"):
                    with zipfile.ZipFile(path) as archive:
                        entries.extend(archive.namelist())
                self.assertIn("zx-slm-tool-195.log", entries)
                self.assertIn("backgrounds/pc_old.jpg", entries)
                (backgrounds / "pc_new.jpg").write_bytes(b"new-image")
                archive_count = len(list((root / "archives").glob("*.zip")))
                main.setup_logging()
                main.archive_old_logs()
                self.assertTrue((backgrounds / "pc_new.jpg").exists())
                self.assertEqual(len(list((root / "archives").glob("*.zip"))), archive_count)

    def test_background_state_initialization_failure_does_not_disable_logging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.isolated_logging(root), patch.object(
                main.BackgroundStateStore, "save", side_effect=OSError("state disk full")
            ):
                logger = main.setup_logging()
                self.assertTrue(main._logging_configured)
                self.assertEqual(sum(isinstance(handler, main.CustomLogHandler) for handler in logger.handlers), 3)

    def test_staging_cleanup_failure_still_initializes_empty_background_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backgrounds = root / "backgrounds"
            backgrounds.mkdir()
            (backgrounds / "pc_old.jpg").write_bytes(b"old-image")
            unlink = log_archiving.os.unlink

            def fail_staged_image(path, *args, **kwargs):
                candidate = Path(path)
                if candidate.name == "pc_old.jpg" and candidate.parent.name.startswith(".backgrounds.archive-"):
                    raise PermissionError("staged image locked")
                return unlink(path, *args, **kwargs)

            with self.isolated_logging(root), patch("log_archiving.os.unlink", side_effect=fail_staged_image):
                main._BACKGROUND_SELECTION_STATE["old"] = "pc_old.jpg"
                main.setup_logging()
                self.assertFalse((backgrounds / "pc_old.jpg").exists())
                self.assertTrue((backgrounds / "background_state.json").exists())
                index = json.loads((backgrounds / "index.json").read_text(encoding="utf-8"))
                self.assertEqual(index, {"files": {}, "feedback": {}, "session_bindings": {}})
                self.assertEqual(main._BACKGROUND_SELECTION_STATE, {})
                staged = list(root.glob(".backgrounds.archive-*"))
                self.assertEqual(len(staged), 1)
                main.setup_logging()
                self.assertTrue((staged[0] / "pc_old.jpg").exists())


if __name__ == "__main__":
    unittest.main()
