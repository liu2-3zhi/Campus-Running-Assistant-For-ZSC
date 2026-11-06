import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from tests.backend_source_utils import read_backend_source


class TestAuthSystemSchoolAccounts(unittest.TestCase):
    def test_list_users_reuses_snapshot_until_account_files_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            system_accounts_dir = root / "system_accounts"
            school_accounts_dir = root / "school_accounts"
            user_accounts_dir = school_accounts_dir / "user_accounts"
            system_accounts_dir.mkdir()
            user_accounts_dir.mkdir(parents=True)
            user_file = system_accounts_dir / "user-file.json"
            user_file.write_text(json.dumps({"auth_username": "alice"}), encoding="utf-8")

            auth_system = object.__new__(main.AuthSystem)
            with patch.object(main, "SYSTEM_ACCOUNTS_DIR", str(system_accounts_dir)), patch.object(
                main, "SCHOOL_ACCOUNTS_DIR", str(school_accounts_dir)
            ), patch.object(
                auth_system,
                "_load_user_school_account_names",
                wraps=auth_system._load_user_school_account_names,
            ) as load_accounts:
                with patch("builtins.open", wraps=open) as open_file:
                    first = auth_system.list_users()
                    first_user_file_reads = open_file.call_count
                    second = auth_system.list_users()
                    self.assertEqual(first_user_file_reads, open_file.call_count)
                    self.assertEqual(1, load_accounts.call_count)
                user_file.write_text(
                    json.dumps({"auth_username": "alice", "nickname": "changed"}),
                    encoding="utf-8",
                )
                with patch("builtins.open", wraps=open) as open_file:
                    third = auth_system.list_users()
                    self.assertGreater(open_file.call_count, 0)
                self.assertEqual(2, load_accounts.call_count)

        self.assertEqual("", first[0]["nickname"])
        self.assertEqual("", second[0]["nickname"])
        self.assertEqual("changed", third[0]["nickname"])

    def test_list_users_returns_snapshot_copy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            system_accounts_dir = root / "system_accounts"
            school_accounts_dir = root / "school_accounts"
            (school_accounts_dir / "user_accounts").mkdir(parents=True)
            system_accounts_dir.mkdir()
            (system_accounts_dir / "user-file.json").write_text(
                json.dumps({"auth_username": "alice"}), encoding="utf-8"
            )
            auth_system = object.__new__(main.AuthSystem)
            with patch.object(main, "SYSTEM_ACCOUNTS_DIR", str(system_accounts_dir)), patch.object(
                main, "SCHOOL_ACCOUNTS_DIR", str(school_accounts_dir)
            ):
                first = auth_system.list_users()
                first[0]["nickname"] = "mutated"
                second = auth_system.list_users()

        self.assertEqual("", second[0]["nickname"])

    def test_user_list_cache_is_invalidated_after_profile_update(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            system_accounts_dir = root / "system_accounts"
            school_accounts_dir = root / "school_accounts"
            (school_accounts_dir / "user_accounts").mkdir(parents=True)
            system_accounts_dir.mkdir()
            user_file = system_accounts_dir / "user-file.json"
            user_file.write_text(
                json.dumps({"auth_username": "alice", "nickname": "Alice"}),
                encoding="utf-8",
            )
            auth_system = object.__new__(main.AuthSystem)
            with patch.object(main, "SYSTEM_ACCOUNTS_DIR", str(system_accounts_dir)), patch.object(
                main, "SCHOOL_ACCOUNTS_DIR", str(school_accounts_dir)
            ):
                first = auth_system.list_users()
                user_file.write_text(
                    json.dumps({"auth_username": "alice", "nickname": "New"}),
                    encoding="utf-8",
                )
                auth_system.invalidate_user_list_cache()
                second = auth_system.list_users()

        self.assertEqual("Alice", first[0]["nickname"])
        self.assertEqual("New", second[0]["nickname"])

    def test_background_worker_refreshes_after_external_file_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            system_accounts_dir = root / "system_accounts"
            school_accounts_dir = root / "school_accounts"
            (school_accounts_dir / "user_accounts").mkdir(parents=True)
            system_accounts_dir.mkdir()
            user_file = system_accounts_dir / "user-file.json"
            user_file.write_text(
                json.dumps({"auth_username": "alice", "nickname": "Alice"}),
                encoding="utf-8",
            )
            auth_system = object.__new__(main.AuthSystem)
            auth_system._user_list_cache_lock = threading.RLock()
            auth_system._user_list_cache = None
            auth_system._user_list_cache_signature = None
            auth_system._user_list_cache_stop = threading.Event()
            refreshed = threading.Event()
            original_refresh = auth_system._refresh_user_list_cache
            refresh_count = 0

            def track_refresh(signature):
                nonlocal refresh_count
                result = original_refresh(signature)
                refresh_count += 1
                if refresh_count > 1:
                    refreshed.set()
                return result

            with patch.object(main, "SYSTEM_ACCOUNTS_DIR", str(system_accounts_dir)), patch.object(
                main, "SCHOOL_ACCOUNTS_DIR", str(school_accounts_dir)
            ), patch("auth_system.USER_LIST_CACHE_REFRESH_SECONDS", 0.01), patch.object(
                auth_system, "_refresh_user_list_cache", side_effect=track_refresh
            ):
                auth_system.list_users()
                auth_system._user_list_cache_stop.set()
                auth_system._user_list_cache_stop.clear()
                worker = threading.Thread(target=auth_system._user_list_cache_worker, daemon=True)
                worker.start()
                user_file.write_text(
                    json.dumps({"auth_username": "alice", "nickname": "External"}),
                    encoding="utf-8",
                )
                self.assertTrue(refreshed.wait(1))
                auth_system._user_list_cache_stop.set()
                worker.join(1)
                users = auth_system.list_users()

        self.assertEqual("External", users[0]["nickname"])

    def test_list_users_loads_school_accounts_without_api_instance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            system_accounts_dir = root / "system_accounts"
            school_accounts_dir = root / "school_accounts"
            user_accounts_dir = school_accounts_dir / "user_accounts"
            system_accounts_dir.mkdir()
            user_accounts_dir.mkdir(parents=True)

            (system_accounts_dir / "user-file.json").write_text(
                json.dumps(
                    {
                        "auth_username": "alice",
                        "nickname": "Alice",
                        "group": "user",
                        "available_runs": 3,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (user_accounts_dir / "alice.json").write_text(
                json.dumps(
                    {
                        "20240001": {"password": "hidden", "ua": "ua"},
                        "20240002": "legacy-password",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            auth_system = object.__new__(main.AuthSystem)
            with patch.object(main, "SYSTEM_ACCOUNTS_DIR", str(system_accounts_dir)), patch.object(
                main, "SCHOOL_ACCOUNTS_DIR", str(school_accounts_dir)
            ):
                users = auth_system.list_users()

        self.assertEqual(1, len(users))
        self.assertEqual("alice", users[0]["auth_username"])
        self.assertEqual(["20240001", "20240002"], users[0]["school_accounts"])

    def test_list_users_uses_cached_city_without_external_lookup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            system_accounts_dir = root / "system_accounts"
            school_accounts_dir = root / "school_accounts"
            user_accounts_dir = school_accounts_dir / "user_accounts"
            system_accounts_dir.mkdir()
            user_accounts_dir.mkdir(parents=True)
            (system_accounts_dir / "user-file.json").write_text(
                json.dumps({
                    "auth_username": "alice",
                    "last_login_ip": "203.0.113.1",
                    "last_login_city": "广州",
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            auth_system = object.__new__(main.AuthSystem)
            with patch.object(main, "SYSTEM_ACCOUNTS_DIR", str(system_accounts_dir)), patch.object(
                main, "SCHOOL_ACCOUNTS_DIR", str(school_accounts_dir)
            ), patch.object(main, "get_ip_location", side_effect=AssertionError("external lookup"), create=True):
                users = auth_system.list_users()

        self.assertEqual("广州", users[0]["last_login_city"])

    def test_school_account_save_invalidates_shared_user_list_cache(self):
        from api_runtime import Api

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            school_accounts_dir = root / "school_accounts"
            (school_accounts_dir / "user_accounts").mkdir(parents=True)
            invalidated = []
            class FakeAuthSystem:
                def invalidate_user_list_cache(self):
                    invalidated.append(True)

            auth_system = FakeAuthSystem()
            api = object.__new__(Api)
            api.user_dir = str(school_accounts_dir)
            with patch.object(main, "auth_system", auth_system, create=True), patch.object(
                main, "SCHOOL_ACCOUNTS_DIR", str(school_accounts_dir)
            ), patch.object(
                main, "_auth_username_storage_key", side_effect=lambda value: value, create=True
            ), patch.object(main, "is_valid_school_username", return_value=True, create=True), patch.object(
                api, "_save_school_account_stats_to_ini"
            ):
                api._save_user_school_accounts("alice", {"20240001": {"password": "pw", "ua": "ua"}})

        self.assertEqual([True], invalidated)


class TestMapServerRuntime(unittest.TestCase):
    def test_backend_map_runtime_page_does_not_load_frontend_auth_bootstrap(self):
        source = read_backend_source()
        html = main._render_map_runtime_page()
        route_source = source[
            source.index("@app.route(MAP_RUNTIME_PATH, methods=[\"GET\"])") :
            source.index('@app.route("/")', source.index("@app.route(MAP_RUNTIME_PATH"))
        ]

        self.assertIn('@app.route(MAP_RUNTIME_PATH, methods=["GET"])', source)
        self.assertIn(
            "_is_map_runtime_request_authorized(",
            route_source,
        )
        self.assertIn("会话无效或未登录", route_source)
        self.assertIn("Map Runtime", html)
        self.assertNotIn("/scripts/main.js", html)
        self.assertNotIn("/uuid=", html)

    def test_backend_map_runtime_permission_requires_active_business_session(self):
        active_session = "11111111-1111-4111-8111-111111111111"
        missing_session = "22222222-2222-4222-8222-222222222222"

        with patch.object(
            main, "web_sessions", {active_session: object()}, create=True
        ), patch.object(
            main, "web_sessions_lock", threading.Lock(), create=True
        ):
            self.assertTrue(
                main._is_map_runtime_request_authorized(active_session)
            )
            self.assertFalse(
                main._is_map_runtime_request_authorized(missing_session)
            )
            self.assertFalse(main._is_map_runtime_request_authorized(""))

    def test_provider_runtime_queues_origin_instead_of_navigating_with_session(self):
        class Page:
            def goto(self, *_args, **_kwargs):
                raise AssertionError("来源准备必须由 execute_js 队列任务执行")

        class FakeChromePool:
            def get_context(self, _session_id):
                return {"page": Page()}

        provider_plan = {"provider": "tencent", "notices": ["provider notice"]}
        with patch.object(main, "chrome_pool", FakeChromePool(), create=True), patch.object(
            main, "_plan_route_with_map_provider", return_value=provider_plan
        ), patch.object(
            main,
            "_plan_route_path_with_tencent_runtime",
            return_value={"error": "来源准备失败"},
        ) as execute:
            result = main._plan_route_path_with_provider_runtime(
                "session-1",
                [{"lng": 113.1, "lat": 22.1}, {"lng": 113.2, "lat": 22.2}],
                provider="tencent",
                app_base_url="http://guangzhou.zelly.cn",
            )

        execution_plan = execute.call_args.args[3]
        self.assertEqual("http://guangzhou.zelly.cn", execution_plan["_runtime_page_origin"])
        self.assertEqual("request", execution_plan["_diagnostic_context"]["origin_source"])
        self.assertIsInstance(execution_plan["_deadline_epoch_ms"], (float, int))
        self.assertIn("来源准备失败", result["error"])
        self.assertEqual("tencent", result["provider"])
        self.assertEqual(provider_plan, result["provider_plan"])
        self.assertEqual(["provider notice"], result["notices"])

    def test_chrome_browser_context_ignores_https_errors_for_backend_map_runtime(self):
        source = "\n\n".join(
            (
                (
                    Path(main.__file__).resolve().parent
                    / "background_task_manager.py"
                ).read_text(encoding="utf-8"),
                read_backend_source(),
            )
        )
        context_source = source[
            source.index("context = self._browser.new_context(") : source.index(
                "page = context.new_page()",
                source.index("context = self._browser.new_context("),
            )
        ]

        self.assertIn("ignore_https_errors=True", context_source)


if __name__ == "__main__":
    unittest.main()
