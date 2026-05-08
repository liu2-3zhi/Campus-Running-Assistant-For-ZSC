import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = PROJECT_ROOT / "main.py"


class TestSmsRouteRegistrationConsolidation(unittest.TestCase):
    def test_start_web_server_registers_sms_helper_and_keeps_single_route_definition(self):
        source = MAIN_PY.read_text(encoding="utf-8")

        self.assertIn("_register_sms_routes(app, login_required)", source)
        self.assertEqual(
            source.count('@app.route("/api/sms/send_code", methods=["POST"])'),
            1,
        )
        self.assertEqual(
            source.count('@app.route("/api/sms/test_send", methods=["POST"])'),
            1,
        )
        self.assertEqual(
            source.count('@app.route("/api/admin/sms/config", methods=["GET"])'),
            1,
        )
        self.assertEqual(
            source.count('@app.route("/api/admin/sms/config", methods=["POST"])'),
            1,
        )

        payment_registration_idx = source.index("_register_payment_routes(app, login_required)")
        sms_registration_idx = source.index("_register_sms_routes(app, login_required)")
        self.assertGreater(sms_registration_idx, payment_registration_idx)


if __name__ == "__main__":
    unittest.main()
