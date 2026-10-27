import json
import unittest

from route_diagnostics import (
    build_route_failure_summary,
    generic_route_failure_message,
    new_diagnostic_id,
    sanitize_diagnostic,
)


class TestRouteDiagnosticSanitizer(unittest.TestCase):
    def test_redacts_nested_credentials_and_urls_without_hiding_reason(self):
        payload = {
            "info": "INVALID_USER_KEY",
            "nested": {"apiKey": "private-one", "securityJsCode": "private-two", "security_js_code": "private-eight"},
            "url": "https://alice:private-three@example.test/maps?key=private-four&from=1,2",
            "message": "Cookie: SID=private-five; Authorization: Bearer private-six",
            "session_id": "private-seven",
            "path": [{"lng": 113.1, "lat": 22.1}] * 100,
        }
        text = sanitize_diagnostic(payload)
        for secret in ("private-one", "private-two", "private-three", "private-four",
                       "private-five", "private-six", "private-seven", "private-eight"):
            self.assertNotIn(secret, text)
        self.assertNotIn("113.1", text)
        self.assertIn("INVALID_USER_KEY", text)
        self.assertIn("example.test/maps", text)
        self.assertIsInstance(json.loads(text), dict)

    def test_known_secrets_are_removed_even_from_plain_messages(self):
        text = sanitize_diagnostic(
            "SDK rejected bare-secret and bare%2Fsecret at https://example.test/bare-secret",
            sensitive_values=["bare-secret", "bare/secret"],
        )
        self.assertNotIn("bare-secret", text)
        self.assertNotIn("bare%2Fsecret", text)

    def test_bounds_utf8_after_redacting_and_handles_cycles(self):
        payload = {"message": "错误" * 20000}
        payload["cycle"] = payload
        text = sanitize_diagnostic(payload, max_bytes=512)
        self.assertLessEqual(len(text.encode("utf-8")), 512)
        self.assertNotIn("\ufffd", text)

    def test_handles_broken_objects_without_raising(self):
        class Broken:
            def __str__(self):
                raise ValueError("no string")

        self.assertIsInstance(sanitize_diagnostic(Broken()), str)

    def test_failure_summary_is_small_and_keeps_specific_reason(self):
        diagnostic_id = new_diagnostic_id()
        result = {
            "diagnostic_id": diagnostic_id,
            "provider": "amap",
            "error": "INVALID_USER_KEY api_key=do-not-keep " + "详情" * 5000,
            "diagnostic": {"segment": 1, "error_code": "10001"},
            "provider_plan": {"provider_config": {"js_key": "secret"}},
        }
        summary = build_route_failure_summary(result)
        self.assertEqual(diagnostic_id, summary["diagnostic_id"])
        self.assertEqual("amap", summary["provider"])
        self.assertIn("INVALID_USER_KEY", summary["message"])
        self.assertNotIn("do-not-keep", json.dumps(summary))
        self.assertNotIn("provider_plan", summary)
        self.assertEqual(1, summary["segment"])
        self.assertLessEqual(len(json.dumps(summary, ensure_ascii=False).encode("utf-8")), 2048)
        self.assertLessEqual(len(json.dumps(summary).encode("utf-8")), 2048)
        self.assertIn(diagnostic_id, generic_route_failure_message(diagnostic_id))


if __name__ == "__main__":
    unittest.main()
