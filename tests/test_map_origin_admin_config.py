import ast
import configparser
import copy
import logging
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from flask import Flask, jsonify, request

import main
from config_adapter import JsonConfigAdapter
from map_runtime_origin import merge_map_settings


class MapOriginAdminConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = JsonConfigAdapter.__new__(JsonConfigAdapter)
        self.config._data = {"Map": {"provider": "amap", "backend_page_origin": "https://global.test", "providers": {
            "amap": {"js_key": "test-key", "security_js_code": "test-scode", "backend_page_origin": "https://amap.test"},
            "tencent": {"map_key": "test-tencent", "backend_page_origin": "https://tencent.test"},
        }}}
        self.write = Mock()
        fake = SimpleNamespace(
            request=request, jsonify=jsonify, CONFIG_FILE="unused-test-config",
            _read_config_ini=lambda _: self.config,
            _get_default_config=lambda: self.config,
            merge_map_settings=merge_map_settings,
            _normalize_map_provider=main._normalize_map_provider,
            _write_config_with_comments=self.write,
            auth_system=SimpleNamespace(check_permission=lambda *_: True, reload_config=Mock(), log_audit=Mock()),
            g=SimpleNamespace(user={"group": "admin"}),
        )
        tree = ast.parse(Path("web_server.py").read_text(encoding="utf-8"))
        function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "admin_config_save")
        function.decorator_list = []
        namespace = {"_main": lambda: fake, "configparser": configparser, "logging": logging, "json": json,
                     "os": SimpleNamespace(path=SimpleNamespace(exists=lambda _: True))}
        self.app = Flask(__name__)
        namespace["app"] = self.app
        exec(compile(ast.Module(body=[function], type_ignores=[]), "web_server.py", "exec"), namespace)
        self.app.add_url_rule("/save", view_func=namespace["admin_config_save"], methods=["POST"])
        self.client = self.app.test_client()

    def test_http_source_only_update_preserves_credentials_and_other_settings(self):
        response = self.client.post("/save", json={"Map": {"backend_page_origin": "https://NEW.test:443/private?session=secret"}})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(response.json["success"])
        self.assertEqual(self.config.get("Map", "backend_page_origin"), "https://new.test")
        providers = self.config.get("Map", "providers")
        self.assertEqual(providers["amap"]["js_key"], "test-key")
        self.assertEqual(providers["amap"]["security_js_code"], "test-scode")
        self.assertEqual(providers["tencent"]["backend_page_origin"], "https://tencent.test")
        self.write.assert_called_once()

    def test_invalid_source_fails_without_mutation_or_disk_save(self):
        original = copy.deepcopy(self.config._data)
        response = self.client.post("/save", json={"Config": {"default_ui": "new"}, "Map": {"backend_page_origin": "https://user:private@host.test"}})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("private", response.json["message"])
        self.assertEqual(self.config._data, original)
        self.write.assert_not_called()

    def test_explicit_empty_values_clear_only_submitted_fields(self):
        response = self.client.post("/save", json={"Map": {"providers": {"amap": {"backend_page_origin": "", "security_js_code": ""}}}})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.config.get("Map", "providers")["amap"]["security_js_code"], "")
        self.assertEqual(self.config.get("Map", "providers")["amap"]["backend_page_origin"], "")
        self.assertEqual(self.config.get("Map", "providers")["amap"]["js_key"], "test-key")
        self.assertEqual(self.config.get("Map", "backend_page_origin"), "https://global.test")

    def test_public_runtime_config_has_no_backend_origin(self):
        public = main._get_map_provider_frontend_config(self.config)
        self.assertNotIn("backend_page_origin", repr(public))
        admin = main._get_map_provider_admin_config(self.config, "amap")
        self.assertEqual(admin["backend_page_origin"], "https://amap.test")

    def test_missing_config_file_default_adapter_accepts_nested_settings(self):
        self.config = main._get_default_config()
        response = self.client.post("/save", json={"Map": {"providers": {"amap": {"security_js_code": "replacement"}}}})
        self.assertEqual(response.status_code, 200, response.json)

    def test_tile_cache_defaults_and_partial_updates(self):
        defaults = main._get_default_config()
        self.assertEqual(defaults.getint("Map", "tile_cache_ttl_days", fallback=-1), 20)
        self.assertEqual(defaults.getfloat("Map", "tile_cache_max_size_gb", fallback=-1), 10)
        response = self.client.post("/save", json={"Map": {
            "tile_cache_ttl_days": 30, "tile_cache_max_size_gb": 2.5,
        }})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.config.getint("Map", "tile_cache_ttl_days"), 30)
        self.assertEqual(self.config.getfloat("Map", "tile_cache_max_size_gb"), 2.5)
        response = self.client.post("/save", json={"Map": {"frontend_proxy_enabled": False}})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.config.getint("Map", "tile_cache_ttl_days"), 30)
        self.assertEqual(self.config.getfloat("Map", "tile_cache_max_size_gb"), 2.5)
        self.assertEqual(self.config.get("Map", "providers")["amap"]["js_key"], "test-key")

    def test_invalid_tile_cache_settings_are_transactional(self):
        invalid = (
            ("tile_cache_ttl_days", 0), ("tile_cache_ttl_days", -1),
            ("tile_cache_ttl_days", 1.5), ("tile_cache_ttl_days", True),
            ("tile_cache_ttl_days", "nan"), ("tile_cache_ttl_days", ""),
            ("tile_cache_max_size_gb", 0), ("tile_cache_max_size_gb", -1),
            ("tile_cache_max_size_gb", "inf"), ("tile_cache_max_size_gb", True),
            ("tile_cache_max_size_gb", 0.001),
        )
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                before = copy.deepcopy(self.config._data)
                self.write.reset_mock()
                response = self.client.post("/save", json={"Map": {"provider": "tencent", field: value}})
                self.assertEqual(response.status_code, 400, response.json)
                self.assertEqual(self.config._data, before)
                self.write.assert_not_called()

    def test_tile_cache_settings_are_not_public_map_configuration(self):
        self.config.set("Map", "tile_cache_ttl_days", "30")
        self.config.set("Map", "tile_cache_max_size_gb", "2.5")
        public = main._get_map_provider_frontend_config(self.config)
        self.assertNotIn("tile_cache", repr(public))

    def test_administrator_configuration_loads_saved_tile_cache_settings(self):
        tree = ast.parse(Path("web_server.py").read_text(encoding="utf-8"))
        function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "admin_config_load")
        map_payload = next(value for node in ast.walk(function) if isinstance(node, ast.Dict)
                           for key, value in zip(node.keys, node.values)
                           if isinstance(key, ast.Constant) and key.value == "Map")
        self.config.set("Map", "tile_cache_ttl_days", "45")
        self.config.set("Map", "tile_cache_max_size_gb", "12.5")
        result = eval(compile(ast.Expression(map_payload), "web_server.py", "eval"),
                      {"_main": lambda: main, "config": self.config})
        self.assertEqual(result["tile_cache_ttl_days"], 45)
        self.assertEqual(result["tile_cache_max_size_gb"], 12.5)


if __name__ == "__main__":
    unittest.main()
