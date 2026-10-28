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

    def test_signature_aliases_are_redacted_in_nested_objects(self):
        for alias in ("sign", "sig", "sn", "SIGN", "Sig", "Sn"):
            with self.subTest(alias=alias):
                payload = {"nested": [{alias: {"raw": "private-signature"}}], "info": "INVALID_USER_SCODE"}
                text = sanitize_diagnostic(payload)
                self.assertNotIn("private-signature", text)
                self.assertEqual(json.loads(text)["nested"][0][alias], "<redacted>")
                self.assertIn("INVALID_USER_SCODE", text)

    def test_signature_aliases_are_redacted_in_text_urls_and_summaries(self):
        for alias in ("sign", "sig", "sn", "SIGN", "Sig", "Sn"):
            for message in (
                f"SDK rejected {alias}=private-signature; reason=INVALID_USER_SCODE",
                f'SDK response {{"{alias}": "private-signature", "reason": "INVALID_USER_SCODE"}}',
                f"SDK https://example.test/maps?{alias}=private-signature&from=1,2 INVALID_USER_SCODE",
            ):
                with self.subTest(alias=alias, message=message):
                    text = sanitize_diagnostic(message)
                    self.assertNotIn("private-signature", text)
                    self.assertIn("INVALID_USER_SCODE", text)
                    summary = build_route_failure_summary({"error": message})
                    self.assertNotIn("private-signature", summary["message"])

    def test_signature_aliases_do_not_redact_similar_ordinary_fields(self):
        payload = {"signal": "strong", "assigned": "worker", "design": "route", "sign_count": 3, "snapped": "road"}
        self.assertEqual(json.loads(sanitize_diagnostic(payload)), payload)
        message = "signal=strong assigned=worker design=route sign_count=3 snapped=road"
        self.assertEqual(sanitize_diagnostic(message), message)

    def test_url_redaction_is_idempotent_in_repeated_diagnostic_layers(self):
        messages = (
            "APP不存在，AK有误：http://lbsyun.baidu.com/apiconsole/key?<redacted>",
            "SDK https://alice:private-user@example.test/map?key=private-key&path=1,2#private-fragment",
            "SDK https://example.test/session/private-session?token=private-token",
            "SDK https://example.test/uuid=private-session?sign=private-signature",
        )
        for message in messages:
            with self.subTest(message=message):
                first = sanitize_diagnostic(message)
                self.assertEqual(first, sanitize_diagnostic(first))
                self.assertEqual(first, sanitize_diagnostic(sanitize_diagnostic(first)))
                self.assertNotIn("private-", first)
                self.assertNotIn("<redacted><redacted>", first)

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
