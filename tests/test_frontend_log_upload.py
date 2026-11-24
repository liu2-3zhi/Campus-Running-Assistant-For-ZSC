"""The lightweight frontend log endpoint preserves server log redaction."""
import ast
from copy import deepcopy
import logging
from pathlib import Path
import threading
from types import SimpleNamespace

from flask import Flask, jsonify, request


def test_log_batch_uses_server_redaction_without_business_initialization(caplog):
    path = Path(__file__).resolve().parents[1] / 'web_server.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = deepcopy(next(node for node in ast.walk(tree)
                         if isinstance(node, ast.FunctionDef) and node.name == 'log_frontend'))
    node.decorator_list = []
    redacted = []

    def redact(message):
        redacted.append(message)
        return '[safe client message]'

    runtime = SimpleNamespace(request=request, jsonify=jsonify,
                              _redact_sensitive_log_value=redact)
    namespace = {'_main': lambda: runtime, 'logging': logging, 'web_sessions': {},
                 'web_sessions_lock': threading.RLock()}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    app = Flask(__name__)
    app.add_url_rule('/api/log_frontend', view_func=namespace['log_frontend'], methods=['POST'])
    with caplog.at_level(logging.INFO), app.test_client() as client:
        result = client.post('/api/log_frontend', json={'batch': [
            {'level': 'INFO', 'message': 'Bearer fixture-only', 'source': 'fixture'},
        ]})
    assert result.status_code == 200
    assert result.json == {'success': True}
    assert redacted == ['Bearer fixture-only']
    assert '[safe client message]' in caplog.text
    assert 'Bearer fixture-only' not in caplog.text
