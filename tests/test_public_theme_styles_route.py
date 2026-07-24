import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask, jsonify, request as flask_request

import main as main_module
from main import Api


class TestPublicThemeStylesRoute(unittest.TestCase):
    def test_public_theme_styles_route_does_not_require_session_header(self):
        app = Flask(__name__)

        @app.route("/api/public/theme_styles", methods=["GET"])
        def get_public_theme_styles():
            requested_style = flask_request.args.get("style_id", "default")
            requested_style = str(requested_style or "default").strip() or "default"
            requested_target = str(flask_request.args.get("background_target") or "").strip().lower()
            if requested_target not in ("pc", "mobile"):
                requested_target = None
            requested_uuid = main_module._normalize_theme_background_session_uuid(
                flask_request.args.get("uuid", "")
            )
            public_api_instance = Api.__new__(Api)
            public_api_instance._web_session_id = requested_uuid
            return jsonify(public_api_instance.get_public_theme_styles(requested_style, requested_target))

        @app.route("/api/<path:method>", methods=["GET", "POST"])
        def api_call(method):
            session_id = flask_request.headers.get("X-Session-ID", "")
            if method.startswith("public/"):
                return jsonify({"success": False, "message": "public namespace should not require session"}), 500
            if not session_id:
                return jsonify({"success": False, "message": "缺少会话ID"}), 401
            return jsonify({"success": True, "method": method})

        auth_system = Mock()
        auth_system.get_available_theme_styles.return_value = [{"id": "default"}]
        auth_system.get_theme_config.return_value = {
            "basic_information": {"id": "default"},
            "global_environment_variables": {},
        }

        with tempfile.TemporaryDirectory() as d, patch("main.auth_system", auth_system, create=True), patch(
            "main.os.path.abspath", return_value=str(Path(d) / "main.py")
        ):
            with app.test_client() as client:
                response = client.get("/api/public/theme_styles?style_id=default&background_target=pc")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["theme_styles"], [{"id": "default"}])


if __name__ == "__main__":
    unittest.main()
