from __future__ import annotations

import json
import logging
import random
import re
import threading
import time
from urllib.parse import urlencode, urlsplit

from main_runtime import _main


# 服务端 checkVersion 返回的 version 形如 "1.0.85"，比较时按数字段比，不能按字符串比
# （"1.0.9" > "1.0.85" 在字符串比较里成立，在版本语义里不成立）。
_VERSION_NUM_RE = re.compile(r"\d+")
_APPLE_MOBILE_UA_RE = re.compile(
    r"(?<![a-z])(?:iphone|ipad(?:os)?|ipod|ios)(?![a-z])",
    re.IGNORECASE | re.ASCII,
)
_ANDROID_UA_RE = re.compile(r"\bandroid\b", re.IGNORECASE | re.ASCII)


def scrub_login_query(message):
    """Hide login query strings in access and HTTP transport logs."""
    return re.sub(r"((?:/app|/api|/auth)/login/?)\?[^\s\"'<>]*", r"\1?<redacted>", message)


def _log_headers(headers):
    return _main()._redact_sensitive_log_value({
        name: "<redacted>" if name.lower() in {"authorization", "cookie", "set-cookie"} else value
        for name, value in headers.items()
    })


def _version_key(value) -> tuple:
    """把 "1.0.85" 这类版本号转成可比较的整数元组。"""
    return tuple(int(part) for part in _VERSION_NUM_RE.findall(str(value or "")))


class ApiClient:
    """与 zslf.zsc.edu.cn（智慧校园 App）后端通信的请求层。

    本文件的接口形状以 App/H5 产物 `www/app-service.js`（uni-app + luch-request 3.1.0）
    为契约参考，关键约定：

    1. 路径前缀
       * 非 /run/* 的接口：`{BASE_URL}/app` + 路径，例如 `/appNotice/unreadNumber`
         -> https://zslf.zsc.edu.cn/app/appNotice/unreadNumber
       * /run/* 的接口：`{BASE_URL}` + 路径（**不带 /app 前缀**），例如
         `/run/errand/getErrandList` -> https://zslf.zsc.edu.cn/run/errand/getErrandList
         （App 使用不分端口的同域地址）

    2. 参数位置（luch-request：params -> query string，data -> 请求体）
       * 本客户端覆盖的登录、查询、通知和签到接口使用 query，body 为空。
       * 轨迹上传使用 JSON 请求体，原 App 的三个上传接口超时为 30 秒，
         quickSave 为 15 秒。不能把对象 data 默认编码成表单。

    3. appVersion 和 platform 是请求头。App 从设备读取实际版本，
       GET `/app/checkVersion` 用于检查更新。本项目保留 sync_app_version()
       作为兼容策略，只提升有效版本；静态产物不能证明服务端最低版本阈值。

    4. 响应体统一为 `{"code": 200, "data": ..., "message": ..., "success": true}`；
       鉴权失败时 HTTP 状态码本身也是 401（body 同样是这个 JSON 信封），
       所以 4xx 不能当请求异常处理、更不能重试 —— 要把 body 交给调用方看。
    """

    BASE_URL = "https://zslf.zsc.edu.cn"
    APP_PREFIX = "/app"
    # /run/* 与 App 一样走不分端口的同域地址。
    RUN_BASE_URL = BASE_URL

    API_VERSION = 66            # 旧调用兼容常量；App 用请求头 appVersion
    NEW_APP_VERSION = "1.0.85"  # 版本查询不可用时的兼容默认值
    APP_CLIENT_ID = "com.zx.slm"
    UA_SUFFIX = " uni-app Html5Plus/1.0 (Immersed/29.09091)"
    JSON_CONTENT_TYPE = "application/json;charset=UTF-8"
    FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"

    CONNECT_TIMEOUT = 5
    READ_TIMEOUT = 10
    TRACK_READ_TIMEOUT = 30
    MAX_RETRIES = 10
    RETRY_BACKOFF_SECONDS = 1.5
    # 只有这些状态码值得重试：408/425/429 + 5xx。4xx 重试 10 次既浪费 15 秒，
    # 又会把服务端返回的 JSON 错误信封丢掉（原实现就是这么把 401 变成 None 的）。
    RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504, 505})
    # 进程级版本号缓存：{base_url: 服务端最新版本}
    _APP_VERSION_CACHE: dict = {}

    def __init__(self, owner_instance):
        self.session = _main().requests.Session()
        self.app = owner_instance
        self._device_ua_lock = threading.Lock()
        self._device_ua = self.normalize_device_ua(getattr(owner_instance, "device_ua", None))
        # 运行期版本号：默认取类常量，登录前后可被 sync_app_version() 抬到服务端最新版
        self.app_version = self.NEW_APP_VERSION
        self._app_version_synced = False
        # App 的登录契约：/login 返回 data.accessToken，之后把它原样放进 Authorization
        self._access_token = None
        self._refresh_token = None
        logging.debug("ApiClient已初始化，创建了新的_main().requests.Session会话实例")

    # ------------------------------------------------------------------ 基础工具

    def _api_url(self, path: str) -> str:
        """按 App 的路径前缀规则拼出完整 URL。"""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("/run/"):
            return f"{self.RUN_BASE_URL}{path}"
        return f"{self.BASE_URL}{self.APP_PREFIX}{path}"

    @staticmethod
    def is_unsupported_device_ua(value) -> bool:
        """识别不能用于校园接口的 Apple 移动设备 UA。"""
        return isinstance(value, str) and _APPLE_MOBILE_UA_RE.search(value) is not None

    @classmethod
    def normalize_device_ua(cls, value) -> str:
        """忽略空配置、序列化空值和不受支持的设备 UA。"""
        if not isinstance(value, str):
            return ""
        value = value.strip()
        if value.lower() in {"", "null", "none", "undefined"} or cls.is_unsupported_device_ua(value):
            return ""
        return value

    def ensure_device_ua(self, fallback: str | None = None) -> str:
        """仅使用本客户端所属账号的 UA；丢失时恢复，不借用父会话设备。"""
        with self._device_ua_lock:
            previous_ua = getattr(self.app, "device_ua", None)
            ua = (
                self.normalize_device_ua(previous_ua)
                or self.normalize_device_ua(self._device_ua)
                or self.normalize_device_ua(fallback)
                or self.generate_random_ua()
            )
            self._device_ua = ua
            self.app.device_ua = ua
        if self.is_unsupported_device_ua(previous_ua):
            repair = getattr(self.app, "_repair_unsupported_device_ua", None)
            if callable(repair):
                try:
                    repair(previous_ua, ua)
                except Exception as exc:
                    logging.warning("[设备 UA] 保存替换后的设备 UA 失败 (%s)", type(exc).__name__)
        return ua

    def _app_platform(self, device_ua: str | None = None) -> str:
        """从设备 UA 确定请求平台，兼容保留其他旧自定义平台。"""
        ua = device_ua if device_ua is not None else self.ensure_device_ua()
        if _ANDROID_UA_RE.search(ua):
            return "android"
        os_name = getattr(self.app, "platform", None)
        if os_name and not self.is_unsupported_device_ua(str(os_name)):
            return str(os_name)
        return "android"

    @staticmethod
    def _clean_params(params: dict | None) -> dict | None:
        """丢掉值为 None 的项：urlencode({'a': None}) 会发出 "a=None" 这种脏参数。"""
        if params is None:
            return None
        return {k: v for k, v in params.items() if v is not None}

    def _cookie_token(self) -> str | None:
        """从 Cookie 里找 shiroCookie（旧版 Web 会话的令牌形态，作为兜底）。"""
        try:
            token = self.session.cookies.get_dict().get("shiroCookie")
            if token:
                return token
        except Exception as exc:  # CookieConflictError 等
            logging.debug(
                f"Cookie 读取异常（{type(exc).__name__}），改为逐条查找 shiroCookie"
            )
        for cookie in self.session.cookies:
            if cookie.name == "shiroCookie" and cookie.value:
                return cookie.value
        return None

    def set_access_token(self, token: str | None):
        """设置/清除 App 契约里的 accessToken（Authorization 请求头原样携带，不加 Bearer）。"""
        self._access_token = token or None
        if not self._access_token:
            self._refresh_token = None

    @property
    def access_token(self) -> str | None:
        return self._access_token

    def _get_headers(self) -> dict:
        """构建请求头，包含认证信息和设备信息（字段对齐 App 的 request 拦截器）"""
        device_ua = self.ensure_device_ua()
        user_agent = device_ua
        if "uni-app" not in device_ua.lower() or "html5plus/" not in device_ua.lower():
            user_agent += self.UA_SUFFIX
        headers = {
            "Connection": "keep-alive",
            "Accept": "*/*",
            "X-Requested-With": self.APP_CLIENT_ID,
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": user_agent,
            "platform": self._app_platform(device_ua),
        }

        auth_token = self._access_token
        if not auth_token:
            auth_token = self._cookie_token()

        if auth_token:
            headers["Authorization"] = auth_token
        else:
            logging.debug("既无 accessToken 也无 shiroCookie，将不设置 Authorization 请求头")

        # 与 App 一致把版本放在请求头，不附加到 query。
        headers["appVersion"] = self.app_version or self.NEW_APP_VERSION
        return headers

    # ------------------------------------------------------------------ 版本号

    def sync_app_version(self, force: bool = False) -> str:
        """从 /app/checkVersion 拉服务端最新版本号，只升不降。

        这是本项目的版本兼容策略；App 本身使用设备版本，并单独检查更新。
        有效结果按 BASE_URL 缓存到进程级，每个 ApiClient 实例登录时
        复用同一个结果，不会变成"每次登录多打一次 checkVersion"。
        同步失败不标记完成，后续可重试；force=True 可刷新进程缓存。
        """
        self.ensure_device_ua()
        cached = ApiClient._APP_VERSION_CACHE.get(self.BASE_URL)
        if cached and not force:
            if _version_key(cached) > _version_key(self.app_version or ""):
                self.app_version = cached
            self._app_version_synced = True
            return self.app_version

        if self._app_version_synced and not force:
            return self.app_version

        current = self.app_version or self.NEW_APP_VERSION
        payload = self._json(
            self._request(
                "GET",
                "/checkVersion",
                retries=3,
            )
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        latest = data.get("version") if isinstance(data, dict) else None
        if (
            isinstance(payload, dict)
            and payload.get("code") == 200
            and isinstance(latest, str)
            and re.fullmatch(r"\d+(?:\.\d+)*", latest)
        ):
            if _version_key(latest) > _version_key(current):
                self.app_version = latest
                logging.info(
                    f"appVersion 已从服务端同步：{current} -> {self.app_version}"
                )
            else:
                logging.debug(f"appVersion 保持 {current}（服务端最新：{latest}）")
            cached = ApiClient._APP_VERSION_CACHE.get(self.BASE_URL)
            if not cached or _version_key(self.app_version) > _version_key(cached):
                ApiClient._APP_VERSION_CACHE[self.BASE_URL] = self.app_version
            self._app_version_synced = True
        else:
            logging.debug(f"appVersion 同步失败，继续使用 {current}")
        return self.app_version

    # ------------------------------------------------------------------ 取消/重试

    def _request_cancelled_by_stop(self):
        execution_cancel_event = getattr(self, "_execution_cancel_event", None)
        return bool(
            execution_cancel_event is not None
            and execution_cancel_event.is_set()
        )

    def _wait_for_retry_or_cancel(self, seconds):
        execution_cancel_event = getattr(self, "_execution_cancel_event", None)
        if execution_cancel_event is not None:
            return bool(execution_cancel_event.wait(timeout=seconds))
        time.sleep(seconds)
        return self._request_cancelled_by_stop()

    # ------------------------------------------------------------------ 请求主流程

    def _request(
        self,
        method: str,
        url: str,
        data: dict | str | bytes | None = None,
        params: dict = None,
        is_post_str=False,
        force_content_type: str = None,
        retries: int = None,
        read_timeout: float | None = None,
    ) -> _main().requests.Response | None:
        """统一的网络请求方法（支持取消、按状态码区分是否重试）"""
        log_func = self.app.log_and_notify_frontend if hasattr(
            self.app, "log_and_notify_frontend") else self.app.api_bridge.log_and_notify_frontend
        is_offline = (
            self.app.is_offline_mode
            if hasattr(self.app, "is_offline_mode")
            else self.app.api_bridge.is_offline_mode
        )

        if self._request_cancelled_by_stop():
            log_func("操作已取消，跳过网络请求。")
            logging.debug(
                f"[网络请求] 请求已取消 --> 请求方法: {method.upper()}, 目标URL: {url}"
            )
            return None

        if is_offline:
            log_func("离线模式：网络请求已被禁用。")
            logging.debug(
                f"[网络请求] 离线模式已启用，已阻止网络请求 --> 请求方法: {method.upper()}, 目标URL: {url}"
            )
            return None

        retries = max(1, int(retries or self.MAX_RETRIES))
        read_timeout = self.READ_TIMEOUT if read_timeout is None else read_timeout
        full_url = self._api_url(url)
        params = self._clean_params(params)
        private = urlsplit(full_url).path.rstrip("/") == "/app/login"
        safe_request_url = _main()._redact_sensitive_log_text(scrub_login_query(full_url))
        log_value = (lambda _: "<redacted>") if private else _main()._redact_sensitive_log_value
        log_text = (lambda _: "<redacted>") if private else _main()._redact_sensitive_log_text

        logging.debug(
            f"[网络请求] 准备发起HTTP请求 --> 请求方法: {method.upper()}, "
            f"目标URL: {safe_request_url}, 重试上限: {retries}次, "
            f"连接超时: {self.CONNECT_TIMEOUT}秒, 读取超时: {read_timeout}秒, "
            f"请求数据: {log_value(data)}, "
            f"URL参数: {log_value(params)}"
        )

        for attempt in range(retries):
            if self._request_cancelled_by_stop():
                log_func("操作已取消，跳过网络请求。")
                return None
            try:
                headers = self._get_headers()

                if method.upper() == "POST":
                    if force_content_type:
                        headers["Content-Type"] = force_content_type
                    else:
                        headers["Content-Type"] = self.JSON_CONTENT_TYPE

                    # 字符串保持已有原始 body 契约；对象与 App 的 data:e 一样使用 JSON。
                    # is_post_str 保留给现有调用，不能让它把 dict 当字符串调用 encode。
                    if data is None:
                        post_data_bytes = b""
                    elif isinstance(data, bytes):
                        post_data_bytes = data
                    elif isinstance(data, str):
                        post_data_bytes = data.encode("utf-8")
                    elif headers["Content-Type"].startswith(self.FORM_CONTENT_TYPE):
                        post_data_bytes = urlencode(data).encode("utf-8")
                    else:
                        post_data_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")

                    logging.debug(
                        f"[网络请求] 发起POST请求 --> URL: {safe_request_url}, "
                        f"请求头: {_log_headers(headers)}, "
                        f"URL参数: {log_value(params)}, "
                        f"请求体字节长度: {len(post_data_bytes)} 字节, "
                        f"请求体: {log_text(post_data_bytes.decode('utf-8', errors='replace'))}"
                    )
                    resp = self.session.post(
                        full_url,
                        data=post_data_bytes,
                        params=params,
                        headers=headers,
                        timeout=(self.CONNECT_TIMEOUT, read_timeout),
                    )
                else:
                    logging.debug(
                        f"[网络请求] 发起GET请求 --> URL: {safe_request_url}, "
                        f"请求头: {_log_headers(headers)}, "
                        f"查询参数: {log_value(params or data)}"
                    )
                    resp = self.session.get(
                        full_url,
                        params=params if params is not None else data,
                        headers=headers,
                        timeout=(self.CONNECT_TIMEOUT, read_timeout),
                    )

                logging.debug(
                    f"[网络请求] 收到服务器响应 <-- 状态码: {resp.status_code} "
                    f"({resp.reason}), 来源URL: {safe_request_url}, "
                    f"响应头: {_log_headers(resp.headers)}, "
                    f"响应内容长度: {len(resp.content)} 字节, "
                    f"响应内容: {log_text(resp.text)}"
                )

                status = resp.status_code
                if 200 <= status < 300:
                    return resp
                if status not in self.RETRYABLE_STATUS:
                    # 401/403/400/404 这类是服务端的业务答复（body 是 JSON 信封），
                    # 交给 _json 解析出 message，不能抛异常也不能重试。
                    logging.warning(
                        f"[网络请求] 服务端返回不可重试状态码 {status}，直接把响应交回调用方"
                        f"（URL: {safe_request_url}）"
                    )
                    return resp

                log_func(
                    f"服务器返回错误 (第{attempt+1}次): {status}"
                )
                logging.error(
                    f"[网络请求] 可重试的HTTP状态码 --> 第{attempt+1}次/共{retries}次, "
                    f"请求方法: {method.upper()}, 目标URL: {safe_request_url}, "
                    f"HTTP状态码: {status}, 状态描述: {resp.reason}, "
                    f"响应内容: {log_text(resp.text)}",
                    exc_info=False,
                )
                if attempt + 1 == retries:
                    log_func(f"服务器错误: {status}")
                    logging.error(
                        f"[网络请求] HTTP请求最终失败 --> 已达到最大重试次数({retries}次), HTTP状态码: {status}"
                    )
                    return resp
                if self._wait_for_retry_or_cancel(self.RETRY_BACKOFF_SECONDS):
                    log_func("操作已取消，停止重试。")
                    return None
                continue

            except (
                _main().requests.exceptions.ConnectionError,
                _main().requests.exceptions.Timeout,
            ) as net_err:
                log_func(
                    f"网络连接失败 (第{attempt+1}/{retries}次)，"
                    f"异常类型: {type(net_err).__name__}"
                )
                logging.error(
                    f"[网络请求] 网络连接失败 --> 重试次数: 第{attempt+1}次/共{retries}次, "
                    f"请求方法: {method.upper()}, 目标URL: {safe_request_url}, "
                    f"错误类型: {type(net_err).__name__}, "
                    f"错误详情: {log_text(str(net_err))}",
                    exc_info=False,
                )
                if attempt + 1 == retries:
                    log_func(
                        f"网络连接最终失败: 无法连接到服务器 "
                        f"{_main()._redact_sensitive_log_text(self.BASE_URL)}"
                    )
                    logging.error(
                        f"[网络请求] 网络连接最终失败 --> 已达到最大重试次数({retries}次), "
                        f"目标服务器: {_main()._redact_sensitive_log_text(self.BASE_URL)}"
                    )
                    return None
                logging.info(
                    f"[网络请求] 准备重试 --> 等待{self.RETRY_BACKOFF_SECONDS}秒后进行第{attempt+2}次请求尝试"
                )
                if self._wait_for_retry_or_cancel(self.RETRY_BACKOFF_SECONDS):
                    log_func("操作已取消，停止重试。")
                    return None
                continue

            except _main().requests.exceptions.RequestException as req_err:
                log_func(
                    f"请求发生意外错误 (第{attempt+1}次)，"
                    f"异常类型: {type(req_err).__name__}"
                )
                logging.error(
                    f"[网络请求] 意外的请求异常 --> 重试次数: 第{attempt+1}次/共{retries}次, "
                    f"请求方法: {method.upper()}, 目标URL: {safe_request_url}, "
                    f"异常类型: {type(req_err).__name__}, "
                    f"异常详情: {log_text(str(req_err))}",
                    exc_info=not private,
                )
                if attempt + 1 == retries:
                    log_func(f"请求最终失败，异常类型: {type(req_err).__name__}")
                    logging.error(
                        f"[网络请求] 请求最终失败 --> 已达到最大重试次数({retries}次), "
                        f"所有重试均失败, 异常类型: {type(req_err).__name__}"
                    )
                    return None
                logging.info(
                    f"[网络请求] 准备重试 --> 等待{self.RETRY_BACKOFF_SECONDS}秒后进行第{attempt+2}次请求尝试"
                )
                if self._wait_for_retry_or_cancel(self.RETRY_BACKOFF_SECONDS):
                    log_func("操作已取消，停止重试。")
                    return None
                continue

        return None

    def _json(self, resp: _main().requests.Response | None, *, private=False) -> dict | None:
        """安全地将Response对象解析为JSON字典"""
        log_func = self.app.log_and_notify_frontend if hasattr(
            self.app, "log_and_notify_frontend") else self.app.api_bridge.log_and_notify_frontend
        if resp is None:
            logging.debug("[JSON解析] 响应对象为空，无法解析JSON")
            return None
        log_value = (lambda _: "<redacted>") if private else _main()._redact_sensitive_log_value
        log_text = (lambda _: "<redacted>") if private else _main()._redact_sensitive_log_text
        try:
            json_data = resp.json()
            logging.debug(
                f"[JSON解析] 成功解析JSON响应 --> 响应状态码: {resp.status_code}, "
                f"响应内容: {log_text(resp.text)}, "
                f"JSON数据: {log_value(json_data)}"
            )
            return json_data
        except ValueError as e:
            # requests>=2.27 的 JSONDecodeError 继承自 json.JSONDecodeError，但网关
            # 502/404 时返回的是 HTML，某些路径下抛的是普通 ValueError，一并兜住。
            log_func("服务器响应解析失败。")
            logging.error(
                f"[JSON解析] JSON解码失败 --> 响应状态码: {resp.status_code}, "
                f"响应内容类型: {resp.headers.get('Content-Type', '未知')}, "
                f"错误详情: {log_text(str(e))}, "
                f"响应内容长度: {len(resp.content)} 字节, "
                f"响应内容: {log_text(resp.text)}"
            )
            return None

    # ------------------------------------------------------------------ 账号/会话

    def login(self, username, password):
        """登录。

        App 的登录是 `POST /app/login?...&username=..&password=..`（参数在 query，body 为空），
        成功后从 `data.accessToken` / `data.refreshToken` 取令牌，之后所有请求把
        accessToken 原样塞进 `Authorization` 头（不加 Bearer 前缀）。
        """
        self.set_access_token(None)
        self.session.cookies.clear()
        self.sync_app_version()
        payload = self._json(
            self._request(
                "POST",
                "/login",
                data="",
                params={"username": username, "password": password},
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
                retries=3,
            ),
            private=True,
        )
        self._apply_login_tokens(payload)
        return payload

    def _apply_login_tokens(self, payload):
        """从登录响应里取 token 并落到 Authorization 会用到的地方。"""
        if not isinstance(payload, dict):
            return
        data = payload.get("data")
        if not isinstance(data, dict):
            return
        access_token = data.get("accessToken")
        if not access_token:
            return
        self._access_token = access_token
        logging.debug("学校登录响应已更新访问令牌")
        refresh_token = data.get("refreshToken")
        if refresh_token:
            self._refresh_token = refresh_token

    # ------------------------------------------------------------------ 跑腿（/run/errand/*）

    def get_run_list(self, user_id, offset=0, limit=10, is_finish=None):
        """跑腿列表。

        App 侧参数：userId / offset / limit / isFinish（isFinish 是页签类型，不传则由后端返回全部）。
        """
        return self._json(
            self._request(
                "POST",
                "/run/errand/getErrandList",
                data="",
                params={
                    "userId": user_id,
                    "offset": offset,
                    "limit": str(limit),
                    "isFinish": is_finish,
                },
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
            )
        )

    def get_run_details(self, errand_id, user_id, errand_schedule_id):
        """跑腿任务详情。

        注意：该接口受 appVersion 请求头的最低版本校验，版本过低会得到
        `{"errandDetail":{"startTime":"请更新APP后再进行跑步"}}` 这种"伪成功"响应。
        """
        return self._json(
            self._request(
                "POST",
                "/run/errand/getErrandDetail",
                data="",
                params={
                    "errandId": errand_id,
                    "userId": user_id,
                    "errandScheduleId": errand_schedule_id,
                },
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
            )
        )

    def get_run_history_list(self, user_id, errand_schedule_id, offset=0, limit=10):
        """跑腿轨迹记录列表（App 侧 limit 传字符串 "10"）。"""
        return self._json(
            self._request(
                "POST",
                "/run/errand/getUserErrandTrackRecord",
                data="",
                params={
                    "errandScheduleId": errand_schedule_id,
                    "userId": user_id,
                    "offset": offset,
                    "limit": str(limit),
                },
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
            )
        )

    def get_history_track_by_trid(self, trid):
        """按 trid 取历史轨迹点（App 用的是 POST + query，原实现误用 GET）。"""
        return self._json(
            self._request(
                "POST",
                "/run/errand/getTrackByTrid",
                data="",
                params={"trid": trid},
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
            )
        )

    def submit_run_track(self, payload_str: str | dict):
        """上报跑腿轨迹。

        接受 App 同形 JSON 对象或已有 JSON 字符串；使用 App 的 30 秒上传读取超时。
        """
        return self._json(
            self._request(
                "POST",
                "/run/errand/addErrandTrackByData",
                payload_str,
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
                read_timeout=self.TRACK_READ_TIMEOUT,
            )
        )

    def get_run_info_by_trid(self, trid):
        """按 trid 取轨迹记录（POST + query）。"""
        return self._json(
            self._request(
                "POST",
                "/run/errand/getTrackRecordByTrid",
                data="",
                params={"trid": trid},
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
            )
        )

    # ------------------------------------------------------------------ 通知

    def get_unread_notice_count(self):
        """获取未读通知数量 (POST, 空body, 无参数)"""
        return self._json(
            self._request(
                "POST",
                "/appNotice/unreadNumber",
                data="",
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
            )
        )

    def get_notice_list(self, offset=0, limit=10, type_id=0):
        """获取通知列表 (POST, 空body, query: offset/limit/typeId)"""
        return self._json(
            self._request(
                "POST",
                "/appNotice/noticeListByType",
                data="",
                params={"offset": offset, "limit": str(limit), "typeId": type_id},
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
            )
        )

    def mark_notice_as_read(self, notice_id):
        """将单个通知设为已读 (POST, 空body, query: noticeId)"""
        return self._json(
            self._request(
                "POST",
                "/appNotice/updateNoticeIsRead",
                data="",
                params={"noticeId": notice_id},
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
            )
        )

    # ------------------------------------------------------------------ 设备/UA

    @classmethod
    def generate_random_ua(cls):
        """生成一个随机的 Android User-Agent 字符串。

        优先使用 fake_useragent 的 Android 候选，否则使用内置 WebView 模板。
        """
        try:
            from fake_useragent import UserAgent

            ua = cls.normalize_device_ua(UserAgent(platforms=["mobile"], os=["Android"]).random)
            if _ANDROID_UA_RE.search(ua):
                return ua
        except Exception:
            pass

        # ── 方案二：内置安卓移动端 UA 模板（兜底）──────────────────────────
        build_texts = [
            "TD1A.221105.001.A1",
            "TP1A.221005.003",
            "SQ3A.220705.004",
            "SP2A.220505.008",
            "SQ1D.220205.004",
            "RP1A.201005.004",
            "TQ3A.230805.001",
            "UP1A.231005.007",
        ]
        phone_models = [
            "Xiaomi 12",
            "Xiaomi 13 Pro",
            "Redmi K60",
            "vivo X90",
            "iQOO 11",
            "OPPO Find X6 Pro",
            "Realme GT Neo5",
            "HONOR Magic5 Pro",
            "OnePlus 11",
            "Samsung Galaxy S23",
            "Pixel 7",
        ]
        android_version_map = {"U": 14, "T": 13, "S": 12, "R": 11, "Q": 10, "P": 9}
        random_build = random.choice(build_texts)
        build_letter = random_build.split(".")[0][0]
        android_version = android_version_map.get(build_letter, 13)
        chrome_major = random.randint(110, 124)
        chrome_minor = random.randint(4000, 6500)
        chrome_patch = random.randint(100, 250)
        chrome_version = f"Chrome/{chrome_major}.0.{chrome_minor}.{chrome_patch}"
        return (
            f"Mozilla/5.0 (Linux; Android {android_version}; "
            f"{random.choice(phone_models)} Build/{random_build}; wv) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Version/4.0 {chrome_version} Mobile Safari/537.36"
        )

    # ------------------------------------------------------------------ 签到（/run/attendanceRecord/*）

    def get_roll_call_info(self, roll_call_id, user_id):
        """获取指定签到活动的信息 (query: id/userId)。

        响应 data 形如 {rollCallInfo: {id, status, ...}, attendFinish: 0|1}。
        """
        return self._json(
            self._request(
                "POST",
                "/run/attendanceRecord/getAttendanceByRollCallId",
                data="",
                params={"id": roll_call_id, "userId": user_id},
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
            )
        )

    def submit_attendance(self, payload: dict):
        """提交签到记录。

        App 侧字段（全部在 query）：id / userId / name / rollCallId / coordinate /
        distance / status / reason / signCode。id 由调用方从 rollCallInfo.id 取得，
        不可用 rollCallId 猜测；coordinate 按 App 契约为纬度,经度。
        """
        payload = dict(payload or {})
        return self._json(
            self._request(
                "POST",
                "/run/attendanceRecord/addAttendance",
                data="",
                params=payload,
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
            )
        )

    def get_attendance_radius(self):
        """获取服务器设定的签到半径 (query: code=attendanceRadius&num=1)。

        响应 data.info 是 [{name:"radius", code:"<米数>"}]，App 用 name=="radius" 取值。
        """
        logging.debug("正在从服务器请求签到有效半径配置参数...")
        return self._json(
            self._request(
                "POST",
                "/appFind/getDictTips",
                data="",
                params={"code": "attendanceRadius", "num": "1"},
                is_post_str=True,
                force_content_type=self.JSON_CONTENT_TYPE,
            )
        )
