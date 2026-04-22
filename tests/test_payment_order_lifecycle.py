import os
import tempfile
import time
import unittest
from unittest import mock

from flask import Flask, jsonify, g as flask_g, request as flask_request

import main as main_module
from main import (
    _advance_order_status_by_timeout,
    _apply_payment_success_transition,
    _apply_refund_transition,
    _build_billing_qr_cache_key,
    _build_payment_verify_probe_url,
    _cleanup_expired_payment_verify_probes,
    _consume_payment_verify_probe,
    _create_payment_verify_probe,
    _get_reusable_billing_qr,
    _invalidate_billing_qr_cache_by_order,
    _is_order_terminal_for_repay,
    _is_payment_verify_probe_consumed,
    _load_qr_cache_index,
    _normalize_payment_return_url,
    _register_payment_verify_host_route_for_tests,
    _register_payment_verify_probe_route,
    _resolve_billing_payment_entry,
    _save_qr_cache_index,
)


class TestPaymentOrderLifecycle(unittest.TestCase):
    def test_pending_order_becomes_closed_after_timeout(self):
        order = {
            "status": "pending",
            "expires_at": "2026-04-12T10:00:00+00:00",
            "closed_at": None,
        }

        changed = _advance_order_status_by_timeout(
            order,
            now_iso="2026-04-12T10:00:01+00:00",
        )

        self.assertTrue(changed)
        self.assertEqual(order["status"], "closed")
        self.assertIsNotNone(order["closed_at"])

    def test_paid_and_refunded_are_terminal_for_repay(self):
        self.assertTrue(_is_order_terminal_for_repay({"status": "paid"}))
        self.assertTrue(_is_order_terminal_for_repay({"status": "refunded_partial"}))
        self.assertTrue(_is_order_terminal_for_repay({"status": "refunded_full"}))
        self.assertFalse(_is_order_terminal_for_repay({"status": "pending"}))

    def test_qr_cache_key_uses_school_billing_paytype(self):
        key = _build_billing_qr_cache_key("2024030101053", "5b603357-cc36", "wxpay")
        self.assertEqual(key, "2024030101053:5b603357-cc36:wxpay")

    def test_reuse_qr_within_timeout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index_file = os.path.join(tmpdir, "qr_cache_index.json")
            with mock.patch.object(main_module, "PAYMENT_ORDERS_DIR", tmpdir), mock.patch.object(main_module, "QR_CACHE_INDEX_FILE", index_file):
                _save_qr_cache_index({
                    "a:b:wxpay": {
                        "order_id": "order_1",
                        "qr_payload": "https://qrcode.example/1",
                        "created_at": "2026-04-12T10:00:00+00:00",
                        "expires_at": "2026-04-12T10:15:00+00:00",
                        "status_snapshot": "pending",
                    }
                })
                item = _get_reusable_billing_qr("a:b:wxpay", now_iso="2026-04-12T10:10:00+00:00")
                self.assertIsInstance(item, dict)
                self.assertEqual(item["order_id"], "order_1")

                expired = _get_reusable_billing_qr("a:b:wxpay", now_iso="2026-04-12T10:16:00+00:00")
                self.assertIsNone(expired)

    def test_qr_cache_invalidated_by_order_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index_file = os.path.join(tmpdir, "qr_cache_index.json")
            with mock.patch.object(main_module, "PAYMENT_ORDERS_DIR", tmpdir), mock.patch.object(main_module, "QR_CACHE_INDEX_FILE", index_file):
                _save_qr_cache_index({
                    "a:b:wxpay": {
                        "order_id": "order_a",
                        "qr_payload": "qra",
                        "created_at": "2026-04-12T10:00:00+00:00",
                        "expires_at": "2026-04-12T10:15:00+00:00",
                        "status_snapshot": "pending",
                    },
                    "x:y:alipay": {
                        "order_id": "order_b",
                        "qr_payload": "qrb",
                        "created_at": "2026-04-12T10:00:00+00:00",
                        "expires_at": "2026-04-12T10:15:00+00:00",
                        "status_snapshot": "pending",
                    },
                })
                _invalidate_billing_qr_cache_by_order("order_a")
                index_data = _load_qr_cache_index()
                self.assertNotIn("a:b:wxpay", index_data)
                self.assertIn("x:y:alipay", index_data)

    def test_resolve_existing_expired_pending_as_create_new(self):
        result = _resolve_billing_payment_entry(
            school_id="2024030101053",
            billing_id="5b603357-cc36-4279-a346-38d2da3e7581",
            pay_type="wxpay",
            existing_order={
                "status": "pending",
                "expires_at": "2026-04-12T10:00:00+00:00",
            },
            now_iso="2026-04-12T10:00:01+00:00",
        )
        self.assertEqual(result["decision"], "create_new")
        self.assertEqual(result["normalized_existing_status"], "closed")

    def test_resolve_terminal_existing_order_rejects(self):
        result = _resolve_billing_payment_entry(
            school_id="2024030101053",
            billing_id="b1",
            pay_type="wxpay",
            existing_order={"status": "paid"},
            now_iso="2026-04-12T10:00:01+00:00",
        )
        self.assertEqual(result["decision"], "reject_terminal")

    def test_closed_order_can_be_marked_paid_by_notify(self):
        order = {"status": "closed", "paid_time": None}
        _apply_payment_success_transition(order, paid_time="2026-04-12T11:00:00+00:00")
        self.assertEqual(order["status"], "paid")
        self.assertEqual(order["paid_time"], "2026-04-12T11:00:00+00:00")

    def test_paid_to_partial_then_full_refund(self):
        order = {"status": "paid", "amount": "10.00", "refund_total": 0}
        _apply_refund_transition(order, refund_amount=2.5)
        self.assertEqual(order["status"], "refunded_partial")
        _apply_refund_transition(order, refund_amount=7.5)
        self.assertEqual(order["status"], "refunded_full")


class TestPaymentVerifyProbeLifecycle(unittest.TestCase):
    def setUp(self):
        main_module.payment_verify_probes = {}

    def test_probe_roundtrip_consumes_once(self):
        token, challenge = _create_payment_verify_probe(ttl_seconds=15)

        self.assertFalse(_is_payment_verify_probe_consumed(token))
        self.assertTrue(_consume_payment_verify_probe(token, challenge))
        self.assertTrue(_is_payment_verify_probe_consumed(token))
        self.assertFalse(_consume_payment_verify_probe(token, challenge))

    def test_probe_rejects_wrong_challenge(self):
        token, challenge = _create_payment_verify_probe(ttl_seconds=15)

        self.assertFalse(_consume_payment_verify_probe(token, challenge + "-wrong"))
        self.assertFalse(_is_payment_verify_probe_consumed(token))

    def test_cleanup_drops_expired_probe(self):
        token, challenge = _create_payment_verify_probe(ttl_seconds=0)
        time.sleep(0.01)

        _cleanup_expired_payment_verify_probes()

        self.assertFalse(_consume_payment_verify_probe(token, challenge))
        self.assertNotIn(token, main_module.payment_verify_probes)


class TestPaymentVerifyProbeRoute(unittest.TestCase):
    def setUp(self):
        main_module.payment_verify_probes = {}

    def test_build_probe_url_uses_random_api_path(self):
        url = _build_payment_verify_probe_url("https://example.com/", "token-123")
        self.assertEqual(url, "https://example.com/api/payment/verify_probe/token-123")

    def test_probe_route_consumes_probe_and_sets_no_cache_headers(self):
        app = Flask(__name__)
        with mock.patch.object(main_module, "request", flask_request, create=True), \
             mock.patch.object(main_module, "jsonify", jsonify, create=True):
            _register_payment_verify_probe_route(app)
            token, challenge = main_module._create_payment_verify_probe(ttl_seconds=15)

            with app.test_client() as client:
                response = client.post(
                    f"/api/payment/verify_probe/{token}",
                    json={"challenge": challenge},
                )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(response.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(response.headers["Pragma"], "no-cache")
        self.assertEqual(response.headers["Expires"], "0")
        self.assertTrue(main_module._is_payment_verify_probe_consumed(token))


class TestCheckAppHostProbeValidation(unittest.TestCase):
    def test_check_app_host_posts_to_random_probe_url(self):
        verifier = main_module.IPVerifier()
        response_mock = mock.Mock()
        response_mock.status_code = 200
        response_mock.json.return_value = {"success": True}
        requests_mock = mock.Mock(post=mock.Mock(return_value=response_mock))

        with mock.patch.object(main_module, "urllib", __import__("urllib"), create=True), \
             mock.patch.object(main_module, "requests", requests_mock, create=True), \
             mock.patch.object(main_module, "_create_payment_verify_probe", return_value=("token-123", "challenge-abc")), \
             mock.patch.object(main_module, "_is_payment_verify_probe_consumed", return_value=True):
            ok = verifier.check_app_host("https://pay.example.com")

        self.assertTrue(ok)
        requests_mock.post.assert_called_once_with(
            "https://pay.example.com/api/payment/verify_probe/token-123",
            json={"challenge": "challenge-abc"},
            timeout=5,
        )

    def test_check_app_host_rejects_fake_success_when_probe_not_consumed(self):
        verifier = main_module.IPVerifier()
        response_mock = mock.Mock()
        response_mock.status_code = 200
        response_mock.json.return_value = {"success": True}

        with mock.patch.object(main_module, "urllib", __import__("urllib"), create=True), \
             mock.patch.object(main_module, "requests", mock.Mock(post=mock.Mock(return_value=response_mock)), create=True), \
             mock.patch.object(main_module, "_create_payment_verify_probe", return_value=("token-123", "challenge-abc")), \
             mock.patch.object(main_module, "_is_payment_verify_probe_consumed", return_value=False):
            ok = verifier.check_app_host("https://pay.example.com")

        self.assertFalse(ok)


class TestVerifyHostEndpoint(unittest.TestCase):
    def test_verify_host_endpoint_uses_ipverifier_check_app_host(self):
        app = Flask(__name__)
        verifier_calls = []

        with mock.patch.object(main_module, "request", flask_request, create=True), \
             mock.patch.object(main_module, "jsonify", jsonify, create=True):
            _register_payment_verify_host_route_for_tests(
                app,
                login_required=lambda func: func,
                verifier_factory=lambda: type(
                    "VerifierStub",
                    (),
                    {"check_app_host": lambda self, host: verifier_calls.append(host) or True},
                )(),
            )

            with app.test_client() as client:
                response = client.post("/api/payment/verify_host", json={"app_host": "https://pay.example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(verifier_calls, ["https://pay.example.com"])


class TestPaymentReturnUrlValidation(unittest.TestCase):
    def test_same_origin_return_url_is_preserved(self):
        result = _normalize_payment_return_url(
            "https://pay.example.com/orders/result?order=1",
            app_host="https://pay.example.com",
            notify_url="https://pay.example.com/api/payment/yipay_notify",
        )
        self.assertEqual(result, "https://pay.example.com/orders/result?order=1")

    def test_cross_origin_return_url_is_rejected(self):
        result = _normalize_payment_return_url(
            "https://evil.example.com/phish",
            app_host="https://pay.example.com",
            notify_url="https://pay.example.com/api/payment/yipay_notify",
        )
        self.assertIsNone(result)


class TestPaymentRouteRegistration(unittest.TestCase):
    def test_verify_host_route_is_registered_from_single_location(self):
        with open(main_module.__file__, "r", encoding="utf-8") as fp:
            source = fp.read()

        self.assertEqual(
            source.count("_register_payment_verify_host_route_for_tests(app, login_required)"),
            1,
        )


class TestBillingLocalQueryAdminGuard(unittest.TestCase):
    def test_billing_local_query_defines_is_admin_before_permission_check(self):
        with open(main_module.__file__, "r", encoding="utf-8") as fp:
            source = fp.read()

        route_anchor = '@app.route("/api/payment/query_billing_local", methods=["POST"])'
        start = source.index(route_anchor)
        end = source.index('@app.route("/api/payment/create_order_for_overdue", methods=["POST"])', start)
        route_source = source[start:end]

        self.assertIn('is_admin = auth_system.check_permission(g.user, "manage_users")', route_source)
        self.assertLess(
            route_source.index('is_admin = auth_system.check_permission(g.user, "manage_users")'),
            route_source.index('if order_data.get("username") != g.user and not is_admin:'),
        )


class TestLegacyPaymentChallengeRemoval(unittest.TestCase):
    def test_legacy_payment_challenge_globals_are_not_required(self):
        self.assertFalse(hasattr(main_module, "payment_verify_challenge_get"))

    def test_legacy_self_check_flag_is_not_required(self):
        self.assertFalse(hasattr(main_module, "PAYMENT_APP_HOST_SELF_CHECK_ENABLED"))


class TestMidnightRuntimeMaintenance(unittest.TestCase):
    def setUp(self):
        main_module.web_sessions = {}
        main_module.web_sessions_lock = main_module.threading.Lock()
        main_module.session_activity = {}
        main_module.session_activity_lock = main_module.threading.Lock()
        main_module.browsing_activity = {}
        main_module.browsing_activity_lock = main_module.threading.Lock()
        main_module.session_file_locks = {}
        main_module.session_file_locks_lock = main_module.threading.Lock()
        main_module.payment_verify_probes = {}
        main_module.payment_verify_probes_lock = main_module.threading.Lock()
        main_module.public_ip_cache = {"ipv4": None, "ipv6": None}
        main_module.public_ip_cache_time = 0
        main_module.js_cache_storage = {}
        main_module.js_cache_last_update = {}
        main_module.font_cache_storage = {}
        main_module.source_map_storage = {}
        main_module.sms_verification_codes = {}
        main_module.sms_extended_once_keys = set()
        main_module.cache = {}
        main_module.user_ban_cache = {}
        main_module.ip_ban_list_cache = []
        main_module.ip_ban_cache_timestamp = 123
        main_module.chrome_pool = None
        main_module.background_task_manager = None
        main_module.brute_force_manager = None

    def test_should_run_midnight_runtime_maintenance_only_at_midnight(self):
        midnight = main_module.datetime.datetime(2026, 4, 23, 0, 0, 0)
        before_midnight = main_module.datetime.datetime(2026, 4, 22, 23, 59, 59)
        morning = main_module.datetime.datetime(2026, 4, 23, 6, 0, 0)

        self.assertTrue(main_module._should_run_midnight_runtime_maintenance(midnight))
        self.assertFalse(main_module._should_run_midnight_runtime_maintenance(before_midnight))
        self.assertFalse(main_module._should_run_midnight_runtime_maintenance(morning))

    def test_midnight_runtime_maintenance_clears_runtime_state_and_reloads_caches(self):
        session_id = "session-1"
        api_instance = type(
            "ApiStub",
            (),
            {
                "stop_run_flag": mock.Mock(set=mock.Mock()),
                "multi_run_stop_flag": mock.Mock(set=mock.Mock()),
                "stop_auto_refresh": mock.Mock(set=mock.Mock()),
                "stop_multi_auto_refresh": mock.Mock(set=mock.Mock()),
                "is_multi_account_mode": False,
            },
        )()
        chrome_pool = mock.Mock()
        background_task_manager = mock.Mock()
        background_task_manager.lock = main_module.threading.Lock()
        background_task_manager.tasks = {"task-1": {"status": "running"}}
        brute_force_manager = mock.Mock()
        brute_force_manager.tasks = {"bf-1": {"status": "running"}}

        main_module.web_sessions = {session_id: api_instance}
        main_module.session_activity = {session_id: 123}
        main_module.browsing_activity = {session_id: 456}
        main_module.session_file_locks = {session_id: object()}
        main_module.payment_verify_probes = {"probe-1": {"consumed": False}}
        main_module.public_ip_cache = {"ipv4": "1.1.1.1", "ipv6": "::1"}
        main_module.public_ip_cache_time = 999
        main_module.js_cache_storage = {"main": "js"}
        main_module.js_cache_last_update = {"main": 1.23}
        main_module.font_cache_storage = {"font": "data"}
        main_module.source_map_storage = {"map": "data"}
        main_module.sms_verification_codes = {"13800138000": {"code": "123456"}}
        main_module.sms_extended_once_keys = {"13800138000:123456"}
        main_module.cache = {"answer": 42}
        main_module.user_ban_cache = {"demo": {"banned": True}}
        main_module.ip_ban_list_cache = ["127.0.0.1"]
        main_module.ip_ban_cache_timestamp = 321
        main_module.chrome_pool = chrome_pool
        main_module.background_task_manager = background_task_manager
        main_module.brute_force_manager = brute_force_manager

        with mock.patch.object(main_module, "_load_ip_cache") as load_ip_cache, \
             mock.patch.object(main_module, "_load_phone_cache") as load_phone_cache, \
             mock.patch.object(main_module, "gc") as gc_module:
            main_module._run_midnight_runtime_maintenance()

        chrome_pool.cleanup_context.assert_called_once_with(session_id)
        api_instance.stop_run_flag.set.assert_called_once_with()
        api_instance.multi_run_stop_flag.set.assert_called_once_with()
        api_instance.stop_auto_refresh.set.assert_called_once_with()
        api_instance.stop_multi_auto_refresh.set.assert_called_once_with()
        self.assertEqual(main_module.web_sessions, {})
        self.assertEqual(main_module.session_activity, {})
        self.assertEqual(main_module.browsing_activity, {})
        self.assertEqual(main_module.session_file_locks, {})
        self.assertEqual(main_module.payment_verify_probes, {})
        self.assertEqual(main_module.public_ip_cache, {"ipv4": None, "ipv6": None})
        self.assertEqual(main_module.public_ip_cache_time, 0)
        self.assertEqual(main_module.js_cache_storage, {})
        self.assertEqual(main_module.js_cache_last_update, {})
        self.assertEqual(main_module.font_cache_storage, {})
        self.assertEqual(main_module.source_map_storage, {})
        self.assertEqual(main_module.sms_verification_codes, {})
        self.assertEqual(main_module.sms_extended_once_keys, set())
        self.assertEqual(main_module.cache, {})
        self.assertEqual(main_module.user_ban_cache, {})
        self.assertIsNone(main_module.ip_ban_list_cache)
        self.assertEqual(main_module.ip_ban_cache_timestamp, 0)
        self.assertEqual(background_task_manager.tasks, {})
        self.assertEqual(brute_force_manager.tasks, {})
        load_ip_cache.assert_called_once_with()
        load_phone_cache.assert_called_once_with()
        gc_module.collect.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
