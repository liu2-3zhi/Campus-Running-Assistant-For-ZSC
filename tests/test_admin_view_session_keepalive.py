"""管理员强制进入他人会话后掉线的回归测试。

背景（真实故障）:
    管理员用老版 UI 的上帝模式强制进入他人会话后，前端不再调用
    /auth/switch_session，管理员自身会话（来源会话）的 API 流量全部转移到
    目标会话。于是:

    1. 来源会话不再被 update_session_activity 续期，会话不活跃监控会在
       session_inactivity_timeout 之后回收它；回收时因为"用户没有其他浏览
       行为"还会删除该用户的 token 文件（TokenManager 是每用户一个 token）。
    2. token 文件被删掉之后，通用 /api/<path:method> 的上帝模式兜底也失效，
       而命名路由（例如 POST /api/check_overdue）此前根本没有上帝模式兜底，
       于是管理员查看态下所有接口返回 401，前端弹出登录遮罩 = 掉线。

本文件锁定两条修复链路:
    1. 查看态请求必须续期来源会话（会话/浏览/保活窗口），且围绕来源会话的
       其他会话被清理时不得连带吊销 token；
    2. login_required / admin_required 必须和通用 API 一样接受已验证的超级
       管理员 token（上帝模式），而不是直接 401。
"""

import functools
import hashlib
import json
import logging
import os
import subprocess
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import main as main_module

PROJECT_ROOT = Path(main_module.__file__).resolve().parent
WEB_SERVER_PATH = PROJECT_ROOT / "web_server.py"

ORIGIN_SESSION_ID = "11111111-1111-4111-8111-111111111111"
TARGET_SESSION_ID = "22222222-2222-4222-8222-222222222222"
OTHER_SESSION_ID = "33333333-3333-4333-8333-333333333333"

ADMIN_COOKIE_TOKEN = "unit-test-admin-cookie-token"
VIEWED_SCHOOL_USERNAME = "2024080402005"


class DummySession:
    """会话监控/清理所需的最小 Api 会话替身。"""

    is_guest = False
    is_multi_account_mode = False
    user_data = None

    def __init__(self, session_id, auth_username="admin"):
        self._web_session_id = session_id
        self.is_authenticated = True
        self.auth_username = auth_username
        self.auth_group = "super_admin"
        self.stop_run_flag = threading.Event()
        self.stop_run_flag.set()
        self.multi_run_stop_flag = threading.Event()
        self.multi_run_stop_flag.set()
        self.api_client = mock.Mock()

    def shutdown_session_runtime(self, reason="cleanup", timeout=3.0):
        self.api_client.session.close()
        return True


def _build_origin_api(session_id=ORIGIN_SESSION_ID, username="admin"):
    return SimpleNamespace(
        _web_session_id=session_id,
        is_authenticated=True,
        is_guest=False,
        auth_username=username,
        auth_group="super_admin",
    )


def _build_target_api(session_id=TARGET_SESSION_ID, username=VIEWED_SCHOOL_USERNAME):
    return SimpleNamespace(
        _web_session_id=session_id,
        is_authenticated=True,
        is_guest=False,
        auth_username=username,
        auth_group="user",
    )


class AdminViewOriginKeepaliveTests(unittest.TestCase):
    """查看态请求必须续期来源会话，避免管理员被清理后掉线。"""

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)

    def _patch_runtime_state(self, sessions, session_activity, browsing_activity):
        session_dir = Path(self._temp_dir.name) / "sessions"
        return mock.patch.multiple(
            main_module,
            web_sessions=sessions,
            web_sessions_lock=threading.Lock(),
            session_activity=session_activity,
            session_activity_lock=threading.Lock(),
            browsing_activity=browsing_activity,
            browsing_activity_lock=threading.Lock(),
            admin_view_origin_activity={},
            admin_view_origin_activity_lock=threading.Lock(),
            session_file_locks={},
            session_file_locks_lock=threading.Lock(),
            SESSION_STORAGE_DIR=str(session_dir),
            SESSION_INDEX_FILE=str(session_dir / "_index.json"),
            chrome_pool=None,
            create=True,
        )

    def test_verified_admin_view_refreshes_origin_session_activity(self):
        sessions = {
            ORIGIN_SESSION_ID: _build_origin_api(),
            TARGET_SESSION_ID: _build_target_api(),
        }
        session_activity = {ORIGIN_SESSION_ID: time.time() - 10_000}
        browsing_activity = {}
        token_manager = SimpleNamespace(
            verify_token=mock.Mock(return_value=(True, "valid")),
        )
        auth_system = SimpleNamespace(
            check_permission=mock.Mock(return_value=True),
        )

        with self._patch_runtime_state(
            sessions, session_activity, browsing_activity
        ), mock.patch.multiple(
            main_module,
            token_manager=token_manager,
            auth_system=auth_system,
            create=True,
        ):
            context = main_module.resolve_admin_origin_session_context(
                TARGET_SESSION_ID,
                ORIGIN_SESSION_ID,
                ADMIN_COOKIE_TOKEN,
            )

            self.assertIsNotNone(context)
            self.assertEqual(context["username"], "admin")
            # 来源会话被续期：不活跃监控和内存上限淘汰都以 session_activity 为准。
            self.assertGreater(
                session_activity[ORIGIN_SESSION_ID], time.time() - 60
            )
            # 浏览活跃度同步：清理该用户其他会话时据此跳过 token 失效。
            self.assertGreater(
                browsing_activity[ORIGIN_SESSION_ID], time.time() - 60
            )
            # 保活窗口记录：即使管理员页面长时间不发请求（轮询暂停、休眠），
            # 会话监控也不会把来源会话当成超时会话回收。
            self.assertTrue(
                main_module.is_admin_view_origin_session_active(ORIGIN_SESSION_ID)
            )

    def test_rejected_admin_origin_does_not_refresh_origin_session(self):
        sessions = {
            ORIGIN_SESSION_ID: _build_origin_api(),
            TARGET_SESSION_ID: _build_target_api(),
        }
        session_activity = {ORIGIN_SESSION_ID: time.time() - 10_000}
        browsing_activity = {}
        token_manager = SimpleNamespace(
            verify_token=mock.Mock(return_value=(True, "valid")),
        )
        auth_system = SimpleNamespace(
            check_permission=mock.Mock(return_value=False),
        )

        with self._patch_runtime_state(
            sessions, session_activity, browsing_activity
        ), mock.patch.multiple(
            main_module,
            token_manager=token_manager,
            auth_system=auth_system,
            create=True,
        ):
            context = main_module.resolve_admin_origin_session_context(
                TARGET_SESSION_ID,
                ORIGIN_SESSION_ID,
                ADMIN_COOKIE_TOKEN,
            )

            self.assertIsNone(context)
            self.assertFalse(
                main_module.is_admin_view_origin_session_active(ORIGIN_SESSION_ID)
            )
            self.assertNotIn(ORIGIN_SESSION_ID, browsing_activity)

    def test_keepalive_window_expires_and_ignores_invalid_ids(self):
        with self._patch_runtime_state({}, {}, {}):
            self.assertFalse(
                main_module.is_admin_view_origin_session_active(ORIGIN_SESSION_ID)
            )
            self.assertFalse(
                main_module.is_admin_view_origin_session_active("not-a-uuid")
            )

            main_module.touch_admin_view_origin_session(ORIGIN_SESSION_ID)
            self.assertTrue(
                main_module.is_admin_view_origin_session_active(
                    ORIGIN_SESSION_ID, ttl=1800
                )
            )
            # 窗口结束后必须回到普通回收逻辑，避免来源会话永久驻留。
            self.assertFalse(
                main_module.is_admin_view_origin_session_active(
                    ORIGIN_SESSION_ID,
                    now_ts=time.time() + 1801,
                    ttl=1800,
                )
            )

    def test_session_cleanup_clears_keepalive_record(self):
        sessions = {ORIGIN_SESSION_ID: DummySession(ORIGIN_SESSION_ID)}
        auth_system = mock.Mock()
        auth_system.get_user_sessions.return_value = [ORIGIN_SESSION_ID]
        token_manager = mock.Mock()
        token_manager.get_token_last_activity.return_value = 0

        with self._patch_runtime_state(sessions, {}, {}), mock.patch.multiple(
            main_module,
            auth_system=auth_system,
            token_manager=token_manager,
            create=True,
        ):
            main_module.touch_admin_view_origin_session(ORIGIN_SESSION_ID)
            self.assertTrue(
                main_module.is_admin_view_origin_session_active(ORIGIN_SESSION_ID)
            )

            main_module.cleanup_inactive_session(ORIGIN_SESSION_ID, reason="logout")

            self.assertFalse(
                main_module.is_admin_view_origin_session_active(ORIGIN_SESSION_ID)
            )
            self.assertNotIn(ORIGIN_SESSION_ID, main_module.web_sessions)

    def _cleanup_token_decision(
        self, last_activity, other_live_sessions=(), stored_sessions=(), state_files=()
    ):
        """跑一次会话清理，返回 token_manager 以便检查是否吊销了 token。"""
        sessions = {OTHER_SESSION_ID: DummySession(OTHER_SESSION_ID, auth_username="manager")}
        for sid in other_live_sessions:
            sessions[sid] = DummySession(sid, auth_username="manager")
        auth_system = mock.Mock()
        auth_system.get_user_sessions.return_value = list(stored_sessions)
        token_manager = mock.Mock()
        token_manager.get_token_last_activity.return_value = last_activity

        session_dir = Path(self._temp_dir.name) / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        for sid in state_files:
            (session_dir / f"{hashlib.sha256(sid.encode()).hexdigest()}.json").write_text(
                "{}", encoding="utf-8"
            )

        with self._patch_runtime_state(
            sessions, {}, {}
        ), mock.patch.multiple(
            main_module,
            auth_system=auth_system,
            token_manager=token_manager,
            create=True,
        ):
            main_module.cleanup_inactive_session(OTHER_SESSION_ID, reason="inactive")

        return token_manager

    def test_cleanup_keeps_token_when_user_has_another_live_session(self):
        """销毁会话时只有该用户最后一个会话才需要吊销 token。"""
        token_manager = self._cleanup_token_decision(
            time.time() - 10_000,
            other_live_sessions=[ORIGIN_SESSION_ID],
        )

        token_manager.invalidate_token.assert_not_called()
        # 还有其他会话时连 token 活动时间都不需要查。
        token_manager.get_token_last_activity.assert_not_called()

    def test_cleanup_keeps_token_when_persisted_session_still_exists(self):
        token_manager = self._cleanup_token_decision(
            time.time() - 10_000,
            stored_sessions=[ORIGIN_SESSION_ID],
            state_files=[ORIGIN_SESSION_ID],
        )

        token_manager.invalidate_token.assert_not_called()

    def test_cleanup_ignores_stale_stored_session_ids(self):
        """用户文件里残留、但没有状态文件的会话 ID 不算"还有其他会话"。"""
        token_manager = self._cleanup_token_decision(
            time.time() - 10_000,
            stored_sessions=[ORIGIN_SESSION_ID],
        )

        token_manager.get_token_last_activity.assert_called_once()
        token_manager.invalidate_token.assert_called_once()

    def test_cleanup_keeps_token_that_is_still_refreshing(self):
        """最后一个会话，但 token 仍在被刷新（查看态），不能整体吊销。"""
        token_manager = self._cleanup_token_decision(time.time())
        token_manager.get_token_last_activity.assert_called_once()
        token_manager.invalidate_token.assert_not_called()

    def test_cleanup_invalidates_token_when_nobody_uses_it(self):
        token_manager = self._cleanup_token_decision(time.time() - 10_000)
        token_manager.get_token_last_activity.assert_called_once()
        token_manager.invalidate_token.assert_called_once()

    def test_cleanup_invalidates_token_when_activity_unknown(self):
        for value in (None, 0, "not-a-number"):
            with self.subTest(value=value):
                token_manager = self._cleanup_token_decision(value)
                token_manager.invalidate_token.assert_called_once()

    def test_token_in_use_check_survives_missing_token_manager(self):
        """token_manager 未初始化时判据必须返回 False，而不是抛异常。"""
        with mock.patch.multiple(main_module, token_manager=None, create=True):
            self.assertFalse(
                main_module._is_user_token_in_active_use("manager", 300)
            )

    def test_token_guard_runs_even_when_browsing_check_fails(self):
        """浏览状态检查报错时不能顺手把仍在使用的 token 删掉。"""
        sessions = {OTHER_SESSION_ID: DummySession(OTHER_SESSION_ID)}
        auth_system = mock.Mock()
        auth_system.get_user_sessions.side_effect = RuntimeError(
            "auth store unavailable"
        )
        token_manager = mock.Mock()
        token_manager.get_token_last_activity.return_value = time.time()

        with self._patch_runtime_state(
            sessions, {}, {}
        ), mock.patch.multiple(
            main_module,
            auth_system=auth_system,
            token_manager=token_manager,
            create=True,
        ):
            main_module.cleanup_inactive_session(OTHER_SESSION_ID, reason="inactive")

        token_manager.get_token_last_activity.assert_called_once()
        token_manager.invalidate_token.assert_not_called()

    def test_view_origin_owner_activity_uses_token_refresh(self):
        sessions = {ORIGIN_SESSION_ID: DummySession(ORIGIN_SESSION_ID)}
        token_manager = mock.Mock()
        token_manager.get_token_last_activity.return_value = time.time()

        with self._patch_runtime_state(sessions, {}, {}), mock.patch.multiple(
            main_module,
            token_manager=token_manager,
            create=True,
        ):
            # 没有查看态记录过这个会话时不能凭 token 活跃度保活。
            self.assertFalse(
                main_module.is_admin_view_origin_owner_active(
                    ORIGIN_SESSION_ID, "manager", 300
                )
            )

            main_module.touch_admin_view_origin_session(ORIGIN_SESSION_ID)
            self.assertTrue(
                main_module.is_admin_view_origin_owner_active(
                    ORIGIN_SESSION_ID, "manager", 300
                )
            )

            token_manager.get_token_last_activity.return_value = (
                time.time() - 10_000
            )
            self.assertFalse(
                main_module.is_admin_view_origin_owner_active(
                    ORIGIN_SESSION_ID, "manager", 300
                )
            )

    def _run_monitor_once(
        self,
        sessions,
        session_activity,
        browsing_activity,
        token_manager=None,
        setup=None,
    ):
        """跑一轮 monitor_session_inactivity，返回被清理的会话 ID 列表。

        setup 在运行时的同一套补丁内执行，用于预置保活/活跃度状态。
        """
        cleanup_calls = []
        sleep_calls = []

        def fake_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) >= 2:
                # 让 while True 循环在完成一轮检查后退出。
                raise SystemExit

        config = main_module.configparser.ConfigParser(strict=False)
        config.add_section("System")
        config.set("System", "session_monitor_check_interval", "1")
        config.set("System", "session_inactivity_timeout", "1")

        with self._patch_runtime_state(
            sessions, session_activity, browsing_activity
        ), mock.patch.multiple(
            main_module,
            _is_auto_attendance_enabled=mock.Mock(return_value=False),
            cleanup_inactive_session=mock.Mock(
                side_effect=lambda sid, reason="manual": cleanup_calls.append(sid)
            ),
            _read_config_ini=mock.Mock(return_value=config),
            token_manager=token_manager if token_manager is not None else mock.Mock(),
            create=True,
        ), mock.patch.object(
            main_module.os.path, "exists", return_value=True
        ), mock.patch.object(main_module.time, "sleep", fake_sleep):
            if setup is not None:
                setup()
            with self.assertRaises(SystemExit):
                main_module.monitor_session_inactivity()

        # 监控循环的间隔来自被 mock 的配置，说明这一轮用的是本测试的阈值。
        self.assertEqual(sleep_calls[0], 1)
        return cleanup_calls

    def test_session_monitor_skips_cleanup_for_view_origin(self):
        """会话监控必须把保活窗口内的来源会话当成活跃会话。"""
        sessions = {
            ORIGIN_SESSION_ID: DummySession(ORIGIN_SESSION_ID),
            OTHER_SESSION_ID: DummySession(
                OTHER_SESSION_ID, auth_username=VIEWED_SCHOOL_USERNAME
            ),
        }
        stale_ts = time.time() - 10_000
        session_activity = {
            ORIGIN_SESSION_ID: stale_ts,
            OTHER_SESSION_ID: stale_ts,
        }
        browsing_activity = {}

        def setup():
            main_module.touch_admin_view_origin_session(ORIGIN_SESSION_ID)
            # 保活窗口内（1800s > 不活跃阈值 1s）但 session_activity 已过期。
            with main_module.session_activity_lock:
                main_module.session_activity[ORIGIN_SESSION_ID] = stale_ts
            with main_module.admin_view_origin_activity_lock:
                main_module.admin_view_origin_activity[ORIGIN_SESSION_ID] = (
                    time.time() - 600
                )

        cleanup_calls = self._run_monitor_once(
            sessions, session_activity, browsing_activity, setup=setup
        )

        self.assertEqual(cleanup_calls, [OTHER_SESSION_ID])

    def test_session_monitor_keeps_view_origin_while_owner_is_active(self):
        """保活窗口过期但查看者仍在活动时，来源会话同样不能回收。"""
        sessions = {
            ORIGIN_SESSION_ID: DummySession(ORIGIN_SESSION_ID, auth_username="manager"),
            OTHER_SESSION_ID: DummySession(
                OTHER_SESSION_ID, auth_username=VIEWED_SCHOOL_USERNAME
            ),
        }
        stale_ts = time.time() - 10_000
        session_activity = {
            ORIGIN_SESSION_ID: stale_ts,
            OTHER_SESSION_ID: stale_ts,
        }
        browsing_activity = {}
        token_manager = mock.Mock()
        # 查看者仍在其他会话发请求：token 刚刚被刷新。
        token_manager.get_token_last_activity.return_value = time.time()

        def setup():
            main_module.touch_admin_view_origin_session(ORIGIN_SESSION_ID)
            with main_module.session_activity_lock:
                main_module.session_activity[ORIGIN_SESSION_ID] = stale_ts
            # 保活窗口已经过期（模拟查看态页面 30 分钟没有任何带来源会话头的请求）。
            with main_module.admin_view_origin_activity_lock:
                main_module.admin_view_origin_activity[ORIGIN_SESSION_ID] = (
                    time.time() - 3600
                )

        cleanup_calls = self._run_monitor_once(
            sessions,
            session_activity,
            browsing_activity,
            token_manager=token_manager,
            setup=setup,
        )

        self.assertEqual(cleanup_calls, [OTHER_SESSION_ID])
        token_manager.get_token_last_activity.assert_called()


class AdminViewIdentityResolutionTests(unittest.TestCase):
    """查看态身份解析：按 view_all_sessions 权限放行，不限于超级管理员。"""

    def _resolve(
        self,
        token=ADMIN_COOKIE_TOKEN,
        session_owner=VIEWED_SCHOOL_USERNAME,
        **overrides
    ):
        auth_system = SimpleNamespace(
            config=SimpleNamespace(
                get=mock.Mock(return_value=overrides.pop("super_admin", "root-admin"))
            ),
            check_permission=mock.Mock(
                return_value=overrides.pop("has_permission", True)
            ),
            get_user_group=mock.Mock(
                return_value=overrides.pop("group", "admin")
            ),
        )
        token_manager = SimpleNamespace(
            resolve_username_by_token=mock.Mock(
                return_value=overrides.pop("token_owner", "manager")
            ),
            verify_token=mock.Mock(
                return_value=overrides.pop("token_result", (True, "valid"))
            ),
        )
        with mock.patch.multiple(
            main_module,
            auth_system=auth_system,
            token_manager=token_manager,
            create=True,
        ):
            result = main_module.resolve_admin_view_identity(
                TARGET_SESSION_ID, token, session_owner
            )
        return result, token_manager, auth_system

    def test_admin_group_viewer_is_accepted(self):
        """能进入他人会话的不一定是超级管理员：admin 组也能通过。"""
        result, token_manager, auth_system = self._resolve()

        self.assertIsNotNone(result)
        self.assertEqual(result["username"], "manager")
        self.assertEqual(result["group"], "admin")
        self.assertEqual(result["session_id"], TARGET_SESSION_ID)
        token_manager.resolve_username_by_token.assert_called_once_with(
            ADMIN_COOKIE_TOKEN
        )
        token_manager.verify_token.assert_called_once_with(
            "manager", TARGET_SESSION_ID, ADMIN_COOKIE_TOKEN
        )
        auth_system.check_permission.assert_called_once_with(
            "manager", "view_all_sessions"
        )

    def test_viewer_without_permission_is_rejected(self):
        result, _, _ = self._resolve(has_permission=False)
        self.assertIsNone(result)

    def test_super_admin_without_explicit_permission_keeps_fallback(self):
        result, _, _ = self._resolve(
            has_permission=False, token_owner="root-admin", super_admin="root-admin"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["username"], "root-admin")

    def test_expired_or_mismatched_token_is_rejected(self):
        for token_result in ((False, "token_mismatch"), (False, "token_expired")):
            with self.subTest(token_result=token_result):
                result, _, _ = self._resolve(token_result=token_result)
                self.assertIsNone(result)

    def test_session_owner_token_is_not_treated_as_view_mode(self):
        result, token_manager, _ = self._resolve(token_owner=VIEWED_SCHOOL_USERNAME)
        self.assertIsNone(result)
        token_manager.verify_token.assert_not_called()

    def test_unknown_token_owner_is_rejected(self):
        for token_owner in ("", None, "not-a-username-but-ok"):
            with self.subTest(token_owner=token_owner):
                result, _, _ = self._resolve(
                    token_owner=token_owner, has_permission=True
                )
                if token_owner == "not-a-username-but-ok":
                    self.assertIsNotNone(result)
                else:
                    self.assertIsNone(result)

    def test_non_string_reverse_lookup_result_is_rejected(self):
        """反查返回非字符串（异常实现/mock）时不能当作有效身份。"""
        result, _, _ = self._resolve(token_owner=mock.Mock())
        self.assertIsNone(result)

    def test_missing_reverse_lookup_is_rejected(self):
        with mock.patch.multiple(
            main_module,
            auth_system=SimpleNamespace(
                config=SimpleNamespace(get=mock.Mock(return_value="root-admin"))
            ),
            token_manager=SimpleNamespace(),
            create=True,
        ):
            self.assertIsNone(
                main_module.resolve_admin_view_identity(
                    TARGET_SESSION_ID, ADMIN_COOKIE_TOKEN, VIEWED_SCHOOL_USERNAME
                )
            )

    def test_empty_token_or_session_is_rejected(self):
        self.assertIsNone(
            main_module.resolve_admin_view_identity(TARGET_SESSION_ID, "", "x")
        )
        self.assertIsNone(
            main_module.resolve_admin_view_identity("not-a-uuid", "token", "x")
        )


class _MainHolder:
    current = None


def _load_decorator(decorator_name):
    """从 web_server.py 中提取装饰器源码并在测试命名空间中执行。

    这两个装饰器定义在 start_web_server() 内部，直接导入会拉起整个服务；
    这里只取装饰器本体，用假的 _main() 驱动真实代码路径。
    """
    source = WEB_SERVER_PATH.read_text(encoding="utf-8")
    start = source.index(f"    def {decorator_name}(f):")
    marker = "        return decorated_function"
    end = source.index(marker, start) + len(marker)
    block = textwrap.dedent(source[start:end])

    namespace = {
        "functools": functools,
        "logging": logging,
        "time": time,
        "web_sessions": {},
        "web_sessions_lock": threading.Lock(),
        "_main": lambda: _MainHolder.current,
    }
    exec(compile(block, str(WEB_SERVER_PATH), "exec"), namespace)
    return namespace


class _FakeRequest:
    def __init__(self, session_id, origin_session_id="", token=ADMIN_COOKIE_TOKEN):
        self.headers = {
            "X-Session-ID": session_id,
            "X-Admin-Origin-Session-ID": origin_session_id,
        }
        self.cookies = {"auth_token": token}


class _FakeMain:
    def __init__(
        self,
        session_id,
        api_instance,
        *,
        origin_context=None,
        cookie_token_valid=False,
        view_identity=None,
        origin_session_id="",
    ):
        self.request = _FakeRequest(
            session_id, origin_session_id, ADMIN_COOKIE_TOKEN
        )
        self.g = SimpleNamespace()
        self.ADMIN_ORIGIN_SESSION_HEADER = main_module.ADMIN_ORIGIN_SESSION_HEADER
        self.normalize_session_uuid = main_module.normalize_session_uuid
        self._is_safe_auth_username = lambda value: bool(str(value or "").strip())
        self._verify_session_cookie_token = mock.Mock(
            return_value=cookie_token_valid
        )
        self.resolve_admin_origin_session_context = mock.Mock(
            return_value=origin_context
        )
        self.resolve_admin_view_identity = mock.Mock(return_value=view_identity)
        self.auth_system = SimpleNamespace(
            get_account_cancellation_status=mock.Mock(return_value=None),
            delete_user=mock.Mock(),
        )
        self.token_manager = mock.Mock()
        self.cleanup_session = mock.Mock()
        self._api_instance = api_instance

    def jsonify(self, payload):
        return payload


class NamedRouteGodModeFallbackTests(unittest.TestCase):
    """命名路由在管理员查看态下不能因为缺少来源会话头而 401。"""

    def setUp(self):
        self.login_namespace = _load_decorator("login_required")
        self.admin_namespace = _load_decorator("admin_required")

    def _run_login_required(self, fake_main, api_instance):
        self.login_namespace["web_sessions"][TARGET_SESSION_ID] = api_instance
        _MainHolder.current = fake_main
        decorator = self.login_namespace["login_required"]

        @decorator
        def view():
            return {"success": True, "message": "view-ran"}

        return view()

    def _run_admin_required(self, fake_main, api_instance):
        self.admin_namespace["web_sessions"][TARGET_SESSION_ID] = api_instance
        _MainHolder.current = fake_main
        decorator = self.admin_namespace["admin_required"]

        @decorator
        def view():
            return {"success": True, "message": "view-ran"}

        return view()

    def test_login_required_accepts_verified_view_identity(self):
        """非超级管理员（admin 组，有 view_all_sessions）也必须能继续操作。"""
        api_instance = _build_target_api()
        fake_main = _FakeMain(
            TARGET_SESSION_ID,
            api_instance,
            cookie_token_valid=False,
            view_identity={
                "username": "manager",
                "group": "admin",
                "session_id": TARGET_SESSION_ID,
            },
        )

        response = self._run_login_required(fake_main, api_instance)

        self.assertEqual(response, {"success": True, "message": "view-ran"})
        # 目标会话 owner 的 token 不匹配，必须调用查看态身份兜底。
        fake_main.resolve_admin_view_identity.assert_called_once_with(
            TARGET_SESSION_ID, ADMIN_COOKIE_TOKEN, VIEWED_SCHOOL_USERNAME
        )
        self.assertEqual(fake_main.g.user, "manager")
        self.assertIs(fake_main.g.api_instance, api_instance)
        self.assertEqual(fake_main.g.session_id, TARGET_SESSION_ID)

    def test_login_required_still_rejects_unverified_token(self):
        api_instance = _build_target_api()
        fake_main = _FakeMain(
            TARGET_SESSION_ID,
            api_instance,
            cookie_token_valid=False,
            view_identity=None,
        )

        response = self._run_login_required(fake_main, api_instance)

        payload, status_code = response
        self.assertEqual(status_code, 401)
        self.assertTrue(payload["need_login"])
        self.assertFalse(hasattr(fake_main.g, "user"))

    def test_login_required_prefers_origin_admin_view_context(self):
        api_instance = _build_target_api()
        origin_api = _build_origin_api()
        fake_main = _FakeMain(
            TARGET_SESSION_ID,
            api_instance,
            origin_context={
                "session_id": ORIGIN_SESSION_ID,
                "username": "admin",
                "group": "super_admin",
                "api_instance": origin_api,
            },
        )

        response = self._run_login_required(fake_main, api_instance)

        self.assertEqual(response, {"success": True, "message": "view-ran"})
        fake_main.resolve_admin_view_identity.assert_not_called()
        self.assertEqual(fake_main.g.user, "admin")
        self.assertEqual(fake_main.g.session_id, ORIGIN_SESSION_ID)
        self.assertEqual(fake_main.g.viewed_session_id, TARGET_SESSION_ID)

    def test_login_required_revokes_token_for_cancelled_account(self):
        api_instance = _build_target_api()
        fake_main = _FakeMain(
            TARGET_SESSION_ID, api_instance, cookie_token_valid=True
        )
        fake_main.auth_system.get_account_cancellation_status = mock.Mock(
            return_value={"status": "pending", "execute_at": 0}
        )

        response = self._run_login_required(fake_main, api_instance)

        payload, status_code = response
        self.assertEqual(status_code, 403)
        self.assertEqual(payload["message"], "账号已注销")
        fake_main.auth_system.delete_user.assert_called_once_with(
            VIEWED_SCHOOL_USERNAME
        )
        # 注销账号必须显式吊销 token，不能依赖会话清理中的“仍在使用”判定。
        fake_main.token_manager.invalidate_token.assert_called_once_with(
            VIEWED_SCHOOL_USERNAME
        )
        fake_main.cleanup_session.assert_called_once_with(
            TARGET_SESSION_ID, reason="account_cancelled"
        )

    def test_admin_required_accepts_admin_group_view_identity(self):
        api_instance = _build_target_api()
        fake_main = _FakeMain(
            TARGET_SESSION_ID,
            api_instance,
            cookie_token_valid=False,
            view_identity={
                "username": "manager",
                "group": "admin",
                "session_id": TARGET_SESSION_ID,
            },
        )

        response = self._run_admin_required(fake_main, api_instance)

        self.assertEqual(response, {"success": True, "message": "view-ran"})
        self.assertEqual(fake_main.g.user, "manager")

    def test_admin_required_rejects_non_admin_group_view_identity(self):
        api_instance = _build_target_api()
        fake_main = _FakeMain(
            TARGET_SESSION_ID,
            api_instance,
            cookie_token_valid=False,
            view_identity={
                "username": "watcher",
                "group": "user",
                "session_id": TARGET_SESSION_ID,
            },
        )

        response = self._run_admin_required(fake_main, api_instance)

        payload, status_code = response
        self.assertEqual(status_code, 403)
        self.assertIn("权限不足", payload["message"])

    def test_admin_required_rejects_unverified_token(self):
        api_instance = _build_target_api()
        fake_main = _FakeMain(
            TARGET_SESSION_ID,
            api_instance,
            cookie_token_valid=False,
            view_identity=None,
        )

        response = self._run_admin_required(fake_main, api_instance)

        payload, status_code = response
        self.assertEqual(status_code, 401)
        self.assertTrue(payload["need_login"])


class TokenLastActivityTests(unittest.TestCase):
    """TokenManager.get_token_last_activity 是"token 仍在使用"的判据来源。"""

    def test_reports_refresh_activity_and_handles_missing_or_broken_files(self):
        from runtime_models import TokenManager

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = TokenManager(temp_dir)

            self.assertEqual(manager.get_token_last_activity("ghost"), 0)

            manager.create_token("admin", TARGET_SESSION_ID)
            created_activity = manager.get_token_last_activity("admin")
            self.assertGreater(created_activity, time.time() - 60)

            manager.refresh_token("admin", TARGET_SESSION_ID)
            self.assertGreaterEqual(
                manager.get_token_last_activity("admin"), created_activity
            )

            token_path = Path(temp_dir) / "admin.json"
            token_path.write_text("{not-json", encoding="utf-8")
            self.assertEqual(manager.get_token_last_activity("admin"), 0)


class TokenOwnerReverseLookupTests(unittest.TestCase):
    """按 token 值反查持有者：查看态身份解析的基础。"""

    def setUp(self):
        from runtime_models import TokenManager

        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        self.temp_dir = self._temp_dir.name
        self.manager = TokenManager(self.temp_dir)

    def test_created_token_resolves_to_owner_and_is_forgotten_on_invalidate(self):
        token = self.manager.create_token("manager", TARGET_SESSION_ID)

        self.assertEqual(
            self.manager.resolve_username_by_token(token), "manager"
        )

        self.manager.invalidate_token("manager", TARGET_SESSION_ID)
        self.assertEqual(self.manager.resolve_username_by_token(token), "")

    def test_scan_finds_tokens_created_before_this_process(self):
        """服务重启后旧 token 不在索引里，必须能在启动扫描时反查到。"""
        from runtime_models import TokenManager

        legacy_token = "legacy-token-value"
        (Path(self.temp_dir) / "manager.json").write_text(
            json.dumps(
                {
                    "token": legacy_token,
                    "created_at": time.time(),
                    "expires_at": time.time() + 3600,
                    "last_activity": time.time(),
                }
            ),
            encoding="utf-8",
        )

        fresh_manager = TokenManager(self.temp_dir)
        self.assertEqual(
            fresh_manager.resolve_username_by_token(legacy_token), "manager"
        )

    def test_request_path_does_not_scan_the_token_directory(self):
        """反查是纯内存索引：请求路径不扫描目录（避免拖住全局会话锁）。"""
        from runtime_models import TokenManager

        late_token = "late-token-value"
        (Path(self.temp_dir) / "late.json").write_text(
            json.dumps(
                {
                    "token": late_token,
                    "created_at": time.time(),
                    "expires_at": time.time() + 3600,
                    "last_activity": time.time(),
                }
            ),
            encoding="utf-8",
        )

        # 运行期出现的令牌文件不会立刻进入索引，重启后的新实例才会加载。
        self.assertEqual(self.manager.resolve_username_by_token(late_token), "")
        self.assertEqual(
            TokenManager(self.temp_dir).resolve_username_by_token(late_token),
            "late",
        )

    def test_unknown_or_empty_token_resolves_to_empty(self):
        self.assertEqual(self.manager.resolve_username_by_token(""), "")
        self.assertEqual(
            self.manager.resolve_username_by_token("no-such-token"), ""
        )

    def test_expired_token_cleanup_drops_reverse_lookup_entry(self):
        token = self.manager.create_token("manager", TARGET_SESSION_ID)
        self.assertEqual(
            self.manager.resolve_username_by_token(token), "manager"
        )

        # 手工把过期时间调到过去，模拟令牌自然过期后的定期清理。
        token_path = Path(self.temp_dir) / "manager.json"
        token_data = json.loads(token_path.read_text(encoding="utf-8"))
        token_data["expires_at"] = time.time() - 10
        token_path.write_text(json.dumps(token_data), encoding="utf-8")

        self.manager.cleanup_expired_tokens("manager")

        self.assertFalse(token_path.exists())
        # 索引里不能留下已经删掉的令牌条目（否则长期运行会缓慢增长）。
        with self.manager._token_owner_index_lock:
            self.assertNotIn(token, self.manager._token_owner_index)
        self.assertEqual(self.manager.resolve_username_by_token(token), "")


class CheckOverdueRouteContractTests(unittest.TestCase):
    """锁定被报告的接口本身仍受 login_required 保护。"""

    def test_check_overdue_route_uses_login_required(self):
        source = WEB_SERVER_PATH.read_text(encoding="utf-8")
        block = source[
            source.index('@app.route("/api/check_overdue", methods=["POST"])') :
        ]
        block = block[: block.index("\n    @app.route")]
        self.assertIn("@login_required", block)


def _extract_js_section(source, start_marker, end_marker):
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _run_node_script(script):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".cjs",
            encoding="utf-8",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(script)
        return subprocess.run(
            ["node", str(temp_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=False,
            check=False,
        )
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


class AdminViewOverdueRequestHeaderTests(unittest.TestCase):
    """管理员查看态下 /api/check_overdue 必须携带来源会话头。

    这是被报告的那个请求：老版 UI 用裸 fetch 调 /api/check_overdue，之前只带
    X-Session-ID，后端只能按目标会话 owner 校验 token → 401。
    """

    def test_check_overdue_sends_origin_session_header_in_admin_view(self):
        main_source = (PROJECT_ROOT / "scripts" / "main.js").read_text(
            encoding="utf-8"
        )
        payment_source = (
            PROJECT_ROOT / "scripts" / "legacy-payment-user.js"
        ).read_text(encoding="utf-8")
        resolver_source = _extract_js_section(
            main_source,
            "function isUsableClientSessionUUID(value) {",
            "\n\nfunction shouldSuppressLoggedOutElsewhereNotice",
        )
        overdue_source = _extract_js_section(
            payment_source,
            "async function checkOverdueBeforeStart(",
            "\nlet _requirePaymentForOverdueCache",
        )

        node_script = f"""
const resolverSource = {json.dumps(resolver_source)};
const overdueSource = {json.dumps(overdue_source)};
const originSession = {json.dumps(ORIGIN_SESSION_ID)};
const targetSession = {json.dumps(TARGET_SESSION_ID)};
const fetchCalls = [];
const storage = new Map([['admin_return_origin', originSession]]);
globalThis.console = {{ log() {{}}, info() {{}}, warn() {{}}, error() {{}} }};
globalThis.window = {{ location: {{ pathname: `/uuid=${{targetSession}}` }} }};
globalThis.document = {{ getElementById() {{ return null; }} }};
globalThis.localStorage = {{
  getItem(key) {{ return storage.has(key) ? storage.get(key) : null; }},
  setItem(key, value) {{ storage.set(key, value); }},
  removeItem(key) {{ storage.delete(key); }},
}};
globalThis.sessionStorage = {{ setItem() {{}}, getItem() {{ return ''; }} }};
globalThis.sessionUUID = targetSession;
globalThis.authSessionUUID = null;
globalThis.authLoginInProgress = false;
globalThis.getUUIDFromURL = () => targetSession;
globalThis.fetch = async (url, options) => {{
  fetchCalls.push({{ url, headers: options.headers }});
  return {{
    ok: true,
    json: async () => ({{ success: true, has_overdue: false, overdue_accounts: [] }}),
  }};
}};

const {{ checkOverdueBeforeStart }} = Function(
  resolverSource + "\\n" + overdueSource + "\\nreturn {{ checkOverdueBeforeStart }};",
)();

(async () => {{
  await checkOverdueBeforeStart('{VIEWED_SCHOOL_USERNAME}');
  process.stdout.write(JSON.stringify(fetchCalls));
}})().catch((error) => {{
  process.stderr.write(error.stack || String(error));
  process.exit(1);
}});
"""

        result = _run_node_script(node_script)
        stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
        stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

        if result.returncode != 0:
            self.fail(
                "Node overdue header regression failed\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            )

        payload = json.loads(stdout)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["url"], "/api/check_overdue")
        self.assertEqual(
            payload[0]["headers"],
            {
                "Content-Type": "application/json",
                "X-Session-ID": TARGET_SESSION_ID,
                "X-Admin-Origin-Session-ID": ORIGIN_SESSION_ID,
            },
        )

    def test_generic_api_route_tries_view_fallbacks_for_any_token_failure(self):
        """通用 /api/<method> 不能用 reason 当门槛，否则查看态会 401。"""
        source = WEB_SERVER_PATH.read_text(encoding="utf-8")
        start = source.index("    def api_call(method):")
        end = source.index("\n    @app.route", start)
        block = source[start:end]

        self.assertIn("resolve_admin_origin_session_context(", block)
        self.assertIn("resolve_admin_view_identity(", block)
        # 旧实现把两个兜底都挂在 reason == "token_mismatch" 上；被查看用户的
        # token 缺失/过期（no_token_file / token_expired）时查看者会被 401。
        self.assertNotIn('not is_valid and reason == "token_mismatch"', block)
        self.assertIn("if not is_valid:", block)

    def test_generic_api_permission_check_uses_caller_identity(self):
        """查看态下细粒度权限必须按实际调用者判断。"""
        source = WEB_SERVER_PATH.read_text(encoding="utf-8")
        start = source.index("    def api_call(method):")
        end = source.index("\n    @app.route", start)
        block = source[start:end]

        self.assertIn('admin_view_identity["username"]', block)
        self.assertIn("permission_username = (", block)

    def test_named_routes_use_shared_view_identity_resolver(self):
        source = WEB_SERVER_PATH.read_text(encoding="utf-8")
        for decorator in ("login_required", "admin_required"):
            start = source.index(f"    def {decorator}(f):")
            end = source.index("        return decorated_function", start)
            block = source[start:end]
            self.assertIn("resolve_admin_view_identity(", block)


def _load_web_server_helper(helper_name):
    """从 web_server.py 中提取 start_web_server() 内部的辅助函数并执行。

    这些辅助函数依赖 web_sessions/_main()，直接导入会拉起整个服务；
    这里只取函数本体，用假的 _main() 驱动真实代码路径。
    """
    source = WEB_SERVER_PATH.read_text(encoding="utf-8")
    start = source.index(f"    def {helper_name}(")
    end = source.index("\n    # ======", start)
    block = textwrap.dedent(source[start:end])

    namespace = {
        "logging": logging,
        "os": os,
        "json": json,
        "web_sessions": {},
        "web_sessions_lock": threading.Lock(),
        "_main": lambda: _MainHolder.current,
    }
    exec(compile(block, str(WEB_SERVER_PATH), "exec"), namespace)
    return namespace


class UserCredentialPurgeTests(unittest.TestCase):
    """删除用户 / 改密 / 销毁会话共用的凭证作废逻辑。"""

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        self.user_file = Path(self._temp_dir.name) / "manager.json"
        self.user_file.write_text(
            json.dumps({"auth_username": "manager", "session_ids": ["s-1"]}),
            encoding="utf-8",
        )

    def _build(self, sessions, stored_sessions=None):
        namespace = _load_web_server_helper("_purge_user_credentials")
        cleaned = []
        token_manager = mock.Mock()
        auth_system = SimpleNamespace(
            get_user_sessions=mock.Mock(return_value=list(stored_sessions or [])),
            get_user_file_path=mock.Mock(return_value=str(self.user_file)),
            lock=threading.Lock(),
        )
        fake_main = SimpleNamespace(
            normalize_session_uuid=main_module.normalize_session_uuid,
            token_manager=token_manager,
            auth_system=auth_system,
            cleanup_session=mock.Mock(
                side_effect=lambda sid, reason="manual": cleaned.append((sid, reason))
            ),
        )
        namespace["web_sessions"].update(sessions)
        _MainHolder.current = fake_main
        return namespace["_purge_user_credentials"], cleaned, token_manager, fake_main

    def test_purge_invalidates_token_and_cleans_all_sessions(self):
        purge, cleaned, token_manager, _ = self._build(
            {
                "s-1": SimpleNamespace(auth_username="manager"),
                "s-2": SimpleNamespace(auth_username="manager"),
                "s-3": SimpleNamespace(auth_username="someone-else"),
            },
            stored_sessions=["s-9"],
        )

        count = purge("manager", reason="user_deleted")

        token_manager.invalidate_token.assert_called_once_with("manager")
        self.assertEqual(count, 3)
        self.assertEqual(
            [sid for sid, _ in cleaned], ["s-1", "s-2", "s-9"]
        )
        self.assertTrue(all(reason == "user_deleted" for _, reason in cleaned))

    def test_purge_keeps_current_session_but_invalidates_token(self):
        third_session = "44444444-4444-4444-8444-444444444444"
        purge, cleaned, token_manager, _ = self._build(
            {
                ORIGIN_SESSION_ID: SimpleNamespace(auth_username="manager"),
                OTHER_SESSION_ID: SimpleNamespace(auth_username="manager"),
                third_session: SimpleNamespace(auth_username="manager"),
            }
        )

        count = purge(
            "manager",
            reason="password_changed",
            keep_session_id=ORIGIN_SESSION_ID,
        )

        token_manager.invalidate_token.assert_called_once_with("manager")
        self.assertEqual(count, 2)
        self.assertEqual(
            sorted(sid for sid, _ in cleaned),
            sorted([OTHER_SESSION_ID, third_session]),
        )

    def test_purge_clears_stored_session_list_when_requested(self):
        purge, _, _, _ = self._build(
            {"s-1": SimpleNamespace(auth_username="manager")}
        )

        purge(
            "manager",
            reason="admin_force_logout",
            clear_stored_session_list=True,
        )

        user_data = json.loads(self.user_file.read_text(encoding="utf-8"))
        self.assertEqual(user_data["session_ids"], [])

    def test_purge_survives_token_and_session_lookup_failures(self):
        purge, cleaned, token_manager, fake_main = self._build(
            {"s-1": SimpleNamespace(auth_username="manager")}
        )
        token_manager.invalidate_token.side_effect = RuntimeError("no token file")
        fake_main.auth_system.get_user_sessions.side_effect = RuntimeError(
            "user file gone"
        )

        count = purge("manager", reason="user_deleted")

        # token 吊销失败、用户文件读取失败都不能阻止会话清理。
        self.assertEqual(count, 1)
        self.assertEqual([sid for sid, _ in cleaned], ["s-1"])

    def test_purge_ignores_empty_username(self):
        purge, cleaned, token_manager, _ = self._build({})

        self.assertEqual(purge("", reason="user_deleted"), 0)
        token_manager.invalidate_token.assert_not_called()
        self.assertEqual(cleaned, [])


class LogoutTargetResolutionTests(unittest.TestCase):
    """退出应用/登出必须销毁调用者自己的会话，而不是被查看的会话。"""

    def setUp(self):
        self.namespace = _load_web_server_helper("_resolve_logout_target_sessions")
        self.victim_session = OTHER_SESSION_ID

    def _run(self, requested_session_id, *, cookie_token="admin-token",
             cookie_session_id="", origin_header="", token_owner="manager",
             verify_valid=True):
        token_manager = SimpleNamespace(
            resolve_username_by_token=mock.Mock(return_value=token_owner),
        )
        fake_main = SimpleNamespace(
            normalize_session_uuid=main_module.normalize_session_uuid,
            ADMIN_ORIGIN_SESSION_HEADER=main_module.ADMIN_ORIGIN_SESSION_HEADER,
            token_manager=token_manager,
            _verify_session_cookie_token=mock.Mock(return_value=verify_valid),
            request=SimpleNamespace(
                headers={main_module.ADMIN_ORIGIN_SESSION_HEADER: origin_header},
                cookies={
                    "auth_token": cookie_token,
                    "session_id": cookie_session_id,
                },
            ),
        )
        _MainHolder.current = fake_main
        return self.namespace["_resolve_logout_target_sessions"](
            requested_session_id
        )

    def _sessions(self, entries):
        self.namespace["web_sessions"].clear()
        for sid, owner, is_guest in entries:
            self.namespace["web_sessions"][sid] = SimpleNamespace(
                auth_username=owner, is_guest=is_guest
            )

    def test_normal_logout_destroys_the_requested_session(self):
        self._sessions([(ORIGIN_SESSION_ID, "manager", False)])

        targets, username, is_guest = self._run(
            ORIGIN_SESSION_ID, cookie_session_id=ORIGIN_SESSION_ID
        )

        self.assertEqual(targets, [ORIGIN_SESSION_ID])
        self.assertEqual(username, "manager")
        self.assertFalse(is_guest)

    def test_view_mode_logout_destroys_origin_session_not_viewed_session(self):
        """管理员查看他人会话时退出应用：只销毁来源会话。"""
        self._sessions(
            [
                (ORIGIN_SESSION_ID, "manager", False),
                (self.victim_session, VIEWED_SCHOOL_USERNAME, False),
            ]
        )

        targets, username, is_guest = self._run(
            self.victim_session,
            cookie_session_id=ORIGIN_SESSION_ID,
            origin_header=ORIGIN_SESSION_ID,
        )

        self.assertEqual(targets, [ORIGIN_SESSION_ID])
        self.assertNotIn(self.victim_session, targets)
        self.assertEqual(username, "manager")
        self.assertFalse(is_guest)

    def test_view_mode_logout_falls_back_to_viewer_live_sessions(self):
        """没有来源会话头/Cookie 时，退化为销毁查看者自己的活跃会话。"""
        self._sessions(
            [
                (ORIGIN_SESSION_ID, "manager", False),
                (self.victim_session, VIEWED_SCHOOL_USERNAME, False),
            ]
        )

        targets, username, _ = self._run(self.victim_session)

        self.assertEqual(targets, [ORIGIN_SESSION_ID])
        self.assertNotIn(self.victim_session, targets)
        self.assertEqual(username, "manager")

    def test_unverifiable_targets_destroy_nothing(self):
        self._sessions(
            [
                (ORIGIN_SESSION_ID, "manager", False),
                (self.victim_session, VIEWED_SCHOOL_USERNAME, False),
            ]
        )

        targets, username, _ = self._run(
            self.victim_session,
            cookie_session_id=ORIGIN_SESSION_ID,
            origin_header=ORIGIN_SESSION_ID,
            verify_valid=False,
        )

        self.assertEqual(targets, [])
        self.assertEqual(username, "manager")

    def test_guest_logout_destroys_guest_session(self):
        self._sessions([(self.victim_session, "guest", True)])

        targets, _, is_guest = self._run(
            self.victim_session, cookie_token="", token_owner=""
        )

        self.assertEqual(targets, [self.victim_session])
        self.assertTrue(is_guest)


class CredentialRouteContractTests(unittest.TestCase):
    """凭证作废必须挂到所有“必须立刻下线”的路由上。"""

    def _route_block(self, route):
        source = WEB_SERVER_PATH.read_text(encoding="utf-8")
        start = source.index(f'@app.route("{route}"')
        end = source.index("\n    @app.route", start + 1)
        return source[start:end]

    def test_delete_user_purges_credentials(self):
        block = self._route_block("/auth/admin/delete_user")
        self.assertIn("_purge_user_credentials(", block)
        # 用户文件删除前必须先取出登记的会话，否则磁盘上的会话文件会复活。
        self.assertLess(
            block.index("get_user_sessions("),
            block.index("delete_user(target_username)"),
        )
        self.assertIn('"user_deleted"', block)

    def test_force_reset_password_purges_credentials(self):
        block = self._route_block("/auth/admin/force_reset_password")
        self.assertIn("_purge_user_credentials(", block)
        self.assertIn('"admin_force_reset_password"', block)

    def test_force_logout_user_uses_shared_purge(self):
        block = self._route_block("/auth/admin/force_logout_user")
        self.assertIn("_purge_user_credentials(", block)
        self.assertIn("clear_stored_session_list=True", block)
        self.assertNotIn("_main().token_manager.invalidate_token(", block)

    def test_reset_password_purges_and_reissues_token_for_self_change(self):
        block = self._route_block("/auth/admin/reset_password")
        self.assertIn("_purge_user_credentials(", block)
        self.assertIn("keep_session_id=current_session_id", block)
        self.assertIn('"password_changed"', block)
        self.assertIn('"password_reset"', block)
        # 改自己的密码后必须给当前会话补发 token，否则当前页面会立刻掉线。
        self.assertIn("create_token(", block)
        self.assertIn('set_cookie(', block)

    def test_destroy_session_only_destroys_the_one_session(self):
        """销毁单个会话交给统一清理逻辑判断 token（只在最后一个会话时吊销）。"""
        block = self._route_block("/auth/admin/destroy_session")
        self.assertIn('cleanup_session(', block)
        self.assertIn('"admin_force_logout"', block)
        self.assertNotIn("_purge_user_credentials(", block)
        self.assertNotIn("invalidate_token(", block)

    def test_logout_routes_destroy_caller_session_only(self):
        """退出应用/登出必须解析"调用者自己的会话"，不能销毁被查看的会话。"""
        for route in ("/auth/logout", "/api/shutdown"):
            with self.subTest(route=route):
                block = self._route_block(route)
                self.assertIn("_resolve_logout_target_sessions(", block)
                self.assertNotIn("_main().token_manager.invalidate_token(", block)

    def test_all_sessions_handles_view_mode_without_origin_header(self):
        """查看态没有来源会话头时不能再用被查看会话 owner 校验查看者 token。"""
        block = self._route_block("/auth/admin/all_sessions")
        self.assertIn("admin_view_without_origin", block)
        self.assertIn("is_admin_view_fallback", block)
        self.assertIn(
            "if not is_guest and auth_username and not is_admin_view_fallback:",
            block,
        )

    def test_switch_session_accepts_resolved_view_identity(self):
        block = self._route_block("/auth/switch_session")
        self.assertIn("resolve_admin_view_identity(", block)
        self.assertIn("if view_identity:", block)
        self.assertIn("username = view_identity[\"username\"]", block)

    def test_cancellation_does_not_destroy_viewed_session(self):
        source = WEB_SERVER_PATH.read_text(encoding="utf-8")
        start = source.index("    def login_required(f):")
        end = source.index("        return decorated_function", start)
        block = source[start:end]
        self.assertIn("if not god_mode_admin:", block)
        self.assertIn("account_cancelled", block)

    def test_generic_restore_branch_uses_view_identity_fallback(self):
        source = WEB_SERVER_PATH.read_text(encoding="utf-8")
        start = source.index("    def api_call(method):")
        end = source.index("\n    @app.route", start)
        block = source[start:end]
        self.assertGreaterEqual(block.count("resolve_admin_view_identity("), 2)

    def test_create_session_uses_caller_identity_in_view_mode(self):
        """查看态下创建会话必须按查看者签发 token，不能把被查看用户的 token
        写进查看者 cookie（同时覆盖对方令牌文件）。"""
        block = self._route_block("/auth/user/create_session_persistence")
        self.assertIn('"resolve_username_by_token"', block)
        self.assertIn("auth_username = token_owner.strip()", block)
        self.assertIn("_verify_session_cookie_token(", block)


if __name__ == "__main__":
    unittest.main()
