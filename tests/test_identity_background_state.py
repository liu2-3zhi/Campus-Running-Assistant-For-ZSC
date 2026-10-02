import tempfile
import time
import unittest

from guest_token_store import GuestTokenStore
from theme_background_state import BackgroundStateStore, empty_state


class TestIdentityBackgroundState(unittest.TestCase):
    def test_empty_state_has_identity_and_guest_sections(self):
        state = empty_state()
        self.assertEqual(state["identity_bindings"], {})
        self.assertEqual(state["guest_bindings"], {})
        self.assertEqual(state["auth_claims"], {})

    def test_identity_bundle_replaces_without_touching_guest_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            first = store.create_bundle(
                "/theme-assets/random_background_image/pc_a.jpg",
                "/theme-assets/random_background_image/mb_a.jpg",
                "test",
            )
            second = store.create_bundle(
                "/theme-assets/random_background_image/pc_b.jpg",
                "/theme-assets/random_background_image/mb_b.jpg",
                "test",
            )
            store.bind_identity("user:admin", first["bundle_id"], "login")
            store.bind_guest_session("guest-session", first["bundle_id"], "guest")
            store.bind_identity("user:admin", second["bundle_id"], "login")
            self.assertEqual(
                store.get_identity_bundle("user:admin")["bundle_id"],
                second["bundle_id"],
            )
            self.assertEqual(
                store.get_guest_session_bundle("guest-session")["bundle_id"],
                first["bundle_id"],
            )

    def test_guest_token_is_refreshed_for_active_session(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GuestTokenStore(directory)
            session_id = "11111111-1111-4111-8111-111111111111"
            token = store.create(session_id)
            store._force_expiry_for_test(session_id, time.time() - 1)
            result = store.verify(
                session_id,
                token,
                session_active=True,
                session_expires_at=time.time() + 300,
            )
            self.assertTrue(result["valid"])
            self.assertEqual(result["reason"], "refreshed_for_active_session")

    def test_guest_exit_removes_only_current_guest_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            bundle = store.create_bundle(
                "/theme-assets/random_background_image/pc_a.jpg",
                "/theme-assets/random_background_image/mb_a.jpg",
                "guest",
            )
            store.bind_guest_session("guest-1", bundle["bundle_id"], "guest")
            store.bind_guest_session("guest-2", bundle["bundle_id"], "guest")
            store.remove_guest_binding("guest-1")
            self.assertIsNone(store.get_guest_session_bundle("guest-1"))
            self.assertIsNotNone(store.get_guest_session_bundle("guest-2"))


if __name__ == "__main__":
    unittest.main()
