import ast
import json
import io
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import main as main_module
from tests.backend_source_utils import read_backend_source


class TestTwoFactorChallenge(unittest.TestCase):
    def setUp(self):
        challenge_store = getattr(main_module, "two_fa_challenges", None)
        if isinstance(challenge_store, dict):
            challenge_store.clear()

    def test_challenge_is_single_use_and_bound_to_username(self):
        self.assertTrue(
            hasattr(main_module, "_create_two_fa_challenge"),
            "2FA challenge creation helper is required",
        )
        self.assertTrue(
            hasattr(main_module, "_consume_two_fa_challenge"),
            "2FA challenge verification helper is required",
        )

        token = main_module._create_two_fa_challenge("alice", ttl_seconds=60)
        verifier = lambda username, code: username == "alice" and code == "123456"

        self.assertFalse(
            main_module._consume_two_fa_challenge(
                token, "bob", "123456", verifier
            )[0]
        )
        self.assertTrue(
            main_module._consume_two_fa_challenge(
                token, "alice", "123456", verifier
            )[0]
        )
        self.assertFalse(
            main_module._consume_two_fa_challenge(
                token, "alice", "123456", verifier
            )[0]
        )

    def test_challenge_expires(self):
        self.assertTrue(
            hasattr(main_module, "_create_two_fa_challenge"),
            "2FA challenge creation helper is required",
        )
        token = main_module._create_two_fa_challenge("alice", ttl_seconds=0)
        time.sleep(0.01)

        ok, reason = main_module._consume_two_fa_challenge(
            token,
            "alice",
            "123456",
            lambda _username, _code: True,
        )

        self.assertFalse(ok)
        self.assertIn("过期", reason)


class TestUsernamePathHardening(unittest.TestCase):
    def test_invalid_auth_username_is_rejected(self):
        self.assertTrue(
            hasattr(main_module, "_is_safe_auth_username"),
            "auth username validation helper is required",
        )
        self.assertTrue(main_module._is_safe_auth_username("alice_01"))
        self.assertTrue(main_module._is_safe_auth_username("alice@example.com"))
        self.assertFalse(main_module._is_safe_auth_username("../../configs/config"))
        self.assertFalse(main_module._is_safe_auth_username(r"..\\..\\configs\\config"))
        self.assertFalse(main_module._is_safe_auth_username("a" * 201))

    def test_invalid_auth_username_storage_key_never_contains_separators(self):
        self.assertTrue(
            hasattr(main_module, "_auth_username_storage_key"),
            "safe auth username storage key helper is required",
        )
        key = main_module._auth_username_storage_key("../../configs/config")
        self.assertNotIn("/", key)
        self.assertNotIn("\\", key)
        self.assertNotIn("..", key)


class TestExecuteJSRouteRemoval(unittest.TestCase):
    def test_public_execute_js_route_is_removed(self):
        source = read_backend_source()
        self.assertNotIn('@app.route("/execute_js"', source)


class TestSecurityRouteWiring(unittest.TestCase):
    def test_2fa_login_uses_server_challenge(self):
        source = read_backend_source()
        route_start = source.index('@app.route("/auth/2fa/verify_login"')
        route_end = source.index(
            '@app.route("/auth/admin/create_user"', route_start
        )
        route_source = source[route_start:route_end]

        self.assertIn("_consume_two_fa_challenge", route_source)
        self.assertNotIn(
            "if not auth_system.verify_2fa(auth_username, verification_code)",
            route_source,
        )

    def test_2fa_login_carries_and_returns_theme_background(self):
        source = read_backend_source()
        route_start = source.index('@app.route("/auth/2fa/verify_login"')
        route_end = source.index(
            '@app.route("/auth/admin/create_user"', route_start
        )
        route_source = source[route_start:route_end]

        self.assertIn('data.get("background_preview")', route_source)
        self.assertIn('_bind_login_bundle_for_user', route_source)
        self.assertIn('"theme_background"', route_source)

    def test_generic_api_route_checks_allowlist(self):
        source = read_backend_source()
        route_start = source.index('@app.route("/api/<path:method>"')
        route_source = source[route_start:route_start + 2000]

        self.assertIn("_is_api_method_allowed(method)", route_source)

    def test_payment_jump_is_sanitized_before_template_insertion(self):
        source = read_backend_source()
        route_start = source.index('@app.route("/api/payment/yipay_notify"')
        route_source = source[route_start:route_start + 5000]

        self.assertIn("_normalize_payment_jump_url", route_source)
        self.assertIn("_encode_inline_script_json(jump_url)", route_source)

    def test_payment_notify_does_not_treat_missing_jump_as_sync_return(self):
        source = read_backend_source()
        route_start = source.index('@app.route("/api/payment/yipay_notify"')
        route_end = source.index('@app.route("/api/frontend-config")', route_start)
        route_source = source[route_start:route_end]

        self.assertIn('raw_jump = str(params.get("jump", "") or "").strip()', route_source)
        self.assertIn("if raw_jump", route_source)
        self.assertIn('else ""', route_source)
        self.assertIn('{"Content-Type": "text/plain; charset=utf-8"}', route_source)

    def test_frontend_config_loader_does_not_create_active_session_from_referer(self):
        source = read_backend_source()
        route_start = source.index('@app.route("/api/frontend_config.js")')
        route_end = source.index(
            "# Vue 前端自动构建", route_start
        )
        route_source = source[route_start:route_end]

        self.assertNotIn("web_sessions[uuid] = api_instance", route_source)
        self.assertIn("不创建活动会话", route_source)


class TestGenericApiAllowlist(unittest.TestCase):
    def test_sensitive_unmapped_method_is_not_callable(self):
        self.assertTrue(
            hasattr(main_module, "_is_api_method_allowed"),
            "API method allowlist helper is required",
        )
        self.assertFalse(
            main_module._is_api_method_allowed(
                "update_school_account_overdue_count"
            )
        )
        self.assertTrue(main_module._is_api_method_allowed("get_initial_data"))


class TestPaymentJumpHardening(unittest.TestCase):
    def test_payment_jump_only_allows_same_origin_or_relative_paths(self):
        self.assertTrue(
            hasattr(main_module, "_normalize_payment_jump_url"),
            "payment jump URL sanitizer is required",
        )
        self.assertEqual(
            main_module._normalize_payment_jump_url(
                "/uuid=11111111-1111-4111-8111-111111111111",
                "https://example.com",
            ),
            "/uuid=11111111-1111-4111-8111-111111111111",
        )
        self.assertEqual(
            main_module._normalize_payment_jump_url(
                "https://example.com/result",
                "https://example.com",
            ),
            "/result",
        )
        self.assertEqual(
            main_module._normalize_payment_jump_url(
                'javascript:alert(1)"</script>',
                "https://example.com",
            ),
            "/",
        )
        self.assertEqual(
            main_module._normalize_payment_jump_url(
                "//evil.example.com/phish",
                "https://example.com",
            ),
            "/",
        )


class TestTrustedProxyIpHandling(unittest.TestCase):
    def setUp(self):
        import business_storage
        import trusted_ip
        from persistence.engine import DatabaseSettings
        from persistence.store import RelationalStore

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.store = RelationalStore(DatabaseSettings(root=root))
        self.store.init_schema(ready=True)
        self.addCleanup(self.store.database.dispose)
        self.store.put('settings', 'trusted_ips.txt', b'127.0.0.1\n')
        runtime = business_storage.StorageRuntime('sqlite', business_storage.StoragePolicy(root, {}), self.store)
        for patcher in (
            mock.patch.object(business_storage, '_runtime', runtime),
            mock.patch.object(main_module, 'TRUSTED_IPS_FILE', str(root / 'trusted_ips.txt')),
            mock.patch.object(trusted_ip, '_trusted_ip_networks_cache', None),
            mock.patch.object(trusted_ip, '_trusted_ip_networks_cache_mtime', None),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_untrusted_peer_cannot_override_client_ip(self):
        self.assertTrue(
            hasattr(main_module, "_select_forwarded_client_ip"),
            "trusted forwarded IP selector is required",
        )
        resolved = main_module._select_forwarded_client_ip(
            "8.8.8.8",
            "1.1.1.1",
        )
        self.assertEqual(resolved, "1.1.1.1")

    def test_trusted_private_proxy_strips_spoofed_leftmost_value(self):
        resolved = main_module._select_forwarded_client_ip(
            "8.8.8.8, 1.1.1.1",
            "127.0.0.1",
        )
        self.assertEqual(resolved, "1.1.1.1")

    def test_configured_public_trusted_proxy_is_skipped(self):
        trusted = [main_module.ipaddress.ip_network("1.1.1.1/32")]
        resolved = main_module._select_forwarded_client_ip(
            "8.8.8.8, 1.1.1.1",
            "127.0.0.1",
            trusted_networks=trusted,
        )
        self.assertEqual(resolved, "8.8.8.8")

    def test_empty_external_rules_still_recognize_ipv4_and_ipv6_local_proxies(self):
        for peer in ("10.8.0.1", "172.16.5.7", "192.168.0.1", "127.0.0.9", "169.254.0.1",
                     "::1", "fd00::1", "fe80::1", "::ffff:192.168.0.1",
                     "::ffff:127.0.0.9", "::ffff:169.254.0.1"):
            with self.subTest(peer=peer):
                self.assertEqual(main_module._select_forwarded_client_ip(
                    "198.51.100.9", peer, trusted_networks=()
                ), "198.51.100.9")

    def test_mapped_ipv4_peer_obeys_configured_ipv4_rules(self):
        trusted = [main_module.ipaddress.ip_network("203.0.113.8/32")]
        self.assertEqual(main_module._select_forwarded_client_ip(
            "198.51.100.9", "::ffff:203.0.113.8", trusted_networks=trusted
        ), "198.51.100.9")

    def test_both_forwarding_headers_require_a_trusted_peer(self):
        self.assertEqual(main_module._select_forwarded_client_ip(
            "198.51.100.9", "::ffff:203.0.113.8", trusted_networks=(),
            real_ip="198.51.100.10",
        ), "::ffff:cb00:7108")

    def test_real_ip_fallback_applies_only_without_a_valid_forwarded_chain(self):
        for forwarded, expected in (
            ("198.51.100.9, 10.0.0.4", "198.51.100.9"),
            ("", "198.51.100.10"),
            ("invalid", "198.51.100.10"),
        ):
            with self.subTest(forwarded=forwarded):
                self.assertEqual(main_module._select_forwarded_client_ip(
                    forwarded, "::1", trusted_networks=(), real_ip="198.51.100.10",
                ), expected)
        self.assertEqual(main_module._select_forwarded_client_ip(
            "", "::1", trusted_networks=(), real_ip="invalid",
        ), "::1")

    def test_ban_check_and_request_hooks_share_resolved_client_ip(self):
        import logging

        import trusted_ip
        from flask import Flask, request

        app = Flask(__name__)
        source = Path(main_module.__file__).with_name("web_server.py")
        hook_names = {"check_ip_ban_before_request", "handle_forwarded_proto"}
        hooks = [
            node for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
            if isinstance(node, ast.FunctionDef) and node.name in hook_names
        ]
        ban = mock.Mock(return_value=False)
        exec(compile(ast.Module(body=hooks, type_ignores=[]), str(source), "exec"), {
            "app": app,
            "_main": lambda: main_module,
            "check_ip_ban": ban,
            "logging": logging,
        })

        @app.get("/")
        def client_ip():
            return {"environ": request.environ["REMOTE_ADDR"], "remote_addr": request.remote_addr}

        with mock.patch.object(trusted_ip, "_select_forwarded_client_ip",
                               wraps=trusted_ip._select_forwarded_client_ip) as resolve:
            response = app.test_client().get("/", headers={"X-Real-IP": "198.51.100.9"},
                                             environ_overrides={"REMOTE_ADDR": "::ffff:192.168.0.1"})
        assert response.get_json() == {"environ": "198.51.100.9", "remote_addr": "198.51.100.9"}
        ban.assert_called_once_with("198.51.100.9", scope="all")
        resolve.assert_called_once()

    def test_trusted_ips_configuration_exists_only_in_database(self):
        self.assertTrue(main_module.os.path.isfile(main_module.TRUSTED_IPS_FILE))
        self.assertIsNotNone(self.store.get('settings', 'trusted_ips.txt'))
        self.assertFalse(Path(main_module.TRUSTED_IPS_FILE).exists())


class TestTrustedIpFileFormats(unittest.TestCase):
    def _load_matcher(self, content):
        with tempfile.TemporaryDirectory() as tmpdir:
            trusted_file = Path(tmpdir) / "trusted_ips.txt"
            trusted_file.write_text(content, encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                matcher = main_module._load_trusted_ip_networks(
                    str(trusted_file)
                )
            return matcher, output.getvalue()

    def test_single_ip_cidr_range_and_wildcard_formats(self):
        matcher, _output = self._load_matcher(
            "\n".join(
                [
                    "8.8.8.8",
                    "1.1.1.0/24",
                    "9.9.9.1-9.9.9.3",
                    "11.22.33.*",
                    "44.*",
                ]
            )
        )

        self.assertTrue(
            matcher.matches(main_module.ipaddress.ip_address("8.8.8.8"))
        )
        self.assertTrue(
            matcher.matches(main_module.ipaddress.ip_address("1.1.1.200"))
        )
        self.assertTrue(
            matcher.matches(main_module.ipaddress.ip_address("9.9.9.2"))
        )
        self.assertTrue(
            matcher.matches(main_module.ipaddress.ip_address("11.22.33.99"))
        )
        self.assertTrue(
            matcher.matches(main_module.ipaddress.ip_address("44.5.6.7"))
        )
        self.assertFalse(
            matcher.matches(main_module.ipaddress.ip_address("8.8.4.4"))
        )
        self.assertFalse(
            matcher.matches(main_module.ipaddress.ip_address("9.9.9.4"))
        )

    def test_full_wildcard_prints_red_console_warning(self):
        matcher, output = self._load_matcher("*")

        self.assertTrue(matcher.match_all)
        self.assertIn("\x1b[31m", output)
        self.assertIn("通配符", output)
        self.assertIn("*", output)
        self.assertEqual(
            main_module._select_forwarded_client_ip(
                "8.8.8.8",
                "1.1.1.1",
                trusted_networks=matcher,
            ),
            "8.8.8.8",
        )

    def test_missing_trusted_ip_file_falls_back_to_trust_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = io.StringIO()
            with redirect_stdout(output):
                matcher = main_module._load_trusted_ip_networks(
                    str(Path(tmpdir) / "missing-trusted-ips.txt")
                )
        self.assertTrue(matcher.match_all)
        self.assertIn("\x1b[31m", output.getvalue())
        self.assertEqual(
            main_module._select_forwarded_client_ip(
                "",
                "203.0.113.8",
                trusted_networks=matcher,
                real_ip="198.51.100.9",
            ),
            "198.51.100.9",
        )

    def test_blank_trusted_ip_file_falls_back_to_trust_all(self):
        for content in ("", " \n\t\r\n  "):
            with self.subTest(content=repr(content)):
                matcher, output = self._load_matcher(content)
                self.assertTrue(matcher.match_all)
                self.assertIn("\x1b[31m", output)

    def test_comment_only_trusted_ip_file_uses_builtin_proxies(self):
        matcher, output = self._load_matcher("# no extra proxies")
        self.assertFalse(matcher.match_all)
        self.assertEqual(matcher.entries, ())
        self.assertNotIn("\x1b[31m", output)


class TestSessionLimitEnforcement(unittest.TestCase):
    def test_single_session_limit_replaces_old_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            user_file = Path(tmpdir) / "user.json"
            user_file.write_text(
                json.dumps({"max_sessions": 1, "session_ids": ["old-1"]}),
                encoding="utf-8",
            )
            auth = object.__new__(main_module.AuthSystem)
            auth.lock = threading.RLock()
            auth.get_user_file_path = lambda _username: str(user_file)

            removed, _message = auth.check_single_session_enforcement(
                "alice", "new-1"
            )
            saved = json.loads(user_file.read_text(encoding="utf-8"))

        self.assertEqual(removed, ["old-1"])
        self.assertEqual(saved["session_ids"], ["new-1"])


class TestSessionTokenValidation(unittest.TestCase):
    def test_non_guest_session_without_cookie_token_is_rejected(self):
        self.assertTrue(
            hasattr(main_module, "_verify_session_cookie_token"),
            "session cookie token verifier is required",
        )
        self.assertFalse(
            main_module._verify_session_cookie_token(
                "11111111-1111-4111-8111-111111111111",
                "alice",
                "",
            )
        )

    def test_valid_guest_session_does_not_require_token(self):
        self.assertTrue(
            main_module._verify_session_cookie_token(
                "11111111-1111-4111-8111-111111111111",
                "guest",
                "",
            )
        )

    def test_non_guest_session_with_valid_token_is_accepted(self):
        with mock.patch.object(
            main_module, "token_manager", create=True
        ) as token_manager:
            token_manager.verify_token.return_value = (True, "ok")
            valid = main_module._verify_session_cookie_token(
                "11111111-1111-4111-8111-111111111111",
                "alice",
                "token",
            )

        self.assertTrue(valid)


if __name__ == "__main__":
    unittest.main()
