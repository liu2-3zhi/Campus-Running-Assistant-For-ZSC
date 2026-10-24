import contextlib
import io
import json
import logging
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class TestLoggingJsonConfig(unittest.TestCase):
    @contextlib.contextmanager
    def isolated_logging(self, config_data):
        logger = logging.getLogger()
        previous_handlers = list(logger.handlers)
        previous_level = logger.level
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as resources:
            root = Path(directory)
            config_file = root / "config.json"
            config_file.write_text(json.dumps(config_data), encoding="utf-8")
            output = io.StringIO()
            resources.enter_context(contextlib.chdir(root))
            resources.enter_context(contextlib.redirect_stdout(output))
            for name, value in {
                "CONFIG_JSON_FILE": str(config_file),
                "RANDOM_BACKGROUND_IMAGE_DIR": str(root / "backgrounds"),
                "_logging_configured": False,
                "_logging_archive_manager": None,
                "_log_buffer": [],
                "_BACKGROUND_SELECTION_STATE": {},
                "log_dir": None,
                "archive_dir": None,
                "eventlet": types.SimpleNamespace(
                    patcher=types.SimpleNamespace(original=lambda name: threading)
                ),
            }.items():
                resources.enter_context(patch.object(main, name, value, create=True))
            resources.enter_context(patch.object(main, "_install_global_exception_logging"))
            logger.handlers = []
            try:
                yield root, output
            finally:
                for handler in logger.handlers:
                    handler.close()
                logger.handlers = previous_handlers
                logger.setLevel(previous_level)

    def test_real_json_logging_settings_configure_all_file_handlers(self):
        config_data = {
            "Logging": {
                "log_dir": "custom-logs",
                "archive_dir": "custom-archives",
                "log_rotation_size_mb": "3",
                "log_backup_count": "4",
                "archive_max_size_mb": "7",
            }
        }
        with self.isolated_logging(config_data) as (root, output):
            logger = main.setup_logging()
            handlers = [
                handler for handler in logger.handlers
                if isinstance(handler, main.CustomLogHandler)
            ]
            self.assertEqual(
                {Path(handler.baseFilename) for handler in handlers},
                {
                    root / "custom-logs" / "zx-slm-tool.log",
                    root / "custom-logs" / "zx-slm-tool-WARNING.log",
                    root / "custom-logs" / "zx-slm-tool-ERROR.log",
                },
            )
            self.assertEqual(len(handlers), 3)
            for handler in handlers:
                self.assertEqual(handler.max_bytes, 3 * 1024 * 1024)
                self.assertEqual(handler.backup_count, 4)
                self.assertEqual(handler.archive_manager.archive_dir, root / "custom-archives")
                self.assertEqual(handler.archive_manager.max_size_mb, 7)
            self.assertNotIn("读取配置失败", output.getvalue())
            self.assertFalse((root / "logs").exists())

    def test_json_without_logging_section_uses_defaults_without_read_failure(self):
        with self.isolated_logging({"System": {"name": "test"}}) as (root, output):
            logger = main.setup_logging()
            handlers = [
                handler for handler in logger.handlers
                if isinstance(handler, main.CustomLogHandler)
            ]
            self.assertEqual(len(handlers), 3)
            for handler in handlers:
                self.assertEqual(Path(handler.baseFilename).parent, root / "logs")
                self.assertEqual(handler.max_bytes, 10 * 1024 * 1024)
                self.assertEqual(handler.backup_count, 10)
                self.assertEqual(handler.archive_manager.archive_dir, root / "logs" / "archive")
                self.assertEqual(handler.archive_manager.max_size_mb, 5120)
            self.assertNotIn("读取配置失败", output.getvalue())


if __name__ == "__main__":
    unittest.main()
