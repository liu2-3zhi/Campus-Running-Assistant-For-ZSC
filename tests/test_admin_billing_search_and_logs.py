import unittest

import main as main_module


class TestAdminBillingSearchAndSummary(unittest.TestCase):
    def test_admin_billing_list_filters_by_keyword_and_returns_full_summary(self):
        with open(main_module.__file__, "r", encoding="utf-8") as fp:
            source = fp.read()

        route_anchor = '@app.route("/api/admin/billing/list", methods=["GET"])'
        start = source.index(route_anchor)
        end = source.index('@app.route("/api/admin/billing/update", methods=["POST"])', start)
        route_source = source[start:end]

        self.assertIn('keyword = request.args.get("keyword", "").strip()', route_source)
        self.assertIn('summary = {', route_source)
        self.assertIn('"paid_amount"', route_source)
        self.assertIn('"pending_amount"', route_source)
        self.assertIn('"admin_cleared_amount"', route_source)
        self.assertIn('return jsonify({"success": True, "records": page_records, "total": total, "summary": summary', route_source)


class TestBillingLogs(unittest.TestCase):
    def test_admin_billing_logs_route_exists_and_accepts_keyword(self):
        with open(main_module.__file__, "r", encoding="utf-8") as fp:
            source = fp.read()

        self.assertIn('@app.route("/api/admin/billing/logs", methods=["GET"])', source)
        self.assertIn('keyword = request.args.get("keyword", "").strip()', source)
        self.assertIn('event_type = request.args.get("event_type", "").strip()', source)

    def test_billing_add_update_delete_write_billing_logs(self):
        with open(main_module.__file__, "r", encoding="utf-8") as fp:
            source = fp.read()

        self.assertIn('_write_billing_log(', source)
        self.assertIn('"billing_created"', source)
        self.assertIn('"billing_amount_changed"', source)
        self.assertIn('"billing_status_changed"', source)
        self.assertIn('"billing_admin_cleared"', source)
        self.assertIn('"billing_deleted"', source)


class TestAdminUsersSearchAndLinks(unittest.TestCase):
    def test_admin_list_users_route_accepts_keyword(self):
        with open(main_module.__file__, "r", encoding="utf-8") as fp:
            source = fp.read()

        anchor = '@app.route("/auth/admin/list_users", methods=["GET"])'
        start = source.index(anchor)
        end = source.index('@app.route("/auth/admin/update_user_group", methods=["POST"])', start)
        route_source = source[start:end]

        self.assertIn('keyword = request.args.get("keyword", "").strip().lower()', route_source)
        self.assertIn('_user_matches_keyword', route_source)
        self.assertIn('school_accounts', route_source)

    def test_outstanding_link_route_exists_and_filters_by_student_number(self):
        with open(main_module.__file__, "r", encoding="utf-8") as fp:
            source = fp.read()

        self.assertIn('@app.route("/api/admin/school-account-linked-users", methods=["GET"])', source)
        self.assertIn('student_number = request.args.get("student_number", "").strip()', source)
        self.assertIn('if linked_student_number != student_number:', source)
        self.assertNotIn('return jsonify({"success": True, "users": auth_system.list_users()', source)


if __name__ == "__main__":
    unittest.main()
