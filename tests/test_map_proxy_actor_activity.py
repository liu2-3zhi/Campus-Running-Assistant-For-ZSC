import ast
import logging
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main


ACTOR = "11111111-1111-4111-8111-111111111111"
TARGET = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def actor_runtime(monkeypatch):
    actor = SimpleNamespace(is_authenticated=True, is_guest=False, auth_username="administrator")
    target = SimpleNamespace(is_authenticated=True, is_guest=False, auth_username="target-owner")
    sessions = {ACTOR: actor, TARGET: target}
    values = {
        "web_sessions": sessions, "web_sessions_lock": threading.Lock(),
        "session_activity": {ACTOR: 1, TARGET: 2}, "session_activity_lock": threading.Lock(),
        "browsing_activity": {TARGET: 3}, "browsing_activity_lock": threading.Lock(),
        "admin_view_origin_activity": {}, "admin_view_origin_activity_lock": threading.Lock(),
        "_verify_session_cookie_token": Mock(return_value=True),
        "auth_system": SimpleNamespace(check_permission=Mock(return_value=True)),
        "token_manager": Mock(), "save_session_state": Mock(),
    }
    for name, value in values.items():
        monkeypatch.setattr(main, name, value, raising=False)
    source = Path(main.__file__).with_name("web_server.py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef)
                and item.name == "_authorize_map_proxy_actor")
    namespace = {"_main": lambda: main, "web_sessions": sessions,
                 "web_sessions_lock": values["web_sessions_lock"], "logging": logging, "time": time}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[node.name], actor, values


@pytest.mark.parametrize("viewing", (False, True))
def test_successful_map_requests_keep_only_the_real_actor_active(actor_runtime, viewing):
    authorize, _actor, values = actor_runtime
    before = time.time()
    assert authorize("administrator", "valid-cookie", ACTOR, viewing)
    assert values["session_activity"][ACTOR] >= before
    assert values["browsing_activity"][ACTOR] >= before
    assert values["session_activity"][TARGET] == 2
    assert values["browsing_activity"][TARGET] == 3
    if viewing:
        assert values["admin_view_origin_activity"][ACTOR] >= before
    else:
        assert values["admin_view_origin_activity"] == {}
    values["_verify_session_cookie_token"].assert_called_once_with(ACTOR, "administrator", "valid-cookie")
    assert values["token_manager"].mock_calls == []
    values["save_session_state"].assert_not_called()


@pytest.mark.parametrize("failure", ("token", "view_map", "view_all_sessions", "role_query", "guest", "owner", "missing"))
def test_failed_map_authorization_never_refreshes_actor_or_target_activity(actor_runtime, failure):
    authorize, actor, values = actor_runtime
    if failure == "token":
        values["_verify_session_cookie_token"].return_value = False
    elif failure in ("view_map", "view_all_sessions"):
        values["auth_system"].check_permission.side_effect = lambda _user, permission: permission != failure
    elif failure == "role_query":
        values["auth_system"].check_permission.side_effect = RuntimeError("role lookup unavailable")
    elif failure == "guest":
        actor.is_guest = True
    elif failure == "owner":
        actor.auth_username = "other-owner"
    else:
        values["web_sessions"].pop(ACTOR)
    assert not authorize("administrator", "valid-cookie", ACTOR, True)
    assert values["session_activity"] == {ACTOR: 1, TARGET: 2}
    assert values["browsing_activity"] == {TARGET: 3}
    assert values["admin_view_origin_activity"] == {}
    assert values["token_manager"].mock_calls == []
    values["save_session_state"].assert_not_called()
