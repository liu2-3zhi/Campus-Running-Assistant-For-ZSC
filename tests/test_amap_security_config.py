import json
from unittest.mock import patch

import main


def config_for(tmp_path, code="example-security-code"):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    config = main.JsonConfigAdapter(str(path))
    config.add_section("Map")
    config.set("Map", "provider", "amap")
    config.set("Map", "providers", {"amap": {"js_key": "example-js-key", "security_js_code": code}})
    return config


def test_amap_optional_security_code_is_read_and_excluded_from_public_metadata(tmp_path):
    config = config_for(tmp_path)
    provider = main._get_map_provider_runtime_config(config, "amap")
    assert provider["security_js_code"] == "example-security-code"
    public = main._strip_map_provider_secret_fields({"amap": provider})
    assert "example-security-code" not in json.dumps(public)
    assert "security_js_code" not in public["amap"]
    config.set("Map", "providers", {"amap": {"js_key": "example-js-key"}})
    assert main._get_map_provider_runtime_config(config, "amap")["security_js_code"] == ""


def test_amap_security_code_round_trips_only_in_encrypted_bundle():
    context = main._generate_map_key_runtime_context()
    provider = {"amap": {"js_key": "example-js-key", "security_js_code": "example-security-code"}}
    bundle = main._build_map_provider_key_bundle(provider, "amap", context)
    assert "example-security-code" not in json.dumps(bundle)
    assert main._decrypt_map_provider_key_bundle(bundle, context) == provider
    old_bundle = main._build_map_provider_key_bundle({"amap": {"js_key": "example-js-key"}}, "amap", context)
    assert main._decrypt_map_provider_key_bundle(old_bundle, context) == {"amap": {"js_key": "example-js-key"}}


def test_config_save_preserves_absent_security_code_and_allows_explicit_clear(tmp_path):
    config = config_for(tmp_path)
    for new_value in (None, "replacement-code", ""):
        amap = {"js_key": "example-js-key"}
        if new_value is not None:
            amap["security_js_code"] = new_value
        merged = main.merge_map_settings(config, {"provider": "amap", "providers": {"amap": amap}})
        config.set("Map", "providers", merged["providers"])
        expected = "example-security-code" if new_value is None else new_value
        assert config.get("Map", "providers")["amap"]["security_js_code"] == expected


def test_background_planning_passes_the_optional_security_code(tmp_path):
    config = config_for(tmp_path)
    plan = main._plan_route_with_map_provider([[1, 2], [3, 4]], runtime_config=config)
    class Pool:
        def execute_js(self, _session, _script, *args, **_kwargs):
            assert args[5] == "example-security-code"
            return {"path": []}
    with patch.object(main, "chrome_pool", Pool(), create=True):
        main._plan_route_path_with_amap_runtime("test-session", None, [[1, 2], [3, 4]], plan)


def test_security_code_is_redacted_from_log_text():
    assert "example-secret" not in main._redact_sensitive_log_text("security_js_code=example-secret")
    assert "example-secret" not in main._redact_sensitive_log_text("securityJsCode=example-secret")
