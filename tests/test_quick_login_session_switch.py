"""快捷登录会话切换（/auth/switch_session 400）的回归测试。

复现的真实故障：
    用户在"检测到之前的登录记录 → 快捷登录 → 进入"后收到
    POST /auth/switch_session 400 {"message": "缺少会话ID参数"}。

根因:
    前端只在通过 /uuid=<uuid> 打开页面时才持有会话 UUID
    （getAuthenticatedSessionHeaderValue() 依赖 authSessionUUID / sessionUUID）。
    直接从根路径打开首页时两者都为空，X-Session-ID 请求头是空串，而接口
    只信任请求头，于是把它误判为"缺少会话ID参数"。
"""

import unittest
from unittest import mock

import main as main_module


class _FakeRequest:
    """最小化的 Flask request 替身（只覆盖 resolve_request_session_id 的读取面）。"""

    def __init__(self, headers=None, cookies=None, path="/"):
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.path = path


class TestResolveRequestSessionId(unittest.TestCase):
    def _resolve(self, **kwargs):
        fake = _FakeRequest(**kwargs)
        with mock.patch.object(main_module, "request", fake, create=True):
            return main_module.resolve_request_session_id()

    def test_header_takes_precedence(self):
        header_id = "11111111-1111-4111-8111-111111111111"
        cookie_id = "22222222-2222-4222-8222-222222222222"

        resolved = self._resolve(
            headers={"X-Session-ID": header_id},
            cookies={"session_id": cookie_id},
            path=f"/uuid={cookie_id}",
        )

        self.assertEqual(resolved, header_id)

    def test_cookie_fallback_when_header_missing(self):
        """本次报错的核心场景：页面没有 UUID，只有服务端下发的 Cookie。"""
        cookie_id = "22222222-2222-4222-8222-222222222222"

        resolved = self._resolve(
            headers={},
            cookies={"session_id": cookie_id},
            path="/",
        )

        self.assertEqual(
            resolved,
            cookie_id,
            "缺少 X-Session-ID 时必须回退到 session_id Cookie，否则快捷登录直接 400",
        )

    def test_cookie_fallback_when_header_is_empty_string(self):
        """前端在无 UUID 时会发送空串请求头，不能被当作有效会话。"""
        cookie_id = "33333333-3333-4333-8333-333333333333"

        resolved = self._resolve(
            headers={"X-Session-ID": ""},
            cookies={"session_id": cookie_id},
            path="/",
        )

        self.assertEqual(resolved, cookie_id)

    def test_path_fallback_when_header_and_cookie_missing(self):
        path_id = "44444444-4444-4444-8444-444444444444"

        resolved = self._resolve(
            headers={},
            cookies={},
            path=f"/uuid={path_id}",
        )

        self.assertEqual(resolved, path_id)

    def test_invalid_header_is_not_trusted(self):
        """非法请求头（非 UUID v4）不得胜出，应继续回退。"""
        cookie_id = "55555555-5555-4555-8555-555555555555"

        resolved = self._resolve(
            headers={"X-Session-ID": "not-a-uuid"},
            cookies={"session_id": cookie_id},
            path="/",
        )

        self.assertEqual(resolved, cookie_id)

    def test_returns_empty_when_nothing_available(self):
        self.assertEqual(self._resolve(headers={}, cookies={}, path="/"), "")

    def test_normalizes_to_lowercase(self):
        upper = "ABCDEF01-2345-4678-8ABC-DEF012345678"

        resolved = self._resolve(headers={"X-Session-ID": upper}, path="/")

        self.assertEqual(resolved, upper.lower())

    def test_null_like_values_are_rejected(self):
        resolved = self._resolve(
            headers={"X-Session-ID": "null"}, cookies={"session_id": "undefined"}
        )

        self.assertEqual(resolved, "")


class TestQuickLoginFlowContract(unittest.TestCase):
    """结构性契约：快捷登录路径上的会话接口必须使用统一解析。"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path

        cls.source = (
            Path(__file__).resolve().parents[1] / "web_server.py"
        ).read_text(encoding="utf-8")

    _HEADER_ONLY = (
        'normalize_session_uuid(_main().request.headers.get("X-Session-ID", ""))'
    )

    def _route_block(self, route):
        return self.source.split(f'@app.route("{route}"', 1)[1].split(
            "@app.route", 1
        )[0]

    def test_switch_session_uses_shared_resolver(self):
        block = self._route_block("/auth/switch_session")

        self.assertIn("_main().resolve_request_session_id()", block)
        self.assertNotIn(
            self._HEADER_ONLY,
            block,
            "会话切换不得只信任 X-Session-ID 请求头",
        )

    def test_quick_login_related_routes_use_shared_resolver(self):
        for route in (
            "/auth/user/sessions",
            "/auth/user/delete_session",
            "/auth/user/create_session_persistence",
        ):
            with self.subTest(route=route):
                block = self._route_block(route)
                self.assertIn("_main().resolve_request_session_id()", block)
                self.assertNotIn(self._HEADER_ONLY, block)

    def test_missing_ids_report_distinct_messages(self):
        """当前会话与目标会话缺失必须给出可区分的提示，便于定位。"""
        block = self._route_block("/auth/switch_session")

        self.assertIn("缺少会话ID参数", block)
        self.assertIn("缺少目标会话ID参数", block)


class TestResolveRequestSessionIdWithRealFlaskContext(unittest.TestCase):
    """用真实 Flask 请求上下文验证解析函数（而非仅用替身对象）。

    这能一并验证 request.headers / request.cookies / request.path 的读取方式
    与 Flask 实际行为一致——只靠替身对象无法发现属性名写错这类问题。
    """

    COOKIE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    HEADER_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    PATH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

    def _build_app(self):
        from flask import Flask

        app = Flask(__name__)
        captured = {}

        @app.route("/probe")
        @app.route("/uuid=<path_uuid>/probe")
        def _probe(path_uuid=None):
            captured["resolved"] = main_module.resolve_request_session_id()
            return "ok"

        return app, captured

    def test_cookie_only_request_resolves(self):
        """本次报错场景：只有 Cookie，没有 X-Session-ID 请求头。"""
        app, captured = self._build_app()
        with app.test_client() as client:
            client.set_cookie("session_id", self.COOKIE_ID)
            response = client.get("/probe")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["resolved"], self.COOKIE_ID)

    def test_header_wins_over_cookie_in_real_context(self):
        app, captured = self._build_app()
        with app.test_client() as client:
            client.set_cookie("session_id", self.COOKIE_ID)
            client.get(
                "/probe", headers={"X-Session-ID": self.HEADER_ID}
            )

        self.assertEqual(captured["resolved"], self.HEADER_ID)

    def test_path_uuid_resolves_on_legacy_route(self):
        app, captured = self._build_app()
        with app.test_client() as client:
            client.get(f"/uuid={self.PATH_ID}/probe")

        self.assertEqual(captured["resolved"], self.PATH_ID)


if __name__ == "__main__":
    unittest.main()
