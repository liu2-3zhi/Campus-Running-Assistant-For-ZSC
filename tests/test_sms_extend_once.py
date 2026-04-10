import unittest

from main import (
    _build_sms_extend_once_key,
    _is_sms_extend_allowed_once,
    _mark_sms_extend_used_once,
    _reset_sms_extend_once_for_phone,
    sms_extended_once_keys,
)


class TestSmsExtendOnce(unittest.TestCase):
    def setUp(self):
        sms_extended_once_keys.clear()

    def test_extend_once_allows_first_and_blocks_second(self):
        phone = "13800138000"
        code = "123456"

        self.assertTrue(_is_sms_extend_allowed_once(phone, code))
        _mark_sms_extend_used_once(phone, code)
        self.assertFalse(_is_sms_extend_allowed_once(phone, code))

    def test_different_code_on_same_phone_is_independent(self):
        phone = "13800138000"
        _mark_sms_extend_used_once(phone, "111111")
        self.assertTrue(_is_sms_extend_allowed_once(phone, "222222"))

    def test_reset_by_phone_clears_previous_marks(self):
        phone = "13800138000"
        _mark_sms_extend_used_once(phone, "111111")
        _reset_sms_extend_once_for_phone(phone)
        self.assertTrue(_is_sms_extend_allowed_once(phone, "111111"))

    def test_key_is_stable(self):
        self.assertEqual(
            _build_sms_extend_once_key("13800138000", "123456"),
            "13800138000:123456",
        )


if __name__ == "__main__":
    unittest.main()
