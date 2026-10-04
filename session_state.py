from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time


from main_runtime import _main


def _load_session_index():
    """加载会话索引文件"""
    try:
        if os.path.exists(_main().SESSION_INDEX_FILE):
            with open(_main().SESSION_INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.warning(f"加载会话索引失败: {e}")
    return {}


def _save_session_index(index):
    """保存会话索引文件"""
    try:
        with open(_main().SESSION_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"保存会话索引失败: {e}")


def save_session_state(session_id, api_instance, force_save=False):
    """
    将会话状态保存到文件（完整版：保存所有应用状态包括离线任务数据）

    Args:
        session_id: 会话UUID
        api_instance: Api实例
        force_save: 强制保存，即使距离上次保存时间很短
    """
    session_id = _main().normalize_session_uuid(session_id)
    if not session_id:
        logging.warning(f"拒绝保存会话：无效的 session_id: '{session_id}'")
        return
    if not getattr(api_instance, "_is_persistent_session", True):
        logging.debug(f"跳过保存认证上下文：{session_id}")
        return
    try:
        session_hash = hashlib.sha256(session_id.encode()).hexdigest()
        session_file = os.path.join(
            _main().SESSION_STORAGE_DIR, f"{session_hash}.json")
        with _main().session_file_locks_lock:
            if session_hash not in _main().session_file_locks:
                _main().session_file_locks[session_hash] = threading.Lock()
            file_lock = _main().session_file_locks[session_hash]
        with file_lock:
            if not force_save:
                last_save_time = getattr(
                    api_instance, "_last_session_save_time", 0)
                if time.time() - last_save_time < 2.0:
                    return
            api_instance._last_session_save_time = time.time()
            session_login_success = _main().get_business_session_login_success(api_instance)
            state = {
                "session_id": session_id,
                "school_account_logged_in": session_login_success,
                "login_success": session_login_success,
                "user_info": getattr(api_instance, "user_info", None),
                "created_at": getattr(api_instance, "_session_created_at", time.time()),
                "last_accessed": time.time(),
                "last_saved": time.time(),
            }
            if hasattr(api_instance, "auth_username"):
                state["auth_username"] = api_instance.auth_username
                state["auth_group"] = getattr(
                    api_instance, "auth_group", "guest")
                state["is_guest"] = getattr(api_instance, "is_guest", False)
                state["is_authenticated"] = getattr(
                    api_instance, "is_authenticated", False
                )
            if hasattr(api_instance, "params"):
                params_to_save = api_instance.params.copy()
                if "amap_js_key" in params_to_save:
                    del params_to_save["amap_js_key"]

                state["params"] = params_to_save
            if hasattr(api_instance, "device_ua"):
                state["device_ua"] = api_instance.device_ua
            if hasattr(api_instance, "cached_notifications"):
                state["cached_notifications"] = api_instance.cached_notifications
            if hasattr(api_instance, "user_data") and api_instance.user_data:
                user_data = api_instance.user_data
                state["user_data"] = {
                    "name": getattr(user_data, "name", ""),
                    "phone": getattr(user_data, "phone", ""),
                    "student_id": getattr(user_data, "student_id", ""),
                    "id": getattr(user_data, "id", ""),
                    "username": getattr(user_data, "username", ""),
                    "gender": getattr(user_data, "gender", ""),
                    "school_name": getattr(user_data, "school_name", ""),
                }
            if hasattr(api_instance, "current_run_idx"):
                state["current_run_idx"] = api_instance.current_run_idx
            if hasattr(api_instance, "all_run_data") and api_instance.all_run_data:
                loaded_tasks = []
                for run_data in api_instance.all_run_data:
                    task_dict = {
                        "run_name": getattr(run_data, "run_name", ""),
                        "errand_id": getattr(run_data, "errand_id", ""),
                        "errand_schedule": getattr(run_data, "errand_schedule", ""),
                        "status": getattr(run_data, "status", 0),
                        "start_time": getattr(run_data, "start_time", ""),
                        "end_time": getattr(run_data, "end_time", ""),
                        "upload_time": getattr(run_data, "upload_time", ""),
                        "total_run_time_s": getattr(run_data, "total_run_time_s", 0.0),
                        "total_run_distance_m": getattr(
                            run_data, "total_run_distance_m", 0.0
                        ),
                        "target_points": getattr(run_data, "target_points", []),
                        "target_point_names": getattr(
                            run_data, "target_point_names", ""
                        ),
                        "recommended_coords": getattr(
                            run_data, "recommended_coords", []
                        ),
                        "draft_coords": getattr(run_data, "draft_coords", []),
                        "run_coords": getattr(run_data, "run_coords", []),
                        "target_sequence": getattr(run_data, "target_sequence", 0),
                        "is_in_target_zone": getattr(
                            run_data, "is_in_target_zone", False
                        ),
                        "trid": getattr(run_data, "trid", ""),
                        "details_fetched": getattr(run_data, "details_fetched", False),
                        "distance_covered_m": getattr(
                            run_data, "distance_covered_m", 0.0
                        ),
                    }
                    loaded_tasks.append(task_dict)
                state["loaded_tasks"] = loaded_tasks
            state["is_offline_mode"] = getattr(
                api_instance, "is_offline_mode", False)

            if (
                hasattr(api_instance, "api_client")
                and api_instance.api_client.session.cookies
            ):
                try:
                    state["api_cookies"] = _main().requests.utils.dict_from_cookiejar(
                        api_instance.api_client.session.cookies
                    )
                    logging.debug(
                        f"会话保存: 正在保存 {len(state['api_cookies'])} 个 API Cookies..."
                    )
                except Exception as e:
                    logging.warning(f"会话保存: 保存 API Cookies 失败: {e}")
            state["is_multi_account_mode"] = getattr(
                api_instance, "is_multi_account_mode", False
            )
            if getattr(api_instance, "is_multi_account_mode", False):
                if hasattr(api_instance, "global_params"):
                    global_params_to_save = api_instance.global_params.copy()
                    if "amap_js_key" in global_params_to_save:
                        del global_params_to_save["amap_js_key"]
                    state["multi_global_params"] = global_params_to_save
                else:
                    state["multi_global_params"] = {}
                multi_account_states = {}
                accounts = getattr(api_instance, "accounts", {})
                for username, account_session in accounts.items():
                    try:
                        account_state = {
                            "status_text": getattr(
                                account_session, "status_text", "待命"
                            ),
                            "is_first_login_verified": getattr(
                                account_session, "is_first_login_verified", False
                            ),
                            "school_account_logged_in": _main().is_multi_account_logged_in(
                                account_session
                            ),
                            "summary": getattr(account_session, "summary", {}),
                            "progress_pct": getattr(
                                account_session, "progress_pct", 0
                            ),
                            "progress_text": getattr(
                                account_session, "progress_text", ""
                            ),
                            "progress_extra": getattr(
                                account_session, "progress_extra", ""
                            ),
                            "current_position": getattr(
                                account_session, "current_position", None
                            ),
                        }
                        if hasattr(account_session, "params"):
                            account_state["params"] = account_session.params

                        multi_account_states[username] = account_state

                    except Exception as e:
                        logging.warning(f"保存账号 {username} 状态时出错: {e}")
                        continue

                state["multi_account_states"] = multi_account_states
                state["multi_account_usernames"] = list(
                    getattr(api_instance, "accounts", {}).keys()
                )
                if hasattr(api_instance, "global_params"):
                    global_params_to_save = api_instance.global_params.copy()
                    if "amap_js_key" in global_params_to_save:
                        del global_params_to_save["amap_js_key"]
                    state["multi_global_params"] = global_params_to_save
                else:
                    state["multi_global_params"] = {}
                multi_account_states = {}
                accounts = getattr(api_instance, "accounts", {})
                for username, account_session in accounts.items():
                    try:
                        account_state = {
                            "status_text": getattr(
                                account_session, "status_text", "待命"
                            ),
                            "school_account_logged_in": _main().is_multi_account_logged_in(
                                account_session
                            ),
                            "summary": getattr(account_session, "summary", {}),
                            "progress_pct": getattr(
                                account_session, "progress_pct", 0
                            ),
                            "progress_text": getattr(
                                account_session, "progress_text", ""
                            ),
                            "progress_extra": getattr(
                                account_session, "progress_extra", ""
                            ),
                            "current_position": getattr(
                                account_session, "current_position", None
                            ),
                        }
                        if hasattr(account_session, "params"):
                            account_state["params"] = account_session.params

                        multi_account_states[username] = account_state

                    except Exception as e:
                        logging.warning(f"保存账号 {username} 状态时出错: {e}")
                        continue

                state["multi_account_states"] = multi_account_states
                state["multi_dashboard_info"] = {
                    "total_accounts": len(accounts),
                    "running_accounts": sum(
                        1
                        for acc in accounts.values()
                        if getattr(acc, "is_running", False)
                    ),
                    "logged_in_accounts": sum(
                        1
                        for acc in accounts.values()
                        if _main().is_multi_account_logged_in(acc)
                    ),
                    "total_tasks": sum(
                        len(getattr(acc, "all_run_data", []))
                        for acc in accounts.values()
                    ),
                    "completed_tasks": sum(
                        sum(
                            1
                            for task in getattr(acc, "all_run_data", [])
                            if getattr(task, "status", 0) == 1
                        )
                        for acc in accounts.values()
                    ),
                }
            if not getattr(api_instance, "is_multi_account_mode", False):
                all_tasks = getattr(api_instance, "all_run_data", [])
                state["dashboard_info"] = {
                    "total_tasks": len(all_tasks),
                    "completed_tasks": sum(
                        1 for task in all_tasks if getattr(task, "status", 0) == 1
                    ),
                    "pending_tasks": sum(
                        1 for task in all_tasks if getattr(task, "status", 0) == 0
                    ),
                    "selected_task_index": getattr(api_instance, "current_run_idx", -1),
                    "is_offline_mode": getattr(api_instance, "is_offline_mode", False),
                    "school_account_logged_in": getattr(
                        api_instance, "login_success", False
                    ),
                }
                if (
                    hasattr(api_instance, "current_run_idx")
                    and api_instance.current_run_idx >= 0
                ):
                    if hasattr(
                        api_instance, "all_run_data"
                    ) and api_instance.current_run_idx < len(api_instance.all_run_data):
                        current_task = api_instance.all_run_data[
                            api_instance.current_run_idx
                        ]
                        state["dashboard_info"]["current_task"] = {
                            "run_name": getattr(current_task, "run_name", ""),
                            "status": getattr(current_task, "status", 0),
                            "total_distance": getattr(
                                current_task, "total_run_distance_m", 0.0
                            ),
                            "total_time": getattr(
                                current_task, "total_run_time_s", 0.0
                            ),
                            "has_path": len(getattr(current_task, "run_coords", []))
                            > 0,
                        }
            if hasattr(api_instance, "stop_run_flag"):
                state["stop_run_flag_set"] = api_instance.stop_run_flag.is_set()
            if hasattr(api_instance, "ui_state"):
                state["ui_state"] = api_instance.ui_state
            if hasattr(api_instance, "user_settings"):
                state["user_settings"] = api_instance.user_settings
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            index = _main()._load_session_index()
            index[session_id] = session_hash
            _main()._save_session_index(index)

            tasks_count = len(state.get("loaded_tasks", []))
            logging.debug(
                f"会话状态已保存: {session_id} (任务数:{tasks_count}, 选中索引:{state.get('current_run_idx', -1)})"
            )
    except Exception as e:
        logging.error(f"保存会话状态失败: {e}", exc_info=True)


def load_session_state(session_id):
    """从文件加载会话状态"""
    try:
        index = _main()._load_session_index()
        if session_id in index:
            session_hash = index[session_id]
            logging.debug(
                f"从索引找到会话哈希: {session_id[:32]}... -> {session_hash[:16]}..."
            )
        else:
            session_hash = hashlib.sha256(session_id.encode()).hexdigest()
            logging.debug(
                f"索引中未找到，计算会话哈希: {session_id[:32]}... -> {session_hash[:16]}..."
            )

        session_file = os.path.join(
            _main().SESSION_STORAGE_DIR, f"{session_hash}.json")

        if os.path.exists(session_file):
            with _main().session_file_locks_lock:
                if session_hash not in _main().session_file_locks:
                    _main().session_file_locks[session_hash] = threading.Lock()
                file_lock = _main().session_file_locks[session_hash]
            with file_lock:
                with open(session_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
            if state.get("session_id") == session_id:
                last_accessed = state.get("last_accessed", 0)
                session_age_days = (time.time() - last_accessed) / 86400
                max_age_days = 7

                if session_age_days > max_age_days:
                    logging.warning(
                        f"[会话管理] 会话已过期 --> 会话ID: {session_id[:32]}..., 最后访问: {session_age_days:.1f}天前, 最大保留期限: {max_age_days}天, 将被自动清理"
                    )
                    try:
                        os.remove(session_file)
                        logging.info(f"[会话管理] 已删除过期会话文件: {session_file}")
                    except Exception as remove_err:
                        logging.error(f"[会话管理] 删除过期会话文件失败: {remove_err}")
                    return None

                tasks_count = len(state.get("loaded_tasks", []))
                logging.info(
                    f"[会话管理] 从文件加载会话 --> 会话ID: {session_id[:32]}..., 登录状态: {state.get('login_success')}, 任务数: {tasks_count}, 最后访问: {session_age_days:.1f}天前"
                )
                return state
            else:
                logging.warning(f"[会话管理] 会话文件UUID不匹配，忽略")
    except Exception as e:
        logging.error(f"[会话管理] 加载会话状态失败 --> 错误: {e}", exc_info=True)
    return None


def cleanup_expired_sessions():
    """
    清理过期的会话文件（7天未访问）

    此函数遍历所有会话文件，删除超过7天未访问的会话。
    """
    try:
        if not os.path.exists(_main().SESSION_STORAGE_DIR):
            return

        max_age_days = 7
        max_age_seconds = max_age_days * 86400
        current_time = time.time()
        cleaned_count = 0
        error_count = 0

        logging.info(f"[会话清理] 开始清理过期会话 --> 最大保留期限: {max_age_days}天")

        for filename in os.listdir(_main().SESSION_STORAGE_DIR):
            if not filename.endswith(".json") or filename == "_index.json":
                continue

            session_file = os.path.join(_main().SESSION_STORAGE_DIR, filename)

            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    state = json.load(f)

                last_accessed = state.get("last_accessed", 0)
                if current_time - last_accessed > max_age_seconds:
                    session_id = state.get("session_id", "unknown")[:32]
                    age_days = (current_time - last_accessed) / 86400

                    os.remove(session_file)
                    cleaned_count += 1
                    logging.info(
                        f"[会话清理] 已删除过期会话 --> 会话ID: {session_id}..., 文件: {filename}, 年龄: {age_days:.1f}天"
                    )

            except Exception as e:
                error_count += 1
                logging.debug(
                    f"[会话清理] 处理会话文件失败 --> 文件: {filename}, 错误: {e}"
                )

        logging.info(
            f"[会话清理] 清理完成 --> 已删除: {cleaned_count}个过期会话, 错误: {error_count}个"
        )

    except Exception as e:
        logging.error(f"[会话清理] 清理过期会话失败 --> 错误: {e}", exc_info=True)


def restore_session_to_api_instance(api_instance, state):
    """
    将保存的会话状态恢复到Api实例
    """
    try:
        if "auth_username" in state:
            api_instance.auth_username = state["auth_username"]
            api_instance.auth_group = state.get("auth_group", "guest")
            api_instance.is_guest = state.get("is_guest", False)
            api_instance.is_authenticated = state.get(
                "is_authenticated", False)
        if "login_success" in state:
            api_instance.login_success = state["login_success"]
        if "user_info" in state:
            api_instance.user_info = state["user_info"]
        if "params" in state:
            saved_params = state["params"]
            if isinstance(saved_params, dict):
                api_instance.params.update(saved_params)
        if "device_ua" in state:
            api_instance.device_ua = state["device_ua"]
        if "cached_notifications" in state:
            api_instance.cached_notifications = state["cached_notifications"]
        if "user_data" in state:
            user_data_dict = state["user_data"]
            api_instance.user_data.name = user_data_dict.get("name", "")
            api_instance.user_data.phone = user_data_dict.get("phone", "")
            api_instance.user_data.student_id = user_data_dict.get(
                "student_id", "")
            api_instance.user_data.id = user_data_dict.get("id", "")
            api_instance.user_data.username = user_data_dict.get(
                "username", "")
            api_instance.user_data.gender = user_data_dict.get("gender", "")
            api_instance.user_data.school_name = user_data_dict.get(
                "school_name", "")
        if "loaded_tasks" in state:
            api_instance.all_run_data = []
            for task_dict in state["loaded_tasks"]:
                run_data = _main().RunData()
                run_data.run_name = task_dict.get("run_name", "")
                run_data.errand_id = task_dict.get("errand_id", "")
                run_data.errand_schedule = task_dict.get("errand_schedule", "")
                run_data.status = task_dict.get("status", 0)
                run_data.start_time = task_dict.get("start_time", "")
                run_data.end_time = task_dict.get("end_time", "")
                run_data.upload_time = task_dict.get("upload_time", "")
                run_data.total_run_time_s = task_dict.get(
                    "total_run_time_s", 0.0)
                run_data.total_run_distance_m = task_dict.get(
                    "total_run_distance_m", 0.0
                )
                run_data.target_points = [
                    tuple(p) for p in task_dict.get("target_points", [])
                ]
                run_data.target_point_names = task_dict.get(
                    "target_point_names", "")
                run_data.recommended_coords = [
                    tuple(p) for p in task_dict.get("recommended_coords", [])
                ]
                run_data.draft_coords = [
                    tuple(p) for p in task_dict.get("draft_coords", [])
                ]
                run_data.run_coords = [
                    tuple(p) for p in task_dict.get("run_coords", [])
                ]
                run_data.target_sequence = task_dict.get("target_sequence", 0)
                run_data.is_in_target_zone = task_dict.get(
                    "is_in_target_zone", False)
                run_data.trid = task_dict.get("trid", "")
                run_data.details_fetched = task_dict.get(
                    "details_fetched", False)
                run_data.distance_covered_m = task_dict.get(
                    "distance_covered_m", 0.0)

                api_instance.all_run_data.append(run_data)
        if "current_run_idx" in state:
            api_instance.current_run_idx = state["current_run_idx"]
        if "is_offline_mode" in state:
            api_instance.is_offline_mode = state["is_offline_mode"]
        if "is_multi_account_mode" in state:
            api_instance.is_multi_account_mode = state["is_multi_account_mode"]
            if state["is_multi_account_mode"]:
                if "multi_global_params" in state:
                    saved_global_params = state["multi_global_params"]
                    if isinstance(saved_global_params, dict):
                        api_instance.global_params.update(saved_global_params)
                api_instance.global_params.setdefault(
                    "auto_attendance_stop_after_success", True
                )
                api_instance.global_params.setdefault(
                    "auto_attendance_success_limit", 1
                )
                if "multi_account_states" in state:
                    multi_account_states = state["multi_account_states"]

                    logging.info(
                        f"会话恢复：找到 {len(multi_account_states)} 个账号状态，正在重建..."
                    )

                    for username, account_state in multi_account_states.items():
                        if username not in api_instance.accounts:
                            try:
                                # 从新路径加载密码
                                auth_username = getattr(
                                    api_instance, "auth_username", None)
                                loaded_password = None
                                if auth_username:
                                    accounts = api_instance._load_user_school_accounts(
                                        auth_username)
                                    account_info = accounts.get(username)
                                    if account_info:
                                        loaded_password = account_info.get(
                                            "password")
                                loaded_tag = api_instance._load_account_tag(
                                    username)
                                acc = _main().AccountSession(
                                    username=username,
                                    password=loaded_password or "",
                                    api_bridge=api_instance,
                                    tag=loaded_tag or "",
                                )
                                acc.status_text = account_state.get(
                                    "status_text", "待命"
                                )
                                saved_params = account_state.get("params", {})
                                if isinstance(saved_params, dict):
                                    acc.params.update(saved_params)
                                acc.summary = account_state.get(
                                    "summary",
                                    {
                                        "total": 0,
                                        "completed": 0,
                                        "not_started": 0,
                                        "executable": 0,
                                        "expired": 0,
                                        "att_pending": 0,
                                        "att_completed": 0,
                                        "att_expired": 0,
                                    },
                                )
                                acc.progress_pct = account_state.get(
                                    "progress_pct", 0
                                )
                                acc.progress_text = account_state.get(
                                    "progress_text", ""
                                )
                                acc.progress_extra = account_state.get(
                                    "progress_extra", ""
                                )
                                acc.current_position = account_state.get(
                                    "current_position"
                                )
                                school_account_logged_in = bool(
                                    account_state.get(
                                        "school_account_logged_in", False
                                    )
                                )
                                acc.is_first_login_verified = bool(
                                    account_state.get(
                                        "is_first_login_verified", False
                                    )
                                ) or school_account_logged_in
                                acc.login_success = school_account_logged_in
                                api_instance.accounts[username] = acc
                                logging.info(
                                    f"会话恢复：成功重建账号 {username} (密码从 .ini 加载)"
                                )

                            except Exception as e:
                                logging.error(
                                    f"会话恢复：重建账号 {username} 失败: {e}",
                                    exc_info=True,
                                )
                                continue

                if len(api_instance.accounts) > 0:
                    logging.info(
                        f"会话恢复：正在为 {len(api_instance.accounts)} 个已恢复的账号启动后台刷新..."
                    )
                    for acc_session in api_instance.accounts.values():
                        try:
                            threading.Thread(
                                target=api_instance._multi_refresh_worker,
                                args=(
                                    acc_session,
                                    False,
                                ),
                                daemon=True,
                                name=f"RestoreRefresh-{acc_session.username}",
                            ).start()
                        except Exception as thread_err:
                            logging.error(
                                f"会话恢复：启动账号 {acc_session.username} 的刷新线程失败: {thread_err}",
                                exc_info=True,
                            )
                logging.info(
                    f"会话恢复：检测到多账号模式，已恢复 {len(api_instance.accounts)} 个账号"
                )
        if "stop_run_flag_set" in state:
            if state["stop_run_flag_set"]:
                api_instance.stop_run_flag.set()
            else:
                api_instance.stop_run_flag.clear()
        if "ui_state" in state:
            api_instance.ui_state = state["ui_state"]
        if "user_settings" in state:
            api_instance.user_settings = state["user_settings"]
        if "api_cookies" in state and state["api_cookies"]:
            try:
                cookies_dict = state["api_cookies"]
                api_instance.api_client.session.cookies = (
                    _main().requests.utils.cookiejar_from_dict(cookies_dict)
                )
                logging.info(
                    f"会话恢复: 成功恢复 {len(cookies_dict)} 个 API Cookies (shiroCookie等)。"
                )
            except Exception as e:
                logging.warning(f"会话恢复: 恢复 API Cookies 失败: {e}")
        # 恢复单账号自动签到线程（旧版本，已废弃但保留兼容）
        # 新版本使用 _account_refresh_worker，但这里保留以防某些场景仍在使用
        if not api_instance.is_multi_account_mode:
            # 检查该用户是否启用了自动签到（从JSON配置读取）
            school_username = api_instance.user_data.username if api_instance.user_data and api_instance.user_data.username else None
            if school_username and _main()._is_auto_attendance_enabled(school_username):
                api_instance.stop_auto_refresh.clear()
                api_instance.auto_refresh_thread = threading.Thread(
                    target=api_instance._auto_refresh_worker, daemon=True
                )
                api_instance.auto_refresh_thread.start()
                logging.info(f"会话恢复: 已重启单账号自动签到后台线程（旧版本）")

        # 恢复多账号自动签到线程（旧版本，已废弃但保留兼容）
        # 新版本为每个账号单独创建刷新线程
        if api_instance.is_multi_account_mode:
            # 检查是否有任何账号启用了自动签到
            has_auto_attendance = False
            for username, acc in api_instance.accounts.items():
                if acc.user_data and acc.user_data.username:
                    if _main()._is_auto_attendance_enabled(acc.user_data.username):
                        has_auto_attendance = True
                        break

            if has_auto_attendance:
                api_instance.stop_multi_auto_refresh.clear()
            api_instance.multi_auto_refresh_thread = threading.Thread(
                target=api_instance._multi_auto_attendance_worker, daemon=True
            )
            api_instance.multi_auto_refresh_thread.start()
            logging.info(f"会话恢复: 已重启多账号自动签到后台线程")

        logging.info(
            f"会话状态恢复完成: 任务数={len(api_instance.all_run_data)}, 选中索引={api_instance.current_run_idx}, 多账号模式={api_instance.is_multi_account_mode}"
        )

    except Exception as e:
        logging.error(f"恢复会话状态失败: {e}", exc_info=True)
