from __future__ import annotations

import copy
import datetime
import json
import logging
import os
import secrets
import threading
import time


def _main():
    import main
    return main


class TokenManager:
    """管理用户登录令牌的系统"""

    def __init__(self, tokens_dir):
        logging.info("=" * 80)
        logging.info(f"TokenManager: 初始化令牌管理器，目录: {tokens_dir}")
        self.tokens_dir = tokens_dir
        self.lock = threading.Lock()
        self.guest_store = _main().GuestTokenStore(os.path.join(tokens_dir, "guests"))
        if not os.path.exists(tokens_dir):
            os.makedirs(tokens_dir)
            logging.info(f"TokenManager: 创建令牌目录: {tokens_dir}")
        else:
            logging.debug(f"TokenManager: 令牌目录已存在: {tokens_dir}")
        logging.info("TokenManager: 初始化完成")
        logging.info("=" * 80)

    def _get_token_file_path(self, username):
        """获取用户的token文件路径"""
        file_path = os.path.join(self.tokens_dir, f"{username}.json")
        logging.debug(
            f"_get_token_file_path: 用户 {username} 的令牌文件: {file_path}")
        return file_path

    def generate_token(self):
        """生成2048位(256字节)的安全令牌"""
        token = secrets.token_hex(256)
        logging.debug(f"generate_token: 生成新令牌，长度: {len(token)} 字符")
        return token

    def create_token(self, username, session_id=None):
        """为用户创建新令牌并存储"""
        logging.info(f"create_token: 为用户 {username} 创建令牌...")
        token = self.generate_token()
        created_at = time.time()
        expires_at = created_at + 3600

        token_data = {
            "token": token,
            "created_at": created_at,
            "expires_at": expires_at,
            "last_activity": created_at,
        }

        with self.lock:
            token_file = self._get_token_file_path(username)

            with open(token_file, "w", encoding="utf-8") as f:
                json.dump(token_data, f, indent=2, ensure_ascii=False)

        logging.info(f"为用户 {username} 创建新令牌完成")
        return token

    def verify_token(self, username, session_id, token):
        """验证令牌是否有效"""
        token_file = self._get_token_file_path(username)

        if not os.path.exists(token_file):
            return False, "no_token_file"

        try:
            with open(token_file, "r", encoding="utf-8") as f:
                token_data = json.load(f)

            if token_data.get("token") != token:
                return False, "token_mismatch"

            if time.time() > token_data.get("expires_at", 0):
                return False, "token_expired"

            return True, "valid"

        # 捕获JSON解析错误：当token文件为空或格式错误时，直接返回无效标记，不记录ERROR日志
        # 这是预期的错误情况（文件损坏或被手动修改），不需要记录错误级别日志
        except json.JSONDecodeError:
            return False, "invalid_token_file"
        except Exception as e:
            # 只有在遇到其他意外错误时才记录ERROR日志
            logging.error(f"验证令牌时出错: {e}")
            return False, "error"

    def get_valid_token_for_session(self, username, session_id=None):
        """
        获取指定用户的有效Token（如果存在且未过期）。
        如果找到有效Token，会刷新其活动时间。
        """
        token_file = self._get_token_file_path(username)

        if not os.path.exists(token_file):
            return None

        try:
            with self.lock:
                with open(token_file, "r", encoding="utf-8") as f:
                    token_data = json.load(f)

                current_time = time.time()

                if current_time > token_data.get("expires_at", 0):
                    logging.debug(
                        f"get_valid_token_for_session: 用户 {username} 的Token已过期"
                    )
                    return None

                token_data["last_activity"] = current_time
                token_data["expires_at"] = current_time + 3600

                with open(token_file, "w", encoding="utf-8") as f:
                    json.dump(token_data, f, indent=2, ensure_ascii=False)

                logging.info(
                    f"get_valid_token_for_session: 找到并刷新了用户 {username} 的有效Token"
                )
                return token_data.get("token")

        except Exception as e:
            logging.error(f"获取Token时出错 (用户: {username}): {e}")
            return None

    def refresh_token(self, username, session_id=None):
        """刷新令牌的过期时间和最后活动时间"""
        with self.lock:
            token_file = self._get_token_file_path(username)

            if not os.path.exists(token_file):
                return False

            try:
                with open(token_file, "r", encoding="utf-8") as f:
                    token_data = json.load(f)

                current_time = time.time()
                token_data["expires_at"] = current_time + 3600
                token_data["last_activity"] = current_time

                with open(token_file, "w", encoding="utf-8") as f:
                    json.dump(token_data, f, indent=2, ensure_ascii=False)

                return True

            except Exception as e:
                logging.error(f"刷新令牌时出错: {e}")
                return False

    def invalidate_token(self, username, session_id=None):
        """使令牌失效（用于登出）

        新的简化设计：直接删除用户的token文件

        Args:
            username: 用户名
            session_id: 会话UUID（保留参数以兼容，不再使用）
        """
        with self.lock:
            token_file = self._get_token_file_path(username)

            if os.path.exists(token_file):
                try:
                    os.remove(token_file)
                    logging.info(f"令牌已失效: {username}")
                except Exception as e:
                    logging.error(f"删除令牌文件时出错: {e}")

    def get_active_sessions(self, username):
        """获取用户所有有效的会话"""
        logging.debug(
            f"get_active_sessions: token文件不再管理session列表，请使用session管理功能"
        )
        return []

    def cleanup_expired_tokens(self, username):
        """清理过期的令牌

        新的简化设计：如果token过期，直接删除整个token文件

        Args:
            username: 用户名
        """
        with self.lock:
            token_file = self._get_token_file_path(username)

            if not os.path.exists(token_file):
                return

            try:
                with open(token_file, "r", encoding="utf-8") as f:
                    token_data = json.load(f)

                current_time = time.time()

                if current_time > token_data.get("expires_at", 0):
                    os.remove(token_file)
                    logging.info(f"清理了过期令牌: {username}")

            except Exception as e:
                logging.error(f"清理过期令牌时出错: {e}")

    def detect_multi_device_login(self, username, new_session_id):
        """检测多设备登录"""
        active_sessions = self.get_active_sessions(username)

        old_sessions = [s for s in active_sessions if s != new_session_id]

        if old_sessions:
            logging.info(f"检测到多设备登录: {username}, 旧会话数: {len(old_sessions)}")

        return old_sessions


# ==============================================================================
# 数据结构定义
# ==============================================================================


class UserData:
    """存储用户相关信息的类"""

    def __init__(self):
        self.name: str = ""
        self.phone: str = ""
        self.student_id: str = ""
        self.id: str = ""
        self.registration_time: str = ""
        self.first_login_time: str = ""
        self.id_card: str = ""
        self.last_login_time: str = ""
        self.current_login_time: str = ""
        self.username: str = ""
        self.gender: str = ""
        self.school_name: str = ""
        self.attribute_type: str = ""
        self.avatar_url: str = ""


def _normalize_gender_value(value) -> str:
    """将学校接口返回的性别值统一为前端使用的“男/女”文本。"""
    if value is None or isinstance(value, bool):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    normalized = text.casefold()
    if normalized in {"0", "unknown", "未知", "保密"}:
        return ""
    if normalized in {"1", "m", "male", "man", "男", "男生", "男性"}:
        return "男"
    if normalized in {"2", "f", "female", "woman", "女", "女生", "女性"}:
        return "女"
    return text


class RunData:
    """存储单个跑步任务相关数据的类"""

    def __init__(self):
        self.draft_coords: list[tuple[float, float, int]] = []
        self.run_coords: list[tuple[float, float, int]] = []
        self.recommended_coords: list[tuple[float, float]] = []
        self.target_points: list[tuple[float, float]] = []
        self.target_point_names: str = ""
        self.upload_time: str = ""
        self.start_time: str = ""
        self.end_time: str = ""
        self.run_name: str = ""
        self.errand_id: str = ""
        self.errand_schedule: str = ""
        self.status: int = 0

        self.target_sequence: int = 0
        self.is_in_target_zone: bool = False
        self.trid: str = ""
        self.details_fetched: bool = False
        self.total_run_time_s: float = 0.0
        self.total_run_distance_m: float = 0.0
        self.distance_covered_m: float = 0.0
        self.current_point_index: int = 0
        self.suppress_last_target_until_finish: bool = True


class AccountSession:
    """封装单个账号的所有运行时数据、状态和操作"""

    def __init__(self, username, password, api_bridge, tag=None):
        self.username: str = username
        self.password: str = password
        self.api_bridge = api_bridge
        self.window = api_bridge.window

        self.api_client = _main().ApiClient(self)
        self.user_data = _main().UserData()
        self.all_run_data: list[RunData] = []

        self.params = copy.deepcopy(api_bridge.global_params)
        self.device_ua: str = ""

        self.server_attendance_radius_m = 0.0
        self.last_radius_fetch_time = 0

        self.tag: str = tag if tag else ""

        self.is_first_login_verified: bool = False
        self.is_verifying: bool = False
        self.last_refresh_time: float = 0

        self.status_text: str = "待命"
        self.summary = {
            "total": 0,
            "completed": 0,
            "pending": 0,
            "executable": 0,
            "expired": 0,
            "not_started": 0,
        }

        self.worker_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.account_operation_lock = threading.Lock()

    def log(self, message: str):
        """为日志自动添加账号前缀"""
        self.api_bridge.log(f"[{self.username}] {message}")


















def _is_order_terminal_for_repay(order_data):
    status = str((order_data or {}).get("status", "")).strip()
    return status in {"paid", "refunded_partial", "refunded_full"}


def _advance_order_status_by_timeout(order_data, now_iso=None):
    if not isinstance(order_data, dict):
        return False

    status = str(order_data.get("status", "")).strip()
    if status not in {
        _main().ORDER_STATUS_PENDING,
        _main().ORDER_STATUS_TIMEOUT,
    }:
        return False

    expires_at = str(order_data.get("expires_at") or "").strip()
    if not expires_at:
        return False

    now_dt = (
        datetime.datetime.fromisoformat(now_iso)
        if now_iso
        else datetime.datetime.now(datetime.timezone.utc)
    )
    expires_dt = datetime.datetime.fromisoformat(expires_at)
    if expires_dt.tzinfo is None:
        expires_dt = expires_dt.replace(tzinfo=datetime.timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=datetime.timezone.utc)

    if now_dt <= expires_dt:
        return False

    order_data["status"] = _main().ORDER_STATUS_CLOSED
    order_data["closed_at"] = now_dt.isoformat()
    return True


def _build_billing_qr_cache_key(school_id, billing_id, pay_type):
    return f"{str(school_id).strip()}:{str(billing_id).strip()}:{str(pay_type).strip()}"


def _load_qr_cache_index():
    if not os.path.exists(_main().QR_CACHE_INDEX_FILE):
        return {}
    try:
        with open(_main().QR_CACHE_INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_qr_cache_index(index_data):
    os.makedirs(_main().PAYMENT_ORDERS_DIR, exist_ok=True)
    safe_data = index_data if isinstance(index_data, dict) else {}
    with open(_main().QR_CACHE_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(safe_data, f, ensure_ascii=False, indent=2)


def _get_reusable_billing_qr(cache_key, now_iso=None):
    index_data = _load_qr_cache_index()
    item = index_data.get(str(cache_key or "").strip())
    if not isinstance(item, dict):
        return None

    expires_at = str(item.get("expires_at") or "").strip()
    if not expires_at:
        return None

    now_dt = (
        datetime.datetime.fromisoformat(now_iso)
        if now_iso
        else datetime.datetime.now(datetime.timezone.utc)
    )
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=datetime.timezone.utc)

    try:
        expires_dt = datetime.datetime.fromisoformat(expires_at)
    except Exception:
        return None
    if expires_dt.tzinfo is None:
        expires_dt = expires_dt.replace(tzinfo=datetime.timezone.utc)

    if now_dt > expires_dt:
        return None

    return item


def _invalidate_billing_qr_cache_by_order(order_id):
    target_order_id = str(order_id or "").strip()
    if not target_order_id:
        return False

    index_data = _load_qr_cache_index()
    changed = False
    for key, value in list(index_data.items()):
        if isinstance(value, dict) and str(value.get("order_id") or "").strip() == target_order_id:
            index_data.pop(key, None)
            changed = True

    if changed:
        _save_qr_cache_index(index_data)
    return changed


def _resolve_billing_payment_entry(school_id, billing_id, pay_type, existing_order, now_iso=None):
    normalized_order = existing_order if isinstance(existing_order, dict) else {}
    _advance_order_status_by_timeout(normalized_order, now_iso=now_iso)
    normalized_status = str(normalized_order.get("status") or "").strip()

    if _is_order_terminal_for_repay(normalized_order):
        return {
            "decision": "reject_terminal",
            "normalized_existing_status": normalized_status,
            "cache_key": _build_billing_qr_cache_key(school_id, billing_id, pay_type),
        }

    cache_key = _build_billing_qr_cache_key(school_id, billing_id, pay_type)
    reusable_item = _get_reusable_billing_qr(cache_key, now_iso=now_iso)
    if isinstance(reusable_item, dict):
        return {
            "decision": "reuse_qr",
            "normalized_existing_status": normalized_status,
            "cache_key": cache_key,
            "reusable_item": reusable_item,
        }

    return {
        "decision": "create_new",
        "normalized_existing_status": normalized_status,
        "cache_key": cache_key,
    }


def _apply_payment_success_transition(order_data, paid_time=None):
    if not isinstance(order_data, dict):
        return order_data
    order_data["status"] = _main().ORDER_STATUS_PAID
    order_data["paid_time"] = paid_time or datetime.datetime.now(datetime.timezone.utc).isoformat()
    order_data["paid_at"] = order_data.get("paid_at") or time.time()
    return order_data


def _apply_refund_transition(order_data, refund_amount):
    if not isinstance(order_data, dict):
        return order_data
    current_total = float(order_data.get("refund_total") or 0)
    refund_value = float(refund_amount or 0)
    new_total = round(current_total + refund_value, 2)
    order_data["refund_total"] = new_total

    total_amount = float(order_data.get("amount") or 0)
    if total_amount > 0 and new_total >= total_amount:
        order_data["status"] = _main().ORDER_STATUS_REFUNDED_FULL
    else:
        order_data["status"] = _main().ORDER_STATUS_REFUNDED_PARTIAL
    return order_data














def _cleanup_random_background_index(cache_dir):
    index_data = _main()._load_random_background_index(cache_dir)
    files = index_data.get("files", {}) if isinstance(index_data, dict) else {}
    if not files:
        return
    existing_files = {
        file_name
        for file_name in os.listdir(cache_dir)
        if os.path.isfile(os.path.join(cache_dir, file_name)) and file_name != "index.json"
    }
    cleaned_files = {
        file_name: entry
        for file_name, entry in files.items()
        if file_name in existing_files
    }
    if cleaned_files != files:
        index_data["files"] = cleaned_files
        _main()._save_random_background_index(cache_dir, index_data)


def _allow_random_background_feedback(cache_dir, client_ip, target):
    normalized_ip = str(client_ip or "-").strip() or "-"
    normalized_target = "mobile" if str(target or "").strip().lower() == "mobile" else "pc"
    feedback_key = f"{normalized_ip}:{normalized_target}"
    index_data = _main()._load_random_background_index(cache_dir)
    feedback = index_data.setdefault("feedback", {})
    now = time.time()
    last_feedback_at = float(feedback.get(feedback_key) or 0)
    if now - last_feedback_at < 5:
        return False
    feedback[feedback_key] = now
    stale_keys = [key for key, value in feedback.items() if now - float(value or 0) > 3600]
    for key in stale_keys:
        feedback.pop(key, None)
    _main()._save_random_background_index(cache_dir, index_data)
    return True


def _cleanup_random_background_cache(cache_dir, max_cache_size_bytes=None):
    _cleanup_random_background_index(cache_dir)
    if max_cache_size_bytes is None:
        try:
            config = (
                _main()._read_config_ini(_main().CONFIG_JSON_FILE)
                or _main()._get_default_config()
            )
            limit_mb = config.getint(
                "Logging", "random_background_cache_max_size_mb", fallback=1024
            )
            max_cache_size_bytes = 0 if limit_mb <= 0 else limit_mb * 1024 * 1024
        except Exception as e:
            logging.warning(f"[主题背景] 读取背景缓存上限失败，使用默认值 1024MB: {e}")
            max_cache_size_bytes = 1024 * 1024 * 1024
    if max_cache_size_bytes == 0:
        return

    try:
        cache_files = []
        total_size = 0
        for file_name in os.listdir(cache_dir):
            file_path = os.path.join(cache_dir, file_name)
            if file_name == "index.json":
                continue
            if not os.path.isfile(file_path):
                continue

            try:
                stat = os.stat(file_path)
            except OSError as e:
                logging.warning(f"[主题背景] 读取缓存文件信息失败 {file_path}: {e}")
                continue

            total_size += stat.st_size
            cache_files.append((file_path, stat.st_mtime, stat.st_size))

        if total_size <= max_cache_size_bytes:
            return

        cache_files.sort(key=lambda item: item[1])
        for file_path, _, file_size in cache_files:
            if total_size <= max_cache_size_bytes:
                break

            try:
                os.remove(file_path)
                total_size -= file_size
                logging.info(f"[主题背景] 缓存目录超过上限，已删除最早缓存文件: {file_path}")
            except OSError as e:
                logging.warning(f"[主题背景] 删除旧缓存文件失败 {file_path}: {e}")
    except Exception as e:
        logging.warning(f"[主题背景] 清理背景缓存目录失败: {e}")
