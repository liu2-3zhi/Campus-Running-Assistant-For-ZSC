import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import main as main_module


class TestAuthSessionLifecycle(unittest.TestCase):
    def test_promote_auth_only_session_to_persistent_reuses_instance(self):
        source_id = "11111111-1111-4111-8111-111111111111"
        target_id = "22222222-2222-4222-8222-222222222222"
        api_instance = SimpleNamespace(
            _is_persistent_session=False,
            _web_session_id=source_id,
            _session_created_at=123456.0,
            auth_username="alice",
        )

        with mock.patch.multiple(
            main_module,
            web_sessions={source_id: api_instance},
            web_sessions_lock=main_module.threading.Lock(),
            create=True,
        ):
            promoted = main_module.promote_auth_session_to_persistent(
                source_id, target_id
            )

            self.assertIs(promoted, api_instance)
            self.assertNotIn(source_id, main_module.web_sessions)
            self.assertIs(main_module.web_sessions[target_id], api_instance)
            self.assertTrue(api_instance._is_persistent_session)
            self.assertEqual(api_instance._web_session_id, target_id)

    def test_temporary_auth_context_is_not_a_business_session(self):
        self.assertFalse(
            main_module.is_persistent_business_session(
                SimpleNamespace(_is_persistent_session=False)
            )
        )
        self.assertTrue(
            main_module.is_persistent_business_session(
                SimpleNamespace(_is_persistent_session=True)
            )
        )
        self.assertTrue(main_module.is_persistent_business_session(SimpleNamespace()))

    def test_get_initial_data_is_the_only_auth_optional_generic_api(self):
        self.assertTrue(
            main_module.is_auth_optional_api_method("get_initial_data")
        )
        self.assertFalse(main_module.is_auth_optional_api_method("load_tasks"))
        self.assertFalse(main_module.is_auth_optional_api_method("update_param"))

    def test_get_initial_data_with_unrestorable_session_uses_auth_optional_context(self):
        self.assertTrue(
            main_module.should_use_auth_optional_api_context(
                "get_initial_data",
                "22222222-2222-4222-8222-222222222222",
                session_exists=False,
                restored_state=None,
            )
        )
        self.assertTrue(
            main_module.should_use_auth_optional_api_context(
                "get_initial_data",
                "22222222-2222-4222-8222-222222222222",
                session_exists=False,
                restored_state={"login_success": False},
            )
        )
        self.assertFalse(
            main_module.should_use_auth_optional_api_context(
                "get_initial_data",
                "22222222-2222-4222-8222-222222222222",
                session_exists=False,
                restored_state={"login_success": True},
            )
        )
        self.assertFalse(
            main_module.should_use_auth_optional_api_context(
                "load_tasks",
                "22222222-2222-4222-8222-222222222222",
                session_exists=False,
                restored_state=None,
            )
        )
        auth_optional_api = SimpleNamespace(
            _is_persistent_session=False,
            _web_session_id="",
        )
        self.assertEqual(
            main_module.resolve_auth_optional_api_session_id(
                "get_initial_data",
                "22222222-2222-4222-8222-222222222222",
                auth_optional_api,
            ),
            "",
        )
        persistent_api = SimpleNamespace(
            _is_persistent_session=True,
            _web_session_id="22222222-2222-4222-8222-222222222222",
        )
        self.assertEqual(
            main_module.resolve_auth_optional_api_session_id(
                "get_initial_data",
                "22222222-2222-4222-8222-222222222222",
                persistent_api,
            ),
            "22222222-2222-4222-8222-222222222222",
        )

    def test_auth_only_login_context_is_not_saved_as_persistent_session(self):
        auth_session_id = "11111111-1111-4111-8111-111111111111"
        auth_only_api = SimpleNamespace(
            _is_persistent_session=False,
            _session_created_at=123456.0,
            auth_username="alice",
            auth_group="user",
            is_guest=False,
            is_authenticated=True,
            all_run_data=[],
            current_run_idx=-1,
        )

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.multiple(
            main_module,
            session_file_locks={},
            session_file_locks_lock=main_module.threading.Lock(),
            SESSION_STORAGE_DIR=str(Path(temp_dir) / "sessions"),
            SESSION_INDEX_FILE=str(Path(temp_dir) / "sessions" / "_index.json"),
            create=True,
        ):
            Path(main_module.SESSION_STORAGE_DIR).mkdir(parents=True, exist_ok=True)

            main_module.save_session_state(auth_session_id, auth_only_api, force_save=True)

            self.assertEqual(list(Path(main_module.SESSION_STORAGE_DIR).glob("*.json")), [])
            self.assertFalse(Path(main_module.SESSION_INDEX_FILE).exists())

    def test_login_without_existing_business_session_returns_auth_context_only(self):
        requested_uuid = "22222222-2222-4222-8222-222222222222"

        def auth_login_like_flow(requested_session_id, auth_result):
            session_id = main_module.normalize_session_uuid(requested_session_id)
            api_instance = None
            session_is_persistent = bool(auth_result.get("is_guest", False))

            if session_id:
                if session_id in main_module.web_sessions:
                    api_instance = main_module.web_sessions[session_id]
                    session_is_persistent = getattr(
                        api_instance, "_is_persistent_session", True
                    )
                else:
                    state = main_module.load_session_state(session_id)
                    if state:
                        api_instance = SimpleNamespace()
                        api_instance._session_created_at = state.get("created_at", 0)
                        api_instance._web_session_id = session_id
                        api_instance._is_persistent_session = True
                        main_module.web_sessions[session_id] = api_instance
                        session_is_persistent = True

            if api_instance is None:
                session_id = "33333333-3333-4333-8333-333333333333"
                api_instance = SimpleNamespace()
                api_instance._session_created_at = 123456.0
                api_instance._web_session_id = session_id
                api_instance._is_persistent_session = session_is_persistent
                main_module.web_sessions[session_id] = api_instance

            api_instance.auth_username = auth_result["auth_username"]
            api_instance.auth_group = auth_result["group"]
            api_instance.is_guest = auth_result.get("is_guest", False)
            api_instance.is_authenticated = True

            if session_is_persistent or auth_result.get("is_guest", False):
                main_module.save_session_state(session_id, api_instance, force_save=True)

            return {
                "session_id": session_id if session_is_persistent else None,
                "auth_session_id": session_id,
            }

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.multiple(
            main_module,
            web_sessions={},
            session_file_locks={},
            session_file_locks_lock=main_module.threading.Lock(),
            SESSION_STORAGE_DIR=str(Path(temp_dir) / "sessions"),
            SESSION_INDEX_FILE=str(Path(temp_dir) / "sessions" / "_index.json"),
            create=True,
        ):
            Path(main_module.SESSION_STORAGE_DIR).mkdir(parents=True, exist_ok=True)
            response = auth_login_like_flow(
                requested_uuid,
                {"auth_username": "alice", "group": "user", "is_guest": False},
            )

            self.assertIsNone(response["session_id"])
            self.assertEqual(
                response["auth_session_id"], "33333333-3333-4333-8333-333333333333"
            )
            self.assertNotIn(requested_uuid, main_module.web_sessions)
            self.assertIn(response["auth_session_id"], main_module.web_sessions)
            self.assertEqual(list(Path(main_module.SESSION_STORAGE_DIR).glob("*.json")), [])
            self.assertFalse(Path(main_module.SESSION_INDEX_FILE).exists())

    def test_admin_origin_session_context_uses_origin_identity(self):
        target_session_id = "22222222-2222-4222-8222-222222222222"
        origin_session_id = "11111111-1111-4111-8111-111111111111"
        target_api = SimpleNamespace(
            _web_session_id=target_session_id,
            is_authenticated=True,
            is_guest=False,
            auth_username="alice",
            auth_group="user",
        )
        origin_api = SimpleNamespace(
            _web_session_id=origin_session_id,
            is_authenticated=True,
            is_guest=False,
            auth_username="manager",
            auth_group="admin",
        )
        token_manager = SimpleNamespace(
            verify_token=mock.Mock(return_value=(True, "valid")),
        )
        auth_system = SimpleNamespace(
            check_permission=mock.Mock(return_value=True),
        )

        with mock.patch.multiple(
            main_module,
            web_sessions={
                target_session_id: target_api,
                origin_session_id: origin_api,
            },
            web_sessions_lock=main_module.threading.Lock(),
            token_manager=token_manager,
            auth_system=auth_system,
            create=True,
        ):
            context = main_module.resolve_admin_origin_session_context(
                target_session_id,
                origin_session_id,
                "admin-cookie",
            )

        self.assertIsNotNone(context)
        self.assertEqual(context["username"], "manager")
        self.assertIs(context["api_instance"], origin_api)
        token_manager.verify_token.assert_called_once_with(
            "manager",
            origin_session_id,
            "admin-cookie",
        )
        auth_system.check_permission.assert_called_once_with(
            "manager",
            "view_all_sessions",
        )

    def test_admin_session_status_uses_multi_account_login_state(self):
        multi_account = SimpleNamespace(
            user_data=SimpleNamespace(id="student-1"),
            is_first_login_verified=True,
        )
        target_api = SimpleNamespace(
            is_multi_account_mode=True,
            accounts={"alice-school": multi_account},
        )

        self.assertTrue(
            main_module.get_business_session_login_success(target_api)
        )
        self.assertTrue(
            main_module.get_business_session_login_success(
                SimpleNamespace(
                    is_multi_account_mode=True,
                    accounts={
                        "restored-account": SimpleNamespace(
                            login_success=True,
                            user_data=SimpleNamespace(id=""),
                            is_first_login_verified=False,
                        )
                    },
                )
            )
        )
        self.assertFalse(
            main_module.get_business_session_login_success(
                SimpleNamespace(
                    is_multi_account_mode=True,
                    accounts={
                        "inactive-account": SimpleNamespace(
                            user_data=SimpleNamespace(id="student-2"),
                            is_first_login_verified=False,
                        )
                    },
                )
            )
        )
        self.assertFalse(
            main_module.get_business_session_login_success(
                SimpleNamespace(
                    is_multi_account_mode=True,
                    accounts={},
                )
            )
        )
        self.assertTrue(
            main_module.get_business_session_login_success(
                SimpleNamespace(
                    is_multi_account_mode=False,
                    login_success=True,
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
