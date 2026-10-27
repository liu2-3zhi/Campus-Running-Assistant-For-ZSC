"""Project route diagnostics using the authenticated HTTP caller."""

import copy

from main_runtime import _main
from route_diagnostics import build_route_failure_summary, detailed_route_failure_message, generic_route_failure_message


def can_view_route_failure_details(session_id):
    try:
        runtime = _main()
        with runtime.web_sessions_lock:
            api = runtime.web_sessions.get(session_id)
            if not api or not getattr(api, "is_authenticated", False) or getattr(api, "is_guest", True):
                return False
            owner = getattr(api, "auth_username", None)
        if not owner:
            return False
        token = runtime.request.cookies.get("auth_token")
        origin = runtime.request.headers.get(runtime.ADMIN_ORIGIN_SESSION_HEADER, "")
        if origin and origin != session_id:
            context = runtime.resolve_admin_origin_session_context(session_id, origin, token)
            if not context:
                return False
            actor = context["username"]
        elif runtime._verify_session_cookie_token(session_id, owner, token):
            actor = owner
        else:
            context = runtime.resolve_admin_view_identity(session_id, token, owner)
            if not context:
                return False
            actor = context["username"]
        role_username = owner if getattr(api, "is_multi_account_mode", False) else actor
        return runtime.auth_system.get_user_group(role_username) in ("admin", "super_admin")
    except Exception:
        return False


def project_route_failure_response(result, session_id):
    if not isinstance(result, dict):
        return result
    response = copy.deepcopy(result)
    failure = response.pop("_route_failure", None)
    if not isinstance(failure, dict):
        return response
    summary = build_route_failure_summary(failure)
    message = generic_route_failure_message(summary["diagnostic_id"])
    if can_view_route_failure_details(session_id):
        message = detailed_route_failure_message(summary)
    return {
        "success": False, "message": message,
        "diagnostic_id": summary["diagnostic_id"], "provider": summary["provider"], "notices": [],
    }
