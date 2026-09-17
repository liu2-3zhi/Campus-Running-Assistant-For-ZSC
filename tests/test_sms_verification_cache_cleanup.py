import unittest

import main as main_module


class TestSmsVerificationCacheCleanup(unittest.TestCase):
    def test_cleanup_removes_expired_codes_and_extend_markers(self):
        main_module.sms_verification_codes = {
            "13800000000": ("111111", 100),
            "13900000000": ("222222", 1500),
        }
        main_module.sms_extended_once_keys = {
            "13800000000:111111",
            "13900000000:222222",
        }

        main_module._cleanup_expired_sms_verification_codes(now_ts=1000)

        self.assertEqual(
            main_module.sms_verification_codes,
            {"13900000000": ("222222", 1500)},
        )
        self.assertEqual(
            main_module.sms_extended_once_keys,
            {"13900000000:222222"},
        )

    def test_cleanup_enforces_max_entries_by_expiry(self):
        main_module.sms_verification_codes = {
            f"1380000000{index}": ("111111", 2000 + index)
            for index in range(5)
        }
        main_module.sms_extended_once_keys = set()

        main_module._cleanup_expired_sms_verification_codes(
            now_ts=1000,
            max_entries=2,
        )

        self.assertEqual(
            list(main_module.sms_verification_codes),
            ["13800000003", "13800000004"],
        )


if __name__ == "__main__":
    unittest.main()
