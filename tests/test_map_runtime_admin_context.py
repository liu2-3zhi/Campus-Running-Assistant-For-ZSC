from unittest.mock import patch

from flask import Flask

import main as main_module


def test_map_runtime_keeps_target_crypto_context_after_verifying_admin_origin():
    app = Flask(__name__)
    target = "22222222-2222-4222-8222-222222222222"
    origin = "11111111-1111-4111-8111-111111111111"
    target_context = {"runtime_version": "target-runtime"}
    with app.test_request_context(
        "/api/map_key_runtime.js?v=target-runtime",
        headers={"X-Session-ID": target, "X-Admin-Origin-Session-ID": origin,
                 "Cookie": "auth_token=admin-token"},
    ), patch.object(main_module, "_get_map_key_runtime_session_identity", return_value=(target, "target-owner", True)), patch.object(
        main_module, "_get_map_key_runtime_context_for_session", return_value=target_context
    ) as context_for_session, patch.object(main_module, "_get_map_key_runtime_context_by_version", return_value=target_context), patch.object(
        main_module, "resolve_admin_origin_session_context", return_value={"username": "administrator"}
    ) as validate_origin:
        assert main_module._get_map_key_runtime_context_for_request() is target_context
        validate_origin.assert_called_once_with(target, origin, "admin-token")
        context_for_session.assert_called_once_with(target, "target-owner")


def test_map_runtime_rejects_invalid_explicit_origin_before_allocating_context():
    app = Flask(__name__)
    target = "22222222-2222-4222-8222-222222222222"
    with app.test_request_context(
        "/api/map_key_runtime.js?v=target-runtime",
        headers={"X-Session-ID": target, "X-Admin-Origin-Session-ID": "invalid-origin"},
    ), patch.object(main_module, "_get_map_key_runtime_session_identity", return_value=(target, "owner", True)), patch.object(
        main_module, "_get_map_key_runtime_context_for_session"
    ) as allocate, patch.object(main_module, "resolve_admin_origin_session_context", return_value=None) as validate:
        assert main_module._get_map_key_runtime_context_for_request() is None
        validate.assert_called_once_with(target, "invalid-origin", "")
        allocate.assert_not_called()
