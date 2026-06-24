import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = PROJECT_ROOT / "index.html"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.new.js"


class TestMobileAdminUsersUi(unittest.TestCase):
    def test_admin_users_panels_have_keyword_search_inputs(self):
        html = INDEX_PATH.read_text(encoding="utf-8")
        js = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('id="admin-users-search-input_modal"', html)
        self.assertIn('id="admin-users-search-btn_modal"', html)
        self.assertIn('id="mobile-multi-admin-users-search-input"', html)
        self.assertIn('id="mobile-multi-admin-users-search-btn"', html)
        self.assertIn('/auth/admin/list_users?keyword=', js)

    def test_mobile_multi_admin_users_sync_phone_location_badge(self):
        js = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('mobileContainer.querySelectorAll(".phone-location-badge[data-phone]")', js)
        self.assertIn('const info = await fetchPhoneInfo(span.dataset.phone);', js)

    def test_outstanding_details_render_linked_users_section(self):
        js = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('/api/admin/school-account-linked-users', js)
        self.assertIn('关联账号', js)
        self.assertIn('student_number', js)


if __name__ == "__main__":
    unittest.main()
