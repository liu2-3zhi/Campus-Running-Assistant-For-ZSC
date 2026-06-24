import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.new.js"
INDEX_PATH = PROJECT_ROOT / "index.html"
MAIN_PATH = PROJECT_ROOT / "main.py"


class TestMobileAdminPaymentLogsUi(unittest.TestCase):
    def test_mobile_payment_logs_search_button_reloads_first_page(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        index_source = INDEX_PATH.read_text(encoding="utf-8")

        self.assertIn('id="mobile-multi-admin-payment-logs-panel"', index_source)
        self.assertIn('id="search-payment-logs-btn"', index_source)
        self.assertIn('searchPaymentLogsBtn.addEventListener("click", function () {', source)
        self.assertIn('loadPaymentLogs(1);', source)

    def test_load_payment_logs_appends_action_type_query_parameter(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('document.getElementById("payment-logs-action-type")?.value || ""', source)
        self.assertIn('url += `&action_type=${encodeURIComponent(actionType)}`;', source)

    def test_admin_payment_logs_route_accepts_action_type_query_parameter(self):
        source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn(
            'request.args.get("action_type", request.args.get("action", "")).strip()',
            source,
        )
    def test_admin_billing_logs_panel_has_search_and_pagination_hooks(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        index_source = INDEX_PATH.read_text(encoding="utf-8")

        self.assertIn('id="admin-billing-logs-panel_modal"', index_source)
        self.assertIn('id="admin-billing-logs-search-btn_modal"', index_source)
        self.assertIn('async function loadAdminBillingLogs(page = 1)', source)
        self.assertIn('/api/admin/billing/logs', source)
        self.assertIn('admin-billing-logs-prev-btn_modal', source)
        self.assertIn('admin-billing-logs-next-btn_modal', source)
