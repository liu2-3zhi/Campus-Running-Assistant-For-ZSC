import ast
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]


def load_method(filename, class_name, method_name, namespace):
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8-sig"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    exec(compile(ast.Module(body=[method], type_ignores=[]), filename, "exec"), namespace)
    return namespace[method_name]


def test_server_log_and_frontend_message_are_independent():
    runtime = SimpleNamespace(socketio=Mock(), _redact_sensitive_log_value=lambda value: value)
    namespace = {"_main": lambda: runtime, "logging": Mock(), "threading": __import__("threading")}
    notify = load_method("api_runtime.py", "Api", "log_and_notify_frontend", namespace)
    api = SimpleNamespace(_web_session_id="session")
    notify(api, "provider secret failure", frontend_message="路径规划失败", diagnostic_id="diag-1")
    namespace["logging"].info.assert_called_once_with("provider secret failure")
    runtime.socketio.emit.assert_called_once_with(
        "log_message", {"msg": "路径规划失败", "diagnostic_id": "diag-1"}, room="session"
    )


def test_server_log_is_written_without_websocket():
    namespace = {"_main": lambda: SimpleNamespace(socketio=None, _redact_sensitive_log_value=lambda value: value), "logging": Mock()}
    notify = load_method("api_runtime.py", "Api", "log_and_notify_frontend", namespace)
    notify(SimpleNamespace(), "message")
    namespace["logging"].info.assert_called_once_with("message")


def test_account_prefix_is_added_once_to_both_messages():
    namespace = {}
    notify = load_method("runtime_models.py", "AccountSession", "log_and_notify_frontend", namespace)
    bridge = Mock()
    notify(SimpleNamespace(username="student", api_bridge=bridge), "detail", frontend_message="generic", diagnostic_id="diag-2")
    bridge.log_and_notify_frontend.assert_called_once_with(
        "[student] detail", frontend_message="[student] generic", diagnostic_id="diag-2"
    )


def test_temporary_client_adapter_supports_the_new_logging_contract():
    from api_client import ApiClient
    tree = ast.parse((ROOT / "brute_force_manager.py").read_text(encoding="utf-8-sig"))
    adapter = next(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == "TempApp")
    namespace = {"_main": lambda: SimpleNamespace(ApiClient=SimpleNamespace(generate_random_ua=lambda: "test-agent")), "logging": Mock()}
    exec(compile(ast.Module(body=[adapter], type_ignores=[]), "brute_force_manager.py", "exec"), namespace)
    app = namespace["TempApp"]()
    client = object.__new__(ApiClient)
    client.app = app
    assert app.api_bridge is None
    assert not hasattr(app, "log")
    assert client._json(None) is None
