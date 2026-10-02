import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main as main_module


class TestGuestRuntimeConfig(unittest.TestCase):
    def test_default_config_contains_guest_runtime_limits(self):
        config = main_module._get_default_config()
        self.assertEqual(config.get("Guest", "max_active_guest_sessions"), "100")
        self.assertEqual(
            config.get("Guest", "guest_session_inactivity_timeout"),
            "300",
        )
        self.assertEqual(config.get("Guest", "guest_token_ttl_seconds"), "3600")
        self.assertEqual(config.get("Guest", "guest_token_grace_seconds"), "60")

    def test_capacity_zero_rejects_before_session_creation(self):
        with tempfile.TemporaryDirectory() as directory, patch.multiple(
            main_module,
            SESSION_STORAGE_DIR=str(Path(directory) / "sessions"),
            CONFIG_FILE=str(Path(directory) / "config.ini"),
            create=True,
        ):
            Path(main_module.SESSION_STORAGE_DIR).mkdir(parents=True, exist_ok=True)
            result = main_module._create_guest_session_atomic(
                session_id="11111111-1111-4111-8111-111111111111",
                preview_bundle_id="bundle-preview",
                max_active_guest_sessions=0,
            )
            self.assertFalse(result["success"])
            self.assertEqual(result["code"], "guest_limit_reached")
            self.assertEqual(
                list(Path(main_module.SESSION_STORAGE_DIR).glob("*.json")),
                [],
            )

    def test_guest_config_updates_validate_capacity(self):
        config = main_module._get_default_config()
        with self.assertRaises(ValueError):
            main_module._apply_guest_config_updates(
                config,
                {"max_active_guest_sessions": -1},
            )


if __name__ == "__main__":
    unittest.main()
