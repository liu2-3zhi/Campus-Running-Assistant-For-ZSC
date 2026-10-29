import ast
import configparser
import copy
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, jsonify, request

from config_adapter import JsonConfigAdapter
from map_runtime_origin import (
    get_map_config_selection,
    get_map_config_settings,
    merge_map_settings,
    resolve_backend_page_origin,
)


def adapter(data):
    config = JsonConfigAdapter.__new__(JsonConfigAdapter)
    config._data = copy.deepcopy(data)
    return config


def profiles_config():
    return adapter({"Map": {
        "provider": "amap",
        "frontend_config_id": "amap-front",
        "backend_config_id": "amap-back",
        "backend_page_origin": "https://global.test",
        "configs": [
            {"id": "amap-front", "name": "Frontend", "provider": "amap",
             "js_key": "front-key", "security_js_code": "front-code",
             "backend_page_origin": "https://front.test"},
            {"id": "amap-back", "name": "Backend", "provider": "amap",
             "js_key": "back-key", "security_js_code": "back-code",
             "backend_page_origin": "https://back.test"},
        ],
    }})


def test_legacy_migration_preserves_keys_origins_and_active_provider():
    config = adapter({"Map": {
        "provider": "tencent", "baidu_map_ak": "legacy-baidu",
        "providers": {"tencent": {"map_key": "legacy-tencent", "backend_page_origin": "https://old.test"}},
    }})
    settings = get_map_config_settings(config)
    assert [row["id"] for row in settings["configs"]] == [
        "legacy-amap", "legacy-tencent", "legacy-tianditu", "legacy-baidu",
    ]
    assert settings["frontend_config_id"] == settings["backend_config_id"] == "legacy-tencent"
    assert get_map_config_selection(config)["map_key"] == "legacy-tencent"
    assert get_map_config_selection(config, provider="baidu")["ak"] == "legacy-baidu"
    assert resolve_backend_page_origin(config, "tencent") == ("https://old.test", "provider")
    assert "configs" not in config._data["Map"]


def test_independent_profiles_resolve_credentials_and_origins():
    config = profiles_config()
    assert get_map_config_selection(config, "frontend")["js_key"] == "front-key"
    assert get_map_config_selection(config)["js_key"] == "back-key"
    assert resolve_backend_page_origin(config, "amap", scope="frontend") == ("https://front.test", "provider")
    assert resolve_backend_page_origin(config, "amap") == ("https://back.test", "provider")
    selected = get_map_config_selection(config)
    selected["js_key"] = "changed"
    assert get_map_config_selection(config)["js_key"] == "back-key"


def test_order_and_names_do_not_change_profile_bindings():
    config = profiles_config()
    rows = list(reversed(config.get("Map", "configs")))
    rows[0]["name"] = "Renamed"
    merged = merge_map_settings(config, {"configs": rows})
    assert [row["id"] for row in merged["configs"]] == ["amap-back", "amap-front"]
    assert merged["frontend_config_id"] == "amap-front"
    assert merged["backend_config_id"] == "amap-back"
    assert merged["providers"]["amap"]["js_key"] == "front-key"


def test_legacy_admin_projection_roundtrip_cannot_copy_backend_credentials_to_frontend():
    import main

    config = profiles_config()
    projection = main._get_map_provider_admin_config(config, "amap")
    assert projection["js_key"] == "front-key"
    assert projection["security_js_code"] == "front-code"
    assert projection["backend_page_origin"] == "https://front.test"
    merged = merge_map_settings(config, {"providers": {"amap": projection}})
    assert merged["configs"] == get_map_config_settings(config)["configs"]


def test_legacy_provider_updates_only_modify_frontend_profile():
    config = profiles_config()
    merged = merge_map_settings(config, {"providers": {"amap": {"js_key": "replacement", "security_js_code": ""}}})
    front, back = merged["configs"]
    assert front["js_key"] == "replacement"
    assert front["security_js_code"] == ""
    assert back["js_key"] == "back-key"
    assert back["security_js_code"] == "back-code"
    assert merged["backend_config_id"] == "amap-back"


def test_legacy_updates_cannot_overwrite_another_providers_backend_only_profile():
    config = profiles_config()
    config.get("Map", "configs")[0].update({"provider": "tencent", "map_key": "front-tencent"})
    with pytest.raises(ValueError, match="后端专用"):
        merge_map_settings(config, {"providers": {"amap": {"js_key": "overwrite-backend"}}})
    merged = merge_map_settings(config, {"providers": {
        "amap": {"js_key": "back-key"}, "baidu": {"ak": "", "backend_page_origin": ""},
    }})
    assert merged["configs"][1]["js_key"] == "back-key"


def test_authoritative_list_preserves_omitted_fields_and_honors_explicit_clear():
    config = profiles_config()
    rows = copy.deepcopy(config.get("Map", "configs"))
    rows[0].pop("js_key")
    rows[1]["js_key"] = ""
    merged = merge_map_settings(config, {"configs": rows, "providers": {"amap": {"js_key": "ignored-old-projection"}}})
    assert merged["configs"][0]["js_key"] == "front-key"
    assert merged["configs"][1]["js_key"] == ""


def test_profile_deletion_and_rebinding_is_atomic_and_strips_other_provider_fields():
    config = profiles_config()
    merged = merge_map_settings(config, {
        "configs": [{"id": "tencent-only", "name": "Tencent", "provider": "tencent",
                     "map_key": "new-key", "js_key": "discard", "security_js_code": "discard"}],
        "frontend_config_id": "tencent-only", "backend_config_id": "tencent-only",
    })
    assert merged["provider"] == "tencent"
    assert "js_key" not in merged["configs"][0]
    assert "security_js_code" not in merged["configs"][0]
    assert set(merged["providers"]) == {"tencent"}


@pytest.mark.parametrize("change", [
    {"configs": []},
    {"configs": {}},
    {"frontend_config_id": "missing"},
    {"backend_config_id": []},
    {"configs": [{"id": "bad id", "name": "Map", "provider": "amap"}]},
    {"configs": [{"id": "x" * 129, "name": "Map", "provider": "amap"}]},
    {"configs": [{"id": "one", "name": " ", "provider": "amap"}]},
    {"configs": [{"id": "one", "name": "x" * 101, "provider": "amap"}]},
    {"configs": [{"id": "one", "name": "Map", "provider": "unknown"}]},
    {"configs": [{"id": "one", "name": "Map", "provider": {}}]},
    {"configs": [{"id": "one", "name": "Map", "provider": "amap", "js_key": {}}]},
    {"configs": [{"id": "one", "name": "Map", "provider": "amap", "backend_page_origin": "file:///private"}]},
])
def test_invalid_profile_updates_do_not_mutate_existing_configuration(change):
    config = profiles_config()
    before = copy.deepcopy(config._data)
    with pytest.raises(ValueError):
        merge_map_settings(config, change)
    assert config._data == before


def test_duplicate_ids_are_rejected():
    config = profiles_config()
    rows = copy.deepcopy(config.get("Map", "configs"))
    rows[1]["id"] = rows[0]["id"]
    with pytest.raises(ValueError, match="ID"):
        merge_map_settings(config, {"configs": rows})


def test_json_adapter_roundtrip_preserves_list_order_and_values(tmp_path):
    path = tmp_path / "config.json"
    config = JsonConfigAdapter(str(path))
    settings = merge_map_settings(profiles_config(), {})
    for key, value in settings.items():
        config.set("Map", key, value)
    config.write()
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(stored["Map"]["configs"], list)
    reloaded = JsonConfigAdapter(str(path))
    assert get_map_config_selection(reloaded)["js_key"] == "back-key"
    config.read(str(path))
    assert config.get("Map", "configs") == settings["configs"]


def test_configparser_can_read_json_serialized_profiles():
    source = profiles_config()
    config = configparser.ConfigParser()
    config["Map"] = {key: json.dumps(value) if isinstance(value, list) else value
                     for key, value in source._data["Map"].items()}
    assert get_map_config_selection(config)["id"] == "amap-back"


@pytest.fixture
def admin_client():
    config = profiles_config()
    writer = Mock()
    fake = SimpleNamespace(
        request=request, jsonify=jsonify, CONFIG_FILE="unused-profiles-test",
        _read_config_ini=lambda _: config, _get_default_config=lambda: config,
        merge_map_settings=merge_map_settings, _normalize_map_provider=lambda value: value,
        _write_config_with_comments=writer,
        auth_system=SimpleNamespace(check_permission=lambda *_: True, reload_config=Mock(), log_audit=Mock()),
        g=SimpleNamespace(user={"group": "admin"}),
    )
    tree = ast.parse(Path("web_server.py").read_text(encoding="utf-8"))
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "admin_config_save")
    function.decorator_list = []
    app = Flask(__name__)
    namespace = {"_main": lambda: fake, "configparser": configparser, "logging": logging, "json": json,
                 "app": app, "os": SimpleNamespace(path=SimpleNamespace(exists=lambda _: True))}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "web_server.py", "exec"), namespace)
    app.add_url_rule("/save", view_func=namespace["admin_config_save"], methods=["POST"])
    return app.test_client(), config, writer


def test_admin_http_saves_order_selections_and_explicit_empty_credentials(admin_client):
    client, config, writer = admin_client
    rows = copy.deepcopy(config.get("Map", "configs"))
    rows.reverse()
    rows[0]["js_key"] = ""
    response = client.post("/save", json={"Map": {"configs": rows, "frontend_config_id": "amap-back"}})
    assert response.status_code == 200
    assert response.json["success"] is True
    assert config.get("Map", "frontend_config_id") == "amap-back"
    assert config.get("Map", "backend_config_id") == "amap-back"
    assert config.get("Map", "configs")[0]["js_key"] == ""
    writer.assert_called_once()


def test_admin_http_rejects_dangling_references_before_any_configuration_mutation(admin_client):
    client, config, writer = admin_client
    before = copy.deepcopy(config._data)
    response = client.post("/save", json={"Config": {"default_ui": "old"}, "Map": {"frontend_config_id": "missing"}})
    assert response.status_code == 400
    assert config._data == before
    writer.assert_not_called()
