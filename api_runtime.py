from __future__ import annotations

import base64
import bisect
import collections
import configparser
import copy
import csv
import datetime
import hashlib
import io
import json
import logging
import math
import os
import queue
import random
import sys
import threading
import time
import traceback
import uuid
import warnings


from main_runtime import _main
from route_diagnostics import build_route_failure_summary, detailed_route_failure_message, generic_route_failure_message, sanitize_diagnostic
from theme_background_state import background_files_locked


# ===================== 折返路径规划：路段缓存 =====================
# 折返点探测会针对「折返点 -> 打卡点」「打卡点 -> 最后一个打卡点」反复规划同一条腿，
# 同一任务的不同轮次、以及重复生成路线时都会命中，因此做进程内缓存。
DETOUR_LEG_CACHE_LIMIT = 256
_DETOUR_LEG_CACHE: "collections.OrderedDict[tuple, list]" = collections.OrderedDict()


def _detour_leg_cache_key(provider, start, end):
    return (
        str(provider or ""),
        round(float(start[0]), 6),
        round(float(start[1]), 6),
        round(float(end[0]), 6),
        round(float(end[1]), 6),
    )


def _detour_leg_cache_get(provider, start, end):
    key = _detour_leg_cache_key(provider, start, end)
    cached = _DETOUR_LEG_CACHE.get(key)
    if cached is None:
        return None
    _DETOUR_LEG_CACHE.move_to_end(key)
    return [tuple(point) for point in cached]


def _detour_leg_cache_put(provider, start, end, geometry):
    if not geometry or len(geometry) < 2:
        return
    key = _detour_leg_cache_key(provider, start, end)
    _DETOUR_LEG_CACHE[key] = [tuple(point) for point in geometry]
    _DETOUR_LEG_CACHE.move_to_end(key)
    while len(_DETOUR_LEG_CACHE) > DETOUR_LEG_CACHE_LIMIT:
        _DETOUR_LEG_CACHE.popitem(last=False)


def _detour_dedupe_points(points):
    """按顺序归一化并去重相邻重复点，保留原始顺序。

    兼容 ``(lng, lat)`` 元组/列表与 ``{"lng": .., "lat": ..}`` 字典。
    """
    deduped = []
    for point in points or []:
        try:
            if isinstance(point, dict):
                lng = float(point.get("lng", point.get("lon")))
                lat = float(point.get("lat"))
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                lng = float(point[0])
                lat = float(point[1])
            else:
                continue
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(lng) and math.isfinite(lat)):
            continue
        coord = (lng, lat)
        if not deduped or deduped[-1] != coord:
            deduped.append(coord)
    return deduped


# ===================== 多账号导入：表头识别与列推断 =====================
# 导入文件既可能是系统模板（标题行 + 序号/账号/密码/标记），也可能是用户自己
# 导出的表格（账号/密码/标记），甚至完全没有表头。列位置不固定，因此：
#   1. 先在第 1~N 行里找表头，按表头名称定位账号/密码/标记列（序号列忽略）；
#   2. 找不到表头就按数据内容推断“学号列”（最左且大多为 ≥4 位纯数字的列）；
#   3. 推断不出才退化为“第 1 列账号、第 2 列密码、第 3 列标记”。
# 绝不允许再出现把“序号/姓名”当成“账号/密码”的导入（真实事故：
# 1.ini..21.ini、序号.ini 与 password=姓名 的 JSON 记录）。
_IMPORT_ACCOUNT_HEADER_ALIASES = (
    "账号",
    "帐号",
    "用户名",
    "用户",
    "学号",
    "学生学号",
    "username",
    "user",
    "account",
    "studentid",
    "studentnum",
    "student_id",
    "student_num",
)
_IMPORT_PASSWORD_HEADER_ALIASES = (
    "密码",
    "初始密码",
    "登录密码",
    "password",
    "passwd",
    "pwd",
    "pass",
)
_IMPORT_TAG_HEADER_ALIASES = (
    "标记",
    "标签",
    "备注",
    "tag",
    "label",
    "note",
)
_IMPORT_HEADER_SCAN_ROWS = 10
_IMPORT_COLUMN_SAMPLE_ROWS = 30
_IMPORT_ACCOUNT_COLUMN_MIN_SCORE = 0.6
_IMPORT_ACCOUNT_COLUMN_MIN_UNIQUE_RATIO = 0.5
_IMPORT_TEMPLATE_FREE_ROWS = 100
# 下载模板优先直接返回仓库里的真实模板文件；该文件缺失时才按同版式生成。
_IMPORT_TEMPLATE_RELATIVE_PATH = os.path.join(
    "tests", "fixtures", "school_accounts_template.xlsx"
)


def _normalize_import_cell(value):
    # Excel 里以数字形式存储的学号可能被读成浮点（如 2024050101059.0），
    # 必须先还原成整数字符串，否则会被误判成非法学号。
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value if value is not None else "").strip()


def _import_header_cell_key(cell):
    return (
        _normalize_import_cell(cell)
        .lower()
        .replace(" ", "")
        .replace("\u3000", "")
    )


def _import_header_matches(cell, aliases):
    normalized = _import_header_cell_key(cell)
    if not normalized:
        return False
    return any(normalized == alias or alias in normalized for alias in aliases)


def _detect_import_header(rows):
    """找表头行，返回 (数据起始下标, 账号列, 密码列, 标记列)；无表头返回 None。

    采用“匹配度打分”而不是“第一行命中就算表头”：模板第 1 行往往只是
    标题（如“莲峰账号导入表”本身就含“账号”二字），按行取最高分可以让
    真正的 `序号/账号/密码/标记` 表头胜出，标题行不会被当成表头。
    """

    def _score_header_row(row):
        score = 0
        account_col = None
        password_col = None
        tag_col = None
        for col, cell in enumerate(row):
            normalized = _import_header_cell_key(cell)
            if not normalized:
                continue
            if account_col is None and normalized in _IMPORT_ACCOUNT_HEADER_ALIASES:
                account_col = col
                score += 3
                continue
            if (
                password_col is None
                and normalized in _IMPORT_PASSWORD_HEADER_ALIASES
            ):
                password_col = col
                score += 2
                continue
            if tag_col is None and normalized in _IMPORT_TAG_HEADER_ALIASES:
                tag_col = col
                score += 2
                continue
            if account_col is None and _import_header_matches(
                cell, _IMPORT_ACCOUNT_HEADER_ALIASES
            ):
                account_col = col
                score += 1
                continue
            if password_col is None and _import_header_matches(
                cell, _IMPORT_PASSWORD_HEADER_ALIASES
            ):
                password_col = col
                score += 1
                continue
            if tag_col is None and _import_header_matches(
                cell, _IMPORT_TAG_HEADER_ALIASES
            ):
                tag_col = col
                score += 1
        return score, account_col, password_col, tag_col

    best = None
    for row_index, row in enumerate(rows[:_IMPORT_HEADER_SCAN_ROWS]):
        if not row:
            continue
        score, account_col, password_col, tag_col = _score_header_row(row)
        # 至少要命中两种表头信息（或一个精确账号表头），且必须定位到账号列。
        if account_col is None or score < 2:
            continue
        if best is None or score > best[0]:
            best = (score, row_index, account_col, password_col, tag_col)

    if best is None:
        return None

    _, row_index, account_col, password_col, tag_col = best
    row = rows[row_index]
    if password_col is None and account_col + 1 < len(row):
        password_col = account_col + 1
    if (
        tag_col is None
        and password_col is not None
        and password_col + 1 < len(row)
    ):
        tag_col = password_col + 1
    return row_index + 1, account_col, password_col, tag_col


def _infer_import_columns(rows):
    """无表头时推断列位置：账号列取最左、且大多数值为 ≥4 位纯数字的列。"""
    sample = [row for row in rows[:_IMPORT_COLUMN_SAMPLE_ROWS] if row]
    if not sample:
        return 0, 1, 2

    width = max(len(row) for row in sample)
    for col_index in range(width):
        values = [
            _normalize_import_cell(row[col_index])
            for row in sample
            if col_index < len(row) and _normalize_import_cell(row[col_index])
        ]
        if not values:
            continue
        matches = sum(
            1 for value in values if _main().is_valid_school_username(value)
        )
        if not matches:
            continue
        score = matches / len(values)
        # 全部取值都是合法学号时允许重复（例如文件内重复行），否则要求
        # 账号列大体唯一，避免把重复出现的班级编号列误判成学号列。
        unique_ratio = len(set(values)) / len(values)
        if score >= _IMPORT_ACCOUNT_COLUMN_MIN_SCORE and (
            matches == len(values)
            or unique_ratio >= _IMPORT_ACCOUNT_COLUMN_MIN_UNIQUE_RATIO
        ):
            return col_index, col_index + 1, col_index + 2
    return 0, 1, 2


class Api:
    """此类的方法会暴露给WebView前端的JavaScript调用"""

    def __init__(self, args):
        self.args = args
        self.window = None
        self.path_gen_callbacks = {}

        self.run_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.user_dir = _main().SCHOOL_ACCOUNTS_DIR
        os.makedirs(self.user_dir, exist_ok=True)
        self.config_path = _main().CONFIG_JSON_ABS_PATH
        self.user_config_path = self.config_path

        self.api_client = _main().ApiClient(self)

        self._init_state_variables()

        # 初始化类级别的锁，防止并发初始化冲突
        if not hasattr(_main().Api, "_submission_init_lock"):
            _main().Api._submission_init_lock = threading.Lock()

        with _main().Api._submission_init_lock:
            # 1. 初始化类级别的队列和事件
            if (
                not hasattr(_main().Api, "_static_submission_queue")
                or _main().Api._static_submission_queue is None
            ):
                _main().Api._static_submission_queue = queue.Queue()

            if (
                not hasattr(_main().Api, "_static_submission_stop")
                or _main().Api._static_submission_stop is None
            ):
                _main().Api._static_submission_stop = threading.Event()

            if not hasattr(_main().Api, "_static_submission_threads"):
                _main().Api._static_submission_threads = []

            # 2. 将当前实例的属性指向类级别的对象 (实现复用)
            self._submission_queue = _main().Api._static_submission_queue
            self._submission_worker_stop = _main().Api._static_submission_stop
            self._submission_worker_threads = _main().Api._static_submission_threads

            # 3. 清理已死亡的线程
            _main().Api._static_submission_threads[:] = [
                t for t in _main().Api._static_submission_threads if t.is_alive()
            ]

            # 4. 检查并补充线程
            MAX_SUBMISSION_CONCURRENCY = 20
            current_threads = len(_main().Api._static_submission_threads)

            if current_threads < MAX_SUBMISSION_CONCURRENCY:
                threads_to_start = MAX_SUBMISSION_CONCURRENCY - current_threads
                # 仅在确实需要启动新线程时才记录日志，避免刷屏
                if threads_to_start > 0:
                    current_thread = threading.current_thread()
                    logging.info(
                        f"[线程创建] 正在从 Thread[{current_thread.name}, id={current_thread.ident}] 创建 {threads_to_start} 个 SubmissionWorker 线程"
                    )
                    logging.warning(
                        "[Eventlet 警告] SubmissionWorker 线程在 eventlet.monkey_patch 之后创建 - 注意：这些线程可能导致 greenlet 冲突！"
                    )
                    logging.warning(
                        "[Eventlet 警告] 这些 worker 线程使用 threading.Thread，与 eventlet 的基于 greenlet 的并发机制不兼容"
                    )
                    for i in range(threads_to_start):
                        t = threading.Thread(
                            # [修正] 使用静态方法，不绑定self
                            target=_main().Api._submission_worker_static,
                            args=(
                                _main().Api._static_submission_queue,
                                _main().Api._static_submission_stop,
                            ),  # [修正] 显式传递参数
                            name=f"SubmissionWorker-{len(Api._static_submission_threads) + 1}",
                            daemon=True,
                        )
                        t.start()
                        _main().Api._static_submission_threads.append(t)
                        logging.debug(f"[线程创建] SubmissionWorker 已启动: {t.name} (id={t.ident})")
                    logging.info(
                        f"已启动 {threads_to_start} 个数据提交工作线程 (全局池共 {len(Api._static_submission_threads)} 个)"
                    )

    def _init_state_variables(self):
        """初始化或重置应用的所有状态变量"""
        self.device_ua = ""
        self.is_offline_mode = False
        self.user_data = _main().UserData()
        self.all_run_data: list[_main().RunData] = []
        self.current_run_idx = -1
        self.stop_run_flag = threading.Event()
        self.stop_run_flag.set()
        self.single_execution_lock = threading.Lock()
        self._single_school_account_execution_token = None
        self.target_range_m = 30.0

        if not hasattr(self, "login_success"):
            self.login_success = False
        if not hasattr(self, "user_info"):
            self.user_info = None
        if not hasattr(self, "multi_login_lock") or self.multi_login_lock is None:
            self.multi_login_lock = threading.Semaphore(20)

        self.global_params = {
            "interval_ms": 3000,
            "interval_random_ms": 500,
            "speed_mps": 1.5,
            "speed_random_mps": 0.5,
            "location_random_m": 1.5,
            "task_gap_min_s": 600,
            "task_gap_max_s": 1800,
            "api_fallback_line": False,
            "api_retries": 2,
            "api_retry_delay_s": 0.5,
            "api_queue_interval_s": 0.1,
            "api_qps_limit": 4,
            "detour_max_overrun_ratio": 1.15,
            "ignore_task_time": True,
            "theme_base_color": "#7dd3fc",
            "theme_style": "default",
            "min_time_m": 20,
            "max_time_m": 30,
            "min_dist_m": 2000,
            "auto_attendance_enabled": False,
            "auto_attendance_stop_after_success": True,
            "auto_attendance_success_limit": 1,
            "auto_attendance_refresh_s": 15,
            "attendance_user_radius_m": 40,
            "amap_js_key": "",
        }

        self.server_attendance_radius_m = 0.0
        self.last_radius_fetch_time = 0

        # 旧的单账号刷新线程机制，保留以兼容旧代码
        self.auto_refresh_thread: threading.Thread | None = None
        self.stop_auto_refresh = threading.Event()
        self.stop_auto_refresh.set()

        # 旧的多账号刷新线程机制，保留以兼容旧代码
        self.multi_auto_refresh_thread: threading.Thread | None = None
        self.stop_multi_auto_refresh = threading.Event()
        self.stop_multi_auto_refresh.set()

        # 统一的账号刷新线程管理字典
        # 键: 账号标识符（字符串格式，例如 "12345"），值: 线程对象
        # 这个字典用于追踪每个账号的独立刷新线程，避免重复创建
        self.account_refresh_threads: dict[str, threading.Thread] = {}

        # 线程锁，用于保护 account_refresh_threads 字典的并发访问
        # 在多线程环境下，对字典的读写操作需要加锁以确保线程安全
        self.threads_lock = threading.Lock()

        # 多账号执行门闩：同一账号同一时间只允许一个业务执行或刷新任务占用会话。
        self.multi_execution_lock = threading.RLock()
        self.multi_active_executions: set[str] = set()

        # 多账号监控线程的停止事件
        # 用于优雅地停止多账号监控线程
        self.stop_account_monitor = threading.Event()
        self.stop_account_monitor.set()

        # 多账号监控线程对象
        # 该线程负责定期检查所有账号，确保每个启用自动签到的账号都有刷新线程
        self.account_monitor_thread: threading.Thread | None = None

        self.params = self.global_params.copy()

        self._first_center_done = False

        self.is_multi_account_mode = False
        if hasattr(self, "accounts"):
            for acc in self.accounts.values():
                if acc.worker_thread and acc.worker_thread.is_alive():
                    acc.stop_event.set()
        self.accounts: dict[str, _main().AccountSession] = {}
        self.multi_run_stop_flag = threading.Event()
        self.multi_run_stop_flag.set()

        self._load_tasks_lock = threading.RLock()
        self._load_tasks_inflight = False
        self.multi_run_only_incomplete = True
        # 管理员在欠费警告弹窗选择“此次不计费”后置 True：
        # 本次执行跳过可用次数扣减与账单生成，直到停止/下一次启动重置。
        self.waive_charge_active = False

    def _get_session_stop_event(self):
        stop_event = getattr(self, "_session_stop_event", None)
        if stop_event is None:
            stop_event = threading.Event()
            self._session_stop_event = stop_event
        return stop_event

    def shutdown_session_runtime(self, reason="cleanup", timeout=3.0):
        if getattr(self, "_session_shutdown_requested", False):
            return

        self._session_shutdown_requested = True
        self._get_session_stop_event().set()

        for event_name in (
            "stop_run_flag",
            "multi_run_stop_flag",
            "stop_auto_refresh",
            "stop_multi_auto_refresh",
            "stop_account_monitor",
        ):
            event = getattr(self, event_name, None)
            if event is not None:
                event.set()
        self.waive_charge_active = False

        accounts = list(getattr(self, "accounts", {}).values())
        for account in accounts:
            event = getattr(account, "stop_event", None)
            if event is not None:
                event.set()

        threads_lock = getattr(self, "threads_lock", None)
        refresh_threads = list(
            getattr(self, "account_refresh_threads", {}).values()
        )
        if threads_lock is not None:
            with threads_lock:
                getattr(self, "account_refresh_threads", {}).clear()

        threads = list(refresh_threads)
        for attribute_name in (
            "auto_refresh_thread",
            "multi_auto_refresh_thread",
            "account_monitor_thread",
        ):
            thread = getattr(self, attribute_name, None)
            if thread is not None:
                threads.append(thread)

        for account in accounts:
            thread = getattr(account, "worker_thread", None)
            if thread is not None:
                threads.append(thread)

        unique_threads = {id(thread): thread for thread in threads}
        alive_before = [
            thread for thread in unique_threads.values() if thread.is_alive()
        ]
        logging.info(
            "[内存诊断] 会话销毁开始: reason=%s, accounts=%d, "
            "tracked_threads=%d, alive_tracked_threads=%d, process_threads=%d",
            reason,
            len(accounts),
            len(unique_threads),
            len(alive_before),
            threading.active_count(),
        )
        deadline = time.monotonic() + max(float(timeout), 0.0)
        for thread in unique_threads.values():
            if not thread.is_alive():
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logging.warning(
                    "[会话运行时] 线程停止超时: reason=%s, thread=%s",
                    reason,
                    getattr(thread, "name", "unknown"),
                )
                break
            thread.join(remaining)

        session = getattr(getattr(self, "api_client", None), "session", None)
        if session is not None and hasattr(session, "close"):
            session.close()
            logging.info(
                "[内存诊断] requests.Session 已关闭: reason=%s",
                reason,
            )

        alive_after = [
            thread for thread in unique_threads.values() if thread.is_alive()
        ]
        if alive_after:
            logging.warning(
                "[内存诊断] 会话销毁后仍有线程存活: reason=%s, threads=%s",
                reason,
                [getattr(thread, "name", "unknown") for thread in alive_after],
            )

        logging.info(
            "[内存诊断] 会话销毁完成: reason=%s, tracked_threads=%d, "
            "alive_before=%d, alive_after=%d, process_threads=%d",
            reason,
            len(unique_threads),
            len(alive_before),
            len(alive_after),
            threading.active_count(),
        )

    def _safe_socketio_emit(self, event_name, data, room=None):
        """
        安全的 socketio emit 方法，带有详细的线程和 greenlet 诊断日志
        用于从多线程环境中安全地发送 SocketIO 事件
        """
        if not _main().socketio:
            logging.debug(f"[SocketIO] SocketIO not available, skipping emit: {event_name}")
            return False
        
        current_thread = threading.current_thread()
        thread_info = f"Thread[name={current_thread.name}, id={current_thread.ident}]"
        
        # 获取 greenlet 信息（如果可用）
        try:
            import greenlet
            current_greenlet = _main().greenlet.getcurrent()
            greenlet_info = f"Greenlet[id={id(current_greenlet)}, parent={id(current_greenlet.parent) if current_greenlet.parent else 'None'}]"
        except:
            greenlet_info = "Greenlet info unavailable"
        
        logging.debug(f"[SocketIO Emit] Event: {event_name}, From: {thread_info}, {greenlet_info}")
        
        try:
            if room:
                _main().socketio.emit(event_name, data, room=room)
            else:
                _main().socketio.emit(event_name, data)
            logging.debug(f"[SocketIO Emit] Success: {event_name}")
            return True
        except Exception as e:
            logging.error(f"[SocketIO Emit] Failed: {event_name} from {thread_info}")
            logging.error(f"[SocketIO Emit] Error type: {type(e).__name__}")
            logging.error(f"[SocketIO Emit] Error message: {e}")
            logging.error(f"[SocketIO Emit] Traceback:\n{traceback.format_exc()}")
            return False

    def set_multi_run_only_incomplete(self, flag: bool):
        """
        设置多账号模式下“仅执行未完成”的全局开关。

        切换后必须立刻用已缓存的任务列表重算每个账号的统计
        （total/completed/not_started/executable/expired），否则列表里的任务
        状态文本会停留在旧规则的结果上（真实缺陷：勾选/取消勾选后
        「可跑 / 过期 / 未开始」这些数字不变）。
        """
        try:
            self.multi_run_only_incomplete = bool(flag)
            for acc in list(getattr(self, "accounts", {}).values()):
                self._refresh_multi_account_summary_for_mode(acc)
            self._update_multi_global_buttons()
            return {
                "success": True,
                "run_only_incomplete": self.multi_run_only_incomplete,
                "accounts": self.multi_get_all_accounts_status().get(
                    "accounts", []
                ),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def log_and_notify_frontend(self, message, *, frontend_message=None, diagnostic_id=None):
        """记录服务器日志，并向会话前端发送可独立选择的文案。"""
        session_id = getattr(self, "_web_session_id", None)
        safe_message = _main()._redact_sensitive_log_value(message)
        logging.info(safe_message)
        public_message = safe_message if frontend_message is None else _main()._redact_sensitive_log_value(frontend_message)
        if session_id and _main().socketio:
            try:
                # 添加线程诊断日志
                current_thread = threading.current_thread()
                thread_info = f"Thread[name={current_thread.name}, id={current_thread.ident}]"
                logging.debug(f"[SocketIO Emit] Attempting emit from {thread_info}")
                
                payload = {"msg": str(public_message)}
                if diagnostic_id:
                    payload["diagnostic_id"] = str(diagnostic_id)
                _main().socketio.emit("log_message", payload, room=session_id)
                logging.debug(f"[SocketIO Emit] Success from {thread_info}")
            except Exception as e:
                current_thread = threading.current_thread()
                logging.error(
                    f"WebSocket emit log failed for session {session_id[:8]} from Thread[{current_thread.name}]: {e}"
                )
                logging.error(f"Error details: {type(e).__name__}: {e}")
                logging.error(f"Traceback: {traceback.format_exc()}")
        else:
            logging.debug(
                f"[Log Emission Skipped] Session ID or SocketIO missing. Message: {message}"
            )

    def js_log(self, level, message):
        """接收并记录来自JavaScript的日志"""
        level = level.upper()
        if level == "INFO":
            logging.info(f"{message}")
        elif level == "DEBUG":
            logging.debug(f"{message}")
        elif level == "WARNING":
            logging.warning(f"{message}")
        elif level == "ERROR":
            logging.error(f"{message}")
        else:
            logging.info(f"[JS-{level}] {message}")

    @staticmethod
    def _robust_decode(raw: bytes) -> str:
        """尽可能兼容所有编码的解码函数"""
        if _main().chardet:
            det = _main().chardet.detect(raw) or {}
            enc = det.get("encoding")
            if enc:
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    pass

        for enc in ("utf-8", "gbk", "big5", "shift_jis", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue

        return raw.decode("utf-8", errors="replace")

    def normalize_chinese_config_to_english(self, path: str) -> None:
        """
        将可能包含中文分区/键名的 INI 配置文件，转换为标准英文分区与键名，并统一写回 UTF-8。
        """
        if not os.path.exists(path):
            return

        with open(path, "rb") as f:
            raw = f.read()
        text = self._robust_decode(raw)

        cfg_existing = configparser.ConfigParser(
            delimiters=("=", ":"),
            comment_prefixes=("#"),
            strict=False,
            interpolation=None,
        )
        try:
            cfg_existing.read_string(text)
        except Exception:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return

        if cfg_existing.has_section("Config") or cfg_existing.has_section("System"):
            return
        cfg_cn = configparser.ConfigParser(
            delimiters=("=", ":"),
            comment_prefixes=("#"),
            strict=False,
            interpolation=None,
        )
        try:
            cfg_cn.read_string(text)
        except Exception:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return

        if not (cfg_cn.has_section("配置") or cfg_cn.has_section("系统")):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return

        config_key_map = {
            "间隔时间": "interval_ms",
            "间隔时间随机": "interval_random_ms",
            "速度": "speed_mps",
            "速度随机": "speed_random_mps",
            "定位随机": "location_random_m",
            "任务间速度": "task_interval_speed",
            "用户名": "Username",
            "密码": "Password",
            "有效": "Enabled",
            "未完成次数": "PendingCount",
            "未完成次数上次检查时间": "LastPendingCheckTs",
            "下次最早开始时间": "NextEarliestStartTs",
        }
        system_key_map = {
            "cookie": "AuthorizationCookie",
            "UA": "UA",
        }

        cfg_en = configparser.ConfigParser(
            delimiters=("=", ":"),
            comment_prefixes=("#"),
            strict=False,
            interpolation=None,
        )
        cfg_en.add_section("Config")
        cfg_en.add_section("System")

        valid_config_keys = set(self.global_params.keys())
        valid_config_keys.add("Username")
        valid_config_keys.add("Password")

        if cfg_cn.has_section("配置"):
            for k, v in cfg_cn.items("配置"):
                k_en = config_key_map.get(k, k)
                if k_en in valid_config_keys:
                    cfg_en.set("Config", k_en, v)

        if cfg_cn.has_section("系统"):
            for k, v in cfg_cn.items("系统"):
                k_en = system_key_map.get(k, k)
                if (
                    k_en == "UA"
                    and isinstance(v, str)
                    and v.lower().startswith("user-agent:")
                ):
                    v = v.split(":", 1)[1].strip()
                if k_en in ["AuthorizationCookie", "UA"]:
                    cfg_en.set("System", k_en, v)

        if cfg_cn.has_section("stats"):
            # 添加 [stats] 节到新配置
            cfg_en.add_section("stats")
            # 复制所有 stats 节中的配置项
            for key, value in cfg_cn.items("stats"):
                cfg_en.set("stats", key, value)
            logging.debug(
                f"normalize_chinese_config_to_english 保留了 [stats] 节 - 文件: {path}"
            )

        try:
            backup_path = f"{path}.bak"
            with open(backup_path, "wb") as bf:
                bf.write(raw)
        except Exception:
            pass

        with open(path, "w", encoding="utf-8") as f:
            cfg_en.write(f)

    def _get_user_accounts_file(self, auth_username):
        """
        获取指定认证用户的 school_accounts 存储文件路径。
        """
        user_accounts_dir = os.path.join(_main().SCHOOL_ACCOUNTS_DIR, "user_accounts")
        storage_key = _main()._auth_username_storage_key(auth_username)
        return os.path.join(user_accounts_dir, f"{storage_key}.json")

    def _load_school_account_stats_from_ini(self, school_username):
        """
        从 INI 文件读取指定学校账号的统计数据（overdue_count 和 completed_count）。
        """
        # 直接构建 INI 文件路径，指向 school_accounts 目录
        ini_file = os.path.join(self.user_dir, f"{school_username}.ini")

        # 准备默认返回值
        default_stats = {
            "overdue_count": 0,      # 默认欠费次数为 0（无欠费）
            "completed_count": 0     # 默认已完成任务数为 0（新账号）
        }

        # 检查 INI 文件是否存在
        if not os.path.exists(ini_file):
            logging.debug(
                f"[统计数据] 配置文件不存在，返回默认值: {school_username}"
            )
            return default_stats

        try:
            # 创建 RawConfigParser 对象用于读取 INI 文件
            # 使用 RawConfigParser 避免插值错误，并保持与 _save_config 一致
            config = configparser.RawConfigParser()
            config.optionxform = str

            # 读取 INI 文件
            config.read(ini_file, encoding='utf-8')

            # 从 [stats] 配置节读取统计数据
            overdue_count = config.getint('stats', 'overdue_count', fallback=0)
            completed_count = config.getint(
                'stats', 'completed_count', fallback=0)

            # 记录成功读取的日志（调试级别）
            logging.debug(
                f"[统计数据] 成功读取 INI 文件: {school_username}, "
                f"overdue_count={overdue_count}, completed_count={completed_count}"
            )

            # 返回读取到的统计数据
            return {
                "overdue_count": overdue_count,
                "completed_count": completed_count
            }

        except Exception as e:
            logging.error(
                f"[统计数据] 读取 INI 文件失败: {school_username}, 错误: {e}",
                exc_info=True
            )
            return default_stats

    def _save_school_account_stats_to_ini(self, school_username, overdue_count, completed_count):
        """
        将学校账号的统计数据保存到 INI 文件（合并模式）。
        """
        if not _main().is_valid_school_username(school_username):
            logging.warning(
                "[统计数据] 拒绝为非法学号写入统计 INI: %r"
                "（学号必须是至少4位纯数字）",
                school_username,
            )
            return False

        # 获取该学校账号对应的 INI 文件路径 (使用 self.user_dir，即 school_accounts)
        ini_file = os.path.join(self.user_dir, f"{school_username}.ini")

        try:
            # 创建 RawConfigParser 对象
            config = configparser.RawConfigParser()
            config.optionxform = str  # 保持键名大小写敏感

            # 如果文件存在，先读取现有内容以进行合并
            if os.path.exists(ini_file):
                try:
                    # 使用 normalize_chinese_config_to_english 确保格式兼容性
                    # 虽然这通常在加载时做，但写入前标准化一下更安全
                    self.normalize_chinese_config_to_english(ini_file)
                    config.read(ini_file, encoding='utf-8')
                except Exception as read_e:
                    logging.warning(f"[统计数据] 读取现有配置文件出错 (将覆盖): {read_e}")

            # 确保 [stats] 配置节存在
            if not config.has_section('stats'):
                config.add_section('stats')

            # 设置统计数据
            config.set('stats', 'overdue_count', str(overdue_count))
            config.set('stats', 'completed_count', str(completed_count))

            # 将配置写回文件
            # encoding='utf-8'：使用 UTF-8 编码
            with open(ini_file, 'w', encoding='utf-8') as f:
                config.write(f)

            # 记录成功保存的日志
            logging.debug(
                f"[统计数据] 成功合并保存 INI 文件: {school_username}, "
                f"overdue_count={overdue_count}, completed_count={completed_count}"
            )

            return True

        except Exception as e:
            logging.error(
                f"[统计数据] 保存 INI 文件失败: {school_username}, 错误: {e}",
                exc_info=True
            )
            return False

    def _save_school_account_password_to_ini(self, school_username, password, ua=None):
        """
        将学校账号的密码和UA信息保存到 INI 文件（作为备份）。

        功能说明：
            将学校账号登录成功后的密码和 User-Agent 保存到对应的 INI 文件中。
            采用读取-修改-写入模式，确保不丢失文件中原有的其他配置（如统计数据）。

        参数:
            school_username (str): 学校账号用户名
            password (str): 账号密码
            ua (str): User-Agent（可选）

        返回:
            bool: 保存成功返回 True，失败返回 False
        """
        if not _main().is_valid_school_username(school_username):
            logging.warning(
                "[密码备份] 拒绝为非法学号写入 INI: %r"
                "（学号必须是至少4位纯数字）",
                school_username,
            )
            return False

        # 获取该学校账号对应的 INI 文件路径
        ini_file = os.path.join(self.user_dir, f"{school_username}.ini")

        try:
            # 创建 RawConfigParser 对象
            config = configparser.RawConfigParser()
            config.optionxform = str  # 保持键名大小写敏感

            # 如果文件存在，先读取现有内容以进行合并
            if os.path.exists(ini_file):
                try:
                    config.read(ini_file, encoding='utf-8')
                except Exception as read_e:
                    logging.warning(f"[密码备份] 读取现有配置文件出错 (将覆盖): {read_e}")

            # 确保 [Config] 和 [System] 配置节存在
            if not config.has_section('Config'):
                config.add_section('Config')
            if not config.has_section('System'):
                config.add_section('System')

            # 设置密码信息（仅写入小写格式，与读取逻辑保持一致）
            if password:
                config.set('Config', 'password', password)
                logging.debug(f"[密码备份] 已在 INI 文件中保存密码: {school_username}")

            # 设置 UA 信息（仅写入小写格式，与读取逻辑保持一致）
            if ua:
                config.set('System', 'ua', ua)
                logging.debug(f"[密码备份] 已在 INI 文件中保存UA: {school_username}")

            # 将配置写回文件
            with open(ini_file, 'w', encoding='utf-8') as f:
                config.write(f)

            # 记录成功保存的日志
            logging.info(
                f"[密码备份] 成功将密码和UA备份到 INI 文件: {school_username}"
            )

            return True

        except Exception as e:
            logging.error(
                f"[密码备份] 保存密码到 INI 文件失败: {school_username}, 错误: {e}",
                exc_info=True
            )
            return False

    def _load_user_school_accounts(self, auth_username):
        """
        加载指定认证用户的所有 school_account 账户密码和UA。

        参数:
            auth_username: 认证用户名

        返回:
            字典，格式为 {school_username: {"password": "xxx", "ua": "xxx", "overdue_count": 0}, ...}
            或旧格式 {school_username: password, ...}（向后兼容）
        """
        if not auth_username or auth_username == "guest":
            return {}

        file_path = self._get_user_accounts_file(auth_username)
        data = {}

        # 尝试加载当前用户的JSON文件（如果存在）
        if os.path.exists(file_path):
            try:
                # 步骤1：从 JSON 文件读取账号密码和 UA 信息
                # JSON 文件只包含账号基本信息，不包含统计数据
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logging.error(f"读取用户 {auth_username} 的 JSON 文件失败: {e}")
                data = {}
        else:
            logging.debug(f"用户 {auth_username} 的 JSON 文件不存在，初始化为空字典")
            data = {}

        if not isinstance(data, dict):
            logging.warning(
                "用户 %s 的 school_accounts 不是字典格式，已忽略", auth_username
            )
            data = {}
        invalid_keys = [
            key
            for key in list(data)
            if not _main().is_valid_school_username(key)
        ]
        for key in invalid_keys:
            data.pop(key, None)
        if invalid_keys:
            logging.warning(
                "用户 %s 的 school_accounts 已忽略 %d 个非法学号"
                "（学号必须是至少4位纯数字）: %s",
                auth_username,
                len(invalid_keys),
                invalid_keys[:20],
            )

        try:

            # 步骤2：处理并标准化每个账号的数据格式
            # 同时从对应的 INI 文件读取统计数据（overdue_count 和 completed_count）
            for school_username, account_info in data.items():
                # 如果是新格式（字典类型），处理并加载统计数据
                if isinstance(account_info, dict):
                    # 从 INI 文件加载该学校账号的统计数据
                    # _load_school_account_stats_from_ini() 返回：
                    # {"overdue_count": int, "completed_count": int}
                    stats = self._load_school_account_stats_from_ini(
                        school_username)

                    # 将从 INI 读取的统计数据合并到账号信息中
                    # 这样返回的数据结构就包含了完整信息：密码、UA、欠费次数、完成次数
                    account_info["overdue_count"] = stats["overdue_count"]
                    account_info["completed_count"] = stats["completed_count"]

                # 如果是旧格式（字符串密码），转换为新格式并加载统计数据
                elif isinstance(account_info, str):
                    # 从 INI 文件加载统计数据
                    stats = self._load_school_account_stats_from_ini(
                        school_username)

                    # 转换为新格式：将字符串密码转换为字典结构
                    data[school_username] = {
                        "password": account_info,    # 保留原密码
                        "ua": None,                  # UA 默认为 None
                        # 从 INI 读取
                        "overdue_count": stats["overdue_count"],
                        # 从 INI 读取
                        "completed_count": stats["completed_count"]
                    }

            # 记录加载成功的日志
            if data:
                logging.debug(
                    f"成功加载用户 {auth_username} 的 school_accounts，共 {len(data)} 个账户 "
                    f"(从 JSON 加载密码和 UA，从 INI 加载统计数据)"
                )

            # 如果当前用户具有管理权限，则遍历所有用户的 user_accounts
            # 将其它用户的 school_accounts 汇总（排除 password 为空的数据）并去重
            try:
                # 使用全局 auth_system 进行权限检查，确保管理员可聚合所有用户账号
                if _main().auth_system.check_permission(auth_username, "manage_users"):
                    # 使用已有 data 作为基准，优先保留当前用户的数据
                    aggregated = dict(data)

                    # 1. 遍历所有用户的 user_accounts JSON 文件
                    user_accounts_dir = os.path.join(
                        _main().SCHOOL_ACCOUNTS_DIR, "user_accounts")
                    if os.path.isdir(user_accounts_dir):
                        for fname in os.listdir(user_accounts_dir):
                            if not fname.endswith('.json'):
                                continue
                            fpath = os.path.join(user_accounts_dir, fname)
                            # 跳过无法读取的文件
                            try:
                                with open(fpath, 'r', encoding='utf-8') as uf:
                                    other = json.load(uf)
                            except Exception:
                                logging.debug(
                                    f"跳过无法读取的 user_accounts 文件: {fpath}")
                                continue

                            # 合并 other 中的账号
                            for school_username, account_info in (other or {}).items():
                                if not _main().is_valid_school_username(
                                    school_username
                                ):
                                    continue
                                # 标准化为字典格式以便检查 password
                                if isinstance(account_info, dict):
                                    pwd = account_info.get('password', '')
                                else:
                                    pwd = account_info or ''

                                # 排除 password 为空或 None 的记录
                                if pwd is None or str(pwd).strip() == "":
                                    continue

                                # 如果已存在于 aggregated 中，跳过以避免覆盖当前用户已有数据
                                if school_username in aggregated:
                                    continue

                                # 将记录转换为新格式并加载统计数据
                                if isinstance(account_info, dict):
                                    entry = {
                                        'password': account_info.get('password', ''),
                                        'ua': account_info.get('ua') if 'ua' in account_info else None,
                                    }
                                else:
                                    entry = {
                                        'password': account_info, 'ua': None}

                                stats = self._load_school_account_stats_from_ini(
                                    school_username)
                                entry['overdue_count'] = stats.get(
                                    'overdue_count', 0)
                                entry['completed_count'] = stats.get(
                                    'completed_count', 0)

                                aggregated[school_username] = entry

                    # 2. 遍历 school_accounts 根目录下的旧版 INI 文件
                    if os.path.isdir(_main().SCHOOL_ACCOUNTS_DIR):
                        for fname in os.listdir(_main().SCHOOL_ACCOUNTS_DIR):
                            if not fname.endswith('.ini'):
                                continue

                            # 从文件名提取学校账号用户名（去掉 .ini 后缀）
                            school_username = fname[:-4]

                            if not _main().is_valid_school_username(
                                school_username
                            ):
                                continue

                            # 如果已存在于 aggregated 中，跳过以避免覆盖
                            if school_username in aggregated:
                                continue

                            ini_path = os.path.join(_main().SCHOOL_ACCOUNTS_DIR, fname)
                            try:
                                # 从旧版 INI 文件读取账号密码
                                config = configparser.ConfigParser(strict=False)
                                config.read(ini_path, encoding='utf-8')

                                # 从 [Config] 或 [System] 节读取密码和UA
                                password = None
                                ua = None

                                if config.has_section('Config'):
                                    if config.has_option('Config', 'password'):
                                        password = config.get(
                                            'Config', 'password')
                                    elif config.has_option('Config', 'Password'):
                                        password = config.get(
                                            'Config', 'Password')

                                if config.has_section('System'):
                                    if config.has_option('System', 'ua'):
                                        ua = config.get('System', 'ua')
                                    elif config.has_option('System', 'UA'):
                                        ua = config.get('System', 'UA')

                                # 排除 password 为空或 None 的记录
                                if password is None or str(password).strip() == "":
                                    continue

                                # 加载统计数据
                                stats = self._load_school_account_stats_from_ini(
                                    school_username)

                                # 添加到聚合结果中
                                aggregated[school_username] = {
                                    'password': password,
                                    'ua': ua,
                                    'overdue_count': stats.get('overdue_count', 0),
                                    'completed_count': stats.get('completed_count', 0)
                                }

                                logging.debug(f"从旧版INI加载账号: {school_username}")
                            except Exception as e:
                                logging.debug(
                                    f"跳过无法读取的 INI 文件: {ini_path}, 错误: {e}")
                                continue

                    # 替换为汇总后的结果
                    data = aggregated
                    logging.debug(
                        f"管理员权限聚合完成，总共 {len(data)} 个账户（包含JSON和INI格式）")
            except Exception as e:
                logging.debug(f"管理员合并 user_accounts 失败: {e}")

            return data
        except Exception as e:
            logging.error(
                f"加载用户 {auth_username} 的 school_accounts 失败: {e}", exc_info=True
            )
            return {}

    def _save_user_school_accounts(self, auth_username, accounts_dict):
        """
        保存指定认证用户的所有 school_account 账户密码和UA。

        功能说明：
            将账号的密码和 UA 信息保存到 JSON 文件。
            同时将统计数据（overdue_count 和 completed_count）保存到各自的 INI 文件。
            实现了数据分离存储：敏感信息（密码）在 JSON，统计数据在 INI。

        参数:
            auth_username: 认证用户名
            accounts_dict: 字典，格式为 {school_username: {"password": "xxx", "ua": "xxx", 
                          "overdue_count": 0, "completed_count": 0}, ...}

        实现逻辑：
            1. 遍历所有账号，提取统计数据
            2. 将统计数据保存到各账号对应的 INI 文件
            3. 从字典中移除统计数据字段
            4. 将剩余的账号信息（密码和 UA）保存到 JSON 文件
        """
        if not auth_username or auth_username == "guest":
            logging.debug("游客用户不保存 school_accounts")
            return

        file_path = self._get_user_accounts_file(auth_username)

        try:
            # 步骤1：创建一个新的字典用于保存到 JSON
            # 这个字典只包含密码和 UA 信息，不包含统计数据
            json_data = {}
            invalid_usernames = []

            # 步骤2：遍历所有账号，分离统计数据和账号信息
            for school_username, account_info in accounts_dict.items():
                # 非法学号（如名单里的“序号/1..21”）不写回 JSON/INI，
                # 直接丢弃，防止坏数据在每次保存时被续命。
                if not _main().is_valid_school_username(school_username):
                    invalid_usernames.append(school_username)
                    continue
                # 如果账号信息是字典格式（新格式）
                if isinstance(account_info, dict):
                    # 提取统计数据（如果存在）
                    overdue_count = account_info.get("overdue_count", 0)
                    completed_count = account_info.get("completed_count", 0)

                    # 将统计数据保存到该账号对应的 INI 文件
                    # 这样统计数据就与密码信息分离存储了
                    self._save_school_account_stats_to_ini(
                        school_username,
                        overdue_count,
                        completed_count
                    )

                    # 创建一个只包含密码和 UA 的字典，用于保存到 JSON
                    # 注意：这里不包含 overdue_count 和 completed_count
                    json_data[school_username] = {
                        "password": account_info.get("password", ""),
                        "ua": account_info.get("ua", "")
                    }
                else:
                    # 如果是旧格式（字符串密码），直接保存
                    # 旧格式不包含统计数据，所以不需要特殊处理
                    json_data[school_username] = account_info

            if invalid_usernames:
                logging.warning(
                    "[账号保存] 用户 %s 的账号列表中有 %d 个非法学号已丢弃: %s",
                    auth_username,
                    len(invalid_usernames),
                    invalid_usernames[:20],
                )

            # 步骤3：将处理后的数据（只包含密码和 UA）保存到 JSON 文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)

            # 记录成功保存的日志
            logging.debug(
                f"成功保存用户 {auth_username} 的 school_accounts，共 {len(json_data)} 个账户 "
                f"(密码和 UA 保存到 JSON，统计数据保存到各账号的 INI 文件)"
            )
        except Exception as e:
            logging.error(
                f"保存用户 {auth_username} 的 school_accounts 失败: {e}", exc_info=True
            )

    def _update_school_account_password(
        self, auth_username, school_username, password, ua=None, login_verified=False
    ):
        """
        更新指定认证用户的某个 school_account 的密码和UA。

        参数:
            auth_username: 认证用户名
            school_username: 学校账户用户名
            password: 密码
            ua: User-Agent（可选）
            login_verified: 是否已验证登录成功（True 时才会覆盖现有密码）
        """
        if not auth_username or auth_username == "guest":
            return

        accounts = self._load_user_school_accounts(auth_username)

        existing_data = accounts.get(school_username)
        if existing_data:
            if isinstance(existing_data, str):
                existing_data = {"password": existing_data, "ua": ""}

            if not login_verified:
                logging.debug(
                    f"school_account {school_username} 已存在，且未验证登录成功，跳过更新"
                )
                return

        # ========== 更新密码时保留统计数据 ==========
        # 问题：直接赋值 accounts[school_username] = {...} 会丢失 overdue_count 和 completed_count
        # 解决：先获取现有数据，更新密码和UA，保留统计数据
        if school_username in accounts:
            # 账号已存在，更新密码和UA，保留其他字段
            accounts[school_username]["password"] = password
            accounts[school_username]["ua"] = ua if ua else ""
            logging.debug(
                f"更新 {school_username} 密码和UA，保留统计数据: "
                f"overdue_count={accounts[school_username].get('overdue_count', 'N/A')}, "
                f"completed_count={accounts[school_username].get('completed_count', 'N/A')}"
            )
        else:
            # 账号不存在，创建新条目（统计数据默认为0）
            accounts[school_username] = {
                "password": password,
                "ua": ua if ua else "",
                "overdue_count": 0,
                "completed_count": 0
            }
            logging.debug(
                f"创建新账号 {school_username}，统计数据初始化为0"
            )

        self._save_user_school_accounts(auth_username, accounts)
        logging.info(
            f"已更新用户 {auth_username} 的 school_account {school_username} 的密码和UA"
        )

    def _get_school_account_password(self, auth_username, school_username):
        """
        获取指定认证用户的某个 school_account 的密码。

        参数:
            auth_username: 认证用户名
            school_username: 学校账户用户名

        返回:
            密码字符串，如果不存在则返回 None
        """
        if not auth_username or auth_username == "guest":
            return None

        accounts = self._load_user_school_accounts(auth_username)
        account_data = accounts.get(school_username)

        if isinstance(account_data, str):
            return account_data
        elif isinstance(account_data, dict):
            return account_data.get("password")
        return None

    def _get_school_account_ua(self, auth_username, school_username):
        """
        获取指定认证用户的某个 school_account 的UA。

        参数:
            auth_username: 认证用户名
            school_username: 学校账户用户名

        返回:
            UA字符串，如果不存在则返回 None
        """
        if not auth_username or auth_username == "guest":
            return None

        accounts = self._load_user_school_accounts(auth_username)
        account_data = accounts.get(school_username)

        if isinstance(account_data, dict):
            return account_data.get("ua", "")
        return None

    def _get_auth_user_and_check_admin(self):
        """
        获取当前认证用户名并检查其是否为管理员。

        返回:
            元组 (auth_username, is_admin)
            如果无法获取认证用户，返回 (None, False)
            为了安全，默认不是管理员，只有确认后才给予管理员权限。
        """
        auth_username = getattr(self, "auth_username", None)
        is_admin = False

        if auth_username and auth_username != "guest":
            # 使用全局的 auth_system 而不是实例属性
            try:
                # 直接引用全局变量 auth_system
                if hasattr(_main(), "auth_system") and _main().auth_system:
                    user_group = _main().auth_system.get_user_group(auth_username)
                    is_admin = user_group in ["admin", "super_admin"]
                    logging.debug(
                        f"用户 {auth_username} 权限组: {user_group}, 是否管理员: {is_admin}")
                else:
                    logging.debug(f"全局权限系统未初始化，用户 {auth_username} 默认为非管理员")
                    is_admin = False
            except Exception as e:
                logging.debug(f"检查用户权限失败: {e}，默认为非管理员")
                is_admin = False

        return auth_username, is_admin

    def _load_accounts_by_permission(self, auth_username: str) -> dict:
        """
        根据用户权限加载账号信息。
        """
        if not auth_username or auth_username == "guest":
            return {}

        # 检查权限
        _, is_admin = self._get_auth_user_and_check_admin()

        try:
            if is_admin:
                # 管理员：使用 _load_user_school_accounts，已内置权限聚合逻辑
                logging.info(f"管理员 {auth_username} 正在加载所有账号信息")
                accounts = self._load_user_school_accounts(auth_username)
            else:
                # 普通用户：仅加载自己的账号
                logging.info(f"普通用户 {auth_username} 正在加载自己的账号信息")
                file_path = self._get_user_accounts_file(auth_username)
                accounts = {}

                if os.path.exists(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        # 标准化格式：兼容旧版 INI 和新版 JSON
                        for sch_user, account_info in data.items():
                            if not _main().is_valid_school_username(sch_user):
                                continue
                            if isinstance(account_info, dict):
                                # 新格式：直接使用
                                accounts[sch_user] = account_info
                            elif isinstance(account_info, str):
                                # 旧格式兼容：将字符串密码转换为字典
                                accounts[sch_user] = {
                                    "password": account_info,
                                    "ua": None
                                }

                        logging.debug(
                            f"成功加载普通用户 {auth_username} 的账户，共 {len(accounts)} 个")
                    except Exception as e:
                        logging.error(f"加载普通用户 {auth_username} 的账户失败: {e}")
                        accounts = {}
                else:
                    logging.debug(
                        f"普通用户 {auth_username} 的账户文件不存在: {file_path}")

        except Exception as e:
            logging.error(f"_load_accounts_by_permission 执行失败: {e}")
            accounts = {}

        return accounts

    def update_school_account_overdue_count(self, auth_username, school_username, new_overdue_count):
        """
        更新指定学校账号的欠费次数（overdue_count）
        """
        # 验证参数有效性
        # 欠费次数不能为负数
        if new_overdue_count < 0:
            return {
                "success": False,
                "message": "欠费次数不能为负数"
            }

        # 验证用户名和学校账号用户名不能为空
        if not auth_username or not school_username:
            return {
                "success": False,
                "message": "用户名和学校账号用户名不能为空"
            }

        # 游客用户不允许操作学校账号
        if auth_username == "guest":
            return {
                "success": False,
                "message": "游客用户不允许操作学校账号"
            }

        try:
            # 使用线程锁确保文件操作的原子性
            # 防止多个请求同时修改同一个用户的数据导致数据不一致
            with self.lock:
                # 步骤1：加载用户的所有学校账号数据（验证账号是否存在）
                # 返回格式：{school_username: {"password": "xxx", "ua": "xxx", "overdue_count": 0}, ...}
                accounts = self._load_user_school_accounts(auth_username)

                # 步骤2：检查指定的学校账号是否存在
                if school_username not in accounts:
                    # 学校账号不存在，返回错误
                    # 我们不会自动创建账号，因为账号必须由用户主动添加
                    return {
                        "success": False,
                        "message": f"学校账号 {school_username} 不存在"
                    }

                # 步骤3：从 INI 文件读取当前的统计数据
                # 这样我们可以保留 completed_count，只更新 overdue_count
                stats = self._load_school_account_stats_from_ini(
                    school_username)
                current_completed_count = stats["completed_count"]

                # 步骤4：将新的 overdue_count 和原有的 completed_count 保存到 INI 文件
                # 使用专门的 INI 写入函数，实现数据分离存储
                success = self._save_school_account_stats_to_ini(
                    school_username,
                    new_overdue_count,           # 使用新的欠费次数
                    current_completed_count      # 保留原有的完成次数
                )

                # 步骤5：检查保存是否成功
                if not success:
                    return {
                        "success": False,
                        "message": "保存统计数据到 INI 文件失败"
                    }

                # 步骤6：记录操作日志
                logging.info(
                    f"[学校账号管理] 更新欠费次数成功 - 用户: {auth_username}, "
                    f"学校账号: {school_username}, 新欠费次数: {new_overdue_count}"
                )

                # 步骤7：返回成功结果
                return {
                    "success": True,
                    "message": f"已将学校账号 {school_username} 的欠费次数更新为 {new_overdue_count}"
                }

        except Exception as e:
            # 捕获所有异常（文件读写错误、JSON解析错误等）
            # 记录详细的错误日志，包含堆栈信息
            logging.error(
                f"[学校账号管理] 更新欠费次数失败 - 用户: {auth_username}, "
                f"学校账号: {school_username}, 错误: {str(e)}"
            )
            logging.error(traceback.format_exc())

            # 返回失败结果
            return {
                "success": False,
                "message": f"更新欠费次数失败: {str(e)}"
            }

    def _deduct_available_runs_or_increment_overdue(self, auth_username, school_username):
        """Serialize settlement so concurrent accounts share one run balance."""
        with _main().SYSTEM_ACCOUNT_BILLING_LOCK:
            return self._deduct_available_runs_or_increment_overdue_unlocked(
                auth_username,
                school_username,
            )

    def _deduct_available_runs_or_increment_overdue_unlocked(
        self, auth_username, school_username
    ):
        """
        任务完成后处理可用次数扣减或欠费次数增加的逻辑。

        扣减优先级（两段式，先系统账号后学校账号）:
            第一优先级 —— 平台（系统）账号：system_accounts/{auth}.json 的
                available_runs >= 1 时扣减 1 次；available_runs == -1 表示无限，
                直接跳过且不产生任何欠费。
            第二优先级 —— 学校账号：仅当系统账号 available_runs <= 0 时，
                才对该学校账号 overdue_count +1 并生成一条账单记录。

        也就是说，欠费只发生在系统账号次数确实用尽之后，不会因为学校账号
        自身状态而产生欠费。
        """
        try:
            # 步骤0：检查付费控制配置
            # 从配置文件中读取 require_payment（是否需要付费）和 single_run_cost（单次费用）
            # 如果不需要付费或价格为0/负数，则跳过所有付费相关逻辑（不扣除次数、不产生欠费）
            if getattr(self, "is_offline_mode", False):
                logging.info(
                    f"[付费控制] 离线测试模式，跳过次数扣除与欠费记录。"
                    f"(认证用户: {auth_username}, 学校账号: {school_username})"
                )
                return
            if getattr(self, "waive_charge_active", False):
                logging.info(
                    "[付费控制] 管理员选择“此次不计费”，跳过次数扣减与账单生成。"
                    f"(认证用户: {auth_username}, 学校账号: {school_username})"
                )
                return
            config = configparser.ConfigParser(strict=False)
            config = _main()._read_config_ini(_main().CONFIG_JSON_FILE) or _main()._get_default_config()
            # 读取 require_payment 配置项，默认值为 true（需要付费）
            # 如果配置为 false，表示系统运行在免费模式下
            require_payment = config.getboolean(
                "Payment_Settings", "require_payment", fallback=True)
            # 读取 single_run_cost 配置项，默认值为 1.0元
            # 如果价格设置为0或负数，也表示免费模式
            single_run_cost = config.getfloat(
                "Payment_Settings", "single_run_cost", fallback=1.0)

            # 判断是否需要跳过付费逻辑
            # 满足以下任一条件时跳过：
            # 1. require_payment 为 false（明确配置为免费模式）
            # 2. single_run_cost <= 0（价格为0或负数，等同于免费）
            if not require_payment or single_run_cost <= 0:
                logging.info(
                    f"[付费控制] 用户 {auth_username} (学校账号: {school_username}) "
                    f"免费模式运行，跳过次数扣除和欠费记录。"
                    f"(require_payment={require_payment}, single_run_cost={single_run_cost})"
                )
                # 免费模式下，直接返回，不执行后续的扣减或欠费逻辑
                return

            # 步骤1：加载认证用户的 system_accounts 数据
            # 使用全局 auth_system 来获取用户文件路径
            if not _main().auth_system:
                logging.warning(
                    f"[次数扣减] auth_system 未初始化，跳过次数扣减逻辑"
                )
                return

            user_file = _main().auth_system.get_user_file_path(auth_username)

            # 如果用户文件不存在，记录警告并返回
            if not os.path.exists(user_file):
                logging.warning(
                    f"[次数扣减] 用户文件不存在: {user_file}，跳过次数扣减逻辑"
                )
                return

            # 读取用户数据（JSON格式）
            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            # 步骤2：获取 available_runs 字段（向后兼容：如果不存在则默认为0）
            available_runs = user_data.get("available_runs", 0)

            logging.debug(
                f"[次数扣减] 用户 {auth_username} 当前可用次数: {available_runs}"
            )

            # 步骤3：如果是无限次数（-1），直接返回（无限账号不产生欠费）
            if available_runs == -1:
                logging.debug(
                    f"[次数扣减] 用户 {auth_username} 拥有无限次数，跳过扣减"
                )
                return

            # 步骤4：按优先级扣减
            #   第一优先级：平台（系统）账号的 available_runs
            #   第二优先级：学校账号的 overdue_count（仅在第一优先级不足时）
            if available_runs >= 1:
                # 第一优先级命中：扣减系统账号可用次数
                user_data["available_runs"] = available_runs - 1

                # 保存更新后的用户数据
                with open(user_file, "w", encoding="utf-8") as f:
                    json.dump(user_data, f, indent=2, ensure_ascii=False)

                logging.info(
                    f"[次数扣减] 扣减来源=系统账号：用户 {auth_username} 扣减1次可用次数，"
                    f"剩余: {user_data['available_runs']} 次"
                )
            else:
                # 第二优先级：系统账号可用次数已用尽，转为该学校账号的欠费次数
                # 加载该认证用户的所有学校账号配置
                school_accounts = self._load_user_school_accounts(
                    auth_username)

                # 查找目标学校账号
                if school_username in school_accounts:
                    account_info = school_accounts[school_username]

                    # 确保是字典格式（向后兼容）
                    if not isinstance(account_info, dict):
                        account_info = {
                            "password": account_info if isinstance(account_info, str) else "",
                            "ua": None,
                            "overdue_count": 0
                        }
                        school_accounts[school_username] = account_info

                    # 增加欠费次数
                    current_overdue = account_info.get("overdue_count", 0)
                    account_info["overdue_count"] = current_overdue + 1

                    # 保存更新后的学校账号配置
                    self._save_user_school_accounts(
                        auth_username, school_accounts)

                    # 读取单次费用配置，创建账单记录
                    try:
                        _billing_config = _main()._read_config_ini()
                        _single_run_cost_str = _billing_config.get(
                            "Payment_Settings", "single_run_cost", fallback="1.0") if _billing_config else "1.0"
                        _single_run_cost = round(float(_single_run_cost_str), 2)
                    except Exception:
                        _single_run_cost = 1.0
                    # 调用全局函数创建账单记录
                    _main()._create_user_billing_record(
                        auth_username,
                        school_username,
                        _main()._build_run_billing_reason(1, _single_run_cost),
                        _single_run_cost
                    )

                    logging.info(
                        f"[次数扣减] 扣减来源=学校账号：系统账号 {auth_username} 可用次数不足"
                        f"（当前: {available_runs}），学校账号 {school_username} 欠费次数 +1，"
                        f"当前欠费: {account_info['overdue_count']} 次"
                    )
                else:
                    # 如果学校账号不在配置中，记录警告（不得静默成功）
                    logging.warning(
                        f"[次数扣减] 扣减来源=学校账号，但认证用户 {auth_username} 的学校账号配置中"
                        f"未找到 {school_username}，无法增加欠费次数；"
                        f"本次不计欠费（系统账号可用次数: {available_runs}）"
                    )

        except Exception as e:
            # 捕获所有异常，避免影响主任务流程
            logging.error(
                f"[次数扣减] 处理用户 {auth_username}（学校账号: {school_username}）的次数扣减时发生异常: {e}",
                exc_info=True
            )

    def _increment_completed_count(self, auth_username, school_username):
        """
        增加学校账号的已完成任务计数。
        """
        try:
            # 步骤1：验证学校账号是否存在
            # 加载用户的所有学校账号配置，用于验证账号是否存在
            # 返回格式：{school_username: {"password": "xxx", "ua": "xxx", "overdue_count": 0, "completed_count": 0}, ...}
            accounts = self._load_user_school_accounts(auth_username)

            # 如果返回的是空字典，说明没有找到配置文件或加载失败
            if not accounts:
                logging.warning(
                    f"[任务计数] 无法加载用户 {auth_username} 的学校账号配置，跳过计数更新"
                )
                return

            # 步骤2：检查学校账号是否存在
            # 如果账号不存在，不进行任何操作
            if school_username not in accounts:
                logging.warning(
                    f"[任务计数] 在用户 {auth_username} 的配置中未找到学校账号 {school_username}，无法更新计数"
                )
                return

            # 步骤3：从 INI 文件读取当前的统计数据
            # 获取当前的 overdue_count 和 completed_count
            stats = self._load_school_account_stats_from_ini(school_username)
            current_overdue_count = stats["overdue_count"]
            current_completed_count = stats["completed_count"]

            # 步骤4：增加已完成任务计数
            # 将 completed_count 加1
            new_completed_count = current_completed_count + 1

            # 记录日志：显示更新前后的计数值
            logging.info(
                f"[任务计数] 用户 {auth_username} 的学校账号 {school_username} "
                f"已完成任务数: {current_completed_count} → {new_completed_count}"
            )

            # 步骤5：将更新后的统计数据保存到 INI 文件
            # 使用专门的 INI 写入函数保存
            # overdue_count 保持不变，只更新 completed_count
            success = self._save_school_account_stats_to_ini(
                school_username,
                current_overdue_count,      # 保持原有的欠费次数
                new_completed_count         # 使用新的完成次数
            )

            # 步骤6：检查保存是否成功
            if success:
                logging.debug(
                    f"[任务计数] 成功更新学校账号 {school_username} 的任务计数到 INI 文件"
                )
            else:
                logging.warning(
                    f"[任务计数] 保存学校账号 {school_username} 的任务计数到 INI 文件失败"
                )

        except Exception as e:
            # 捕获所有可能的异常（文件IO错误、权限错误等）
            # 记录详细的错误信息，包括完整的异常堆栈（exc_info=True）
            # 但不抛出异常，避免影响主任务流程的执行
            logging.error(
                f"[任务计数] 更新用户 {auth_username}（学校账号: {school_username}）的任务计数时发生异常: {e}",
                exc_info=True
            )

    def _save_config(self, username, password=None, ua=None):
        """保存指定用户的配置到 user/<username>.ini；当 password 为 None 时保留现有密码；当 ua 为 None 时保留现有 UA。同时更新主 config.ini 的 LastUser 和 amap_js_key。"""
        logging.debug(
            f"Saving config: username={username!r}, password provided: {password is not None}, ua provided: {ua is not None}"
        )

        if not _main().is_valid_school_username(username):
            logging.warning(
                "[配置] 拒绝保存非法学号的 INI 配置: %r"
                "（学号必须是至少4位纯数字）",
                username,
            )
            return False

        user_ini_path = os.path.join(self.user_dir, f"{username}.ini")

        self.normalize_chinese_config_to_english(user_ini_path)
        cfg_to_save = configparser.RawConfigParser()
        cfg_to_save.optionxform = str
        if os.path.exists(user_ini_path):
            try:
                cfg_to_save.read(user_ini_path, encoding="utf-8")
                # 记录读取到的所有节
                logging.debug(
                    f" _save_config读取INI文件 - "
                    f"用户: {username}, 包含的节: {cfg_to_save.sections()}"
                )
                # 如果存在stats节，记录其内容
                if cfg_to_save.has_section('stats'):
                    stats_items = dict(cfg_to_save.items('stats'))
                    logging.debug(
                        f" _save_config读取到 [stats] 节 - "
                        f"用户: {username}, 内容: {stats_items}"
                    )
            except Exception as e:
                logging.warning(
                    f"读取旧配置文件 {user_ini_path} 失败: {e}, 将创建新的。"
                )

        # ========== 保留 [stats] 节，避免覆盖欠费数据 ==========
        # 问题背景：
        # 1. 欠费系统通过 _save_school_account_stats_to_ini() 修改了 [stats] 节
        # 2. 任务系统调用 _save_config() 保存密码或其他配置时，会覆盖整个文件
        # 3. 导致 [stats] 节的数据丢失，欠费数据被还原
        #
        # 解决方案：
        # 在读取现有配置后，检查是否存在 [stats] 节
        # 如果存在，保存其内容到临时变量
        # 在写入文件前，将保存的内容恢复到配置对象中
        #
        # 这样可以确保 [stats] 节的 overdue_count 和 completed_count 不被覆盖

        # --- 步骤1：备份 [stats] 节的数据 ---
        # 初始化备份字典，用于存储 [stats] 节的所有配置项
        stats_section_backup = {}

        # 检查配置对象中是否存在 [stats] 节
        if cfg_to_save.has_section('stats'):
            # [stats] 节存在，遍历并保存其所有配置项
            for option in cfg_to_save.options('stats'):
                # 将每个配置项的名称和值保存到备份字典中
                stats_section_backup[option] = cfg_to_save.get('stats', option)

            # 记录调试日志：已检测到并备份 [stats] 节
            # 这有助于排查问题，确认备份操作是否执行
            logging.debug(
                f"检测到现有 [stats] 节，已备份 - "
                f"用户: {username}, 备份数据: {stats_section_backup}"
            )
        else:
            # [stats] 节不存在，记录调试日志
            # 这是正常情况，说明该用户的INI文件中还没有欠费统计数据
            logging.debug(
                f"用户配置中不存在 [stats] 节 - 用户: {username}"
            )

        if not cfg_to_save.has_section("Config"):
            cfg_to_save.add_section("Config")
        if not cfg_to_save.has_section("System"):
            cfg_to_save.add_section("System")

        cfg_to_save.set("Config", "Username", username)
        if password is not None:
            cfg_to_save.set("Config", "password", password)
        else:
            if not cfg_to_save.has_option("Config", "password"):
                backup_path = f"{user_ini_path}.bak"
                if os.path.exists(backup_path):
                    try:
                        with open(backup_path, "rb") as bf:
                            raw_backup = bf.read()
                        backup_text = self._robust_decode(raw_backup)
                        for line in backup_text.splitlines():
                            clean_line = line.strip()
                            normalized_line = clean_line.lower().replace(" ", "")
                            if normalized_line.startswith(
                                "password="
                            ) or normalized_line.startswith("密码="):
                                parts = clean_line.split("=", 1)
                                if len(parts) == 2:
                                    recovered_password = parts[1].strip()
                                    if recovered_password:
                                        cfg_to_save.set(
                                            "Config", "password", recovered_password
                                        )
                                        logging.info(
                                            f"已从备份文件恢复用户 {username} 的密码"
                                        )
                                        break
                    except Exception as e:
                        logging.warning(f"从备份文件恢复密码失败: {e}")
            else:
                pass

        if ua is not None:
            cfg_to_save.set("System", "ua", ua)
        params_to_save = self.params
        if self.is_multi_account_mode and username in self.accounts:
            params_to_save = self.accounts[username].params

        # auto_attendance_enabled 已迁移到JSON配置文件管理，不再保存到INI
        for k, v in params_to_save.items():
            # 跳过 auto_attendance_enabled，这个参数不再保存到INI文件
            if k == "auto_attendance_enabled":
                continue
            if k in self.global_params and k != "amap_js_key":
                cfg_to_save.set("Config", k, str(v))

        # 在写入文件之前，将之前备份的 [stats] 节数据恢复到配置对象中
        # 这样可以确保 [stats] 节的数据不会在保存配置时丢失

        # --- 步骤2：恢复 [stats] 节的数据 ---
        # 检查备份字典是否包含数据（非空）
        if stats_section_backup:
            # 备份字典非空，说明之前存在 [stats] 节，需要恢复

            # 首先检查配置对象中是否已经有 [stats] 节
            # 如果没有，则创建一个新的 [stats] 节
            if not cfg_to_save.has_section('stats'):
                cfg_to_save.add_section('stats')
                logging.debug(
                    f"重新创建 [stats] 节 - 用户: {username}"
                )

            # 遍历备份字典，将所有配置项恢复到 [stats] 节中
            for option, value in stats_section_backup.items():
                cfg_to_save.set('stats', option, value)

            # 记录调试日志：已成功恢复 [stats] 节
            # 这是关键的验证步骤，确保数据恢复成功
            logging.debug(
                f"已恢复 [stats] 节到配置文件 - "
                f"用户: {username}, 恢复的配置项数量: {len(stats_section_backup)}"
            )

            # 记录信息日志：用于监控和审计
            # 让管理员知道 [stats] 节被正确保留了
            logging.info(
                f"成功保留 [stats] 节数据 - "
                f"用户: {username}, overdue_count: {stats_section_backup.get('overdue_count', 'N/A')}, "
                f"completed_count: {stats_section_backup.get('completed_count', 'N/A')}"
            )

        try:
            # ========== 记录即将写入的所有节 ==========
            logging.debug(
                f" _save_config即将写入INI文件 - "
                f"用户: {username}, 包含的节: {cfg_to_save.sections()}"
            )
            # 如果存在stats节，记录其内容
            if cfg_to_save.has_section('stats'):
                stats_items = dict(cfg_to_save.items('stats'))
                logging.debug(
                    f" _save_config即将写入 [stats] 节 - "
                    f"用户: {username}, 内容: {stats_items}"
                )
            else:
                logging.warning(
                    f" _save_config即将写入但没有 [stats] 节 - "
                    f"用户: {username}"
                )

            with open(user_ini_path, "w", encoding="utf-8") as f:
                cfg_to_save.write(f)
            logging.debug(
                f"Saved user config for {username} -> {user_ini_path}")
        except Exception as e:
            logging.error(f"写入用户配置文件 {user_ini_path} 失败: {e}", exc_info=True)

        if (
            password is not None
            and hasattr(self, "auth_username")
            and self.auth_username
        ):
            self._update_school_account_password(
                self.auth_username, username, password, ua, login_verified=False
            )

        main_cfg = _main()._read_config_ini(self.config_path) or configparser.RawConfigParser()
        # [修正] 不再将 LastUser 写入 config.ini，而是更新到系统账号文件
        if (
            hasattr(self, "auth_username")
            and self.auth_username
            and self.auth_username != "guest"
        ):
            if hasattr(_main(), "auth_system"):
                _main().auth_system.update_user_last_school_account(
                    self.auth_username, username
                )
                logging.debug(
                    f"已更新用户 {self.auth_username} 的最后使用学校账号为: {username}"
                )

        # 下面仅保留必要的全局配置写入（如 Map Key）
        if not main_cfg.has_section("Map"):
            main_cfg.add_section("Map")

        amap_key_in_memory = self.global_params.get("amap_js_key", "").strip()
        amap_key_in_file = main_cfg.get(
            "Map", "amap_js_key", fallback="").strip()

        if amap_key_in_memory:
            main_cfg.set("Map", "amap_js_key", amap_key_in_memory)
        elif amap_key_in_file:
            self.global_params["amap_js_key"] = amap_key_in_file
        else:
            main_cfg.set("Map", "amap_js_key", "")

        # 只有当确实有内容变更需要写入 config.ini 时才写入 (这里主要是 Map Key)
        # 如果只是更新了用户配置，没必要每次都覆写 config.ini
        try:
            _main()._write_config_with_comments(main_cfg, self.config_path)
            logging.debug(f"更新主配置文件 {self.config_path} 成功 (Map Key)")
        except Exception as e:
            logging.error(f"写入主配置文件 {self.config_path} 失败: {e}", exc_info=True)

    def _load_global_config(self):
        """从主 config.ini 加载全局配置（优先读取新版 Map.amap_js_key，兼容旧版 System.AmapJsKey）"""
        if not os.path.exists(self.config_path):
            return
        try:
            cfg = _main()._read_config_ini(self.config_path) or _main()._get_default_config()

            amap_key = _main()._resolve_amap_js_key(cfg)

            if not amap_key:
                amap_key = cfg.get("System", "AmapJsKey", fallback="")

            self.global_params["amap_js_key"] = amap_key

            # [修正] 加载全局主题配置 (仅当配置文件中存在时才覆盖内存中的值)
            if cfg.has_option("Config", "theme_base_color"):
                self.global_params["theme_base_color"] = cfg.get(
                    "Config", "theme_base_color"
                )

            if cfg.has_option("Config", "theme_style"):
                self.global_params["theme_style"] = cfg.get(
                    "Config", "theme_style")

            # [修正] auto_attendance_enabled 不再从全局配置文件读取，而是依赖会话持久化或默认值
            # 仅保留刷新间隔和半径作为全局默认值（如果需要的话），或者也完全移除
            # 这里根据指示移除 enabled 的读取

            if cfg.has_option("Config", "auto_attendance_refresh_s"):
                self.global_params["auto_attendance_refresh_s"] = cfg.getint(
                    "Config", "auto_attendance_refresh_s"
                )

            if cfg.has_option("Config", "auto_attendance_stop_after_success"):
                self.global_params["auto_attendance_stop_after_success"] = cfg.getboolean(
                    "Config", "auto_attendance_stop_after_success"
                )

            if cfg.has_option("Config", "auto_attendance_success_limit"):
                self.global_params["auto_attendance_success_limit"] = max(
                    1, cfg.getint("Config", "auto_attendance_success_limit")
                )

            if cfg.has_option("Config", "attendance_user_radius_m"):
                self.global_params["attendance_user_radius_m"] = cfg.getint(
                    "Config", "attendance_user_radius_m"
                )

            # Keep the single-account parameter view aligned with persisted globals.
            if not self.is_multi_account_mode:
                for key in (
                    "auto_attendance_stop_after_success",
                    "auto_attendance_success_limit",
                    "auto_attendance_refresh_s",
                    "attendance_user_radius_m",
                ):
                    if key in self.global_params:
                        self.params[key] = self.global_params[key]

            logging.info(
                f"Loaded global config: AmapKey={'Yes' if amap_key else 'No'}, Theme={self.global_params.get('theme_base_color')}"
            )
        except Exception as e:
            logging.error(
                f"加载全局配置文件 {self.config_path} 失败: {e}", exc_info=True
            )

    # def _load_user_config(self, username):
    #     """(已弃用) 从school_accounts加载指定用户的配置。不要调用此方法以获取 UA 或密码。

    #     说明: 该函数保留以便参考历史实现，但已重命名为 `_load_user_config`，
    #     目的在于避免覆盖无参的 `_load_config` 方法。UA 和密码不再应从
    #     本地 ini 文件读取；如需生产环境中的凭据，请使用安全存储或环境变量。
    #     """
    #     self.user_config_path = os.path.join(self.user_dir, f"{username}.ini")
    #     if not os.path.exists(self.user_config_path):
    #         return None

    #     self.normalize_chinese_config_to_english(self.user_config_path)

    #     cfg = configparser.ConfigParser(strict=False)
    #     try:
    #         cfg.read(self.user_config_path, encoding="utf-8")
    #     except Exception as e:
    #         logging.warning(f"解析用户配置文件 {username} 时出错 (已忽略): {e}")

    #     password = ""
    #     ua = ""

    #     if hasattr(self, "auth_username") and self.auth_username:
    #         school_password = self._get_school_account_password(
    #             self.auth_username, username
    #         )
    #         school_ua = self._get_school_account_ua(
    #             self.auth_username, username)
    #         if school_password:
    #             password = school_password
    #             logging.debug(
    #                 f"从用户 {self.auth_username} 的 school_accounts 加载了 {username} 的密码"
    #             )
    #         if school_ua:
    #             ua = school_ua
    #             logging.debug(
    #                 f"从用户 {self.auth_username} 的 school_accounts 加载了 {username} 的UA"
    #             )

    #     target_params = self.params
    #     if self.is_multi_account_mode and username in self.accounts:
    #         target_params = self.accounts[username].params

    #     if self.is_multi_account_mode and username in self.accounts:
    #         self.accounts[username].device_ua = ua
    #     else:
    #         self.device_ua = ua

    #     for k in self.global_params:
    #         if k in target_params:
    #             try:
    #                 if cfg.has_option("Config", k):
    #                     val_str = cfg.get("Config", k)
    #                     original_type = type(target_params[k])
    #                     if original_type is bool:
    #                         target_params[k] = val_str.lower() in (
    #                             "true",
    #                             "1",
    #                             "t",
    #                             "yes",
    #                         )
    #                     else:
    #                         target_params[k] = original_type(val_str)
    #             except ValueError:
    #                 logging.warning(
    #                     f"无法解析用户 {username} 的配置项 '{k}'，将使用默认值。"
    #                 )
    #                 pass
    #     logging.debug(f"已成功加载用户配置: {username}")
    #     return password

    def _save_account_tag(self, username, tag):
        """保存账号标记到用户配置文件"""
        user_ini_path = os.path.join(self.user_dir, f"{username}.ini")

        cfg = configparser.RawConfigParser()
        cfg.optionxform = str
        if os.path.exists(user_ini_path):
            try:
                cfg.read(user_ini_path, encoding="utf-8")
            except Exception as e:
                logging.warning(f"读取配置文件 {user_ini_path} 失败: {e}")

        if not cfg.has_section("Account"):
            cfg.add_section("Account")

        cfg.set("Account", "Tag", str(tag))

        try:
            with open(user_ini_path, "w", encoding="utf-8") as f:
                cfg.write(f)
            logging.debug(f"已保存账号 {username} 的标记: {tag}")
        except Exception as e:
            logging.error(f"保存账号标记失败 {user_ini_path}: {e}", exc_info=True)

    def _load_account_tag(self, username):
        """从用户配置文件加载账号标记"""
        user_ini_path = os.path.join(self.user_dir, f"{username}.ini")
        if not os.path.exists(user_ini_path):
            return None

        cfg = configparser.ConfigParser(strict=False)
        try:
            cfg.read(user_ini_path, encoding="utf-8")
            if cfg.has_option("Account", "Tag"):
                tag_str = cfg.get("Account", "Tag")
                return tag_str
        except Exception as e:
            logging.warning(f"加载账号标记失败 {username}: {e}")

        return None

    def _get_full_user_info_dict(self):
        """获取当前用户所有信息的字典"""
        return {
            k: v for k, v in self.user_data.__dict__.items() if not k.startswith("_")
        }

    def get_initial_data(self, frontend_logs=None):
        """
        应用启动时由前端调用，获取初始用户列表和最后登录用户

        参数:
            frontend_logs: 可选，前端发送的日志数据（列表或单个日志对象）
        """

        # ========== 处理前端日志（如果提供）==========
        if frontend_logs:
            try:
                # 获取会话信息用于日志记录
                session_id = getattr(self, "_web_session_id", "UnknownSession")
                auth_username = getattr(self, "auth_username", None)
                is_guest = getattr(self, "is_guest", False)

                # 确定用户名
                username = "Guest" if is_guest else (
                    auth_username or "Unknown")

                # 处理日志列表
                logs_to_process = (
                    frontend_logs
                    if isinstance(frontend_logs, list)
                    else [frontend_logs]
                )

                for log_item in logs_to_process:
                    if isinstance(log_item, dict) and log_item.get("message"):
                        level = log_item.get("level", "INFO").upper()
                        message = _main()._redact_sensitive_log_value(log_item.get("message", ""))
                        timestamp = log_item.get("timestamp", "")
                        source = log_item.get("source", "unknown")

                        log_message = f"[前端日志][前端时间:{timestamp}][用户:{username}][Session:{session_id}][{source}] {message}"

                        # 根据日志级别记录到后端
                        if level == "ERROR":
                            logging.error(log_message)
                        elif level == "WARN" or level == "WARNING":
                            logging.warning(log_message)
                        else:
                            logging.info(log_message)

                logging.debug(f"[前端日志] 处理了 {len(logs_to_process)} 条前端日志")
            except Exception as e:
                logging.error(f"[前端日志] 处理前端日志时出错: {e}", exc_info=True)

        try:
            session_id = getattr(self, "_web_session_id", None)
            if session_id:
                with _main().browsing_activity_lock:
                    _main().browsing_activity[session_id] = time.time()
                logging.debug(f"[浏览监控] 更新会话 {session_id[:8]} 的浏览活跃时间")
        except Exception as e:
            logging.warning(f"[浏览监控] 更新活跃时间失败: {e}")

        try:
            logging.info(
                "API调用: get_initial_data - 获取应用初始数据（用户列表和最后登录用户）"
            )

            all_users = sorted(
                [
                    os.path.splitext(f)[0]
                    for f in os.listdir(self.user_dir)
                    if f.endswith(".ini")
                ]
            )

            is_authenticated = (
                hasattr(self, "is_authenticated") and self.is_authenticated
            )
            auth_username = getattr(self, "auth_username", None)
            auth_group = getattr(self, "auth_group", "guest")
            is_guest = getattr(self, "is_guest", False)

            # ========== 权限检查：根据用户权限过滤可见的用户列表 ==========
            if is_guest:
                users = []
                logging.debug(f"游客用户请求 get_initial_data，返回空用户列表")
            elif auth_username and not is_guest:
                # 账号列表可见性共三档：
                #   all  —— auto_fill_password（或管理员组）：可见所有学校账号
                #   own  —— view_school_account_passwords：可见自己的学校账号
                #   none —— 两者皆无：不可见任何学校账号
                # 这里只决定"能列出哪些账号"，密码字段是否下发另由
                # web_server._apply_password_visibility 控制。
                password_visibility = "none"
                try:
                    password_visibility = (
                        _main().auth_system.resolve_password_visibility(auth_username)
                    )
                except Exception as e:
                    logging.warning(
                        f"解析用户 {auth_username} 的密码可见级别时出错: {e}"
                    )

                has_view_all_permission = False
                has_view_own_permission = False

                if auth_group in ["admin", "super_admin"]:
                    has_view_all_permission = True
                    logging.debug(
                        f"用户 {auth_username} 是管理员，拥有查看所有账户的权限"
                    )
                elif password_visibility == "all":
                    has_view_all_permission = True
                    logging.debug(
                        f"用户 {auth_username} 通过 auto_fill_password 获得了查看所有账户的权限"
                    )
                elif password_visibility == "own":
                    has_view_own_permission = True
                    logging.debug(
                        f"用户 {auth_username} 具备查看本账号学校账号密码的权限"
                    )

                if has_view_all_permission:
                    users = all_users
                    logging.debug(
                        f"用户 {auth_username} 有权限，返回所有 {len(users)} 个学校账户"
                    )
                elif has_view_own_permission:
                    # 中层权限：至少能看到自己关联的学校账号（否则中层用户
                    # 会因为缺少 auto_fill_password 而连自己的账号都看不到）
                    school_accounts = self._load_user_school_accounts(
                        auth_username)
                    users = list(school_accounts.keys()) if school_accounts else []
                    logging.debug(
                        f"用户 {auth_username} 具备本账号密码查看权限，"
                        f"返回其自己的 {len(users)} 个学校账户"
                    )
                else:
                    users = []
                    logging.debug(
                        f"用户 {auth_username} 无学校账号可见权限，返回空列表"
                    )
            else:
                users = all_users
                logging.debug(
                    f"未认证用户请求 get_initial_data，返回所有 {len(users)} 个账户（向后兼容）"
                )

            cfg = _main()._read_config_ini(self.config_path) or _main()._get_default_config()

            # [修正] LastUser 不再从 config.ini 读取，而是从当前登录用户的系统账号信息中获取
            last_user = ""

            # 尝试获取当前认证用户的 last_used_school_account
            auth_username = getattr(self, "auth_username", None)
            is_guest = getattr(self, "is_guest", False)

            if (
                auth_username
                and not is_guest
                and hasattr(_main(), "auth_system")
            ):
                try:
                    details = _main().auth_system.get_user_details(auth_username)
                    if details:
                        last_user = details.get("last_used_school_account", "")
                except Exception as e:
                    logging.warning(f"获取用户 {auth_username} 的 LastUser 失败: {e}")

            # 验证 last_user 是否有效
            if last_user and last_user not in all_users:
                logging.debug(f"LastUser '{last_user}' 不在可用列表中，已忽略。")
                last_user = ""
                try:
                    # 使用 _write_config_with_comments() 函数写入配置文件
                    # 原因：标准的 config.write() 方法会丢失 config.ini 中的所有注释内容
                    # _write_config_with_comments() 函数会保留配置文件中的注释，保持可读性
                    # 这对于维护配置文件的可读性和文档性非常重要
                    _main()._write_config_with_comments(cfg, self.config_path)
                except Exception as e:
                    logging.error(f"写回 config.ini 失败：{e}", exc_info=True)
                last_user = ""

            self._load_global_config()

            is_logged_in = hasattr(
                self, "login_success") and self.login_success
            user_info = None
            if is_logged_in and hasattr(self, "user_info"):
                user_info = self.user_info

            logging.debug(
                f"Initial user count={len(users)}, has_last_user={bool(last_user)}, "
                f"logged_in={is_logged_in}"
            )

            # ========================================
            # 【本地验证码】读取验证码生成器配置
            # ========================================
            def _safe_get_int(section, key, default):
                try:
                    return int(cfg.get(section, key, fallback=str(default)))
                except (ValueError, TypeError):
                    return int(default)

            def _safe_get_float(section, key, default):
                try:
                    return float(cfg.get(section, key, fallback=str(default)))
                except (ValueError, TypeError):
                    return float(default)

            captcha_settings = {
                "length": _safe_get_int("Captcha", "length", 4),
                "scale_factor": _safe_get_int("Captcha", "scale_factor", 2),
                "noise_level": _safe_get_float("Captcha", "noise_level", 0.08),
            }
            try:
                _cap_prov = _main().get_captcha_provider_config()
                captcha_settings["provider"] = _cap_prov["provider"]
                captcha_settings["behavior_type"] = _cap_prov["behavior_type"]
            except Exception:
                captcha_settings["provider"] = "image"
                captcha_settings["behavior_type"] = "SLIDER"
            logging.debug(f"【本地验证码】加载验证码设置: {captcha_settings}")

            current_theme = "light"
            current_theme_style = "default"
            session_uuid = str(getattr(self, "_web_session_id", "") or "").strip()
            base_dir = os.path.dirname(os.path.abspath(__file__))
            theme_background_cache_dir = os.path.join(base_dir, _main().RANDOM_BACKGROUND_IMAGE_DIR)
            current_theme_config = _main().auth_system.get_theme_config(
                "default",
                session_uuid=session_uuid,
                cache_dir=theme_background_cache_dir,
            ) if hasattr(_main(), "auth_system") else {}
            if (
                auth_username
                and not is_guest
                and hasattr(_main(), "auth_system")
            ):
                try:
                    theme_result = _main().auth_system.get_user_theme(auth_username)
                    if theme_result.get("success"):
                        current_theme = theme_result.get("theme", "light")
                except Exception as e:
                    logging.warning(f"获取用户 {auth_username} 的主题失败: {e}")

                current_theme_style = self.global_params.get("theme_style", "default")
                try:
                    current_theme_config = _main().auth_system.get_theme_config(
                        current_theme_style,
                        session_uuid=session_uuid,
                        cache_dir=theme_background_cache_dir,
                    )
                except Exception as e:
                    logging.warning(f"获取主题配置失败 {current_theme_style}: {e}")
                    current_theme_config = _main().auth_system.get_theme_config(
                        "default",
                        session_uuid=session_uuid,
                        cache_dir=theme_background_cache_dir,
                    )
            current_theme_config = _main()._apply_identity_bundle_to_theme_config(
                current_theme_config,
                session_uuid,
            )

            cdn_cache_status = {}
            try:
                with _main().js_cache_lock:
                    for key, config in _main().CDN_FILES.items():
                        cdn_cache_status[key] = {
                            "type": config["type"],
                            "cached": key in _main().js_cache_storage,
                            "last_update_time": (
                                datetime.datetime.fromtimestamp(
                                    _main().js_cache_last_update[key]
                                ).strftime("%Y-%m-%d %H:%M:%S")
                                if key in _main().js_cache_last_update
                                else None
                            ),
                        }
            except Exception as e:
                logging.warning(f"[get_initial_data] 获取CDN缓存状态失败: {e}")

            task_status = None
            try:
                if (
                    session_uuid
                    and hasattr(_main(), "background_task_manager")
                    and _main().background_task_manager
                ):
                    task_status = _main().background_task_manager.get_task_status(session_uuid)
            except Exception as e:
                logging.warning(f"[get_initial_data] 获取后台任务状态失败: {e}")

            required_map_provider = None
            if (
                isinstance(task_status, dict)
                and task_status.get("status") in ("running", "paused")
            ):
                required_map_provider = task_status.get("map_provider")
            map_public_payload = _main()._build_public_map_provider_frontend_payload(
                cfg,
                required_provider=required_map_provider,
                session_id=session_uuid,
                username=auth_username,
            )

            response_data = {
                "success": True,
                "users": users,
                "lastUser": last_user,
                "map_provider": map_public_payload["map_provider"],
                "map_providers": map_public_payload["map_providers"],
                "map_provider_key_bundle": map_public_payload["map_provider_key_bundle"],
                "isLoggedIn": is_logged_in,
                "userInfo": user_info,
                "is_authenticated": is_authenticated,
                "auth_username": auth_username,
                "auth_group": auth_group,
                "is_guest": is_guest,
                "theme": current_theme,
                "theme_styles": _main().auth_system.get_available_theme_styles(),
                "theme_config": current_theme_config,
                "theme_global_environment_variables": current_theme_config.get(
                    "global_environment_variables", {}
                ),
                "cdn_cache": cdn_cache_status,
                "is_multi_account_mode": getattr(self, "is_multi_account_mode", False),
                "captcha_settings": captcha_settings,
            }

            if (
                isinstance(task_status, dict)
                and task_status.get("status") in ("running", "paused")
            ):
                response_data["task_status"] = task_status

            # 如果是超级管理员，在初始化数据中包含密码恢复任务列表
            if auth_group == "super_admin":
                if _main().brute_force_manager:
                    response_data["bruteforce_task_list"] = (
                        _main().brute_force_manager.get_all_tasks_status()
                    )
                else:
                    response_data["bruteforce_task_list"] = []

            # 如果在多账号模式，添加所有账号的状态信息
            if getattr(self, "is_multi_account_mode", False):
                try:
                    # 调用multi_get_all_accounts_status获取所有账号状态
                    multi_status = self.multi_get_all_accounts_status()
                    # 将账号状态数据添加到响应中
                    if multi_status and isinstance(multi_status, dict):
                        # 添加accounts字段
                        response_data["accounts"] = multi_status.get(
                            "accounts", [])
                        logging.debug(
                            f"[多账号模式] 已添加 {len(response_data.get('accounts', []))} 个账号的状态信息"
                        )
                except Exception as e:
                    logging.error(f"[多账号模式] 获取账号状态失败: {e}", exc_info=True)
                    response_data["accounts"] = []

            if is_logged_in and hasattr(self, "device_ua"):
                response_data["device_ua"] = self.device_ua

            logging.debug(
                f"Initial data response prepared: users={len(users)}, last user={last_user}, logged_in={is_logged_in}, ua_sent={response_data.get('device_ua') is not None}"
            )

            return response_data
        except Exception as e:
            logging.error(f"获取初始数据时发生错误: {e}", exc_info=True)
            self.is_offline_mode = True
            return {
                "success": False,
                "offline": True,
                "message": "暂时无法连接到后端服务器，请刷新重试。如果问题依旧，请联系管理员。",
            }

    def get_user_sessions(self):
        """获取当前认证用户的会话列表（供前端调用）"""
        logging.info("API调用: get_user_sessions - 获取当前用户的所有活动会话列表")

        auth_username = getattr(self, "auth_username", None)
        is_guest = getattr(self, "is_guest", True)

        if not auth_username or is_guest:
            logging.warning("get_user_sessions: 用户未登录或为游客，返回空列表。")
            if is_guest and hasattr(self, "_web_session_id"):
                current_session_id = self._web_session_id
                session_file = _main().get_session_file_path(current_session_id)
                created_at = 0
                last_activity = 0
                if os.path.exists(session_file):
                    try:
                        with open(session_file, "r", encoding="utf-8") as f:
                            s_data = json.load(f)
                        created_at = s_data.get("created_at", 0)
                        last_activity = s_data.get("last_accessed", 0)
                    except Exception:
                        pass

                guest_session_info = [
                    {
                        "session_id": current_session_id,
                        "session_hash": hashlib.sha256(
                            current_session_id.encode()
                        ).hexdigest()[:16],
                        "created_at": created_at,
                        "last_activity": last_activity,
                        "is_current": True,
                        "login_success": False,
                        "is_multi_account_mode": False,
                        "user_data": {"username": "guest"},
                    }
                ]
                return _main().jsonify(
                    {
                        "success": True,
                        "sessions": guest_session_info,
                        "max_sessions": -1,
                    }
                )
            else:
                return {"success": True, "sessions": []}

        try:
            session_ids = _main().auth_system.get_user_sessions(auth_username)
            logging.debug(
                f"Found {len(session_ids)} linked session IDs for user {auth_username}"
            )

            sessions_info = []
            current_session_id = getattr(self, "_web_session_id", None)

            for sid in session_ids:
                session_file = _main().get_session_file_path(sid)
                if os.path.exists(session_file):
                    try:
                        with open(session_file, "r", encoding="utf-8") as f:
                            session_data = json.load(f)

                        if session_data.get("auth_username") == auth_username:
                            sessions_info.append(
                                {
                                    "session_id": sid,
                                    "session_hash": hashlib.sha256(
                                        sid.encode()
                                    ).hexdigest()[:16],
                                    "created_at": session_data.get("created_at", 0),
                                    "last_activity": session_data.get(
                                        "last_accessed", 0
                                    ),
                                    "is_current": sid == current_session_id,
                                    "login_success": session_data.get(
                                        "login_success", False
                                    ),
                                    "is_multi_account_mode": session_data.get(
                                        "is_multi_account_mode", False
                                    ),
                                    "user_data": session_data.get("user_data", {}),
                                }
                            )
                    except Exception as e:
                        logging.warning(
                            f"读取会话文件 {session_file} 失败: {e}, 跳过该会话。"
                        )
                        continue

            logging.info(
                f"成功获取用户 {auth_username} 的 {len(sessions_info)} 个会话信息。"
            )
            return {"success": True, "sessions": sessions_info}
        except Exception as e:
            logging.error(f"获取用户会话列表时发生错误: {e}", exc_info=True)
            return {"success": False, "message": f"服务器内部错误: {e}"}

    def save_map_provider_key(self, provider, api_key):
        """由JS调用，保存当前地图提供方对应的 API Key 到主配置文件。"""
        try:
            provider = _main()._normalize_map_provider(provider)
            key_field = _main().MAP_PROVIDER_KEY_FIELDS[provider]
            api_key = str(api_key or "").strip()
            if not api_key:
                return {"success": False, "message": "API Key不能为空"}

            cfg = _main()._read_config_ini(self.config_path) or _main()._get_default_config()

            if not cfg.has_section("Map"):
                cfg.add_section("Map")
            providers = cfg.get("Map", "providers", fallback={})
            if isinstance(providers, str):
                providers = _main().JsonConfigAdapter._coerce_map_providers(providers)
            if not isinstance(providers, dict):
                providers = {}

            provider_config = providers.get(provider) or {}
            provider_config[key_field] = api_key
            providers[provider] = provider_config
            cfg.set("Map", "providers", providers)
            legacy_keys = {
                "amap": "amap_js_key",
                "tencent": "tencent_map_key",
                "tianditu": "tianditu_token",
                "baidu": "baidu_map_ak",
            }
            legacy_key = legacy_keys.get(provider)
            if legacy_key and cfg.has_option("Map", legacy_key):
                cfg.remove_option("Map", legacy_key)
            if provider == "amap":
                self.global_params["amap_js_key"] = api_key

            _main()._write_config_with_comments(cfg, self.config_path)

            display_name = _main().MAP_PROVIDER_DISPLAY_NAMES[provider]
            self.log_and_notify_frontend(f"{display_name} API Key已保存。")
            logging.info(f"已成功保存新的{display_name} API Key")
            map_public_payload = _main()._build_public_map_provider_frontend_payload(
                cfg,
                required_provider=provider,
                session_id=getattr(self, "_web_session_id", None),
                username=getattr(self, "auth_username", None),
            )
            return {
                "success": True,
                "map_provider": map_public_payload["map_provider"],
                "map_providers": map_public_payload["map_providers"],
                "map_provider_key_bundle": map_public_payload["map_provider_key_bundle"],
            }
        except Exception as e:
            self.log_and_notify_frontend(f"保存地图API Key失败: {e}")
            logging.error(f"保存地图API Key失败: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    def save_amap_key(self, api_key: str):
        """由JS调用，保存高德地图API Key到主配置文件"""
        return self.save_map_provider_key("amap", api_key)

    def on_user_selected(self, username):
        """
        当用户在登录界面选择一个已有用户时调用。
        """
        logging.info(
            f"API调用: on_user_selected - 用户选择事件触发，选中的用户名: '{username}'"
        )

        # ========== 输入验证 ==========
        if not username:
            return {"password": "", "ua": "", "params": self.params, "userInfo": {}}

        # ========== 关键安全增强：权限检查 ==========
        auth_username = getattr(self, "auth_username", None)
        auth_group = getattr(self, "auth_group", "guest")
        is_guest = getattr(self, "is_guest", False)
        is_authenticated = hasattr(
            self, "is_authenticated") and self.is_authenticated
        if is_authenticated and auth_username and not is_guest:
            has_view_all_permission = False

            if auth_group in ["admin", "super_admin"]:
                has_view_all_permission = True
                logging.debug(f"用户 {auth_username} 是管理员，可以查看所有账户密码")
            elif hasattr(self, "auth_system"):
                try:
                    has_view_all_permission = _main().auth_system.check_permission(
                        auth_username, "auto_fill_password"
                    )
                    if has_view_all_permission:
                        logging.debug(
                            f"用户 {auth_username} 通过自定义权限获得了查看所有账户密码的权限"
                        )
                except Exception as e:
                    logging.warning(
                        f"检查用户 {auth_username} 的 auto_fill_password 权限时出错: {e}"
                    )
                    pass

            if not has_view_all_permission:
                school_accounts = self._load_user_school_accounts(
                    auth_username)

                if not school_accounts or username not in school_accounts:
                    logging.warning(
                        f"权限拒绝: 普通用户 {auth_username} 试图访问未授权的学校账户 {username}"
                    )
                    return {
                        "password": "",
                        "ua": "",
                        "params": self.params,
                        "userInfo": {},
                    }
                else:
                    logging.debug(
                        f"权限验证通过: 用户 {auth_username} 可以访问其学校账户 {username}"
                    )

        # 尝试从新路径加载密码和 UA
        auth_username_local = getattr(self, "auth_username", None)
        password = None
        ua = None
        if auth_username_local:
            accounts = self._load_user_school_accounts(auth_username_local)
            account_info = accounts.get(username)
            if account_info:
                password = account_info.get("password")
                ua = account_info.get("ua")

        # 如果没有找到，使用默认值
        if password is None:
            password = ""
        if ua is None:
            ua = self.device_ua or ""

        logging.debug(
            f"on_user_selected: username={username}, ua={ua}, password={'***' if password else 'empty'}"
        )

        info = {"name": self.user_data.name,
                "student_id": self.user_data.student_id}

        return {
            "password": password or "",
            "ua": ua,
            "params": self.params,
            "userInfo": info,
        }

    def generate_new_ua(self):
        """生成一个新的UA并保存"""
        logging.info("API调用: generate_new_ua - 生成新的随机User-Agent字符串")
        self.device_ua = _main().ApiClient.generate_random_ua()
        try:
            cfg = _main()._read_config_ini(self.user_config_path)
            if cfg is None:
                cfg = _main()._get_default_config()
            if not cfg.has_section("System"):
                cfg.add_section("System")
            cfg.set("System", "UA", self.device_ua)
            _main()._write_config_with_comments(cfg, self.user_config_path)
        except Exception as e:
            logging.warning(f"保存 UA 到配置文件 {self.user_config_path} 失败: {e}")
        logging.info(f"已成功生成新的User-Agent字符串: {self.device_ua}")
        return self.device_ua

    @staticmethod
    def _apply_login_profile_to_user_data(user_data, data):
        """将学校登录响应中的用户资料同步到 UserData。"""
        data = data if isinstance(data, dict) else {}
        user_info = data.get("userInfo", {})
        dept_info = data.get("deptInfo", {})
        user_info = user_info if isinstance(user_info, dict) else {}
        dept_info = dept_info if isinstance(dept_info, dict) else {}

        def first_non_empty(*values):
            for value in values:
                if value is None:
                    continue
                if isinstance(value, str) and not value.strip():
                    continue
                return value
            return ""

        profile_fields = {
            "name": first_non_empty(
                user_info.get("name"),
                dept_info.get("name"),
                getattr(user_data, "name", ""),
            ),
            "phone": first_non_empty(
                user_info.get("phone"),
                dept_info.get("phone"),
                getattr(user_data, "phone", ""),
            ),
            "student_id": first_non_empty(
                user_info.get("account"),
                dept_info.get("studentNum"),
                dept_info.get("account"),
                getattr(user_data, "student_id", ""),
            ),
            "id": first_non_empty(
                user_info.get("id"),
                dept_info.get("id"),
                getattr(user_data, "id", ""),
            ),
            "registration_time": first_non_empty(
                user_info.get("createtime"),
                dept_info.get("createtime"),
                getattr(user_data, "registration_time", ""),
            ),
            "first_login_time": first_non_empty(
                user_info.get("firstlogin"),
                dept_info.get("firstlogin"),
                getattr(user_data, "first_login_time", ""),
            ),
            "id_card": first_non_empty(
                user_info.get("iDcard"),
                dept_info.get("iDcard"),
                getattr(user_data, "id_card", ""),
            ),
            "current_login_time": first_non_empty(
                user_info.get("logintime"),
                dept_info.get("logintime"),
                getattr(user_data, "current_login_time", ""),
            ),
            "last_login_time": first_non_empty(
                dept_info.get("logintime"),
                user_info.get("logintime"),
                getattr(user_data, "last_login_time", ""),
            ),
            "school_name": first_non_empty(
                dept_info.get("schoolName"),
                getattr(user_data, "school_name", ""),
            ),
            "attribute_type": first_non_empty(
                dept_info.get("typeValue"),
                getattr(user_data, "attribute_type", ""),
            ),
            "avatar_url": first_non_empty(
                user_info.get("avatar"),
                dept_info.get("avatar"),
                getattr(user_data, "avatar_url", ""),
            ),
        }

        student_id = str(profile_fields["student_id"] or "").strip()
        profile_fields["username"] = (
            student_id
            or str(getattr(user_data, "username", "") or "").strip()
        )

        gender = ""
        for candidate in (
            dept_info.get("sexValue"),
            user_info.get("sex"),
            dept_info.get("sex"),
            getattr(user_data, "gender", ""),
        ):
            gender = _main()._normalize_gender_value(candidate)
            if gender:
                break
        if gender:
            profile_fields["gender"] = gender

        for field_name, value in profile_fields.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            setattr(user_data, field_name, value)

        return user_data

    def _persist_school_account_backup(
        self,
        username,
        user_info,
        dept_info,
        source="单账号登录",
    ):
        """将学校用户资料写入 school_accounts/{学号}_backup.json。"""
        username = str(username or "").strip()
        if not username:
            logging.warning("[%s] 备份 user_info 失败：无法确定用户名(学号)", source)
            return None
        if not _main().is_valid_school_username(username):
            logging.warning(
                "[%s] 备份 user_info 失败：学号必须是至少4位纯数字: %r",
                source,
                username,
            )
            return None

        try:
            os.makedirs(self.user_dir, exist_ok=True)
            try:
                stats = self._load_school_account_stats_from_ini(username)
            except Exception as exc:
                logging.warning(
                    "[%s] 读取账号 %s 的 INI 统计失败，备份统计将使用 0: %s",
                    source,
                    username,
                    exc,
                )
                stats = {}

            backup_data = {
                "userInfo": user_info if isinstance(user_info, dict) else {},
                "deptInfo": dept_info if isinstance(dept_info, dict) else {},
                "backup_timestamp": time.time(),
                "overdue_count": stats.get("overdue_count", 0),
                "completed_count": stats.get("completed_count", 0),
            }
            backup_filepath = os.path.join(
                self.user_dir, f"{username}_backup.json"
            )
            with open(backup_filepath, "w", encoding="utf-8") as file_obj:
                json.dump(backup_data, file_obj, indent=2, ensure_ascii=False)

            logging.info(
                "[%s] 已成功备份 user_info 到: %s "
                "(包含统计数据: overdue=%s, completed=%s)",
                source,
                backup_filepath,
                stats.get("overdue_count", 0),
                stats.get("completed_count", 0),
            )
            return backup_filepath
        except Exception as exc:
            logging.error(
                "[%s] 备份 user_info 失败，账号: %s, 错误: %s",
                source,
                username,
                exc,
                exc_info=True,
            )
            return None

    def _load_school_account_backup(self, username):
        """读取扁平和旧版嵌套目录中的账号资料备份。"""
        username = str(username or "").strip()
        if not username:
            return {}

        candidates = (
            os.path.join(self.user_dir, f"{username}_backup.json"),
            os.path.join(
                self.user_dir, username, f"{username}_backup.json"
            ),
        )
        for backup_filepath in candidates:
            if not os.path.exists(backup_filepath):
                continue
            try:
                with open(backup_filepath, "r", encoding="utf-8") as file_obj:
                    backup_data = json.load(file_obj)
                if isinstance(backup_data, dict):
                    return backup_data
            except Exception as exc:
                logging.warning(
                    "读取账号资料备份失败 %s: %s",
                    backup_filepath,
                    exc,
                )
        return {}

    def _get_school_account_gender_from_backup(self, username):
        backup_data = self._load_school_account_backup(username)
        user_info = backup_data.get("userInfo", {})
        dept_info = backup_data.get("deptInfo", {})
        user_info = user_info if isinstance(user_info, dict) else {}
        dept_info = dept_info if isinstance(dept_info, dict) else {}
        for candidate in (
            dept_info.get("sexValue"),
            user_info.get("sex"),
            dept_info.get("sex"),
        ):
            gender = _main()._normalize_gender_value(candidate)
            if gender:
                return gender
        return ""

    def login(self, username, password):
        logging.info(f"API调用: login - 用户登录请求，用户名: '{username}'")
        if not username or not password:
            return {"success": False, "message": "用户名和密码不能为空！"}

        self.log_and_notify_frontend("正在登录...")
        logging.debug(f"正在尝试为用户进行登录认证: 用户名={username}")
        self.user_data = _main().UserData()
        input_username = username
        if not self.device_ua:
            self.device_ua = _main().ApiClient.generate_random_ua()

        resp = self.api_client.login(input_username, password)
        if not resp or not resp.get("success"):
            msg = (
                resp.get("message", "未知错误")
                if resp
                else "网络连接失败，无法连接到学校服务器。"
            )
            self.log_and_notify_frontend(f"服务器反馈登录失败：{msg}")
            logging.warning(f"用户登录失败: {msg}")
            return {"success": False, "message": msg}

        self.log_and_notify_frontend("登录成功，正在解析用户信息...")
        data = resp.get("data", {})
        ud = self.user_data
        ud.username = input_username
        self._apply_login_profile_to_user_data(ud, data)
        self._persist_school_account_backup(
            ud.username,
            data.get("userInfo", {}),
            data.get("deptInfo", {}),
            source="单账号登录",
        )
        self._save_config(ud.username, password, self.device_ua)

        # 将密码和UA备份到旧版 INI 文件（兼容旧版本）
        try:
            if ud.username:
                self._save_school_account_password_to_ini(
                    ud.username,
                    password,
                    self.device_ua
                )
                logging.info(f"已将登录密码备份到 INI 文件: {ud.username}")
        except Exception as e:
            logging.error(f"备份密码到 INI 文件失败: {e}", exc_info=True)

        if hasattr(self, "auth_username") and self.auth_username:
            self._update_school_account_password(
                self.auth_username,
                ud.username,
                password,
                self.device_ua,
                login_verified=True,
            )
            logging.info(
                f"已更新认证用户 {self.auth_username} 的 school_account {ud.username} 密码和UA（登录验证成功）"
            )

        try:
            self._fetch_server_attendance_radius_if_needed(
                self.api_client, None)
        except Exception as e:
            self.log_and_notify_frontend(f"获取签到半径失败: {e}")
            logging.warning(
                f"Failed to fetch attendance radius post-login: {e}")

        self._first_center_done = False
        logging.info(
            f"Login successful: uid={ud.id}, name={ud.name}, sid={ud.student_id}"
        )
        if self.window:
            try:
                self.window.evaluate_js("refreshTasks()")
            except Exception:
                logging.debug(
                    "Attempt to trigger front-end refreshTasks failed (non-fatal)."
                )

        # [新版] 使用统一的线程管理机制启动账号刷新线程
        # 不再使用旧的 auto_refresh_thread，而是使用 account_refresh_threads 字典
        try:
            # 清除旧的停止标志（为了向后兼容）
            self.stop_auto_refresh.clear()

            # 检查是否已登录且有用户ID
            if self.user_data and self.user_data.id:
                # 规范化账号ID为字符串
                account_id = str(self.user_data.id)

                # 确保该账号有刷新线程
                # 这个函数会自动检查是否已有活跃线程，避免重复创建
                self._ensure_account_refresh_thread(account_id)

                logging.info(f"[单账号登录] 已为账号 {account_id} 确保刷新线程")
            else:
                logging.warning("[单账号登录] 无法启动刷新线程：用户未登录或无ID")
        except Exception as e:
            self.log_and_notify_frontend(f"启动自动刷新线程失败: {e}")
            logging.error(f"[单账号登录] 启动刷新线程失败: {e}", exc_info=True)

        user_info_dict = self._get_full_user_info_dict()
        user_info_dict["server_attendance_radius_m"] = self.server_attendance_radius_m

        self.login_success = True
        self.user_info = user_info_dict
        logging.info(
            f"会话状态已保存: login_success={self.login_success}, user_id={ud.id}"
        )

        cached_notifications = None
        try:
            logging.info("登录成功后预加载前5条通知...")
            notif_result = self.get_notifications(
                is_auto_refresh=False, request_limit=5, request_offset=0
            )
            if notif_result and notif_result.get("success"):
                cached_notifications = {
                    "notices": notif_result.get("notices", []),
                    "unreadCount": notif_result.get("unreadCount", 0),
                    "cached_at": time.time(),
                }
                self.cached_notifications = cached_notifications
                logging.info(
                    f"成功预加载并缓存 {len(cached_notifications['notices'])} 条通知"
                )
        except Exception as e:
            logging.warning(f"预加载通知失败（非致命错误）: {e}")

        # auth_group = getattr(self, "auth_group", "guest")
        # auth_group = auth_system.get_user_group( )

        login_map_payload = _main()._build_public_map_provider_frontend_payload(
            _main()._read_config_ini(self.config_path) or _main()._get_default_config(),
            session_id=getattr(self, "_web_session_id", None),
            username=getattr(self, "auth_username", None),
        )
        return {
            "success": True,
            "userInfo": user_info_dict,
            "ua": self.device_ua,
            "map_provider": login_map_payload["map_provider"],
            "map_providers": login_map_payload["map_providers"],
            "map_provider_key_bundle": login_map_payload["map_provider_key_bundle"],
            # "auth_group": auth_group,
            "cached_notifications": cached_notifications,
        }

    def logout(self):
        """处理注销逻辑"""
        logging.info("API调用: logout - 用户注销登出操作")
        self.log_and_notify_frontend("已注销。")
        logging.info("用户已成功登出，正在清除会话和状态数据")

        self.shutdown_session_runtime(reason="logout")

        self.login_success = False
        self.user_info = None

        self._init_state_variables()
        self._load_global_config()
        self.api_client.session = _main().requests.Session()
        return {"success": True}

    def load_tasks(self):
        """加载任务列表（增强：稳健去重 + 并发保护 + 离线模式支持）"""
        logging.info("API调用: load_tasks - 加载用户任务列表")

        if not self.user_data.id:
            if hasattr(self, "all_run_data") and self.all_run_data:
                logging.info(
                    f"load_tasks: 离线模式，返回已加载的 {len(self.all_run_data)} 个任务"
                )
                tasks_for_js = []
                for run in self.all_run_data:
                    task_dict = run.__dict__.copy()
                    task_dict["info_text"] = self._get_task_info_text(run)
                    tasks_for_js.append(task_dict)
                return {"success": True, "tasks": tasks_for_js}
            else:
                return {"success": False, "message": "用户未登录且无离线任务"}

        if not hasattr(self, "_load_tasks_lock"):
            self._load_tasks_lock = threading.RLock()
        if not hasattr(self, "_load_tasks_inflight"):
            self._load_tasks_inflight = False

        with self._load_tasks_lock:
            if self._load_tasks_inflight:
                logging.debug(
                    "load_tasks skipped: another refresh is in-flight.")
                tasks_for_js = []
                for run in self.all_run_data:
                    task_dict = run.__dict__.copy()
                    task_dict["info_text"] = self._get_task_info_text(run)
                    tasks_for_js.append(task_dict)
                return {"success": True, "tasks": tasks_for_js}

            self._load_tasks_inflight = True
            try:
                self.log_and_notify_frontend("正在获取任务列表...")
                logging.debug("正在从服务器获取任务运行列表数据")

                self.all_run_data = []
                seen_keys: set[str] = set()
                offset = 0
                dup_count = 0

                while True:
                    resp = self.api_client.get_run_list(
                        self.user_data.id, offset)
                    if not resp or not resp.get("success"):
                        self.log_and_notify_frontend("获取任务列表失败。")
                        logging.warning("从服务器获取任务列表失败")
                        break

                    tasks = resp.get("data", {}).get("errandList", [])
                    if not tasks:
                        break

                    for td in tasks:
                        eid = td.get("errandId") or ""
                        es = td.get("errandSchedule") or ""
                        st = td.get("startTime") or ""
                        et = td.get("endTime") or ""

                        unique_key = f"{eid}|{es}|{st}|{et}"

                        if unique_key in seen_keys:
                            dup_count += 1
                            continue
                        seen_keys.add(unique_key)

                        run = _main().RunData()
                        run.run_name = td.get("eName")

                        try:
                            run.status = int(td.get("isExecute") or 0)
                        except (TypeError, ValueError):
                            run.status = (
                                1 if str(td.get("isExecute")
                                         ).strip() == "1" else 0
                            )

                        run.errand_id = td.get("errandId")
                        run.errand_schedule = td.get("errandSchedule")
                        run.start_time = td.get("startTime")
                        run.end_time = td.get("endTime")
                        run.upload_time = td.get("updateTime")
                        self.all_run_data.append(run)

                    offset += len(tasks)
                    if len(tasks) < 10:
                        break

                self.log_and_notify_frontend(f"任务列表加载完毕，共 {len(self.all_run_data)} 项。")
                if dup_count > 0:
                    logging.info(
                        f"Task de-dup completed: {dup_count} duplicates skipped (robust key)."
                    )

                tasks_for_js = []
                for run in self.all_run_data:
                    task_dict = run.__dict__.copy()
                    task_dict["info_text"] = self._get_task_info_text(run)
                    tasks_for_js.append(task_dict)
                return {"success": True, "tasks": tasks_for_js}
            finally:
                self._load_tasks_inflight = False

    def _try_parse_dt(self, s):
        """
        (已重构为类方法)
        尝试将不同格式的时间字符串解析为 datetime，支持多种常见格式和值类型。失败返回 None。
        """
        if not s:
            return None
        try:
            if isinstance(s, (int, float)):
                ts = int(s)
                if ts > 1e12:
                    return datetime.datetime.fromtimestamp(ts / 1000.0)
                if ts > 1e9:
                    return datetime.datetime.fromtimestamp(ts / 1000.0)
                return datetime.datetime.fromtimestamp(ts)
            if s.isdigit():
                ts = int(s)
                if ts > 1e12:
                    return datetime.datetime.fromtimestamp(ts / 1000.0)
                if ts > 1e9:
                    return datetime.datetime.fromtimestamp(ts / 1000.0)
                return datetime.datetime.fromtimestamp(ts)
        except Exception:
            pass

        fmts = [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M",
        ]
        for f in fmts:
            try:
                return datetime.datetime.strptime(s, f)
            except Exception:
                continue
        try:
            txt = s.rstrip("Z").split("+")[0]
            return datetime.datetime.fromisoformat(txt)
        except Exception:
            pass
        return None

    def _get_task_time_state(self, run_data, ignore_time=None, now=None):
        """Return expired/not_started/active using the same rules for all modes."""
        if ignore_time is None:
            ignore_time = self.params.get("ignore_task_time", True)
        if now is None:
            now = datetime.datetime.now()

        end_dt = self._try_parse_dt(getattr(run_data, "end_time", ""))
        if end_dt:
            is_expired = (
                end_dt.date() < now.date() if ignore_time else end_dt < now
            )
            if is_expired:
                return "expired"

        start_dt = self._try_parse_dt(getattr(run_data, "start_time", ""))
        if start_dt:
            is_not_started = (
                now.date() < start_dt.date() if ignore_time else now < start_dt
            )
            if is_not_started:
                return "not_started"

        return "active"

    def _payment_required_for_overdue_gate(self):
        """Return whether overdue bills should block task execution.

        离线导入的任务（``is_offline_mode``）不涉及真实账号与计费，
        因此既不查欠费也不产生支付订单。
        """
        if getattr(self, "is_offline_mode", False):
            logging.info("[欠费检查] 当前为离线测试模式，跳过欠费拦截。")
            return False
        try:
            config = _main()._read_config_ini()
            if config is None:
                return True
            return config.getboolean(
                "Payment_Settings",
                "require_payment",
                fallback=True,
            )
        except Exception as e:
            logging.warning(
                f"[欠费检查] 读取付费配置失败，按付费模式处理: {e}"
            )
            return True

    def _current_auth_group(self):
        """当前登录用户所属权限组（无认证会话时按 guest 处理）。"""
        user = getattr(self, "auth_username", None)
        if not user:
            return "guest"
        try:
            if _main().auth_system:
                return _main().auth_system.get_user_group(user) or "guest"
        except Exception as e:
            logging.warning("[欠费检查] 获取用户权限组失败: %s", e)
        return "guest"

    def _user_can_bypass_overdue(self, auth_username=None):
        """是否拥有“绕过欠费”权限（bypass_overdue）。

        该权限默认仅管理员/超级管理员拥有，但可以通过用户管理单独授予普通
        用户；因此这里必须查权限而不是只看权限组。服务端始终以真实登录用户
        为准确认，前端传入的 bypass_overdue 只是“用户点了强制执行”的意图。
        """
        user = str(
            auth_username or getattr(self, "auth_username", "") or ""
        ).strip()
        if not user or user == "guest":
            return False
        try:
            if not _main().auth_system:
                return False
            return bool(
                _main().auth_system.check_permission(user, "bypass_overdue")
            )
        except Exception as e:
            logging.warning("[欠费检查] 校验 bypass_overdue 权限失败: %s", e)
            return False

    def _resolve_waive_charge(self, waive_requested):
        """“此次不计费”只允许管理员/超级管理员使用（服务端硬校验）。"""
        if not waive_requested:
            return False
        return self._current_auth_group() in ("admin", "super_admin")

    def _overdue_bypass_allowed(self, bypass_overdue_requested):
        """欠费闸门是否放行：必须同时具备权限与本次强制执行意图。"""
        if not bypass_overdue_requested:
            return False
        return self._user_can_bypass_overdue()

    def _get_task_info_text(self, run: _main().RunData) -> str:
        """根据任务状态生成一个简短的信息文本（增强：多格式时间解析、稳健回退）"""
        if run.status == 1:
            return "已完成"

        now = datetime.datetime.now()
        ignore_time = self.params.get("ignore_task_time", True)

        def try_parse_dt(s):
            """尝试将不同格式的时间字符串解析为 datetime，支持多种常见格式和值类型。失败返回 None。"""
            if not s:
                return None
            try:
                if isinstance(s, (int, float)):
                    ts = int(s)
                    if ts > 1e12:
                        return datetime.datetime.fromtimestamp(ts / 1000.0)
                    if ts > 1e9:
                        return datetime.datetime.fromtimestamp(ts / 1000.0)
                    return datetime.datetime.fromtimestamp(ts)
                if s.isdigit():
                    ts = int(s)
                    if ts > 1e12:
                        return datetime.datetime.fromtimestamp(ts / 1000.0)
                    if ts > 1e9:
                        return datetime.datetime.fromtimestamp(ts / 1000.0)
                    return datetime.datetime.fromtimestamp(ts)
            except Exception:
                pass

            fmts = [
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M",
            ]
            for f in fmts:
                try:
                    return datetime.datetime.strptime(s, f)
                except Exception:
                    continue
            try:
                txt = s.rstrip("Z").split("+")[0]
                return datetime.datetime.fromisoformat(txt)
            except Exception:
                pass
            return None

        if run.end_time:
            end_dt = self._try_parse_dt(run.end_time)
            if end_dt:
                if (ignore_time and end_dt.date() < now.date()) or (
                    not ignore_time and end_dt < now
                ):
                    return "已过期"

        if run.start_time:
            start_dt = self._try_parse_dt(run.start_time)
            if start_dt:
                if (ignore_time and now.date() < start_dt.date()) or (
                    not ignore_time and now < start_dt
                ):
                    return f"开始于: {start_dt.strftime('%Y-%m-%d')}"
            else:
                try:
                    s = str(run.start_time).strip()
                    if len(s) == 10 and s[4] == "-" and s[7] == "-":
                        sd = datetime.datetime.strptime(s, "%Y-%m-%d")
                        if (ignore_time and now.date() < sd.date()) or (
                            not ignore_time and now < sd
                        ):
                            return f"开始于: {sd.strftime('%Y-%m-%d')}"
                except (TypeError, ValueError):
                    pass

        if run.end_time:
            try:
                end_dt = self._try_parse_dt(run.end_time)
                if end_dt:
                    return f"截止: {end_dt.strftime('%Y-%m-%d')}"
            except Exception:
                pass

        return "进行中"

    def get_task_details(self, index):
        """获取指定任务的详细信息"""
        logging.info(f"API调用: get_task_details - 获取任务详细信息，任务索引: {index}")
        if not (0 <= index < len(self.all_run_data)):
            return {"success": False, "message": "无效的任务索引"}

        self.current_run_idx = index
        run_data = self.all_run_data[index]

        if run_data.details_fetched:
            task_dict = run_data.__dict__.copy()
            task_dict["target_range_m"] = self.target_range_m
            return {"success": True, "details": task_dict}

        self.log_and_notify_frontend(f"正在加载任务详情...")
        logging.debug(
            f"正在获取任务详细信息: 任务索引={index}, 任务名称={run_data.run_name}"
        )
        resp = self.api_client.get_run_details(
            run_data.errand_id, self.user_data.id, run_data.errand_schedule
        )

        if resp and resp.get("success"):
            details = resp.get("data", {}).get("errandDetail", {})
            run_data.target_points = [
                (float(p["lon"]), float(p["lat"]))
                for p in details.get("geoCoorList", [])
                if p.get("lon") is not None and p.get("lat") is not None
            ]
            run_data.target_point_names = "|".join(
                [p.get("name", "") for p in details.get("geoCoorList", [])]
            )

            if not run_data.target_points:
                logging.warning(
                    f"[警告] 任务 '{run_data.run_name}' (ScheduleID: {run_data.errand_schedule}) 未包含任何打卡点 (geoCoorList为空)。"
                )

            temp_coords = []
            walk_paths = details.get("walkPaths", [])
            if walk_paths:
                for i, seg in enumerate(walk_paths):
                    for pt in seg:
                        if (
                            isinstance(pt, list)
                            and len(pt) == 2
                            and pt[0] is not None
                            and pt[1] is not None
                        ):
                            try:
                                temp_coords.append(
                                    (float(pt[0]), float(pt[1])))
                            except (TypeError, ValueError):
                                logging.warning(
                                    f"Invalid coordinate in recommended path: {pt}"
                                )
                    if i < len(walk_paths) - 1:
                        temp_coords.append((0.0, 0.0))
            run_data.recommended_coords = temp_coords
            run_data.details_fetched = True
            self.log_and_notify_frontend("任务详情加载成功。")
            logging.debug(
                f"任务详情获取成功: 目标点数量={len(run_data.target_points)}, 推荐路径点数量={len(run_data.recommended_coords)}"
            )
            task_dict = run_data.__dict__.copy()
            task_dict["target_range_m"] = self.target_range_m
            return {"success": True, "details": task_dict}
        else:
            self.log_and_notify_frontend("获取任务详情失败。")
            logging.warning("从服务器获取任务详情失败")
            return {"success": False, "message": "获取任务详情失败"}

    def set_draft_path(self, coords):
        """接收前端手动绘制的草稿路径"""

        # 严格校验：拒绝 None, [], [[]] 或非列表类型
        if not coords or not isinstance(coords, list):
            logging.warning(f"API调用: set_draft_path - 拒绝空路径或非列表格式")
            return {"success": False, "message": "路径数据不能为空"}

        # 深度校验：确保列表中至少包含一个有效的字典元素，排除 [[]] 这种情况
        has_valid_item = any(isinstance(c, dict) and c for c in coords)
        if not has_valid_item:
            logging.warning(f"API调用: set_draft_path - 拒绝无效路径结构: {coords}")
            return {"success": False, "message": "路径中不包含有效坐标点"}

        coords_len = len(coords)
        logging.info(f"API调用: set_draft_path - 设置草稿路径，点数: {coords_len}")

        if not (0 <= self.current_run_idx < len(self.all_run_data)):
            logging.warning(
                f"set_draft_path 失败：任务索引无效 (Index: {self.current_run_idx}, List length: {len(self.all_run_data)})"
            )
            return {"success": False, "message": "未选择任务或任务列表已失效"}

        try:
            run = self.all_run_data[self.current_run_idx]

            draft_coords_list = []
            # 此时 coords 肯定为真且为列表，直接遍历
            for c in coords:
                if not isinstance(c, dict):
                    logging.warning(f"set_draft_path: 跳过无效的坐标点（非字典）: {c}")
                    continue

                lng = c.get("lng")
                lat = c.get("lat")

                if lng is None or lat is None:
                    logging.warning(
                        f"set_draft_path: 跳过无效的坐标点（缺少lng或lat）: {c}"
                    )
                    continue

                draft_coords_list.append((lng, lat, c.get("isKey", 0)))

            # 二次校验：如果过滤后没有有效点，也视为失败
            if not draft_coords_list:
                logging.warning("API调用: set_draft_path - 经校验后无有效坐标点")
                return {"success": False, "message": "路径中无有效坐标点"}

            run.draft_coords = draft_coords_list

            logging.debug(f"已成功设置草稿路径，包含 {len(run.draft_coords)} 个坐标点")
            return {"success": True}

        except IndexError:
            logging.error(
                f"set_draft_path 发生索引错误: Index {self.current_run_idx}, List length {len(self.all_run_data)}",
                exc_info=True,
            )
            return {"success": False, "message": "服务器内部错误：任务列表索引失效"}
        except (TypeError, KeyError) as e:
            logging.error(f"set_draft_path 发生数据结构错误: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"服务器内部错误：路径数据格式无效 ({e})",
            }
        except Exception as e:
            logging.error(f"set_draft_path 发生未知错误: {e}", exc_info=True)
            return {"success": False, "message": f"服务器内部错误: {e}"}

    def _calculate_distance_m(self, lon1, lat1, lon2, lat2):
        """
        使用Haversine公式精确计算两个GPS坐标点之间的距离（米）。
        """
        R = 6371000

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) *
            math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        return distance

    def _calculate_distances_vectorized(self, coords):
        """
        ✓ 使用NumPy向量化计算多个坐标点之间的距离（性能优化，问题#11）
        """
        if len(coords) < 2:
            return 0.0

        if _main().np is not None:
            try:
                lons = _main().np.array([c[0] for c in coords])
                lats = _main().np.array([c[1] for c in coords])

                delta_lons = _main().np.diff(lons)
                delta_lats = _main().np.diff(lats)

                lat1_rad = _main().np.radians(lats[:-1])
                lat2_rad = _main().np.radians(lats[1:])
                delta_lat_rad = _main().np.radians(delta_lats)
                delta_lon_rad = _main().np.radians(delta_lons)

                R = 6371000
                a = (
                    _main().np.sin(delta_lat_rad / 2) ** 2
                    + _main().np.cos(lat1_rad)
                    * _main().np.cos(lat2_rad)
                    * _main().np.sin(delta_lon_rad / 2) ** 2
                )
                c = 2 * _main().np.arctan2(_main().np.sqrt(a), _main().np.sqrt(1 - a))
                distances = R * c

                return _main().np.sum(distances)
            except Exception as e:
                logging.debug(f"[性能优化] NumPy向量化计算失败，回退到循环: {e}")

        total_dist = 0.0
        for i in range(len(coords) - 1):
            total_dist += self._calculate_distance_m(
                coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1]
            )
        return total_dist

    def _gps_random_offset(self, lon, lat, params):
        """
        对GPS坐标添加随机偏移，模拟真实GPS的漂移误差。
        """
        m = params["location_random_m"]
        return (
            lon + random.uniform(-m, m) / 102834.74,
            lat + random.uniform(-m, m) / 111712.69,
        )

    def process_path(self):
        """
        处理草稿路径，生成带有时间戳的模拟运动轨迹。
        """
        logging.info("API调用: process_path - 处理路径，生成模拟运动轨迹")

        if self.current_run_idx == -1:
            return {"success": False, "message": "未选择任务"}

        run = self.all_run_data[self.current_run_idx]

        if not run.draft_coords or len(run.draft_coords) < 2:
            return {"success": False, "message": "没有可处理的路径"}

        self.log_and_notify_frontend("正在处理路径...")
        logging.debug(
            f"正在处理路径: 将 {len(run.draft_coords)} 个草稿点转换为运动坐标序列"
        )

        draft = run.draft_coords
        run.run_coords = []

        # ===== 步骤1：处理起点 =====
        start_lon, start_lat = draft[0][0], draft[0][1]
        lon, lat = (
            (start_lon, start_lat)
            if draft[0][2] == 1
            else self._gps_random_offset(start_lon, start_lat, self.params)
        )
        run.run_coords.append((lon, lat, 0))

        total_dist, total_time = 0.0, 0.0
        current_gps_pos, draft_idx = (draft[0][0], draft[0][1]), 0
        p = self.params

        speed_history = []
        speed_window = 3

        while draft_idx < len(draft) - 1:
            interval_t = max(
                0.2,
                random.uniform(
                    p["interval_ms"] - p["interval_random_ms"],
                    p["interval_ms"] + p["interval_random_ms"],
                )
                / 1000.0,
            )

            raw_speed = max(
                0.2,
                random.uniform(
                    p["speed_mps"] - p["speed_random_mps"],
                    p["speed_mps"] + p["speed_random_mps"],
                ),
            )

            speed_history.append(raw_speed)
            if len(speed_history) > speed_window:
                speed_history.pop(0)
            speed = sum(speed_history) / len(speed_history)

            dist_to_go = speed * interval_t

            final_pos, temp_draft_idx = current_gps_pos, draft_idx
            while dist_to_go > 0 and temp_draft_idx < len(draft) - 1:
                seg_start_gps, seg_end_gps = final_pos, (
                    draft[temp_draft_idx + 1][0],
                    draft[temp_draft_idx + 1][1],
                )
                seg_dist = self._calculate_distance_m(
                    seg_start_gps[0], seg_start_gps[1], seg_end_gps[0], seg_end_gps[1]
                )

                if seg_dist >= dist_to_go:
                    ratio = dist_to_go / seg_dist if seg_dist > 0 else 0
                    final_pos = (
                        seg_start_gps[0] + ratio *
                        (seg_end_gps[0] - seg_start_gps[0]),
                        seg_start_gps[1] + ratio *
                        (seg_end_gps[1] - seg_start_gps[1]),
                    )
                    dist_to_go, draft_idx = 0, temp_draft_idx
                else:
                    dist_to_go -= seg_dist
                    final_pos = seg_end_gps
                    temp_draft_idx += 1
                    if draft[temp_draft_idx][2] == 1:
                        dist_to_go = 0

            if dist_to_go > 0:
                final_pos = (draft[-1][0], draft[-1][1])
            draft_idx, current_gps_pos = temp_draft_idx, final_pos

            epsilon = 1e-9
            is_key_point = any(
                abs(d[0] - final_pos[0]) < epsilon
                and abs(d[1] - final_pos[1]) < epsilon
                and d[2] == 1
                for d in draft
            )
            lon, lat = (
                (final_pos[0], final_pos[1])
                if is_key_point
                else self._gps_random_offset(final_pos[0], final_pos[1], self.params)
            )

            if len(run.run_coords) > 0:
                prev_coord = run.run_coords[-1]
                segment_dist = self._calculate_distance_m(
                    prev_coord[0], prev_coord[1], lon, lat
                )
                total_dist += segment_dist

            run.run_coords.append((lon, lat, int(interval_t * 1000)))
            total_time += interval_t

        run.total_run_time_s, run.total_run_distance_m = total_time, total_dist
        self.log_and_notify_frontend(f"处理完成。")
        logging.info(
            f"路径处理完成: 生成坐标点数={len(run.run_coords)}, 总距离={total_dist:.1f}米, 总时长={total_time:.1f}秒"
        )
        return {
            "success": True,
            "run_coords": run.run_coords,
            "total_dist": total_dist,
            "total_time": total_time,
        }

    def check_target_reached_during_run(
        self, run_data: _main().RunData, current_lon: float, current_lat: float
    ):
        """
        在模拟运行时，检查当前位置是否到达了打卡点。
        """
        if not (0 <= run_data.target_sequence < len(run_data.target_points)):
            logging.debug(
                f"打卡点检查跳过: target_sequence={run_data.target_sequence}, total_points={len(run_data.target_points)}"
            )
            return

        tar_lon, tar_lat = run_data.target_points[run_data.target_sequence]

        dist = self._calculate_distance_m(
            current_lon, current_lat, tar_lon, tar_lat
        )

        is_in_zone = dist < self.target_range_m

        logging.debug(
            f"打卡点检查: 当前位置=({current_lon:.6f}, {current_lat:.6f}), "
            f"目标点{run_data.target_sequence+1}(索引{run_data.target_sequence})=({tar_lon:.6f}, {tar_lat:.6f}), "
            f"距离={dist:.2f}米, 范围={self.target_range_m:.2f}米, "
            f"在范围内={is_in_zone}, 已在区域内={run_data.is_in_target_zone}"
        )

        if is_in_zone and not run_data.is_in_target_zone:
            run_data.is_in_target_zone = True

            while 0 <= run_data.target_sequence < len(run_data.target_points):
                current_target_lon, current_target_lat = run_data.target_points[
                    run_data.target_sequence
                ]
                current_dist = self._calculate_distance_m(
                    current_lon, current_lat, current_target_lon, current_target_lat
                )

                if current_dist < self.target_range_m:
                    if (
                        run_data.suppress_last_target_until_finish
                        and run_data.target_sequence == len(run_data.target_points) - 1
                        and run_data.current_point_index < len(run_data.run_coords)
                    ):
                        logging.debug(
                            "抑制最后打卡点提前完成: 当前尚未跑到轨迹终点"
                        )
                        break
                    logging.info(
                        f"✓ 到达打卡点 {run_data.target_sequence+1}/{len(run_data.target_points)}"
                    )
                    run_data.target_sequence += 1
                else:
                    break

        elif not is_in_zone and run_data.is_in_target_zone:
            run_data.is_in_target_zone = False
            logging.debug(
                f"离开打卡点 {run_data.target_sequence}（索引{run_data.target_sequence-1}）区域"
            )

    def start_single_run(
        self, bypass_overdue: bool = False, waive_charge: bool = False
    ):
        """开始执行单个任务

        bypass_overdue: 存在欠费时是否按“强制执行”继续（需有 bypass_overdue 权限）
        waive_charge:   本次执行是否不计费（仅管理员/超级管理员生效）
        """
        logging.info("API调用: start_single_run - 开始执行单个任务")

        # ============================================================
        # [安全加固] 欠费检查：防止单账号模式绕过欠费限制
        # ============================================================
        # 检查当前是否已登录学校账号
        # 这一步骤确保只有无欠费的账号才能启动任务，防止欠费用户通过单账号模式绕过限制
        if not self.user_data or not self.user_data.username:
            # 如果没有登录或无用户信息，也应该拒绝启动任务
            # 这是另一层安全保障，防止未认证用户启动任务
            logging.warning("[欠费检查] 未登录或无用户信息，拒绝启动任务")
            return {
                "success": False,
                "message": "请先登录后再启动任务"
            }

        if self._payment_required_for_overdue_gate():
            # 获取当前登录的学校账号用户名
            school_username = self.user_data.username

            # 从账单文件读取该账号待支付账单数量作为欠费次数
            overdue_count = _main()._count_pending_bills_for_school(school_username)

            # 如果存在欠费（overdue_count > 0），拒绝启动任务
            # 这是关键的安全检查点，防止欠费用户继续使用服务
            if overdue_count > 0 and not self._overdue_bypass_allowed(
                bypass_overdue
            ):
                logging.warning(
                    f"[欠费检查] 账号 {school_username} 存在欠费 ({overdue_count} 次)，拒绝启动单个任务"
                )
                # 返回错误信息，包含欠费详情
                return {
                    "success": False,  # 操作失败
                    "message": "当前账号存在欠费，请先缴费后再启动任务",  # 用户友好的错误提示
                    "error_code": "OVERDUE_PAYMENT",  # 错误代码，前端可以据此做特殊处理
                    "overdue_accounts": [  # 欠费账号列表（单账号模式下只有一个）
                        {
                            "school_username": school_username,  # 欠费账号的用户名
                            "overdue_count": overdue_count  # 欠费次数
                        }
                    ]
                }

        # 本次执行的计费豁免状态（仅管理员可用；不请求豁免时重置为 False）。
        self.waive_charge_active = self._resolve_waive_charge(waive_charge)

        # 通过欠费检查后，原子占用单账号执行槽
        with self.single_execution_lock:
            if not self.stop_run_flag.is_set():
                return {"success": False, "message": "已有任务在运行"}
            if (
                self.current_run_idx == -1
                or not self.all_run_data[self.current_run_idx].run_coords
            ):
                return {"success": False, "message": "请选择任务并生成路线"}

            execution_token, conflict_identity = (
                self._claim_single_school_account_execution()
            )
            if execution_token is None:
                return {
                    "success": False,
                    "message": (
                        f"学校账号 {conflict_identity or self.user_data.username} "
                        "已在单账号或多账号模式中执行任务"
                    ),
                }

            self.stop_run_flag.clear()
            run_data = self.all_run_data[self.current_run_idx]
            run_data.target_sequence = 0
            run_data.is_in_target_zone = False
            self._first_center_done = False

            logging.info(f"正在启动单任务执行: 任务名称={run_data.run_name}")
            submission_thread = threading.Thread(
                target=self._run_with_single_school_account_execution,
                args=(
                    execution_token,
                    self._run_submission_thread,
                    (run_data, self.current_run_idx, self.api_client, False),
                ),
                daemon=True,
            )
            try:
                submission_thread.start()
            except Exception:
                self._release_single_school_account_execution(execution_token)
                self.stop_run_flag.set()
                raise
        logging.info(f"[Thread Creation] Starting submission thread: {submission_thread.name}")
        logging.info(f"[Thread Creation] Submission thread started: {submission_thread.name} (id={submission_thread.ident})")
        return {"success": True}

    def stop_run(self):
        """停止当前所有正在执行的任务"""
        logging.info("API调用: stop_run - 停止当前所有正在执行的任务")
        self.log_and_notify_frontend("正在停止任务...")
        logging.info("已收到停止运行任务的信号")
        self.stop_run_flag.set()
        # 停止后清掉“此次不计费”状态，下一次启动必须重新明确申请豁免。
        self.waive_charge_active = False
        return {"success": True}

    def get_run_status(self):
        """获取当前运行状态（用于前端轮询）"""
        is_running = not self.stop_run_flag.is_set()

        if not is_running or self.current_run_idx == -1:
            return {"running": False}

        run_data = self.all_run_data[self.current_run_idx]
        total_points = len(run_data.run_coords) if run_data.run_coords else 0

        processed_points = getattr(run_data, "current_point_index", 0)
        processed_points = min(processed_points, total_points)

        current_position = None
        if processed_points > 0 and processed_points <= total_points:
            coord = run_data.run_coords[processed_points - 1]
            current_position = {"lon": coord[0], "lat": coord[1]}

        return {
            "running": True,
            "processed_points": processed_points,
            "total_points": total_points,
            "distance_covered": run_data.distance_covered_m,
            "target_sequence": run_data.target_sequence,
            "duration": (
                sum(p[2] for p in run_data.run_coords[:processed_points])
                if processed_points > 0
                else 0
            ),
            "current_position": current_position,
        }

    def _submit_chunk(
        self,
        run_data: _main().RunData,
        chunk,
        start_time,
        is_finish,
        chunk_start_index,
        client: _main().ApiClient,
        user: _main().UserData,
    ):
        """将一小块轨迹数据提交到服务器"""
        log_func = (
            client.app.log_and_notify_frontend if hasattr(
                client.app, "log_and_notify_frontend") else client.app.api_bridge.log_and_notify_frontend
        )

        if self.is_offline_mode:
            log_func(f"[离线测试模式] 模拟提交 {len(chunk)} 个GPS点...")
            logging.info(
                f"[离线测试模式] 模拟提交 chunk: start_index={chunk_start_index}, size={len(chunk)}, is_finish={is_finish}"
            )
            time.sleep(0.1)
            return True

        log_func(f"正在提交数据...")
        logging.debug(
            f"Submitting chunk: start_index={chunk_start_index}, size={len(chunk)}, is_finish={is_finish}"
        )

        last_point_gps = (
            chunk[0]
            if chunk_start_index == 0
            else run_data.run_coords[chunk_start_index - 1]
        )
        time_elapsed_before_chunk_ms = sum(
            p[2] for p in run_data.run_coords[:chunk_start_index]
        )
        coords_list, chunk_total_dist, chunk_total_dur = [], 0.0, 0

        for lon, lat, dur_ms in chunk:
            distance = self._calculate_distance_m(
                last_point_gps[0], last_point_gps[1], lon, lat
            )
            time_elapsed_before_chunk_ms += dur_ms
            coords_list.append(
                {
                    "location": f"{lon},{lat}",
                    "locatetime": int(time.time() * 1000),
                    "dis": round(distance, 1),
                    "count": int(time_elapsed_before_chunk_ms / 1000),
                }
            )
            last_point_gps = (lon, lat, dur_ms)
            chunk_total_dist += distance
            chunk_total_dur += dur_ms

        current_ts_ms = int(time.time() * 1000)
        payload = {
            "scheduleId": run_data.errand_schedule,
            "userId": user.id,
            "userName": user.name or "",
            "runLength": str(int(chunk_total_dist)),
            "runTime": chunk_total_dur,
            "startPoint": "",
            "endPoint": "",
            "imgUrl": getattr(user, "avatar_url", "") or "",
            "startTime": int(start_time) if start_time else current_ts_ms,
            "endTime": current_ts_ms,
            "trid": run_data.trid,
            "sid": "",
            "tid": "",
            "speed": "0",
            "finishType": "1" if is_finish else "0",
            "coordinate": json.dumps(coords_list, separators=(",", ":")),
        }

        payload_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

        logging.debug(
            f"[{user.student_id}] 正在入队提交数据包, 大小: {len(payload_str)} 字节"
        )

        resp = self._enqueue_submission(client, payload_str, wait_timeout=60.0)
        success = bool(resp and resp.get("success"))

        msg = resp.get("message") if resp else "请求无响应或超时"
        if not success:
            log_func(f"数据提交失败: {msg}")
            logging.error(f"[{user.student_id}] 数据提交失败详情: {resp}")
        else:
            log_func(f"数据提交成功。")
            logging.debug(f"[{user.student_id}] 数据提交成功: {msg}")

        return success

    # ===================== 提交队列：串行化所有数据包提交 =====================
    @staticmethod
    def _submission_worker_static(submission_queue, stop_event):
        """后台工作线程：从队列取出提交任务并串行执行。(静态方法，防止绑定实例)"""
        current_thread = threading.current_thread()
        logging.info(
            f"[SubmissionWorker] Worker 在线程中启动: Thread[{current_thread.name}, id={current_thread.ident}]"
        )
        logging.warning(
            "[SubmissionWorker] 此 worker 运行在 threading.Thread 中，而非 eventlet greenlet"
        )
        logging.debug(
            "[SubmissionWorker] 提交队列工作线程已启动"
        )  # [修正] 改为DEBUG级别，防止启动时刷屏

        while not stop_event.is_set():
            try:
                # 1. 获取任务
                try:
                    task = submission_queue.get(timeout=1.0)
                except queue.Empty:  # 使用 queue.Empty 捕获超时
                    continue
                except Exception as e:
                    logging.warning(f"[SubmissionWorker] 队列获取异常: {e}")
                    time.sleep(1)
                    continue

                # 2. 执行任务
                try:
                    # logging.debug("[SubmissionWorker] 正在处理一个提交任务...") # 减少日志噪音

                    client = task.get("client")
                    payload_str = task.get("payload")

                    if client and payload_str:
                        resp = client.submit_run_track(payload_str)
                        task["response"] = resp
                        # logging.debug(f"[SubmissionWorker] 提交完成: {bool(resp and resp.get('success'))}")
                    else:
                        task["response"] = {
                            "success": False,
                            "message": "Invalid task data",
                        }

                except Exception as e:
                    logging.error(
                        f"[SubmissionWorker] 任务执行内部错误: {e}", exc_info=True
                    )
                    task["response"] = None
                finally:
                    # 3. 通知完成
                    try:
                        if "event" in task and task["event"]:
                            task["event"].set()
                    except Exception:
                        pass
                    try:
                        submission_queue.task_done()
                    except Exception:
                        pass

                # 避免CPU空转，虽有队列阻塞，但保留微小延时更稳健
                time.sleep(0.01)

            except Exception as outer_e:
                logging.critical(
                    f"[SubmissionWorker] 线程主循环发生未捕获异常: {outer_e}",
                    exc_info=True,
                )
                time.sleep(5)  # 出错后冷却，防止死循环刷日志

    def _enqueue_submission(
        self, client: _main().ApiClient, payload_str: str, wait_timeout: float = 30.0
    ):
        """将一次提交加入全局队列，并等待结果返回。
        返回值：与 ApiClient.submit_run_track 一致的响应字典，或 None（失败/超时）。
        """
        task = {
            "client": client,
            "payload": payload_str,
            "event": threading.Event(),
            "response": None,
        }
        try:
            qsize = self._submission_queue.qsize()
            logging.debug(
                f"Enqueue submit task. Queue size before push: {qsize}")
        except Exception:
            pass
        self._submission_queue.put(task)
        signaled = task["event"].wait(timeout=wait_timeout)
        if not signaled:
            logging.warning("提交队列等待超时。")
            return None
        return task.get("response")

    def _finalize_run(
        self,
        run_data: _main().RunData,
        task_index: int,
        client: _main().ApiClient,
        school_username: str = None,
        auth_username: str = None,
    ) -> bool:
        """
        在所有数据提交后，查询服务器确认任务是否已标记为完成。

        参数:
            school_username: 本次任务对应的学校账号。多账号模式必须显式传入，
                否则结算会回退到 client.app.user_data 并取到空值，
                导致出现"跳过结算"与"计入完成数"口径不一致的日志。
            auth_username: 认证（系统）用户名，缺省时从 api_instance 推断。
        """
        log_func = (
            client.app.log_and_notify_frontend if hasattr(
                client.app, "log_and_notify_frontend") else client.app.api_bridge.log_and_notify_frontend
        )
        log_func("正在确认任务状态...")
        logging.debug(f"正在确认任务完成状态，任务追踪ID: trid={run_data.trid}")
        for _ in range(3):
            resp = client.get_run_info_by_trid(run_data.trid)
            if resp and resp.get("success"):
                record_map = resp.get("data", {}).get("recordMap", {})
                if record_map and record_map.get("status") == 1:
                    run_data.status = 1
                    log_func("任务已确认完成。")
                    logging.info(f"任务已成功完成: 任务名称={run_data.run_name}")

                    # ========== 任务完成后处理可用次数扣减或欠费次数增加 ==========
                    # 在任务成功执行完成后，需要根据用户的可用次数进行扣减或记录欠费
                    # 这里处理单账号模式下的后台任务完成情况
                    try:
                        # ========== 解析认证用户名与学校账号 ==========
                        # 认证用户名（平台账号）：优先显式传入，其次取 api_instance 的属性
                        resolved_auth_username = (
                            auth_username
                            if auth_username is not None
                            else getattr(self, "auth_username", None)
                        )

                        # 学校账号：优先使用调用方显式传入的值。
                        # 多账号模式下 client.app.user_data 指向平台会话而不是
                        # 本次任务的学校账号，回退链会取到空值，于是日志把跳过
                        # 结算的原因错误地归结为"游客或未设置"。
                        resolved_school_username = school_username
                        if not resolved_school_username:
                            bound_user_data = getattr(
                                getattr(client, "app", None),
                                "user_data",
                                None,
                            )
                            resolved_school_username = getattr(
                                bound_user_data,
                                "username",
                                "",
                            ) or getattr(self.user_data, "username", None)

                        auth_username = resolved_auth_username
                        school_username = resolved_school_username

                        # 只有当两者都存在且认证用户不是游客时，才执行扣减逻辑
                        if auth_username and auth_username != "guest" and school_username:
                            logging.debug(
                                f"[单账号后台任务] 任务完成，开始处理次数扣减：认证用户={auth_username}, "
                                f"学校账号={school_username}, 任务={run_data.run_name}"
                            )

                            # 调用 api_instance 的辅助函数处理可用次数扣减或欠费次数增加
                            self._deduct_available_runs_or_increment_overdue(
                                auth_username, school_username
                            )

                            # ========== 增加已完成任务计数器 ==========
                            # 在任务成功提交并完成后，增加该学校账号的已完成任务计数
                            # 这个计数器用于统计每个学校账号总共完成了多少个任务
                            # 无论用户的可用次数是否充足，只要任务成功完成就增加计数
                            try:
                                logging.debug(
                                    f"[单账号后台任务] 开始增加任务计数：认证用户={auth_username}, "
                                    f"学校账号={school_username}, 任务={run_data.run_name}"
                                )

                                # 调用 api_instance 的辅助函数增加已完成任务计数
                                self._increment_completed_count(
                                    auth_username, school_username)

                            except Exception as e_count:
                                # 捕获计数更新异常，记录日志但不影响主流程
                                logging.error(
                                    f"[单账号后台任务] 更新任务计数时发生异常: {e_count}",
                                    exc_info=True
                                )
                            # ========== 结束：任务计数处理 ==========
                        else:
                            # 明确区分"游客/未设置认证用户"与"未取到学校账号"，
                            # 避免出现"跳过扣减"与"计入完成数"口径不一致却看不出原因
                            missing_fields = []
                            if not auth_username:
                                missing_fields.append("认证用户为空")
                            elif auth_username == "guest":
                                missing_fields.append("认证用户为游客")
                            if not school_username:
                                missing_fields.append("学校账号为空")
                            logging.warning(
                                f"[单账号后台任务] 跳过次数扣减：认证用户={auth_username!r}, "
                                f"学校账号={school_username!r}, "
                                f"原因={'/'.join(missing_fields) or '未知'}"
                            )
                    except Exception as e:
                        # 捕获异常，避免影响主流程
                        logging.error(
                            f"[单账号后台任务] 处理次数扣减时发生异常: {e}",
                            exc_info=True
                        )

                    session_id = getattr(self, "_web_session_id", None)
                    if _main().socketio and session_id and task_index != -1:
                        try:
                            current_thread = threading.current_thread()
                            logging.info(f"[SocketIO Emit] Sending 'task_completed' from Thread[{current_thread.name}, id={current_thread.ident}]")
                            _main().socketio.emit(
                                "task_completed",
                                {"task_index": task_index},
                                room=session_id,
                            )
                            logging.info(f"[SocketIO Emit] 'task_completed' sent successfully")
                        except Exception as e:
                            current_thread = threading.current_thread()
                            logging.error(
                                f"SocketIO发送'task_completed'事件失败 from Thread[{current_thread.name}]: {e}")
                            logging.error(f"Error type: {type(e).__name__}")
                            logging.error(f"Full traceback: {traceback.format_exc()}")
                    return True
            time.sleep(1)
        log_func("暂未确认完成，请稍后刷新。")
        logging.warning(f"任务完成状态确认失败: 任务名称={run_data.run_name}")
        return False

    def _run_submission_thread(
        self,
        run_data: _main().RunData,
        task_index: int,
        client: _main().ApiClient,
        is_all: bool,
        finished_event: threading.Event | None = None,
    ):
        """模拟跑步和提交数据的主线程函数"""
        # 记录线程信息
        current_thread = threading.current_thread()
        logging.info(f"[Thread Entry] _run_submission_thread started in Thread[{current_thread.name}, id={current_thread.ident}]")
        
        log_func = (
            client.app.log_and_notify_frontend if hasattr(
                client.app, "log_and_notify_frontend") else client.app.api_bridge.log_and_notify_frontend
        )
        user_data = (
            client.app.user_data if hasattr(
                client.app, "user_data") else self.user_data
        )
        stop_flag = (
            client.app.stop_event
            if hasattr(client.app, "stop_event")
            else self.stop_run_flag
        )

        sio = getattr(_main(), "socketio", None)
        logging.info(f"[SocketIO Check] SocketIO object available: {sio is not None}")

        session_id = getattr(self, "_web_session_id", None)
        logging.info(f"[Session Check] Session ID: {session_id}")
        last_auto_save_time = time.time()

        try:
            log_func("开始执行任务。")
            logging.info(f"任务提交线程已启动: 任务名称={run_data.run_name} in Thread[{current_thread.name}]")

            run_data.trid = f"{user_data.student_id}{int(time.time() * 1000)}"
            start_time_ms = str(int(time.time() * 1000))
            run_data.distance_covered_m = 0.0
            run_data.current_point_index = 0
            run_data.suppress_last_target_until_finish = True
            last_point_gps = run_data.run_coords[0]
            submission_successful = True

            point_index = 0
            _exec_start_real = time.time()
            _exec_total_points = max(1, len(run_data.run_coords))
            _exec_target_time_s = float(getattr(run_data, "total_run_time_s", 0.0) or 0.0)
            if _exec_target_time_s <= 1.0:
                _exec_target_time_s = sum(max(0.0, d) / 1000.0 for _, _, d in run_data.run_coords)
            _exec_target_time_s = max(1.0, _exec_target_time_s)
            _exec_prefix_plan_s = [0.0]
            _exec_acc_plan_s = 0.0
            for _, _, _dur_ms in run_data.run_coords:
                _exec_acc_plan_s += max(0.0, _dur_ms) / 1000.0
                _exec_prefix_plan_s.append(_exec_acc_plan_s)
            _pid_kp = _main().PID_KP
            _pid_ki = _main().PID_KI
            _pid_kd = _main().PID_KD
            _pid_deadzone = _main().PID_DEADZONE
            _pid_integral = 0.0
            _pid_prev_error = 0.0
            _pid_deadzone_boost = 1.0

            for i in range(0, len(run_data.run_coords), 5):
                if stop_flag.is_set():
                    log_func("任务已中止。")
                    logging.info("检测到停止标志，正在中止任务运行")
                    break

                chunk = run_data.run_coords[i: i + 5]

                for lon, lat, dur_ms in chunk:
                    _elapsed_real_s = time.time() - _exec_start_real
                    _elapsed_real_min = _elapsed_real_s / 60.0
                    _actual_sleep_s = dur_ms / 1000.0
                    if True:
                        _planned_elapsed_s = min(
                            _exec_target_time_s,
                            _exec_prefix_plan_s[min(point_index, len(_exec_prefix_plan_s) - 1)],
                        )
                        _expected_frac = _planned_elapsed_s / _exec_target_time_s
                        _actual_frac = _elapsed_real_s / _exec_target_time_s
                        _progress_diff = _actual_frac - _expected_frac
                        _error = _progress_diff
                        _in_deadzone = abs(_error) <= _pid_deadzone
                        if _in_deadzone:
                            _pid_deadzone_boost = min(
                                _main().PID_DEADZONE_BOOST_MAX,
                                _pid_deadzone_boost + _main().PID_DEADZONE_BOOST_STEP,
                            )
                        else:
                            _pid_deadzone_boost = 1.0
                        _error_for_pid = _error
                        _pid_integral = max(
                            -_main().PID_INTEGRAL_LIMIT,
                            min(_main().PID_INTEGRAL_LIMIT, _pid_integral + _error_for_pid),
                        )
                        _pid_derivative = _error_for_pid - _pid_prev_error
                        _pid_prev_error = _error_for_pid
                        _pid_p_term = _pid_kp * _error_for_pid
                        _pid_i_term = _pid_ki * _pid_integral
                        _pid_d_term = _pid_kd * _pid_derivative
                        _pid_out = _pid_deadzone_boost * (
                            _pid_p_term
                            + _pid_i_term
                            + _pid_d_term
                        )
                        _sleep_ratio = max(0.35, min(1.70, 1.0 - _pid_out))
                        _actual_sleep_s = _actual_sleep_s * _sleep_ratio
                        if _error_for_pid > 0:
                            _remaining_s = max(1.0, _exec_target_time_s - _elapsed_real_s)
                            _remaining_pts = max(1, _exec_total_points - point_index)
                            _actual_sleep_s = min(_actual_sleep_s, _remaining_s / _remaining_pts)
                            logging.debug(
                                f"进度偏慢，PID自动加速: 实际时间进度={_actual_frac:.2%}, "
                                f"规划时间进度={_expected_frac:.2%}, 时间误差={_progress_diff:.2%}, "
                                f"实际累计={_elapsed_real_s:.1f}s, 规划累计={_planned_elapsed_s:.1f}s, "
                                f"P={_pid_p_term:.4f}, I={_pid_i_term:.4f}, D={_pid_d_term:.4f}, "
                                f"PID={_pid_out:.4f}, Boost={_pid_deadzone_boost:.2f}, "
                                f"新等待时间={_actual_sleep_s:.2f}s"
                            )
                        elif _error < 0:
                            logging.debug(
                                f"进度偏快，PID自动减速: 实际时间进度={_actual_frac:.2%}, "
                                f"规划时间进度={_expected_frac:.2%}, 时间误差={_progress_diff:.2%}, "
                                f"实际累计={_elapsed_real_s:.1f}s, 规划累计={_planned_elapsed_s:.1f}s, "
                                f"P={_pid_p_term:.4f}, I={_pid_i_term:.4f}, D={_pid_d_term:.4f}, "
                                f"PID={_pid_out:.4f}, Boost={_pid_deadzone_boost:.2f}, "
                                f"新等待时间={_actual_sleep_s:.2f}s"
                            )
                        else:
                            logging.debug(
                                f"进度正常(±{_pid_deadzone:.0%}): 实际时间进度={_actual_frac:.2%}, "
                                f"规划时间进度={_expected_frac:.2%}, 时间误差={_progress_diff:.2%}，"
                                f"实际累计={_elapsed_real_s:.1f}s, 规划累计={_planned_elapsed_s:.1f}s, "
                                f"P={_pid_p_term:.4f}, I={_pid_i_term:.4f}, D={_pid_d_term:.4f}, "
                                f"PID={_pid_out:.4f}, Boost={_pid_deadzone_boost:.2f}, "
                                f"等待时间={_actual_sleep_s:.2f}s"
                            )
                            
                    else:
                        logging.debug(f"正常执行: 已执行时间={_elapsed_real_min:.2f}分钟, 未接近目标时间，无需调整执行速度。")

                    if stop_flag.wait(timeout=_actual_sleep_s):
                        logging.debug("等待下一个坐标点时被停止信号中断")
                        break

                    run_data.distance_covered_m += self._calculate_distance_m(
                        last_point_gps[0], last_point_gps[1], lon, lat
                    )
                    last_point_gps = (lon, lat, dur_ms)
                    point_index += 1
                    run_data.current_point_index = point_index
                    self.check_target_reached_during_run(run_data, lon, lat)

                    current_session_id = session_id
                    if not current_session_id and hasattr(client, "app"):
                        current_session_id = getattr(
                            client.app, "_web_session_id", None
                        )

                    if current_session_id and (time.time() - last_auto_save_time >= 30):
                        try:
                            if (
                                hasattr(_main(), "web_sessions_lock")
                                and hasattr(_main(), "web_sessions")
                            ):
                                with _main().web_sessions_lock:
                                    if current_session_id in _main().web_sessions:
                                        _main().save_session_state(
                                            current_session_id,
                                            _main().web_sessions[current_session_id],
                                        )
                                        logging.debug(
                                            f"任务执行中自动保存会话状态 (进度: {point_index}/{len(run_data.run_coords)})"
                                        )
                                last_auto_save_time = time.time()
                        except Exception as e:
                            logging.error(f"任务执行中自动保存会话失败: {e}")

                    debug_sio_status = "存在" if sio else "缺失(None)"
                    debug_emit_cond = self.current_run_idx == task_index

                    logging.debug(
                        f"SocketIO状态检查 -> "
                        f"SIO对象: {debug_sio_status}, "
                        f"SessionID: {current_session_id}, "
                        f"任务匹配: {self.current_run_idx}=={task_index} ({debug_emit_cond})"
                    )
                    if sio and current_session_id:
                        should_emit = True

                if stop_flag.is_set():
                    break

                is_final_chunk = i + 5 >= len(run_data.run_coords)

                if not self._submit_chunk_with_retries(
                    run_data,
                    chunk,
                    start_time_ms,
                    is_final_chunk,
                    i,
                    client,
                    user_data,
                    stop_event=stop_flag,
                    log_func=log_func,
                ):
                    submission_successful = False
                    break

            if not stop_flag.is_set() and submission_successful:
                run_data.suppress_last_target_until_finish = False
                if run_data.target_points and run_data.target_sequence < len(run_data.target_points):
                    try:
                        end_lon, end_lat, _ = run_data.run_coords[-1]
                        self.check_target_reached_during_run(run_data, end_lon, end_lat)
                    except Exception:  # nosec B110 - 目标检查失败不影响主流程
                        pass
                log_func("任务执行完毕，等待确认...")
                logging.info("任务运行执行完毕，等待最终确认")
                time.sleep(3)
                self._finalize_run(run_data, task_index, client)

                if session_id:
                    try:
                        if (
                            hasattr(_main(), "web_sessions_lock")
                            and hasattr(_main(), "web_sessions")
                        ):
                            with _main().web_sessions_lock:
                                if session_id in _main().web_sessions:
                                    _main().save_session_state(
                                        session_id,
                                        _main().web_sessions[session_id],
                                        force_save=True,
                                    )
                                    logging.info(f"任务完成，已保存会话状态")
                    except Exception as e:
                        logging.error(f"任务完成后保存会话失败: {e}")

        finally:
            if not is_all:
                if not submission_successful or stop_flag.is_set():
                    self.stop_run_flag.set()
                    logging.info(f"任务停止或失败，设置停止标志")
                else:
                    self.stop_run_flag.set()
                    logging.info(f"任务正常完成，重置停止标志")

                session_id = getattr(self, "_web_session_id", None)
                if sio and session_id:
                    try:
                        current_thread = threading.current_thread()
                        logging.info(f"[SocketIO Emit] Sending 'run_stopped' from Thread[{current_thread.name}, id={current_thread.ident}]")
                        sio.emit("run_stopped", {}, room=session_id)
                        logging.info(f"[SocketIO Emit] 'run_stopped' sent successfully")
                    except Exception as e:
                        current_thread = threading.current_thread()
                        logging.error(f"SocketIO发送'run_stopped'运行停止事件失败 from Thread[{current_thread.name}]: {e}")
                        logging.error(f"Error type: {type(e).__name__}")
                        logging.error(f"Full traceback: {traceback.format_exc()}")

            if finished_event:
                finished_event.set()
            logging.info(
                f"Submission thread finished for task: {run_data.run_name}")

    def _submit_chunk_with_retries(
        self,
        run_data: _main().RunData,
        chunk,
        start_time,
        is_finish,
        chunk_start_index,
        client: _main().ApiClient,
        user: _main().UserData,
        *,
        stop_event: threading.Event,
        log_func,
        stop_predicate=None,
    ) -> bool:
        """使用统一重试语义提交单个轨迹数据块。"""
        max_attempts = 10
        for attempt in range(1, max_attempts + 1):
            if self._submit_chunk(
                run_data,
                chunk,
                start_time,
                is_finish,
                chunk_start_index,
                client,
                user,
            ):
                return True

            if stop_predicate and stop_predicate():
                return False

            if self.is_offline_mode:
                logging.error(
                    f"[离线测试模式] 模拟提交失败，尝试 {attempt}/{max_attempts}"
                )
                continue

            logging.warning(f"数据提交失败，重试 {attempt}/{max_attempts}")
            if stop_event.wait(timeout=1.0):
                log_func("检测到停止信号，已取消重试")
                return False
            if stop_predicate and stop_predicate():
                log_func("检测到停止信号，已取消重试")
                return False

        logging.error(
            f"数据提交在 {max_attempts} 次尝试后仍然失败，任务中止"
        )
        return False

    # ===================== 折返补距：真实道路网络随机折返 =====================
    DETOUR_PROBE_LIMIT = 6
    DETOUR_MAX_ROUNDS = 12
    DETOUR_MIN_LEG_DISTANCE_M = 20.0
    DETOUR_FALLBACK_MIN_BACK_M = 100.0
    # 拼接允许的最大缝隙：超过即视为会形成直线跳点而拒绝拼接
    DETOUR_MAX_SEAM_M = 45.0

    @staticmethod
    def _route_leg_is_rate_limited(path_result):
        text = str((path_result or {}).get("error") or "")
        return "上限" in text or "限流" in text or "too many" in text.lower()

    def _plan_detour_leg(
        self,
        start,
        end,
        *,
        session_id=None,
        python_params=None,
        app_base_url=None,
        guard_label="RouteDetour",
        log_func=None,
    ):
        """规划一段折返腿（真实道路网络），带进程内缓存。

        返回 {"geometry": [(lng, lat), ...], "distance_m": float, "provider": str} 或 None。
        """
        if session_id is None:
            return None
        start_coord = (float(start[0]), float(start[1]))
        end_coord = (float(end[0]), float(end[1]))
        if start_coord == end_coord:
            return {"geometry": [start_coord], "distance_m": 0.0, "provider": None}

        try:
            provider = _main()._get_active_map_provider()
        except Exception:  # nosec B110 - 供应商探测失败不阻断主流程
            provider = None

        cached = _detour_leg_cache_get(provider, start_coord, end_coord)
        if cached is not None:
            total = 0.0
            for i in range(len(cached) - 1):
                total += self._calculate_distance_m(
                    cached[i][0], cached[i][1], cached[i + 1][0], cached[i + 1][1]
                )
            return {
                "geometry": cached,
                "distance_m": total,
                "provider": provider,
                "cached": True,
            }

        try:
            result = _main()._plan_route_path_with_provider_runtime(
                session_id,
                [list(start_coord), list(end_coord)],
                python_params=python_params,
                guard_label=guard_label,
                app_base_url=app_base_url,
            )
        except Exception as e:  # noqa: BLE001 - 折返腿失败必须降级而不是中断
            logging.warning(f"[折返规划] 路段规划异常: {e}")
            return None

        if not isinstance(result, dict) or "path" not in result:
            if self._route_leg_is_rate_limited(result):
                logging.warning(
                    "[折返规划] 路段规划被限流: "
                    f"{result.get('error') if isinstance(result, dict) else result}"
                )
            else:
                logging.debug(
                    "[折返规划] 路段规划失败: "
                    f"{result.get('error') if isinstance(result, dict) else result}"
                )
            return None

        geometry = _detour_dedupe_points(result.get("path") or [])
        if len(geometry) < 2:
            return None

        total = 0.0
        for i in range(len(geometry) - 1):
            total += self._calculate_distance_m(
                geometry[i][0], geometry[i][1], geometry[i + 1][0], geometry[i + 1][1]
            )
        if total <= 0:
            return None

        provider_name = result.get("provider") or provider
        _detour_leg_cache_put(provider_name, start_coord, end_coord, geometry)
        return {
            "geometry": geometry,
            "distance_m": total,
            "provider": provider_name,
            "cached": False,
        }

    def _build_route_path_with_random_detours(
        self,
        base_path,
        waypoints,
        target_dist_m,
        *,
        session_id,
        python_params=None,
        app_base_url=None,
        guard_label="RouteDetour",
        log_func=None,
    ):
        """主路线不足目标距离时，从距终点 50 m 处开始按真实道路网络随机折返补距。

        约束：
        - 折返点沿用既有语义（``total_len - 50``，路线 < 100 m 时取 2/3 处）。
        - 条件随机：只在同时满足「附加距离 >= DETOUR_MIN_LEG_DISTANCE_M」与
          「累计长度不越过 target_dist_m」的打卡点中随机挑选，且不连续重复同一打卡点。
        - 所有打卡点都不满足时回退：在真实道路网络上取一个沿路里程距折返点
          > DETOUR_FALLBACK_MIN_BACK_M 的点作为折返目标。
        - 返回几何路径的累计长度恰好等于 ``target_dist_m``（收尾精确截断），
          以保证 ``_get_point_at_distance`` 的末点不会饱和、模拟时长不超时。
        """

        def _log(message):
            if not log_func:
                return
            try:
                log_func(message)
            except Exception:  # nosec B110 - 日志失败不影响规划
                pass

        base = _detour_dedupe_points(base_path)
        if len(base) < 2:
            return list(base)

        cumulative = [0.0]
        for i in range(len(base) - 1):
            cumulative.append(
                cumulative[-1]
                + self._calculate_distance_m(
                    base[i][0], base[i][1], base[i + 1][0], base[i + 1][1]
                )
            )
        total_len = cumulative[-1]
        if total_len <= 0 or total_len >= target_dist_m:
            return base

        # ---- 折返点：距路线终点 50 m（路线 < 100 m 时取 2/3） ----
        if total_len >= 100.0:
            near_d = max(0.0, total_len - 50.0)
        else:
            near_d = total_len * 2.0 / 3.0
        turn_idx = bisect.bisect_left(cumulative, near_d)
        turn_idx = max(0, min(turn_idx, len(base) - 1))
        turn_point = base[turn_idx]
        final_path = base[: turn_idx + 1]
        added = sum(
            self._calculate_distance_m(
                final_path[i][0], final_path[i][1], final_path[i + 1][0], final_path[i + 1][1]
            )
            for i in range(len(final_path) - 1)
        )

        normalized_waypoints = _detour_dedupe_points(waypoints)
        if len(normalized_waypoints) < 2:
            return self._get_path_for_distance(base, cumulative, target_dist_m)
        dest = normalized_waypoints[-1]
        self._detour_base_length_m = total_len

        def _leg_distance(geometry):
            total = 0.0
            for i in range(len(geometry) - 1):
                total += self._calculate_distance_m(
                    geometry[i][0], geometry[i][1], geometry[i + 1][0], geometry[i + 1][1]
                )
            return total

        def _append_leg(geometry):
            nonlocal added
            leg = _detour_dedupe_points(geometry)
            if len(leg) < 2:
                return 0.0
            if final_path and final_path[-1] == leg[0]:
                leg = leg[1:]
            if not leg:
                return 0.0
            if final_path:
                seam = self._calculate_distance_m(
                    final_path[-1][0],
                    final_path[-1][1],
                    leg[0][0],
                    leg[0][1],
                )
                # 拒绝会制造跳点/直线段的拼接（折返各腿都首尾相连，正常不会触发）
                if seam > self.DETOUR_MAX_SEAM_M:
                    logging.warning(
                        f"[折返规划] 跳过 seam={seam:.1f}m 的拼接段，避免生成直线跳点"
                    )
                    return 0.0
            gain = _leg_distance([final_path[-1]] + leg) if final_path else _leg_distance(leg)
            final_path.extend(leg)
            added += gain
            return gain

        _log(
            f"主路线 {total_len:.0f}m 不足目标 {target_dist_m:.0f}m，"
            f"从距终点 {total_len - near_d:.0f}m 处开始按实际道路网络随机折返"
        )

        rounds = 0
        last_pick = None
        fallback_used = False
        while added + 1.0 < target_dist_m and rounds < self.DETOUR_MAX_ROUNDS:
            rounds += 1
            remaining = target_dist_m - added

            # ---------- 条件随机：候选打卡点 ----------
            picks, stats = self._select_detour_candidates(
                turn_point,
                normalized_waypoints,
                dest,
                remaining,
                session_id=session_id,
                python_params=python_params,
                app_base_url=app_base_url,
                guard_label=f"{guard_label}Probe",
                log_func=_log,
            )
            if last_pick is not None and len(picks) > 1:
                picks = [item for item in picks if item["waypoint"] != last_pick] or picks

            appended = False
            if picks:
                chosen = random.choice(picks)  # nosec B311 - 模拟路径随机选点，非安全用途
                last_pick = chosen["waypoint"]
                _log(
                    f"第 {rounds} 轮随机折返：选中打卡点 {chosen['label']}"
                    f"（往返约 {chosen['round_trip_m']:.0f}m，"
                    f"符合条件 {chosen['viable_total']} 个 / 已探测 {stats['probed']} 个）"
                )
                if self._append_detour_round(
                    final_path,
                    chosen,
                    target_dist_m,
                    session_id=session_id,
                    python_params=python_params,
                    app_base_url=app_base_url,
                    guard_label=f"{guard_label}Loop",
                    log_func=_log,
                    append_leg=_append_leg,
                ):
                    appended = True

            if not appended:
                # ---------- 回退：所有打卡点都不符合条件 ----------
                if not fallback_used:
                    _log(
                        "折返候选筛选：已探测 "
                        f"{stats['probed']} 个打卡点，满足最小距离 "
                        f"{stats['min_distance_ok']} 个，超出可用额度 "
                        f"{stats['over_budget']} 个，不可达 {stats['unreachable']} 个"
                    )
                fallback = self._fallback_detour_point(
                    base,
                    cumulative,
                    near_d,
                    target_dist_m,
                    budget_m=target_dist_m - added,
                )
                if fallback is None:
                    _log(f"第 {rounds} 轮折返无可选目标，改用沿主路线整圈循环兜底")
                    break
                if not fallback_used:
                    _log(
                        "所有打卡点均不符合条件，回退为在道路网络上取距折返点 "
                        f"{fallback['back_m']:.0f}m 处折返"
                    )
                    fallback_used = True
                before = len(final_path)
                fallback_candidate = self._build_fallback_detour_candidate(
                    final_path,
                    fallback,
                    dest,
                    base,
                    target_dist_m - added,
                    session_id=session_id,
                    python_params=python_params,
                    app_base_url=app_base_url,
                    guard_label=f"{guard_label}Fallback",
                )
                if fallback_candidate:
                    self._append_detour_round(
                        final_path,
                        fallback_candidate,
                        target_dist_m,
                        session_id=session_id,
                        python_params=python_params,
                        app_base_url=app_base_url,
                        guard_label=f"{guard_label}FallbackLoop",
                        log_func=_log,
                        append_leg=_append_leg,
                    )
                if len(final_path) == before:
                    break

            added = self._path_length(final_path)

        # ---- 兜底：折返不可用或轮次用尽时，沿主路线整圈循环凑足距离 ----
        if added + 1.0 < target_dist_m:
            fill_cumulative = [0.0]
            for i in range(len(final_path) - 1):
                fill_cumulative.append(
                    fill_cumulative[-1]
                    + self._calculate_distance_m(
                        final_path[i][0],
                        final_path[i][1],
                        final_path[i + 1][0],
                        final_path[i + 1][1],
                    )
                )
            final_path = self._get_path_for_distance(
                final_path, fill_cumulative, target_dist_m
            )

        # ---- 收尾：长度不超过 target_dist_m，且末点落在最后一个打卡点 ----
        return self._finalize_detoured_path(final_path, target_dist_m, dest)

    def _finalize_detoured_path(self, path, target_dist_m, dest):
        """收尾：长度不超过 ``target_dist_m``，且不低于主路线长度，末点尽量落在终点。"""
        result = self._finalize_detoured_path_inner(path, target_dist_m, dest)
        floor = self._detour_length_floor()
        if floor > 0 and self._path_length(result) < floor:
            cleaned = _detour_dedupe_points(path)
            if len(cleaned) >= 2:
                return cleaned
        return result

    def _finalize_detoured_path_inner(self, path, target_dist_m, dest):
        """收尾：长度不超过 ``target_dist_m``，末点尽量落在最后一个打卡点。

        折返每圈都按额度精确拼装并落在最后一个打卡点，正常情况无需处理；
        只有兜底循环或浮点偏差会超出，此时压掉尾部并把末点接回最后一个打卡点
        （收尾段长度不超过路网点距，不会形成跳点或直线）。
        """
        cleaned = _detour_dedupe_points(path)
        if len(cleaned) < 2:
            return cleaned
        dest_coord = (float(dest[0]), float(dest[1])) if dest else None
        if dest_coord is None:
            if self._path_length(cleaned) > target_dist_m + 0.5:
                trimmed = self._trim_to_target(cleaned, target_dist_m)
                return trimmed if len(trimmed) >= 2 else cleaned
            return cleaned

        if cleaned[-1] == dest_coord:
            if self._path_length(cleaned) <= target_dist_m + 0.5:
                return cleaned
            fitted = self._fit_tail_to_dest(cleaned, target_dist_m, dest_coord)
            if len(fitted) >= 2:
                return self._enforce_target_length(fitted, target_dist_m)
            return self._enforce_target_length(cleaned, target_dist_m)

        # 末点不是终点：先截到目标距离，再尝试把末点接回终点
        if self._path_length(cleaned) > target_dist_m + 0.5:
            trimmed = self._trim_to_target(cleaned, target_dist_m)
            if len(trimmed) >= 2:
                cleaned = trimmed
        fitted = self._fit_tail_to_dest(cleaned, target_dist_m, dest_coord)
        if len(fitted) >= 2 and self._path_length(fitted) >= self._detour_length_floor():
            return self._enforce_target_length(fitted, target_dist_m)
        gap = self._calculate_distance_m(
            cleaned[-1][0], cleaned[-1][1], dest_coord[0], dest_coord[1]
        )
        if gap <= self.DETOUR_MAX_SEAM_M:
            return self._enforce_target_length(cleaned + [dest_coord], target_dist_m)
        return self._enforce_target_length(cleaned, target_dist_m)

    def _detour_length_floor(self):
        """折返结果允许的最小长度：不得低于主路线长度。"""
        return float(getattr(self, "_detour_base_length_m", 0.0) or 0.0)

    def _enforce_target_length(self, path, target_dist_m):
        """硬性保证：返回路径不超过目标距离（超出则按累计里程截断）。"""
        points = _detour_dedupe_points(path)
        if len(points) < 2:
            return points
        if self._path_length(points) <= target_dist_m + 0.5:
            return points
        trimmed = self._trim_to_target(points, target_dist_m)
        if len(trimmed) < 2:
            return points
        if self._path_length(trimmed) < self._detour_length_floor():
            return points
        return trimmed

    def _route_cumulative(self, points):
        """返回路径的累计里程表（与 ``points`` 等长）。"""
        cumulative = [0.0]
        for i in range(len(points) - 1):
            cumulative.append(
                cumulative[-1]
                + self._calculate_distance_m(
                    points[i][0],
                    points[i][1],
                    points[i + 1][0],
                    points[i + 1][1],
                )
            )
        return cumulative

    def _point_at_cumulative(self, points, cumulative, dist):
        """按累计里程取路径上的点（段内线性插值）。"""
        if not points:
            return None
        if dist <= 0:
            return points[0]
        if dist >= cumulative[-1]:
            return points[-1]
        idx = bisect.bisect_left(cumulative, dist)
        d0, d1 = cumulative[idx - 1], cumulative[idx]
        ratio = (dist - d0) / (d1 - d0) if d1 > d0 else 0.0
        s, e = points[idx - 1], points[idx]
        return (
            s[0] + (e[0] - s[0]) * ratio,
            s[1] + (e[1] - s[1]) * ratio,
        )

    def _fit_tail_to_dest(self, path, target_dist_m, dest_coord):
        """让路径在不超过目标距离的前提下尽量贴近，并尽量落在 ``dest_coord``。

        - 路径已落在终点：直接按累计里程精确截断（含插值），长度最贴近目标；
        - 未落在终点：沿累计里程定位「到终点收尾段」的起点后再接回终点。
        """
        points = _detour_dedupe_points(path)
        if len(points) < 2:
            return []
        if points[-1] == dest_coord:
            # 已落在终点且超出预算：优先精确截断；若因此丢失终点，
            # 则在「保留终点」的候选里取长度更贴近目标的一个。
            # 结果绝不低于入参长度（折返只允许增加里程，不允许倒退）。
            candidates = []
            trimmed = self._trim_to_target(points, target_dist_m)
            if len(trimmed) >= 2 and trimmed[-1] == dest_coord:
                return trimmed
            if len(trimmed) >= 2:
                candidates.append(trimmed)
            for cut in range(len(points) - 1, 0, -1):
                head = points[:cut]
                gap = self._calculate_distance_m(
                    head[-1][0], head[-1][1], dest_coord[0], dest_coord[1]
                )
                shortened = self._trim_to_target(head, target_dist_m - gap)
                if len(shortened) >= 2:
                    candidates.append(shortened + [dest_coord])
            if not candidates:
                return trimmed if len(trimmed) >= 2 else []
            best = max(candidates, key=self._path_length)
            # 折返只允许增加里程：压缩结果不得低于主路线长度，
            # 也不得低于入参长度（否则等于把已走的折返又删掉）。
            floor = max(self._detour_length_floor(), self._path_length(points))
            if self._path_length(best) < floor:
                return points
            return best

        gap_to_dest = self._calculate_distance_m(
            points[-1][0], points[-1][1], dest_coord[0], dest_coord[1]
        )

        cumulative = self._route_cumulative(points)
        want = max(0.0, target_dist_m - gap_to_dest)
        if want >= cumulative[-1]:
            return points + [dest_coord]

        idx = bisect.bisect_left(cumulative, want)
        if idx <= 0:
            return [points[0], dest_coord]
        anchor = self._point_at_cumulative(points, cumulative, want)
        head = points[:idx]
        if anchor is not None and anchor != head[-1]:
            head = head + [anchor]
        if len(head) < 1:
            return []
        return head + [dest_coord]
    def _trim_to_target(self, path, target_dist_m):
        """把几何路径按累计长度截断到 ``target_dist_m``（不足则原样返回）。

        末尾落在割点处并按需线性插值；若目标距离小到连第一段都放不下，
        则返回 ``[]``（调用方据此放弃截断，绝不返回会制造跳点的短前缀）。
        """
        path = _detour_dedupe_points(path)
        if len(path) < 2 or target_dist_m <= 0:
            return []

        def _seg(a, b):
            return self._calculate_distance_m(a[0], a[1], b[0], b[1])

        result = [path[0]]
        accumulated = 0.0
        for i in range(1, len(path)):
            segment = _seg(path[i - 1], path[i])
            if accumulated + segment > target_dist_m:
                need = target_dist_m - accumulated
                if need > 0 and segment > 0:
                    ratio = need / segment
                    result.append(
                        (
                            path[i - 1][0] + (path[i][0] - path[i - 1][0]) * ratio,
                            path[i - 1][1] + (path[i][1] - path[i - 1][1]) * ratio,
                        )
                    )
                return result
            result.append(path[i])
            accumulated += segment
        return result

    def _truncate_path_to_target(self, path, target_dist_m, dest=None):
        """兼容入口：与 ``_finalize_detoured_path`` 行为一致。"""
        return self._finalize_detoured_path(path, target_dist_m, dest)

    def _select_detour_candidates(
        self,
        turn_point,
        waypoints,
        dest,
        budget_m,
        *,
        session_id,
        python_params=None,
        app_base_url=None,
        guard_label="RouteDetour",
        log_func=None,
    ):
        """按「条件随机」筛选打卡点，返回符合约束的候选列表。

        条件：
        1. 不能超时：``round_trip <= budget_m``（budget_m 为本轮可用额度，
           等价于累计长度不越过 target_dist_m，也就是不超过 min_d_m * 1.15）。
        2. 满足最小距离：单次折返往返里程 >= ``DETOUR_MIN_LEG_DISTANCE_M``。

        返回 ``(viable, stats)``；``viable`` 内每项含 ``out_leg`` / ``loop_leg`` /
        ``round_trip_m``，供调用方按预算做贪心多圈追加。
        """
        viable = []
        seen = set()
        stats = {
            "probed": 0,
            "min_distance_ok": 0,
            "over_budget": 0,
            "unreachable": 0,
            "budget_m": budget_m,
        }

        ranked = []
        for index, point in enumerate(waypoints):
            straight = self._calculate_distance_m(
                turn_point[0], turn_point[1], point[0], point[1]
            )
            ranked.append((straight, index, point))
        # 直线距离最远的优先探测：更可能提供足够折返里程
        ranked.sort(key=lambda item: item[0], reverse=True)
        probe_pool = ranked[: self.DETOUR_PROBE_LIMIT]
        # 全部候选都满足条件时，「随机」应覆盖全部打卡点而非只有最远的几个
        full_pool = ranked

        for pool in (probe_pool, full_pool):
            for straight, index, point in pool:
                if point == turn_point or point in seen:
                    continue
                seen.add(point)

                stats["probed"] += 1
                out_leg = self._plan_detour_leg(
                    turn_point,
                    point,
                    session_id=session_id,
                    python_params=python_params,
                    app_base_url=app_base_url,
                    guard_label=guard_label,
                )
                if not out_leg:
                    stats["unreachable"] += 1
                    continue
                back_leg = self._plan_detour_leg(
                    point,
                    dest,
                    session_id=session_id,
                    python_params=python_params,
                    app_base_url=app_base_url,
                    guard_label=guard_label,
                )
                if not back_leg:
                    stats["unreachable"] += 1
                    continue

                round_trip = out_leg["distance_m"] + back_leg["distance_m"]
                if round_trip < self.DETOUR_MIN_LEG_DISTANCE_M:
                    continue
                stats["min_distance_ok"] += 1
                # 只要「折返点到打卡点」这一段能在本轮额度内走完就可用：
                # 返程段允许在收尾时于段内截断，因此不需要整往返都塞进额度。
                if out_leg["distance_m"] > budget_m + 1.0:
                    stats["over_budget"] += 1
                    continue
                viable.append(
                    {
                        "waypoint": point,
                        "label": f"打卡点 {index + 1}",
                        "out_leg": out_leg,
                        "loop_leg": back_leg,
                        "dest": dest,
                        "round_trip_m": round_trip,
                        "viable_total": 0,  # 稍后回填
                    }
                )
            if viable:
                break

        for item in viable:
            item["viable_total"] = len(viable)
        return viable, stats

    def _append_detour_round(
        self,
        final_path,
        chosen,
        target_dist_m,
        *,
        session_id,
        python_params,
        app_base_url,
        guard_label,
        log_func,
        append_leg,
    ):
        """按选中打卡点追加「折返点 -> 打卡点 -> 最后一个打卡点」往返。

        在「本轮剩余额度」内精确拼装，且**每一圈的末点都落在最后一个打卡点**：
        - 额度够走完整往返时多圈追加；
        - 只剩部分额度时，走完去程后沿返程段几何推进，不够则以**很短的收尾段**
          接回最后一个打卡点（收尾段长度小于路网点距，不产生可见直线）。
        """
        out_leg = chosen["out_leg"]
        loop_leg = chosen["loop_leg"]
        dest_point = chosen["dest"]
        round_trip = chosen["round_trip_m"]
        if round_trip <= 0:
            return False

        current_length = self._path_length(final_path)
        budget = target_dist_m - current_length
        # 允许「部分往返」：只要本轮额度内至少能走出最小折返里程，就值得折返
        if min(round_trip, budget) + 1.0 < self.DETOUR_MIN_LEG_DISTANCE_M:
            return False

        applied = False
        rounds = max(1, min(int(budget // round_trip), self.DETOUR_MAX_ROUNDS))
        for _ in range(rounds):
            remaining = budget - (self._path_length(final_path) - current_length)
            if remaining <= 0:
                break
            out_gain = append_leg(out_leg["geometry"])
            if out_gain <= 0:
                break

            # 返程段：能整段走完就整段走完
            tail_start = final_path[-1]
            loop_geometry = _detour_dedupe_points(loop_leg["geometry"])
            closing_gap = self._calculate_distance_m(
                tail_start[0], tail_start[1], dest_point[0], dest_point[1]
            )
            if self._path_length(final_path) + loop_leg["distance_m"] <= target_dist_m + 0.5:
                append_leg(loop_geometry)
                applied = True
                continue

            if remaining <= closing_gap + 1.0:
                # 剩余额度不足以走完返程：直接以短收尾段接回最后一个打卡点
                append_leg([tail_start, dest_point])
                applied = True
                break

            # 沿返程段几何推进，把「到终点的收尾距离」压到最短
            accumulated = 0.0
            tail = [loop_geometry[0]]
            tail_end = loop_geometry[0]
            for i in range(1, len(loop_geometry)):
                step = self._calculate_distance_m(
                    loop_geometry[i - 1][0],
                    loop_geometry[i - 1][1],
                    loop_geometry[i][0],
                    loop_geometry[i][1],
                )
                gap_here = self._calculate_distance_m(
                    loop_geometry[i][0], loop_geometry[i][1], dest_point[0], dest_point[1]
                )
                if accumulated + step + gap_here > remaining:
                    break
                accumulated += step
                tail.append(loop_geometry[i])
                tail_end = loop_geometry[i]
            if len(tail) >= 2:
                append_leg(tail)
            append_leg([tail_end, dest_point])
            applied = True
            break
        return applied

    def _fallback_detour_point(self, base, cumulative, turn_along, target_dist_m, budget_m=None):
        """回退目标：在真实道路网络上取沿路里程距折返点 > 100 m 的点。

        ``budget_m`` 给定时，优先在「本轮额度内可达」的点中随机挑选，避免一次性
        大幅越过目标距离而被迫砍掉大段路径。
        """
        if len(base) < 2:
            return None
        options = []
        for i, point in enumerate(base):
            along = cumulative[i] if i < len(cumulative) else 0.0
            back_m = abs(along - turn_along)
            if back_m <= self.DETOUR_FALLBACK_MIN_BACK_M:
                continue
            options.append((back_m, i, point))
        if not options:
            return None
        if budget_m is not None and budget_m > 0:
            within = [item for item in options if item[0] <= budget_m + 1.0]
            if within:
                options = within
        back_m, index, point = random.choice(options)  # nosec B311 - 模拟路径随机选点
        return {"index": index, "point": point, "back_m": back_m}

    def _build_fallback_detour_candidate(
        self,
        final_path,
        fallback,
        dest,
        reference_path,
        budget_m,
        *,
        session_id,
        python_params,
        app_base_url,
        guard_label,
    ):
        """构造回退折返候选：沿真实道路前往回退点，再返回最后一个打卡点。"""
        dest_point = (float(dest[0]), float(dest[1]))
        point = fallback["point"]
        out_leg = self._plan_detour_leg(
            final_path[-1],
            point,
            session_id=session_id,
            python_params=python_params,
            app_base_url=app_base_url,
            guard_label=guard_label,
        )
        if not out_leg:
            # 规划不可用时退化为沿主路线既有几何行进（仍是道路网络，不做直线跳点）
            index = fallback["index"]
            if reference_path and 0 <= index < len(reference_path):
                geometry = _detour_dedupe_points(reference_path[: index + 1])
                if len(geometry) < 2:
                    return None
                total = self._path_length(geometry)
                out_leg = {"geometry": geometry, "distance_m": total, "provider": None}
            else:
                return None
        if out_leg["distance_m"] > budget_m + 1.0:
            return None

        loop_leg = self._plan_detour_leg(
            point,
            dest_point,
            session_id=session_id,
            python_params=python_params,
            app_base_url=app_base_url,
            guard_label=guard_label,
        )
        if not loop_leg:
            closing = self._calculate_distance_m(
                point[0], point[1], dest_point[0], dest_point[1]
            )
            if closing <= 0:
                return None
            loop_leg = {
                "geometry": [point, dest_point],
                "distance_m": closing,
                "provider": None,
            }
        return {
            "waypoint": point,
            "label": "道路网络回退点",
            "out_leg": out_leg,
            "loop_leg": loop_leg,
            "dest": dest_point,
            "round_trip_m": out_leg["distance_m"] + loop_leg["distance_m"],
            "viable_total": 1,
        }

    def _path_length(self, path):
        total = 0.0
        for i in range(len(path) - 1):
            total += self._calculate_distance_m(
                path[i][0], path[i][1], path[i + 1][0], path[i + 1][1]
            )
        return total

    def _get_path_for_distance(self, path, cumulative_distances, target_dist):
        """兜底补距：沿主路线整圈循环凑足目标距离。

        说明：正常流程已由 ``_build_route_path_with_random_detours`` 处理（在距终点
        50 m 处开始按真实道路网络随机折返）；本方法只在折返候选全部不可用或折返轮次
        用尽时兜底调用，因此不再使用「最后 50~100 m 原地折返」的旧策略。
        """
        total_len = cumulative_distances[-1]
        final_path = list(path)
        if total_len <= 0 or total_len >= target_dist:
            return final_path

        def _append_if_new(pt):
            if not final_path or final_path[-1] != pt:
                final_path.append(pt)

        def _point_at(d):
            return self._get_point_at_distance(path, cumulative_distances, d)

        def _path_points_between(d_start, d_end):
            if d_start == d_end:
                return [_point_at(d_start)]
            if d_start > d_end:
                points = _path_points_between(d_end, d_start)
                return list(reversed(points))

            idx_start = bisect.bisect_left(cumulative_distances, d_start)
            idx_end = bisect.bisect_left(cumulative_distances, d_end)
            points = []
            start_pt = _point_at(d_start)
            points.append(start_pt)
            for i in range(idx_start, idx_end):
                dist_i = cumulative_distances[i]
                if d_start < dist_i < d_end:
                    pt = path[i]
                    if pt != points[-1]:
                        points.append(pt)
            end_pt = _point_at(d_end)
            if end_pt != points[-1]:
                points.append(end_pt)
            return points

        def _append_path_between(d_start, d_end):
            for pt in _path_points_between(d_start, d_end):
                _append_if_new(pt)

        remaining = target_dist - total_len

        if total_len >= 100.0:
            near_d = max(0.0, total_len - 50.0)   # 最后50米点
            far_d = max(0.0, total_len - 100.0)   # 最后100米点
        else:
            far_d = total_len / 3.0               # 1/3 点
            near_d = total_len * 2.0 / 3.0        # 2/3 点

        if near_d <= far_d:
            # 兜底：保持 near 在 far 之后
            near_d = min(total_len, far_d + max(1e-6, total_len / 10.0))

        end_d = total_len
        step_a = end_d - near_d      # 末端 -> near
        step_b = near_d - far_d      # near <-> far
        if step_b <= 0:
            return final_path

        # 兜底策略：沿主路线整圈循环，避免旧版「最后 50~100 m 原地折返」的密集洄游。
        # 正常流程由 _build_route_path_with_random_detours 在距终点 50 m 处
        # 按真实道路网络随机折返处理，本分支只在折返候选全部不可用时生效。
        #
        # 逐圈按「剩余额度」追加；最后一圈只补部分时，用很短的收尾段接回终点，
        # 使总长贴近目标且不超过目标（避免采样饱和导致模拟距离与实际不符）。
        loop_gain = total_len
        if loop_gain <= 0:
            return final_path
        cycle = self._cycle_points(path)
        if len(cycle) < 2:
            return final_path
        cycle_len = self._path_length(cycle)
        if cycle_len <= 0:
            return final_path

        added_cycle = 0.0
        cycles = 0
        max_cycles = max(
            self.DETOUR_MAX_ROUNDS, int(math.ceil(remaining / loop_gain)) + 2
        )
        while added_cycle + 1.0 < remaining and cycles < max_cycles:
            cycles += 1
            budget = remaining - added_cycle
            if cycle_len <= budget:
                for pt in cycle[1:]:
                    _append_if_new(pt)
                added_cycle += cycle_len
                continue
            # 最后一圈：只补到刚好达到目标距离。收尾段必须落在最后一个打卡点，
            # 且回接段长度不得超过剩余额度。
            leftover = remaining - added_cycle
            tail = self._partial_cycle_to_dest(cycle, leftover, path[-1])
            if len(tail) >= 2:
                for pt in tail[1:]:
                    _append_if_new(pt)
                added_cycle += self._path_length(tail)
            break
        # 硬性约束：兜底路径也不得超过目标距离
        return self._enforce_target_length(final_path, target_dist)

    def _partial_cycle_to_dest(self, cycle, budget_m, dest_point):
        """在 ``budget_m`` 内取 ``cycle`` 的一段前缀，并用很短的收尾段接回终点。"""
        if budget_m <= 0 or len(cycle) < 2:
            return []
        cumulative = self._route_cumulative(cycle)
        idx = bisect.bisect_left(cumulative, budget_m)
        if idx <= 0:
            return []
        head = list(cycle[:idx])
        anchor = self._point_at_cumulative(cycle, cumulative, budget_m)
        if anchor is not None and anchor != head[-1]:
            head = head + [anchor]
        if len(head) < 2:
            return []
        return head + [dest_point]

    def _cycle_points(self, path):
        """返回「接续一整圈」的几何：末点 -> 路径起点 -> 原路径内部点。

        路线通常不是闭合环（起点与终点是不同打卡点），接续方式为直接回到路径
        起点再沿原路线走一遍。回接段直接用 ``path[0]``，不得插值或跳过，
        否则会制造跳点。
        """
        points = _detour_dedupe_points(path)
        if len(points) < 3:
            return []
        return [points[-1], points[0]] + list(points[1:])

    def _get_point_at_distance(self, path, cumulative_distances, dist):
        """在一条路径上，根据距离找到精确的坐标点"""
        idx = bisect.bisect_left(cumulative_distances, dist)
        if idx == 0:
            return path[0]
        if idx >= len(cumulative_distances):
            return path[-1]

        d0, d1 = cumulative_distances[idx - 1], cumulative_distances[idx]
        seg_len = d1 - d0
        ratio = (dist - d0) / seg_len if seg_len > 0 else 0
        s, e = path[idx - 1], path[idx]
        return (s[0] + (e[0] - s[0]) * ratio, s[1] + (e[1] - s[1]) * ratio)

    def auto_generate_path_with_api(self, api_path_coords, min_t_m, max_t_m, min_d_m, *, apply_result=True):
        """接收地图供应商规划好的路径点，并生成模拟数据"""
        logging.info(
            f"API CALL: auto_generate_path_with_api with {len(api_path_coords)} points"
        )
        if self.current_run_idx == -1:
            return {"success": False, "message": "请先选择任务"}
        run = self.all_run_data[self.current_run_idx]

        self.log_and_notify_frontend("收到地图路径规划结果，正在生成模拟数据...")
        logging.info(
            f"Auto-generating path from {len(api_path_coords)} map provider points."
        )
        if not api_path_coords or len(api_path_coords) < 2:
            return {"success": False, "message": "地图服务未能返回有效路径"}

        final_path_dedup = []
        last_coord = None
        for p in api_path_coords:
            longitude = p.get("lng", p.get("lon"))
            if longitude is None:
                continue
            coord = (longitude, p["lat"])
            if coord != last_coord:
                final_path_dedup.append(coord)
                last_coord = coord

        _plan_min_t_m = min_t_m * 1.02
        _plan_max_t_m = max_t_m * 0.98
        if _plan_max_t_m <= _plan_min_t_m:
            _plan_min_t_m, _plan_max_t_m = min_t_m, max_t_m
        target_time_s = random.uniform(_plan_min_t_m * 60, _plan_max_t_m * 60)  # nosec B311 - 用于跑步路径规划的随机参数，非安全用途
        target_dist_m = random.uniform(min_d_m, min_d_m * 1.15)  # nosec B311 - 用于跑步路径规划的随机参数，非安全用途

        final_geo_path = self._build_route_path_with_random_detours(
            final_path_dedup,
            run.target_points,
            target_dist_m,
            session_id=getattr(self, "_web_session_id", None),
            python_params=self.params,
            app_base_url=getattr(self, "_web_app_base_url", None),
            guard_label="SingleAutoGenerate",
            log_func=self.log_and_notify_frontend,
        )

        final_cumulative = [0.0]
        for i in range(len(final_geo_path) - 1):
            final_cumulative.append(
                final_cumulative[-1]
                + self._calculate_distance_m(
                    final_geo_path[i][0],
                    final_geo_path[i][1],
                    final_geo_path[i + 1][0],
                    final_geo_path[i + 1][1],
                )
            )

        actual_total_dist = final_cumulative[-1] if final_cumulative else 0.0
        if actual_total_dist == 0:
            return {"success": False, "message": "路径计算距离为0"}

        avg_speed = actual_total_dist / target_time_s
        run_coords = []
        if not final_geo_path:
            return {"success": False, "message": "无法生成地理路径"}

        start = final_geo_path[0]
        run_coords.append(
            (self._gps_random_offset(start[0], start[1], self.params) + (0,))
        )
        t_elapsed, d_covered = 0.0, 0.0

        while t_elapsed < target_time_s:
            interval = min(
                random.uniform(
                    self.params["interval_ms"] *
                    0.9, self.params["interval_ms"] * 1.1
                )
                / 1000.0,
                target_time_s - t_elapsed,
            )
            if interval <= 0.1:
                break

            d_covered = min(
                d_covered +
                random.uniform(avg_speed * 0.9, avg_speed * 1.1) * interval,
                actual_total_dist,
            )
            lon, lat = self._get_point_at_distance(
                final_geo_path, final_cumulative, d_covered
            )
            lon_o, lat_o = self._gps_random_offset(lon, lat, self.params)
            run_coords.append((lon_o, lat_o, int(interval * 1000)))
            t_elapsed += interval
            if d_covered >= actual_total_dist:
                break

        if apply_result:
            run.run_coords = run_coords
            run.total_run_time_s = t_elapsed
            run.total_run_distance_m = d_covered

        self.log_and_notify_frontend("自动生成完成。")
        logging.info(
            f"Auto-generated path: points={len(run_coords)}, dist={d_covered:.1f}, time={t_elapsed:.1f}"
        )
        return {
            "success": True,
            "run_coords": run_coords,
            "total_dist": d_covered,
            "total_time": t_elapsed,
        }

    def _notify_route_planning_failure(self, result, account=None, execution_id=None):
        summary = build_route_failure_summary(result)
        public_message = generic_route_failure_message(summary["diagnostic_id"])
        if account is not None:
            try:
                owner = getattr(self, "auth_username", None)
                if owner and _main().auth_system.get_user_group(owner) in ("admin", "super_admin"):
                    public_message = detailed_route_failure_message(summary)
            except Exception:
                pass
        elif execution_id is not None:
            manager = getattr(_main(), "background_task_manager", None)
            if manager:
                if manager.record_route_planning_failure(getattr(self, "_web_session_id", ""), summary, execution_id) is None:
                    return summary
        notifier = account if account is not None else self
        notifier.log_and_notify_frontend(
            "路径规划失败 [%s] [%s]: %s" % (summary["diagnostic_id"], summary["provider"], summary["message"]),
            frontend_message=public_message, diagnostic_id=summary["diagnostic_id"],
        )
        return summary

    def auto_generate_path_with_provider(self, min_t_m, max_t_m, min_d_m):
        """按当前地图供应商规划路线，并生成模拟数据。"""
        logging.info("API CALL: auto_generate_path_with_provider")
        if self.current_run_idx == -1:
            return {"success": False, "message": "请先选择任务"}

        run = self.all_run_data[self.current_run_idx]
        if not run.target_points or len(run.target_points) < 2:
            return {"success": False, "message": "请先选择一个有至少两个打卡点的任务"}

        session_id = getattr(self, "_web_session_id", None)
        if not session_id:
            summary = self._notify_route_planning_failure({"error": "当前会话缺少浏览器会话ID，无法执行路径规划"})
            return {"success": False, "message": generic_route_failure_message(summary["diagnostic_id"]), "diagnostic_id": summary["diagnostic_id"], "_route_failure": summary}

        self.log_and_notify_frontend("正在按当前地图供应商进行路径规划...")
        try:
            path_result = _main()._plan_route_path_with_provider_runtime(
                session_id,
                run.target_points,
                python_params=self.params,
                guard_label="SingleManualPathPlanning",
                app_base_url=getattr(self, "_web_app_base_url", None),
            )
        except Exception as exc:
            path_result = {"error": sanitize_diagnostic(exc)}
        if not isinstance(path_result, dict):
            path_result = {"error": "路径规划执行器返回无效结果"}
        notices = path_result.get("notices", [])
        if not path_result.get("path"):
            summary = self._notify_route_planning_failure(path_result)
            return {
                "success": False,
                "message": generic_route_failure_message(summary["diagnostic_id"]),
                "diagnostic_id": summary["diagnostic_id"],
                "_route_failure": summary,
                "provider": path_result.get("provider"),
                "notices": [],
            }
        for notice in notices:
            self.log_and_notify_frontend(sanitize_diagnostic(notice))

        self.log_and_notify_frontend(
            f"路径规划成功，共 {len(path_result['path'])} 个坐标点。正在生成模拟数据..."
        )
        try:
            result = self.auto_generate_path_with_api(path_result["path"], min_t_m, max_t_m, min_d_m)
        except Exception as exc:
            result = {"success": False, "message": sanitize_diagnostic(exc)}
        if not result.get("success"):
            summary = self._notify_route_planning_failure({**path_result, "error": result.get("message", "生成模拟轨迹失败")})
            return {"success": False, "message": generic_route_failure_message(summary["diagnostic_id"]), "diagnostic_id": summary["diagnostic_id"], "_route_failure": summary}
        result["provider"] = path_result.get("provider")
        result["diagnostic_id"] = path_result.get("diagnostic_id")
        result["notices"] = notices
        return result

    def start_all_runs(
        self,
        ignore_completed,
        auto_generate,
        bypass_overdue: bool = False,
        waive_charge: bool = False,
    ):
        """开始执行所有符合条件的任务"""
        logging.info(
            f"API CALL: start_all_runs (ignore_completed={ignore_completed}, auto_generate={auto_generate})"
        )

        # ============================================================
        # [安全加固] 欠费检查：防止单账号模式绕过欠费限制
        # ============================================================
        # 检查当前是否已登录学校账号
        # 这一步骤确保只有无欠费的账号才能批量启动所有任务，防止欠费用户通过单账号模式绕过限制
        if not self.user_data or not self.user_data.username:
            # 如果没有登录或无用户信息，也应该拒绝启动任务
            # 这是另一层安全保障，防止未认证用户启动任务
            logging.warning("[欠费检查] 未登录或无用户信息，拒绝启动所有任务")
            return {
                "success": False,
                "message": "请先登录后再启动任务"
            }

        if self._payment_required_for_overdue_gate():
            # 获取当前登录的学校账号用户名
            school_username = self.user_data.username

            # 从账单文件读取该账号待支付账单数量作为欠费次数
            overdue_count = _main()._count_pending_bills_for_school(school_username)

            # 如果存在欠费（overdue_count > 0），拒绝启动所有任务
            # 这是关键的安全检查点，防止欠费用户批量启动任务继续使用服务
            if overdue_count > 0 and not self._overdue_bypass_allowed(
                bypass_overdue
            ):
                logging.warning(
                    f"[欠费检查] 账号 {school_username} 存在欠费 ({overdue_count} 次)，拒绝启动所有任务"
                )
                # 返回错误信息，包含欠费详情
                return {
                    "success": False,  # 操作失败
                    "message": "当前账号存在欠费，请先缴费后再启动任务",  # 用户友好的错误提示
                    "error_code": "OVERDUE_PAYMENT",  # 错误代码，前端可以据此做特殊处理
                    "overdue_accounts": [  # 欠费账号列表（单账号模式下只有一个）
                        {
                            "school_username": school_username,  # 欠费账号的用户名
                            "overdue_count": overdue_count  # 欠费次数
                        }
                    ]
                }

        # 本次执行的计费豁免状态（仅管理员可用；不请求豁免时重置为 False）。
        self.waive_charge_active = self._resolve_waive_charge(waive_charge)

        # 通过欠费检查后，继续执行原有的任务启动逻辑
        if not self.stop_run_flag.is_set():
            return {"success": False, "message": "已有任务在运行"}

        tasks_to_run = []
        now = datetime.datetime.now()
        ignore_time = self.params.get("ignore_task_time", True)
        for i, d in enumerate(self.all_run_data):
            if d.status == 1 and not ignore_completed:
                continue

            if self._get_task_time_state(d, ignore_time, now) != "active":
                continue

            if auto_generate or d.run_coords:
                tasks_to_run.append(i)

        if not tasks_to_run:
            msg = "没有符合条件的可执行任务。"
            if not auto_generate:
                msg += " (提示: 勾选'全部自动生成'可以为没有路线的任务自动规划)"
            return {"success": False, "message": msg}

        queue = collections.deque(tasks_to_run)
        with self.single_execution_lock:
            if not self.stop_run_flag.is_set():
                return {"success": False, "message": "已有任务在运行"}

            execution_token, conflict_identity = (
                self._claim_single_school_account_execution()
            )
            if execution_token is None:
                return {
                    "success": False,
                    "message": (
                        f"学校账号 {conflict_identity or self.user_data.username} "
                        "已在单账号或多账号模式中执行任务"
                    ),
                }

            self.stop_run_flag.clear()
            logging.info(
                f"Starting 'run all' process. Queue={list(queue)}, auto-generate={auto_generate}"
            )
            task_manager = getattr(_main(), "background_task_manager", None)
            route_session_id = getattr(self, "_web_session_id", "")
            diagnostic_execution_id = task_manager.begin_route_planning_batch(
                route_session_id,
                task_status={"status": "running", "total_tasks": len(queue), "start_time": time.time()},
            ) if task_manager and route_session_id else None
            run_all_thread = threading.Thread(
                target=self._run_with_single_school_account_execution,
                args=(
                    execution_token,
                    self._run_all_tasks_manager,
                    (queue, auto_generate, diagnostic_execution_id),
                ),
                daemon=True,
            )
            try:
                run_all_thread.start()
            except Exception:
                if task_manager and route_session_id:
                    task_manager.clear_route_planning_failures(route_session_id)
                self._release_single_school_account_execution(execution_token)
                self.stop_run_flag.set()
                raise
        logging.info(f"[Thread Creation] Starting run_all thread: {run_all_thread.name}")
        logging.info(f"[Thread Creation] Run_all thread started: {run_all_thread.name} (id={run_all_thread.ident})")
        return {"success": True}

    def _run_all_tasks_manager(self, queue: collections.deque, auto_gen_enabled: bool, execution_id=None):
        """管理队列生命周期，使独立执行线程的失败也可通过状态接口查询。"""
        manager = getattr(_main(), "background_task_manager", None)
        session_id = getattr(self, "_web_session_id", "")
        if execution_id is None and manager and session_id:
            execution_id = manager.begin_route_planning_batch(
                session_id,
                task_status={"status": "running", "total_tasks": len(queue), "start_time": time.time()},
            )
        status = "error"
        try:
            executed = self._execute_all_task_queue(queue, auto_gen_enabled, execution_id)
            failures = manager.get_route_planning_failures(session_id) if manager and session_id else []
            status = "stopped" if self.stop_run_flag.is_set() else "error" if not executed and failures else "completed"
        except Exception as exc:
            self._notify_route_planning_failure({"error": sanitize_diagnostic(exc)}, execution_id=execution_id)
        finally:
            current = not manager or execution_id is None or manager.update_route_planning_batch_status(
                session_id, execution_id, {"status": status, "end_time": time.time()}
            )
            if manager and execution_id is not None:
                with manager.lock:
                    batch = manager.route_failure_batches.get(session_id)
                    current = bool(batch and batch[0] is execution_id)
                    if current:
                        self.stop_run_flag.set()
            elif current:
                self.stop_run_flag.set()
            if current:
                if getattr(self, "window", None):
                    self.window.evaluate_js("onAllRunsToggled(false)")

    def _execute_all_task_queue(self, queue: collections.deque, auto_gen_enabled: bool, execution_id=None):
        manager = getattr(_main(), "background_task_manager", None)
        session_id = getattr(self, "_web_session_id", "")
        self.log_and_notify_frontend("开始执行所有任务。")
        if self.window:
            self.window.evaluate_js("onAllRunsToggled(true)")
        is_first_task = True

        tasks_executed_count = 0

        while queue:
            if manager and execution_id is not None:
                with manager.lock:
                    batch = manager.route_failure_batches.get(session_id)
                    if not batch or batch[0] is not execution_id:
                        return
            if self.stop_run_flag.is_set():
                break

            idx = queue.popleft()
            run_data = self.all_run_data[idx]
            self.current_run_idx = idx

            if self.window:
                self.window.evaluate_js(f"selectTaskFromBackend({idx})")
            time.sleep(1.2)

            if not run_data.run_coords and auto_gen_enabled:
                self.log_and_notify_frontend(f"正在为任务 '{run_data.run_name}' 自动生成路线...")
                logging.info(
                    f"Auto-generating path for task in 'run all' mode: {run_data.run_name}"
                )

                if not run_data.details_fetched:
                    details_resp = self.get_task_details(idx)
                    if not details_resp.get("success"):
                        self.log_and_notify_frontend("获取详情失败，跳过。")
                        logging.warning(
                            f"Skipping task {run_data.run_name}: failed to get details."
                        )
                        continue
                    run_data = self.all_run_data[idx]

                if not run_data.target_points:
                    self.log_and_notify_frontend(f"跳过: 任务 '{run_data.run_name}' 无打卡点")
                    logging.warning(
                        f"[Task Skipped] No checkpoints for task {run_data.run_name}, cannot auto-generate path."
                    )
                    continue

                try:
                    self.log_and_notify_frontend("正在按当前地图供应商进行路径规划...")
                    session_id = getattr(self, "_web_session_id", None)
                    if not session_id:
                        self._notify_route_planning_failure({"error": "当前会话缺少浏览器会话ID"}, execution_id=execution_id)
                        continue

                    waypoints = run_data.target_points
                    path_result = _main()._plan_route_path_with_provider_runtime(
                        session_id,
                        waypoints,
                        python_params=self.params,
                        guard_label="SingleRunPathPlanning",
                        app_base_url=getattr(self, "_web_app_base_url", None),
                    )
                    if not isinstance(path_result, dict) or not path_result.get("path"):
                        self._notify_route_planning_failure(path_result, execution_id=execution_id)
                        continue
                    for notice in path_result.get("notices", []):
                        self.log_and_notify_frontend(sanitize_diagnostic(notice))

                    api_path_coords = path_result["path"]
                    self.log_and_notify_frontend(
                        f"路径规划成功，共 {len(api_path_coords)} 个点，正在生成模拟数据..."
                    )

                    p = self.params
                    gen_resp = self.auto_generate_path_with_api(
                        api_path_coords,
                        p.get("min_time_m", 20),
                        p.get("max_time_m", 30),
                        p.get("min_dist_m", 2000),
                        apply_result=False,
                    )
                    if not gen_resp.get("success"):
                        self._notify_route_planning_failure({**path_result, "error": gen_resp.get("message", "生成轨迹失败")}, execution_id=execution_id)
                        continue

                    if manager and execution_id is not None:
                        with manager.lock:
                            batch = manager.route_failure_batches.get(session_id)
                            if not batch or batch[0] is not execution_id:
                                return
                            run_data.run_coords = gen_resp["run_coords"]
                            run_data.total_run_distance_m = gen_resp["total_dist"]
                            run_data.total_run_time_s = gen_resp["total_time"]
                    else:
                        run_data.run_coords = gen_resp["run_coords"]
                        run_data.total_run_distance_m = gen_resp["total_dist"]
                        run_data.total_run_time_s = gen_resp["total_time"]

                except Exception as e:
                    self._notify_route_planning_failure({"error": sanitize_diagnostic(e)}, execution_id=execution_id)
                    continue

                self.log_and_notify_frontend("路径已生成，正在更新界面...")
                if self.window:
                    self.window.evaluate_js(f"forceRefreshTaskUI({idx})")
                time.sleep(1.0)

            if not run_data.run_coords:
                self.log_and_notify_frontend(f"任务 '{run_data.run_name}' 无可用路线，跳过。")
                logging.warning(
                    f"Skipping task {run_data.run_name}: no route available."
                )
                continue

            if not is_first_task:
                wait_time = random.uniform(
                    self.params["task_gap_min_s"], self.params["task_gap_max_s"]
                )
                self.log_and_notify_frontend(f"任务间等待中...")
                logging.info(f"等待 {wait_time:.1f}秒 后开始执行下一个任务")
                if self.stop_run_flag.wait(timeout=wait_time):
                    break
            is_first_task = False
            tasks_executed_count += 1

            run_data.target_sequence, run_data.is_in_target_zone = 0, False
            self._first_center_done = False
            task_finished_event = threading.Event()
            self._run_submission_thread(
                run_data, idx, self.api_client, True, task_finished_event
            )
            task_finished_event.wait()

        if tasks_executed_count == 0:
            self.log_and_notify_frontend("所有任务均被跳过，未执行任何操作。")
        else:
            self.log_and_notify_frontend("所有任务执行结束。")

        return tasks_executed_count

    def get_task_history(self, index):
        """获取任务的历史跑步记录"""
        logging.info(
            f"API调用: get_task_history - 获取任务历史跑步记录，任务索引: {index}"
        )
        if not (0 <= index < len(self.all_run_data)):
            return {"success": False, "message": "任务索引无效"}
        run_data = self.all_run_data[index]
        self.log_and_notify_frontend("正在获取历史记录...")
        logging.debug(f"正在获取任务的历史记录: 任务名称={run_data.run_name}")
        resp = self.api_client.get_run_history_list(
            self.user_data.id, run_data.errand_schedule
        )

        if resp and resp.get("success"):
            records = resp.get("data", {}).get("userErrandTrackRecord", [])
            history_list = []
            for rec in records:
                run_time_s = rec.get("runTime", 0) / 1000
                length_m = rec.get("runLength", 0)
                km = length_m / 1000 if length_m else 0
                speed_s_per_km = (run_time_s / km) if km > 0 else 0
                s_min, s_sec = divmod(speed_s_per_km, 60)
                total_seconds_int = int(run_time_s)
                run_minutes, run_seconds = divmod(total_seconds_int, 60)
                formatted_used_time = f"{run_minutes:02d}:{run_seconds:02d}"
                history_list.append(
                    {
                        "time": rec.get("createTime", "NULL"),
                        "used_time": formatted_used_time,
                        "len": f"{length_m}m",
                        "speed": (
                            f"{int(s_min)}'{int(s_sec):02d}\"" if km > 0 else "NULL"
                        ),
                        "trid": rec.get("trid"),
                    }
                )
            self.log_and_notify_frontend(f"历史记录已加载。")
            logging.debug(f"已成功加载 {len(records)} 条历史记录")
            return {"success": True, "history": history_list}
        return {"success": False, "message": "获取历史记录失败"}

    def get_historical_track(self, trid):
        """根据轨迹ID获取历史轨迹坐标点"""
        logging.info(
            f"API调用: get_historical_track - 根据轨迹ID获取历史轨迹，trid: {trid}"
        )
        self.log_and_notify_frontend("正在加载历史轨迹...")
        logging.debug(f"正在加载历史运动轨迹数据，轨迹ID: trid={trid}")
        resp = self.api_client.get_history_track_by_trid(trid)
        if resp and resp.get("success"):
            coords = []
            for track_point_list in resp.get("data", {}).get("trackPointList", []):
                try:
                    coords_list = json.loads(
                        track_point_list.get("coordinate", "[]"))
                    for item in coords_list:
                        lon, lat = map(float, item.get(
                            "location", "0,0").split(","))
                        coords.append((lon, lat))
                except (json.JSONDecodeError, ValueError):
                    continue
            self.log_and_notify_frontend("历史轨迹加载成功。")
            logging.debug(f"历史轨迹数据加载成功，包含 {len(coords)} 个坐标点")
            return {"success": True, "coords": coords}
        self.log_and_notify_frontend("加载历史轨迹失败。")
        logging.warning("加载历史运动轨迹数据失败")
        return {"success": False, "message": "加载历史轨迹失败"}

    def update_param(self, key, value):
        """更新并保存单个参数"""
        logging.info(f"API调用: update_param - 更新参数，键: {key}")

        username_to_update = None
        if self.is_multi_account_mode:
            target_params = self.global_params
        else:
            target_params = self.params
            username_to_update = self.user_data.username

        if key in target_params:
            try:
                original_type = type(target_params[key])
                if original_type is bool:
                    target_params[key] = (
                        bool(value)
                        if isinstance(value, bool)
                        else str(value).lower() in ("true", "1", "t", "yes")
                    )
                else:
                    target_params[key] = original_type(value)

                if key == "auto_attendance_success_limit":
                    target_params[key] = max(1, int(target_params[key]))

                # [修正] 如果是全局配置项，立即保存到 config.ini
                # auto_attendance_enabled 已移除，它将仅保存在会话中
                global_keys = [
                    "theme_base_color",
                    "theme_style",
                    "auto_attendance_stop_after_success",
                    "auto_attendance_success_limit",
                    "auto_attendance_refresh_s",
                    "attendance_user_radius_m",
                ]
                if key in global_keys:
                    try:
                        main_cfg = _main()._read_config_ini(self.config_path) or configparser.RawConfigParser()

                        if not main_cfg.has_section("Config"):
                            main_cfg.add_section("Config")

                        main_cfg.set("Config", key, str(target_params[key]))

                        _main()._write_config_with_comments(main_cfg, self.config_path)
                        logging.debug(f"已将全局参数 {key} 保存到 config.ini")
                    except Exception as e:
                        logging.error(f"保存全局参数到 config.ini 失败: {e}")

                if self.is_multi_account_mode:
                    for acc in self.accounts.values():
                        if key in acc.params:
                            acc.params[key] = target_params[key]
                            ini_path = os.path.join(
                                self.user_dir, f"{acc.username}.ini"
                            )
                            if os.path.exists(ini_path):
                                self._save_config(acc.username)

                if not username_to_update:
                    cfg = _main()._read_config_ini(self.config_path) or configparser.ConfigParser(strict=False)
                    username_to_update = cfg.get(
                        "Config", "LastUser", fallback=None)

                if username_to_update and not self.is_multi_account_mode:
                    self._save_config(username_to_update)

                logging.debug(f"参数已更新: 参数名={key}")

                # 当 auto_attendance_enabled 参数改变时，更新JSON配置文件
                # 不再将此参数保存到INI文件，改为使用集中的JSON配置管理
                if key == "auto_attendance_enabled" and not self.is_multi_account_mode:
                    # 单账号模式：处理自动签到开关
                    try:
                        # 验证用户是否已登录
                        if self.user_data and self.user_data.id and self.user_data.username:
                            # 获取学校账号用户名（用于标识配置）
                            school_username = self.user_data.username
                            # 获取账号ID（用于管理刷新线程）
                            account_id = str(self.user_data.id)
                            # 获取会话UUID（用于关联会话和配置）
                            session_uuid = getattr(
                                self, "_web_session_id", None)
                            # 获取认证用户名（用于记录配置所有者）
                            auth_username = username_to_update or school_username

                            # 根据新的参数值决定启用还是禁用自动签到
                            if target_params[key]:  # 如果启用自动签到
                                # 检查是否有有效的会话UUID
                                if session_uuid:
                                    # 调用JSON配置函数启用自动签到
                                    if _main()._enable_auto_attendance(school_username, session_uuid, auth_username):
                                        # 启用成功后，确保刷新线程正在运行
                                        self._ensure_account_refresh_thread(
                                            account_id)
                                        self.log_and_notify_frontend("自动签到已启用，配置已保存到JSON文件。")
                                        logging.info(
                                            f"[参数更新] 已启用自动签到 - "
                                            f"学校账号: {school_username}, "
                                            f"会话: {session_uuid}, "
                                            f"刷新线程已启动"
                                        )
                                    else:
                                        # 启用失败，记录错误日志
                                        logging.error(
                                            f"[参数更新] 启用自动签到失败 - 学校账号: {school_username}")
                                        self.log_and_notify_frontend("自动签到启用失败，请检查日志。")
                                else:
                                    # 没有会话UUID，无法启用自动签到
                                    logging.warning(
                                        f"[参数更新] 无法启用自动签到：未找到会话UUID - "
                                        f"学校账号: {school_username}"
                                    )
                                    self.log_and_notify_frontend("自动签到启用失败：未找到会话信息。")
                            else:  # 如果禁用自动签到
                                # 调用JSON配置函数禁用自动签到
                                if _main()._disable_auto_attendance(school_username):
                                    # 禁用成功后，停止刷新线程
                                    with self.threads_lock:
                                        if account_id in self.account_refresh_threads:
                                            # 从线程字典中移除，线程会自动检测配置变化并退出
                                            del self.account_refresh_threads[account_id]
                                            self.log_and_notify_frontend("自动签到已禁用，刷新线程将停止。")
                                            logging.info(
                                                f"[参数更新] 已禁用自动签到 - "
                                                f"学校账号: {school_username}, "
                                                f"刷新线程已停止"
                                            )
                                else:
                                    # 禁用失败，记录错误日志
                                    logging.error(
                                        f"[参数更新] 禁用自动签到失败 - 学校账号: {school_username}")
                                    self.log_and_notify_frontend("自动签到禁用失败，请检查日志。")
                        else:
                            # 用户未登录，无法更新自动签到配置
                            logging.warning("[参数更新] 无法更新自动签到配置：用户未登录或数据不完整")
                            self.log_and_notify_frontend("自动签到更新失败：用户未登录。")
                    except Exception as e:
                        # 捕获所有异常，避免影响其他参数的更新
                        logging.error(f"[参数更新] 更新自动签到配置失败: {e}", exc_info=True)
                        self.log_and_notify_frontend(f"自动签到更新失败: {e}")

                # [新版] 当 auto_attendance_refresh_s 参数改变时，重启相关线程
                # 刷新间隔时间变化不需要修改JSON配置，只需要重启线程
                elif key == "auto_attendance_refresh_s" and not self.is_multi_account_mode:
                    # 单账号模式：重启当前账号的刷新线程
                    try:
                        # 如果已登录且有用户ID
                        if self.user_data and self.user_data.id and self.user_data.username:
                            school_username = self.user_data.username
                            account_id = str(self.user_data.id)

                            # 检查该账号是否启用了自动签到（从JSON配置读取）
                            if _main()._is_auto_attendance_enabled(school_username):
                                # 如果启用了自动签到，重启刷新线程以应用新的刷新间隔
                                self._ensure_account_refresh_thread(account_id)
                                self.log_and_notify_frontend("自动签到刷新间隔已更新，刷新线程已重启。")
                                logging.info(
                                    f"[参数更新] 已更新刷新间隔为 {target_params[key]} 秒，"
                                    f"账号 {account_id} 刷新线程已重启"
                                )
                        else:
                            logging.warning("[参数更新] 无法更新刷新线程：用户未登录")
                    except Exception as e:
                        logging.error(f"[参数更新] 更新刷新线程失败: {e}", exc_info=True)

                # [多账号模式] 当自动签到参数改变时，监控线程会自动处理
                # 无需在这里额外操作，监控线程会在下一次检查时发现变化

                return {"success": True}
            except (ValueError, TypeError) as e:
                return {"success": False, "message": str(e)}
        return {"success": False, "message": "Unknown parameter"}

    def get_theme_styles(self, background_target=None):
        """获取主题样式列表和当前主题配置"""
        current_theme_style = getattr(self, "global_params", {}).get("theme_style", "default")
        target_list = []
        if background_target == "mobile":
            target_list = ["mobile"]
        elif background_target == "pc":
            target_list = ["pc"]
        session_uuid = str(getattr(self, "_web_session_id", "") or "").strip()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(base_dir, _main().RANDOM_BACKGROUND_IMAGE_DIR)
        theme_config = _main().auth_system.get_theme_config(
            current_theme_style,
            target_list or None,
            session_uuid=session_uuid,
            cache_dir=cache_dir,
        )
        return {
            "success": True,
            "theme_styles": _main().auth_system.get_available_theme_styles(),
            "theme_config": _main()._apply_identity_bundle_to_theme_config(
                theme_config, session_uuid
            ),
        }

    def get_public_theme_styles(self, style_id="default", background_target=None):
        """获取公开主题样式列表和指定主题配置（无需登录）"""
        current_theme_style = str(style_id or "default").strip() or "default"
        target_list = []
        if background_target == "mobile":
            target_list = ["mobile"]
        elif background_target == "pc":
            target_list = ["pc"]
        session_uuid = str(getattr(self, "_web_session_id", "") or "").strip()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(base_dir, _main().RANDOM_BACKGROUND_IMAGE_DIR)
        theme_config = _main().auth_system.get_theme_config(
            current_theme_style,
            target_list or None,
            session_uuid=session_uuid,
            cache_dir=cache_dir,
        )
        return {
            "success": True,
            "theme_styles": _main().auth_system.get_available_theme_styles(),
            "theme_config": _main()._apply_identity_bundle_to_theme_config(
                theme_config, session_uuid
            ),
        }

    def mark_theme_background_consumed(
        self,
        target="pc",
        image_url="",
        login_context=False,
        candidate_image_url="",
    ):
        normalized_target = _main()._normalize_theme_background_target(target)
        result = self._mark_theme_background_consumed_transaction(
            normalized_target,
            image_url,
            login_context,
            candidate_image_url,
        )
        image_type = "mb" if normalized_target == "mobile" else "pc"
        self._refresh_default_theme_background_cache_async([image_type])
        return result

    @background_files_locked
    def _mark_theme_background_consumed_transaction(
        self,
        normalized_target,
        image_url,
        login_context,
        candidate_image_url,
    ):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(base_dir, _main().RANDOM_BACKGROUND_IMAGE_DIR)
        os.makedirs(cache_dir, exist_ok=True)

        session_uuid = str(getattr(self, "_web_session_id", "") or "").strip()
        decision = _main()._resolve_theme_background_binding_decision(
            cache_dir=cache_dir,
            session_uuid=session_uuid,
            target=normalized_target,
            current_image_url=str(image_url or "").strip(),
            login_context=bool(login_context),
            candidate_image_url=str(candidate_image_url or "").strip(),
            ttl_seconds=1800,
        )

        selected_image_url = str(decision.get("selected_image_url") or "").strip()
        if selected_image_url:
            _main()._mark_random_background_file_expired(cache_dir, selected_image_url, expired=True)

        next_theme_config = _main().auth_system.get_theme_config(
            "default",
            [normalized_target],
            session_uuid=session_uuid,
            cache_dir=cache_dir,
        )
        next_env = (
            next_theme_config.get("global_environment_variables")
            if isinstance(next_theme_config, dict)
            else {}
        )
        next_image_url = (
            str(next_env.get("mobile_auth_login_content_background") or "")
            if normalized_target == "mobile"
            else str(next_env.get("auth_login_container_background") or "")
        )
        extracted_next_image_url = _main()._extract_background_image_url_from_value(next_image_url)
        if extracted_next_image_url and not selected_image_url:
            decision = _main()._resolve_theme_background_binding_decision(
                cache_dir=cache_dir,
                session_uuid=session_uuid,
                target=normalized_target,
                current_image_url=extracted_next_image_url,
                ttl_seconds=1800,
            )
            selected_image_url = str(decision.get("selected_image_url") or "").strip()
        if extracted_next_image_url:
            _main()._mark_random_background_file_expired(cache_dir, extracted_next_image_url, expired=True)
        if selected_image_url and selected_image_url != extracted_next_image_url:
            _main()._reset_random_background_file_expired(cache_dir, selected_image_url)

        return {
            "success": True,
            "theme_config": next_theme_config,
            "binding_action": decision.get("action", "noop"),
        }

    def _refresh_default_theme_background_cache_async(self, image_types=None):
        refresher = getattr(
            getattr(_main(), "auth_system", None),
            "_refresh_default_theme_background_cache_async",
            None,
        )
        if callable(refresher):
            refresher(image_types)

    def get_params(self):
        """
        获取当前参数配置
        auto_attendance_enabled 从JSON配置读取，而不是从INI读取
        """
        try:
            if self.is_multi_account_mode:
                params = self.global_params.copy()
            else:
                params = self.params.copy()

            # 动态添加 auto_attendance_enabled 状态
            # 这个值不再存储在params中，而是从JSON配置文件实时读取
            school_username = None
            if self.is_multi_account_mode:
                # 多账号模式下，auto_attendance_enabled 在各账号级别管理
                # 这里返回 False 作为全局默认值
                params["auto_attendance_enabled"] = False
            else:
                # 单账号模式下，从JSON配置读取当前用户的启用状态
                if self.user_data and self.user_data.username:
                    school_username = self.user_data.username
                    params["auto_attendance_enabled"] = _main()._is_auto_attendance_enabled(
                        school_username)
                else:
                    # 用户未登录，返回默认值
                    params["auto_attendance_enabled"] = False

            return params
        except Exception as e:
            logging.error(f"获取参数失败: {e}", exc_info=True)
            # 返回默认参数，auto_attendance_enabled 默认为 False
            return {
                "theme_base_color": "#7dd3fc",
                "theme_style": "default",
                "auto_attendance_enabled": False,
                "auto_attendance_stop_after_success": True,
                "auto_attendance_success_limit": 1,
                "auto_attendance_refresh_s": 15,
                "attendance_user_radius_m": 40,
            }

    def export_task_data(self):
        """导出当前任务数据为JSON文件（Web模式：返回JSON数据让前端下载）"""
        logging.info("API调用: export_task_data - 导出当前任务数据为JSON格式")
        logging.info("导出任务数据...")
        if self.current_run_idx == -1:
            logging.warning("未选择任务，无法导出")
            return {"success": False, "message": "请先选择一个任务。"}
        run_data = self.all_run_data[self.current_run_idx]
        if (
            not run_data.draft_coords
            and not run_data.run_coords
            and not run_data.recommended_coords
        ):
            logging.warning("任务无路径数据，无法导出")
            return {"success": False, "message": "当前任务没有可导出的路径数据。"}

        export_data = {
            "task_name": run_data.run_name,
            "errand_id": run_data.errand_id,
            "errand_schedule": run_data.errand_schedule,
            "target_points": run_data.target_points,
            "target_point_names": run_data.target_point_names,
            "recommended_coords": run_data.recommended_coords,
            "draft_coords (gps)": run_data.draft_coords,
            "run_coords (gps)": run_data.run_coords,
        }

        try:
            logging.info(f"导出任务数据成功: {run_data.run_name}")
            return {
                "success": True,
                "data": export_data,
                "filename": f"task_{run_data.errand_schedule or 'debug'}_{int(time.time())}.json",
                "message": "任务数据已准备完成",
            }
        except Exception as e:
            logging.error(f"导出失败: {e}", exc_info=True)
            return {"success": False, "message": f"导出失败: {e}"}

    def import_task_data(self, json_data=None):
        """导入JSON任务数据，进入离线调试模式（UA=Null，保留用户信息）"""
        logging.info("API调用: import_task_data - 导入JSON任务数据（离线调试模式）")
        logging.info("开始导入任务数据...")

        if not json_data:
            logging.error("导入失败：未提供有效的JSON数据")
            return {"success": False, "message": "未提供导入数据"}

        try:
            if isinstance(json_data, str):
                logging.info("解析JSON字符串...")
                data = json.loads(json_data)
            else:
                data = json_data

            logging.info(f"JSON数据解析成功，任务名称: {data.get('task_name', '未知')}")

            prev_user = copy.deepcopy(getattr(self, "user_data", _main().UserData()))

            self.is_offline_mode = True
            logging.info("切换到离线模式")
            try:
                if hasattr(self, "stop_run_flag") and isinstance(
                    self.stop_run_flag, threading.Event
                ):
                    self.stop_run_flag.set()
                    logging.info("停止运行中的任务")
            except Exception:
                pass
            self.all_run_data = []
            self.current_run_idx = -1
            self._first_center_done = False

            self.user_data = prev_user if prev_user else _main().UserData()
            if not (self.user_data.name or "").strip():
                self.user_data.name = "离线调试"
            if not (self.user_data.student_id or "").strip():
                self.user_data.student_id = "NULL"

            logging.info(
                f"用户信息: {self.user_data.name} ({self.user_data.student_id})"
            )

            self.device_ua = None

            debug_run = _main().RunData()
            debug_run.run_name = data.get("task_name", "调试任务 (离线)")
            debug_run.errand_id = data.get("errand_id", "debug_id")
            debug_run.errand_schedule = data.get(
                "errand_schedule", "debug_schedule")
            debug_run.target_points = data.get("target_points", [])
            if "target_point_names" in data and data["target_point_names"]:
                debug_run.target_point_names = data["target_point_names"]
            else:
                num_points = len(debug_run.target_points)
                if num_points > 0:
                    debug_run.target_point_names = "|".join(
                        [f"打卡点 {i + 1}" for i in range(num_points)]
                    )

            debug_run.recommended_coords = data.get("recommended_coords", [])
            debug_run.draft_coords = data.get("draft_coords (gps)", [])
            debug_run.run_coords = data.get("run_coords (gps)", [])

            if debug_run.run_coords and len(debug_run.run_coords) > 1:
                total_dist_m = 0.0
                for i in range(len(debug_run.run_coords) - 1):
                    p1 = debug_run.run_coords[i]
                    p2 = debug_run.run_coords[i + 1]
                    total_dist_m += self._calculate_distance_m(
                        p1[0], p1[1], p2[0], p2[1]
                    )
                total_time_s = sum(p[2] for p in debug_run.run_coords) / 1000.0
                debug_run.total_run_distance_m = total_dist_m
                debug_run.total_run_time_s = total_time_s
                logging.info(
                    f"导入路径统计完成: 距离={total_dist_m:.1f}米, 时间={total_time_s:.1f}秒"
                )

            debug_run.details_fetched = True
            self.all_run_data = [debug_run]
            self.current_run_idx = 0

            self.log_and_notify_frontend("离线数据已导入。")
            logging.info(f"离线数据导入成功: {debug_run.run_name}")

            tasks_for_js = [r.__dict__.copy() for r in self.all_run_data]
            tasks_for_js[0]["info_text"] = "离线"
            tasks_for_js[0]["target_range_m"] = self.target_range_m

            return {
                "success": True,
                "tasks": tasks_for_js,
                "userInfo": self._get_full_user_info_dict(),
            }
        except Exception as e:
            self.log_and_notify_frontend("导入失败。")
            logging.error(f"导入失败: {e}", exc_info=True)
            return {"success": False, "message": f"导入失败: {e}"}

    def clear_current_task_draft(self):
        """
        清除当前任务的草稿路径和已生成路径。

        功能说明：
        - 首先检查是否有任务正在执行中
        - 如果任务正在执行，拒绝清除操作
        - 否则清除当前任务的草稿路径和运行数据

        返回值：
        - 成功: {"success": True}
        - 失败: {"success": False, "message": "错误信息"}
        """
        logging.info(
            "API调用: clear_current_task_draft - 清除当前任务的草稿路径和生成路径"
        )

        # 步骤1: 检查是否选择了任务
        if self.current_run_idx == -1 or not (
            0 <= self.current_run_idx < len(self.all_run_data)
        ):
            return {"success": False, "message": "未选择任务"}

        # 步骤2: 检查是否有任务正在执行中
        # 需要检查后台任务管理器和单账号模式的运行标志
        is_running = False

        # 检查后台任务管理器中是否有正在运行的任务
        # background_task_manager 是全局变量，用于管理后台任务
        if _main().background_task_manager:
            with _main().background_task_manager.lock:
                # 遍历所有任务，检查是否有状态为 "running" 的任务
                for session_id, task in _main().background_task_manager.tasks.items():
                    if task.get("status") == "running":
                        is_running = True
                        logging.info(
                            f"检测到后台任务正在运行: session_id={session_id[:16]}..."
                        )
                        break

        # 检查单账号模式下的运行标志
        # stop_run_flag 是一个 threading.Event 对象
        # 当它未被设置(is_set()返回False)时，表示任务可能正在运行
        if (
            not is_running
            and hasattr(self, "stop_run_flag")
            and isinstance(self.stop_run_flag, threading.Event)
        ):
            # 还需要检查是否真的有任务在执行
            # 通过检查 run_in_progress 或类似标志来确认
            if hasattr(self, "run_in_progress") and self.run_in_progress:
                is_running = True
                logging.info("检测到单账号模式下任务正在运行")

        # 如果任务正在执行，拒绝清除操作
        if is_running:
            logging.warning("任务正在执行中，拒绝清除路径请求")
            return {"success": False, "message": "任务正在执行中，无法清除路径"}

        # 步骤3: 执行清除操作
        run = self.all_run_data[self.current_run_idx]
        run.draft_coords = []  # 清除草稿路径坐标
        run.run_coords = []  # 清除运行路径坐标
        run.total_run_distance_m = 0  # 重置总运行距离
        run.total_run_time_s = 0  # 重置总运行时间

        # 将修改写入持久化文件
        session_id = getattr(self, "_web_session_id", None)
        if session_id:
            try:
                _main().save_session_state(session_id, self, force_save=True)
                logging.info(
                    f"[持久化] 已保存清除路径后的会话状态: {session_id[:8]}..."
                )
            except Exception as e:
                logging.error(f"[持久化] 保存会话状态失败: {e}")

        logging.info(f"已清除任务的草稿路径和运行数据: 任务名称={run.run_name}")
        return {"success": True}

    def enter_multi_account_mode(self):
        """切换到多账号模式（增强：先打断单账号运行）"""
        try:
            if hasattr(self, "stop_run_flag") and isinstance(
                self.stop_run_flag, threading.Event
            ):
                self.stop_run_flag.set()
            for key, (path_result, completion_event) in list(
                self.path_gen_callbacks.items()
            ):
                path_result["error"] = "模式切换（进入多账号）已取消"
                try:
                    completion_event.set()
                except Exception:
                    pass
            self.path_gen_callbacks.clear()
            session_id = getattr(self, "_web_session_id", None)
            if _main().background_task_manager and session_id:
                try:
                    _main().background_task_manager.stop_task(session_id)
                except Exception:
                    pass
            if session_id and _main().socketio:
                try:
                    _main().socketio.emit("run_stopped", {}, room=session_id)
                except Exception:
                    pass
            if self.window:
                try:
                    self.window.evaluate_js("onRunStopped()")
                except Exception:
                    pass
        except Exception:
            logging.debug(
                "enter_multi_account_mode pre-stop single failed (non-fatal)."
            )

        self.log_and_notify_frontend("进入多账号模式。")
        self.is_multi_account_mode = True
        self._update_multi_global_buttons()

        session_id = getattr(self, "_web_session_id", None)
        if session_id and _main().socketio:
            try:
                current_thread = threading.current_thread()
                logging.info(f"[SocketIO Emit] Preparing 'accounts_updated' from Thread[{current_thread.name}, id={current_thread.ident}]")
                accounts_data = []
                for username, acc in self.accounts.items():
                    accounts_data.append(
                        {
                            "username": username,
                            "name": (
                                acc.user_data.name if acc.user_data.name else username
                            ),
                            "status_text": acc.status_text,
                            "summary": acc.summary,
                            "params": acc.params,
                        }
                    )
                logging.info(f"[SocketIO Emit] Sending 'accounts_updated' to session {session_id[:8]}...")
                _main().socketio.emit(
                    "accounts_updated", {"accounts": accounts_data}, room=session_id
                )
                logging.info(f"[SocketIO Emit] 'accounts_updated' sent successfully")
            except Exception as e:
                current_thread = threading.current_thread()
                logging.error(
                    f"Failed to emit accounts_updated on mode entry from Thread[{current_thread.name}]: {e}")
                logging.error(f"Error type: {type(e).__name__}")
                logging.error(f"Full traceback: {traceback.format_exc()}")

        # [新版] 使用统一的多账号监控线程机制
        # 不再使用旧的 multi_auto_refresh_thread，而是启动监控线程
        try:
            # 清除停止标志（为了向后兼容旧代码）
            self.stop_multi_auto_refresh.clear()

            # 清除新的监控线程停止标志
            self.stop_account_monitor.clear()

            # 检查是否已有监控线程在运行
            if (
                self.account_monitor_thread is None
                or not self.account_monitor_thread.is_alive()
            ):
                # 创建新的多账号监控线程
                # 该线程会定期检查所有账号，为需要的账号创建独立的刷新线程
                self.account_monitor_thread = threading.Thread(
                    target=self._multi_account_monitor_worker,
                    args=(self._get_session_stop_event(),),
                    daemon=True,
                    name="MultiAccountMonitor"
                )
                current_thread = threading.current_thread()
                logging.info(f"[Thread Creation] Creating account monitor thread from Thread[{current_thread.name}, id={current_thread.ident}]")
                self.account_monitor_thread.start()
                logging.info(f"[多账号模式] 已启动账号监控线程: {self.account_monitor_thread.name} (id={self.account_monitor_thread.ident})")
            else:
                logging.debug("[多账号模式] 监控线程已在运行")

            # 立即为所有已登录且启用自动签到的账号创建刷新线程
            # 从JSON配置文件读取启用状态，而不是从INI文件的params读取
            for username, acc in list(self.accounts.items()):
                try:
                    # 检查账号是否已登录（必须有用户数据和ID）
                    if acc.user_data and acc.user_data.id and acc.user_data.username:
                        # 获取学校账号用户名
                        school_username = acc.user_data.username
                        # 检查该账号是否启用了自动签到（从JSON配置读取）
                        if _main()._is_auto_attendance_enabled(school_username):
                            # 账号已启用自动签到，创建刷新线程
                            account_id = str(acc.user_data.id)
                            self._ensure_account_refresh_thread(account_id)
                            logging.info(
                                f"[多账号模式] 已为账号 {username} (ID: {account_id}, "
                                f"学校账号: {school_username}) 创建刷新线程"
                            )
                except Exception as e:
                    logging.error(
                        f"[多账号模式] 为账号 {username} 创建刷新线程失败: {e}", exc_info=True)
        except Exception as e:
            self.log_and_notify_frontend(f"启动多账号监控线程失败: {e}")
            logging.error(f"[多账号模式] 启动监控线程失败: {e}", exc_info=True)

        if session_id:
            try:
                _main().save_session_state(session_id, self, force_save=True)
                logging.info(f"进入多账号模式：已保存会话状态到持久化存储")
            except Exception as e:
                logging.error(f"进入多账号模式：保存会话状态失败: {e}")

        return {"success": True, "params": self.global_params}

    def exit_multi_account_mode(self):
        """退出多账号模式，返回单用户登录页（增强：彻底停止所有执行）"""
        try:
            self.multi_stop_all_accounts()
            for acc in list(self.accounts.values()):
                try:
                    if acc.worker_thread and acc.worker_thread.is_alive():
                        acc.stop_event.set()
                        acc.worker_thread.join(timeout=1.0)
                except Exception:
                    pass
        except Exception:
            logging.debug(
                "exit_multi_account_mode: stop all accounts failed (non-fatal)."
            )

        for key, (path_result, completion_event) in list(
            self.path_gen_callbacks.items()
        ):
            path_result["error"] = "模式切换（退出多账号）已取消"
            try:

                completion_event.set()
            except Exception:
                pass
        self.path_gen_callbacks.clear()

        # [旧版] 停止旧的多账号刷新线程（为了向后兼容）
        try:
            self.stop_multi_auto_refresh.set()
            if (
                self.multi_auto_refresh_thread
                and self.multi_auto_refresh_thread.is_alive()
            ):
                self.multi_auto_refresh_thread.join(timeout=1.0)
            self.multi_auto_refresh_thread = None
        except Exception as e:
            logging.warning(f"停止多账号自动刷新线程失败: {e}")

        # [新版] 停止新的多账号监控线程
        try:
            # 设置停止标志
            self.stop_account_monitor.set()

            # 等待监控线程停止
            if (
                self.account_monitor_thread
                and self.account_monitor_thread.is_alive()
            ):
                self.account_monitor_thread.join(timeout=2.0)
                logging.info("[退出多账号模式] 监控线程已停止")

            self.account_monitor_thread = None
        except Exception as e:
            logging.warning(f"[退出多账号模式] 停止监控线程失败: {e}")

        # [新版] 停止所有账号的刷新线程
        try:
            # 使用线程锁保护对字典的访问
            with self.threads_lock:
                # 获取所有线程的副本（避免在迭代时修改字典）
                threads_to_stop = list(self.account_refresh_threads.items())

            # 停止每个线程
            # 注意：由于线程是守护线程且使用 stop_event，它们会自动退出
            # 这里主要是清理记录
            for account_id, thread in threads_to_stop:
                try:
                    if thread.is_alive():
                        logging.info(f"[退出多账号模式] 等待账号 {account_id} 的刷新线程停止")
                        # 线程会在检测到模式切换后自动退出，这里只等待一小段时间
                        thread.join(timeout=1.0)
                except Exception as e:
                    logging.warning(f"[退出多账号模式] 等待账号 {account_id} 线程失败: {e}")

            # 清空线程字典
            with self.threads_lock:
                self.account_refresh_threads.clear()
                logging.info("[退出多账号模式] 已清空所有账号刷新线程")
        except Exception as e:
            logging.error(f"[退出多账号模式] 停止账号刷新线程失败: {e}", exc_info=True)

        self._init_state_variables()
        self._load_global_config()
        self.log_and_notify_frontend("已退出多账号模式。")

        session_id = getattr(self, "_web_session_id", None)
        if session_id:
            try:
                _main().save_session_state(session_id, self, force_save=True)
                logging.info(f"退出多账号模式：已清空会话中的账号列表并保存")
            except Exception as e:
                logging.error(f"退出多账号模式：保存会话状态失败: {e}")

        return {"success": True}

    def enter_single_account_mode(self):
        """进入单账号模式（增强：先停止多账号运行）"""
        try:
            self.multi_stop_all_accounts()
            for acc in list(getattr(self, "accounts", {}).values()):
                try:
                    if acc.worker_thread and acc.worker_thread.is_alive():
                        acc.stop_event.set()
                        acc.worker_thread.join(timeout=1.0)
                except Exception:
                    pass
        except Exception:
            logging.debug(
                "enter_single_account_mode: stop multi failed (non-fatal).")

        for key, (path_result, completion_event) in list(
            self.path_gen_callbacks.items()
        ):
            path_result["error"] = "模式切换（进入单账号）已取消"
            try:
                completion_event.set()
            except Exception:
                pass
        self.path_gen_callbacks.clear()

        self.is_multi_account_mode = False
        self.log_and_notify_frontend("进入单账号模式。")
        return {"success": True}

    # def exit_single_account_mode(self):
    #     """
    #     退出单账号模式
    #     """
    #     try:
    #         if hasattr(self, "stop_event"):
    #             self.stop_event.set()

    #         if (
    #             hasattr(self, "worker_thread")
    #             and self.worker_thread
    #             and self.worker_thread.is_alive()
    #         ):
    #             self.worker_thread.join(timeout=1.0)

    #         if hasattr(self, "path_gen_callbacks"):
    #             for key, (path_result, completion_event) in list(
    #                 self.path_gen_callbacks.items()
    #             ):
    #                 path_result["error"] = "退出单账号模式已取消"
    #                 try:
    #                     completion_event.set()
    #                 except Exception:
    #                     pass
    #             self.path_gen_callbacks.clear()

    #         self.log("已退出单账号模式")
    #         return {"success": True}
    #     except Exception as e:
    #         logging.error(f"退出单账号模式失败: {e}", exc_info=True)
    #         return {"success": False, "message": f"退出失败: {str(e)}"}

    def get_session_mode_info(self):
        """获取会话模式信息（单账号/多账号），用于页面刷新时恢复状态"""
        mode_info = {
            "success": True,
            "is_multi_account_mode": getattr(self, "is_multi_account_mode", False),
            "school_account_logged_in": _main().get_business_session_login_success(self),
            "is_offline_mode": getattr(self, "is_offline_mode", False),
        }

        if getattr(self, "is_multi_account_mode", False):
            mode_info["multi_account_count"] = len(
                getattr(self, "accounts", {}))
            mode_info["multi_account_usernames"] = list(
                getattr(self, "accounts", {}).keys()
            )
            mode_info["global_params"] = getattr(self, "global_params", {})

            accounts_data = []
            for username, acc in getattr(self, "accounts", {}).items():
                accounts_data.append(
                    {
                        "username": username,
                        "name": acc.user_data.name if acc.user_data.name else username,
                        "status_text": acc.status_text,
                        "summary": acc.summary,
                        "params": acc.params,
                    }
                )
            mode_info["accounts"] = accounts_data
        else:
            mode_info["has_tasks"] = len(getattr(self, "all_run_data", [])) > 0
            mode_info["task_count"] = len(getattr(self, "all_run_data", []))
            mode_info["selected_task_index"] = getattr(
                self, "current_run_idx", -1)

            if hasattr(self, "user_data") and self.user_data:
                user_data = self.user_data
                mode_info["user_data"] = {
                    "name": getattr(user_data, "name", ""),
                    "phone": getattr(user_data, "phone", ""),
                    "student_id": getattr(user_data, "student_id", ""),
                    "id": getattr(user_data, "id", ""),
                    "username": getattr(user_data, "username", ""),
                    "gender": getattr(user_data, "gender", ""),
                    "school_name": getattr(user_data, "school_name", ""),
                }

        return mode_info

    def multi_get_all_config_users(self):
        """
        获取所有存在配置文件的用户列表，用于前端便捷添加
        """
        # 不再直接遍历旧的 .ini 配置文件以读取 UA 或密码
        # 改为从 school_accounts 的用户存储中获取已注册的账号列表
        all_users = []
        try:
            if hasattr(self, "auth_username") and self.auth_username:
                accounts = self._load_user_school_accounts(self.auth_username)
                if isinstance(accounts, dict):
                    all_users = sorted(list(accounts.keys()))
        except Exception:
            all_users = []

        filtered_users = []

        if hasattr(self, "auth_username") and self.auth_username:
            school_accounts = self._load_user_school_accounts(
                self.auth_username)

            for username in all_users:
                if username in school_accounts:
                    filtered_users.append(username)

            logging.debug(
                f"用户 {self.auth_username} 可访问的配置用户: {len(filtered_users)}/{len(all_users)}"
            )
        else:
            logging.warning("multi_get_all_config_users: 没有认证用户信息，返回空列表")

        return {"users": filtered_users}

    def multi_load_accounts_from_config(self, auth_username):
        """
        模式一：从配置文件加载账号
        """
        self.log_and_notify_frontend("正在从配置文件加载账号列表...")

        # 获取用户权限组，判断是否为管理员
        if hasattr(_main(), "auth_system") and _main().auth_system:
            user_group = _main().auth_system.get_user_group(auth_username)
            is_admin = user_group in ["admin", "super_admin"]
        else:
            # 如果无法获取权限信息，默认按管理员处理（向后兼容）
            is_admin = True
        logging.debug(
            f"multi_load_accounts_from_config: 用户 {auth_username}，管理员权限={is_admin}")
        users = {}

        if is_admin:
            # 管理员：遍历所有 school_accounts 并兼容 INI 格式
            # 使用 _load_user_school_accounts 的逻辑，它已经处理了管理员权限聚合
            self.log_and_notify_frontend("检测到管理员权限，加载所有用户的账号...")
            users = self._load_user_school_accounts(auth_username)
        else:
            # 普通用户：仅加载自己的账号
            self.log_and_notify_frontend(f"检测到普通用户权限，仅加载 {auth_username} 的账号...")
            file_path = self._get_user_accounts_file(auth_username)

            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # 标准化数据格式：兼容旧版 INI 和新版 JSON
                    for school_username, account_info in data.items():
                        if not _main().is_valid_school_username(
                            school_username
                        ):
                            continue
                        if isinstance(account_info, dict):
                            # 新格式：直接使用，并加载统计数据
                            stats = self._load_school_account_stats_from_ini(
                                school_username)
                            account_info["overdue_count"] = stats["overdue_count"]
                            account_info["completed_count"] = stats["completed_count"]
                        elif isinstance(account_info, str):
                            # 旧格式：转换为新格式
                            stats = self._load_school_account_stats_from_ini(
                                school_username)
                            data[school_username] = {
                                "password": account_info,
                                "ua": None,
                                "overdue_count": stats["overdue_count"],
                                "completed_count": stats["completed_count"]
                            }

                    users = data
                    logging.debug(
                        f"成功加载普通用户 {auth_username} 的账户，共 {len(users)} 个")
                except Exception as e:
                    logging.error(f"加载普通用户 {auth_username} 的账户失败: {e}")
                    users = {}

        # 将加载的账号添加到系统中
        loaded_count = 0
        accounts_missing_password = []
        for username, account_info in users.items():
            if username not in self.accounts:
                password = account_info.get("password")
                if password is None or password in ["", "null", "None", "NULL", "undefined"]:
                    accounts_missing_password.append(
                        {
                            "username": username,
                            "tag": account_info.get("tag"),
                        }
                    )
                else:
                    add_result = self.multi_add_account(
                        username, password, only_if_missing=True
                    )
                    if add_result and add_result.get("action") == "request_password":
                        accounts_missing_password.append(
                            {
                                "username": username,
                                "tag": add_result.get("tag"),
                            }
                        )
                    elif add_result and add_result.get("success"):
                        loaded_count += 1

        self.log_and_notify_frontend(f"已加载 {loaded_count} 个账号。")
        if accounts_missing_password:
            self.log_and_notify_frontend(
                f"发现 {len(accounts_missing_password)} 个账号缺少密码，等待用户手动添加。"
            )
        self._update_multi_global_buttons()
        final_status = self.multi_get_all_accounts_status()
        final_status["accounts_missing_password"] = accounts_missing_password
        return final_status

    def multi_add_account(
        self, username, password, tag=None, params=None, *, only_if_missing=False
    ):
        """
        模式二：手动或选择性添加账号

        Args:
            only_if_missing: 批量导入用。为 True 时，对**状态正常**的已存在
                账号一律跳过，绝不用文件里的密码去覆盖一个正在正常工作的
                会话（文件里的密码可能与本地记录不同，或本来就过期）。
                异常状态的账号仍然会走恢复路径。
                手动添加走默认值 False：那时给出新密码就是"我要改密码"，
                应当允许覆盖。
        """
        # [安全修复] 验证username输入，防止路径遍历和注入攻击
        if not username or not isinstance(username, str):
            logging.error("[安全] multi_add_account: username必须是非空字符串")
            return {"success": False, "error": "无效的用户名"}

        # [安全修复] 限制username长度，防止DoS攻击
        if len(username) > _main().MAX_USERNAME_LENGTH:
            logging.error(
                f"[安全] multi_add_account: username过长(>{_main().MAX_USERNAME_LENGTH})")
            return {"success": False, "error": "用户名过长"}

        # [安全修复] 验证username格式，只允许安全字符
        # 使用模块级编译的正则表达式，提高性能
        if _main().USERNAME_PATTERN and not _main().USERNAME_PATTERN.match(username):
            logging.error(
                f"[安全] multi_add_account: username包含非法字符: {username}")
            return {"success": False, "error": "用户名包含非法字符"}

        # 学号必须是纯数字且至少 4 位：防止把名单里的“序号/姓名”列当成账号
        # 和密码写进 school_accounts（真实事故：1.ini..21.ini、序号.ini 与
        # 两条 password=姓名 的 JSON 记录）。
        if not _main().is_valid_school_username(username):
            logging.error(
                f"[安全] multi_add_account: 学号必须是至少4位纯数字: {username!r}"
            )
            return {
                "success": False,
                "reason": "invalid_username",
                "message": "学号必须是至少4位数字（纯数字）",
                "username": username,
            }

        # [安全修复] 验证password类型和长度
        if password is not None:
            if not isinstance(password, str):
                logging.error("[安全] multi_add_account: password必须是字符串")
                return {"success": False, "error": "无效的密码"}
            if len(password) > _main().MAX_PASSWORD_LENGTH:
                logging.error(
                    f"[安全] multi_add_account: password过长(>{_main().MAX_PASSWORD_LENGTH})")
                return {"success": False, "error": "密码过长"}
            if not _main().is_valid_school_password(password):
                logging.error(
                    f"[安全] multi_add_account: 密码不能包含中文，学号: {username!r}"
                )
                return {
                    "success": False,
                    "reason": "invalid_password",
                    "message": "密码不能包含中文",
                    "username": username,
                }

        # [安全修复] 验证tag类型和长度
        if tag is not None:
            if not isinstance(tag, str):
                tag = str(tag)
            if len(tag) > _main().MAX_TAG_LENGTH:
                logging.error(
                    f"[安全] multi_add_account: tag过长(>{_main().MAX_TAG_LENGTH})")
                return {"success": False, "error": "标签过长"}

        if username in self.accounts:
            # 「添加」对**状态正常**的已存在账号是无操作：只允许更新元数据
            # （tag / params），绝不动会话与凭证。
            #
            # 「状态正常」的判定 = 密码验证过（is_first_login_verified）
            #                      且会话已建立（user_data.id 非空）
            #   - is_first_login_verified 由多账号刷新线程在登录成功后置 True，
            #     是"这个密码是对的"的权威依据；
            #   - user_data.id 由登录响应写入，为空表示当前没有可用会话。
            #
            # 账号处于异常状态时必须允许**覆盖**，否则"密码填错了想改对"
            # 就永远无法恢复（只能删掉再加回）：
            #   - 首次验证失败（密码错误 / 账号不存在）→ is_first_login_verified=False
            #   - 刷新失败、id 被清空 → user_data.id 为空
            # 这两种情况都按"新添加"处理，覆盖密码并重建会话。
            #
            # 历史行为（反面教材）：不分青红皂白"从配置重读密码并强制重登"，
            # 清空 cookies、置空 user_data.id、另起刷新线程。真实事故
            # （2026-10-11 19:07）：任务跑到 250/411 时前端对同一账号又提交了
            # 一次 multi_add_account，会话被清空，4 秒后下一次提交变成
            # "0 个 Cookie、无 shiroCookie、无 Authorization"的裸请求，
            # 被学校服务器拒绝为 400 `userId不能为空`（这是**认证失败**的表象，
            # 不是业务字段缺失），重试 10 次后任务中止。
            acc = self.accounts[username]

            if params and isinstance(params, dict):
                # [安全修复] 限制params中的键值对数量，防止DoS攻击
                if len(params) > _main().MAX_PARAMS_COUNT:
                    logging.error(
                        f"[安全] multi_add_account: params包含过多键值对(>{_main().MAX_PARAMS_COUNT})")
                    return {"success": False, "error": "参数过多"}
                for k, v in params.items():
                    if k in acc.params:
                        acc.params[k] = v

            account_is_healthy = bool(
                getattr(acc, "is_first_login_verified", False)
                and getattr(getattr(acc, "user_data", None), "id", "")
            )
            password_changed = bool(password) and (
                acc.password != password
            )

            # 导入时（only_if_missing）不允许用文件里的密码覆盖正常账号
            if only_if_missing:
                password_changed = False

            # 只有"状态正常 且 没给新密码"才是真正的"已存在，跳过"。
            # 给了新密码说明用户想改密码，异常状态说明需要恢复 —— 都要覆盖。
            if account_is_healthy and not password_changed:
                if tag is not None:
                    acc.tag = str(tag)
                    self._save_account_tag(username, acc.tag)
                    self.log_and_notify_frontend(f"已更新账号 [{username}] 的标记：{acc.tag}。")

                self.log_and_notify_frontend(f"账号 [{username}] 已存在，未重复添加。")
                logging.info(
                    f"[{username}] 账号已存在且状态正常，跳过重复添加"
                    f"（不清空会话、不重新登录）"
                )
                return {
                    "success": False,
                    "reason": "already_exists",
                    "message": f"账号 {username} 已存在，未重复添加。",
                    "username": username,
                    "accounts": self.multi_get_all_accounts_status().get(
                        "accounts", []
                    ),
                }

            # 走到这里说明要覆盖：异常状态恢复，或用户显式改了密码。
            if self._is_multi_account_execution_active(acc):
                # 运行中不能重建会话，否则会重演上面那次事故
                reason_text = (
                    "密码需要更新" if password_changed else "账号状态异常需要重新登录"
                )
                self.log_and_notify_frontend(
                    f"账号 [{username}] 正在执行任务，{reason_text}，"
                    f"本次未覆盖。请先停止该账号的任务后重试。"
                )
                return {
                    "success": False,
                    "reason": "account_running",
                    "message": (
                        f"账号 {username} 正在执行任务，{reason_text}，"
                        f"未执行覆盖。请先停止该账号的任务后重试。"
                    ),
                    "username": username,
                    "accounts": self.multi_get_all_accounts_status().get(
                        "accounts", []
                    ),
                }

            # 覆盖前先记下原有密码，然后**只在内存里**换成新密码去试。
            # 关键约定：新密码只有登录成功才落盘（见
            # _multi_refresh_worker_unlocked），登录失败就回滚成旧密码，
            # 这样"输错新密码"永远不会把原本可用的凭据弄丢。
            # 落盘统一走 _commit_pending_account_password/_rollback_pending_account_password。
            if password_changed:
                self._stage_pending_account_password(acc, password)
                self.log_and_notify_frontend(
                    f"账号 [{username}] 新密码已暂存，将重新登录验证；"
                    f"验证通过后才写入配置。"
                )
            elif password:
                # 状态异常的账号（本来就没有可用密码）：直接用新密码去试
                acc.password = password
                self.log_and_notify_frontend(f"已更新账号 [{username}] 的密码。")

            if tag is not None:
                acc.tag = str(tag)
                self._save_account_tag(username, acc.tag)
                self.log_and_notify_frontend(f"已更新账号 [{username}] 的标记：{acc.tag}。")

            if not password_changed:
                self.log_and_notify_frontend(
                    f"账号 [{username}] 处于异常状态"
                    f"（首次验证未通过或会话已失效），将重新登录。"
                )

            self._reset_account_session_for_relogin(acc, username)
            self._update_multi_global_buttons()
            return self.multi_get_all_accounts_status([{"success": True}])

        loaded_tag = self._load_account_tag(username)
        final_tag = tag if tag is not None else (
            loaded_tag if loaded_tag else "")
        self.accounts[username] = _main().AccountSession(
            username, password, self, tag=final_tag
        )

        # 不再从旧的配置文件/ini 中自动读取 UA 或密码；只使用调用时提供的密码
        # 如果没有显式提供 UA，则为会话生成随机 UA
        # 但支持从 school_accounts 中读取已保存的 UA 和密码（兼容新旧格式、权限感知）

        # 尝试从 school_accounts 中读取现有账号的 UA 和密码（支持权限检查）
        if not password:
            # 使用权限感知方法加载账号信息
            auth_username, is_admin = self._get_auth_user_and_check_admin()

            if auth_username:
                try:
                    # 根据权限加载账号列表（管理员查看所有，普通用户仅查看自己的）
                    accounts = self._load_accounts_by_permission(auth_username)

                    account_info = accounts.get(username)
                    if account_info:
                        if isinstance(account_info, dict):
                            password = account_info.get("password")
                            if account_info.get("ua"):
                                self.accounts[username].device_ua = account_info["ua"]
                                logging.debug(f"已从配置文件读取账号 {username} 的 UA")
                        else:
                            # 旧格式兼容（直接字符串）
                            password = account_info

                        if password:
                            logging.info(
                                f"已从配置文件读取账号 {username} 的密码 (发起用户: {auth_username}, 是否管理员: {is_admin})")
                    else:
                        logging.debug(
                            f"账号 {username} 未在 {('所有' if is_admin else '当前用户的')} 账户列表中找到")
                except Exception as e:
                    logging.debug(f"从 school_accounts 读取账号信息失败: {e}")

        if not self.accounts[username].device_ua:
            self.accounts[username].device_ua = _main().ApiClient.generate_random_ua()

        final_password = password or ""
        self.accounts[username].password = final_password

        if not final_password:
            try:
                del self.accounts[username]
            except Exception:
                pass
            self.log_and_notify_frontend(f"账号 {username} 缺少密码，已弹出输入框以完善密码。")
            return {
                "success": False,
                "message": "缺少密码",
                "action": "request_password",
                "username": username,
                "tag": final_tag,
            }

        ini_path = os.path.join(self.user_dir, f"{username}.ini")
        needs_verification = False

        # 如果用户提供了密码，则需要进行首次登录验证以确认凭据有效性
        if password:
            needs_verification = True
            self.log_and_notify_frontend(f"账号 {username} 提供了密码，标记为需要首次登录验证。")

        if needs_verification:
            self.accounts[username].is_first_login_verified = False
            self.accounts[username].is_verifying = True
            # 这里**不能**把密码写进配置：此刻密码还没经过登录验证，
            # 写进去会让一个错误的密码覆盖原有凭据。
            # 密码统一由 _multi_refresh_worker_unlocked 在登录成功后落盘，
            # 因此 _save_config 的语义是 "password=None 时保留现有密码"。
            # 这里只同步 UA。
            try:
                self._save_config(
                    username, password=None, ua=self.accounts[username].device_ua
                )
            except Exception:
                logging.warning(f"保存配置失败（将继续运行）：{traceback.format_exc()}")
        else:
            self.accounts[username].is_first_login_verified = True
            self.accounts[username].is_verifying = False
            try:
                pass  # 不再保存到 INI
            except Exception:
                logging.warning(f"保存配置失败（将继续运行）：{traceback.format_exc()}")

        self.log_and_notify_frontend(f"已添加账号: {username}")
        self._update_multi_global_buttons()

        session_id = getattr(self, "_web_session_id", None)
        if session_id and _main().socketio:
            try:
                current_thread = threading.current_thread()
                logging.info(f"[SocketIO Emit] Preparing 'accounts_updated' after account add from Thread[{current_thread.name}, id={current_thread.ident}]")
                current_accounts = self.multi_get_all_accounts_status().get(
                    "accounts", []
                )
                logging.info(f"[SocketIO Emit] Sending 'accounts_updated' to session {session_id[:8]}...")
                _main().socketio.emit(
                    "accounts_updated", {"accounts": current_accounts}, room=session_id
                )
                logging.info(f"[SocketIO Emit] 'accounts_updated' sent successfully")
            except Exception as e:
                current_thread = threading.current_thread()
                logging.error(f"SocketIO emit 'accounts_updated' failed from Thread[{current_thread.name}]: {e}")
                logging.error(f"Error type: {type(e).__name__}")
                logging.error(f"Full traceback: {traceback.format_exc()}")

        try:
            self._reset_account_session_for_relogin(
                self.accounts[username], username
            )
        except Exception:
            logging.error(f"启动刷新线程失败: {traceback.format_exc()}")

        if hasattr(self, "_web_session_id") and self._web_session_id:
            _main().save_session_state(self._web_session_id, self, force_save=True)

        # 保存到新路径（支持权限检查）
        auth_username = getattr(self, "auth_username", None)
        if auth_username:
            # 获取用户权限组，确定是否可以保存到聚合账号
            if hasattr(_main(), "auth_system") and _main().auth_system:
                user_group = _main().auth_system.get_user_group(auth_username)
                is_admin = user_group in ["admin", "super_admin"]
            else:
                is_admin = True

            try:
                if is_admin:
                    # 管理员：使用完整的聚合账号列表
                    accounts = self._load_user_school_accounts(auth_username)
                else:
                    # 普通用户：仅保存到自己的账号列表
                    file_path = self._get_user_accounts_file(auth_username)
                    accounts = {}
                    if os.path.exists(file_path):
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        # 标准化格式
                        for sch_user, account_info in data.items():
                            if isinstance(account_info, dict):
                                accounts[sch_user] = account_info
                            elif isinstance(account_info, str):
                                accounts[sch_user] = {
                                    "password": account_info,
                                    "ua": None
                                }

                accounts[username] = {
                    "password": self.accounts[username].password,
                    "ua": self.accounts[username].device_ua
                }
                self._save_user_school_accounts(auth_username, accounts)
            except Exception as e:
                logging.warning(f"保存账号到 school_accounts 失败: {e}")

        return self.multi_get_all_accounts_status([{"success": True}])

    def _stage_pending_account_password(self, acc, new_password):
        """把新密码暂存到内存并记住旧密码，等待登录验证。

        新密码先写进 `acc.password` 供登录使用；登录成功后由
        `_commit_pending_account_password` 才真正写进配置，
        失败则由 `_rollback_pending_account_password` 还原。
        """
        setattr(acc, "_pending_password", new_password)
        setattr(acc, "_password_before_change", getattr(acc, "password", ""))
        acc.password = new_password

    def _pending_account_password(self, acc):
        """返回待验证的新密码；没有待验证密码时返回 None。"""
        if getattr(acc, "_pending_password", None) is None:
            return None
        return acc.password

    def _commit_pending_account_password(self, acc):
        """登录成功：把暂存的新密码正式落盘，并清掉暂存标记。"""
        pending = self._pending_account_password(acc)
        if pending is None:
            return
        # 没有待验证密码的账号走原路径（保留 "password=None 保留现有密码" 语义）
        self._save_config(acc.username, acc.password, acc.device_ua)
        setattr(acc, "_pending_password", None)
        setattr(acc, "_password_before_change", None)
        acc.log_and_notify_frontend("新密码登录验证成功，已写入配置。")

    def _rollback_pending_account_password(self, acc):
        """登录失败：撤销内存里的新密码，恢复成原来可用的密码。"""
        if self._pending_account_password(acc) is None:
            return
        previous = getattr(acc, "_password_before_change", "") or ""
        acc.password = previous
        setattr(acc, "_pending_password", None)
        setattr(acc, "_password_before_change", None)
        acc.log_and_notify_frontend("新密码登录验证失败，已恢复原有密码。")

    def _reset_account_session_for_relogin(self, acc, username=None):
        """清空账号的会话状态并另起线程重新登录。

        提取出来是为了让"新增账号"和"覆盖异常账号"走同一条路径，
        避免两处各写一份而漂移。

        调用方**必须**先确认该账号没有在执行任务（见
        `_is_multi_account_execution_active`）：清空 cookies 会让运行中的
        提交变成无凭证的裸请求，被服务器拒绝为 400 `userId不能为空`。
        """
        username = username or getattr(acc, "username", "")
        try:
            acc.api_client.session.cookies.clear()
        except Exception:  # nosec B110 - 清理失败不阻塞重登
            pass
        acc.user_data.id = ""
        threading.Thread(
            target=self._multi_refresh_worker, args=(acc,), daemon=True
        ).start()

    def multi_remove_account(self, username):
        """移除一个账号"""
        if username in self.accounts:
            acc = self.accounts[username]

            # 停止账号的工作线程
            if (
                acc.worker_thread
                and acc.worker_thread.is_alive()
            ):
                acc.stop_event.set()

            # [新版] 停止并清理该账号的刷新线程
            try:
                if acc.user_data and acc.user_data.id:
                    account_id = str(acc.user_data.id)

                    # 使用线程锁保护对字典的访问
                    with self.threads_lock:
                        # 如果该账号有刷新线程，从字典中移除
                        if account_id in self.account_refresh_threads:
                            thread = self.account_refresh_threads[account_id]
                            del self.account_refresh_threads[account_id]

                            logging.info(
                                f"[移除账号] 已停止账号 {username} (ID: {account_id}) 的刷新线程"
                            )

                            # 可选：等待线程停止
                            if thread.is_alive():
                                thread.join(timeout=1.0)
            except Exception as e:
                logging.error(
                    f"[移除账号] 清理账号 {username} 的刷新线程失败: {e}",
                    exc_info=True
                )

            # 从账号字典中删除
            del self.accounts[username]
            self.log_and_notify_frontend(f"已移除账号: {username}")

        self._update_multi_global_buttons()
        if hasattr(self, "_web_session_id") and self._web_session_id:
            _main().save_session_state(self._web_session_id, self, force_save=True)
        return self.multi_get_all_accounts_status()

    def multi_refresh_all_statuses(self):
        """(多线程)刷新所有账号的任务状态和统计信息"""
        session_uuid = _main().session.get("uuid", "unknown")
        logging.info(
            f"[多账号自动刷新] 收到刷新请求，会话UUID: {session_uuid}, 当前账号数量: {len(self.accounts) if self.accounts else 0}"
        )

        if not self.accounts:
            self.log_and_notify_frontend("账号列表为空，无需刷新。")
            return {"success": True}

        self.log_and_notify_frontend("正在刷新所有账号状态...")
        for acc in self.accounts.values():
            if self._is_multi_account_execution_active(acc):
                continue
            self._update_account_status_js(acc, status_text="刷新中...")
            threading.Thread(
                target=self._multi_refresh_worker,
                args=(acc, False),
                daemon=True,
            ).start()

        self._update_multi_global_buttons()
        return {"success": True}

    def multi_refresh_single_status(self, username: str):
        """刷新指定账号的状态与摘要（单账号）"""
        if username not in self.accounts:
            return {"success": False, "message": "账号不存在"}
        acc = self.accounts[username]
        if self._is_multi_account_execution_active(acc):
            return {"success": False, "message": "该账号正在运行，暂不刷新"}

        try:
            self._update_account_status_js(acc, status_text="刷新中...")
            threading.Thread(
                target=self._multi_refresh_worker, args=(acc,), daemon=True
            ).start()
            return {"success": True}
        except Exception as e:
            logging.error(f"启动单账号刷新失败: {e}", exc_info=True)
            self._update_account_status_js(acc, status_text="刷新出错")
            return {"success": False, "message": "启动刷新失败"}

    def _multi_refresh_worker(self, acc: _main().AccountSession, preserve_status: bool = False):
        operation_lock = getattr(acc, "account_operation_lock", None)
        if operation_lock is None:
            return self._multi_refresh_worker_unlocked(acc, preserve_status)
        if not operation_lock.acquire(blocking=False):
            logging.debug(
                f"[{acc.username}] 账号正在执行其它操作，跳过本次状态刷新"
            )
            return
        try:
            return self._multi_refresh_worker_unlocked(acc, preserve_status)
        finally:
            operation_lock.release()

    def _multi_refresh_worker_unlocked(
        self,
        acc: _main().AccountSession,
        preserve_status: bool = False,
    ):
        """用于刷新的单个账号工作线程
        - preserve_status=True 时：若账号正在运行，不改写 status_text，只更新 name 与 summary
        """
        # Status refresh must not be cancelled by a previous task-stop signal.
        acc.api_client._execution_cancel_event = None
        try:
            acc.last_refresh_time = time.time()

            preserve_now = preserve_status and bool(
                acc.worker_thread and acc.worker_thread.is_alive()
            )

            if not acc.user_data.id:
                if not acc.device_ua:
                    acc.device_ua = _main().ApiClient.generate_random_ua()

                if not acc.is_first_login_verified:
                    acc.is_verifying = True
                    if not preserve_now:
                        self._update_account_status_js(
                            acc, status_text="首次验证中...")

                login_resp = self._queued_login(
                    acc, respect_global_stop=False, ignore_all_stops=True
                )
                if not login_resp or not login_resp.get("success"):
                    # 获取实际的错误信息，而不是假设密码错误
                    fail_msg = (
                        login_resp.get("message", "未知错误")
                        if login_resp
                        else "网络请求无响应"
                    )

                    # 新密码验证失败：回滚成原有密码，绝不把可用凭据弄丢
                    self._rollback_pending_account_password(acc)

                    if not acc.is_first_login_verified:
                        acc.is_verifying = False
                        acc.is_first_login_verified = False
                        if not preserve_now:
                            # 显示具体的错误信息
                            self._update_account_status_js(
                                acc, status_text=f"验证失败: {fail_msg}"
                            )
                        acc.log_and_notify_frontend(f"首次登录验证失败: {fail_msg}")
                    else:
                        if not preserve_now:
                            # 已验证过的账号刷新失败，也显示具体原因
                            self._update_account_status_js(
                                acc, status_text=f"刷新失败: {fail_msg}"
                            )
                    return

                data = login_resp.get("data", {})
                acc.user_data.username = (
                    getattr(acc.user_data, "username", "") or acc.username
                )
                self._apply_login_profile_to_user_data(acc.user_data, data)
                self._persist_school_account_backup(
                    acc.user_data.username,
                    data.get("userInfo", {}),
                    data.get("deptInfo", {}),
                    source="多账号刷新登录",
                )

                if not acc.is_first_login_verified:
                    acc.is_first_login_verified = True
                    acc.is_verifying = False
                    try:
                        self._save_config(
                            acc.username, acc.password, acc.device_ua)
                        acc.log_and_notify_frontend(f"首次登录验证成功，密码已保存到配置文件。")
                    except Exception as e:
                        logging.error(f"保存密码到配置文件失败: {e}", exc_info=True)
                else:
                    # 之前已验证过的账号重新登录成功：
                    # - 有待验证的新密码 → 此刻才正式落盘；
                    # - 没有 → 必须显式带上密码，否则 _save_config 的语义是
                    #   "password=None 时保留现有密码"，密码会永远写不进去。
                    ini_path = os.path.join(
                        self.user_dir, f"{acc.username}.ini")
                    if self._pending_account_password(acc) is not None:
                        self._commit_pending_account_password(acc)
                    elif os.path.exists(ini_path):
                        self._save_config(
                            acc.username, acc.password, acc.device_ua
                        )

                self._update_account_status_js(
                    acc, name=acc.user_data.name, status_text="获取数据..."
                )

            tasks_refreshed = self._multi_fetch_and_summarize_tasks(acc)
            if tasks_refreshed is False:
                acc.log_and_notify_frontend("获取任务列表失败，保留上次成功获取的任务状态。")
                if not preserve_now:
                    self._update_account_status_js(
                        acc, status_text="刷新失败: 获取任务列表失败"
                    )
                return

            # 顺带回收所有超时的自动签到记录（与当前账号是否登录无关），
            # 确保"刷新一次"也能清理那些已不在会话中的账号记录。
            try:
                sweep = _main().expire_stale_auto_attendance_accounts(
                    reason="refresh_worker"
                )
                if sweep.get("removed"):
                    logging.info(
                        f"[多账号刷新] 已回收 {len(sweep['removed'])} 条超时自动签到记录: "
                        f"{sweep['removed']}"
                    )
            except Exception as sweep_error:
                logging.error(
                    f"[多账号刷新] 回收超时自动签到记录失败: {sweep_error}",
                    exc_info=True,
                )

            if not preserve_now:
                self._multi_fetch_attendance_stats(acc)

            if not preserve_now:
                exe_cnt = acc.summary.get("executable", 0)
                not_started_cnt = acc.summary.get("not_started", 0)

                if exe_cnt > 0:
                    final_status = f"有 {exe_cnt} 个任务可执行"
                    acc.has_pending_tasks = True
                elif not_started_cnt > 0:
                    final_status = "无任务可执行"
                    acc.has_pending_tasks = False
                else:
                    final_status = "无任务可执行"
                    acc.has_pending_tasks = False

                if self._should_preserve_status(
                    acc.status_text, new_status=final_status
                ):
                    self._update_account_status_js(acc, summary=acc.summary)
                else:
                    self._update_account_status_js(
                        acc, status_text=final_status, summary=acc.summary
                    )

            acc.log_and_notify_frontend("状态刷新完成。")

            # 登录成功后，如果启用了自动签到，确保有刷新线程
            # 从JSON配置文件读取启用状态
            try:
                if acc.user_data and acc.user_data.id and acc.user_data.username:
                    account_id = str(acc.user_data.id)
                    school_username = acc.user_data.username

                    # 检查该账号是否启用了自动签到（从JSON配置读取）
                    if _main()._is_auto_attendance_enabled(school_username):
                        # 确保该账号有刷新线程
                        self._ensure_account_refresh_thread(account_id)
                        logging.info(
                            f"[多账号刷新] 账号 {acc.username} (ID: {account_id}, "
                            f"学校账号: {school_username}) 已登录，已确保刷新线程"
                        )
            except Exception as e:
                logging.error(
                    f"[多账号刷新] 为账号 {acc.username} 创建刷新线程失败: {e}",
                    exc_info=True
                )

            if (
                not preserve_now
                and hasattr(self, "_web_session_id")
                and self._web_session_id
            ):

                def delayed_save():
                    time.sleep(2)
                    try:
                        _main().save_session_state(
                            self._web_session_id, self, force_save=True)
                        logging.debug(f"账号 {acc.username} 刷新完成后已保存会话状态")
                    except Exception as e:
                        logging.error(f"延迟保存会话状态失败: {e}")

                threading.Thread(target=delayed_save, daemon=True).start()

        except Exception as e:
            logging.error(
                f"Error refreshing {acc.username}: {traceback.format_exc()}")
            if not preserve_status:
                self._update_account_status_js(acc, status_text="刷新出错")

    def multi_remove_selected_accounts(self, usernames: list[str]):
        """根据用户名列表移除多个账号"""
        if not usernames:
            return self.multi_get_all_accounts_status()

        removed_count = 0
        for username in usernames:
            if username in self.accounts:
                if (
                    self.accounts[username].worker_thread
                    and self.accounts[username].worker_thread.is_alive()
                ):
                    self.accounts[username].stop_event.set()
                del self.accounts[username]
                removed_count += 1

        self.log_and_notify_frontend(f"移除了 {removed_count} 个选定账号。")
        self._update_multi_global_buttons()
        if hasattr(self, "_web_session_id") and self._web_session_id:
            _main().save_session_state(self._web_session_id, self, force_save=True)

        return self.multi_get_all_accounts_status()

    def multi_remove_all_accounts(self):
        """一键移除所有账号"""
        if not self.accounts:
            return self.multi_get_all_accounts_status()

        self.multi_stop_all_accounts()

        count = len(self.accounts)
        self.accounts.clear()
        self.log_and_notify_frontend(f"已移除全部 {count} 个账号。")
        self._update_multi_global_buttons()
        if hasattr(self, "_web_session_id") and self._web_session_id:
            _main().save_session_state(self._web_session_id, self, force_save=True)
        return self.multi_get_all_accounts_status()

    def multi_get_all_accounts_status(self, addition=None):
        """获取所有账号的当前状态，用于刷新前端UI"""
        status_list = []
        for acc in self.accounts.values():
            tasks_simple = []
            if hasattr(acc, "all_run_data"):
                for r in acc.all_run_data:
                    tasks_simple.append(
                        {
                            "status": getattr(r, "status", 0),
                            "start_time": getattr(r, "start_time", ""),
                            "end_time": getattr(r, "end_time", ""),
                            "info_text": self._get_task_info_text(r),
                        }
                    )

            is_running = self._is_multi_account_execution_active(acc)
            current_pos = getattr(acc, "current_position",
                                  None) if is_running else None
            user_data = getattr(acc, "user_data", None)
            gender = getattr(user_data, "gender", "") or ""
            if not gender:
                backup_username = (
                    getattr(user_data, "username", "")
                    or getattr(user_data, "student_id", "")
                    or acc.username
                )
                gender = self._get_school_account_gender_from_backup(
                    backup_username
                )
                if gender and user_data is not None:
                    user_data.gender = gender

            status_list.append(
                {
                    "username": acc.username,
                    "name": acc.user_data.name or "---",
                    "gender": gender,
                    "status_text": acc.status_text,
                    "summary": acc.summary,
                    "tag": acc.tag,
                    "tasks": tasks_simple,
                    "current_position": current_pos,
                    "progress_pct": getattr(acc, "progress_pct", 0),
                    "progress_text": getattr(acc, "progress_text", ""),
                    "progress_extra": getattr(acc, "progress_extra", ""),
                }
            )

        response = {"accounts": status_list}

        if addition:
            if isinstance(addition, list):
                for item in addition:
                    if isinstance(item, dict):
                        response.update(item)
            elif isinstance(addition, dict):
                response.update(addition)
        response["success"] = True
        return response

    def _build_import_template_bytes(self) -> bytes:
        """按“莲峰账号导入表”版式生成模板（真实模板文件缺失时的兜底）。"""
        wb = _main().openpyxl.Workbook()
        sh = wb.active
        sh.title = "模板"

        sh.merge_cells(start_row=1, start_column=1, end_row=1, end_column=4)
        sh.cell(row=1, column=1, value="莲峰账号导入表")

        for column, header in enumerate(
            ("序号", "账号", "密码", "标记"), start=1
        ):
            sh.cell(row=2, column=column, value=header)

        # 预编排行只方便人工填写；空行导入时会被自动忽略。
        for row_index in range(1, _IMPORT_TEMPLATE_FREE_ROWS + 1):
            sh.cell(row=row_index + 2, column=1, value=row_index)

        for column, width in (("A", 6), ("B", 22), ("C", 18), ("D", 14)):
            sh.column_dimensions[column].width = width

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

    def multi_download_import_template(self):
        """下载导入模板：直接返回仓库真实模板文件，缺失时才按同版式生成。

        真实模板：`tests/fixtures/school_accounts_template.xlsx`
        （第 1 行合并标题“莲峰账号导入表”，第 2 行表头 `序号/账号/密码/标记`，
        序号列只用于人工对行、导入时忽略）。
        """
        try:
            template_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                _IMPORT_TEMPLATE_RELATIVE_PATH,
            )
            file_bytes = None
            if os.path.exists(template_path):
                try:
                    with open(template_path, "rb") as template_file:
                        file_bytes = template_file.read()
                except Exception as read_error:
                    logging.warning(
                        "读取导入模板文件失败，将使用内置版式生成: %s",
                        read_error,
                    )
            if not file_bytes:
                logging.warning(
                    "导入模板文件不存在或为空，使用内置版式生成: %s",
                    template_path,
                )
                file_bytes = self._build_import_template_bytes()

            file_content = base64.b64encode(file_bytes).decode("utf-8")
            filename = f"账号导入模板_{datetime.datetime.now().strftime('%Y%m%d')}.xlsx"

            self.log_and_notify_frontend(f"模板已生成：{filename}")
            return {
                "success": True,
                "filename": filename,
                "content": file_content,
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        except Exception as e:
            self.log_and_notify_frontend(f"模板生成失败：{e}")
            logging.error(
                f"Template generation failed: {traceback.format_exc()}")
            return {"success": False, "message": f"生成失败: {e}"}

    def multi_import_accounts(self, filename, base64_content):
        """从文件导入账号密码，支持 .xlsx/.xls/.csv（仅Web模式，从内存流处理）

        兼容三类常见表格：
        1. 系统模板（如“莲峰账号导入表”）：第 1 行标题、第 2 行表头
           `序号/账号/密码/标记`，序号列只用于人工对行，导入时忽略；
        2. 自定义表头：账号列支持 账号/用户名/学号 等别名，密码列支持
           密码/初始密码/password 等别名，标记列支持 标记/标签/备注；
        3. 完全没有表头：按数据内容推断“学号列”（最左且大多数值为
           ≥4 位纯数字的列），其后一列是密码、再一列是标记；推断不出时才
           退化为第 1/2/3 列。

        学号必须是纯数字且至少 4 位，否则该行计入“非法学号”并跳过，绝不
        允许把“序号/姓名”名单直接当成账号文件导入。

        Args:
            filename: 文件名（从前端传入）
            base64_content: Base64编码的文件内容（从前端传入）
        """
        try:
            file_data = base64.b64decode(base64_content)
            file_stream = io.BytesIO(file_data)

            ext = os.path.splitext(filename)[1].lower()

            logging.info(
                f"正在从内存处理上传的文件 {filename}（大小：{len(file_data)} 字节）"
            )
        except Exception as e:
            logging.error(f"解码Base64内容失败: {e}")
            return {"success": False, "message": f"文件处理失败: {e}"}

        # 逐行处理逻辑在三种格式之间完全一致，抽成一个辅助方法，
        # 避免 .xlsx / .xls / .csv 各写一份而慢慢漂移。
        state = {
            "added": [],
            "already_exists": [],
            "skipped_no_password": [],
            "duplicate_in_file": [],
            "skipped_running": [],
            "failed": [],
            "invalid_username": [],
            "invalid_password": [],
            "total_rows": 0,
        }
        seen_usernames: set[str] = set()

        def handle_row(raw_username, raw_password, raw_tag) -> None:
            """处理一行；结果直接累加到 state。"""
            username = str(raw_username or "").strip()
            if not username:
                return
            state["total_rows"] += 1

            if username in seen_usernames:
                state["duplicate_in_file"].append(username)
                return
            seen_usernames.add(username)

            # 学号格式校验必须在写入任何账号之前：1/序号/姓名 这类值
            # 绝不能进入 multi_add_account。
            if not _main().is_valid_school_username(username):
                state["invalid_username"].append(username)
                return

            tag = str(raw_tag).strip() if raw_tag else None
            password = str(raw_password or "").strip()

            # 行内没给密码时，回退到已保存的密码
            if not password:
                auth_username = getattr(self, "auth_username", None)
                if auth_username:
                    accounts = self._load_user_school_accounts(auth_username)
                    account_info = accounts.get(username)
                    if account_info:
                        password = account_info.get("password") or ""

            if not password:
                state["skipped_no_password"].append(
                    {"username": username, "tag": tag}
                )
                return

            # 密码不能包含中文：名单的“姓名”列是最典型的坏密码。
            if not _main().is_valid_school_password(password):
                state["invalid_password"].append(username)
                return

            result = self.multi_add_account(
                username, password, tag=tag, only_if_missing=True
            )
            if isinstance(result, dict) and result.get("reason") == "already_exists":
                state["already_exists"].append(username)
            elif isinstance(result, dict) and result.get("success"):
                state["added"].append(username)
            else:
                # 账号正在执行任务（reason=account_running）、学号格式非法
                # （reason=invalid_username）等失败原因分别归类，避免被误报成
                # "已存在"或"导入成功"。
                reason = (
                    result.get("reason")
                    if isinstance(result, dict)
                    else None
                )
                if reason == "invalid_username":
                    state["invalid_username"].append(username)
                elif reason == "invalid_password":
                    state["invalid_password"].append(username)
                elif reason:
                    state["skipped_running"].append(username)
                else:
                    state["failed"].append(username)

        def _parse_raw_rows():
            """把上传文件解析成二维表，供列识别与逐行处理复用。"""
            if ext == ".xlsx":
                try:
                    wb = _main().openpyxl.load_workbook(
                        file_stream, data_only=True, read_only=True, keep_links=False
                    )
                except TypeError as e:
                    warnings.warn(f"样式解析失败，已忽略样式: {e}")
                    file_stream.seek(0)
                    wb = _main().openpyxl.load_workbook(
                        file_stream,
                        data_only=True,
                        read_only=True,
                        keep_links=False,
                        keep_vba=False,
                    )

                sh = wb.active
                return [list(row) for row in sh.iter_rows(values_only=True)]

            if ext == ".xls":
                file_stream.seek(0)
                book = _main().xlrd.open_workbook(
                    file_contents=file_stream.read()
                )
                sh = book.sheet_by_index(0)
                return [
                    [sh.cell_value(r, c) for c in range(sh.ncols)]
                    for r in range(sh.nrows)
                ]

            if ext == ".csv":
                file_stream.seek(0)
                text_stream = io.TextIOWrapper(
                    file_stream, encoding="utf-8-sig", newline=""
                )
                text = text_stream.read()
                if not text.strip():
                    return []
                delimiter = ","
                try:
                    delimiter = csv.Sniffer().sniff(
                        text[:4096], delimiters=",;\t"
                    ).delimiter
                except Exception:  # nosec B110 - Sniffer 失败时退回逗号
                    delimiter = ","
                return list(csv.reader(io.StringIO(text), delimiter=delimiter))

            return None

        try:
            raw_rows = _parse_raw_rows()
            if raw_rows is None:
                return {"success": False, "message": f"不支持的导入格式: {ext}"}

            rows = [
                [_normalize_import_cell(cell) for cell in row]
                for row in raw_rows
            ]
            # 全空行直接丢弃：模板里预填的序号行不会进入统计。
            rows = [row for row in rows if any(row)]

            header = _detect_import_header(rows)
            if header is not None:
                start_index, account_col, password_col, tag_col = header
                data_rows = rows[start_index:]
            else:
                account_col, password_col, tag_col = _infer_import_columns(rows)
                data_rows = rows

            def _cell(row, column):
                if column is None or column < 0 or column >= len(row):
                    return ""
                return row[column]

            for row in data_rows:
                handle_row(
                    _cell(row, account_col),
                    _cell(row, password_col),
                    _cell(row, tag_col) or None,
                )

            summary = self._build_import_summary(state)
            # 前端靠 accounts 刷新多账号列表；旧实现返回的是
            # multi_get_all_accounts_status()，这里补回来
            summary["accounts"] = self.multi_get_all_accounts_status().get(
                "accounts", []
            )
            self.log_and_notify_frontend(summary["message"])
            logging.info(
                f"导入完成：共 {summary['total_rows']} 行，"
                f"新增 {summary['imported_count']}，"
                f"已存在 {summary['already_exists_count']}，"
                f"缺密码 {summary['skipped_count']}，"
                f"非法学号 {summary['invalid_username_count']}，"
                f"文件内重复 {summary['duplicate_in_file_count']}"
            )
            return summary

        except Exception as e:
            self.log_and_notify_frontend(f"导入失败: {e}")
            logging.error(f"导入多账号配置失败，详细错误信息: {traceback.format_exc()}")
            return {"success": False, "message": f"导入失败: {e}"}

    @staticmethod
    def _build_import_summary(state):
        """把逐行结果汇总成一份给前端用的完整结果。

        刻意**不做任何截断**：缺密码账号清单可能很长，截断会让用户
        无法知道到底哪些账号没导进来（历史上后端 alert 只列 20 个，
        这正是要修掉的问题）。
        """
        added = list(state.get("added") or [])
        already = list(state.get("already_exists") or [])
        skipped = list(state.get("skipped_no_password") or [])
        duplicated = list(state.get("duplicate_in_file") or [])
        running = list(state.get("skipped_running") or [])
        failed_other = list(state.get("failed") or [])
        invalid = list(state.get("invalid_username") or [])
        invalid_password = list(state.get("invalid_password") or [])

        failed = [{"username": u, "reason": "already_exists"} for u in already]
        failed += [
            {"username": item["username"], "reason": "skipped_no_password"}
            for item in skipped
        ]
        failed += [
            {"username": u, "reason": "account_running"} for u in running
        ]
        failed += [
            {"username": u, "reason": "invalid_username"} for u in invalid
        ]
        failed += [
            {"username": u, "reason": "invalid_password"}
            for u in invalid_password
        ]
        failed += [{"username": u, "reason": "failed"} for u in failed_other]

        message = (
            f"导入完成：新增 {len(added)} 个，"
            f"已存在跳过 {len(already)} 个，"
            f"缺密码跳过 {len(skipped)} 个"
        )
        if invalid:
            message += f"，学号格式不对跳过 {len(invalid)} 个"
        if invalid_password:
            message += f"，密码包含中文跳过 {len(invalid_password)} 个"
        if running:
            message += f"，执行中跳过 {len(running)} 个"
        if failed_other:
            message += f"，失败 {len(failed_other)} 个"
        if duplicated:
            message += f"，文件内重复 {len(duplicated)} 个"

        return {
            "success": True,
            "message": message,
            "total_rows": int(state.get("total_rows") or 0),
            "imported_count": len(added),
            "already_exists_count": len(already),
            "skipped_count": len(skipped),
            "duplicate_in_file_count": len(duplicated),
            "skipped_running_count": len(running),
            "failed_count": len(failed_other),
            "invalid_username_count": len(invalid),
            "invalid_password_count": len(invalid_password),
            "added": added,
            "already_exists": already,
            # 键名与 multi_load_accounts_from_config 保持一致，
            # 前端可以直接复用同一套缺密码补全队列
            "accounts_missing_password": skipped,
            "duplicate_in_file": duplicated,
            "skipped_running": running,
            "invalid_username": invalid,
            "invalid_password": invalid_password,
            "failed_names": failed_other,
            "failed": failed,
        }

    def multi_export_accounts_summary(self):
        """导出多账号汇总，支持 Web模式直接返回文件内容"""
        try:
            headers = [
                "账号",
                "姓名",
                "状态",
                "总任务数",
                "已完成",
                "未开始任务数",
                "可执行任务数",
                "已过期任务数",
            ]

            rows = []
            for acc in sorted(self.accounts.values(), key=lambda x: x.username):
                s = acc.summary
                rows.append(
                    [
                        acc.username,
                        acc.user_data.name or "---",
                        acc.status_text,
                        s.get("total", 0),
                        s.get("completed", 0),
                        s.get("not_started", 0),
                        s.get("executable", 0),
                        s.get("expired", 0),
                    ]
                )

            wb = _main().openpyxl.Workbook()
            sh = wb.active
            sh.title = "任务汇总"
            sh.append(headers)
            for r in rows:
                sh.append(r)

            for col in sh.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    v = "" if cell.value is None else str(cell.value)
                    max_len = max(max_len, len(v))
                sh.column_dimensions[col_letter].width = max_len + 2

            output = io.BytesIO()
            wb.save(output)
            output.seek(0)

            file_content = base64.b64encode(output.read()).decode("utf-8")
            filename = f"跑步任务汇总_{datetime.datetime.now().strftime('%Y%m%d')}.xlsx"

            self.log_and_notify_frontend(f"汇总信息已导出到 {filename}")
            return {
                "success": True,
                "filename": filename,
                "content": file_content,
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        except Exception as e:
            self.log_and_notify_frontend(f"导出失败: {e}")
            logging.error(
                f"Export accounts summary failed: {traceback.format_exc()}")
            return {"success": False, "message": f"导出失败: {e}"}

    def multi_get_account_params(self, username):
        """
        获取指定账号的参数配置。
        """
        if username in self.accounts:
            return {"success": True, "params": self.accounts[username].params}
        return {"success": False, "message": "账号不存在"}

    def multi_update_account_param(self, username, key, value):
        """
        更新指定账号的单个参数值。
        """
        if username not in self.accounts:
            return {"success": False, "message": "账号不存在"}

        acc = self.accounts[username]
        target_params = acc.params
        if key in target_params:
            try:
                original_type = type(target_params[key])
                if original_type is bool:
                    target_params[key] = (
                        bool(value)
                        if isinstance(value, bool)
                        else str(value).lower() in ("true", "1", "t", "yes")
                    )
                else:
                    target_params[key] = original_type(value)

                if key == "auto_attendance_success_limit":
                    target_params[key] = max(1, int(target_params[key]))

                # 只保存参数，不保存密码：无论这个密码是否已验证过，
                # 改参数都不该顺手把内存里的密码写进凭据库。
                # 密码只在登录成功后由 _multi_refresh_worker_unlocked 落盘。
                self._save_config(username)
                self.log_and_notify_frontend(f"已更新账号 [{username}] 的参数 {key}。")

                # 当 auto_attendance_enabled 参数改变时，更新JSON配置文件
                # 多账号模式下也需要使用JSON配置管理
                if key == "auto_attendance_enabled":
                    try:
                        # 检查账号是否已登录且有用户数据
                        if acc.user_data and acc.user_data.id and acc.user_data.username:
                            school_username = acc.user_data.username
                            account_id = str(acc.user_data.id)
                            # 获取会话UUID
                            session_uuid = getattr(
                                self, "_web_session_id", None)
                            # 认证用户名就是当前账号的用户名
                            auth_username = username

                            # 根据新的参数值决定启用还是禁用自动签到
                            if target_params[key]:  # 启用自动签到
                                if session_uuid:
                                    if _main()._enable_auto_attendance(school_username, session_uuid, auth_username):
                                        self._ensure_account_refresh_thread(
                                            account_id)
                                        logging.info(
                                            f"[多账号参数更新] 已启用自动签到 - "
                                            f"账号: {username}, 学校账号: {school_username}, "
                                            f"会话: {session_uuid}"
                                        )
                                    else:
                                        logging.error(
                                            f"[多账号参数更新] 启用自动签到失败 - "
                                            f"账号: {username}, 学校账号: {school_username}"
                                        )
                                else:
                                    logging.warning(
                                        f"[多账号参数更新] 无法启用自动签到：未找到会话UUID - "
                                        f"账号: {username}"
                                    )
                            else:  # 禁用自动签到
                                if _main()._disable_auto_attendance(school_username):
                                    with self.threads_lock:
                                        if account_id in self.account_refresh_threads:
                                            del self.account_refresh_threads[account_id]
                                    logging.info(
                                        f"[多账号参数更新] 已禁用自动签到 - "
                                        f"账号: {username}, 学校账号: {school_username}"
                                    )
                                else:
                                    logging.error(
                                        f"[多账号参数更新] 禁用自动签到失败 - "
                                        f"账号: {username}"
                                    )
                        else:
                            logging.debug(
                                f"[多账号参数更新] 账号 {username} 未登录，无法更新自动签到配置"
                            )
                    except Exception as e:
                        logging.error(
                            f"[多账号参数更新] 更新账号 {username} 的自动签到配置失败: {e}",
                            exc_info=True
                        )
                # [新版] 当 auto_attendance_refresh_s 参数改变时，处理刷新线程
                elif key == "auto_attendance_refresh_s":
                    try:
                        # 检查账号是否已登录且有用户ID
                        if acc.user_data and acc.user_data.id and acc.user_data.username:
                            school_username = acc.user_data.username
                            account_id = str(acc.user_data.id)

                            # 检查该账号是否启用了自动签到（从JSON配置读取）
                            if _main()._is_auto_attendance_enabled(school_username):
                                # 如果启用了自动签到，重启刷新线程以应用新的刷新间隔
                                self._ensure_account_refresh_thread(account_id)
                                logging.info(
                                    f"[多账号参数更新] 已更新刷新间隔 - "
                                    f"账号: {username} (ID: {account_id}), "
                                    f"刷新线程已重启"
                                )
                        else:
                            logging.debug(
                                f"[多账号参数更新] 账号 {username} 未登录，无需处理刷新线程"
                            )
                    except Exception as e:
                        logging.error(
                            f"[多账号参数更新] 处理账号 {username} 的刷新线程失败: {e}",
                            exc_info=True
                        )

                if hasattr(self, "_web_session_id") and self._web_session_id:
                    _main().save_session_state(self._web_session_id,
                                       self, force_save=True)

                return {"success": True}
            except (ValueError, TypeError) as e:
                return {"success": False, "message": str(e)}
        return {"success": False, "message": "Unknown parameter"}

    def _is_multi_account_execution_active(self, acc: _main().AccountSession) -> bool:
        """Return whether the account already owns an execution slot."""
        username = getattr(acc, "username", None)
        execution_lock = getattr(self, "multi_execution_lock", None)
        if execution_lock is not None and username is not None:
            with execution_lock:
                if username in getattr(self, "multi_active_executions", set()):
                    return True
        worker = getattr(acc, "worker_thread", None)
        return bool(worker and worker.is_alive())

    def _claim_single_school_account_execution(self):
        user_data = getattr(self, "user_data", None)
        user_info = getattr(self, "user_info", {}) or {}
        identities = [
            getattr(user_data, "username", ""),
            getattr(user_data, "student_id", ""),
            user_info.get("student_id", "") if isinstance(user_info, dict) else "",
            user_info.get("account", "") if isinstance(user_info, dict) else "",
        ]
        execution_token = object()
        claimed, conflict_identity = _main()._claim_school_account_execution(
            identities,
            execution_token,
        )
        if not claimed:
            return None, conflict_identity
        self._single_school_account_execution_token = execution_token
        return execution_token, None

    def _release_single_school_account_execution(self, execution_token):
        _main()._release_school_account_execution(execution_token)
        if (
            getattr(self, "_single_school_account_execution_token", None)
            is execution_token
        ):
            self._single_school_account_execution_token = None

    def _run_with_single_school_account_execution(
        self,
        execution_token,
        target,
        args,
    ):
        try:
            return target(*args)
        finally:
            self._release_single_school_account_execution(execution_token)

    def _mark_multi_account_run_stopped_if_idle(self):
        """没有账号 worker 在运行时，把 multi_run_stop_flag 恢复为“已停止”。

        multi_run_stop_flag 的语义是“当前没有多账号任务在跑，或已请求停止”：
        启动流程会先清空它；只要还有账号 worker 存活就保持清空，最后一个
        worker 退出后必须重新置位。旧实现只在“全部停止”时置位，账号 worker
        自然跑完后标志一直保持清空，空闲的多账号会话会被会话不活跃监控永久
        当成“多账号任务执行中”，无法按不活跃超时回收。
        """
        multi_stop_flag = getattr(self, "multi_run_stop_flag", None)
        if multi_stop_flag is None:
            return

        execution_lock = getattr(self, "multi_execution_lock", None)
        if execution_lock is None:
            multi_stop_flag.set()
            return

        with execution_lock:
            if getattr(self, "multi_active_executions", set()):
                return
            for acc in list((getattr(self, "accounts", None) or {}).values()):
                worker = getattr(acc, "worker_thread", None)
                if worker is not None and worker.is_alive():
                    return
            multi_stop_flag.set()

    def _finish_multi_account_worker(
        self,
        acc: _main().AccountSession,
        worker_thread: threading.Thread | None,
    ):
        """Release the per-account execution slot after the worker exits."""
        username = getattr(acc, "username", None)
        execution_lock = getattr(self, "multi_execution_lock", None)
        if execution_lock is not None and username is not None:
            with execution_lock:
                getattr(self, "multi_active_executions", set()).discard(username)
                if getattr(acc, "worker_thread", None) is worker_thread:
                    acc.worker_thread = None
        _main()._release_school_account_execution(
            getattr(acc, "_school_account_execution_token", None)
        )
        acc._school_account_execution_token = None
        operation_lock = getattr(acc, "account_operation_lock", None)
        if operation_lock is not None:
            try:
                operation_lock.release()
            except RuntimeError:
                pass
        # 最后一个账号 worker 退出后把全局标志恢复为“已停止”，否则自然跑完的
        # 空闲会话会被会话不活跃监控永久当成“多账号任务执行中”。
        self._mark_multi_account_run_stopped_if_idle()

    def _start_multi_account_worker(
        self,
        acc: _main().AccountSession,
        delay: float,
        run_only_incomplete: bool,
    ) -> bool:
        """Start at most one execution thread for an account."""
        username = getattr(acc, "username", None)
        if not username:
            return False
        execution_lock = getattr(self, "multi_execution_lock", None)
        if execution_lock is None:
            execution_lock = threading.RLock()
            self.multi_execution_lock = execution_lock
            self.multi_active_executions = set()

        with execution_lock:
            active_executions = getattr(self, "multi_active_executions", set())
            if username in active_executions:
                return False
            worker = getattr(acc, "worker_thread", None)
            if worker and worker.is_alive():
                return False

            operation_lock = getattr(acc, "account_operation_lock", None)
            if operation_lock is None:
                operation_lock = threading.Lock()
                acc.account_operation_lock = operation_lock
            if not operation_lock.acquire(blocking=False):
                return False

            execution_token = object()
            claimed, _conflict = _main()._claim_school_account_execution(
                [
                    acc.username,
                    getattr(acc.user_data, "username", ""),
                    getattr(acc.user_data, "student_id", ""),
                ],
                execution_token,
            )
            if not claimed:
                operation_lock.release()
                return False

            active_executions.add(username)
            acc._school_account_execution_token = execution_token
            acc.stop_event.clear()
            multi_stop_flag = getattr(self, "multi_run_stop_flag", None)
            if multi_stop_flag is not None and multi_stop_flag.is_set():
                multi_stop_flag.clear()
            thread_ref: dict[str, threading.Thread | None] = {"thread": None}

            def run_worker():
                try:
                    self._multi_account_worker(
                        acc,
                        delay,
                        run_only_incomplete,
                    )
                finally:
                    self._finish_multi_account_worker(
                        acc,
                        thread_ref.get("thread"),
                    )

            worker = threading.Thread(
                target=run_worker,
                daemon=True,
                name=f"MultiAccountWorker-{username}",
            )
            thread_ref["thread"] = worker
            acc.worker_thread = worker
            try:
                worker.start()
            except Exception:
                active_executions.discard(username)
                acc.worker_thread = None
                _main()._release_school_account_execution(execution_token)
                acc._school_account_execution_token = None
                try:
                    operation_lock.release()
                except RuntimeError:
                    pass
                # 已经清空“已停止”标志却一个 worker 都没跑起来：必须补回置位。
                self._mark_multi_account_run_stopped_if_idle()
                raise
            return True

    def multi_start_single_account(
        self,
        username,
        run_only_incomplete: bool = True,
        bypass_overdue: bool = False,
        waive_charge: bool = False,
    ):
        """
        启动指定账号的任务执行线程。

        功能说明：
            在启动任务前，会检查该账号是否存在欠费。
            如果存在欠费（overdue_count > 0），则拒绝启动任务。

        参数：
            username: 学校账号用户名
            run_only_incomplete: 是否只运行未完成的任务
            bypass_overdue: 存在欠费时是否按“强制执行”继续（需有 bypass_overdue 权限）
            waive_charge:   本次执行是否不计费（仅管理员/超级管理员生效）

        返回：
            包含 success 和 message 的字典
            如果存在欠费，还会包含 error_code 和 overdue_accounts
        """
        # 步骤1：检查账号是否存在
        if username not in self.accounts:
            return {"success": False, "message": "账号不存在"}

        # 步骤2：欠费检查（仅在付费模式下执行）
        if self._payment_required_for_overdue_gate():
            # 从账单文件读取该账号待支付账单数量作为欠费次数
            overdue_count = _main()._count_pending_bills_for_school(username)

            # 如果存在欠费，拒绝启动任务
            if overdue_count > 0 and not self._overdue_bypass_allowed(
                bypass_overdue
            ):
                self.log_and_notify_frontend(f"[欠费检查] 账号 {username} 存在欠费 ({overdue_count} 次)，拒绝启动任务")
                return {
                    "success": False,
                    "message": "有账号存在欠费，请先缴费",
                    "error_code": "OVERDUE_PAYMENT",
                    "overdue_accounts": [
                        {
                            "school_username": username,
                            "overdue_count": overdue_count
                        }
                    ]
                }

        # 本次执行的计费豁免状态（仅管理员可用；不请求豁免时重置为 False）。
        self.waive_charge_active = self._resolve_waive_charge(waive_charge)

        acc = self.accounts[username]
        if self._is_multi_account_execution_active(acc):
            self.log_and_notify_frontend(f"账号 {username} 已在运行中。")
            return {"success": False, "message": "该账号已在运行"}

        # 步骤3：原子占用该账号的执行槽，避免双击或并发 API 启动多个线程
        if not self._start_multi_account_worker(
            acc,
            0,
            bool(run_only_incomplete),
        ):
            self.log_and_notify_frontend(f"账号 {username} 正在执行其它操作。")
            return {"success": False, "message": "该账号正在运行或刷新，请稍后重试"}
        self.log_and_notify_frontend(f"已启动账号: {username}")
        self._update_multi_global_buttons()
        return {"success": True}

    def multi_stop_single_account(self, username):
        """
        停止指定账号的任务执行线程。
        """
        acc = self.accounts.get(username)
        if not acc:
            return {"success": False, "message": f"账号 {username} 不存在"}

        if self._is_multi_account_execution_active(acc):
            acc.stop_event.set()
            self.log_and_notify_frontend(f"已向账号 {username} 发送停止信号。")
            self._update_account_status_js(acc, status_text="正在停止...")
            self._update_multi_global_buttons()

            def _watch_stop():
                try:
                    while acc.worker_thread and acc.worker_thread.is_alive():
                        time.sleep(0.2)
                    acc.worker_thread = None
                    # 停止请求已发出：保留 worker 收尾写入的“已停止”，
                    # 不能被“待命”覆盖（真实缺陷：停止后列表显示待命）。
                    if acc.stop_event.is_set():
                        self._update_account_status_js(acc, status_text="已停止")
                    elif not self._should_preserve_status(
                        acc.status_text, new_status="待命"
                    ):
                        self._update_account_status_js(acc, status_text="待命")
                    self._update_multi_global_buttons()
                except Exception:
                    logging.debug(
                        "Stop watcher encountered a non-fatal error.", exc_info=True
                    )

            threading.Thread(target=_watch_stop, daemon=True).start()

            return {"success": True}
        else:
            self._update_account_status_js(acc, status_text="待命")
            self._update_multi_global_buttons()
            return {"success": False, "message": "该账号未在运行"}

    def multi_start_all_accounts(
        self,
        min_delay,
        max_delay,
        use_delay,
        run_only_incomplete,
        skip_overdue=False,
        bypass_overdue: bool = False,
        waive_charge: bool = False,
    ):
        """
        一键启动所有账号的任务

        功能说明：
            在启动所有任务前，会检查所有账号是否存在欠费。
            如果任何账号存在欠费（overdue_count > 0），则拒绝启动所有任务。

        参数：
            min_delay: 最小延迟时间（秒）
            max_delay: 最大延迟时间（秒）
             use_delay: 是否使用延迟
             run_only_incomplete: 是否只运行未完成的任务
             skip_overdue: 是否跳过欠费账号并启动其余账号
             bypass_overdue: 存在欠费时是否按“强制执行”继续（需有 bypass_overdue 权限）
             waive_charge:   本次执行是否不计费（仅管理员/超级管理员生效）

        返回：
            包含 success 和 message 的字典
            如果存在欠费，还会包含 error_code 和 overdue_accounts
        """
        # 步骤1：检查账号列表是否为空
        if not self.accounts:
            self.log_and_notify_frontend("账号列表为空，无法开始。请先添加账号。")
            return {
                "success": False,
                "message": "账号列表为空，无法开始。请先添加账号。",
            }

        # 步骤2：欠费检查（仅在付费模式下执行）
        overdue_accounts_list = []
        if self._payment_required_for_overdue_gate():
            # 遍历所有账号，检查是否存在欠费
            for username in self.accounts.keys():
                # 从账单文件读取该账号待支付账单数量作为欠费次数
                overdue_count = _main()._count_pending_bills_for_school(username)

                # 如果存在欠费，记录到列表中
                if overdue_count > 0:
                    overdue_accounts_list.append({
                        "school_username": username,
                        "overdue_count": overdue_count
                    })
        else:
            self.log_and_notify_frontend("[欠费检查] 当前为免费模式，跳过欠费拦截。")

        # 如果发现任何账号有欠费，拒绝启动所有任务（拿到授权并点了强制执行
        # 的用户放行，且不再跳过欠费账号）。
        force_allowed = self._overdue_bypass_allowed(bypass_overdue)
        if overdue_accounts_list and not skip_overdue and not force_allowed:
            self.log_and_notify_frontend(
                f"[欠费检查] 发现 {len(overdue_accounts_list)} 个账号存在欠费，拒绝启动任务"
            )
            return {
                "success": False,
                "message": "有账号存在欠费，请先缴费",
                "error_code": "OVERDUE_PAYMENT",
                "overdue_accounts": overdue_accounts_list
            }

        skipped_overdue_usernames = (
            set()
            if force_allowed
            else {
                item["school_username"]
                for item in overdue_accounts_list
                if item.get("school_username")
            }
        )
        account_list = [
            acc
            for acc in self.accounts.values()
            if acc.username not in skipped_overdue_usernames
        ]
        if not account_list:
            return {
                "success": False,
                "message": "全部账号均存在欠费",
                "error_code": "OVERDUE_PAYMENT",
                "overdue_accounts": overdue_accounts_list,
            }
        if skipped_overdue_usernames:
            self.log_and_notify_frontend(
                f"[欠费检查] 已跳过 {len(skipped_overdue_usernames)} 个欠费账号，"
                "继续启动其余账号。"
            )

        # 本次执行的计费豁免状态（仅管理员可用；不请求豁免时重置为 False）。
        self.waive_charge_active = self._resolve_waive_charge(waive_charge)

        # 步骤3：检查是否所有账号都已在运行
        total_accounts = len(self.accounts)
        running_count = sum(
            1
            for acc in self.accounts.values()
            if self._is_multi_account_execution_active(acc)
        )
        if total_accounts > 0 and running_count == total_accounts:
            return {"success": False, "message": "任务已在运行中"}

        # 步骤4：准备启动所有账号
        self.log_and_notify_frontend("开始执行所有账号...")
        self._update_multi_global_buttons()
        if self.multi_run_stop_flag.is_set():
            self.multi_run_stop_flag.clear()

        num_accounts = len(account_list)
        delays = [0] * num_accounts

        # 步骤5：计算延迟时间（如果启用）
        if use_delay and num_accounts > 0 and max_delay >= min_delay:
            try:
                delays = [
                    random.uniform(min_delay, max_delay) for _ in range(num_accounts)
                ]
            except ValueError:
                delays = [
                    random.uniform(min_delay, max_delay) for _ in range(num_accounts)
                ]

        random.shuffle(account_list)

        # 步骤6：启动所有账号的任务线程
        started_threads = self._start_multi_account_threads(
            account_list,
            delays,
            use_delay,
            run_only_incomplete,
        )

        if started_threads == 0:
            # 清空“已停止”标志后一个账号都没真正启动：若当前也没有账号在跑，
            # 必须把标志补回去，否则空闲会话会被会话不活跃监控永久保活。
            self._mark_multi_account_run_stopped_if_idle()
            self.log_and_notify_frontend("当前没有可启动的账号任务。")
            return {"success": False, "message": "当前没有可启动的账号任务。"}

        self._update_multi_global_buttons()
        return {
            "success": True,
            "started_accounts": started_threads,
            "skipped_overdue_accounts": overdue_accounts_list
            if skip_overdue
            else [],
        }

    def multi_stop_all_accounts(self):
        """停止所有账号的运行"""
        logging.info("API调用: multi_stop_all_accounts - 停止所有多账号任务的运行")
        # 停止后清掉“此次不计费”状态，下一次启动必须重新明确申请豁免。
        self.waive_charge_active = False
        if not self.accounts:
            self.log_and_notify_frontend("当前无账号，无需停止。")
            self.multi_run_stop_flag.set()
            return {"success": False, "message": "当前无账号，无需停止。"}

        if self.multi_run_stop_flag.is_set():
            return {"success": True}

        self.log_and_notify_frontend("正在发送停止信号...")
        self.multi_run_stop_flag.set()
        for acc in self.accounts.values():
            acc.stop_event.set()
        self._update_multi_global_buttons()
        self.log_and_notify_frontend("所有任务将在当前步骤完成后停止。")
        self._update_multi_global_buttons()

        time.sleep(1)

        self._update_multi_global_buttons()
        return {"success": True}

    def _update_account_status_js(
        self,
        acc: _main().AccountSession,
        status_text: str = None,
        summary: dict = None,
        name: str = None,
        progress_pct: int | None = None,
        progress_text: str | None = None,
        progress_extra: str | None = None,
    ):
        """一个辅助函数，用于向前端发送状态更新

        内存字段（status_text/progress_* 等）必须无条件更新：多账号列表的轮询
        接口 multi_get_all_accounts_status 读的就是这些字段，socket 只是推送
        通道；缺少 socketio 或会话 ID 时若直接返回，状态栏会一直停在旧文案。
        """
        update_data = {}
        if status_text is not None:
            acc.status_text = status_text
            update_data["status_text"] = status_text
        if summary is not None:
            acc.summary = summary
            update_data["summary"] = summary
        if name is not None:
            update_data["name"] = name

        if progress_pct is not None:
            acc.progress_pct = int(progress_pct)
            update_data["progress_pct"] = int(progress_pct)
        if progress_text is not None:
            acc.progress_text = progress_text
            update_data["progress_text"] = progress_text
        if progress_extra is not None:
            acc.progress_extra = progress_extra
            update_data["progress_extra"] = progress_extra

        session_id = getattr(self, "_web_session_id", None)
        if update_data and session_id and _main().socketio:
            try:
                _main().socketio.emit(
                    "multi_status_update",
                    {"username": acc.username, "data": update_data},
                    room=session_id,
                )
                time.sleep(0.001)
            except Exception as e:
                logging.error(
                    f"SocketIO emit 'multi_status_update' failed: {e}")
        elif update_data:
            logging.debug(
                f"仅更新内存状态（缺少会话ID或socketio未初始化），账号: {acc.username}"
            )

        self._update_multi_global_buttons()

    def _update_multi_global_buttons(self):
        """根据当前多账号状态刷新“全部开始/全部停止/返回登录页”按钮的可用性"""
        session_id = getattr(self, "_web_session_id", None)
        if not session_id or not _main().socketio:
            logging.debug(
                "跳过多账号全局按钮更新（_update_multi_global_buttons），原因: 缺少会话ID或socketio未初始化"
            )
            return

        active_accounts = []
        for acc in self.accounts.values():
            total = acc.summary.get("total", 0)
            expired = acc.summary.get("expired", 0)
            not_started = acc.summary.get("not_started", 0)
            executable = acc.summary.get("executable", 0)
            candidates = max(0, total - expired - not_started)
            has_tasks = (
                (executable > 0) if self.multi_run_only_incomplete else (
                    candidates > 0)
            )
            if has_tasks:
                active_accounts.append(acc)

        total_active = len(active_accounts)
        running_count = sum(
            1
            for acc in active_accounts
            if self._is_multi_account_execution_active(acc)
        )

        if total_active == 0:
            start_disabled = True
            stop_disabled = True
            exit_disabled = False
        elif running_count == 0:
            start_disabled = False
            stop_disabled = True
            exit_disabled = False
        elif running_count == total_active:
            start_disabled = True
            stop_disabled = False
            exit_disabled = True
        else:
            start_disabled = False
            stop_disabled = False
            exit_disabled = True

        try:
            _main().socketio.emit(
                "multi_global_buttons_update",
                {
                    "start_disabled": start_disabled,
                    "stop_disabled": stop_disabled,
                    "exit_disabled": exit_disabled,
                },
                room=session_id,
            )
        except Exception as e:
            logging.error(
                f"SocketIO emit 'multi_global_buttons_update' failed: {e}")

    def _queued_login(
        self,
        acc: _main().AccountSession,
        respect_global_stop: bool = True,
        ignore_all_stops: bool = False,
    ) -> dict | None:
        """
        多账号模式下的“排队登录”：
        """
        try:
            self._update_account_status_js(acc, status_text="排队登录...")
        except Exception:
            pass

        while True:
            if not ignore_all_stops and (
                acc.stop_event.is_set()
                or (respect_global_stop and self.multi_run_stop_flag.is_set())
            ):
                logging.debug(
                    f"[{acc.username}] 登录被中止: stop_event={acc.stop_event.is_set()}"
                )
                return None

            try:
                acquired = self.multi_login_lock.acquire(blocking=False)
                if acquired:
                    break

                time.sleep(0.5)

            except (Exception, BaseException) as e:
                logging.warning(
                    f"[{acc.username}] 获取登录锁异常 ({type(e).__name__}): {e}，正在尝试修复锁..."
                )

                try:
                    # from eventlet import patcher

                    native_threading = _main().eventlet.patcher.original("threading")
                    self.multi_login_lock = native_threading.Semaphore(1)
                    logging.info(
                        "[Lock Repair] 已将 multi_login_lock 重置为原生 Semaphore"
                    )
                except Exception as reset_err:
                    logging.error(f"[Lock Repair] 重置锁失败: {reset_err}")
                    pass

                time.sleep(0.5)
                continue

        try:
            if not ignore_all_stops and (
                acc.stop_event.is_set()
                or (respect_global_stop and self.multi_run_stop_flag.is_set())
            ):
                self.multi_login_lock.release()
                return None

            self._update_account_status_js(acc, status_text="正在登录...")

            return acc.api_client.login(acc.username, acc.password)
        except Exception as e:
            logging.error(
                f"[{acc.username}] 执行登录请求时发生异常: {e}", exc_info=True
            )
            try:
                self.multi_login_lock.release()
            except Exception:
                pass
            return {"success": False, "message": f"登录执行异常: {e}"}
        finally:
            try:
                self.multi_login_lock.release()
            except Exception:
                pass

    def _summarize_multi_account_run_data(
        self,
        acc: _main().AccountSession,
        run_data_list=None,
        multi_run_only_incomplete=None,
    ) -> dict:
        """按“仅执行未完成”开关统计任务（worker / 列表 / 开关切换共用口径）。

        - 勾选（True）：已完成任务只计入 completed，不再计入可跑/过期/未开始；
        - 不勾选（False）：已完成任务仍按时间状态参与可跑/过期/未开始统计，
          即完成过的任务只要还在时间窗口内就可以重跑。
        """
        if run_data_list is None:
            run_data_list = getattr(acc, "all_run_data", None) or []
        if multi_run_only_incomplete is None:
            multi_run_only_incomplete = self.multi_run_only_incomplete

        total = len(run_data_list)
        completed = 0
        expired = 0
        executable = 0
        not_started = 0

        now = datetime.datetime.now()
        ignore_time = acc.params.get("ignore_task_time", True)

        for run in run_data_list:
            if getattr(run, "status", 0) == 1:
                completed += 1
                if multi_run_only_incomplete:
                    continue

            time_state = self._get_task_time_state(run, ignore_time, now)
            if time_state == "expired":
                expired += 1
                continue
            if time_state == "not_started":
                not_started += 1
                continue

            executable += 1

        return {
            "total": total,
            "completed": completed,
            "pending": total - completed,
            "not_started": not_started,
            "executable": executable,
            "expired": expired,
            # 未过期任务数量 = 总数 - 已过期
            "unexpired_count": max(0, total - expired),
            # 未过期且未完成的任务数量 = 总数 - 已过期 - 已完成
            "unexpired_incomplete_count": max(0, total - expired - completed),
        }

    def _refresh_multi_account_summary_for_mode(self, acc) -> None:
        """按当前“仅执行未完成”开关，用缓存任务重算 summary 与状态文案。"""
        run_data = getattr(acc, "all_run_data", None) or []
        had_snapshot = bool(run_data)
        summary = self._summarize_multi_account_run_data(acc, run_data)
        acc.summary.update(summary)

        status_text = str(getattr(acc, "status_text", "") or "")

        # 运行中的账号由 worker 维护进度文案，这里只刷新统计数字。
        if self._is_multi_account_execution_active(acc):
            self._update_account_status_js(acc, summary=acc.summary)
            return

        # 还没拉取过任务列表的账号，不要凭空把状态写成“无任务可执行”。
        is_task_count_status = (
            status_text.endswith("个任务可执行")
            or status_text in ("无任务可执行", "无可执行任务")
        )
        if not had_snapshot and not is_task_count_status:
            self._update_account_status_js(acc, summary=acc.summary)
            return

        # 已停止/已中止/已取消与错误态保持原样，切换开关不能覆盖终态文案。
        if any(
            keyword in status_text
            for keyword in ("已停止", "已中止", "已取消", "失败", "出错")
        ):
            self._update_account_status_js(acc, summary=acc.summary)
            return

        final_status = (
            f"有 {summary['executable']} 个任务可执行"
            if summary["executable"] > 0
            else "无任务可执行"
        )
        if self._should_preserve_status(status_text, new_status=final_status):
            self._update_account_status_js(acc, summary=acc.summary)
            return
        self._update_account_status_js(
            acc, status_text=final_status, summary=acc.summary
        )

    def _multi_fetch_and_summarize_tasks(self, acc: _main().AccountSession):
        """(辅助函数) 为单个账号获取任务列表并计算统计信息（按任务ID去重）"""
        fetched_run_data = []
        seen_keys: set[str] = set()
        offset = 0
        dup_count = 0

        while True:
            if acc.stop_event.is_set():
                return None
            resp = acc.api_client.get_run_list(acc.user_data.id, offset)
            if not resp or not resp.get("success"):
                acc.log_and_notify_frontend("获取任务列表失败。")
                return False

            tasks = resp.get("data", {}).get("errandList", [])
            if not tasks:
                break

            for td in tasks:
                eid = td.get("errandId") or ""
                es = td.get("errandSchedule") or ""
                st = td.get("startTime") or ""
                et = td.get("endTime") or ""
                unique_key = f"{eid}|{es}|{st}|{et}"

                if unique_key in seen_keys:
                    dup_count += 1
                    continue
                seen_keys.add(unique_key)

                run = _main().RunData()
                run.run_name = td.get("eName")

                try:
                    run.status = int(td.get("isExecute") or 0)
                except (TypeError, ValueError):
                    run.status = (
                        1
                        if str(td.get("isExecute")).strip().lower()
                        in ("1", "true", "yes")
                        else 0
                    )

                run.errand_id = eid
                run.errand_schedule = es
                run.start_time = st
                run.end_time = et
                fetched_run_data.append(run)

                logging.info(
                    f"[{acc.username}] Parsed task {eid!r}: raw_isExecute={td.get('isExecute')!r} -> status={run.status}"
                )

            offset += len(tasks)
            if len(tasks) < 10:
                break

        if dup_count > 0:
            logging.info(
                f"[{acc.username}] Task de-dup: {dup_count} duplicates skipped (by errandId)."
            )

        acc.all_run_data = fetched_run_data
        summary = self._summarize_multi_account_run_data(acc, fetched_run_data)
        acc.summary.update(summary)
        acc.has_pending_tasks = summary["executable"] > 0
        return True

    @staticmethod
    def _format_multi_task_summary(acc: _main().AccountSession) -> str:
        """
        把账号的任务统计格式化为单行文本。

        数据全部取自 _multi_fetch_and_summarize_tasks() 已写入的 acc.summary，
        不引入新的统计口径。四个要素缺一不可，便于用户一眼判断
        "为什么没跑起来"（可执行 0 / 未开始若干 / 已过期若干）。
        """
        summary = getattr(acc, "summary", None) or {}
        return (
            f"可执行 {summary.get('executable', 0)} 个 / "
            f"未开始 {summary.get('not_started', 0)} 个 / "
            f"已过期 {summary.get('expired', 0)} 个 / "
            f"共 {summary.get('total', 0)} 个"
        )

    def _log_multi_task_summary(
        self,
        acc: _main().AccountSession,
        prefix: str = "任务统计",
        level: int = logging.INFO,
    ) -> str:
        """
        在多账号日志中输出任务统计（Q2/Q4 的统一出口）。

        参数:
            acc: 账号会话
            prefix: 日志前缀，例如 "任务统计" / "任务执行流程结束"
            level: 同时写入系统日志的级别
        """
        text = self._format_multi_task_summary(acc)
        message = f"{prefix}: {text}"
        try:
            acc.log_and_notify_frontend(message)
        except Exception:  # nosec B110 - 日志失败不能影响主流程
            pass
        logging.log(level, f"[{getattr(acc, 'username', '?')}] {message}")
        return message

    def _count_multi_remaining_tasks(
        self,
        acc: _main().AccountSession,
        attempted_keys: set,
        run_only_incomplete: bool = True,
    ) -> int:
        """
        统计"当前仍待执行、且本次尚未尝试过"的任务数量。

        用于退出前显式记录剩余待执行数量（Q4）：只统计服务端仍标记为未完成、
        时间状态为 active、且本次运行未尝试过的任务。已被本次尝试过的任务
        即使服务端仍为未完成，也不计入（避免把刚失败的任务算成"剩余"）。
        """
        now = datetime.datetime.now()
        ignore_time = acc.params.get("ignore_task_time", True)
        remaining = 0
        for run in getattr(acc, "all_run_data", []) or []:
            if run_only_incomplete and getattr(run, "status", 0) != 0:
                continue
            if self._get_task_time_state(run, ignore_time, now) != "active":
                continue
            if self._multi_task_key(run) in attempted_keys:
                continue
            remaining += 1
        return remaining

    @staticmethod
    def _multi_task_key(run) -> str:
        """
        多账号任务去重键。

        必须与 _multi_fetch_and_summarize_tasks() 的去重键保持一致
        （errandId|errandSchedule|startTime|endTime），否则同一任务会被
        重复执行或错误跳过。
        """
        return "|".join(
            str(getattr(run, field, "") or "")
            for field in ("errand_id", "errand_schedule", "start_time", "end_time")
        )

    def _select_next_multi_task(
        self,
        acc: _main().AccountSession,
        attempted_keys: set,
        run_only_incomplete: bool,
    ):
        """
        从当前 acc.all_run_data 中挑出下一个应当执行的任务。

        每完成一个任务都会重新拉取任务列表，因此本函数每轮都会基于最新的
        服务端数据决策，而不是启动时固化的快照（Q3）。

        返回值:
            RunData 或 None（None 表示本轮已无任务可执行）
        """
        now = datetime.datetime.now()
        ignore_time = acc.params.get("ignore_task_time", True)
        for run in getattr(acc, "all_run_data", []) or []:
            if self._get_task_time_state(run, ignore_time, now) != "active":
                continue
            if run_only_incomplete and getattr(run, "status", 0) != 0:
                continue
            if self._multi_task_key(run) in attempted_keys:
                continue
            return run
        return None

    def _run_single_multi_account_task(
        self,
        acc: _main().AccountSession,
        run_data,
        task_index: int,
        task_name_short: str,
        attempted_count: int = 1,
        planned_total: int | None = None,
    ) -> str:
        """
        执行单个多账号任务的完整流程（详情 → 规划 → 提交 → 确认）。

        从 _multi_account_worker 的主循环中抽出，使"每完成一个任务就重新
        拉取任务列表"的调度逻辑可以被独立测试。

        参数:
            task_index: 当前任务是本次运行的第几个（从 1 开始）
            attempted_count: 本次运行累计已尝试的任务数量。抽出方法后它不再
                能直接读取调用方的 attempted_task_keys 集合，必须显式传入，
                否则进度文案会抛 NameError（曾因此导致 worker 整体崩溃）。
            planned_total: 本次运行预计要执行的任务数，仅用于 "运行 i/n" 文案的
                分母；缺省或小于当前序号时退化为已尝试数量。

        返回值:
            "success"  —— 服务器已确认完成
            "failed"   —— 该任务无法完成（详情失败/无打卡点/规划失败/未确认）
            "aborted"  —— 运行被停止信号中断
        """
        # 兜底：调用方漏传或传入非法值时，至少退化为"当前序号/当前序号"
        attempted_count = max(
            int(task_index),
            int(attempted_count or 0),
        )
        # 必须先声明结果标记：下面的成功分支只在"提交成功"时才赋值，
        # 提交失败/中止的路径会直接跳到函数末尾的 return，
        # 漏掉这行就会抛
        # UnboundLocalError: cannot access local variable 'task_succeeded'
        # 使 worker 整体崩溃，且任务已提交的成果也一起丢掉。
        task_succeeded = False
        try:
            total_tasks = max(task_index, int(planned_total or 0))
        except Exception:
            total_tasks = task_index
        if total_tasks <= 0:
            total_tasks = task_index
        details_resp = acc.api_client.get_run_details(
            run_data.errand_id, acc.user_data.id, run_data.errand_schedule
        )
        if not (details_resp and details_resp.get("success")):
            acc.log_and_notify_frontend(f"获取任务详情失败，跳过。")
            return "failed"   # 详情失败/无打卡点/规划失败等，交回主循环

        details = details_resp.get("data", {}).get("errandDetail", {})
        waypoints = [
            (float(p["lon"]), float(p["lat"]))
            for p in details.get("geoCoorList", [])
            if p.get("lon") is not None
        ]
        if not waypoints:
            task_name = details.get("title", run_data.run_name)
            acc.log_and_notify_frontend(f"跳过: 任务 '{task_name}' 无打卡点")
            return "failed"   # 详情失败/无打卡点/规划失败等，交回主循环
        run_data.target_points = waypoints

        api_path_coords = None

        if not _main().chrome_pool:
            self._notify_route_planning_failure({"error": "Chrome浏览器池不可用，无法进行路径规划"}, account=acc)
            return "failed"   # 详情失败/无打卡点/规划失败等，交回主循环

        try:
            acc.log_and_notify_frontend("正在按当前地图供应商进行路径规划...")

            session_id = getattr(self, "_web_session_id", None)
            if not session_id:
                self._notify_route_planning_failure({"error": "无法获取浏览器会话ID"}, account=acc)
                return "failed"   # 详情失败/无打卡点/规划失败等，交回主循环

            path_coords = _main()._plan_route_path_with_provider_runtime(
                session_id,
                waypoints,
                python_params=acc.params,
                guard_label="MultiAccountPathPlanning",
                app_base_url=getattr(self, "_web_app_base_url", None),
            )
            if path_coords and path_coords.get("path"):
                api_path_coords = path_coords["path"]
                for notice in path_coords.get("notices", []):
                    acc.log_and_notify_frontend(sanitize_diagnostic(notice))
                acc.log_and_notify_frontend(f"路径规划成功。")
            else:
                self._notify_route_planning_failure(path_coords, account=acc)
                return "failed"   # 详情失败/无打卡点/规划失败等，交回主循环

        except Exception as e:
            self._notify_route_planning_failure({"error": sanitize_diagnostic(e)}, account=acc)
            return "failed"   # 详情失败/无打卡点/规划失败等，交回主循环

        if not api_path_coords:
            self._notify_route_planning_failure({"error": "路径规划未返回有效路径"}, account=acc)
            return "failed"   # 详情失败/无打卡点/规划失败等，交回主循环

        logging.debug(
            f"[{acc.username}] 路径规划返回点数: {len(api_path_coords)}"
        )

        min_t_m, max_t_m, min_d_m = (
            acc.params.get("min_time_m", 20),
            acc.params.get("max_time_m", 30),
            acc.params.get("min_dist_m", 2000),
        )

        final_path_dedup = []
        last_coord = None
        for p in api_path_coords:
            longitude = p.get("lng", p.get("lon"))
            if longitude is None:
                self._notify_route_planning_failure({**path_coords, "error": "路径坐标缺少经度"}, account=acc)
                return "failed"   # 详情失败/无打卡点/规划失败等，交回主循环
            coord = (longitude, p["lat"])
            if coord != last_coord:
                final_path_dedup.append(coord)
                last_coord = coord

        if not final_path_dedup:
            self._notify_route_planning_failure({**path_coords, "error": "路径处理失败：无有效坐标点"}, account=acc)
            return "failed"   # 详情失败/无打卡点/规划失败等，交回主循环

        logging.debug(
            f"[{acc.username}] 路径去重后点数: {len(final_path_dedup)}"
        )

        _plan_min_t_m = min_t_m * 1.02
        _plan_max_t_m = max_t_m * 0.98
        if _plan_max_t_m <= _plan_min_t_m:
            _plan_min_t_m, _plan_max_t_m = min_t_m, max_t_m
        target_time_s = random.uniform(_plan_min_t_m * 60, _plan_max_t_m * 60)  # nosec B311 - 用于跑步路径规划的随机参数，非安全用途
        target_dist_m = random.uniform(min_d_m, min_d_m * 1.15)  # nosec B311 - 用于跑步路径规划的随机参数，非安全用途

        final_geo_path = self._build_route_path_with_random_detours(
            final_path_dedup,
            run_data.target_points,
            target_dist_m,
            session_id=getattr(self, "_web_session_id", None),
            python_params=acc.params,
            app_base_url=getattr(self, "_web_app_base_url", None),
            guard_label="MultiAccountAutoGenerate",
            log_func=acc.log_and_notify_frontend,
        )
        final_cumulative = [0.0]
        for idx_c in range(len(final_geo_path) - 1):
            final_cumulative.append(
                final_cumulative[-1]
                + self._calculate_distance_m(
                    final_geo_path[idx_c][0],
                    final_geo_path[idx_c][1],
                    final_geo_path[idx_c + 1][0],
                    final_geo_path[idx_c + 1][1],
                )
            )

        actual_total_dist = final_cumulative[-1] if final_cumulative else 0.0
        if actual_total_dist == 0:
            self._notify_route_planning_failure({**path_coords, "error": "路径计算距离为0"}, account=acc)
            return "failed"   # 详情失败/无打卡点/规划失败等，交回主循环

        acc.log_and_notify_frontend(
            f"路径计算完成: 目标距离 {actual_total_dist:.1f}m, 目标耗时 {target_time_s:.1f}s"
        )

        avg_speed = actual_total_dist / target_time_s
        new_run_coords = []
        start = final_geo_path[0]
        new_run_coords.append(
            self._gps_random_offset(
                start[0], start[1], acc.params) + (0,)
        )
        t_elapsed, d_covered = 0.0, 0.0

        while t_elapsed < target_time_s:
            interval = min(
                random.uniform(
                    acc.params["interval_ms"] * 0.9,
                    acc.params["interval_ms"] * 1.1,
                )
                / 1000.0,
                target_time_s - t_elapsed,
            )
            if interval <= 0.1:
                break

            d_covered = min(
                d_covered
                + random.uniform(avg_speed * 0.9,
                                 avg_speed * 1.1) * interval,
                actual_total_dist,
            )
            lon, lat = self._get_point_at_distance(
                final_geo_path, final_cumulative, d_covered
            )
            lon_o, lat_o = self._gps_random_offset(
                lon, lat, acc.params)
            new_run_coords.append((lon_o, lat_o, int(interval * 1000)))
            t_elapsed += interval
            if d_covered >= actual_total_dist:
                break

        run_data.run_coords = new_run_coords
        run_data.total_run_distance_m = d_covered
        run_data.total_run_time_s = t_elapsed

        acc.log_and_notify_frontend(f"已生成模拟轨迹: {len(new_run_coords)} 个GPS点")

        run_data.trid = f"{acc.user_data.student_id}{int(time.time() * 1000)}"
        start_time_ms = str(int(time.time() * 1000))
        submission_successful = True
        total_points = max(1, len(run_data.run_coords))
        run_data.distance_covered_m = 0.0
        run_data.current_point_index = 0
        run_data.suppress_last_target_until_finish = True

        if total_points <= 1:
            acc.log_and_notify_frontend("警告: 生成的轨迹点数过少，无法执行任务。")
            return "failed"   # 详情失败/无打卡点/规划失败等，交回主循环

        _mr_exec_start_real = time.time()
        _mr_last_point_gps = run_data.run_coords[0]
        _mr_last_auto_save_time = time.time()
        _mr_exec_point_idx = 0
        _mr_target_time_s = float(getattr(run_data, "total_run_time_s", 0.0) or 0.0)
        if _mr_target_time_s <= 1.0:
            _mr_target_time_s = sum(max(0.0, d) / 1000.0 for _, _, d in run_data.run_coords)
        _mr_target_time_s = max(1.0, _mr_target_time_s)
        _mr_prefix_plan_s = [0.0]
        _mr_acc_plan_s = 0.0
        for _, _, _dur_ms in run_data.run_coords:
            _mr_acc_plan_s += max(0.0, _dur_ms) / 1000.0
            _mr_prefix_plan_s.append(_mr_acc_plan_s)
        _mr_pid_kp = _main().PID_KP
        _mr_pid_ki = _main().PID_KI
        _mr_pid_kd = _main().PID_KD
        _mr_pid_deadzone = _main().PID_DEADZONE
        _mr_pid_integral = 0.0
        _mr_pid_prev_error = 0.0
        _mr_pid_deadzone_boost = 1.0

        for chunk_idx in range(0, len(run_data.run_coords), 5):
            logging.debug(
                f"[{acc.username}] 执行进度: {chunk_idx}/{len(run_data.run_coords)}"
            )
            if self.multi_run_stop_flag.is_set() or acc.stop_event.is_set():
                submission_successful = False
                return "aborted"
                break

            chunk = run_data.run_coords[chunk_idx: chunk_idx + 5]
            processed_points = chunk_idx
            for lon, lat, dur_ms in chunk:
                if self.multi_run_stop_flag.is_set() or acc.stop_event.is_set():
                    submission_successful = False
                    return "aborted"
                    break

                session_id = getattr(self, "_web_session_id", None)

                acc.current_position = {"lon": lon, "lat": lat}

                if session_id and _main().socketio:
                    try:
                        _main().socketio.emit(
                            "multi_position_update",
                            {
                                "username": acc.username,
                                "lon": lon,
                                "lat": lat,
                                "name": acc.user_data.name,
                            },
                            room=session_id,
                        )
                        time.sleep(0.001)
                    except Exception as e:
                        logging.debug(
                            f"Failed to emit multi_position_update: {e}"
                        )

                _mr_elapsed_real_s = time.time() - _mr_exec_start_real
                _mr_elapsed_real_min = _mr_elapsed_real_s / 60.0
                _mr_actual_sleep_s = dur_ms / 1000.0
                if True:
                    _mr_planned_elapsed_s = min(
                        _mr_target_time_s,
                        _mr_prefix_plan_s[min(_mr_exec_point_idx, len(_mr_prefix_plan_s) - 1)],
                    )
                    _mr_expected_frac = _mr_planned_elapsed_s / _mr_target_time_s
                    _mr_actual_frac = _mr_elapsed_real_s / _mr_target_time_s
                    _mr_progress_diff = _mr_actual_frac - _mr_expected_frac
                    _mr_error = _mr_progress_diff
                    _mr_in_deadzone = abs(_mr_error) <= _mr_pid_deadzone
                    if _mr_in_deadzone:
                        _mr_pid_deadzone_boost = min(
                            _main().PID_DEADZONE_BOOST_MAX,
                            _mr_pid_deadzone_boost + _main().PID_DEADZONE_BOOST_STEP,
                        )
                    else:
                        _mr_pid_deadzone_boost = 1.0
                    _mr_error_for_pid = _mr_error
                    _mr_pid_integral = max(
                        -_main().PID_INTEGRAL_LIMIT,
                        min(_main().PID_INTEGRAL_LIMIT, _mr_pid_integral + _mr_error_for_pid),
                    )
                    _mr_pid_derivative = _mr_error_for_pid - _mr_pid_prev_error
                    _mr_pid_prev_error = _mr_error_for_pid
                    _mr_pid_p_term = _mr_pid_kp * _mr_error_for_pid
                    _mr_pid_i_term = _mr_pid_ki * _mr_pid_integral
                    _mr_pid_d_term = _mr_pid_kd * _mr_pid_derivative
                    _mr_pid_out = _mr_pid_deadzone_boost * (
                        _mr_pid_p_term
                        + _mr_pid_i_term
                        + _mr_pid_d_term
                    )
                    _mr_sleep_ratio = max(0.35, min(1.70, 1.0 - _mr_pid_out))
                    _mr_actual_sleep_s = _mr_actual_sleep_s * _mr_sleep_ratio
                    if _mr_error_for_pid > 0:
                        _mr_remaining_s = max(1.0, _mr_target_time_s - _mr_elapsed_real_s)
                        _mr_remaining_pts = max(1, total_points - _mr_exec_point_idx)
                        _mr_actual_sleep_s = min(_mr_actual_sleep_s, _mr_remaining_s / _mr_remaining_pts)
                        logging.debug(
                            f"[{acc.username}] 进度偏慢，PID自动加速: "
                            f"实际时间进度={_mr_actual_frac:.2%}, 规划时间进度={_mr_expected_frac:.2%}, "
                            f"时间误差={_mr_progress_diff:.2%}, 实际累计={_mr_elapsed_real_s:.1f}s, "
                            f"规划累计={_mr_planned_elapsed_s:.1f}s, "
                            f"P={_mr_pid_p_term:.4f}, I={_mr_pid_i_term:.4f}, D={_mr_pid_d_term:.4f}, "
                            f"PID={_mr_pid_out:.4f}, Boost={_mr_pid_deadzone_boost:.2f}, "
                            f"新等待时间={_mr_actual_sleep_s:.2f}s"
                        )
                    elif _mr_error < 0:
                        logging.debug(
                            f"[{acc.username}] 进度偏快，PID自动减速: "
                            f"实际时间进度={_mr_actual_frac:.2%}, 规划时间进度={_mr_expected_frac:.2%}, "
                            f"时间误差={_mr_progress_diff:.2%}, 实际累计={_mr_elapsed_real_s:.1f}s, "
                            f"规划累计={_mr_planned_elapsed_s:.1f}s, "
                            f"P={_mr_pid_p_term:.4f}, I={_mr_pid_i_term:.4f}, D={_mr_pid_d_term:.4f}, "
                            f"PID={_mr_pid_out:.4f}, Boost={_mr_pid_deadzone_boost:.2f}, "
                            f"新等待时间={_mr_actual_sleep_s:.2f}s"
                        )
                    else:
                        logging.debug(
                            f"[{acc.username}] 进度正常(±{_mr_pid_deadzone:.0%}): "
                            f"实际时间进度={_mr_actual_frac:.2%}, 规划时间进度={_mr_expected_frac:.2%}, "
                            f"时间误差={_mr_progress_diff:.2%}，实际累计={_mr_elapsed_real_s:.1f}s, "
                            f"规划累计={_mr_planned_elapsed_s:.1f}s, "
                            f"P={_mr_pid_p_term:.4f}, I={_mr_pid_i_term:.4f}, D={_mr_pid_d_term:.4f}, "
                            f"PID={_mr_pid_out:.4f}, Boost={_mr_pid_deadzone_boost:.2f}, "
                            f"等待时间={_mr_actual_sleep_s:.2f}s"
                        )
                else:
                    logging.debug(
                            f"[{acc.username}] 已执行时间={_mr_elapsed_real_min:.2f}分钟，未接近目标时间，无需调整执行速度。")

                if acc.stop_event.wait(timeout=_mr_actual_sleep_s):
                    submission_successful = False
                    return "aborted"
                    break

                run_data.distance_covered_m += self._calculate_distance_m(
                    _mr_last_point_gps[0],
                    _mr_last_point_gps[1],
                    lon,
                    lat,
                )
                _mr_last_point_gps = (lon, lat, dur_ms)
                _mr_exec_point_idx += 1
                run_data.current_point_index = _mr_exec_point_idx

                processed_points += 1
                try:
                    pct = int(processed_points * 100 / total_points)
                    self._update_account_status_js(
                        acc,
                        progress_pct=pct,
                        progress_text=f"运行 {task_index}/{total_tasks}: {task_name_short} · {pct}%",
                        progress_extra=f"{processed_points}/{total_points} 点",
                    )
                except Exception:
                    pass

                if session_id and (
                    time.time() - _mr_last_auto_save_time >= 30
                ):
                    try:
                        if (
                            hasattr(_main(), "web_sessions_lock")
                            and hasattr(_main(), "web_sessions")
                        ):
                            with _main().web_sessions_lock:
                                if session_id in _main().web_sessions:
                                    _main().save_session_state(
                                        session_id,
                                        _main().web_sessions[session_id],
                                    )
                                    _mr_last_auto_save_time = time.time()
                    except Exception as e:
                        logging.error(
                            f"[{acc.username}] 任务执行中自动保存会话失败: {e}"
                        )

            if not submission_successful:
                break

            is_final_chunk = chunk_idx + 5 >= len(run_data.run_coords)
            if not self._submit_chunk_with_retries(
                run_data,
                chunk,
                start_time_ms,
                is_final_chunk,
                chunk_idx,
                acc.api_client,
                acc.user_data,
                stop_event=acc.stop_event,
                log_func=acc.log_and_notify_frontend,
                stop_predicate=self.multi_run_stop_flag.is_set,
            ):
                submission_successful = False
                break

        if submission_successful:
            run_data.suppress_last_target_until_finish = False
            if run_data.target_points and run_data.target_sequence < len(run_data.target_points):
                try:
                    end_lon, end_lat, _ = run_data.run_coords[-1]
                    self.check_target_reached_during_run(run_data, end_lon, end_lat)
                except Exception:  # nosec B110 - 目标检查失败不影响主流程
                    pass
            acc.log_and_notify_frontend(f"任务 {run_data.run_name} 数据提交完毕，等待服务器确认...")
            time.sleep(3)
            if self._finalize_run(
                run_data,
                -1,
                acc.api_client,
                school_username=acc.user_data.username,
                auth_username=getattr(self, "auth_username", None),
            ):
                task_succeeded = True
                # 完成计数在 _finalize_run 内已处理；此处仅刷新展示用的统计
                self._multi_fetch_and_summarize_tasks(acc)
                self._update_account_status_js(acc, summary=acc.summary)
                acc.log_and_notify_frontend(f"任务 {run_data.run_name} 执行流程完成。")
                self._update_account_status_js(
                    acc,
                    status_text="任务已完成",
                    progress_pct=100,
                    progress_text=f"运行 {task_index}/{total_tasks}: {task_name_short} · 100%",
                    progress_extra="",
                )
            else:
                task_succeeded = False
                acc.log_and_notify_frontend(f"任务 {run_data.run_name} 未被服务器确认完成。")
                self._update_account_status_js(
                    acc,
                    status_text="任务未确认完成",
                )
            session_id = getattr(self, "_web_session_id", None)
            if session_id:
                try:
                    _main().save_session_state(
                        session_id,
                        self,
                        force_save=True,
                    )
                except Exception as e:
                    logging.error(
                        f"[{acc.username}] 任务结束后保存会话失败: {e}"
                    )
        if not (self.multi_run_stop_flag.is_set() or acc.stop_event.is_set()):
            acc.log_and_notify_frontend(f"任务 {run_data.run_name} 执行失败。")
            self._update_account_status_js(acc, status_text="任务失败")

        return "success" if task_succeeded else "failed"


    def _multi_fetch_attendance_stats(self, acc: _main().AccountSession):
        """(多账号) 获取单个账号的签到统计 - 循环获取所有通知"""
        if not acc.user_data.id:
            return

        att_pending = 0
        att_completed = 0
        att_expired = 0

        offset = 0
        limit = 200

        try:
            while True:
                list_resp = acc.api_client.get_notice_list(
                    offset=offset, limit=limit, type_id=0
                )

                if not (list_resp and list_resp.get("success")):
                    acc.log_and_notify_frontend(f"获取通知列表失败 (Offset: {offset})")
                    break

                notices = list_resp.get("data", {}).get("noticeList", [])
                if not notices:
                    break

                for notice in notices:
                    is_attendance = notice.get(
                        "image"
                    ) == "attendance" or "签到" in notice.get("title", "")

                    if is_attendance and notice.get("id"):
                        roll_call_id = notice["id"]
                        info_resp = acc.api_client.get_roll_call_info(
                            roll_call_id, acc.user_data.id
                        )

                        status = -2
                        finished = 0
                        if info_resp and info_resp.get("success"):
                            data = info_resp.get("data", {})
                            roll_call_info = data.get("rollCallInfo", {})
                            status = roll_call_info.get("status")
                            finished = data.get("attendFinish")

                        _s = int(status) if isinstance(status, str) and status.lstrip('-').isdigit() else status
                        _f = int(finished) if isinstance(finished, str) and finished.isdigit() else finished
                        if _s == -1 and (_f == 1 or _f is True):
                            att_expired += 1
                        elif (_s != -1) and (_f == 1 or _f is True):
                            att_completed += 1
                        else:
                            att_pending += 1

                offset += len(notices)

                if len(notices) < limit:
                    break

                time.sleep(0.1)

            acc.summary.update(
                {
                    "att_pending": att_pending,
                    "att_completed": att_completed,
                    "att_expired": att_expired,
                }
            )
            logging.debug(
                f"[{acc.username}] 签到统计(循环获取): 待签{att_pending}, 完成{att_completed}, 过期{att_expired}"
            )

        except Exception as e:
            acc.log_and_notify_frontend(f"刷新签到统计时出错: {e}")
            logging.error(
                f"[{acc.username}] Failed to fetch attendance stats: {e}", exc_info=True
            )

    def multi_path_generation_callback(self, username: str, success: bool, data: any):
        """接收来自JS的路径规划结果并唤醒对应线程"""
        if username in self.path_gen_callbacks:
            path_result, completion_event = self.path_gen_callbacks.pop(
                username)
            if success:
                path_result["path"] = data
            else:
                path_result["error"] = data
            completion_event.set()

    @staticmethod
    def _shorten_task_name_for_status(run_name, limit: int = 24) -> str:
        """把任务名压缩到状态栏可读长度（超长截断加省略号）。

        状态文案（等待中/正在执行）统一复用，避免各处各写一份截断逻辑
        导致同一任务在等待态与执行态显示不同名字。
        """
        name = str(run_name or "").strip()
        if len(name) <= limit:
            return name
        return f"{name[:limit]}..."

    def _multi_account_worker(
        self, acc: _main().AccountSession, delay: float, run_only_incomplete: bool
    ):
        acc.api_client._execution_cancel_event = acc.stop_event
        try:
            if self.multi_run_stop_flag.is_set() or acc.stop_event.is_set():
                self._update_account_status_js(acc, status_text="已取消")
                return

            current_time = time.time()
            time_since_last_refresh = current_time - acc.last_refresh_time
            skip_refresh = (
                time_since_last_refresh < 20
                and acc.user_data.id
                and len(acc.all_run_data) > 0
            )

            if skip_refresh:
                acc.log_and_notify_frontend(
                    f"距离上次刷新仅 {time_since_last_refresh:.1f} 秒，跳过重复刷新，直接使用已有数据。"
                )
            else:
                self._update_account_status_js(acc, status_text="登录中...")
                if not acc.device_ua:
                    acc.device_ua = _main().ApiClient.generate_random_ua()

                if self.multi_run_stop_flag.is_set() or acc.stop_event.is_set():
                    self._update_account_status_js(acc, status_text="已中止")
                    self._update_multi_global_buttons()
                    return

                login_resp = self._queued_login(acc)

                if self.multi_run_stop_flag.is_set() or acc.stop_event.is_set():
                    self._update_account_status_js(acc, status_text="已中止")
                    self._update_multi_global_buttons()
                    return

                if not login_resp or not login_resp.get("success"):
                    msg = (
                        login_resp.get("message", "未知错误")
                        if login_resp
                        else "网络错误"
                    )
                    self._update_account_status_js(
                        acc, status_text=f"登录失败: {msg}")
                    return

                data = login_resp.get("data", {})
                # 设置登录名兜底，随后由学校响应覆盖为学号等完整资料。
                acc.user_data.username = (
                    getattr(acc.user_data, "username", "") or acc.username
                )
                self._apply_login_profile_to_user_data(acc.user_data, data)

                execution_token = getattr(
                    acc, "_school_account_execution_token", None
                )
                identity_claimed, conflict_identity = (
                    _main()._extend_school_account_execution(
                        [
                            acc.user_data.username,
                            acc.user_data.student_id,
                        ],
                        execution_token,
                    )
                )
                if not identity_claimed:
                    acc.log_and_notify_frontend(
                        f"学校账号 {conflict_identity or acc.user_data.username} "
                        "已在单账号或其他多账号任务中执行，本次启动已中止。"
                    )
                    self._update_account_status_js(
                        acc,
                        status_text="账号冲突: 已在其它模式运行",
                    )
                    acc.stop_event.set()
                    return

                acc.log_and_notify_frontend("登录成功。")

                self._persist_school_account_backup(
                    acc.user_data.username,
                    data.get("userInfo", {}),
                    data.get("deptInfo", {}),
                    source="多账号执行登录",
                )

                self._update_account_status_js(
                    acc, status_text="分析任务", name=acc.user_data.name
                )

                if self.multi_run_stop_flag.is_set() or acc.stop_event.is_set():
                    self._update_account_status_js(acc, status_text="已中止")
                    return

                self._multi_fetch_and_summarize_tasks(acc)
                self._update_account_status_js(acc, summary=acc.summary)

                acc.last_refresh_time = time.time()

            # ========== 任务调度：每完成一个任务就重新拉取任务列表（Q3）==========
            # 旧实现把启动时筛选出的 tasks_to_run 固化成列表后一次性遍历，
            # 运行期间新发布到服务端的待执行任务不会被追加，导致"有 2 个待执行
            # 只跑了 1 个"的现象。现在改为每轮都重新拉取并重新挑任务。
            task_outcomes = {}
            attempted_task_keys: set[str] = set()
            successful_tasks = 0
            failed_tasks = 0
            aborted = False
            task_fetch_failed = False
            # 第一个任务前不等待；只有"已确认还有下一个可执行任务"时才进入任务间隔等待
            has_completed_any = False
            # 本次运行的"计划任务数"：取自最新任务统计里的可执行数量，随时可能因为
            # 运行期间新发布任务而变大（不会变小），只作为 "正在执行 i/n" 的分母。
            # 运行前无法知道确切总数，这里给的是用户列表里看到的"可执行 N 个"口径。
            planned_total = 0

            while True:
                # ---- 中止检查 ----
                if self.multi_run_stop_flag.is_set() or acc.stop_event.is_set():
                    aborted = True
                    self._update_account_status_js(acc, status_text="已中止")
                    self._update_multi_global_buttons()
                    break

                # ---- 安全上限：防止服务端持续返回同一批未完成任务导致死循环 ----
                if len(attempted_task_keys) >= _main().MULTI_WORKER_MAX_TASKS:
                    acc.log_and_notify_frontend(
                        f"已达到单次运行的任务上限 "
                        f"{_main().MULTI_WORKER_MAX_TASKS} 个，停止继续挑任务。"
                    )
                    break

                # ---- 第一步：重新拉取任务列表 ----
                # 每次都基于最新服务端状态决策，因此任务体内部的
                # _multi_fetch_and_summarize_tasks() 之后无需再次拉取。
                tasks_refreshed = self._multi_fetch_and_summarize_tasks(acc)
                if tasks_refreshed is False:
                    task_fetch_failed = True
                    acc.log_and_notify_frontend("获取任务列表失败，本次执行停止并保留上次成功状态。")
                    self._update_account_status_js(
                        acc, status_text="刷新失败: 获取任务列表失败"
                    )
                    break

                ignore_time = acc.params.get("ignore_task_time", True)
                acc.log_and_notify_frontend(
                    f"分析任务参数: ignore_task_time={ignore_time}, "
                    f"run_only_incomplete={run_only_incomplete}"
                )
                # 任务时间状态统一由 _get_task_time_state() 评估，多账号 worker
                # 与任务汇总必须共用同一判定，不得各自解析时间字符串。
                active_task_count = sum(
                    1
                    for r in (getattr(acc, "all_run_data", None) or [])
                    if self._get_task_time_state(r, ignore_time, datetime.datetime.now())
                    == "active"
                )
                logging.debug(
                    f"[{acc.username}] 本轮候选任务（时间状态 active）: {active_task_count}"
                )
                self._log_multi_task_summary(acc, prefix="任务统计")

                # 计划任务数只增不减：可执行数量会因运行期间新发布任务而变大，
                # 同时保证分母不小于已尝试序号（否则会出现 "2/1" 这种文案）。
                try:
                    planned_total = max(
                        planned_total,
                        int((getattr(acc, "summary", None) or {}).get("executable") or 0),
                        len(attempted_task_keys),
                    )
                except Exception:  # nosec B110 - 统计失败不影响执行
                    planned_total = max(planned_total, len(attempted_task_keys))

                # ---- 第二步：从最新列表中挑出下一个可执行任务 ----
                run_data = self._select_next_multi_task(
                    acc,
                    attempted_task_keys,
                    run_only_incomplete,
                )

                if run_data is None:
                    # 没有下一个可执行任务：直接结束，**不进入任务间隔等待**
                    if not attempted_task_keys:
                        acc.has_pending_tasks = False
                        self._update_account_status_js(
                            acc,
                            status_text=_main()._build_multi_account_completion_status(
                                0, 0
                            ),
                        )
                    break

                # ---- 第三步：确认有新任务后才进入任务间隔等待 ----
                # 必须先确定"确实还有下一个任务"再等待；
                # 若先等待后拉取，最后一个任务跑完还要白等一轮才退出。
                acc.has_pending_tasks = True

                # 状态文案要让人一眼看出"在等什么、等的是第几个任务"：
                # 旧文案只有裸的 `延迟 12s` / `等待 300s`，两种等待无法区分，
                # 也看不出后面还有没有任务。这里统一成
                # `开始前等待 Ns: 待执行 i/n 个任务` 与
                # `任务间等待 Ns: 下一个 i/n · 任务名`。
                next_task_index = len(attempted_task_keys) + 1
                next_task_name = self._shorten_task_name_for_status(
                    run_data.run_name
                )
                effective_total_for_wait = max(next_task_index, planned_total)

                # 账号级启动延迟：仅在"确实已经挑到任务"时才延迟，避免无任务时白等。
                if delay > 0 and not has_completed_any:
                    delay_end_time = time.time() + delay
                    while time.time() < delay_end_time:
                        if acc.stop_event.is_set() or self.multi_run_stop_flag.is_set():
                            aborted = True
                            self._update_account_status_js(acc, status_text="已中止")
                            self._update_multi_global_buttons()
                            break
                        delay_remaining = delay_end_time - time.time()
                        self._update_account_status_js(
                            acc,
                            status_text=(
                                f"开始前等待 {delay_remaining:.0f}s: "
                                f"待执行 {next_task_index}/"
                                f"{effective_total_for_wait} 个任务"
                            ),
                        )
                        time.sleep(1)
                    if aborted:
                        break
                    # 延迟只对本次运行的第一个任务生效
                    delay = 0

                # 任务间隔：只有"已经跑过至少一个任务"且"已确认还有下一个"才等待
                if has_completed_any:
                    wait_time = random.uniform(
                        acc.params["task_gap_min_s"], acc.params["task_gap_max_s"]
                    )
                    acc.log_and_notify_frontend(
                        f"已确认存在下一个可执行任务，进入任务间隔等待 {wait_time:.0f}s。"
                    )
                    should_break_worker = False
                    end_time = time.time() + wait_time
                    while time.time() < end_time:
                        if acc.stop_event.is_set() or self.multi_run_stop_flag.is_set():
                            should_break_worker = True
                            break
                        remaining = end_time - time.time()
                        self._update_account_status_js(
                            acc,
                            status_text=(
                                f"任务间等待 {remaining:.0f}s: "
                                f"下一个 {next_task_index}/"
                                f"{effective_total_for_wait} · {next_task_name}"
                            ),
                        )
                        time.sleep(1)
                    if should_break_worker:
                        aborted = True
                        self._update_account_status_js(acc, status_text="已中止")
                        break

                # ---- 第四步：执行该任务 ----
                # 用已尝试集合的长度作为展示序号，与旧实现的 i+1 语义保持一致
                attempted_task_keys.add(self._multi_task_key(run_data))
                task_index = len(attempted_task_keys)

                task_name_short = (
                    run_data.run_name[:10] + "..."
                    if len(run_data.run_name) > 10
                    else run_data.run_name
                )

                # 任务真正开始执行：把状态从"延迟/等待/排队"切换到正在执行的任务。
                # 否则状态栏会一直停留在启动延迟时的旧文案（例如"延迟 0s"），
                # 管理员查看他人会话时看到的也是同一个状态字段。
                task_name_for_status = next_task_name
                # 分母不能小于当前序号（计划数是在挑任务之前统计的）。
                effective_total = max(task_index, planned_total)
                if effective_total > 1:
                    running_status_text = (
                        f"正在执行 {task_index}/{effective_total}: "
                        f"{task_name_for_status}"
                    )
                else:
                    running_status_text = f"正在执行: {task_name_for_status}"
                running_progress_text = (
                    f"运行 {task_index}/{effective_total}: {task_name_short}"
                )
                self._update_account_status_js(
                    acc,
                    status_text=running_status_text,
                    progress_pct=0,
                    progress_text=running_progress_text,
                    progress_extra="",
                )

                outcome = self._run_single_multi_account_task(
                    acc,
                    run_data,
                    task_index,
                    task_name_short,
                    attempted_count=task_index,
                    planned_total=effective_total,
                )
                task_outcomes[id(run_data)] = outcome
                if outcome == "aborted":
                    aborted = True
                    self._update_account_status_js(acc, status_text="已中止")
                    break

                has_completed_any = True


                if not acc.stop_event.is_set() and not task_fetch_failed:
                    successful_tasks = sum(
                        1 for outcome in task_outcomes.values() if outcome == "success"
                    )
                    failed_tasks = sum(
                        1 for outcome in task_outcomes.values() if outcome == "failed"
                    )
                    aborted = aborted or self.multi_run_stop_flag.is_set()
                    # 退出前显式记录剩余待执行数量（Q4）。
                    # 先按最新服务端状态刷新一次，再统计"未完成 + active + 本次未尝试"的任务。
                    try:
                        self._multi_fetch_and_summarize_tasks(acc)
                        remaining_count = self._count_multi_remaining_tasks(
                            acc, attempted_task_keys, run_only_incomplete
                        )
                        remaining_text = f"剩余待执行 {remaining_count}"
                    except Exception as remaining_error:
                        logging.error(
                            f"[{acc.username}] 统计剩余待执行任务失败: {remaining_error}",
                            exc_info=True,
                        )
                        remaining_text = "剩余待执行 未知"

                    summary_message = (
                        f"任务执行流程结束：成功 {successful_tasks} / "
                        f"失败 {failed_tasks} / {remaining_text}"
                        + ("（已中止）" if aborted else "")
                    )
                    acc.log_and_notify_frontend(summary_message)
                    logging.info(f"[{acc.username}] {summary_message}")
                    self._log_multi_task_summary(
                        acc, prefix="结束时的任务统计", level=logging.INFO
                    )

                    final_status = _main()._build_multi_account_completion_status(
                        len(task_outcomes),
                        successful_tasks,
                    )
                    self._update_account_status_js(
                        acc,
                        status_text=final_status,
                        progress_pct=100,
                        progress_text=final_status,
                        progress_extra="",
                    )
                else:
                    # 被中止时同样记录剩余量，便于判断"是没任务还是被中断"
                    try:
                        self._multi_fetch_and_summarize_tasks(acc)
                        remaining_count = self._count_multi_remaining_tasks(
                            acc, attempted_task_keys, run_only_incomplete
                        )
                    except Exception:  # nosec B110 - 中止路径的统计失败不影响退出
                        remaining_count = "未知"
                    logging.info(
                        f"[{acc.username}] 任务执行流程中止：成功 "
                        f"{sum(1 for o in task_outcomes.values() if o == 'success')} / "
                        f"剩余待执行 {remaining_count}"
                    )

        except Exception:
            logging.error(
                f"Error in worker for {acc.username}: {traceback.format_exc()}"
            )
            self._update_account_status_js(acc, status_text="执行出错")
        finally:
            try:
                acc.worker_thread = None
                acc.current_position = None
                if acc.stop_event.is_set():
                    self._update_account_status_js(acc, status_text="已停止")
                else:
                    if not self._should_preserve_status(
                        acc.status_text, new_status="待命"
                    ):
                        if (
                            acc.status_text
                            in (
                                "登录中...",
                                "排队登录...",
                                "已启动",
                                "分析任务",
                                "运行",
                                "等待",
                            )
                            or not acc.status_text
                        ):
                            self._update_account_status_js(
                                acc, status_text="待命")

            except Exception:
                logging.debug(
                    "Finalize worker status update failed (non-fatal).", exc_info=True
                )
            finally:
                acc.api_client._execution_cancel_event = None
                self._update_multi_global_buttons()

    def _run_all_multi_accounts_thread(self, *args, **kwargs):
        return self._start_multi_account_threads(*args, **kwargs)

    def _start_multi_account_threads(
        self, account_list, delays, use_delay, run_only_incomplete
    ):
        started_threads = 0
        for i, acc in enumerate(account_list):
            if self._is_multi_account_execution_active(acc):
                acc.log_and_notify_frontend("已在运行，本次'全部开始'将跳过此账号。")
                continue

            delay = delays[i] if use_delay else 0
            if self._start_multi_account_worker(
                acc,
                delay,
                run_only_incomplete,
            ):
                started_threads += 1
            else:
                acc.log_and_notify_frontend("正在执行其它操作，本次'全部开始'将跳过此账号。")

        return started_threads

    def _get_device_sign_code(self, username):
        """生成或获取设备标识码 (signCode)"""
        return str(uuid.uuid4())

    def _fetch_server_attendance_radius_if_needed(
        self, client: _main().ApiClient, acc: _main().AccountSession | None = None
    ):
        """
        (辅助函数) 检查并获取服务器签到半径。
        - 单账号模式: 缓存到 self.server_attendance_radius_m
        - 多账号模式: 缓存到 acc.server_attendance_radius_m
        """
        log_func = acc.log_and_notify_frontend if acc else self.log_and_notify_frontend
        cache_duration_s = 3600

        if acc:
            last_fetch_time = acc.last_radius_fetch_time
            current_radius = acc.server_attendance_radius_m
        else:
            last_fetch_time = self.last_radius_fetch_time
            current_radius = self.server_attendance_radius_m

        if time.time() - last_fetch_time < cache_duration_s and current_radius > 0:
            logging.debug(f"使用缓存的服务器签到半径值: {current_radius}米")
            return current_radius

        log_func("正在获取服务器签到半径...")
        new_radius = 0.0
        try:
            resp = client.get_attendance_radius()
            if resp and resp.get("success"):
                info_list = resp.get("data", {}).get("info", [])
                if info_list and isinstance(info_list, list) and len(info_list) > 0:
                    radius_str = info_list[0].get("code")
                    new_radius = float(radius_str)
                    if new_radius <= 0:
                        log_func("服务器返回半径为0，启用精确签到。")
                        new_radius = 0.0
                    else:
                        log_func(f"服务器签到半径更新为: {new_radius} 米")
                else:
                    log_func("服务器未返回半径信息，默认为精确签到。")
            else:
                log_func("获取半径API失败，默认为精确签到。")
        except Exception as e:
            log_func(f"获取半径时出错: {e}，默认为精确签到。")
            logging.error(
                f"Failed to fetch attendance radius: {e}", exc_info=True)

        if acc:
            acc.server_attendance_radius_m = new_radius
            acc.last_radius_fetch_time = time.time()
        else:
            self.server_attendance_radius_m = new_radius
            self.last_radius_fetch_time = time.time()

        return new_radius

    def trigger_attendance(
        self,
        roll_call_id: str,
        target_coords: tuple[float, float],
        location_choice: str = "random",
        specific_coords: tuple[float, float] | None = None,
        is_makeup: bool = False,
        acc: _main().AccountSession | None = None,
    ):
        """
        触发签到流程。
        - acc: (可选) 在多账号模式下传入 AccountSession。

        Args:
            roll_call_id: 签到活动的 ID.
            target_coords: 签到目标的坐标 (经度, 纬度).
            location_choice: 'random' (在目标点范围内随机) 或 'specific' (使用 specific_coords).
            specific_coords: 当 location_choice 为 'specific' 时使用的具体坐标 (经度, 纬度).
            is_makeup: 是否为补签。
            acc: (可选) 在多账号模式下传入 AccountSession。
        """

        if acc:
            client = acc.api_client
            log_func = acc.log_and_notify_frontend
            user = acc.user_data
            params = acc.params
        elif not self.is_multi_account_mode:
            client = self.api_client
            log_func = self.log_and_notify_frontend
            user = self.user_data
            params = self.params
        else:
            self.log_and_notify_frontend("trigger_attendance 在多账号模式下被错误调用（未传入acc）")
            return {"success": False, "message": "多账号模式内部错误"}

        if not user.id:
            log_func("用户未登录，无法签到。")
            return {"success": False, "message": "用户未登录"}

        log_func(f"正在处理签到: {roll_call_id}")

        server_radius_m = self._fetch_server_attendance_radius_if_needed(
            client, acc)
        is_precise_checkin = server_radius_m <= 0

        try:
            info_resp = client.get_roll_call_info(roll_call_id, user.id)
            if info_resp and info_resp.get("success"):
                data = info_resp.get("data", {})
                roll_call_info = data.get("rollCallInfo", {})

                status = roll_call_info.get("status")
                finished = data.get("attendFinish")
            _s = int(status) if isinstance(status, str) and status.lstrip('-').isdigit() else status
            _f = int(finished) if isinstance(finished, str) and finished.isdigit() else finished
            if _s == -1 and (_f == 1 or _f is True):
                # 已过期：status=-1 且 attendFinish=1
                if not is_makeup:
                    log_func("此签到任务已过期（status=-1, attendFinish=1）。")
                    return {"success": False, "message": "任务已过期"}
                else:
                    log_func(f"任务 {roll_call_id} 已过期，正在尝试[补签]...")
            elif (_s != -1) and (_f == 1 or _f is True):
                # 已完成签到
                log_func("你已经签到过了 (status!=−1 and attendFinish=1)。")
                return {"success": True, "message": "已签到"}
            elif _s == -1:
                # 待签到：status=-1 且 attendFinish 未设置/为0
                log_func("任务状态：待签到。")
            else:
                log_func("获取签到信息失败，将继续尝试签到...")
        except Exception as e:
            log_func(f"检查签到状态时出错: {e}，将继续尝试...")
            logging.error(
                f"Error checking roll call status: {e}", exc_info=True)

        final_lon, final_lat = 0.0, 0.0
        target_lon, target_lat = target_coords

        if location_choice == "specific" and specific_coords:
            final_lon, final_lat = specific_coords
            log_func(f"使用指定坐标签到: ({final_lon:.6f}, {final_lat:.6f})")

        elif location_choice == "random":
            radius_for_random = 0.0

            if not is_precise_checkin:
                user_radius_m = params.get("attendance_user_radius_m", 40)
                radius_for_random = max(
                    0.0, min(user_radius_m, server_radius_m))

            if radius_for_random <= 0:
                final_lon, final_lat = target_lon, target_lat
                log_func(
                    f"精确签到模式：使用目标点坐标签到: ({final_lon:.6f}, {final_lat:.6f})"
                )
            else:
                angle = random.uniform(0, 2 * math.pi)
                radius_ratio = random.uniform(0, 1.0)
                radius_m = radius_for_random * radius_ratio

                offset_lon = (radius_m * math.cos(angle)) / 102834.74
                offset_lat = (radius_m * math.sin(angle)) / 111712.69

                final_lon = target_lon + offset_lon
                final_lat = target_lat + offset_lat
                log_func(
                    f"在 {radius_for_random:.1f} 米范围内随机生成坐标签到: ({final_lon:.6f}, {final_lat:.6f})"
                )

        else:
            log_func("无效的位置选择，无法签到。")
            return {"success": False, "message": "无效的位置选择"}

        actual_distance = self._calculate_distance_m(
            final_lon, final_lat, target_lon, target_lat
        )
        log_func(f"签到点距离目标点 {actual_distance:.2f} 米。")

        sign_code = self._get_device_sign_code(user.username)
        if is_makeup:
            payload = {
                "rollCallId": roll_call_id,
                "userId": user.id,
                "coordinate": f"{final_lon},{final_lat}",
                "distance": int(actual_distance),
                "status": 2,
                "signCode": sign_code,
                "reason": "补签",
            }
            log_func("正在构建签到信息，检测到是补签任务")
        else:
            payload = {
                "rollCallId": roll_call_id,
                "userId": user.id,
                "coordinate": f"{final_lon},{final_lat}",
                "distance": int(actual_distance),
                "status": 1,
                "signCode": sign_code,
                "reason": "",
            }
            log_func("正在构建签到信息，检测到是正常签到任务")

        try:
            log_func("正在提交签到...")
            submit_resp = client.submit_attendance(payload)
            if submit_resp and submit_resp.get("success"):
                log_func("签到成功！")
                logging.info(
                    f"Attendance submitted successfully for {roll_call_id}")
                return {"success": True, "message": "签到成功"}
            else:
                msg = (
                    submit_resp.get("message", "未知错误")
                    if submit_resp
                    else "网络错误"
                )
                log_func(f"签到失败: {msg}")
                logging.warning(
                    f"Attendance submission failed for {roll_call_id}: {msg}"
                )
                return {"success": False, "message": f"签到失败: {msg}"}
        except Exception as e:
            log_func(f"提交签到时出错: {e}")
            logging.error(f"提交签到请求时发生错误，异常信息: {e}", exc_info=True)
            return {"success": False, "message": f"提交签到时出错: {e}"}

    # --- 获取通知功能 ---

    def get_notifications(
        self,
        is_auto_refresh: bool = False,
        request_limit: int = None,
        request_offset: int = 0,
    ):
        """
        (已重构) 获取未读通知数量和通知列表。
        - 附加基于新逻辑的签到状态。
        - (自动签到逻辑已移至 _check_and_trigger_auto_attendance)
        - 支持分段加载：可指定 request_limit 和 request_offset 参数

        Args:
            is_auto_refresh: 是否为自动刷新调用
            request_limit: 请求的最大通知数量（None表示获取全部）
            request_offset: 请求的起始偏移量（默认为0）

        Returns:
            包含 success、unreadCount、notices、hasMore、totalCount 的字典
        """
        logging.info(
            f"API调用: get_notifications - 获取用户通知消息列表 (limit={request_limit}, offset={request_offset})"
        )
        if not self.user_data.id or self.is_multi_account_mode:
            return {"success": False, "message": "仅单账号登录模式可用"}

        if self.is_offline_mode:
            return {"success": True, "data": {"unreadNumber": 0, "notices": []}}

        try:
            count_resp = self.api_client.get_unread_notice_count()
            unread_count = 0
            if count_resp and count_resp.get("success"):
                unread_count = count_resp.get(
                    "data", {}).get("unreadNumber", 0)

            all_notices = []
            offset = request_offset
            limit = 10
            total_fetched = 0

            if request_limit is not None:
                while total_fetched < request_limit:
                    batch_size = min(limit, request_limit - total_fetched)

                    list_resp = self.api_client.get_notice_list(
                        offset=offset, limit=batch_size, type_id=0
                    )
                    if list_resp and list_resp.get("success"):
                        current_notices = list_resp.get("data", {}).get(
                            "noticeList", []
                        )
                        if not current_notices:
                            break
                        all_notices.extend(current_notices)
                        total_fetched += len(current_notices)
                        offset += len(current_notices)
                        if len(current_notices) < batch_size:
                            break
                    else:
                        self.log_and_notify_frontend("获取通知列表时失败。")
                        break
            else:
                while True:
                    list_resp = self.api_client.get_notice_list(
                        offset=offset, limit=limit, type_id=0
                    )
                    if list_resp and list_resp.get("success"):
                        current_notices = list_resp.get("data", {}).get(
                            "noticeList", []
                        )
                        if not current_notices:
                            break
                        all_notices.extend(current_notices)
                        offset += limit
                        if len(current_notices) < limit:
                            break
                    else:
                        self.log_and_notify_frontend("获取通知列表时失败。")
                        break

            notices = all_notices

            if notices:
                logging.debug(f"正在为 {len(notices)} 条通知附加签到状态...")
                for notice in notices:
                    try:
                        is_attendance = notice.get(
                            "image"
                        ) == "attendance" or "签到" in notice.get("title", "")
                        if is_attendance and notice.get("id"):
                            roll_call_id = notice["id"]

                            info_resp = self.api_client.get_roll_call_info(
                                roll_call_id, self.user_data.id
                            )

                            status = -2
                            finished = 0

                            if info_resp and info_resp.get("success"):
                                data = info_resp.get("data", {})
                                roll_call_info = data.get("rollCallInfo", {})
                                status = roll_call_info.get("status")
                                finished = data.get("attendFinish")

                            notice["attendance_finished"] = finished
                            notice["attendance_status_code"] = status

                            _s = int(status) if isinstance(status, str) and status.lstrip('-').isdigit() else status
                            _f = int(finished) if isinstance(finished, str) and finished.isdigit() else finished
                            if _s == -1 and (_f == 1 or _f is True):
                                # 已过期：status=-1 且 attendFinish=1
                                notice["attendance_code"] = -1
                            elif (_s != -1) and (_f == 1 or _f is True):
                                # 已完成签到
                                notice["attendance_code"] = 1
                            else:
                                # 待签到（status=-1 且 attendFinish 未设置）或其他待处理状态
                                notice["attendance_code"] = 0

                    except Exception as e:
                        logging.warning(
                            f"附加签到状态失败 (ID: {notice.get('id')}): {e}"
                        )
            has_more = False
            if request_limit is not None and len(notices) >= request_limit:
                peek_resp = self.api_client.get_notice_list(
                    offset=offset, limit=1, type_id=0
                )
                if peek_resp and peek_resp.get("success"):
                    peek_notices = peek_resp.get(
                        "data", {}).get("noticeList", [])
                    has_more = len(peek_notices) > 0

            if not is_auto_refresh:
                self.log_and_notify_frontend(
                    f"获取到 {unread_count} 条未读通知，本次返回 {len(notices)} 条通知。"
                )

            if request_offset == 0 and len(notices) >= 5:
                self.cached_notifications = {
                    "notices": notices[:5],
                    "unreadCount": unread_count,
                    "cached_at": time.time(),
                }
                logging.debug(
                    f"已更新缓存通知：{len(self.cached_notifications['notices'])} 条"
                )

            return {
                "success": True,
                "unreadCount": unread_count,
                "notices": notices,
                "hasMore": has_more,
                "totalCount": offset,
                "returnedCount": len(notices),
            }
        except Exception as e:
            self.log_and_notify_frontend(f"获取通知失败: {e}")
            logging.error(f"get_notifications failed: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    def get_cached_notifications(self):
        """获取缓存的通知（用于快速显示）"""
        logging.info("API调用: get_cached_notifications - 获取缓存的通知")

        if hasattr(self, "cached_notifications") and self.cached_notifications:
            cached_at = self.cached_notifications.get("cached_at", 0)
            age_seconds = time.time() - cached_at

            if age_seconds < 300:
                logging.debug(f"返回缓存的通知，缓存年龄: {age_seconds:.1f}秒")
                return {
                    "success": True,
                    "cached": True,
                    "unreadCount": self.cached_notifications.get("unreadCount", 0),
                    "notices": self.cached_notifications.get("notices", []),
                    "cached_at": cached_at,
                }
            else:
                logging.debug(f"缓存已过期（{age_seconds:.1f}秒），返回空")

        return {"success": True, "cached": False, "notices": []}

    def mark_notification_read(self, notice_id):
        """(单账号) 将指定ID的通知设为已读"""
        logging.info(
            f"API调用: mark_notification_read - 标记通知为已读，通知ID: {notice_id}"
        )
        if not self.user_data.id or self.is_multi_account_mode:
            return {"success": False, "message": "仅单账号登录模式可用"}

        resp = self.api_client.mark_notice_as_read(notice_id)
        if resp and resp.get("success"):
            return {"success": True}
        else:
            return {"success": False, "message": resp.get("message", "标记已读失败")}

    def _get_account_by_id(self, account_id: str):
        """
        根据账号ID获取账号对象

        此函数用于在单账号模式和多账号模式下统一获取账号对象。
        它会规范化账号ID（转为字符串），然后在相应的模式下查找账号。

        参数:
            account_id: 账号标识符，可以是数字或字符串，会被自动转换为字符串

        返回值:
            Api 或 AccountSession 对象，如果找不到则返回 None
        """
        # 规范化账号ID：统一转换为字符串格式
        # 这确保数字 1 和字符串 "1" 被视为同一个账号
        account_id = str(account_id)

        # 单账号模式：检查当前用户
        # 在单账号模式下，只有一个账号（self），检查其user_data.id是否匹配
        if not self.is_multi_account_mode:
            # 确保当前用户已登录（有 user_data 和 id）
            if self.user_data and self.user_data.id:
                # 比较账号ID（也转为字符串以确保类型一致）
                if str(self.user_data.id) == account_id:
                    # 返回 self，即 Api 对象本身
                    return self
            # 如果不匹配或未登录，返回 None
            return None

        # 多账号模式：从 accounts 字典查找
        # accounts 是一个字典，键是用户名（username），值是 AccountSession 对象
        for username, acc in self.accounts.items():
            # 检查该账号是否已登录（有 user_data 和 id）
            if acc.user_data and acc.user_data.id:
                # 比较账号ID（转为字符串）
                if str(acc.user_data.id) == account_id:
                    # 返回找到的 AccountSession 对象
                    return acc

        # 如果在多账号模式下也没找到匹配的账号，返回 None
        return None

    def _ensure_account_refresh_thread(self, account_id):
        """
        确保指定账号有刷新线程在运行

        此函数会检查指定账号是否已有活跃的刷新线程。
        如果没有或线程已停止，则创建新的线程。
        这是线程去重机制的核心函数。

        参数:
            account_id: 账号标识符（任意类型，会被转换为字符串）
        """
        # 规范化账号ID为字符串
        account_id = str(account_id)
        stop_event = self._get_session_stop_event()
        if stop_event.is_set():
            return

        # 使用线程锁保护对 account_refresh_threads 字典的访问
        # 这确保在多线程环境下不会发生竞态条件
        with self.threads_lock:
            # 检查字典中是否已有该账号的线程记录
            if account_id in self.account_refresh_threads:
                # 获取线程对象
                thread = self.account_refresh_threads[account_id]
                # 检查线程是否仍在运行
                if thread.is_alive():
                    # 线程仍活跃，无需创建新线程，直接返回
                    logging.debug(f"[线程管理] 账号 {account_id} 已有活跃线程，跳过创建")
                    return
                else:
                    # 线程已停止，记录日志，稍后会创建新线程
                    logging.info(f"[线程管理] 账号 {account_id} 的线程已停止，将创建新线程")

            # 创建新的后台刷新线程
            # target: 线程要执行的函数
            # args: 传递给目标函数的参数（账号ID）
            # daemon: 设为 True，使其成为守护线程（主程序退出时自动结束）
            # name: 线程名称，便于调试和日志追踪
            thread = threading.Thread(
                target=self._account_refresh_worker,
                args=(account_id, stop_event),
                daemon=True,
                name=f"AccountRefresh-{account_id}"
            )

            # 将新线程记录到字典中
            self.account_refresh_threads[account_id] = thread

            # 启动线程
            thread.start()

            # 记录日志，表明新线程已创建并启动
            logging.info(f"[线程管理] 已为账号 {account_id} 创建并启动刷新线程")

    def _account_refresh_worker(self, account_id: str, stop_event=None):
        """
        单个账号的后台刷新和签到线程（新版统一实现）

        这是每个账号独立运行的后台线程函数。
        它会定期执行以下操作：
        1. 检查账号是否启用了自动签到
        2. 如果启用，执行签到检查
        3. 刷新通知
        4. 等待指定时间后重复

        参数:
            account_id: 账号标识符（字符串格式）
        """
        # 规范化账号ID为字符串（确保类型一致）
        account_id = str(account_id)

        # 记录线程启动日志
        logging.info(f"[账号刷新线程] 启动 - 账号ID: {account_id}")

        # 连续未启用自动签到的轮次计数：达到阈值后线程主动退出，
        # 避免自动签到关闭后线程永久驻留空转
        disabled_rounds = 0

        stop_event = stop_event or self._get_session_stop_event()

        try:
            # 主循环：持续运行直到收到停止信号
            while not stop_event.is_set():
                try:
                    # === 第一步：获取账号对象 ===
                    # 使用辅助函数根据账号ID获取对应的账号对象
                    account = self._get_account_by_id(account_id)

                    # 如果账号不存在（可能已被删除），退出线程
                    if not account:
                        logging.warning(f"[账号刷新线程] 账号不存在: {account_id}，线程退出")
                        break

                    # === 第二步：检查是否启用自动签到 ===
                    # 从JSON配置文件中获取自动签到开关状态，不再从INI文件读取
                    # 首先需要获取学校账号用户名
                    school_username = None
                    if account.user_data and account.user_data.username:
                        school_username = account.user_data.username

                    # 如果无法获取学校账号用户名，无法检查配置，等待后重试
                    if not school_username:
                        logging.debug(
                            f"[账号刷新线程] 账号 {account_id} 无法获取学校用户名，等待..."
                        )
                        if stop_event.wait(timeout=30):
                            break
                        continue

                    # 从JSON配置文件读取该账号的自动签到启用状态
                    is_auto_attendance_enabled = _main()._is_auto_attendance_enabled(
                        school_username)

                    if not is_auto_attendance_enabled:
                        # 未启用自动签到：累计未启用轮次，连续多轮仍未启用则退出线程。
                        # 旧实现无条件 continue + wait(30)，导致线程永久存活空转
                        # （自动签到关闭后台线程却不退出，属于"无限期存在"的根因之一）。
                        disabled_rounds += 1
                        if disabled_rounds >= _main().AUTO_ATTENDANCE_DISABLED_ROUNDS_BEFORE_EXIT:
                            logging.info(
                                f"[账号刷新线程] 账号 {account_id} (学校账号: {school_username}) "
                                f"连续 {disabled_rounds} 轮未启用自动签到，线程退出"
                            )
                            break
                        logging.debug(
                            f"[账号刷新线程] 账号 {account_id} (学校账号: {school_username}) 未启用自动签到，等待..."
                        )
                        # 使用 wait 而不是 sleep，以便能响应停止信号
                        if stop_event.wait(timeout=30):
                            # 如果收到停止信号，退出循环
                            break
                        # 继续下一次循环
                        continue

                    # 本轮确认启用，重置未启用计数
                    disabled_rounds = 0

                    # === 第三步：检查是否已登录 ===
                    # 确保账号已登录（有有效的 user_data.id）
                    if not account.user_data or not account.user_data.id:
                        logging.info(f"[账号刷新线程] 账号 {account_id} 未登录，等待...")
                        # 等待30秒后重新检查
                        if stop_event.wait(timeout=30):
                            break
                        continue

                    operation_lock = getattr(
                        account, "account_operation_lock", None
                    )
                    if operation_lock is None:
                        operation_lock = threading.Lock()
                    if not operation_lock.acquire(blocking=False):
                        logging.debug(
                            f"[账号刷新线程] 账号 {account_id} 正在执行其它操作，跳过本轮"
                        )
                        if stop_event.wait(timeout=1):
                            break
                        continue

                    try:
                        # === 第四步：获取刷新间隔 ===
                        # 从账号参数中获取刷新间隔（秒）
                        refresh_interval_s = account.params.get(
                            "auto_attendance_refresh_s", 15)
                        # 确保刷新间隔不小于10秒（防止过于频繁的请求）
                        refresh_interval_s = max(10, refresh_interval_s)

                        # === 第五步：执行自动签到检查 ===
                        logging.info(
                            f"[账号刷新线程] 账号 {account_id} 开始自动签到检查"
                        )

                        # 调用签到检查函数
                        # 这个函数会检查是否有需要签到的活动，并自动执行签到
                        auto_attendance_closed = (
                            self._check_and_trigger_auto_attendance(account)
                        )
                        if auto_attendance_closed:
                            break

                        # === 第六步：刷新通知 ===
                        logging.info(f"[账号刷新线程] 账号 {account_id} 刷新通知")

                        # 检查账号对象是否有 get_notifications 方法
                        if hasattr(account, 'get_notifications'):
                            result = account.get_notifications(
                                is_auto_refresh=True)

                            if result.get("success"):
                                session_id = getattr(
                                    account, "_web_session_id", None)

                                if session_id and hasattr(_main(), "socketio"):
                                    try:
                                        _main().socketio.emit(
                                            "onNotificationsUpdated",
                                            result,
                                            room=session_id
                                        )
                                        logging.debug(
                                            f"[账号刷新线程] 已向账号 {account_id} 的会话推送通知更新"
                                        )
                                    except Exception as e:
                                        logging.error(
                                            f"[账号刷新线程] 账号 {account_id} SocketIO推送通知失败: {e}",
                                            exc_info=True
                                        )

                        # === 第七步：更新多账号统计信息 ===
                        if (
                            self.is_multi_account_mode
                            and hasattr(account, 'summary')
                        ):
                            try:
                                self._multi_fetch_attendance_stats(account)
                                self._update_account_status_js(
                                    account, summary=account.summary)
                            except Exception as e:
                                logging.error(
                                    f"[账号刷新线程] 账号 {account_id} 更新统计失败: {e}",
                                    exc_info=True
                                )
                    finally:
                        operation_lock.release()

                    # === 第八步：等待下一次刷新 ===
                    logging.info(
                        f"[账号刷新线程] 账号 {account_id} 等待 {refresh_interval_s} 秒后再次刷新"
                    )

                    # 等待指定的刷新间隔
                    # 使用 wait 而不是 sleep，以便能响应停止信号
                    if stop_event.wait(timeout=refresh_interval_s):
                        # 如果收到停止信号，退出循环
                        break

                except Exception as e:
                    # 捕获并记录执行过程中的任何异常
                    logging.error(
                        f"[账号刷新线程] 账号 {account_id} 执行出错: {e}",
                        exc_info=True
                    )
                    # 发生错误后等待60秒再重试（避免错误循环）
                    if stop_event.wait(timeout=60):
                        break

        finally:
            # === 清理阶段 ===
            # 无论线程是正常退出还是异常退出，都会执行此清理代码

            # 使用线程锁保护对共享字典的访问
            with self.threads_lock:
                # 从线程管理字典中移除该线程的记录
                if account_id in self.account_refresh_threads:
                    del self.account_refresh_threads[account_id]
                    logging.info(f"[账号刷新线程] 已从线程字典中移除账号 {account_id}")

            # 记录线程停止日志
            logging.info(f"[账号刷新线程] 停止 - 账号ID: {account_id}")

    def _multi_account_monitor_worker(self, stop_event=None):
        """
        多账号模式监控线程（新版实现）

        这是一个守护线程，在多账号模式下持续运行。
        它的职责是：
        1. 定期遍历所有账号
        2. 检查每个账号是否启用了自动签到
        3. 确保每个启用自动签到的账号都有独立的刷新线程在运行

        这个监控线程不直接执行签到，而是确保每个账号都有自己的工作线程。
        """
        # 记录监控线程启动日志
        logging.info("[多账号监控] 监控线程已启动")
        stop_event = stop_event or self._get_session_stop_event()

        # 主循环：持续运行直到收到停止信号
        # 使用 wait 而不是直接循环，可以更快地响应停止信号
        while (
            not stop_event.is_set()
            and not self.stop_account_monitor.is_set()
        ):
            try:
                # === 第零步：回收所有超时的自动签到记录 ===
                # 这一步与当前是否登录某个账号无关，是修复"自动签到账号无限期
                # 存在"的关键：仅靠 _is_auto_attendance_enabled() 的读路径清理，
                # 永远不会评估那些已不在会话中的账号。
                try:
                    sweep = _main().expire_stale_auto_attendance_accounts(
                        reason="monitor_sweep"
                    )
                    if sweep.get("removed"):
                        logging.info(
                            f"[多账号监控] 已回收 {len(sweep['removed'])} 条超时自动签到记录: "
                            f"{sweep['removed']}"
                        )
                except Exception as sweep_error:
                    logging.error(
                        f"[多账号监控] 回收超时自动签到记录失败: {sweep_error}",
                        exc_info=True,
                    )

                # === 第一步：检查是否处于多账号模式 ===
                if not self.is_multi_account_mode:
                    # 如果不在多账号模式，等待5秒后重新检查
                    # 这种情况可能发生在退出多账号模式后
                    if stop_event.wait(timeout=5):
                        break
                    continue

                # === 第二步：检查是否有账号 ===
                if not self.accounts:
                    # 如果没有任何账号，等待5秒后重新检查
                    if stop_event.wait(timeout=5):
                        break
                    continue

                # === 第三步：遍历所有账号 ===
                # 使用 list() 创建副本，避免在迭代时字典被修改导致错误
                for username, acc in list(self.accounts.items()):
                    try:
                        # 从JSON配置读取该账号的自动签到启用状态
                        school_username = acc.user_data.username if acc.user_data and acc.user_data.username else None
                        is_auto_enabled = _main()._is_auto_attendance_enabled(
                            school_username) if school_username else False

                        # 检查账号是否已登录（有有效的 user_data.id）
                        has_user_id = acc.user_data and acc.user_data.id

                        # 只有同时满足以下条件才需要刷新线程：
                        # 1. 启用了自动签到
                        # 2. 账号已登录
                        if is_auto_enabled and has_user_id:
                            # 规范化账号ID为字符串
                            account_id = str(acc.user_data.id)

                            # 确保该账号有刷新线程
                            # 如果没有或线程已停止，会自动创建新线程
                            self._ensure_account_refresh_thread(account_id)

                            logging.debug(
                                f"[多账号监控] 已检查账号 {username} (ID: {account_id})"
                            )

                    except Exception as e:
                        # 处理单个账号时出错，记录日志但继续处理其他账号
                        logging.error(
                            f"[多账号监控] 处理账号 {username} 时出错: {e}",
                            exc_info=True
                        )

                # === 第三步之二：清理不再需要的刷新线程记录 ===
                # 自动签到关闭或账号登出后，刷新线程会自行退出；此处回收其字典项，
                # 避免 account_refresh_threads 无限增长，也让"线程仍在"的旧记录
                # 不再阻止后续重新创建线程。
                try:
                    active_account_ids = set()
                    for username, acc in list(self.accounts.items()):
                        if (
                            acc.user_data
                            and acc.user_data.id
                            and acc.user_data.username
                            and _main()._is_auto_attendance_enabled(
                                acc.user_data.username
                            )
                        ):
                            active_account_ids.add(str(acc.user_data.id))

                    with self.threads_lock:
                        stale_ids = [
                            account_id
                            for account_id, thread in list(
                                self.account_refresh_threads.items()
                            )
                            if account_id not in active_account_ids
                            and not thread.is_alive()
                        ]
                        for account_id in stale_ids:
                            self.account_refresh_threads.pop(account_id, None)
                    if stale_ids:
                        logging.info(
                            f"[多账号监控] 已回收 {len(stale_ids)} 个已停止的刷新线程记录: "
                            f"{stale_ids}"
                        )
                except Exception as cleanup_error:
                    logging.error(
                        f"[多账号监控] 清理刷新线程记录失败: {cleanup_error}",
                        exc_info=True,
                    )

                # === 第四步：等待一段时间后再次检查 ===
                # 每60秒检查一次所有账号的线程状态
                # 使用 wait 而不是 sleep，以便能响应停止信号
                if (
                    stop_event.wait(timeout=60)
                    or self.stop_account_monitor.is_set()
                ):
                    # 如果收到停止信号，退出循环
                    break

            except Exception as e:
                # 捕获并记录监控循环中的任何异常
                logging.error(f"[多账号监控] 出错: {e}", exc_info=True)
                # 发生错误后等待60秒再重试
                if stop_event.wait(timeout=60):
                    break

        # 记录监控线程停止日志
        logging.info("[多账号监控] 监控线程已停止")

    def _auto_refresh_worker(self):
        """
        (单账号) 后台自动刷新通知和签到的线程 (已修复)
        已废弃但保留以兼容旧代码，改为从JSON配置读取自动签到状态
        """
        # 连续未启用自动签到的轮次计数：达到阈值后线程主动退出
        disabled_rounds = 0
        while not self.stop_auto_refresh.is_set():
            try:
                if not self.user_data.id or self.is_multi_account_mode:
                    if self.stop_auto_refresh.wait(timeout=5.0):
                        break
                    continue
                refresh_interval_s = self.params.get(
                    "auto_attendance_refresh_s", 15)
                refresh_interval_s = max(10, refresh_interval_s)
                if self.is_multi_account_mode or not self.user_data.id:
                    continue

                # 从JSON配置读取自动签到启用状态
                school_username = self.user_data.username if self.user_data and self.user_data.username else None
                is_enabled = _main()._is_auto_attendance_enabled(
                    school_username) if school_username else False

                if is_enabled:
                    # 本轮确认启用，重置未启用计数
                    disabled_rounds = 0
                    self.log_and_notify_frontend("(后台) 自动签到已启用，正在检查...")
                    auto_attendance_closed = self._check_and_trigger_auto_attendance(self)
                    if auto_attendance_closed:
                        break
                    self.log_and_notify_frontend("正在自动刷新通知 (后台)...")
                    result = self.get_notifications(is_auto_refresh=True)
                    if result.get("success"):
                        session_id = getattr(self, "_web_session_id", None)
                        if session_id and hasattr(_main(), "socketio"):
                            try:
                                _main().socketio.emit(
                                    "onNotificationsUpdated", result, room=session_id
                                )
                                logging.debug(
                                    f"[_auto_refresh_worker] 已向会话 {session_id[:8]} 推送通知更新"
                                )
                            except Exception as e:
                                logging.error(
                                    f"[_auto_refresh_worker] SocketIO推送通知失败: {e}",
                                    exc_info=True,
                                )
                        elif not session_id:
                            logging.warning(
                                f"[_auto_refresh_worker] 无法推送通知：未找到 _web_session_id"
                            )
                        else:
                            logging.warning(
                                f"[_auto_refresh_worker] 无法推送通知：socketio 实例不可用"
                            )
                else:
                    # 未启用自动签到：累计未启用轮次，连续多轮仍未启用则退出线程，
                    # 避免线程在自动签到关闭后永久驻留空转。
                    disabled_rounds += 1
                    if disabled_rounds >= _main().AUTO_ATTENDANCE_DISABLED_ROUNDS_BEFORE_EXIT:
                        logging.info(
                            f"[_auto_refresh_worker] 连续 {disabled_rounds} 轮未启用自动签到，线程退出"
                        )
                        break

                self.log_and_notify_frontend(f"自动刷新完成，等待 {refresh_interval_s} 秒后再次刷新...")
                if self.stop_auto_refresh.wait(timeout=refresh_interval_s):
                    break

            except Exception as e:
                self.log_and_notify_frontend(f"自动刷新线程出错: {e}")
                logging.error(f"Auto-refresh worker error: {e}", exc_info=True)
                if self.stop_auto_refresh.wait(timeout=60):
                    break

        logging.info("Auto-refresh worker stopped.")

    def _check_and_trigger_auto_attendance(self, context: "Api | AccountSession"):
        """
        检查并执行单个上下文(Api或AccountSession)的自动签到。
        改为从JSON配置读取自动签到状态
        """
        if isinstance(context, _main().AccountSession):
            client = context.api_client
            log_func = context.log_and_notify_frontend
            user = context.user_data
            params = context.params
            # 从JSON配置读取启用状态
            school_username = user.username if user and user.username else None
            if not school_username or not _main()._is_auto_attendance_enabled(school_username):
                return False
        else:
            client = self.api_client
            log_func = self.log_and_notify_frontend
            user = self.user_data
            params = self.params
            # 从JSON配置读取启用状态
            school_username = user.username if user and user.username else None
            if not school_username or not _main()._is_auto_attendance_enabled(school_username):
                return False

        if not user.id:
            log_func("用户未登录，跳过自动签到。")
            return False

        log_func("(后台) 正在检查自动签到任务...")

        try:
            # 性能优化：只拉取前几条通知而非全部
            # 使用配置常量 AUTO_ATTENDANCE_NOTICE_LIMIT 控制拉取数量
            # 原因：签到任务通常出现在最新的通知中，减少拉取数量可以：
            # 1. 降低API调用开销，减少网络传输时间
            # 2. 减少服务器负载，提高响应速度
            # 3. 加快通知遍历处理速度
            # 4. 降低内存占用
            # 实践中，前几条通知足以覆盖绝大多数签到任务场景
            list_resp = client.get_notice_list(
                offset=0, limit=_main().AUTO_ATTENDANCE_NOTICE_LIMIT, type_id=0)
            if not (list_resp and list_resp.get("success")):
                log_func("获取通知列表失败，跳过自动签到。")
                return False

            notices = list_resp.get("data", {}).get("noticeList", [])
            if not notices:
                log_func("(后台) 通知列表为空。")
                return False

            log_func(f"(后台) 获取到 {len(notices)} 条通知，正在检查签到任务...")
            logging.debug(f"(后台) 通知列表原始数据: {notices}")
            logging.debug(f"(后台) 通知列表: {[notice.get('title') + ' - ' + notice.get('image') for notice in notices]}")
            
            triggered_count = 0
            for notice in notices:
                is_attendance = (notice.get("image") == "attendance" )or ("签到" in notice.get("title", "")) or ("签到" in notice.get("content",""))
                if not (is_attendance and notice.get("id")):
                    continue
                
                if is_attendance:
                    logging.debug(f"(后台) 发现签到通知: {notice.get('title')} (ID: {notice.get('id')})")

                roll_call_id = notice["id"]
                info_resp = client.get_roll_call_info(roll_call_id, user.id)
                logging.debug(f"(后台) 获取签到信息响应: {info_resp}")
                status = -1
                finished = None
                if info_resp and info_resp.get("success"):
                    data = info_resp.get("data", {})
                    roll_call_info = data.get("rollCallInfo", {})
                    status = roll_call_info.get("status")  # 签到状态
                    finished = data.get("attendFinish")    # 签到是否完成 1为完成

                    # 统一转换为 int 方便比较
                    status = int(status) if isinstance(status, str) and status.lstrip('-').isdigit() else status
                    finished = int(finished) if isinstance(finished, str) and finished.isdigit() else finished

                logging.debug(f"(后台) 签到任务状态: {status}, 完成状态: {finished}")

                # 待签到：status==-1 且 attendFinish 未设置/为0（无 attendFinish 字段）
                # 已过期：status==-1 且 attendFinish==1
                # 已完成：status!=-1 且 attendFinish==1
                if status == -1 and (finished == 1 or finished is True):
                    logging.debug(f"(后台) 签到任务已过期，跳过: {notice.get('title')}")
                    continue
                if (status != -1) and (finished == 1 or finished is True):
                    logging.debug(f"(后台) 签到任务已完成，跳过: {notice.get('title')}")
                    continue

                # 待签到任务（status==-1 且 attendFinish 未设置，或 status!=-1 且 attendFinish!=1）
                log_func(
                    f"检测到待签到任务 '{notice.get('title')}'，正在自动签到..."
                )
                coords_str = notice.get("updateBy", "").split(",")   # 获取签到坐标字符串并拆分为经纬度
                if len(coords_str) == 2:
                    try:
                        target_lat, target_lon = float(coords_str[0]), float(
                            coords_str[1]
                        )
                        target_coords = (target_lon, target_lat)
                        logging.debug(f"(后台) 解析签到坐标: {target_coords}")
                        logging.debug(f"(后台) 执行自动签到，参数 - roll_call_id: {roll_call_id}, target_coords: {target_coords}")
                        auto_result = self.trigger_attendance(
                            roll_call_id,
                            target_coords,
                            "random",
                            specific_coords=None,
                            is_makeup=False,
                            acc=(
                                context
                                if isinstance(context, _main().AccountSession)
                                else None
                            ),
                        )

                        if auto_result.get("success") and auto_result.get("message") != "已签到":
                            log_func(f"自动签到 '{notice.get('title')}' 成功。")
                            triggered_count += 1
                            if _main()._record_auto_attendance_success(school_username, params):
                                log_func(
                                    "自动签到已达到设定次数，自动签到已关闭。"
                                )
                                return True
                        else:
                            log_func(
                                f"自动签到 '{notice.get('title')}' 失败: {auto_result.get('message', '')}"
                            )
                    except Exception as e:
                        log_func(f"签到坐标解析或执行失败: {e}")
                else:
                    log_func("签到通知坐标格式错误，跳过。")

            if triggered_count == 0:
                log_func("(后台) 未发现待处理的签到任务。")
            return False

        except Exception as e:
            log_func(f"自动签到检查时出错: {e}")
            logging.error(
                f"[_check_and_trigger_auto_attendance] Error: {e}", exc_info=True
            )
            return False

    def _multi_auto_attendance_worker(self):
        """
        (多账号) 后台自动刷新和签到所有账号的线程
        已废弃但保留以兼容旧代码，改为从JSON配置读取自动签到状态
        注意：新版本使用 _account_refresh_worker 替代此线程
        """
        while not self.stop_multi_auto_refresh.wait(timeout=1.0):
            try:
                # 此处不再检查 global_params 中的 auto_attendance_enabled
                # 因为新版本中每个账号独立在JSON中配置，不使用全局开关
                if (
                    not self.is_multi_account_mode
                    or not self.accounts
                ):
                    time.sleep(5)
                    continue

                refresh_interval_s = self.global_params.get(
                    "auto_attendance_refresh_s", 15)

                self.log_and_notify_frontend(f"(多账号) 自动签到: 等待 {refresh_interval_s} 秒...")
                if self.stop_multi_auto_refresh.wait(timeout=refresh_interval_s):
                    break

                if not self.is_multi_account_mode:
                    continue

                self.log_and_notify_frontend("(多账号) 正在为所有账号执行后台签到检查...")

                accounts_to_check = list(self.accounts.values())

                for acc in accounts_to_check:
                    if self.stop_multi_auto_refresh.is_set():
                        break

                    # 从JSON配置读取该账号的自动签到启用状态
                    school_username = acc.user_data.username if acc.user_data and acc.user_data.username else None
                    if school_username and _main()._is_auto_attendance_enabled(school_username):
                        if acc.user_data.id:
                            if self._check_and_trigger_auto_attendance(acc):
                                acc.log_and_notify_frontend("(后台) 自动签到已达到设定次数，停止本账号自动刷新。")
                                continue
                            self._multi_fetch_attendance_stats(acc)
                            self._update_account_status_js(
                                acc, summary=acc.summary)
                            time.sleep(random.uniform(1.0, 3.0))
                        else:

                            acc.log_and_notify_frontend("(后台) 尚未登录，跳过自动签到检查。")
                    else:

                        acc.log_and_notify_frontend("(后台) 自动签到未在此账号上启用，跳过。")

            except Exception as e:
                self.log_and_notify_frontend(f"(多账号) 自动签到线程出错: {e}")
                logging.error(
                    f"Multi-auto-attendance worker error: {e}", exc_info=True)
                time.sleep(60)

        logging.info("Multi-auto-attendance worker stopped.")

    def _normalize_status_flag(self, v) -> int:
        """将后端返回的各种 isExecute 表达式规范为 0 或 1"""
        try:
            if v is None:
                return 0
            if isinstance(v, bool):
                return 1 if v else 0
            s = str(v).strip()
            if s == "":
                return 0
            if s.isdigit():
                return 1 if int(s) == 1 else 0
            if s.lower() in ("true", "yes", "y", "1"):
                return 1
            return 0
        except Exception:
            return 0

    def _should_preserve_status(self, status: str, new_status: str = None) -> bool:
        """
        判断当前状态是否应保留。
        - 如果当前是错误/中止态，则保留，除非新状态明确表示成功或完成。
        """
        if not status:
            return False
        s = str(status).strip()
        error_keywords = (
            "登录失败",
            "刷新失败",
            "执行出错",
            "网络错误",
            "已中止",
            "已停止",
        )

        if any(k in s for k in error_keywords):
            if new_status and new_status in (
                "登录成功",
                "全部完成",
                "无任务可执行",
                "待命",
            ):
                return False
            return True
        return False
