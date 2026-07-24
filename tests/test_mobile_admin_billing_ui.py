import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.new.js"


def _extract_js_section(source, start_marker, end_marker):
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


class TestMobileAdminBillingUi(unittest.TestCase):
    def test_mobile_multi_admin_billing_renders_summary_metrics(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        billing_source = _extract_js_section(
            source,
            "async function loadMobileMultiAdminBillingList() {",
            "\n\nasync function loadMobileMultiRemovedAccountsList() {",
        )

        self.assertIn("billingStats.total", billing_source)
        self.assertIn("billingStats.pending", billing_source)
        self.assertIn("billingStats.paid", billing_source)
        self.assertIn("billingStats.admin_cleared", billing_source)
        self.assertIn("billingStats.total_amount", billing_source)
        self.assertIn("总账单", billing_source)
        self.assertIn("待支付", billing_source)
        self.assertIn("已支付", billing_source)
        self.assertIn("已清除", billing_source)
        self.assertIn("总金额", billing_source)

    def test_mobile_multi_admin_billing_uses_backend_summary_fields(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        billing_source = _extract_js_section(
            source,
            "async function loadMobileMultiAdminBillingList() {",
            "\n\nasync function loadMobileMultiRemovedAccountsList() {",
        )

        self.assertIn('mobile-multi-admin-billing-search-input', source)
        self.assertIn('keyword=', billing_source)
        self.assertIn('summary.admin_cleared_amount', billing_source)
        self.assertIn('summary.pending_amount', billing_source)
        self.assertIn('summary.paid_amount', billing_source)

    def test_pc_and_mobile_billing_search_support_enter_key(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('const adminBillingSearchInput = $("admin-billing-search-input");', source)
        self.assertIn('adminBillingSearchInput.addEventListener("keypress"', source)
        self.assertIn('const mobileAdminBillingSearchInput = $("mobile-multi-admin-billing-search-input");', source)
        self.assertIn('mobileAdminBillingSearchInput.addEventListener("keypress"', source)
        self.assertIn('loadMobileMultiAdminBillingList();', source)
