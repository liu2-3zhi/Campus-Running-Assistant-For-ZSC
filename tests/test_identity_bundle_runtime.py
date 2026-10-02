import tempfile
import unittest
from unittest.mock import Mock, patch

import main as main_module
from theme_background_state import BackgroundStateStore


class TestIdentityBundleRuntime(unittest.TestCase):
    def test_quick_login_list_does_not_write_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            identity = {
                "authenticated": True,
                "principal_type": "user",
                "username": "alice",
                "session_id": "sid-1",
            }
            auth_system = Mock()
            auth_system.get_user_sessions.return_value = []
            with patch.object(main_module, "background_state_store", store), patch.object(
                main_module,
                "auth_system",
                auth_system,
                create=True,
            ), patch.object(store, "bind_identity") as bind_mock:
                result = main_module._list_selectable_sessions_for_identity(identity)
            self.assertEqual(result, [])
            bind_mock.assert_not_called()

    def test_identity_bundle_is_shared_without_active_uuid(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            bundle = store.create_bundle(
                "/theme-assets/random_background_image/pc_a.jpg",
                "/theme-assets/random_background_image/mb_a.jpg",
                "test",
            )
            store.bind_identity("user:admin", bundle["bundle_id"], "test")
            identity = {
                "authenticated": True,
                "principal_type": "user",
                "username": "admin",
                "session_id": "",
            }
            with patch.object(main_module, "background_state_store", store):
                resolved = (
                    main_module._resolve_identity_background_for_request_identity(
                        identity
                    )
                )
            self.assertEqual(resolved["bundle_id"], bundle["bundle_id"])


if __name__ == "__main__":
    unittest.main()
