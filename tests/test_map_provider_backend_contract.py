import unittest
from pathlib import Path
import ast
import base64
import json
import logging
import re
import subprocess
import tempfile
import threading
from types import SimpleNamespace
from unittest import mock

from flask import Flask

import main as main_module


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_ROOT / "main.py"
DOCKER_ENTRYPOINT_PATH = PROJECT_ROOT / "docker" / "docker-entrypoint.sh"


class TestMapProviderBackendContract(unittest.TestCase):
    def _decode_obfuscated_runtime_script(self, script):
        match = re.search(
            r"const\s+_[0-9a-f]+='([^']+)',_[0-9a-f]+='([^']+)';",
            script,
        )
        self.assertIsNotNone(match)
        payload = base64.b64decode(match.group(1))
        mask = base64.b64decode(match.group(2))
        decoded = bytes(
            byte ^ mask[index % len(mask)]
            for index, byte in enumerate(payload)
        )
        return decoded.decode("utf-8")

    def _runtime_config_with_map(self, provider, providers):
        temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
        self.addCleanup(lambda path=temp.name: Path(path).unlink(missing_ok=True))
        temp.write("{}")
        temp.close()
        runtime_config = main_module.JsonConfigAdapter(temp.name)
        runtime_config.add_section("Map")
        runtime_config.set("Map", "provider", provider)
        runtime_config.set("Map", "providers", providers)
        return runtime_config

    def _route_helper_execute_js_source(self, helper_name):
        source = MAIN_PATH.read_text(encoding="utf-8")
        module = ast.parse(source)
        for node in ast.walk(module):
            if isinstance(node, ast.FunctionDef) and node.name == helper_name:
                for sub_node in ast.walk(node):
                    if (
                        isinstance(sub_node, ast.Call)
                        and isinstance(sub_node.func, ast.Attribute)
                        and sub_node.func.attr == "execute_js"
                    ):
                        js_arg = sub_node.args[1]
                        self.assertIsInstance(js_arg, ast.Constant)
                        self.assertIsInstance(js_arg.value, str)
                        return js_arg.value
        self.fail(f"{helper_name} execute_js source not found")

    def test_frontend_config_includes_map_provider_contract(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('"map_provider"', source)
        self.assertIn('"map_providers"', source)
        self.assertIn('"amap"', source)
        self.assertIn('"tencent"', source)
        self.assertIn('"tianditu"', source)
        self.assertIn('"baidu"', source)

    def test_admin_config_save_accepts_global_provider_and_multi_provider_keys(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('if "Map" in data and "provider" in data["Map"]:', source)
        self.assertIn('config.set("Map", "provider",', source)
        self.assertIn('providers = data["Map"].get("providers") or {}', source)
        self.assertIn('amap_provider = providers.get("amap") or {}', source)
        self.assertIn('tencent_provider = providers.get("tencent") or {}', source)
        self.assertIn('tianditu_provider = providers.get("tianditu") or {}', source)
        self.assertIn('baidu_provider = providers.get("baidu") or {}', source)
        self.assertIn('config.set(\n                    "Map",\n                    "providers",', source)
        self.assertIn('for legacy_key in [', source)
        self.assertIn('config.remove_option("Map", legacy_key)', source)

    def test_backend_exposes_map_provider_resolution_helpers(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('MAP_PROVIDER_KEY_FIELDS = {', source)
        self.assertIn('def _get_active_map_provider(', source)
        self.assertIn('def _get_map_provider_runtime_config(', source)
        self.assertIn('def _get_map_provider_frontend_config(', source)
        self.assertIn('def _normalize_map_provider(', source)
        self.assertIn('def _resolve_amap_js_key(', source)

    def test_backend_runtime_config_exposes_provider_display_and_business_coordinates(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        runtime_source = source[
            source.index("def _get_map_provider_runtime_config("):
            source.index("def _get_map_provider_frontend_config(", source.index("def _get_map_provider_runtime_config("))
        ]

        self.assertIn('"coordinate_system": "gcj02"', runtime_source)
        self.assertIn('"business_coordinate_system": "gcj02"', runtime_source)
        self.assertIn('"coordinate_system": "wgs84"', runtime_source)
        self.assertIn('"coordinate_system": "bd09"', runtime_source)

    def test_backend_exposes_generic_map_provider_key_save_method(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('def save_map_provider_key(self, provider, api_key):', source)
        self.assertIn('key_field = MAP_PROVIDER_KEY_FIELDS[provider]', source)
        self.assertIn('"save_map_provider_key": "modify_params"', source)

    def test_tianditu_walking_falls_back_to_driving_with_explicit_notice(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('provider == "tianditu" and route_mode == "walking"', source)
        self.assertIn('actual_mode = "driving"', source)
        self.assertIn('当前地图供应商不支持步行规划，已自动使用驾车规划代替', source)

    def test_route_planning_no_longer_hardcodes_amap_walking_only(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('def _plan_route_with_map_provider(', source)
        self.assertIn('provider_config = _get_map_provider_runtime_config(', source)
        self.assertIn('provider = _get_active_map_provider(', source)
        self.assertIn('plugins = _get_map_provider_plugins(', source)

    def test_initial_data_uses_encrypted_map_provider_bundle(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn("def _build_public_map_provider_frontend_payload(", source)
        self.assertIn('"map_provider_key_bundle": map_public_payload["map_provider_key_bundle"]', source)

    def test_initial_data_and_login_return_map_provider_contract(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        get_initial_data_source = source[
            source.index("    def get_initial_data("):
            source.index("    def save_amap_key(", source.index("    def get_initial_data("))
        ]
        login_source = source[
            source.rindex("    def login(", 0, source.index("    def logout(")):
            source.index("    def logout(")
        ]

        self.assertIn(
            'map_public_payload = _build_public_map_provider_frontend_payload(',
            get_initial_data_source,
        )
        self.assertIn('"map_provider": map_public_payload["map_provider"]', get_initial_data_source)
        self.assertIn('"map_providers": map_public_payload["map_providers"]', get_initial_data_source)
        self.assertIn('"map_provider_key_bundle": map_public_payload["map_provider_key_bundle"]', get_initial_data_source)
        self.assertIn('login_map_payload = _build_public_map_provider_frontend_payload(', login_source)
        self.assertIn('"map_provider": login_map_payload["map_provider"]', login_source)
        self.assertIn('"map_providers": login_map_payload["map_providers"]', login_source)
        self.assertIn('"map_provider_key_bundle": login_map_payload["map_provider_key_bundle"]', login_source)

    def test_initial_data_returns_running_background_task_status_for_provider_lock(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        get_initial_data_source = source[
            source.index("    def get_initial_data("):
            source.index("    def save_amap_key(", source.index("    def get_initial_data("))
        ]

        self.assertIn("background_task_manager.get_task_status(session_uuid)", get_initial_data_source)
        self.assertIn('"task_status"', get_initial_data_source)
        self.assertIn('task_status.get("status") in ("running", "paused")', get_initial_data_source)

    def test_provider_runtime_dispatches_each_configured_provider(self):
        runtime_config = self._runtime_config_with_map("amap", {
            "amap": {"js_key": "amap-key"},
            "tencent": {"map_key": "tencent-key"},
            "tianditu": {"token": "tianditu-token"},
            "baidu": {"ak": "baidu-ak"},
        })

        class ChromePoolStub:
            def get_context(self, session_id):
                return {"page": mock.Mock(on=mock.Mock())}

        helper_results = {
            "amap": {"path": [{"lng": 1, "lat": 1}]},
            "tencent": {"path": [{"lng": 2, "lat": 2}]},
            "tianditu": {"path": [{"lng": 3, "lat": 3}]},
            "baidu": {"path": [{"lng": 4, "lat": 4}]},
        }
        called = []

        def make_helper(provider):
            def _helper(session_id, page, waypoints, provider_plan, python_params):
                called.append((provider, provider_plan["actual_mode"], provider_plan["provider_config"]))
                return helper_results[provider].copy()
            return _helper

        with mock.patch.object(main_module, "chrome_pool", ChromePoolStub(), create=True), \
             mock.patch.object(main_module, "_plan_route_path_with_amap_runtime", side_effect=make_helper("amap")), \
             mock.patch.object(main_module, "_plan_route_path_with_tencent_runtime", side_effect=make_helper("tencent")), \
             mock.patch.object(main_module, "_plan_route_path_with_tianditu_runtime", side_effect=make_helper("tianditu")), \
             mock.patch.object(main_module, "_plan_route_path_with_baidu_runtime", side_effect=make_helper("baidu")):
            results = {
                provider: main_module._plan_route_path_with_provider_runtime(
                    "session-1",
                    [[113.39, 22.52], [113.40, 22.53]],
                    python_params={"api_retries": 0},
                    provider=provider,
                    runtime_config=runtime_config,
                )
                for provider in ["amap", "tencent", "tianditu", "baidu"]
            }

        self.assertEqual([item[0] for item in called], ["amap", "tencent", "tianditu", "baidu"])
        self.assertEqual(called[0][2]["js_key"], "amap-key")
        self.assertEqual(called[1][2]["map_key"], "tencent-key")
        self.assertEqual(called[2][2]["token"], "tianditu-token")
        self.assertEqual(called[3][2]["ak"], "baidu-ak")
        self.assertEqual(results["amap"]["provider"], "amap")
        self.assertEqual(results["tencent"]["provider"], "tencent")
        self.assertEqual(results["tianditu"]["provider"], "tianditu")
        self.assertEqual(results["baidu"]["provider"], "baidu")

    def test_strip_map_provider_secret_fields_removes_raw_keys(self):
        sanitized = main_module._strip_map_provider_secret_fields(
            {
                "amap": {"provider": "amap", "js_key": "a"},
                "tencent": {"provider": "tencent", "map_key": "b"},
                "tianditu": {"provider": "tianditu", "token": "c"},
                "baidu": {"provider": "baidu", "ak": "d"},
            }
        )
        self.assertNotIn("js_key", sanitized["amap"])
        self.assertNotIn("map_key", sanitized["tencent"])
        self.assertNotIn("token", sanitized["tianditu"])
        self.assertNotIn("ak", sanitized["baidu"])

    def test_sensitive_initialization_logs_do_not_include_credentials_or_signed_content(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertNotIn("密码: admin", source)
        self.assertNotIn("发现可能的密码: {found_pwds}", source)
        self.assertIn("发现 {len(found_pwds)} 个可能的历史密码", source)
        self.assertNotIn("当前Session的Cookies:", source)
        self.assertNotIn("使用shiroCookie作为认证令牌进行Authorization请求头设置:", source)
        self.assertNotIn("Initial users={users}", source)
        self.assertNotIn("token: {token_preview}", source)
        self.assertIn('print("[管理员账号] 创建默认管理员账号 (用户名: admin)...")', source)
        self.assertIn('logging.info(f"[RSA验签] 待验证原文长度: {len(content)}")', source)
        self.assertNotIn('logging.info(f"[RSA验签] 待验证原文: {content}")', source)

    def test_build_map_provider_key_bundle_encrypts_secrets(self):
        bundle = main_module._build_map_provider_key_bundle(
            {
                "amap": {"js_key": "amap-key"},
                "tencent": {"map_key": "tencent-key"},
                "tianditu": {"token": "tianditu-key"},
                "baidu": {"ak": "baidu-key"},
            },
            provider="amap",
        )
        self.assertNotIn("algorithm", bundle)
        self.assertRegex(
            bundle["runtime_script"],
            r"^/api/map_key_runtime\.js\?v=[0-9a-f]+$",
        )
        self.assertEqual(set(bundle["providers"]), {"amap"})
        self.assertNotEqual(bundle["providers"]["amap"]["ciphertext"], "")
        self.assertNotEqual(bundle["providers"]["amap"]["ciphertext"], "amap-key")

    def test_build_map_provider_key_bundle_returns_only_requested_provider(self):
        bundle = main_module._build_map_provider_key_bundle(
            {
                "amap": {"js_key": "amap-key"},
                "tencent": {"map_key": "tencent-key"},
                "tianditu": {"token": "tianditu-key"},
                "baidu": {"ak": "baidu-key"},
            },
            provider="tencent",
        )

        self.assertEqual(bundle["provider"], "tencent")
        self.assertEqual(set(bundle["providers"]), {"tencent"})
        self.assertEqual(bundle["providers"]["tencent"]["field"], "map_key")
        self.assertNotIn("amap", bundle["providers"])
        self.assertNotIn("baidu", bundle["providers"])

    def test_map_key_runtime_context_can_be_initialized_for_each_server_start(self):
        first_context = {
            "runtime_version": "first-runtime",
            "runtime_script": "first-script",
        }
        second_context = {
            "runtime_version": "second-runtime",
            "runtime_script": "second-script",
        }

        with mock.patch.object(
            main_module,
            "_generate_map_key_runtime_context",
            side_effect=[first_context, second_context],
            create=True,
        ) as generate_context:
            main_module.map_key_runtime_cache.clear()
            first = dict(main_module._initialize_map_key_runtime())
            main_module.map_key_runtime_cache.clear()
            second = dict(main_module._initialize_map_key_runtime())

        for runtime_map in (
            main_module.map_key_runtime_cache,
            main_module.map_key_runtime_session_contexts,
            main_module.map_key_runtime_session_users,
            main_module.map_key_runtime_user_contexts,
            main_module.map_key_runtime_contexts_by_version,
        ):
            runtime_map.clear()
        self.assertEqual(first, first_context)
        self.assertEqual(second, second_context)
        self.assertEqual(generate_context.call_count, 2)

    def test_map_key_runtime_reuses_user_context_until_last_session_is_released(self):
        first_context = {
            "runtime_version": "user-runtime-1",
            "runtime_script": "user-script-1",
        }
        second_context = {
            "runtime_version": "user-runtime-2",
            "runtime_script": "user-script-2",
        }
        runtime_maps = (
            main_module.map_key_runtime_cache,
            main_module.map_key_runtime_session_contexts,
            main_module.map_key_runtime_session_users,
            main_module.map_key_runtime_user_contexts,
            main_module.map_key_runtime_contexts_by_version,
        )

        for runtime_map in runtime_maps:
            runtime_map.clear()
        try:
            with mock.patch.object(
                main_module,
                "_generate_map_key_runtime_context",
                side_effect=[first_context, second_context],
            ):
                first = main_module._get_map_key_runtime_context_for_session(
                    "session-1", "alice"
                )
                reused = main_module._get_map_key_runtime_context_for_session(
                    "session-2", "alice"
                )
                main_module._release_map_key_runtime_session("session-1")
                still_active = main_module._get_map_key_runtime_context_for_session(
                    "session-2", "alice"
                )
                main_module._release_map_key_runtime_session("session-2")
                regenerated = main_module._get_map_key_runtime_context_for_session(
                    "session-3", "alice"
                )
        finally:
            for runtime_map in runtime_maps:
                runtime_map.clear()

        self.assertIs(first, first_context)
        self.assertIs(reused, first_context)
        self.assertIs(still_active, first_context)
        self.assertIs(regenerated, second_context)

    def test_map_key_runtime_rotates_after_anonymous_session_authenticates(self):
        anonymous_context = {
            "runtime_version": "anonymous-runtime",
            "runtime_script": "anonymous-script",
        }
        authenticated_context = {
            "runtime_version": "authenticated-runtime",
            "runtime_script": "authenticated-script",
        }
        runtime_maps = (
            main_module.map_key_runtime_cache,
            main_module.map_key_runtime_session_contexts,
            main_module.map_key_runtime_session_users,
            main_module.map_key_runtime_user_contexts,
            main_module.map_key_runtime_contexts_by_version,
        )

        for runtime_map in runtime_maps:
            runtime_map.clear()
        try:
            with mock.patch.object(
                main_module,
                "_generate_map_key_runtime_context",
                side_effect=[anonymous_context, authenticated_context],
            ) as generate_context:
                anonymous = main_module._get_map_key_runtime_context_for_session(
                    "session-1", None
                )
                authenticated = main_module._get_map_key_runtime_context_for_session(
                    "session-1", "alice"
                )

            self.assertIs(anonymous, anonymous_context)
            self.assertIs(authenticated, authenticated_context)
            self.assertEqual(generate_context.call_count, 2)
        finally:
            for runtime_map in runtime_maps:
                runtime_map.clear()

    def test_map_key_runtime_without_session_uses_global_fallback(self):
        fallback_context = {
            "runtime_version": "fallback-runtime",
            "runtime_script": "fallback-script",
        }
        runtime_maps = (
            main_module.map_key_runtime_cache,
            main_module.map_key_runtime_session_contexts,
            main_module.map_key_runtime_session_users,
            main_module.map_key_runtime_user_contexts,
            main_module.map_key_runtime_contexts_by_version,
        )

        for runtime_map in runtime_maps:
            runtime_map.clear()
        try:
            with mock.patch.object(
                main_module,
                "_generate_map_key_runtime_context",
                return_value=fallback_context,
            ) as generate_context:
                result = main_module._get_map_key_runtime_context_for_session(
                    None, None
                )

            self.assertEqual(result, fallback_context)
            self.assertEqual(main_module.map_key_runtime_session_contexts, {})
            self.assertEqual(main_module.map_key_runtime_session_users, {})
            self.assertEqual(main_module.map_key_runtime_user_contexts, {})
            self.assertEqual(
                dict(main_module.map_key_runtime_contexts_by_version),
                {"fallback-runtime": main_module.map_key_runtime_cache},
            )
            self.assertIs(
                main_module.map_key_runtime_contexts_by_version["fallback-runtime"],
                main_module.map_key_runtime_cache,
            )
            generate_context.assert_called_once_with()
        finally:
            for runtime_map in runtime_maps:
                runtime_map.clear()

    def test_map_key_runtime_is_served_from_api_with_no_store_headers(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn('@app.route("/api/map_key_runtime.js")', source)
        self.assertIn('@app.route("/api/map_provider_keys/decrypt"', source)
        self.assertIn("def _decrypt_map_provider_key_bundle(", source)
        self.assertIn('return _apply_no_cache_headers(response)', source)
        self.assertIn(
            '"runtime_script": _get_map_key_runtime_script_url(',
            source,
        )
        scripts_source = source[source.index('@app.route("/scripts/<path:filename>")'):]
        self.assertNotIn(
            'runtime_js = _ensure_map_key_runtime_cache().get("runtime_script", "")',
            scripts_source,
        )

    def test_generated_map_key_runtime_hides_static_crypto_material(self):
        runtime_template = main_module._load_map_key_runtime_template()
        script = main_module._build_obfuscated_map_key_runtime_script(
            "runtime-secret-version",
        )
        decoded_script = self._decode_obfuscated_runtime_script(script)

        for clear_text in (
            "__MAP_KEY_RUNTIME_PRIVATE_KEY_PEM__",
            "BEGIN PRIVATE KEY",
            "secret-private-key",
            "RSA-OAEP",
            "SHA-256",
            "pkcs8",
            "crypto.subtle",
            "runtimePrivateKeyPem",
        ):
            self.assertNotIn(clear_text, runtime_template)
            self.assertNotIn(clear_text, script)
            self.assertNotIn(clear_text, decoded_script)
        self.assertIn('"/api/map_provider_keys/decrypt"', runtime_template)
        self.assertIn('"/api/map_provider_keys/decrypt"', decoded_script)
        self.assertNotIn("__MAP_KEY_RUNTIME__", script)
        self.assertNotIn("decryptMapProviderKeys", script)
        self.assertNotIn("/api/map_provider_keys/decrypt", script)
        self.assertNotIn("runtime-secret-version", script)
        self.assertLessEqual(script.count("\n"), 2)

    def test_server_decrypts_map_provider_bundle_without_client_private_key(self):
        context = main_module._generate_map_key_runtime_context()
        bundle = main_module._build_map_provider_key_bundle(
            {
                "amap": {"js_key": "amap-server-secret"},
                "tencent": {"map_key": "tencent-server-secret"},
            },
            provider="amap",
            runtime_context=context,
        )

        decrypted = main_module._decrypt_map_provider_key_bundle(bundle, context)

        self.assertEqual(decrypted, {"amap": {"js_key": "amap-server-secret"}})
        self.assertNotIn("private_key", json.dumps(bundle, ensure_ascii=False))

    def test_map_provider_decrypt_request_requires_active_session_and_version(self):
        app = Flask(__name__)
        session_id = "55555555-5555-4555-8555-555555555555"
        context = main_module._generate_map_key_runtime_context()
        bundle = main_module._build_map_provider_key_bundle(
            {"amap": {"js_key": "amap-endpoint-secret"}},
            provider="amap",
            runtime_context=context,
        )
        tencent_bundle = main_module._build_map_provider_key_bundle(
            {"tencent": {"map_key": "tencent-endpoint-secret"}},
            provider="tencent",
            runtime_context=context,
        )
        bundle["providers"]["tencent"] = tencent_bundle["providers"]["tencent"]
        runtime_maps = (
            main_module.map_key_runtime_cache,
            main_module.map_key_runtime_session_contexts,
            main_module.map_key_runtime_session_users,
            main_module.map_key_runtime_user_contexts,
            main_module.map_key_runtime_contexts_by_version,
        )
        original_web_sessions = getattr(main_module, "web_sessions", None)
        original_web_sessions_lock = getattr(main_module, "web_sessions_lock", None)

        for runtime_map in runtime_maps:
            runtime_map.clear()
        main_module.web_sessions = {
            session_id: SimpleNamespace(is_guest=False, auth_username="alice")
        }
        main_module.web_sessions_lock = threading.RLock()
        main_module.map_key_runtime_session_contexts[session_id] = context
        main_module.map_key_runtime_session_users[session_id] = "alice"
        main_module.map_key_runtime_user_contexts["alice"] = context
        main_module.map_key_runtime_contexts_by_version[
            context["runtime_version"]
        ] = context

        try:
            with app.test_request_context(
                f"/api/map_provider_keys/decrypt?v={context['runtime_version']}",
                method="POST",
                headers={"X-Session-ID": session_id},
                json={
                    "runtime_version": context["runtime_version"],
                    "bundle": bundle,
                },
            ):
                response = main_module._decrypt_map_provider_keys_for_request()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.get_json(),
                    {
                        "success": True,
                        "providers": {
                            "amap": {"js_key": "amap-endpoint-secret"}
                        },
                    },
                )
                self.assertIn("no-store", response.headers.get("Cache-Control", ""))

            with app.test_request_context(
                "/api/map_provider_keys/decrypt?v=wrong-runtime",
                method="POST",
                headers={"X-Session-ID": session_id},
                json={
                    "runtime_version": "wrong-runtime",
                    "bundle": bundle,
                },
            ):
                response = main_module._decrypt_map_provider_keys_for_request()
                self.assertEqual(response.status_code, 404)
                self.assertFalse(response.get_json()["success"])

            with app.test_request_context(
                f"/api/map_provider_keys/decrypt?v={context['runtime_version']}",
                method="POST",
                headers={"Referer": f"http://localhost/uuid={session_id}"},
                json={
                    "runtime_version": context["runtime_version"],
                    "bundle": bundle,
                },
            ):
                response = main_module._decrypt_map_provider_keys_for_request()
                self.assertEqual(response.status_code, 404)
                self.assertFalse(response.get_json()["success"])
        finally:
            for runtime_map in runtime_maps:
                runtime_map.clear()
            if original_web_sessions is not None:
                main_module.web_sessions = original_web_sessions
            else:
                delattr(main_module, "web_sessions")
            if original_web_sessions_lock is not None:
                main_module.web_sessions_lock = original_web_sessions_lock
            else:
                delattr(main_module, "web_sessions_lock")

    def test_generated_map_key_runtime_executes_obfuscated_payload(self):
        context = main_module._generate_map_key_runtime_context()
        session_id = "11111111-1111-4111-8111-111111111111"
        secret = "amap-runtime-secret-from-api"
        payload = json.dumps(
            {
                "script": context["runtime_script"],
                "runtime_version": context["runtime_version"],
                "session_id": session_id,
                "secret": secret,
            }
        )
        node_script = r"""
const payload = JSON.parse(process.argv[process.argv.length - 1]);
const { TextDecoder } = require("util");
globalThis.TextDecoder = TextDecoder;
globalThis.window = globalThis;
globalThis.location = { pathname: `/uuid=${payload.session_id}` };
globalThis.sessionStorage = {
  getItem(name) {
    return name === "session_uuid" ? payload.session_id : "";
  },
};
if (!globalThis.atob) {
  globalThis.atob = (value) => Buffer.from(value, "base64").toString("binary");
}
globalThis.fetch = async (url, options) => {
  if (!String(url).includes("/api/map_provider_keys/decrypt?v=" + encodeURIComponent(payload.runtime_version))) {
    throw new Error("unexpected decrypt endpoint: " + url);
  }
  if (!options || options.method !== "POST") {
    throw new Error("decrypt request must use POST");
  }
  if (!options.headers || options.headers["X-Session-ID"] !== payload.session_id) {
    throw new Error("missing session header");
  }
  const body = JSON.parse(options.body || "{}");
  if (body.runtime_version !== payload.runtime_version) {
    throw new Error("missing runtime version");
  }
  if (!body.bundle || !body.bundle.providers || !body.bundle.providers.amap) {
    throw new Error("missing key bundle");
  }
  return {
    ok: true,
    json: async () => ({ success: true, providers: { amap: { js_key: payload.secret } } }),
  };
};
(async () => {
  eval(payload.script);
  const runtime = globalThis.__MAP_KEY_RUNTIME__;
  if (!runtime || typeof runtime.decryptMapProviderKeys !== "function") {
    throw new Error("runtime unavailable");
  }
  const result = await runtime.decryptMapProviderKeys({
    runtime_version: payload.runtime_version,
    providers: {
      amap: { field: "js_key", ciphertext: "server-only-ciphertext" },
    },
  });
  if (!result.amap || result.amap.js_key !== payload.secret) {
    throw new Error("server decrypt result mismatch");
  }
})().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});
"""
        result = subprocess.run(
            ["node", "-e", node_script, payload],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )

    def test_map_key_runtime_template_is_not_public_static_asset(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        entrypoint_source = DOCKER_ENTRYPOINT_PATH.read_text(encoding="utf-8")

        self.assertFalse((PROJECT_ROOT / "scripts" / "map_key_runtime.js").exists())
        self.assertNotIn('"scripts", MAP_KEY_RUNTIME_SCRIPT_NAME', source)
        self.assertIn(
            r"location ~* ^/scripts/map_key_runtime\.js$",
            entrypoint_source,
        )

    def test_server_start_initializes_a_fresh_map_key_runtime(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        start_source = source[source.index("def start_web_server(args_param):"):]

        self.assertIn("_initialize_map_key_runtime()", start_source)

    def test_api_logging_redacts_sensitive_parameters(self):
        redacted = main_module._redact_sensitive_log_value(
            {
                "api_key": "real-map-key",
                "nested": [{"password": "real-password"}],
                "safe": "visible",
            }
        )

        self.assertEqual(redacted["api_key"], "<redacted>")
        self.assertEqual(redacted["nested"][0]["password"], "<redacted>")
        self.assertEqual(redacted["safe"], "visible")

        redacted_nested = main_module._redact_sensitive_log_value(
            {
                "platform_data": {"token": "real-token"},
                "pay_info": "real-pay-info",
                "api_response": {"secret": "real-secret"},
                "safe": "visible",
            }
        )
        for field in ("platform_data", "pay_info", "api_response"):
            self.assertEqual(redacted_nested[field], "<redacted>")
        self.assertEqual(redacted_nested["safe"], "visible")

        redacted_text = main_module._redact_sensitive_log_value(
            "password=real-password token:real-token api_key=real-key"
        )
        self.assertEqual(
            redacted_text,
            "password=<redacted> token:<redacted> api_key=<redacted>",
        )
        self.assertEqual(
            main_module._redact_sensitive_log_text(
                "https://example.invalid/sms?u=user&p=real-key&phone=1"
            ),
            "https://example.invalid/sms?u=user&p=<redacted>&phone=1",
        )

        quoted_record = logging.LogRecord(
            "test",
            logging.INFO,
            __file__,
            1,
            "{'password': 'real-password', 'auth_code': 'real-auth', "
            "'pay_url': 'https://pay.example.invalid/pay?token=real-token'}",
            (),
            None,
        )
        rendered = main_module.SensitiveLogFormatter("%(message)s").format(
            quoted_record
        )
        for secret in ("real-password", "real-auth", "real-token"):
            self.assertNotIn(secret, rendered)

    def test_sensitive_persisted_payment_logs_are_redacted_at_boundary(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn(
            "full_log_data = _redact_sensitive_log_value({",
            source,
        )
        self.assertIn('"pay_url",', source)
        self.assertIn('"return_url",', source)
        self.assertIn('"notify_url",', source)

    def test_auth_config_does_not_return_legacy_raw_map_key(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        auth_config_source = source[
            source.index('@app.route("/auth/get_config"'):
            source.index('@app.route("/auth/check_uuid_type"')
        ]

        self.assertIn('"allow_guest_login": allow_guest_login', auth_config_source)
        self.assertNotIn('"amap_js_key": amap_js_key', auth_config_source)

    def test_frontend_config_normalizes_session_header_before_runtime_binding(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        config_route_source = source[
            source.index('def api_frontend_config():'):
            source.index('@app.route("/api/cdn/<file_key>")')
        ]

        self.assertIn(
            'session_id = normalize_session_uuid(',
            config_route_source,
        )

    def test_map_runtime_request_rejects_unvalidated_session_header(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        runtime_request_source = source[
            source.index("def _get_map_key_runtime_context_for_request("):
            source.index("def _initialize_map_key_runtime(")
        ]

        self.assertIn(
            'session_id = normalize_session_uuid(',
            runtime_request_source,
        )

    def test_session_uuid_normalization_is_case_insensitive(self):
        session_id = "ABCDEFAB-CDEF-4ABC-8ABC-ABCDEFABCDEF"

        self.assertEqual(
            main_module.normalize_session_uuid(session_id),
            session_id.lower(),
        )

    def test_map_runtime_request_binds_version_to_active_session(self):
        first_session = "11111111-1111-4111-8111-111111111111"
        second_session = "22222222-2222-4222-8222-222222222222"
        unknown_session = "33333333-3333-4333-8333-333333333333"
        first_context = {
            "runtime_version": "first-runtime",
            "runtime_script": "first-script",
        }
        second_context = {
            "runtime_version": "second-runtime",
            "runtime_script": "second-script",
        }
        runtime_maps = (
            main_module.map_key_runtime_cache,
            main_module.map_key_runtime_session_contexts,
            main_module.map_key_runtime_session_users,
            main_module.map_key_runtime_user_contexts,
            main_module.map_key_runtime_contexts_by_version,
        )
        original_web_sessions = getattr(main_module, "web_sessions", None)
        original_web_sessions_lock = getattr(main_module, "web_sessions_lock", None)
        request_obj = SimpleNamespace(
            headers={"X-Session-ID": first_session},
            referrer=None,
            args={"v": "first-runtime"},
        )

        for runtime_map in runtime_maps:
            runtime_map.clear()
        main_module.web_sessions = {
            first_session: SimpleNamespace(
                is_guest=False,
                auth_username="alice",
            ),
            second_session: SimpleNamespace(
                is_guest=False,
                auth_username="bob",
            ),
        }
        main_module.web_sessions_lock = threading.RLock()
        main_module.map_key_runtime_session_contexts.update(
            {
                first_session: first_context,
                second_session: second_context,
            }
        )
        main_module.map_key_runtime_session_users.update(
            {
                first_session: "alice",
                second_session: "bob",
            }
        )
        main_module.map_key_runtime_user_contexts.update(
            {"alice": first_context, "bob": second_context}
        )
        main_module.map_key_runtime_contexts_by_version.update(
            {
                "first-runtime": first_context,
                "second-runtime": second_context,
            }
        )

        try:
            with mock.patch.object(
                main_module,
                "request",
                request_obj,
                create=True,
            ), mock.patch.object(
                main_module,
                "_generate_map_key_runtime_context",
                side_effect=AssertionError("unknown sessions must not allocate contexts"),
            ):
                self.assertIs(
                    main_module._get_map_key_runtime_context_for_request(),
                    first_context,
                )
                request_obj.args["v"] = "second-runtime"
                self.assertIsNone(
                    main_module._get_map_key_runtime_context_for_request()
                )
                request_obj.headers["X-Session-ID"] = unknown_session
                request_obj.args["v"] = "first-runtime"
                self.assertIsNone(
                    main_module._get_map_key_runtime_context_for_request()
                )
        finally:
            for runtime_map in runtime_maps:
                runtime_map.clear()
            if original_web_sessions is not None:
                main_module.web_sessions = original_web_sessions
            else:
                delattr(main_module, "web_sessions")
            if original_web_sessions_lock is not None:
                main_module.web_sessions_lock = original_web_sessions_lock
            else:
                delattr(main_module, "web_sessions_lock")

    def test_public_map_payload_does_not_allocate_runtime_without_active_session(self):
        runtime_config = self._runtime_config_with_map(
            "amap",
            {"amap": {"js_key": "amap-key"}},
        )
        unknown_session = "44444444-4444-4444-8444-444444444444"
        original_web_sessions = getattr(main_module, "web_sessions", None)
        original_web_sessions_lock = getattr(main_module, "web_sessions_lock", None)
        runtime_maps = (
            main_module.map_key_runtime_cache,
            main_module.map_key_runtime_session_contexts,
            main_module.map_key_runtime_session_users,
            main_module.map_key_runtime_user_contexts,
            main_module.map_key_runtime_contexts_by_version,
        )

        for runtime_map in runtime_maps:
            runtime_map.clear()
        main_module.web_sessions = {}
        main_module.web_sessions_lock = threading.RLock()
        try:
            with mock.patch.object(
                main_module,
                "_generate_map_key_runtime_context",
                side_effect=AssertionError("inactive sessions must not allocate contexts"),
            ):
                payload = main_module._build_public_map_provider_frontend_payload(
                    runtime_config,
                    session_id=unknown_session,
                )
        finally:
            for runtime_map in runtime_maps:
                runtime_map.clear()
            if original_web_sessions is not None:
                main_module.web_sessions = original_web_sessions
            else:
                delattr(main_module, "web_sessions")
            if original_web_sessions_lock is not None:
                main_module.web_sessions_lock = original_web_sessions_lock
            else:
                delattr(main_module, "web_sessions_lock")

        bundle = payload["map_provider_key_bundle"]
        self.assertFalse(bundle["available"])
        self.assertEqual(set(bundle["providers"]), {"amap"})
        self.assertEqual(bundle["providers"]["amap"]["ciphertext"], "")

    def test_legacy_config_recovery_does_not_create_unknown_uuid_sessions(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        legacy_config_source = source[
            source.index('@app.route("/api/frontend_config.js")'):
            source.index("# Vue 前端自动构建", source.index('@app.route("/api/frontend_config.js")'))
        ]

        self.assertIn("state = load_session_state(uuid)", legacy_config_source)
        self.assertIn("if state:", legacy_config_source)
        self.assertIn("拒绝恢复未登记会话", legacy_config_source)
        self.assertIn("web_sessions[uuid] = api_instance", legacy_config_source)

    def test_map_runtime_static_route_blocks_runtime_script_case_insensitively(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        scripts_source = source[source.index('@app.route("/scripts/<path:filename>")'):]

        self.assertIn("MAP_KEY_RUNTIME_SCRIPT_NAME.casefold()", scripts_source)

    def test_sensitive_error_paths_do_not_return_exception_text(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn(
            'return jsonify({"success": False, "message": "网络请求失败，请稍后重试"})',
            source,
        )
        self.assertIn(
            '"message": "创建订单失败，请稍后重试"',
            source,
        )
        self.assertIn(
            '"message": "创建账单支付订单失败，请稍后重试"',
            source,
        )
        self.assertNotIn(
            '"message": f"网络请求失败: {str(e)}"',
            source,
        )
        self.assertNotIn(
            '"message": f"创建订单失败: {str(e)}"',
            source,
        )
        self.assertNotIn(
            '"message": f"创建账单支付订单失败: {str(e)}"',
            source,
        )
        self.assertNotIn(
            '"message": f"退款失败：{result_msg}"',
            source,
        )
        self.assertIn(
            '"message": "退款失败，请稍后重试"',
            source,
        )

    def test_sensitive_frontend_logs_do_not_dump_payment_or_pricing_payloads(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        legacy_source = (
            PROJECT_ROOT / "scripts" / "main.new.js"
        ).read_text(encoding="utf-8")
        request_log_start = legacy_source.index(
            "[PC端测试支付] 发送创建订单请求"
        )
        request_log_end = legacy_source.index(
            "const response = await fetch",
            request_log_start,
        )

        self.assertNotIn("订单数据: {order_data}", source)
        self.assertNotIn("数据：{local_order_data}", source)
        self.assertNotIn(
            "JSON.stringify(requestData)",
            legacy_source[request_log_start:request_log_end],
        )
        self.assertIn(
            'console.log("[价格配置] 正在保存价格配置");',
            legacy_source,
        )
        self.assertIn(
            'console.log("[价格配置] 正在保存价格配置（移动端）");',
            legacy_source,
        )
        self.assertNotIn(
            "print(f\"获取token成功: {result['access_token']}\")",
            source,
        )

    def test_payment_order_responses_use_minimal_whitelists(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        helper_start = source.index("def _build_payment_order_response(")
        helper_end = source.index(
            "def _get_billing_scope_from_order_data(",
            helper_start,
        )
        helper_source = source[helper_start:helper_end]

        for field in (
            "platform_data",
            "order_data",
            "notify_params",
            "api_response",
            "active_query_token_hash",
            "active_query_session_hash",
        ):
            self.assertNotIn(f'"{field}"', helper_source)
        self.assertIn('"pay_url"', helper_source)
        self.assertIn("if status == ORDER_STATUS_PENDING", helper_source)

        orders_start = source.index('@app.route("/api/payment/orders"')
        orders_end = source.index(
            '@app.route("/api/payment/order_by_tradeno"',
            orders_start,
        )
        orders_source = source[orders_start:orders_end]
        self.assertNotIn("orders.append(order_data)", orders_source)
        self.assertIn("_build_payment_order_response(", orders_source)
        self.assertNotIn('"order": order_data', source)

    def test_payment_logs_are_sanitized_before_return(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn(
            "log_entry = _redact_sensitive_log_value(log_entry)",
            source,
        )
        self.assertIn(
            "log_data = _redact_sensitive_log_value(log_data)",
            source,
        )
        self.assertIn(
            "log_detail = _redact_sensitive_log_value(log_detail)",
            source,
        )

    def test_session_cleanup_releases_map_runtime_context(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn(
            '_release_map_key_runtime_session(session_id, runtime_username)',
            source,
        )
        cleanup_worker_source = source[
            source.index("def cleanup_sessions():"):
            source.index("cleanup_thread = threading.Thread", source.index("def cleanup_sessions():"))
        ]
        self.assertIn(
            "for session_id in expired_sessions:\n                    _release_map_key_runtime_session(session_id)",
            cleanup_worker_source,
        )

    def test_provider_runtime_navigates_to_session_page_before_backend_js_execution(self):
        runtime_config = self._runtime_config_with_map("amap", {
            "amap": {"js_key": "amap-key"},
        })
        page = mock.Mock(on=mock.Mock(), goto=mock.Mock())

        class ChromePoolStub:
            def get_context(self, session_id):
                return {"page": page}

        def amap_helper(session_id, helper_page, waypoints, provider_plan, python_params):
            page.goto.assert_called_once_with(
                "http://127.0.0.1:5000/uuid=session-1",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            self.assertIs(helper_page, page)
            return {"path": [{"lng": 1, "lat": 1}]}

        with mock.patch.object(main_module, "chrome_pool", ChromePoolStub(), create=True), \
             mock.patch.object(main_module, "_plan_route_path_with_amap_runtime", side_effect=amap_helper):
            result = main_module._plan_route_path_with_provider_runtime(
                "session-1",
                [[113.39, 22.52], [113.40, 22.53]],
                provider="amap",
                runtime_config=runtime_config,
                app_base_url="http://127.0.0.1:5000/",
            )

        self.assertEqual(result["provider"], "amap")
        self.assertIn("path", result)

    def test_provider_runtime_reports_unavailable_chrome_pool_with_provider_context(self):
        runtime_config = self._runtime_config_with_map("tencent", {
            "tencent": {"map_key": "tencent-key"},
        })

        with mock.patch.object(main_module, "chrome_pool", None, create=True):
            result = main_module._plan_route_path_with_provider_runtime(
                "session-1",
                [[113.39, 22.52], [113.40, 22.53]],
                runtime_config=runtime_config,
            )

        self.assertEqual(result["provider"], "tencent")
        self.assertIn("Chrome浏览器池不可用", result["error"])

    def test_tianditu_provider_runtime_returns_driving_notice_for_walking_contract(self):
        runtime_config = self._runtime_config_with_map("tianditu", {
            "tianditu": {"token": "tianditu-token"},
        })

        class ChromePoolStub:
            def get_context(self, session_id):
                return {"page": mock.Mock(on=mock.Mock())}

        def tianditu_helper(session_id, page, waypoints, provider_plan, python_params):
            self.assertEqual(provider_plan["actual_mode"], "driving")
            return {"path": [{"lng": 113.39, "lat": 22.52}, {"lng": 113.40, "lat": 22.53}]}

        with mock.patch.object(main_module, "chrome_pool", ChromePoolStub(), create=True), \
             mock.patch.object(main_module, "_plan_route_path_with_tianditu_runtime", side_effect=tianditu_helper):
            result = main_module._plan_route_path_with_provider_runtime(
                "session-1",
                [[113.39, 22.52], [113.40, 22.53]],
                runtime_config=runtime_config,
            )

        self.assertEqual(result["provider"], "tianditu")
        self.assertIn("当前地图供应商不支持步行规划，已自动使用驾车规划代替", result["notices"])

    def test_tencent_provider_runtime_completes_snapped_route_endpoints(self):
        runtime_config = self._runtime_config_with_map("tencent", {
            "tencent": {"map_key": "tencent-key"},
        })

        class ChromePoolStub:
            def get_context(self, session_id):
                return {"page": mock.Mock(on=mock.Mock())}

        snapped_path = [
            {"lng": 113.391, "lat": 22.521},
            {"lng": 113.399, "lat": 22.529},
        ]

        def tencent_helper(session_id, page, waypoints, provider_plan, python_params):
            return {"path": snapped_path.copy()}

        with mock.patch.object(main_module, "chrome_pool", ChromePoolStub(), create=True), \
             mock.patch.object(main_module, "_plan_route_path_with_tencent_runtime", side_effect=tencent_helper):
            result = main_module._plan_route_path_with_provider_runtime(
                "session-1",
                [[113.39, 22.52], [113.40, 22.53]],
                runtime_config=runtime_config,
            )

        self.assertEqual(result["provider"], "tencent")
        self.assertEqual(result["path"][0], {"lng": 113.39, "lat": 22.52})
        self.assertEqual(result["path"][1], snapped_path[0])
        self.assertEqual(result["path"][-2], snapped_path[-1])
        self.assertEqual(result["path"][-1], {"lng": 113.40, "lat": 22.53})

    def test_tencent_provider_runtime_preserves_intermediate_waypoint_coordinates(self):
        runtime_config = self._runtime_config_with_map("tencent", {
            "tencent": {"map_key": "tencent-key"},
        })

        class ChromePoolStub:
            def get_context(self, session_id):
                return {"page": mock.Mock(on=mock.Mock())}

        waypoints = [
            [113.3900, 22.5200],
            [113.3950, 22.5250],
            [113.4000, 22.5300],
        ]
        snapped_path = [
            {"lng": 113.3902, "lat": 22.5202},
            {"lng": 113.3948, "lat": 22.5248},
            {"lng": 113.3952, "lat": 22.5252},
            {"lng": 113.3998, "lat": 22.5298},
        ]

        def tencent_helper(session_id, page, helper_waypoints, provider_plan, python_params):
            self.assertEqual(helper_waypoints, waypoints)
            return {"path": snapped_path.copy()}

        with mock.patch.object(main_module, "chrome_pool", ChromePoolStub(), create=True), \
             mock.patch.object(main_module, "_plan_route_path_with_tencent_runtime", side_effect=tencent_helper):
            result = main_module._plan_route_path_with_provider_runtime(
                "session-1",
                waypoints,
                runtime_config=runtime_config,
            )

        self.assertIn({"lng": 113.395, "lat": 22.525}, result["path"])
        self.assertLess(
            result["path"].index({"lng": 113.395, "lat": 22.525}),
            result["path"].index({"lng": 113.4, "lat": 22.53}),
        )

    def test_provider_route_helpers_report_missing_keys_before_external_js_calls(self):
        page = mock.Mock(goto=mock.Mock())
        waypoints = [[113.39, 22.52], [113.40, 22.53]]

        helpers = [
            (
                main_module._plan_route_path_with_amap_runtime,
                {"provider_config": {"js_key": ""}, "actual_mode": "walking", "plugins": ["AMap.Walking"]},
                "未配置高德地图 JS Key",
            ),
            (
                main_module._plan_route_path_with_tencent_runtime,
                {"provider_config": {"map_key": ""}, "actual_mode": "walking"},
                "未配置腾讯地图 Key",
            ),
            (
                main_module._plan_route_path_with_tianditu_runtime,
                {"provider_config": {"token": ""}, "actual_mode": "driving"},
                "未配置天地图 Token",
            ),
            (
                main_module._plan_route_path_with_baidu_runtime,
                {"provider_config": {"ak": ""}, "actual_mode": "walking"},
                "未配置百度地图 AK",
            ),
        ]

        chrome_pool_mock = mock.Mock(execute_js=mock.Mock())
        with mock.patch.object(main_module, "chrome_pool", chrome_pool_mock, create=True):
            for helper, provider_plan, error_text in helpers:
                with self.subTest(helper=helper.__name__):
                    result = helper("session-1", page, waypoints, provider_plan, python_params={})
                    self.assertIn(error_text, result["error"])

        chrome_pool_mock.execute_js.assert_not_called()
        page.goto.assert_not_called()

    def test_provider_route_helpers_call_chrome_executor_with_provider_credentials(self):
        waypoints = [[113.39, 22.52], [113.40, 22.53]]
        expected_calls = [
            (
                main_module._plan_route_path_with_amap_runtime,
                {"provider_config": {"js_key": "amap-key"}, "actual_mode": "walking", "plugins": ["AMap.Walking"]},
                ["amap-key", {"api_retries": 0}, ["AMap.Walking"], "walking"],
            ),
            (
                main_module._plan_route_path_with_tencent_runtime,
                {"provider_config": {"map_key": "tencent-key"}, "actual_mode": "walking"},
                ["tencent-key", {"api_retries": 0}, "walking"],
            ),
            (
                main_module._plan_route_path_with_tianditu_runtime,
                {"provider_config": {"token": "tianditu-token"}, "actual_mode": "driving"},
                ["tianditu-token", {"api_retries": 0}, "driving"],
            ),
            (
                main_module._plan_route_path_with_baidu_runtime,
                {"provider_config": {"ak": "baidu-ak"}, "actual_mode": "walking"},
                ["baidu-ak", {"api_retries": 0}, "walking"],
            ),
        ]

        for helper, provider_plan, expected_tail in expected_calls:
            with self.subTest(helper=helper.__name__):
                page = mock.Mock(goto=mock.Mock())
                chrome_pool_mock = mock.Mock(
                    execute_js=mock.Mock(return_value={"path": [{"lng": 113.39, "lat": 22.52}]})
                )
                with mock.patch.object(main_module, "chrome_pool", chrome_pool_mock, create=True):
                    result = helper(
                        "session-1",
                        page,
                        waypoints,
                        provider_plan,
                        python_params={"api_retries": 0},
                    )

                page.goto.assert_not_called()
                chrome_pool_mock.execute_js.assert_called_once()
                args = chrome_pool_mock.execute_js.call_args.args
                self.assertEqual(args[0], "session-1")
                self.assertEqual(args[2], waypoints)
                self.assertEqual(list(args[3:]), expected_tail)
                self.assertEqual(result["path"], [{"lng": 113.39, "lat": 22.52}])

    def test_provider_route_helper_js_payloads_are_syntax_valid(self):
        expected_snippets = {
            "_plan_route_path_with_amap_runtime": [
                "https://webapi.amap.com/loader.js",
                "AMapLoader.load",
                "AMap.Walking",
                "地图路线服务请求超时",
                "window.setTimeout",
                "window.clearTimeout",
            ],
            "_plan_route_path_with_tencent_runtime": [
                "https://apis.map.qq.com/ws/direction/v1/",
                "output=jsonp",
                "${startCoord.lat},${startCoord.lng}",
            ],
            "_plan_route_path_with_tianditu_runtime": [
                "https://api.tianditu.gov.cn/drive?postStr=",
                "function gcj02ToTdtCoordinate(",
                "function tdtCoordinateToGcj02(",
                "AbortController",
                "地图路线服务请求超时",
                "window.setTimeout",
                "window.clearTimeout",
                "signal: controller.signal",
            ],
            "_plan_route_path_with_baidu_runtime": [
                "https://api.map.baidu.com/api?v=1.0&type=webgl&ak=",
                "function gcj02ToBd09(",
                "function bd09ToGcj02(",
                "BMapGL.Map",
                "BMapGL.WalkingRoute",
                "BMapGL.DrivingRoute",
                "百度地图脚本加载完成但运行时不可用",
                "地图路线服务请求超时",
                "window.setTimeout",
                "window.clearTimeout",
            ],
        }

        for helper_name, snippets in expected_snippets.items():
            with self.subTest(helper=helper_name):
                js_source = self._route_helper_execute_js_source(helper_name).strip()
                with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", suffix=".js", delete=False
                ) as tmp:
                    tmp.write(f"const routeHelper = {js_source};\n")
                    tmp_path = Path(tmp.name)
                try:
                    result = subprocess.run(
                        ["node", "--check", str(tmp_path)],
                        cwd=PROJECT_ROOT,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                finally:
                    tmp_path.unlink(missing_ok=True)

                if result.returncode != 0:
                    self.fail(
                        f"{helper_name} execute_js payload syntax check failed\n"
                        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                    )
                for snippet in snippets:
                    self.assertIn(snippet, js_source)

    def test_provider_route_helpers_queue_segment_requests_for_rate_limits(self):
        expected_snippets = [
            "api_queue_interval_s ??0.1",
            "const maxFailedWaves =2",
            "let consecutiveFailedWaves =0",
            "const pendingIndexes = Array.from",
            "await sleep(queueIntervalMs * order)",
            "Promise.all(waveIndexes.map",
            "waveSuccessCount ===0",
            "consecutiveFailedWaves >= maxFailedWaves",
            "pendingIndexes.length >0",
        ]

        for helper_name in [
            "_plan_route_path_with_amap_runtime",
            "_plan_route_path_with_tencent_runtime",
            "_plan_route_path_with_tianditu_runtime",
            "_plan_route_path_with_baidu_runtime",
        ]:
            with self.subTest(helper=helper_name):
                js_source = self._route_helper_execute_js_source(helper_name)
                for snippet in expected_snippets:
                    self.assertIn(snippet, js_source)

    def test_provider_runtime_completes_snapped_route_endpoints_for_baidu_and_tianditu(self):
        waypoints = [
            [113.3900, 22.5200],
            [113.3950, 22.5250],
            [113.4000, 22.5300],
        ]
        snapped_path = [
            {"lng": 113.3902, "lat": 22.5202},
            {"lng": 113.3948, "lat": 22.5248},
            {"lng": 113.3998, "lat": 22.5298},
        ]
        cases = [
            (
                "baidu",
                {"baidu": {"ak": "baidu-ak"}},
                "_plan_route_path_with_baidu_runtime",
            ),
            (
                "tianditu",
                {"tianditu": {"token": "tianditu-token"}},
                "_plan_route_path_with_tianditu_runtime",
            ),
        ]

        class ChromePoolStub:
            def get_context(self, session_id):
                return {"page": mock.Mock(on=mock.Mock())}

        for provider, providers, helper_name in cases:
            runtime_config = self._runtime_config_with_map(provider, providers)

            def helper(session_id, page, helper_waypoints, provider_plan, python_params):
                self.assertEqual(helper_waypoints, waypoints)
                return {"path": snapped_path.copy()}

            with self.subTest(provider=provider), \
                 mock.patch.object(main_module, "chrome_pool", ChromePoolStub(), create=True), \
                 mock.patch.object(main_module, helper_name, side_effect=helper):
                result = main_module._plan_route_path_with_provider_runtime(
                    "session-1",
                    waypoints,
                    runtime_config=runtime_config,
                )

            self.assertEqual(result["path"][0], {"lng": 113.39, "lat": 22.52})
            self.assertIn({"lng": 113.395, "lat": 22.525}, result["path"])
            self.assertEqual(result["path"][-1], {"lng": 113.4, "lat": 22.53})


if __name__ == "__main__":
    unittest.main()
