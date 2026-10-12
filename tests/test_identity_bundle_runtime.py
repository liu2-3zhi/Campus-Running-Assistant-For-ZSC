import tempfile
import unittest
from unittest.mock import Mock, patch

from flask import Flask

import main as main_module
from theme_background_state import BackgroundStateStore


class TestIdentityBundleRuntime(unittest.TestCase):
    def test_public_uuid_background_survives_invalid_cookie_without_writes(self):
        app = Flask(__name__)
        for is_guest in (False, True):
            for target in ("pc", "mobile"):
                with self.subTest(is_guest=is_guest, target=target), tempfile.TemporaryDirectory() as directory:
                    store = BackgroundStateStore(directory)
                    bundle = store.create_bundle("/theme-assets/pc_bound.jpg", "/theme-assets/mb_bound.jpg", "test")
                    if is_guest:
                        store.bind_guest_session("sid-bound", bundle["bundle_id"], "test")
                    else:
                        store.bind_identity("user:alice", bundle["bundle_id"], "test")
                    auth_system = Mock()
                    auth_system.get_theme_config.return_value = {"global_environment_variables": {}}
                    api = main_module.Api.__new__(main_module.Api)
                    api._web_session_id = "sid-bound"
                    with app.test_request_context(headers={"Cookie": "auth_token=expired"}), patch.object(
                        main_module, "background_state_store", store
                    ), patch.object(main_module, "auth_system", auth_system, create=True), patch.object(
                        main_module, "load_session_state", return_value={"auth_username": "alice", "is_guest": is_guest}
                    ), patch.object(store, "create_bundle") as create, patch.object(store, "bind_identity") as bind, patch.object(
                        store, "bind_guest_session"
                    ) as guest_bind:
                        result = api.get_public_theme_styles("default", target)
                    env = result["theme_config"]["global_environment_variables"]
                    self.assertIn("pc_bound.jpg", env.get("auth_login_container_background", ""))
                    self.assertIn("mb_bound.jpg", env.get("mobile_auth_login_content_background", ""))
                    create.assert_not_called()
                    bind.assert_not_called()
                    guest_bind.assert_not_called()
                    auth_system._refresh_default_theme_background_cache_async.assert_not_called()

    def test_login_without_preview_reuses_existing_bundle_without_random_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            bundle = store.create_bundle("/theme-assets/pc_bound.jpg", "/theme-assets/mb_bound.jpg", "test")
            store.bind_identity("user:alice", bundle["bundle_id"], "test")
            with patch.object(main_module, "background_state_store", store), patch.object(
                main_module, "_pick_available_background_image"
            ) as pick, patch.object(store, "create_bundle") as create:
                resolved = main_module._bind_login_bundle_for_user("alice", "", "login_preview", True)
            self.assertEqual(resolved["bundle_id"], bundle["bundle_id"])
            pick.assert_not_called()
            create.assert_not_called()

    def test_bootstrap_uuid_fallback_reads_binding_when_cookie_is_expired(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            bundle = store.create_bundle(
                "/theme-assets/pc_bound.jpg",
                "/theme-assets/mb_bound.jpg",
                "test",
            )
            store.bind_identity("user:alice", bundle["bundle_id"], "test")
            with patch.object(main_module, "background_state_store", store), patch.object(
                main_module,
                "_resolve_request_identity",
                return_value={"authenticated": False, "principal_type": "anonymous"},
            ), patch.object(
                main_module,
                "load_session_state",
                return_value={"auth_username": "alice", "is_guest": False},
            ), patch.object(main_module, "_create_preview_bundle_payload") as preview:
                result = main_module._build_site_bootstrap_response(
                    "11111111-1111-4111-8111-111111111111"
                )

            self.assertEqual(result["theme_background"]["source"], "identity_binding")
            self.assertEqual(
                result["theme_background"]["pc"]["image_url"],
                "/theme-assets/pc_bound.jpg",
            )
            preview.assert_not_called()

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
