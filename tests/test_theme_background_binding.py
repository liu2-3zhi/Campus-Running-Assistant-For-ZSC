import configparser
import datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import main as main_module
from main import (
    Api,
    AuthSystem,
    _get_session_theme_background_binding,
    _load_random_background_index,
    _resolve_theme_background_binding_decision,
    _save_random_background_index,
    _set_session_theme_background_binding,
)


class TestThemeBackgroundBinding(unittest.TestCase):
    def test_default_theme_prefers_unexpired_binding_for_pc_target(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            _set_session_theme_background_binding(
                str(cache_dir),
                session_uuid="sid-bound",
                target="pc",
                image_url="/theme-assets/random_background_image/pc_bound.jpg",
                ttl_seconds=1800,
            )

            auth_system = AuthSystem()
            with patch.object(
                auth_system,
                "_peek_default_theme_background_images",
                return_value={"pc": "/theme-assets/random_background_image/pc_random.jpg"},
            ):
                theme_config = auth_system.get_theme_config(
                    "default",
                    targets=["pc"],
                    session_uuid="sid-bound",
                    cache_dir=str(cache_dir),
                )

            env = theme_config["global_environment_variables"]
            self.assertIn("pc_bound.jpg", env["auth_login_container_background"])
            self.assertNotIn("pc_random.jpg", env["auth_login_container_background"])

    def test_default_theme_falls_back_to_random_when_binding_expired(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            _set_session_theme_background_binding(
                str(cache_dir),
                session_uuid="sid-expired",
                target="pc",
                image_url="/theme-assets/random_background_image/pc_old.jpg",
                ttl_seconds=1,
            )

            auth_system = AuthSystem()
            future_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                seconds=5
            )
            with patch("main.datetime.datetime") as mocked_datetime:
                mocked_datetime.now.return_value = future_now
                mocked_datetime.fromisoformat.side_effect = datetime.datetime.fromisoformat

                with patch.object(
                    auth_system,
                    "_peek_default_theme_background_images",
                    return_value={"pc": "/theme-assets/random_background_image/pc_random.jpg"},
                ):
                    theme_config = auth_system.get_theme_config(
                        "default",
                        targets=["pc"],
                        session_uuid="sid-expired",
                        cache_dir=str(cache_dir),
                    )

            env = theme_config["global_environment_variables"]
            self.assertIn("pc_random.jpg", env["auth_login_container_background"])
            self.assertNotIn("pc_old.jpg", env["auth_login_container_background"])

    def test_public_theme_styles_uses_web_session_id_for_binding_resolution(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d) / "random_background_image"
            cache_dir.mkdir(parents=True, exist_ok=True)
            _set_session_theme_background_binding(
                str(cache_dir),
                session_uuid="sid-api",
                target="pc",
                image_url="/theme-assets/random_background_image/pc_bound.jpg",
                ttl_seconds=1800,
            )

            api = Api.__new__(Api)
            api._web_session_id = "sid-api"
            auth_system = AuthSystem()

            with patch("main.auth_system", auth_system, create=True), patch(
                "main.os.path.abspath", return_value=str(cache_dir.parent / "main.py")
            ):
                result = api.get_public_theme_styles("default", "pc")

            self.assertTrue(result["success"])
            env = result["theme_config"]["global_environment_variables"]
            self.assertIn("pc_bound.jpg", env["auth_login_container_background"])

    def test_index_backward_compatible_with_session_bindings(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            index = _load_random_background_index(str(cache_dir))
            self.assertIn("files", index)
            self.assertIn("feedback", index)
            self.assertIn("session_bindings", index)

            index["session_bindings"]["sid-1"] = {
                "pc": {
                    "image_url": "/theme-assets/random_background_image/pc_a.jpg",
                    "bound_at": "2026-04-09T10:00:00+08:00",
                    "expires_at": "2099-01-01T00:00:00+00:00",
                }
            }
            _save_random_background_index(str(cache_dir), index)
            reloaded = _load_random_background_index(str(cache_dir))
            self.assertIn("sid-1", reloaded["session_bindings"])

    def test_set_and_get_binding_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            _set_session_theme_background_binding(
                str(cache_dir),
                session_uuid="sid-2",
                target="pc",
                image_url="/theme-assets/random_background_image/pc_b.jpg",
                ttl_seconds=1800,
            )
            binding = _get_session_theme_background_binding(str(cache_dir), "sid-2", "pc")
            self.assertIsNotNone(binding)
            self.assertEqual(
                binding["image_url"],
                "/theme-assets/random_background_image/pc_b.jpg",
            )

    def test_reuse_unexpired_binding(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            first = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-reuse",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_1.jpg",
                login_context=False,
                candidate_image_url="",
                ttl_seconds=1800,
            )
            self.assertEqual(first["action"], "bind_new")

            second = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-reuse",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_2.jpg",
                login_context=False,
                candidate_image_url="",
                ttl_seconds=1800,
            )
            self.assertEqual(second["action"], "reuse_existing")
            self.assertEqual(
                second["selected_image_url"],
                "/theme-assets/random_background_image/pc_1.jpg",
            )

    def test_login_context_overrides_unexpired_binding(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-override",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_old.jpg",
                login_context=False,
                candidate_image_url="",
                ttl_seconds=1800,
            )
            result = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-override",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_old.jpg",
                login_context=True,
                candidate_image_url="/theme-assets/random_background_image/pc_new.jpg",
                ttl_seconds=1800,
            )
            self.assertEqual(result["action"], "override_binding")
            self.assertEqual(
                result["selected_image_url"],
                "/theme-assets/random_background_image/pc_new.jpg",
            )

    def test_login_context_without_candidate_falls_back_to_current_image(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            result = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-fallback",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_current.jpg",
                login_context=True,
                candidate_image_url="",
                ttl_seconds=1800,
            )
            self.assertEqual(result["action"], "bind_new")
            self.assertEqual(
                result["selected_image_url"],
                "/theme-assets/random_background_image/pc_current.jpg",
            )

    def test_null_literal_session_uuid_is_treated_as_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            result = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="null",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_current.jpg",
                login_context=True,
                candidate_image_url="/theme-assets/random_background_image/pc_candidate.jpg",
                ttl_seconds=1800,
            )
            self.assertEqual(result["action"], "noop")
            self.assertEqual(
                result["selected_image_url"],
                "/theme-assets/random_background_image/pc_current.jpg",
            )
            index_data = _load_random_background_index(str(cache_dir))
            self.assertEqual(index_data.get("session_bindings", {}), {})
    def test_get_initial_data_uses_session_uuid_after_initialization(self):
        api = Api.__new__(Api)
        api._web_session_id = "sid-init"
        api.user_dir = tempfile.gettempdir()
        api.config_path = str(Path(tempfile.gettempdir()) / "config.ini")
        api.global_params = {"theme_style": "default", "amap_js_key": ""}
        api._load_global_config = Mock()
        api.is_authenticated = False
        api.is_guest = True
        api.login_success = False

        cfg = configparser.ConfigParser()
        cfg.add_section("Captcha")

        auth_system = Mock()
        auth_system.get_theme_config.return_value = {
            "global_environment_variables": {}
        }
        auth_system.get_available_theme_styles.return_value = ["default"]

        with patch("main._read_config_ini", return_value=cfg), patch(
            "main.auth_system", auth_system, create=True
        ), patch("main.os.listdir", return_value=[]), patch(
            "main.os.path.abspath", return_value=str(Path(tempfile.gettempdir()) / "main.py")
        ):
            result = api.get_initial_data()

        self.assertTrue(result["success"])
        auth_system.get_theme_config.assert_called_once_with(
            "default",
            session_uuid="sid-init",
            cache_dir=str(Path(tempfile.gettempdir()) / "random_background_image"),
        )

    def test_get_initial_data_reads_cdn_cache_from_module_globals(self):
        api = Api.__new__(Api)
        api._web_session_id = "sid-cdn"
        api.user_dir = tempfile.gettempdir()
        api.config_path = str(Path(tempfile.gettempdir()) / "config.ini")
        api.global_params = {"theme_style": "default", "amap_js_key": ""}
        api._load_global_config = Mock()
        api.is_authenticated = False
        api.is_guest = True
        api.login_success = False

        cfg = configparser.ConfigParser()
        cfg.add_section("Captcha")

        auth_system = Mock()
        auth_system.get_theme_config.return_value = {
            "global_environment_variables": {}
        }
        auth_system.get_available_theme_styles.return_value = ["default"]

        with patch("main._read_config_ini", return_value=cfg), patch(
            "main.auth_system", auth_system, create=True
        ), patch("main.os.listdir", return_value=[]), patch(
            "main.os.path.abspath", return_value=str(Path(tempfile.gettempdir()) / "main.py")
        ), patch.object(
            main_module,
            "CDN_FILES",
            {"demo": {"type": "js"}},
        ), patch.object(
            main_module,
            "js_cache_storage",
            {"demo": "console.log('ok')"},
        ), patch.object(
            main_module,
            "js_cache_last_update",
            {"demo": 1},
        ), patch.object(
            main_module,
            "js_cache_lock",
            main_module.threading.Lock(),
        ):
            result = api.get_initial_data()

        self.assertTrue(result["success"])
        self.assertEqual(result["cdn_cache"]["demo"]["type"], "js")
        self.assertTrue(result["cdn_cache"]["demo"]["cached"])


if __name__ == "__main__":
    unittest.main()
