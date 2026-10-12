import unittest
from pathlib import Path
from tests.backend_source_utils import read_backend_source


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SOURCE_PATHS = [
    PROJECT_ROOT / "scripts" / "legacy-payment.js",
    PROJECT_ROOT / "scripts" / "legacy-mobile-core.js",
    PROJECT_ROOT / "scripts" / "legacy-reminders.js",
    PROJECT_ROOT / "scripts" / "legacy-admin-config.js",
    PROJECT_ROOT / "scripts" / "legacy-admin-sessions.js",
    PROJECT_ROOT / "scripts" / "legacy-admin-users.js",
    PROJECT_ROOT / "scripts" / "legacy-mobile-admin.js",
    PROJECT_ROOT / "scripts" / "legacy-payment-user.js",
    PROJECT_ROOT / "scripts" / "legacy-mobile-multi.js",
    PROJECT_ROOT / "scripts" / "legacy-watermark.js",
    PROJECT_ROOT / "scripts" / "legacy-app-runtime.js",
    PROJECT_ROOT / "scripts" / "legacy-map-runtime.js",
    PROJECT_ROOT / "scripts" / "legacy-map-render.js",
    PROJECT_ROOT / "scripts" / "legacy-multi-accounts.js",
    PROJECT_ROOT / "scripts" / "main.js",
]


class _CombinedFrontendSource:
    def read_text(self, encoding="utf-8"):
        return "\n\n".join(
            path.read_text(encoding=encoding)
            for path in SCRIPT_SOURCE_PATHS
        )


SCRIPT_PATH = _CombinedFrontendSource()
PAYMENT_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "legacy-payment.js"
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
        source = read_backend_source()

        self.assertIn(
            'request.args.get("action_type", request.args.get("action", "")).strip()',
            source,
        )

    def test_legacy_payment_logs_translate_backend_actions_and_statuses(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        expected_actions = {
            "create_order": "创建订单",
            "query_order": "查询订单",
            "create_order_failed": "创建失败",
            "payment_success_notify": "支付成功通知",
            "refund": "退款操作",
            "refund_failed": "退款失败",
            "fetch_orders_from_platform": "从平台拉取订单",
            "sync_order_from_platform": "从平台同步订单",
            "query_order_by_tradeno": "按订单号查询",
            "order_status_updated": "订单状态更新",
            "create_order_from_notify": "根据通知补建订单",
            "query_platform_order_failed": "平台订单查询失败",
            "payment_notify_no_public_key": "支付通知未配置公钥",
            "payment_notify_signature_failed": "支付通知验签失败",
            "payment_notify_order_not_found": "支付通知订单不存在",
            "payment_duplicate_notify": "重复支付通知",
            "create_overdue_order": "创建欠费订单",
            "overdue_payment_completed": "欠费支付完成",
            "overdue_payment_error": "欠费支付处理失败",
            "create_billing_order": "创建账单订单",
            "billing_payment_completed": "账单支付完成",
            "query_billing_order_active": "主动查询账单订单",
            "query_billing_order_local": "本地查询账单订单",
            "admin_update_payment_config": "更新支付配置",
            "admin_update_pricing_config": "更新价格配置",
            "admin_update_yipay_config": "更新易支付配置",
            "admin_clear_overdue": "调整欠费次数",
        }
        for action, label in expected_actions.items():
            self.assertIn(f'{action}: "{label}"', source)
        vue_source = (PROJECT_ROOT / "frontend" / "src" / "components" / "admin" / "AdminPaymentLogs.vue").read_text(
            encoding="utf-8"
        )
        for action, label in expected_actions.items():
            self.assertIn(f"{action}: {{ label: '{label}'", vue_source)
        for status, label in {
            "success": "成功",
            "processing": "处理中",
            "refunded_partial": "部分退款",
            "timeout": "支付超时",
        }.items():
            self.assertIn(f'{status}: "{label}"', source)

    def test_payment_log_filters_keep_raw_action_values(self):
        index_source = INDEX_PATH.read_text(encoding="utf-8")
        self.assertIn(
            '<option value="fetch_orders_from_platform">从平台拉取订单</option>',
            index_source,
        )
    def test_admin_billing_logs_panel_has_search_and_pagination_hooks(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8") + "\n" + PAYMENT_SCRIPT_PATH.read_text(
            encoding="utf-8"
        )
        index_source = INDEX_PATH.read_text(encoding="utf-8")

        self.assertIn('id="admin-billing-logs-panel_modal"', index_source)
        self.assertIn('id="admin-billing-logs-search-btn_modal"', index_source)
        self.assertIn('async function loadAdminBillingLogs(page = 1)', source)
        self.assertIn('/api/admin/billing/logs', source)
        self.assertIn('admin-billing-logs-prev-btn_modal', source)
        self.assertIn('admin-billing-logs-next-btn_modal', source)
