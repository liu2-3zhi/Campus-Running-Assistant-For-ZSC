import tempfile
import unittest
from unittest.mock import Mock, patch

import main
from theme_background_state import BackgroundStateStore


class TestEmptyBackgroundBindings(unittest.TestCase):
    def test_login_and_guest_do_not_persist_empty_binding(self):
        for guest in (False, True):
            with self.subTest(guest=guest), tempfile.TemporaryDirectory() as directory:
                store = BackgroundStateStore(directory)
                with patch.object(main, "background_state_store", store), patch.object(
                    main, "_pick_available_background_image", return_value=""
                ), patch.object(main, "auth_system", Mock(), create=True):
                    if guest:
                        bundle = main._bind_guest_bundle_for_session("sid", "", "test", True)
                    else:
                        bundle = main._bind_login_bundle_for_user("alice", "", "test", True)
                    payload = main._bundle_to_public_payload(bundle)
                state = store.load()
                self.assertEqual(state["identity_bindings"], {})
                self.assertEqual(state["guest_bindings"], {})
                self.assertEqual(state["bundles"], {})
                self.assertEqual(payload["pc"]["image_url"], "")
                self.assertEqual(payload["mobile"]["image_url"], "")

    def test_empty_preview_does_not_create_persistent_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            with patch.object(main, "background_state_store", store), patch.object(
                main, "_pick_available_background_image", return_value=""
            ):
                preview = main._create_preview_bundle_payload()
            self.assertEqual(preview["pc"]["image_url"], "")
            self.assertEqual(store.load()["bundles"], {})

    def test_uuid_resolution_replaces_preexisting_empty_binding_when_cache_is_ready(self):
        for guest in (False, True):
            with self.subTest(guest=guest), tempfile.TemporaryDirectory() as directory:
                store = BackgroundStateStore(directory)
                empty = store.create_bundle("", "", "old-empty")
                if guest:
                    store.bind_guest_session("sid", empty["bundle_id"], "test")
                else:
                    store.bind_identity("user:alice", empty["bundle_id"], "test")
                with patch.object(main, "background_state_store", store), patch.object(
                    main, "_pick_available_background_image", side_effect=lambda target: f"/theme-assets/{target}.jpg"
                ), patch.object(main, "auth_system", Mock(), create=True):
                    payload = main._resolve_uuid_theme_background("sid", "alice", guest)
                self.assertEqual(payload["pc"]["image_url"], "/theme-assets/pc.jpg")
                self.assertEqual(payload["mobile"]["image_url"], "/theme-assets/mobile.jpg")
                self.assertNotEqual(payload["bundle_id"], empty["bundle_id"])

    def test_empty_preview_cannot_replace_nonempty_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            bound = store.create_bundle("/theme-assets/pc.jpg", "", "bound")
            store.bind_identity("user:alice", bound["bundle_id"], "test")
            preview = store.create_bundle("", "", "empty-preview", consume=False)
            with patch.object(main, "background_state_store", store), patch.object(
                main, "_pick_available_background_image", return_value=""
            ), patch.object(main, "auth_system", Mock(), create=True):
                resolved = main._bind_login_bundle_for_user("alice", preview["bundle_id"], "test", True)
            self.assertEqual(resolved["bundle_id"], bound["bundle_id"])

    def test_empty_payload_accepts_missing_bundle(self):
        self.assertEqual(main._bundle_to_public_payload(None), {
            "bundle_id": "", "revision": 0,
            "pc": {"image_url": "", "revision": 0},
            "mobile": {"image_url": "", "revision": 0},
        })


if __name__ == "__main__":
    unittest.main()
