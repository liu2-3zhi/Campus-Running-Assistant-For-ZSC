import os
import tempfile
import unittest
from unittest import mock

import main as main_module
from main import (
    _advance_order_status_by_timeout,
    _apply_payment_success_transition,
    _apply_refund_transition,
    _build_billing_qr_cache_key,
    _get_reusable_billing_qr,
    _invalidate_billing_qr_cache_by_order,
    _is_order_terminal_for_repay,
    _load_qr_cache_index,
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


if __name__ == "__main__":
    unittest.main()
