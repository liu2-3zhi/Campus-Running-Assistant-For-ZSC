import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class TestAuthSystemSchoolAccounts(unittest.TestCase):
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


class TestMapServerRuntime(unittest.TestCase):
    def test_provider_runtime_stops_when_backend_origin_navigation_fails(self):
        class FailingPage:
            def goto(self, *_args, **_kwargs):
                raise RuntimeError("导航失败: Page.goto: net::ERR_CERT_DATE_INVALID")

        class FakeChromePool:
            def get_context(self, _session_id):
                return {"page": FailingPage()}

        provider_plan = {"provider": "tencent", "notices": ["provider notice"]}
        with patch.object(main, "chrome_pool", FakeChromePool(), create=True), patch.object(
            main, "_plan_route_with_map_provider", return_value=provider_plan
        ), patch.object(
            main,
            "_plan_route_path_with_tencent_runtime",
            side_effect=AssertionError("provider runtime should not run after origin navigation failure"),
        ):
            result = main._plan_route_path_with_provider_runtime(
                "session-1",
                [{"lng": 113.1, "lat": 22.1}, {"lng": 113.2, "lat": 22.2}],
                provider="tencent",
                app_base_url="http://guangzhou.zelly.cn",
            )

        self.assertIn("后端地图页面来源初始化失败", result["error"])
        self.assertEqual("tencent", result["provider"])
        self.assertEqual(provider_plan, result["provider_plan"])
        self.assertEqual(["provider notice"], result["notices"])

    def test_chrome_browser_context_ignores_https_errors_for_backend_map_runtime(self):
        source = Path(main.__file__).read_text(encoding="utf-8")
        context_source = source[
            source.index("context = self._browser.new_context(") : source.index(
                "page = context.new_page()",
                source.index("context = self._browser.new_context("),
            )
        ]

        self.assertIn("ignore_https_errors=True", context_source)


if __name__ == "__main__":
    unittest.main()
