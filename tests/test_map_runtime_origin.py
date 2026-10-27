import unittest

from map_runtime_origin import (
    merge_map_settings,
    normalize_backend_page_origin,
    resolve_backend_page_origin,
)


class Config:
    def __init__(self, value):
        self.value = value

    def get(self, section, key, fallback=None):
        return self.value.get(section, {}).get(key, fallback)


class MapRuntimeOriginTests(unittest.TestCase):
    def test_url_is_reduced_to_origin(self):
        cases = {
            " https://EXAMPLE.com:443/a?session_id=private#fragment ": "https://example.com",
            "http://example.com:80/path": "http://example.com",
            "https://example.com:8443/path": "https://example.com:8443",
            "http://[::1]:8080/a": "http://[::1]:8080",
            "": "",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(normalize_backend_page_origin(value), expected)

    def test_invalid_origin_is_rejected(self):
        for value in ("example.com", "file:///tmp/a", "https://user:secret@example.com/a",
                      "https://example.com:70000", "https://example.com\\evil", "https://exa mple.com",
                      "https://example.com\n/path", "https:///missing", "https://example.com:",
                      "https://example.com:0", "https://example.com/\x85path", "http://999.999.999.999", "http://[fe80::1%25eth0]"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_backend_page_origin(value)

    def test_provider_global_request_priority(self):
        config = Config({"Map": {"backend_page_origin": "https://global.test/path", "providers": {
            "amap": {"backend_page_origin": "https://amap.test/a"},
        }}})
        self.assertEqual(resolve_backend_page_origin(config, "amap", "https://app.test/a"),
                         ("https://amap.test", "provider"))
        self.assertEqual(resolve_backend_page_origin(config, "baidu", "https://app.test/a"),
                         ("https://global.test", "global"))
        self.assertEqual(resolve_backend_page_origin(Config({}), "amap", "https://app.test/a"),
                         ("https://app.test", "request"))
        with self.assertRaises(ValueError):
            resolve_backend_page_origin(Config({}), "amap", "")

    def test_partial_update_preserves_keys_security_and_other_origins(self):
        config = Config({"Map": {"provider": "amap", "backend_page_origin": "https://global.test",
            "frontend_proxy_enabled": True,
            "providers": {"amap": {"js_key": "key", "security_js_code": "code", "backend_page_origin": "https://a.test"},
                          "tencent": {"map_key": "tencent", "backend_page_origin": "https://t.test"}}}})
        merged = merge_map_settings(config, {"providers": {"amap": {"backend_page_origin": "https://new.test/path"}}})
        self.assertEqual(merged["providers"]["amap"], {"js_key": "key", "security_js_code": "code", "backend_page_origin": "https://new.test"})
        self.assertEqual(merged["providers"]["tencent"]["backend_page_origin"], "https://t.test")
        self.assertEqual(merged["backend_page_origin"], "https://global.test")
        self.assertTrue(merged["frontend_proxy_enabled"])
        cleared = merge_map_settings(config, {"backend_page_origin": "", "providers": {"amap": {"security_js_code": "", "backend_page_origin": ""}}})
        self.assertEqual(cleared["backend_page_origin"], "")
        self.assertEqual(cleared["providers"]["amap"]["security_js_code"], "")
        self.assertEqual(cleared["providers"]["amap"]["js_key"], "key")
        disabled = merge_map_settings(config, {"frontend_proxy_enabled": False})
        self.assertFalse(disabled["frontend_proxy_enabled"])

    def test_frontend_proxy_flag_defaults_to_false_and_accepts_explicit_strings(self):
        self.assertFalse(merge_map_settings(Config({}), {}).get("frontend_proxy_enabled"))
        self.assertTrue(merge_map_settings(Config({}), {"frontend_proxy_enabled": "true"})[
            "frontend_proxy_enabled"
        ])
        with self.assertRaises(ValueError):
            merge_map_settings(Config({}), {"frontend_proxy_enabled": "not-a-bool"})

    def test_legacy_keys_survive_old_request_and_invalid_update_does_not_mutate(self):
        config = Config({"Map": {"amap_js_key": "legacy", "providers": {"amap": {"security_js_code": "scode"}}}})
        merged = merge_map_settings(config, {"provider": "baidu"})
        self.assertEqual(merged["providers"]["amap"]["js_key"], "legacy")
        self.assertEqual(merged["providers"]["amap"]["security_js_code"], "scode")
        with self.assertRaises(ValueError):
            merge_map_settings(config, {"providers": {"amap": {"backend_page_origin": "bad"}}})
        self.assertNotIn("backend_page_origin", config.value["Map"]["providers"]["amap"])


if __name__ == "__main__":
    unittest.main()
