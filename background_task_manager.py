from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import threading
import time


def _main():
    import main
    return main


class BackgroundTaskManager:
    """管理服务器端后台任务执行"""

    def __init__(self):
        self.tasks = {}
        self.execution_tokens = {}
        self.lock = threading.Lock()
        self.task_storage_dir = os.path.join(
            os.path.dirname(__file__), "background_tasks"
        )
        if not os.path.exists(self.task_storage_dir):
            os.makedirs(self.task_storage_dir)
        logging.info("BackgroundTaskManager initialized")

    def _get_task_file_path(self, session_id):
        """获取任务状态文件路径"""
        task_hash = hashlib.sha256(session_id.encode()).hexdigest()
        return os.path.join(self.task_storage_dir, f"{task_hash}.json")

    def save_task_state(self, session_id, task_state):
        """保存任务状态到文件"""
        task_file = self._get_task_file_path(session_id)
        try:
            with open(task_file, "w", encoding="utf-8") as f:
                json.dump(task_state, f, indent=2, ensure_ascii=False)
            logging.debug(f"后台任务状态已保存，会话ID: {session_id}")
            # 同步更新 background_tasks/_index.json 索引
            self._update_tasks_index(session_id, task_state, action="save")
        except Exception as e:
            logging.error(f"保存后台任务状态失败: {e}")

    def _update_tasks_index(self, session_id, task_state, action="save"):
        """
        更新 background_tasks/_index.json 索引文件。
        
        参数:
            session_id: 会话ID
            task_state: 任务状态数据
            action: "save" 或 "remove"
        """
        try:
            index_path = os.path.join(self.task_storage_dir, "_index.json")
            task_hash = hashlib.sha256(session_id.encode()).hexdigest()
            
            # 读取现有索引
            if os.path.exists(index_path):
                try:
                    with open(index_path, "r", encoding="utf-8") as f:
                        index_data = json.load(f)
                except Exception:
                    index_data = {"tasks": {}}
            else:
                index_data = {"tasks": {}}
            
            if "tasks" not in index_data:
                index_data["tasks"] = {}
            
            if action == "save":
                # 添加或更新任务条目
                index_data["tasks"][task_hash] = {
                    "session_id": session_id,
                    "created_at": task_state.get("created_at", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
                    "file": f"{task_hash}.json"
                }
            elif action == "remove":
                # 从索引中移除任务
                if task_hash in index_data["tasks"]:
                    del index_data["tasks"][task_hash]
            
            # 更新时间戳
            index_data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # 写入索引文件
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.warning(f"[任务索引] 更新索引失败: {e}")

    def load_task_state(self, session_id):
        """从文件加载任务状态"""
        task_file = self._get_task_file_path(session_id)
        if not os.path.exists(task_file):
            return None
        try:
            with open(task_file, "r", encoding="utf-8") as f:
                task_state = json.load(f)
            logging.debug(f"后台任务状态已加载，会话ID: {session_id}")
            return task_state
        except Exception as e:
            logging.error(f"加载后台任务状态失败: {e}")
            return None

    def start_background_task(
        self, session_id, api_instance, task_indices, auto_generate=False
    ):
        """
        启动后台任务执行

        功能说明：
            在启动任务前，会检查当前用户的所有学校账号是否存在欠费。
            如果任何账号存在欠费（overdue_count > 0），则拒绝启动任务。

        参数：
            session_id: 会话ID
            api_instance: API实例，包含用户信息
            task_indices: 要执行的任务索引列表
            auto_generate: 是否自动生成路径

        返回：
            包含 success 和 message 的字典
            如果存在欠费，还会包含 error_code 和 overdue_accounts
        """
        # ========== 欠费检查（前后端双重校验中的后端校验） ==========
        # - 单账号模式：仅检查当前学校账号
        # - 多账号模式：检查当前多账号列表中的所有学校账号
        config = _main()._read_config_ini()
        require_payment = True
        if config is not None:
            require_payment = config.getboolean(
                "Payment_Settings", "require_payment", fallback=True
            )

        auth_username = getattr(api_instance, "auth_username", None)
        if require_payment and auth_username:
            overdue_accounts_list = []
            target_school_usernames = []

            try:
                if getattr(api_instance, "is_multi_account_mode", False):
                    target_school_usernames = list(
                        (getattr(api_instance, "accounts", {}) or {}).keys()
                    )
                else:
                    current_user_info = getattr(api_instance, "user_info", {}) or {}
                    current_school_username = str(
                        current_user_info.get("student_id", "") or ""
                    ).strip()
                    if current_school_username:
                        target_school_usernames = [current_school_username]
            except Exception as e:
                logging.warning(f"[欠费检查] 获取目标账号列表失败: {e}")
                target_school_usernames = []

            overdue_accounts_list = _main()._collect_overdue_accounts_from_billing(
                target_school_usernames
            )

            if overdue_accounts_list:
                logging.warning(
                    f"[欠费检查] 用户 {auth_username} 有 {len(overdue_accounts_list)} 个账号存在欠费，拒绝启动任务"
                )
                return {
                    "success": False,
                    "message": "有账号存在欠费，请先缴费",
                    "error_code": "OVERDUE_PAYMENT",
                    "overdue_accounts": overdue_accounts_list,
                }

        # 步骤2：启动任务（没有欠费问题）
        with self.lock:
            existing_task = self.tasks.get(session_id)
            if existing_task and existing_task.get("status") == "running":
                return {
                    "success": False,
                    "message": "当前会话已有后台任务在运行",
                }

            execution_identities = []
            if getattr(api_instance, "is_multi_account_mode", False):
                for account_username, account in (
                    getattr(api_instance, "accounts", {}) or {}
                ).items():
                    execution_identities.append(account_username)
                    account_user_data = getattr(account, "user_data", None)
                    execution_identities.extend(
                        [
                            getattr(account_user_data, "username", ""),
                            getattr(account_user_data, "student_id", ""),
                        ]
                    )
            else:
                user_data = getattr(api_instance, "user_data", None)
                user_info = getattr(api_instance, "user_info", {}) or {}
                execution_identities.extend(
                    [
                        getattr(user_data, "username", ""),
                        getattr(user_data, "student_id", ""),
                        (
                            user_info.get("student_id", "")
                            if isinstance(user_info, dict)
                            else ""
                        ),
                        (
                            user_info.get("account", "")
                            if isinstance(user_info, dict)
                            else ""
                        ),
                    ]
                )

            execution_token = object()
            claimed, conflict_identity = _main()._claim_school_account_execution(
                execution_identities,
                execution_token,
            )
            if not claimed:
                return {
                    "success": False,
                    "message": (
                        f"学校账号 {conflict_identity} 已在单账号或多账号模式中执行任务"
                    ),
                }

            task_state = {
                "session_id": session_id,
                "total_tasks": len(task_indices),
                "completed_tasks": 0,
                "current_task_index": 0,
                "task_indices": task_indices,
                "auto_generate": auto_generate,
                "status": "running",
                "map_provider": _main()._get_active_map_provider(config),
                "start_time": time.time(),
                "last_update": time.time(),
                "progress_percent": 0,
                "current_task_progress": 0,
                "singleProcessedPoints": 0,
                "singleTotalPoints": 0,
            }

            self.tasks[session_id] = task_state
            self.execution_tokens[session_id] = execution_token
            self.save_task_state(session_id, task_state)
            thread = threading.Thread(
                target=self._execute_tasks_background,
                args=(session_id, api_instance, task_indices, auto_generate),
                daemon=True,
            )
            try:
                thread.start()
            except Exception:
                self.tasks.pop(session_id, None)
                self.execution_tokens.pop(session_id, None)
                _main()._release_school_account_execution(execution_token)
                raise

            logging.info(
                f"后台任务已启动，会话ID前缀: {session_id[:8]}, 总任务数: {len(task_indices)}"
            )
            return {
                "success": True,
                "message": f"已启动后台任务，共{len(task_indices)}个任务",
            }

    def _execute_tasks_background(
        self, session_id, api_instance, task_indices, auto_generate
    ):
        """后台执行任务的线程函数"""
        try:
            tasks_executed = 0

            for i, task_idx in enumerate(task_indices):
                with self.lock:
                    if session_id not in self.tasks:
                        logging.info(f"后台任务已取消，会话ID前缀: {session_id[:8]}")
                        return

                    task_state = self.tasks[session_id]
                    if task_state.get("status") == "stopped":
                        logging.info(f"后台任务已停止，会话ID前缀: {session_id[:8]}")
                        return
                with self.lock:
                    task_state["current_task_index"] = i
                    task_state["last_update"] = time.time()
                    self.save_task_state(session_id, task_state)
                logging.info(
                    f"正在执行后台任务 {i+1}/{len(task_indices)}，会话ID前缀: {session_id[:8]}"
                )

                # [修正] 添加索引边界检查，防止列表变化导致越界崩溃
                if task_idx < 0 or task_idx >= len(api_instance.all_run_data):
                    error_msg = f"任务索引 {task_idx} 超出范围 (任务列表长度: {len(api_instance.all_run_data)})，跳过此任务"
                    logging.error(f"[后台任务] {error_msg}")
                    # 可选：更新任务状态为错误（视需求而定，这里选择仅跳过以保持队列继续）
                    continue

                run_data = api_instance.all_run_data[task_idx]
                if auto_generate and not run_data.run_coords:
                    logging.info(
                        f"正在为任务自动生成路径: 任务名称={run_data.run_name}"
                    )
                    try:
                        if not run_data.details_fetched:
                            logging.info(
                                f"正在获取任务详细信息: {run_data.run_name}..."
                            )
                            details_resp = api_instance.get_task_details(
                                task_idx)
                            if not details_resp.get("success"):
                                logging.error(
                                    f"获取任务详情失败，任务名称: {run_data.run_name}，错误信息: {details_resp.get('message', '未知错误')}"
                                )
                                continue
                            run_data = api_instance.all_run_data[task_idx]
                            logging.info(f"任务详情获取成功: {run_data.run_name}")

                        if not run_data.target_points:

                            logging.warning(
                                f"[跳过任务] 任务 '{run_data.run_name}' 因缺少打卡点 (0个) 而无法自动生成路径。请检查学校平台任务设置。"
                            )

                            continue

                        logging.info(
                            f"任务包含 {len(run_data.target_points)} 个目标打卡点: {run_data.run_name}"
                        )
                        waypoints = run_data.target_points
                        logging.info(
                            f"正在规划路径，包含 {len(waypoints)} 个路点，任务名称: {run_data.run_name}"
                        )
                        logging.info(
                            f"Waypoints: {waypoints[:3]}..."
                            if len(waypoints) > 3
                            else f"Waypoints: {waypoints}"
                        )

                        if not _main().chrome_pool:
                            logging.error("Chrome浏览器池不可用，无法进行路径规划！")
                            continue

                        try:
                            path_coords = _main()._plan_route_path_with_provider_runtime(
                                session_id,
                                waypoints,
                                python_params=api_instance.params,
                                guard_label="BackgroundTaskPathPlanning",
                                app_base_url=getattr(api_instance, "_web_app_base_url", None),
                            )
                            for notice in path_coords.get("notices", []):
                                logging.info(notice)
                        except Exception as e:
                            logging.error(
                                f"Chrome浏览器池路径规划失败，任务名称: {run_data.run_name}，异常信息: {e}",
                                exc_info=True,
                            )
                            continue

                        logging.info(
                            f"路径规划JavaScript返回结果: 类型={type(path_coords)}, 包含'path'键={'是' if (path_coords and 'path' in path_coords) else '否'}"
                        )

                        if path_coords and "path" in path_coords:
                            api_path_coords = path_coords["path"]
                            logging.info(
                                f"路径规划成功，包含 {len(api_path_coords)} 个坐标点"
                            )
                            p = api_instance.params
                            logging.info(
                                f"正在生成运动模拟数据，参数: 最小时长={p.get('min_time_m', 20)}分钟, 最大时长={p.get('max_time_m', 30)}分钟, 最小距离={p.get('min_dist_m', 2000)}米"
                            )
                            gen_resp = api_instance.auto_generate_path_with_api(
                                api_path_coords,
                                p.get("min_time_m", 20),
                                p.get("max_time_m", 30),
                                p.get("min_dist_m", 2000),
                            )

                            logging.info(
                                f"auto_generate_path_with_api函数返回: 成功={gen_resp.get('success')}"
                            )

                            if gen_resp.get("success"):
                                run_data.run_coords = gen_resp["run_coords"]
                                run_data.total_run_distance_m = gen_resp[
                                    "total_dist"
                                ]
                                run_data.total_run_time_s = gen_resp[
                                    "total_time"
                                ]
                                logging.info(
                                    f"路径自动生成成功，任务: {run_data.run_name}，坐标点数: {len(gen_resp['run_coords'])}, 总距离: {gen_resp['total_dist']}米, 总时长: {gen_resp['total_time']}秒"
                                )

                                with self.lock:
                                    if session_id in self.tasks:
                                        task_state = self.tasks[session_id]
                                        task_state["last_update"] = time.time(
                                        )
                                        task_state["estimated_total_time_s"] = (
                                            run_data.total_run_time_s
                                        )
                                        task_state[
                                            "estimated_total_distance_m"
                                        ] = run_data.total_run_distance_m
                                        task_state["target_points"] = (
                                            run_data.target_points
                                            if hasattr(
                                                run_data, "target_points"
                                            )
                                            else []
                                        )
                                        task_state["target_point_names"] = (
                                            run_data.target_point_names
                                            if hasattr(
                                                run_data, "target_point_names"
                                            )
                                            else ""
                                        )
                                        task_state["recommended_coords"] = (
                                            run_data.recommended_coords
                                            if hasattr(
                                                run_data, "recommended_coords"
                                            )
                                            else []
                                        )
                                        task_state["run_coords"] = (
                                            run_data.run_coords
                                            if hasattr(run_data, "run_coords")
                                            else []
                                        )
                                        total_points = len(
                                            run_data.run_coords)
                                        task_state["singleTotalPoints"] = (
                                            total_points
                                        )
                                        task_state["singleProcessedPoints"] = 0
                                        self.save_task_state(
                                            session_id, task_state
                                        )

                            else:
                                logging.error(
                                    f"生成运动坐标序列失败: {gen_resp.get('message')}"
                                )
                                continue
                        else:
                            error_msg = (
                                path_coords.get(
                                    "error", "Unknown error")
                                if path_coords
                                else "No response from path planning"
                            )
                            logging.error(
                                f"任务路径规划失败，任务名称: {run_data.run_name}，错误信息: {error_msg}"
                            )
                            continue

                    except Exception as e:
                        logging.error(f"自动生成路径失败，异常信息: {e}", exc_info=True)
                        continue

                if not run_data.run_coords:
                    logging.warning(f"任务没有可用路径，跳过执行: {run_data.run_name}")
                    continue
                try:
                    task_idx = api_instance.all_run_data.index(run_data)
                except ValueError:
                    task_idx = -1
                run_data.target_sequence = 0
                run_data.is_in_target_zone = False
                if hasattr(api_instance, "stop_run_flag"):
                    api_instance.stop_run_flag.clear()
                finished_event = threading.Event()
                try:
                    thread = threading.Thread(
                        target=api_instance._run_submission_thread,
                        args=(
                            run_data,
                            task_idx,
                            api_instance.api_client,
                            False,
                            finished_event,
                        ),
                        daemon=True,
                    )
                    thread.start()
                    tasks_executed += 1
                    total_time_s = sum(p[2]
                                       for p in run_data.run_coords) / 1000.0
                    timeout = max(total_time_s * 2, 300)
                    start_wait = time.time()
                    while not finished_event.is_set():
                        if time.time() - start_wait > timeout:
                            logging.warning(f"任务执行超时: {run_data.run_name}")
                            api_instance.stop_run_flag.set()
                            break
                        with self.lock:
                            if hasattr(run_data, "current_point_index"):
                                total_points = len(run_data.run_coords)
                                current_progress = int(
                                    run_data.current_point_index / total_points * 100
                                )
                                task_state["current_task_progress"] = current_progress
                                task_state["last_update"] = time.time()
                                current_idx = run_data.current_point_index
                                task_state["singleProcessedPoints"] = current_idx
                                task_state["singleTotalPoints"] = total_points
                                task_state["target_points"] = (
                                    run_data.target_points
                                    if hasattr(run_data, "target_points")
                                    else []
                                )
                                task_state["target_point_names"] = (
                                    run_data.target_point_names
                                    if hasattr(run_data, "target_point_names")
                                    else ""
                                )
                                task_state["recommended_coords"] = (
                                    run_data.recommended_coords
                                    if hasattr(run_data, "recommended_coords")
                                    else []
                                )
                                task_state["run_coords"] = (
                                    run_data.run_coords
                                    if hasattr(run_data, "run_coords")
                                    else []
                                )
                                server_target_sequence_0based = getattr(
                                    run_data, "target_sequence", 0
                                )
                                task_state["checked_targets_count"] = (
                                    server_target_sequence_0based + 1
                                )

                                task_state["total_targets_count"] = (
                                    len(run_data.target_points)
                                    if hasattr(run_data, "target_points")
                                    else 0
                                )
                                task_state["elapsed_time_s"] = time.time() - \
                                    start_wait
                                task_state["current_distance_m"] = getattr(
                                    run_data, "distance_covered_m", 0
                                )
                                task_state["estimated_total_time_s"] = getattr(
                                    run_data, "total_run_time_s", 0
                                )
                                task_state["estimated_total_distance_m"] = getattr(
                                    run_data, "total_run_distance_m", 0
                                )
                                if current_idx > 0 and current_idx <= total_points:
                                    coord = run_data.run_coords[current_idx - 1]
                                    task_state["current_position"] = {
                                        "lon": coord[0],
                                        "lat": coord[1],
                                        "distance": getattr(
                                            run_data, "distance_covered_m", 0
                                        ),
                                        "target_sequence": getattr(
                                            run_data, "target_sequence", 0
                                        ),
                                        "point_index": current_idx,
                                    }
                        if int(time.time() - start_wait) % 5 == 0:
                            with self.lock:
                                self.save_task_state(session_id, task_state)

                        time.sleep(1)
                    thread.join(timeout=10)

                except Exception as e:
                    logging.error(f"任务执行失败，异常信息: {e}", exc_info=True)

                # 标记当前任务已完成（更新进度状态）
                with self.lock:
                    task_state["completed_tasks"] = i + 1
                    task_state["progress_percent"] = int(
                        (i + 1) / len(task_indices) * 100
                    )
                    task_state["current_task_progress"] = 100
                    task_state["last_update"] = time.time()
                    self.save_task_state(session_id, task_state)

                logging.info(
                    f"任务 {i+1}/{len(task_indices)} 已完成，会话ID: {session_id}"
                )

                # ========== 结束：次数扣减处理 ==========
            if tasks_executed > 0:
                with self.lock:
                    task_state["status"] = "completed"
                    task_state["last_update"] = time.time()
                    self.save_task_state(session_id, task_state)

                logging.info(f"所有后台任务已完成，会话ID: {session_id}")
            else:
                with self.lock:
                    if task_state.get("status") != "error":
                        task_state["status"] = "error"
                        if auto_generate:
                            task_state["error"] = "自动生成路径失败，请尝试手动生成路径"
                        else:
                            task_state["error"] = "所有任务都没有路径，请先生成路径"
                        task_state["last_update"] = time.time()
                        self.save_task_state(session_id, task_state)
                if auto_generate:
                    logging.error(
                        f"没有任务被执行，会话ID前缀: {session_id[:8]} - 所有自动生成路径尝试均失败"
                    )
                else:
                    logging.warning(
                        f"没有任务被执行，会话ID前缀: {session_id[:8]} - 没有可用的路径"
                    )

        except Exception as e:
            logging.error(f"后台任务执行失败，异常信息: {e}", exc_info=True)
            with self.lock:
                if session_id in self.tasks:
                    self.tasks[session_id]["status"] = "error"
                    self.tasks[session_id]["error"] = str(e)
                    self.save_task_state(session_id, self.tasks[session_id])
        finally:
            with self.lock:
                execution_token = self.execution_tokens.pop(session_id, None)
            _main()._release_school_account_execution(execution_token)

    def get_task_status(self, session_id):
        """获取任务状态"""
        with self.lock:
            if session_id in self.tasks:
                return self.tasks[session_id]
        task_state = self.load_task_state(session_id)
        if task_state:
            with self.lock:
                self.tasks[session_id] = task_state
            return task_state

        return None

    def stop_task(self, session_id):
        """停止后台任务"""
        with self.lock:
            if session_id in self.tasks:
                self.tasks[session_id]["status"] = "stopped"
                self.save_task_state(session_id, self.tasks[session_id])
                logging.info(f"后台任务已停止，会话ID前缀: {session_id[:8]}")
                return {"success": True, "message": "后台任务已停止"}
            return {"success": False, "message": "未找到运行中的后台任务"}

    def cleanup_old_tasks(self, max_age_hours=24):
        """清理旧的任务状态文件"""
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            for filename in os.listdir(self.task_storage_dir):
                if not filename.endswith(".json"):
                    continue

                filepath = os.path.join(self.task_storage_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        task_state = json.load(f)

                    last_update = task_state.get("last_update", 0)
                    if current_time - last_update > max_age_seconds:
                        os.remove(filepath)
                        _session_id = task_state.get("session_id")
                        if _session_id:
                            self._update_tasks_index(_session_id, {}, action="remove")
                        logging.info(f"已删除旧的任务状态文件: {filename}")
                except Exception as e:
                    logging.warning(f"处理任务文件失败，文件名: {filename}，错误: {e}")
        except Exception as e:
            logging.error(f"清理旧任务文件失败，异常信息: {e}")


class MicroPixelCaptcha:

    FONT = {
        "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
        "N": ["10001", "11001", "10101", "10101", "10011", "10001", "10001"],
        "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
        "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
        "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
        "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
        "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
        "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
        "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
        "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
        "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
        "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
        "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
        "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
        "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
        "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
        "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
        "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
        "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
        "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
        "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
        "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
        "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
        "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
        "Y": ["10001", "10001", "10001", "01010", "00100", "00100", "00100"],
        "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
        "0": ["01110", "10011", "10101", "10101", "10101", "11001", "01110"],
        "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
        "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
        "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
        "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
        "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
        "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
        "7": ["11111", "00001", "00010", "00100", "00100", "00100", "00100"],
        "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
        "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    }

    def _random_string(self, length: int) -> str:
        return "".join(random.choices(string.ascii_lowercase, k=length))

    def generate(
        self, length: int = 4, scale_factor: int = 2, noise_level: float = 0.08
    ):
        """
        生成高密度微像素验证码
        :param length: 验证码字符数
        :param scale_factor: 细分倍数 (建议2或3)
        :param noise_level: 噪点比例
        """
        code = "".join(random.choices(list(self.FONT.keys()), k=length))

        char_patterns = [self.FONT.get(c, ["11111"] * 7) for c in code]
        base_rows = ["0".join(row_tuple) for row_tuple in zip(*char_patterns)]
        expanded_bit_string = []
        for row in base_rows:
            expanded_row_str = "".join([bit * scale_factor for bit in row])
            for _ in range(scale_factor):
                expanded_bit_string.append(expanded_row_str)

        full_bit_stream = "".join(expanded_bit_string)
        logic_width = length * 5 + (length - 1)
        grid_cols = logic_width * scale_factor
        cls_con = self._random_string(10)
        cls_bg = self._random_string(5)
        cls_fg = self._random_string(5)

        pixels = []
        for bit in full_bit_stream:
            is_fg = bit == "1"
            if random.random() < noise_level:
                is_fg = not is_fg

            pixels.append(
                f'<span class="{cls_fg if is_fg else cls_bg}"></span>')

        html_content = "".join(pixels)
        pixel_size = 12 // scale_factor
        if pixel_size < 4:
            pixel_size = 4
        grid_rows = 7 * scale_factor
        captcha_width = grid_cols * (pixel_size + 1) - 1 + 2 * 10 + 2 * 1
        captcha_height = grid_rows * (pixel_size + 1) - 1 + 2 * 10 + 2 * 1

        css = f"""<style>
.{cls_con}{{
    display:grid;
    grid-template-columns:repeat({grid_cols}, {pixel_size}px);
    gap:1px;
    background:#000;
    padding:10px;
    width:fit-content;
    border:1px solid #333;
}}
.{cls_con} span{{
    width:{pixel_size}px;
    height:{pixel_size}px;
    display:block;
    border-radius:0;
}}
.{cls_bg}{{background:#000;}}
.{cls_fg}{{background:#fff;}}
</style>"""

        full_html = f'<div class="{cls_con}">{html_content}</div>{css}'
        return code, full_html, captcha_width, captcha_height


class PlaywrightPageProxy:
    """
    Playwright Page 对象的代理类。

    此代理类拦截对 Page 对象方法的调用，并将其路由到专用的 Playwright 工作线程执行。
    这样做是为了解决 Playwright 对象的线程绑定问题 - Page 对象只能在创建它的线程中使用。

    通过此代理，调用代码可以像使用普通 Page 对象一样使用它，而实际操作会在正确的线程中执行。
    """

    def __init__(self, session_id, browser_pool):
        """
        初始化 Page 代理。

        参数:
            session_id: 会话标识符，用于关联到特定的浏览器上下文
            browser_pool: ChromeBrowserPool 实例，用于发送操作请求
        """
        # 会话ID，用于标识此代理对应的浏览器上下文
        self._session_id = session_id
        # 浏览器池实例，用于发送操作请求到专用线程
        self._browser_pool = browser_pool

    def evaluate(self, script, arg=None):
        """
        在页面中执行 JavaScript 代码并返回结果。

        参数:
            script: 要执行的 JavaScript 代码字符串
            arg: 传递给 JavaScript 的参数（可选）

        返回:
            JavaScript 执行结果
        """
        # 通过浏览器池的专用线程执行 JavaScript
        return self._browser_pool.execute_js(self._session_id, script, arg)

    def goto(self, url, **kwargs):
        """
        导航到指定的 URL。

        参数:
            url: 目标 URL
            **kwargs: 其他参数（如 wait_until, timeout 等）

        返回:
            导航结果
        """
        # 向专用线程发送导航请求
        result = self._browser_pool._send_request(
            "page_goto",
            {
                "session_id": self._session_id,
                "url": url,
                "options": kwargs,
            },
        )
        if not result.get("success"):
            raise RuntimeError(f"导航失败: {result.get('error', '未知错误')}")
        return result.get("result")

    def set_content(self, html, **kwargs):
        """
        设置页面的 HTML 内容。

        参数:
            html: HTML 内容字符串
            **kwargs: 其他参数（如 wait_until, timeout 等）

        返回:
            操作结果
        """
        # 向专用线程发送设置内容请求
        result = self._browser_pool._send_request(
            "page_set_content",
            {
                "session_id": self._session_id,
                "html": html,
                "options": kwargs,
            },
        )
        if not result.get("success"):
            raise RuntimeError(f"设置内容失败: {result.get('error', '未知错误')}")
        return result.get("result")

    def wait_for_function(self, expression, **kwargs):
        """
        等待 JavaScript 函数返回真值。

        参数:
            expression: JavaScript 表达式
            **kwargs: 其他参数（如 timeout 等）

        返回:
            操作结果
        """
        # 向专用线程发送等待函数请求
        result = self._browser_pool._send_request(
            "page_wait_for_function",
            {
                "session_id": self._session_id,
                "expression": expression,
                "options": kwargs,
            },
        )
        if not result.get("success"):
            raise RuntimeError(f"等待函数失败: {result.get('error', '未知错误')}")
        return result.get("result")


class PlaywrightContextProxy:
    """
    Playwright BrowserContext 对象的代理类。

    此代理类用于保持与现有代码的兼容性，提供一个类似 BrowserContext 的接口。
    """

    def __init__(self, session_id, browser_pool):
        """
        初始化 Context 代理。

        参数:
            session_id: 会话标识符
            browser_pool: ChromeBrowserPool 实例
        """
        self._session_id = session_id
        self._browser_pool = browser_pool

    def close(self):
        """
        关闭浏览器上下文。
        """
        self._browser_pool.close_context(self._session_id)


class ChromeBrowserPool:
    """
    管理服务器端Chrome浏览器实例，用于执行JS计算 (专用线程模式)

    注意：应用使用 async_mode='threading' 且未调用 eventlet.monkey_patch()，
    所有调用方均运行在普通 OS 线程中。Playwright 的同步 API 是线程绑定的，
    因此所有 Playwright 操作必须在同一个专用线程中执行。

    解决方案：创建一个专用的持久化原生线程来运行所有 Playwright 操作。
    使用队列机制将操作请求发送到这个专用线程，调用方通过原生
    threading.Event.wait() 阻塞等待结果返回。
    """

    # 队列轮询超时时间（秒）：工作线程从队列获取请求时的等待时间
    QUEUE_POLL_TIMEOUT_SEC = 1
    # 线程关闭超时时间（秒）：等待工作线程退出的最大时间
    THREAD_SHUTDOWN_TIMEOUT_SEC = 10
    # 默认操作超时时间（秒）：等待 Playwright 操作完成的默认超时时间
    DEFAULT_OPERATION_TIMEOUT_SEC = 60

    def __init__(self, headless=True, max_instances=5):
        """
        初始化 ChromeBrowserPool 实例。

        参数:
            headless: 是否以无头模式运行浏览器（无图形界面）
            max_instances: 最大浏览器实例数量限制（保留参数以兼容现有接口，当前实现使用单一实例）
        """
        # 是否以无头模式运行浏览器（无图形界面）
        self.headless = headless
        # 最大浏览器实例数量限制（保留以兼容现有接口，当前实现使用单一浏览器实例配合多上下文）
        self.max_instances = max_instances

        # 导入 eventlet.patcher 获取未被 monkey patch 的原生模块
        # 这是关键：必须使用原生的 threading 和 queue 模块，而不是被 eventlet 修改过的版本
        # from eventlet import patcher

        # 获取原生的 threading 模块，用于创建真正的系统线程
        self._native_threading = eventlet.patcher.original("threading")
        # 获取原生的 queue 模块，用于线程间通信
        self._native_queue = eventlet.patcher.original("queue")

        # 创建请求队列：用于从 eventlet greenlet 发送操作请求到专用线程
        # 使用原生 queue.Queue 确保线程安全，且不受 eventlet 影响
        self._request_queue = self._native_queue.Queue()

        # 创建专用线程的停止标志，用于优雅关闭
        self._stop_flag = self._native_threading.Event()

        # 在专用线程中维护的 Playwright 相关对象引用
        # 这些对象只在专用线程中创建和使用
        self._playwright = None  # Playwright 实例
        self._browser = None  # Browser 浏览器实例
        self._contexts = {}  # 会话ID到浏览器上下文的映射字典

        # 记录专用线程是否已初始化的标志
        self._initialized = False

        # 创建并启动专用的原生线程
        # 不使用 daemon=True，以确保程序退出时能够正确清理 Playwright 资源
        # 需要通过 shutdown() 方法显式停止线程
        self._worker_thread = self._native_threading.Thread(
            target=self._worker_loop,  # 线程的主循环函数
            name="PlaywrightWorkerThread",  # 线程名称，便于调试
        )
        # 启动专用线程
        self._worker_thread.start()
        # 记录线程启动日志
        logging.info(f"Playwright 专用工作线程已启动 (headless={self.headless})")

    def _worker_loop(self):
        """
        专用线程的主循环函数。

        这个函数在专用线程中持续运行，从请求队列中获取操作请求，
        执行相应的 Playwright 操作，并将结果返回给调用者。
        """
        # 持续运行直到收到停止信号
        while not self._stop_flag.is_set():
            try:
                # 从请求队列获取操作请求，设置超时避免无限阻塞
                # 使用 QUEUE_POLL_TIMEOUT_SEC 常量控制轮询间隔
                request = self._request_queue.get(
                    timeout=self.QUEUE_POLL_TIMEOUT_SEC)
            except self._native_queue.Empty:
                # 队列为空且超时，继续循环检查停止标志
                continue

            # 解析请求：操作类型、参数、用于返回结果的事件和结果容器
            operation = request.get("operation")  # 操作类型字符串
            args = request.get("args", {})  # 操作参数字典
            result_event = request.get("result_event")  # 用于通知完成的事件
            result_container = request.get("result_container")  # 用于存储结果的容器

            # 检查是否是关闭信号（不需要返回结果）
            if operation == "_shutdown":
                continue

            try:
                # 根据操作类型执行相应的 Playwright 操作
                if operation == "initialize":
                    # 初始化 Playwright 和浏览器
                    result = self._do_initialize()
                elif operation == "get_context":
                    # 获取或创建浏览器上下文
                    result = self._do_get_context(args.get("session_id"))
                elif operation == "execute_js":
                    # 执行 JavaScript 代码
                    result = self._do_execute_js(
                        args.get("session_id"),
                        args.get("script"),
                        args.get("js_args", []),
                    )
                elif operation == "close_context":
                    # 关闭指定会话的上下文
                    result = self._do_close_context(args.get("session_id"))
                elif operation == "cleanup":
                    # 清理所有资源
                    result = self._do_cleanup()
                elif operation == "cleanup_context":
                    # 清理指定会话的上下文（别名，与 close_context 功能相同）
                    result = self._do_close_context(args.get("session_id"))
                elif operation == "page_goto":
                    # 导航到指定 URL
                    result = self._do_page_goto(
                        args.get("session_id"), args.get(
                            "url"), args.get("options", {})
                    )
                elif operation == "page_set_content":
                    # 设置页面 HTML 内容
                    result = self._do_page_set_content(
                        args.get("session_id"),
                        args.get("html"),
                        args.get("options", {}),
                    )
                elif operation == "page_wait_for_function":
                    # 等待 JavaScript 函数返回真值
                    result = self._do_page_wait_for_function(
                        args.get("session_id"),
                        args.get("expression"),
                        args.get("options", {}),
                    )
                else:
                    # 未知操作类型，返回错误
                    result = {"success": False, "error": f"未知操作: {operation}"}

            except Exception as e:
                # 捕获操作执行过程中的任何异常
                logging.error(
                    f"Playwright 操作 {operation} 失败: {e}", exc_info=True)
                result = {"success": False, "error": str(e)}

            # 将结果存入结果容器并通知等待的调用者
            if result_container is not None:
                result_container["result"] = result
            if result_event is not None:
                result_event.set()  # 触发事件，通知调用者操作已完成

        # 线程退出前的清理工作
        logging.info("Playwright 专用工作线程正在退出...")
        self._do_cleanup()

    def _do_initialize(self):
        """
        在专用线程中初始化 Playwright 和浏览器。

        此方法只在专用线程中被调用，确保 Playwright 对象在正确的线程中创建。

        返回:
            dict: 包含 success 标志的结果字典
        """
        # 检查是否已经初始化过
        if self._initialized:
            return {"success": True, "message": "已经初始化"}

        try:
            # 记录初始化日志
            logging.info("正在专用线程中初始化 Playwright...")

            # 启动 Playwright，这会返回一个 Playwright 实例
            self._playwright = sync_playwright().start()

            # 使用 Playwright 启动 Chromium 浏览器
            # --no-sandbox: 在 Docker/Linux 环境中必需
            # --disable-setuid-sandbox: 在某些 Linux 环境中必需
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )

            # 初始化上下文字典
            self._contexts = {}
            # 标记为已初始化
            self._initialized = True

            logging.info(
                f"Playwright 和 Chrome 浏览器初始化成功 (headless={self.headless})"
            )
            return {"success": True}

        except Exception as e:
            # 初始化失败，记录错误并返回失败结果
            logging.error(f"初始化 Playwright 失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _do_get_context(self, session_id):
        """
        在专用线程中获取或创建指定会话的浏览器上下文。

        参数:
            session_id: 会话标识符

        返回:
            dict: 包含 success 标志和上下文信息的结果字典
        """
        # 确保已初始化
        if not self._initialized:
            init_result = self._do_initialize()
            if not init_result.get("success"):
                return init_result

        # 检查会话是否已有上下文
        if session_id not in self._contexts:
            try:
                # 创建新的浏览器上下文
                # viewport: 设置视口大小为 1920x1080，模拟标准桌面分辨率
                # user_agent: 设置用户代理字符串
                context = self._browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    ignore_https_errors=True,
                )
                # 在上下文中创建新页面（标签页）
                page = context.new_page()
                # 存储上下文和页面到字典中
                self._contexts[session_id] = {"context": context, "page": page}
                logging.info(f"为会话 {session_id} 创建了新的 Chrome 上下文")
            except Exception as e:
                logging.error(f"创建上下文失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        return {"success": True, "session_id": session_id}

    def _do_execute_js(self, session_id, script, js_args):
        """
        在专用线程中执行 JavaScript 代码。

        参数:
            session_id: 会话标识符
            script: 要执行的 JavaScript 代码字符串
            js_args: 传递给 JavaScript 的参数列表

        返回:
            dict: 包含 success 标志和执行结果的结果字典
        """
        # 确保上下文存在
        ctx_result = self._do_get_context(session_id)
        if not ctx_result.get("success"):
            return ctx_result

        try:
            # 获取页面对象
            page = self._contexts[session_id]["page"]
            # 执行 JavaScript 代码
            result = page.evaluate(script, js_args)
            return {"success": True, "result": result}
        except Exception as e:
            logging.error(
                f"执行 JS 失败 (session={session_id}): {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _do_close_context(self, session_id):
        """
        在专用线程中关闭指定会话的浏览器上下文。

        参数:
            session_id: 要关闭的会话标识符

        返回:
            dict: 包含 success 标志的结果字典
        """
        # 检查会话是否存在
        if session_id not in self._contexts:
            return {"success": True, "message": "上下文不存在，无需关闭"}

        try:
            # 获取并关闭上下文
            ctx = self._contexts[session_id]
            ctx["context"].close()
            # 从字典中删除引用
            del self._contexts[session_id]
            logging.info(f"已关闭会话 {session_id} 的 Chrome 上下文")
            return {"success": True}
        except Exception as e:
            logging.error(f"关闭上下文失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _do_page_goto(self, session_id, url, options):
        """
        在专用线程中执行页面导航操作。

        参数:
            session_id: 会话标识符
            url: 目标 URL
            options: 导航选项字典

        返回:
            dict: 包含 success 标志和导航结果的字典
        """
        # 确保上下文存在
        ctx_result = self._do_get_context(session_id)
        if not ctx_result.get("success"):
            return ctx_result

        try:
            # 获取页面对象
            page = self._contexts[session_id]["page"]
            # 执行导航操作
            result = page.goto(url, **options) if options else page.goto(url)
            return {"success": True, "result": result}
        except Exception as e:
            logging.error(
                f"页面导航失败 (session={session_id}, url={url}): {e}", exc_info=True
            )
            return {"success": False, "error": str(e)}

    def _do_page_set_content(self, session_id, html, options):
        """
        在专用线程中设置页面 HTML 内容。

        参数:
            session_id: 会话标识符
            html: HTML 内容字符串
            options: 设置选项字典

        返回:
            dict: 包含 success 标志的结果字典
        """
        # 确保上下文存在
        ctx_result = self._do_get_context(session_id)
        if not ctx_result.get("success"):
            return ctx_result

        try:
            # 获取页面对象
            page = self._contexts[session_id]["page"]
            # 设置页面内容
            result = (
                page.set_content(
                    html, **options) if options else page.set_content(html)
            )
            return {"success": True, "result": result}
        except Exception as e:
            logging.error(
                f"设置页面内容失败 (session={session_id}): {e}", exc_info=True
            )
            return {"success": False, "error": str(e)}

    def _do_page_wait_for_function(self, session_id, expression, options):
        """
        在专用线程中等待 JavaScript 函数返回真值。

        参数:
            session_id: 会话标识符
            expression: JavaScript 表达式
            options: 等待选项字典

        返回:
            dict: 包含 success 标志的结果字典
        """
        # 确保上下文存在
        ctx_result = self._do_get_context(session_id)
        if not ctx_result.get("success"):
            return ctx_result

        try:
            # 获取页面对象
            page = self._contexts[session_id]["page"]
            # 等待函数
            result = (
                page.wait_for_function(expression, **options)
                if options
                else page.wait_for_function(expression)
            )
            return {"success": True, "result": result}
        except Exception as e:
            logging.error(f"等待函数失败 (session={session_id}): {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _do_cleanup(self):
        """
        在专用线程中清理所有 Playwright 资源。

        返回:
            dict: 包含 success 标志的结果字典
        """
        try:
            logging.info("正在清理 Playwright 资源...")

            # 关闭所有上下文
            for session_id, ctx in list(self._contexts.items()):
                try:
                    ctx["context"].close()
                    logging.debug(f"已关闭会话 {session_id} 的上下文")
                except Exception as e:
                    logging.warning(f"关闭会话 {session_id} 上下文失败: {e}")
            self._contexts.clear()

            # 关闭浏览器
            if self._browser:
                try:
                    self._browser.close()
                    logging.debug("浏览器已关闭")
                except Exception as e:
                    logging.warning(f"关闭浏览器失败: {e}")
                self._browser = None

            # 停止 Playwright
            if self._playwright:
                try:
                    self._playwright.stop()
                    logging.debug("Playwright 已停止")
                except Exception as e:
                    logging.warning(f"停止 Playwright 失败: {e}")
                self._playwright = None

            self._initialized = False
            logging.info("Playwright 资源清理完毕")
            return {"success": True}

        except Exception as e:
            logging.error(f"清理 Playwright 资源时出错: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _send_request(self, operation, args=None, timeout=None):
        """
        向专用线程发送操作请求并等待结果。

        此方法运行在普通 OS 线程（非 eventlet greenlet）中，因为应用使用
        async_mode='threading' 且未调用 eventlet.monkey_patch()。
        直接调用原生 threading.Event.wait() 阻塞当前线程直到工作线程完成操作。

        参数:
            operation: 操作类型字符串 (如 "initialize", "get_context", "execute_js" 等)
            args: 操作参数字典（可选）
            timeout: 等待结果的超时时间（秒），默认使用 DEFAULT_OPERATION_TIMEOUT_SEC

        返回:
            dict: 操作结果字典，包含 success 标志和其他结果数据
        """
        # 如果未指定超时时间，使用默认值
        if timeout is None:
            timeout = self.DEFAULT_OPERATION_TIMEOUT_SEC

        # 使用原生 threading.Event 作为同步机制
        result_event = self._native_threading.Event()
        # 结果容器，用于存储操作结果
        result_container = {}

        # 构建请求对象
        request = {
            "operation": operation,
            "args": args or {},
            "result_event": result_event,
            "result_container": result_container,
        }

        # 将请求放入队列
        self._request_queue.put(request)

        # 直接在当前线程中等待结果。
        # 应用使用 async_mode='threading'（非 eventlet greenlet 模式），
        # 不调用 eventlet.monkey_patch()，所有后台任务均运行在普通 OS 线程中。
        # 因此无需通过 eventlet.tpool.execute() 转发等待调用——直接阻塞即可，
        # 且 tpool.execute() 在非 greenlet 线程中调用会导致内部 hub 通知机制失效而挂起。
        wait_result = result_event.wait(timeout=timeout)

        if wait_result:
            # 操作完成，返回结果
            return result_container.get("result", {"success": False, "error": "无结果"})
        else:
            # 超时，返回错误
            logging.error(f"Playwright 操作 {operation} 超时 (>{timeout}秒)")
            return {"success": False, "error": f"操作超时 (>{timeout}秒)"}

    def _initialize_for_thread(self):
        """
        初始化 Playwright 和浏览器（通过专用线程执行）。

        此方法保留原有接口，内部实现改为向专用线程发送初始化请求。
        这确保了与现有代码的兼容性。
        """
        # 向专用线程发送初始化请求
        result = self._send_request("initialize")
        if not result.get("success"):
            error_msg = result.get("error", "未知错误")
            logging.error(f"初始化 Playwright 失败: {error_msg}")
            raise RuntimeError(f"初始化 Playwright 失败: {error_msg}")

    def get_context(self, session_id):
        """
        获取或创建指定会话的浏览器上下文（通过专用线程执行）。

        参数:
            session_id: 会话标识符，用于区分不同用户/会话的浏览器上下文

        返回:
            dict: 包含 'context' 和 'page' 键的字典
                  - context: PlaywrightContextProxy 代理对象
                  - page: PlaywrightPageProxy 代理对象

        说明:
            返回的 context 和 page 是代理对象，它们会将所有操作路由到专用线程执行。
            调用代码可以像使用普通 Playwright 对象一样使用它们。
        """
        # 向专用线程发送获取上下文请求
        result = self._send_request("get_context", {"session_id": session_id})
        if not result.get("success"):
            error_msg = result.get("error", "未知错误")
            logging.error(f"获取上下文失败 (session={session_id}): {error_msg}")
            raise RuntimeError(f"获取上下文失败: {error_msg}")

        # 返回代理对象，而不是实际的 Playwright 对象
        # 代理对象会将所有方法调用路由到专用线程执行
        return {
            "context": PlaywrightContextProxy(session_id, self),
            "page": PlaywrightPageProxy(session_id, self),
        }

    def execute_js(self, session_id, script, *args):
        """
        在指定会话的Chrome中执行JavaScript代码（通过专用线程执行）。

        参数:
            session_id: 会话标识符
            script: 要执行的 JavaScript 代码字符串
            *args: 传递给 JavaScript 代码的参数

        返回:
            JavaScript 代码的执行结果，如果执行失败则返回 None
        """
        try:
            # 向专用线程发送执行 JS 请求
            result = self._send_request(
                "execute_js",
                {
                    "session_id": session_id,
                    "script": script,
                    "js_args": list(args),
                },
            )

            if result.get("success"):
                return result.get("result")
            else:
                error_msg = result.get("error", "未知错误")
                logging.error(f"执行 JS 失败 (session={session_id}): {error_msg}")
                return None

        except Exception as e:
            logging.error(
                f"执行 JS 异常 (session={session_id}): {e}", exc_info=True)
            return None

    def close_context(self, session_id):
        """
        关闭指定会话的浏览器上下文（通过专用线程执行）。

        参数:
            session_id: 要关闭的会话标识符
        """
        try:
            # 向专用线程发送关闭上下文请求
            result = self._send_request(
                "close_context", {"session_id": session_id})
            if not result.get("success"):
                error_msg = result.get("error", "未知错误")
                logging.error(f"关闭上下文失败 (session={session_id}): {error_msg}")
        except Exception as e:
            logging.error(f"关闭上下文异常: {e}", exc_info=True)

    def cleanup_context(self, session_id):
        """
        清理指定会话的浏览器上下文（通过专用线程执行）。

        此方法是 close_context 的别名，用于兼容现有代码。

        参数:
            session_id: 要清理的会话标识符
        """
        self.close_context(session_id)

    def cleanup_thread(self):
        """
        清理所有 Playwright 资源（通过专用线程执行）。

        此方法应在程序退出前调用，以确保正确释放所有浏览器资源。
        """
        try:
            # 向专用线程发送清理请求
            result = self._send_request("cleanup", timeout=30)
            if not result.get("success"):
                error_msg = result.get("error", "未知错误")
                logging.error(f"清理资源失败: {error_msg}")
        except Exception as e:
            logging.error(f"清理资源异常: {e}", exc_info=True)

    def shutdown(self):
        """
        关闭专用线程并清理所有资源。

        此方法设置停止标志，通知专用线程退出，并等待线程结束。
        如果线程未能在超时时间内退出，会记录警告日志。

        注意：由于 Python 的 GIL 和线程模型限制，无法强制终止一个正在运行的线程。
        如果线程卡在某个 Playwright 操作中，可能需要等待该操作完成才能退出。
        """
        logging.info("正在关闭 Playwright 专用工作线程...")
        # 设置停止标志，通知工作线程退出循环
        self._stop_flag.set()

        # 向队列发送一个空请求，确保工作线程能从 queue.get() 中唤醒
        # 这是因为工作线程可能正在 queue.get(timeout=QUEUE_POLL_TIMEOUT_SEC) 中等待
        try:
            self._request_queue.put(
                {
                    "operation": "_shutdown",
                    "args": {},
                    "result_event": None,
                    "result_container": None,
                }
            )
        except Exception:
            pass  # 忽略队列操作失败

        # 等待线程结束，使用 THREAD_SHUTDOWN_TIMEOUT_SEC 常量控制超时时间
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=self.THREAD_SHUTDOWN_TIMEOUT_SEC)
            if self._worker_thread.is_alive():
                # 线程未能在超时时间内退出
                # 由于 Python 不支持强制终止线程，只能记录警告
                # 线程将在其当前操作完成后自然退出
                logging.warning(
                    f"Playwright 工作线程未能在 {self.THREAD_SHUTDOWN_TIMEOUT_SEC} 秒内退出。"
                    "线程可能正在执行长时间操作，将在操作完成后退出。"
                    "如果程序正在关闭，线程将随进程终止。"
                )
            else:
                logging.info("Playwright 工作线程已正常退出")
        else:
            logging.info("Playwright 工作线程已结束")
