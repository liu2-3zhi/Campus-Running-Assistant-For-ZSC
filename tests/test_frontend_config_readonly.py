"""Reading public feature switches must not rewrite the database config."""

import ast
import configparser
from copy import deepcopy
import logging
from pathlib import Path
from types import SimpleNamespace


def test_frontend_feature_config_reads_without_writing():
    path = Path(__file__).resolve().parents[1] / 'web_server.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = deepcopy(next(node for node in ast.walk(tree)
                         if isinstance(node, ast.FunctionDef) and node.name == 'get_frontend_config'))
    config = configparser.ConfigParser()
    config.read_dict({'Features': {'enable_sms_service': 'true', 'enable_phone_login': 'true'}})
    writes = []
    contexts = []

    def public_map(config, **context):
        contexts.append(context)
        return {'map_provider': 'test', 'map_providers': {}, 'frontend_proxy_enabled': False,
                'map_provider_key_bundle': {}}

    runtime = SimpleNamespace(
        CONFIG_FILE='configs/config.json',
        _read_config_ini=lambda path: config,
        _write_config_with_comments=lambda *args: writes.append(args),
        _build_public_map_provider_frontend_payload=public_map,
    )
    namespace = {'_main': lambda: runtime, 'configparser': configparser, 'logging': logging}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)

    for _ in range(2):
        result = namespace['get_frontend_config'](session_id='session-one', username='owner')
        assert result['sms_enabled'] is True
        assert result['enable_phone_login'] is True
    assert contexts == [{'session_id': 'session-one', 'username': 'owner'}] * 2
    assert writes == []
