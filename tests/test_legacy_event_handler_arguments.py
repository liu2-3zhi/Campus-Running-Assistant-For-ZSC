import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.js"


class TestLegacyEventHandlerArguments(unittest.TestCase):
    def test_click_handlers_do_not_forward_dom_event_as_business_argument(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        expected_wrappers = (
            'refreshUsersBtnModal.addEventListener("click", () => loadAdminUsers())',
            'loginBtn.addEventListener("click", () => handleAuthLogin())',
            'registerBtn.addEventListener("click", () => handleAuthRegister())',
            '$("multi-remove-all-btn").addEventListener("click", () => multi_removeAll())',
            '$("multi-remove-selected-btn").addEventListener("click", () => multi_removeSelected())',
            'refreshCaptchaHistoryBtn.addEventListener("click", () => loadCaptchaHistory())',
        )
        for wrapper in expected_wrappers:
            self.assertIn(wrapper, source)

        invalid_direct_handlers = (
            'refreshUsersBtnModal.addEventListener("click", loadAdminUsers)',
            'loginBtn.addEventListener("click", handleAuthLogin)',
            'registerBtn.addEventListener("click", handleAuthRegister)',
            '$("multi-remove-all-btn").addEventListener("click", multi_removeAll)',
            '$("multi-remove-selected-btn").addEventListener("click", multi_removeSelected)',
            'refreshCaptchaHistoryBtn.addEventListener("click", loadCaptchaHistory)',
        )
        for direct_handler in invalid_direct_handlers:
            self.assertNotIn(direct_handler, source)


if __name__ == "__main__":
    unittest.main()
