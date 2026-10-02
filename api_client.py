from __future__ import annotations

import json
import logging
import random
import threading
import time


def _main():
    import main
    return main


class ApiClient:
    """处理与后端服务器网络请求的类"""

    BASE_URL = "https://zslf.zsc.edu.cn"
    API_VERSION = 66    # 该变量已被弃用，不再使用
    NEW_APP_VERSION = "1.0.79"  # 新版本APP的版本号

    def __init__(self, owner_instance):
        self.session = _main().requests.Session()
        self.app = owner_instance
        logging.debug("ApiClient已初始化，创建了新的_main().requests.Session会话实例")

    def _get_headers(self) -> dict:
        """构建请求头，包含认证信息和设备信息"""
        headers = {
            "Connection": "keep-alive",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "com.zx.slm",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": self.app.device_ua + " uni-app Html5Plus/1.0 (Immersed/29.09091)",
            "platform":"android",
        }
        try:
            logging.debug(
                f"当前Session包含 {len(self.session.cookies)} 个 Cookie"
            )
        except _main().requests.cookies.CookieConflictError:
            logging.warning(
                "CookieConflictError 即使在使用 get_dict() 时也发送。获取原始cookie列表进行失败....")
        
        try:
            logging.debug(f"尝试获取shiroCookie。")
            auth_token = self.session.cookies.get_dict().get("shiroCookie")
        except _main().requests.cookies.CookieConflictError:
            logging.warning(
                "CookieConflictError 即使在使用 get_dict() 时也发生，尝试手动查找..."
            )
            auth_token = None
            for cookie in self.session.cookies:
                if cookie.name == "shiroCookie":
                    auth_token = cookie.value
                    logging.warning(
                        f"手动查找到 shiroCookie，长度: {len(auth_token)}"
                    )
                    break

        if auth_token:
            logging.debug(
                f"使用 shiroCookie 设置 Authorization 请求头，令牌长度: {len(auth_token)}"
            )
            headers["Authorization"] = auth_token
        else:
            logging.debug("未找到shiroCookie认证令牌，将不会设置Authorization请求头")
            
        # try:
        #     logging.debug(f"尝试获取JSESSIONID。")
        #     JSESSIONID = self.session.cookies.get_dict().get("JSESSIONID")
        # except _main().requests.cookies.CookieConflictError:
        #     logging.warning(
        #         "CookieConflictError 即使在使用 get_dict() 时也发生，尝试手动查找..."            )
        #     JSESSIONID = None
        #     for cookie in self.session.cookies:
        #         if cookie.name == "JSESSIONID":
        #             JSESSIONID = cookie.value
        #             logging.warning(
        #                 f"手动查找到 'JSESSIONID': {JSESSIONID[:10]}..."
        #             )
        #             break
        # if JSESSIONID:
        #     logging.debug(
        #         f"找到cookie['JSESSIONID']: {JSESSIONID}"
        #     )
        # else:
        #     logging.debug("未找到JSESSIONID cookie")
        
        # try:
        #     logging.debug(f"尝试获取SESSION。")
        #     SESSION= self.session.cookies.get_dict().get("SESSION")
        # except _main().requests.cookies.CookieConflictError:
        #     logging.warning(
        #         "CookieConflictError 即使在使用 get_dict() 时也发生，尝试手动查找..."            )
        #     SESSION = None
        #     for cookie in self.session.cookies:
        #         if cookie.name == "SESSION":
        #             SESSION = cookie.value
        #             logging.warning(
        #                 f"手动查找到 'SESSION': {SESSION[:10]}..."
        #             )
        #             break
        # if SESSION:
        #     logging.debug(
        #         f"找到cookie['SESSION']: {SESSION}"
        #     )
        # else:
        #     logging.debug("未找到SESSION cookie")
        # cookie_parts = []
        # if auth_token:
        #     cookie_parts.append(f"shiroCookie={auth_token}")
        # if JSESSIONID:
        #     cookie_parts.append(f"JSESSIONID={JSESSIONID}")
        # if SESSION:
        #     cookie_parts.append(f"SESSION={SESSION}")
        # headers["Cookie"] = "; ".join(cookie_parts) if cookie_parts else ""

        if self.NEW_APP_VERSION:
            headers["appVersion"] = self.NEW_APP_VERSION
        return headers

    def _request_cancelled_by_stop(self):
        execution_cancel_event = getattr(
            self, "_execution_cancel_event", None
        )
        return bool(
            execution_cancel_event is not None
            and execution_cancel_event.is_set()
        )

    def _wait_for_retry_or_cancel(self, seconds):
        execution_cancel_event = getattr(
            self, "_execution_cancel_event", None
        )
        if execution_cancel_event is not None:
            return bool(execution_cancel_event.wait(timeout=seconds))
        time.sleep(seconds)
        return self._request_cancelled_by_stop()

    def _request(
        self,
        method: str,
        url: str,
        data: dict = None,
        params: dict = None,
        is_post_str=False,
        force_content_type: str = None,
    ) -> _main().requests.Response | None:
        """统一的网络请求方法（增强：支持取消）"""

        log_func = self.app.log if hasattr(
            self.app, "log") else self.app.api_bridge.log
        is_offline = (
            self.app.is_offline_mode
            if hasattr(self.app, "is_offline_mode")
            else self.app.api_bridge.is_offline_mode
        )

        cancel_requested = self._request_cancelled_by_stop()

        if cancel_requested:
            log_func("操作已取消，跳过网络请求。")
            logging.debug(
                f"[网络请求] 请求已取消 --> 请求方法: {method.upper()}, 目标URL: {url}, 取消原因: 用户停止操作或系统取消标志已设置"
            )
            return None

        if is_offline:
            log_func("离线模式：网络请求已被禁用。")
            logging.debug(
                f"[网络请求] 离线模式已启用，已阻止网络请求 --> 请求方法: {method.upper()}, 目标URL: {url}, 说明: 离线模式下所有网络通信将被禁用"
            )
            return None

        retries = 10
        connect_timeout = 5
        read_timeout = 10

        request_field_names = (
            sorted(data.keys()) if isinstance(data, dict) else []
        )
        safe_request_url = _main()._redact_sensitive_log_text(url)

        logging.debug(
            f"[网络请求] 准备发起HTTP请求 --> 请求方法: {method.upper()}, "
            f"目标URL: {safe_request_url}, 重试次数配置: {retries}次, "
            f"连接超时: {connect_timeout}秒, 读取超时: {read_timeout}秒, "
            f"请求字段: {request_field_names}"
        )

        for attempt in range(retries):
            if self._request_cancelled_by_stop():
                log_func("操作已取消，跳过网络请求。")
                return None
            try:
                headers = self._get_headers()

                if method.upper() == "POST":
                    post_data_bytes = b""

                    if force_content_type:
                        headers["Content-Type"] = force_content_type
                    elif is_post_str:
                        headers["Content-Type"] = "application/x-www-form-urlencoded"
                    else:
                        headers["Content-Type"] = "application/x-www-form-urlencoded"

                    if is_post_str:
                        post_data_bytes = (data or "").encode("utf-8")
                    else:
                        post_data_bytes = _main().urllib.parse.urlencode(data or {}).encode(
                            "utf-8"
                        )
                    
                        
                        

                    logging.debug(
                        f"[网络请求] 发起POST请求 --> URL: {safe_request_url}, "
                        f"请求头字段: {sorted(headers.keys())}, "
                        f"请求体字节长度: {len(post_data_bytes)} 字节"
                    )
                    resp = self.session.post(
                        url,
                        data=post_data_bytes,
                        params=params,
                        headers=headers,
                        timeout=(connect_timeout, read_timeout),
                    )
                else:
                    resp = self.session.get(
                        url,
                        params=data,
                        headers=headers,
                        timeout=(connect_timeout, read_timeout),
                    )

                logging.debug(
                    f"[网络请求] 收到服务器响应 <-- 状态码: {resp.status_code} "
                    f"({resp.reason}), 来源URL: {safe_request_url}, "
                    f"响应头字段: {sorted(resp.headers.keys())}, "
                    f"响应内容长度: {len(resp.content)} 字节"
                )
                resp.raise_for_status()
                return resp

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
                    f"连接超时配置: {connect_timeout}秒, 读取超时配置: {read_timeout}秒",
                    exc_info=False,
                )
                if attempt + 1 == retries:
                    log_func(
                        f"网络连接最终失败: 无法连接到服务器 "
                        f"{_main()._redact_sensitive_log_text(self.BASE_URL)}"
                    )
                    logging.error(
                        f"[网络请求] 网络连接最终失败 --> 已达到最大重试次数({retries}次), "
                        f"目标服务器: {_main()._redact_sensitive_log_text(self.BASE_URL)}, 无法建立连接"
                    )
                    return None
                logging.info(
                    f"[网络请求] 准备重试 --> 等待1.5秒后进行第{attempt+2}次请求尝试"
                )
                if self._wait_for_retry_or_cancel(1.5):
                    log_func("操作已取消，停止重试。")
                    return None
                continue

            except _main().requests.exceptions.HTTPError as http_err:
                log_func(
                    f"服务器返回错误 (第{attempt+1}次): {http_err.response.status_code}"
                )
                logging.error(
                    f"[网络请求] HTTP错误 --> 重试次数: 第{attempt+1}次/共{retries}次, "
                    f"请求方法: {method.upper()}, 目标URL: {safe_request_url}, "
                    f"HTTP状态码: {http_err.response.status_code}, "
                    f"状态描述: {http_err.response.reason}, "
                    f"响应内容长度: {len(http_err.response.content)} 字节",
                    exc_info=False,
                )
                if attempt + 1 == retries:
                    log_func(f"服务器错误: {http_err.response.status_code}")
                    logging.error(
                        f"[网络请求] HTTP请求最终失败 --> 已达到最大重试次数({retries}次), HTTP状态码: {http_err.response.status_code}, 请求无法成功完成"
                    )
                    return None
                logging.info(
                    f"[网络请求] 准备重试 --> 等待1.5秒后进行第{attempt+2}次请求尝试"
                )
                if self._wait_for_retry_or_cancel(1.5):
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
                    f"异常类型: {type(req_err).__name__}, 完整堆栈信息如下:",
                    exc_info=True,
                )
                if attempt + 1 == retries:
                    log_func(
                        f"请求最终失败，异常类型: {type(req_err).__name__}"
                    )
                    logging.error(
                        f"[网络请求] 请求最终失败 --> 已达到最大重试次数({retries}次), "
                        f"所有重试均失败, 异常类型: {type(req_err).__name__}"
                    )
                    return None
                logging.info(
                    f"[网络请求] 准备重试 --> 等待1.5秒后进行第{attempt+2}次请求尝试"
                )
                if self._wait_for_retry_or_cancel(1.5):
                    log_func("操作已取消，停止重试。")
                    return None
                continue

        return None

    def _json(self, resp: _main().requests.Response | None) -> dict | None:
        """安全地将Response对象解析为JSON字典"""
        log_func = self.app.log if hasattr(
            self.app, "log") else self.app.api_bridge.log
        if resp:
            try:
                json_data = resp.json()
                logging.debug(
                    f"[JSON解析] 成功解析JSON响应 --> 响应状态码: {resp.status_code}, JSON数据字段: {list(json_data.keys()) if isinstance(json_data, dict) else type(json_data).__name__}"
                )
                return json_data
            except json.JSONDecodeError as e:
                log_func("服务器响应解析失败。")
                logging.error(
                    f"[JSON解析] JSON解码失败 --> 响应状态码: {resp.status_code}, "
                    f"响应内容类型: {resp.headers.get('Content-Type', '未知')}, "
                    f"解码错误位置: 第{e.lineno}行第{e.colno}列, "
                    f"响应内容长度: {len(resp.content)} 字节"
                )
                return None
        logging.debug(f"[JSON解析] 响应对象为空，无法解析JSON")
        return None

    def login(self, username, password):
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}/app/login",
                data={"username": username, "password": password},
            )
        )

    def get_run_list(self, user_id, offset=0):
        return self._json(
            self._request(
                "POST",
                # 原方案:合并isFinish=0和isFinish=1的接口，减少请求次数
                # 现方案:不传入isFinish参数，后端默认返回所有状态的跑腿列表，前端根据status字段进行分类统计和显示
                f"{self.BASE_URL}:9097/run/errand/getErrandList?userId={user_id}&offset={offset}&limit=10",
                # {
                #     "userId": user_id,
                #     "offset": offset,
                #     "limit": 10,
                #     "appVersion": self.API_VERSION,
                # },
                data="",
            )
        )

    def get_run_details(self, errand_id, user_id, errand_schedule_id):
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}:9097/run/errand/getErrandDetail?errandId={errand_id}&userId={user_id}&errandScheduleId={errand_schedule_id}",
                # {
                #     "errandId": errand_id,
                #     "userId": user_id,
                #     "errandScheduleId": errand_schedule_id,
                #     "appVersion": self.API_VERSION,
                # },
                data="",
            )
        )

    def get_run_history_list(self, user_id, errand_schedule_id):
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}:9097/run/errand/getUserErrandTrackRecord?errandScheduleId={errand_schedule_id}&userId={user_id}&offset=0&limit=20",
                # {
                #     "errandScheduleId": errand_schedule_id,
                #     "userId": user_id,
                #     "offset": 0,
                #     "limit": 20,
                #     "appVersion": self.API_VERSION,
                # },
                data="",
            )
        )

    def get_history_track_by_trid(self, trid):
        return self._json(
            self._request(
                "GET",
                f"{self.BASE_URL}:9097/run/errand/getTrackByTrid?trid={trid}",
                # {"trid": trid, "appVersion": self.API_VERSION},
                data="",
            )
        )

    def submit_run_track(self, payload_str):
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}:9097/run/errand/addErrandTrackByData",
                payload_str,
                is_post_str=True,
                force_content_type="application/json;charset=UTF-8",
            )
        )

    def get_run_info_by_trid(self, trid):
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}:9097/run/errand/getTrackRecordByTrid?trid={trid}",
                # {"trid": trid, "appVersion": self.API_VERSION},
                data="",
            )
        )

    def get_unread_notice_count(self):
        """获取未读通知数量 (POST, 空body, application/json)"""
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}/app/appNotice/unreadNumber",
                data="",
                is_post_str=True,
                force_content_type="application/json;charset=UTF-8",
            )
        )

    def get_notice_list(self, offset=0, limit=10, type_id=0):
        """获取通知列表 (POST, 空body, 带URL参数)"""
        params = {"offset": offset, "limit": limit, "typeId": type_id}
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}/app/appNotice/noticeListByType",
                data="",
                params=params,
                is_post_str=True,
                force_content_type="application/json;charset=UTF-8",
            )
        )

    def mark_notice_as_read(self, notice_id):
        """将单个通知设为已读 (POST, 空body, 带URL参数)"""
        params = {"noticeId": notice_id}
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}/app/appNotice/updateNoticeIsRead",
                data="",
                params=params,
                is_post_str=True,
                force_content_type="application/json;charset=UTF-8",
            )
        )

    @staticmethod
    def generate_random_ua():
        """生成一个随机的、仅限移动端设备的User-Agent字符串。
        
        优先使用 fake_useragent 库（如已安装）生成真实度更高的随机UA；
        若库不可用则回退到内置的安卓设备UA模板列表。
        """
        # ── 方案一：使用 fake_useragent 库（移动端限定）──────────────────────
        try:
            from fake_useragent import UserAgent
            ua_gen = _main().UserAgent(platforms=["mobile"])
            ua = ua_gen.random
            # 如果生成的 UA 不含 Mobile/Android 关键词，则触发回退
            if "Mobile" in ua or "Android" in ua:
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

    def get_roll_call_info(self, roll_call_id, user_id):
        """获取指定签到活动的信息"""
        params = {"id": roll_call_id, "userId": user_id,
                  "appVersion": self.API_VERSION}
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}:9097/run/attendanceRecord/getAttendanceByRollCallId",
                data="",
                params=params,
                is_post_str=True,
                force_content_type="application/json;charset=UTF-8",
            )
        )

    def submit_attendance(self, payload: dict):
        """提交签到记录"""
        payload["appVersion"] = self.API_VERSION
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}:9097/run/attendanceRecord/addAttendance",
                data=payload,
                is_post_str=False,
            )
        )

    def get_attendance_radius(self):
        """获取服务器设定的签到半径"""
        params = {"code": "attendanceRadius", "num": 1}
        logging.debug("正在从服务器请求签到有效半径配置参数...")
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}/app/appFind/getDictTips",
                data="",
                params=params,
                is_post_str=True,
                force_content_type="application/json;charset=UTF-8",
            )
        )


BACKGROUND_CACHE_TARGET_COUNT = 5
_BACKGROUND_SELECTION_STATE = {}
_BACKGROUND_SELECTION_LOCK = threading.Lock()
_THEME_BACKGROUND_REFRESH_LOCK = threading.Lock()
_THEME_BACKGROUND_REFRESH_IN_PROGRESS = False
_THEME_BACKGROUND_WARMUP_LOCK = threading.Lock()
_THEME_BACKGROUND_WARMUP_IN_PROGRESS = False


# ==============================================================================
# 3. 后端主逻辑 (Backend API Bridge)
#    作为Python后端和WebView前端之间的桥梁，处理所有业务逻辑。
# ==============================================================================


def _ensure_random_background_cache_count(cache_dir, api_key, image_type, target_count=5):
    logging.info(f"[主题背景] 确保 {image_type} 背景缓存数量至少为 {target_count} 张...")
    target_count = max(int(target_count or 0), 0)
    if target_count == 0:
        logging.info(f"[主题背景] 目标缓存数量为 0，跳过 {image_type} 背景缓存检查")
        return

    available_count = len(
        [
            file_name
            for file_name in os.listdir(cache_dir)
            if os.path.isfile(os.path.join(cache_dir, file_name))
            and file_name != "index.json"
            and file_name.startswith(f"{image_type}_")
        ]
    )
    missing_count = max(target_count - available_count, 0)
    logging.info(f"[主题背景] {image_type} 背景缓存缺失 {missing_count} 张")
    if missing_count == 0:
        return

    temp_api = Api(args)
    for _ in range(missing_count):
        try:
            logging.info(f"[主题背景] 正在拉取新的 {image_type} 随机背景图以补足缓存...")
            _fetch_random_background_image(cache_dir, api_key, image_type)
        except Exception as e:
            logging.warning(f"[主题背景] 补足 {image_type} 背景缓存失败: {e}")
            break
        logging.info(f"[主题背景] 已完成一次 {image_type} 背景图拉取尝试以补足缓存")


def _start_default_theme_background_cache_warmup():
    global _THEME_BACKGROUND_WARMUP_IN_PROGRESS
    with _THEME_BACKGROUND_WARMUP_LOCK:
        if _THEME_BACKGROUND_WARMUP_IN_PROGRESS:
            logging.info("[主题背景] 启动预热线程已在执行，跳过重复启动")
            return
        _THEME_BACKGROUND_WARMUP_IN_PROGRESS = True

    logging.info("[主题背景] 启动时预下载背景缓存线程正在启动...")

    def _worker():
        global _THEME_BACKGROUND_WARMUP_IN_PROGRESS
        try:
            logging.info("[主题背景] 启动时预下载背景缓存线程已启动")
            config = _read_config_ini(CONFIG_JSON_FILE) or _get_default_config()
            api_key = config.get("IP_Location", "uapipro_api_key", fallback="").strip()
            if not api_key:
                logging.info("[主题背景] 未配置 UapiPro API Key，跳过启动预下载缓存")
                return

            base_dir = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(base_dir, RANDOM_BACKGROUND_IMAGE_DIR)
            os.makedirs(cache_dir, exist_ok=True)

            index_data = _load_random_background_index(cache_dir)
            _save_random_background_index(cache_dir, index_data)

            for image_type in ("pc", "mb"):
                _ensure_random_background_cache_count(
                    cache_dir,
                    api_key,
                    image_type,
                    target_count=BACKGROUND_CACHE_TARGET_COUNT,
                )

            try:
                _cleanup_random_background_cache(cache_dir)
            except Exception as cleanup_error:
                logging.warning(f"[主题背景] 启动预热后清理缓存失败: {cleanup_error}")
        except Exception as e:
            logging.warning(f"[主题背景] 启动时预下载背景缓存失败: {e}", exc_info=True)
        finally:
            with _THEME_BACKGROUND_WARMUP_LOCK:
                _THEME_BACKGROUND_WARMUP_IN_PROGRESS = False

    threading.Thread(target=_worker, name="ThemeBackgroundWarmup", daemon=True).start()


def _fetch_random_background_image(cache_dir, api_key, image_type):
    url = f"https://uapis.cn/api/v1/random/image?category=acg&type={image_type}"
    headers = {"Authorization": f"Bearer {api_key}"}
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = _main().requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                extension = mimetypes.guess_extension(content_type) or ".jpg"
                if extension == ".jpe":
                    extension = ".jpg"
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]
                file_name = f"{image_type}_{timestamp}{extension}"
                file_path = os.path.join(cache_dir, file_name)
                with open(file_path, "wb") as f:
                    f.write(response.content)

                _mark_random_background_file_state(
                    cache_dir,
                    file_name,
                    image_type=image_type,
                    expired=False,
                    created_at=datetime.datetime.now().isoformat(timespec="seconds"),
                    last_used_at=None,
                    expired_at=None,
                )
                _cleanup_random_background_cache(cache_dir)
                return _build_theme_background_image_url(
                    f"{RANDOM_BACKGROUND_IMAGE_DIR}/{file_name}"
                )

            if response.status_code == 404:
                logging.warning(f"[主题背景] 未找到类型为 {image_type} 的随机背景图")
                return ""

            logging.warning(
                f"[主题背景] 拉取 {image_type} 随机背景图失败，状态码: {response.status_code}，第 {attempt} 次尝试"
            )
        except _main().requests.exceptions.RequestException as e:
            logging.warning(f"[主题背景] 拉取 {image_type} 随机背景图异常，第 {attempt} 次尝试: {e}")

    return ""


def _build_theme_background_image_url(relative_path):
    normalized_path = str(relative_path or "").replace("\\", "/").strip("/")
    if not normalized_path:
        return ""
    return f"/theme-assets/{normalized_path}"
