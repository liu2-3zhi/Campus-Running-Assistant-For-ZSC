from __future__ import annotations

import collections
import configparser
import datetime
import hashlib
import json
import logging
import os
import secrets
import sys
import threading
import time
import uuid


from main_runtime import _main
from theme_background_state import (
    background_files_locked,
    background_files_log,
    is_background_image_file,
)


# 学校账号密码可见级别（高 → 低）
#   ALL  : 持有 auto_fill_password（或管理员组）—— 可看所有用户的学校账号密码
#   OWN  : 持有 view_school_account_passwords —— 只能看当前系统账号自己关联的学校账号密码
#   NONE : 两者皆无 —— 不返回任何密码字段
PASSWORD_VISIBILITY_ALL = "all"
PASSWORD_VISIBILITY_OWN = "own"
PASSWORD_VISIBILITY_NONE = "none"

# 各内置权限组对新增权限的默认值（仅用于回填缺失键，不覆盖已有配置）
BUILTIN_PERMISSION_DEFAULTS = {
    "view_school_account_passwords": {
        "guest": False,
        "user": False,
        "admin": True,
        "super_admin": True,
    },
    # 绕过欠费（强制执行）：默认仅管理员/超级管理员拥有；
    # 可以通过用户管理为普通用户单独授予。
    "bypass_overdue": {
        "guest": False,
        "user": False,
        "admin": True,
        "super_admin": True,
    },
}


class AuthSystem:
    """用户认证和权限管理系统"""

    def __init__(self):
        logging.info("=" * 80)
        logging.info("初始化AuthSystem认证系统...")
        self.config = self._load_config()
        logging.info("配置文件已加载")
        self.permissions = self._load_permissions()
        # 回填内置权限组中缺失的新权限键（只补齐缺失项，不覆盖任何已有值）
        self._ensure_builtin_permissions()
        logging.info("权限配置已加载")
        # [修正] 使用 RLock (可重入锁) 替代 Lock。
        # 原因: register_user 方法持有锁时会调用 unbind_phone_from_user，后者也会请求锁。
        # 如果使用普通 Lock 会导致死锁，RLock 允许同一线程多次获取锁。
        self.lock = threading.RLock()
        logging.info("线程锁已创建（使用threading.RLock以防止递归死锁）")
        self._synchronize_super_admin_permissions()
        logging.info("AuthSystem初始化完成")
        logging.info("=" * 80)

    def _load_config(self):
        """加载配置文件（增强：处理错误并提示用户修复）"""
        logging.debug("_load_config: 开始加载配置文件...")
        try:
            _main()._create_config_ini()
        except configparser.DuplicateOptionError as e:
            logging.error(
                f"[系统初始化] 配置文件检查失败 --> 错误类型: {type(e).__name__}, 错误详情: {e}, 可能原因: 配置文件损坏或存在重复选项",
                exc_info=True,
            )
            print(
                f"\n[严重错误] 配置文件 ('{_main().CONFIG_FILE}') 已损坏。请修复上述提到的重复选项，然后重新启动程序。"
            )
            sys.exit(1)
        except Exception as e:
            logging.error(
                f"[系统初始化] 配置文件检查时发生未知错误 --> 错误类型: {type(e).__name__}, 错误详情: {e}",
                exc_info=True,
            )
            print(
                f"\n[严重错误] 检查配置文件 '{_main().CONFIG_FILE}' 时发生意外错误: {e}\n请检查文件格式是否正确，然后重新启动程序。"
            )
            sys.exit(1)

        config = configparser.ConfigParser(strict=False)
        config.optionxform = str
        try:
            config = _main()._read_config_ini(_main().CONFIG_FILE)
            logging.debug(
                f"_load_config: 配置文件加载完成，配置节: {list(config.sections())}"
            )
            return config
        except configparser.DuplicateOptionError as e:
            logging.error(
                f"加载配置文件 '{_main().CONFIG_FILE}' 失败，存在重复的配置项: {e}",
                exc_info=True,
            )
            print(f"\n{'='*60}")
            print(f"[配置文件错误] 无法加载 {_main().CONFIG_FILE} 文件！")
            print(
                f"  错误原因: 在区域 [{e.section}] 中发现重复的选项 '{e.option}' (不区分大小写)."
            )
            print(f"  错误位置: 大约在文件的第 {e.lineno} 行附近.")
            print(f"\n  请手动打开文件 '{_main().CONFIG_FILE}' 并进行以下操作:")
            print(f"    1. 找到 [{e.section}] 区域.")
            print(
                f"    2. 确保选项 '{e.option}' (例如 LastUser 或 lastuser) 只出现一次."
            )
            print(f"    3. 删除重复的那一行.")
            print(f"    4. 保存文件后重新运行程序.")
            print(f"{'='*60}\n")
            sys.exit(1)
        except Exception as e:
            logging.error(
                f"加载配置文件 '{_main().CONFIG_FILE}' 时发生未知错误: {e}", exc_info=True
            )
            print(f"\n[配置文件错误] 读取 config.ini 文件时发生意外错误: {e}")
            print(f"  请检查文件是否存在、是否有读取权限以及格式是否基本正确。")
            sys.exit(1)

    def reload_config(self):
        """
        重新加载配置文件

        功能说明：
        当配置文件被修改后，调用此方法重新加载配置，确保内存中的配置与文件一致。
        这样可以避免使用缓存的旧配置值。

        使用场景：
        - 管理员通过管理面板修改了 config.ini 文件
        - 外部脚本修改了配置文件
        - 需要立即应用新配置而不重启服务器

        线程安全：
        使用锁来确保在多线程环境下安全地重新加载配置

        返回值：
        无返回值。重新加载后，self.config 会指向新的配置对象
        """
        # [步骤1] 获取锁，确保线程安全
        # 避免在重新加载配置时，其他线程正在读取配置，导致数据不一致
        with self.lock:
            try:
                # [步骤2] 记录日志
                logging.info("[配置重载] 开始重新加载 config.ini 配置文件...")

                # [步骤3] 调用 _load_config 方法重新加载配置
                # 这会创建一个新的 ConfigParser 对象并读取最新的文件内容
                self.config = self._load_config()

                # [步骤4] 记录成功日志
                logging.info("[配置重载] 配置文件重新加载完成，当前配置节: {}".format(
                    list(self.config.sections())))

            except Exception as e:
                # [错误处理] 如果重新加载失败，记录错误日志
                # 保持旧的配置对象不变，确保系统仍能使用之前的配置运行
                logging.error(f"[配置重载] 重新加载配置文件失败: {str(e)}", exc_info=True)
                # 不抛出异常，让系统继续运行
                # 旧配置仍然有效，虽然不是最新的，但总比崩溃好

    def find_user_by_phone(self, phone):
        """
        遍历所有系统账号，查找绑定了特定手机号的用户。
        """
        accounts_dir = _main().SYSTEM_ACCOUNTS_DIR
        if not os.path.exists(accounts_dir):
            return None

        for filename in os.listdir(accounts_dir):
            if filename.endswith(".json"):
                user_file = os.path.join(accounts_dir, filename)
                try:
                    with open(user_file, "r", encoding="utf-8") as f:
                        user_data = json.load(f)
                        if user_data.get("phone") == phone:
                            return user_data.get("auth_username")
                except Exception:
                    continue
        return None

    def unbind_phone_from_user(self, phone, except_username=None):
        """
        查找绑定了指定手机号的用户，并将其手机号字段清空。
        """
        if not phone:
            return

        bound_username = self.find_user_by_phone(phone)

        if bound_username and bound_username != except_username:
            logging.info(
                f"[手机号解绑] 手机号 {phone} 原本绑定在 {bound_username}。正在解绑..."
            )
            user_file = self.get_user_file_path(bound_username)
            if os.path.exists(user_file):
                try:
                    with self.lock:
                        with open(user_file, "r", encoding="utf-8") as f:
                            user_data = json.load(f)

                        if user_data.get("phone") == phone:
                            user_data["phone"] = ""
                            with open(user_file, "w", encoding="utf-8") as f:
                                json.dump(user_data, f, indent=2,
                                          ensure_ascii=False)
                            logging.info(
                                f"[手机号解绑] 已成功解绑用户 {bound_username} 的手机号。"
                            )

                            self.log_audit(
                                "System",
                                "auto_unbind_phone",
                                f"因手机号 {phone} 被新用户注册或绑定，系统自动解绑了用户 {bound_username} 的手机号",
                            )
                except Exception as e:
                    logging.error(
                        f"[手机号解绑] 解绑用户 {bound_username} 手机号失败: {e}",
                        exc_info=True,
                    )

    def _load_permissions(self):
        """加载权限配置（修复：增强的容错处理）"""
        logging.debug(f"_load_permissions: 检查权限文件: {_main().PERMISSIONS_FILE}")

        default_perms = {"permission_groups": {}, "user_groups": {}}

        # 如果文件不存在，直接创建默认并返回
        if not os.path.exists(_main().PERMISSIONS_FILE):
            logging.debug("_load_permissions: 权限文件不存在，创建默认配置")
            _main()._create_permissions_json()
            try:
                with open(_main().PERMISSIONS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return default_perms

        # 文件存在，尝试安全读取
        try:
            with open(_main().PERMISSIONS_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()

            # 检查内容是否为空（处理只有换行符的情况）
            if not content:
                raise json.JSONDecodeError("文件内容为空", "", 0)

            perms = json.loads(content)
            logging.debug(
                f"_load_permissions: 权限配置已加载，权限组数: {len(perms.get('permission_groups', {}))}, 用户组数: {len(perms.get('user_groups', {}))}"
            )
            return perms

        except (json.JSONDecodeError, Exception) as e:
            logging.error(
                f"_load_permissions: 读取权限文件异常 ({type(e).__name__}): {e}"
            )
            logging.warning("检测到权限文件损坏或格式错误，正在备份并重建...")

            # 调用通用备份函数，备份损坏的权限文件
            # 使用default_perms（默认权限配置）作为重置内容
            _main()._backup_and_reset_corrupted_file(
                _main().PERMISSIONS_FILE,
                default_perms,
                "json"
            )

            # 强制清空重建，确保权限文件结构完整
            _main()._create_permissions_json(force=True)

            # 重建后尝试重新读取新文件，确保内存数据与文件一致
            try:
                with open(_main().PERMISSIONS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return default_perms

    def _ensure_builtin_permissions(self):
        """
        为已存在的 permissions.json 回填新增的内置权限键。

        背景:
            新增权限（如 view_school_account_passwords）只写进
            _create_permissions_json() 的默认模板时，**已存在**的
            permissions.json 不会自动获得该键。缺少键的组会被
            check_permission() 视为 False，导致管理员也无法使用新功能，
            且权限面板看不到该权限项。

        行为:
            - 只补齐 BUILTIN_PERMISSION_DEFAULTS 中声明、且组内**缺失**的键；
            - 绝不覆盖任何已有值（用户自定义调整不会被重置）；
            - 只处理内置组，不动自定义权限组；
            - 无变更时不写盘。
        """
        try:
            groups = self.permissions.get("permission_groups")
            if not isinstance(groups, dict):
                return

            changed = False
            backfilled = {}
            for permission, group_defaults in BUILTIN_PERMISSION_DEFAULTS.items():
                for group_name, default_value in group_defaults.items():
                    group_info = groups.get(group_name)
                    if not isinstance(group_info, dict):
                        continue
                    # 只处理内置组，避免给自定义组强加语义
                    if group_info.get("is_system") is False:
                        continue
                    perms = group_info.get("permissions")
                    if not isinstance(perms, dict):
                        continue
                    if permission in perms:
                        continue
                    perms[permission] = default_value
                    changed = True
                    backfilled.setdefault(permission, {})[group_name] = default_value

            if changed:
                self._save_permissions()
                logging.info(
                    f"[权限配置] 已回填新增内置权限键: {backfilled}"
                )
        except Exception as e:
            # 回填失败不能阻断启动：缺少键时按 False 处理是安全的
            logging.error(
                f"[权限配置] 回填内置权限键失败: {e}", exc_info=True
            )

    def _save_permissions(self):
        """保存权限配置"""
        logging.debug("_save_permissions: 保存权限配置到文件...")
        with open(_main().PERMISSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.permissions, f, indent=2, ensure_ascii=False)
        logging.debug(f"_save_permissions: 权限配置已保存到 {_main().PERMISSIONS_FILE}")

    def get_user_theme_file_path(self, auth_username):
        """获取用户主题配置文件路径（存储到 system_accounts）"""
        return self.get_user_file_path(auth_username)

    def _deep_merge_theme_config(self, base_config, override_config):
        """递归合并主题配置"""
        if not isinstance(base_config, dict):
            base_config = {}
        if not isinstance(override_config, dict):
            return dict(base_config)

        merged = dict(base_config)
        for key, value in override_config.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge_theme_config(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _read_theme_definition(self, style_id):
        """读取主题定义文件"""
        normalized_style = str(style_id or "default").strip() or "default"
        file_stem = normalized_style
        if normalized_style.startswith("theme-"):
            file_stem = normalized_style[6:]

        theme_path = os.path.join(os.path.dirname(__file__), _main().THEME_DIR, f"{file_stem}.json")
        if not os.path.exists(theme_path):
            return {}

        try:
            with open(theme_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logging.warning(f"读取主题定义失败 {theme_path}: {e}")
            return {}

    def _build_theme_background_image_url(self, relative_path):
        return _main()._build_theme_background_image_url(relative_path)

    def _get_random_background_cache_limit_bytes(self):
        try:
            config = _main()._read_config_ini(_main().CONFIG_JSON_FILE) or _main()._get_default_config()
            limit_mb = config.getint(
                "Logging", "random_background_cache_max_size_mb", fallback=1024
            )
            if limit_mb <= 0:
                return 0
            return limit_mb * 1024 * 1024
        except Exception as e:
            logging.warning(f"[主题背景] 读取背景缓存上限失败，使用默认值 1024MB: {e}")
            return 1024 * 1024 * 1024

    @background_files_locked
    def _get_cached_random_background_image_urls(self, cache_dir, image_type, limit=5):
        try:
            _main()._cleanup_random_background_index(cache_dir)
            candidates = []
            for file_name in os.listdir(cache_dir):
                file_path = os.path.join(cache_dir, file_name)
                if not is_background_image_file(cache_dir, file_name, image_type):
                    continue
                entry, normalized_name = _main()._get_random_background_index_entry(cache_dir, file_name)
                if not normalized_name or (entry and entry.get("expired")):
                    continue
                try:
                    stat = os.stat(file_path)
                except OSError:
                    continue
                created_at = entry.get("created_at") if isinstance(entry, dict) else None
                sort_key = stat.st_mtime
                if created_at:
                    try:
                        sort_key = datetime.datetime.fromisoformat(str(created_at)).timestamp()
                    except (TypeError, ValueError):
                        sort_key = stat.st_mtime
                candidates.append((float(sort_key), normalized_name))

            if not candidates:
                return []

            candidates.sort(key=lambda item: item[0])
            urls = []
            selected_candidates = candidates if int(limit or 0) <= 0 else candidates[:max(int(limit or 0), 1)]
            for _, file_name in selected_candidates:
                urls.append(
                    self._build_theme_background_image_url(
                        f"{_main().RANDOM_BACKGROUND_IMAGE_DIR}/{file_name}"
                    )
                )
            return urls
        except Exception as e:
            background_files_log(logging.WARNING, f"[主题背景] 读取 {image_type} 背景缓存失败: {e}")
            return []

    @background_files_locked
    def _get_cached_random_background_image_url(self, cache_dir, image_type, random_pick=False):
        cached_urls = self._get_cached_random_background_image_urls(cache_dir, image_type, limit=0)
        if not cached_urls:
            return ""
        if random_pick and len(cached_urls) > 1:
            with _main()._BACKGROUND_SELECTION_LOCK:
                previous_url = _main()._BACKGROUND_SELECTION_STATE.get(image_type)
                available_urls = [url for url in cached_urls if url != previous_url]
                selected_url = secrets.choice(available_urls or cached_urls)
                _main()._BACKGROUND_SELECTION_STATE[image_type] = selected_url
                return selected_url
        return cached_urls[0]

    def _peek_cached_random_background_image_url(self, cache_dir, image_type):
        return self._get_cached_random_background_image_url(cache_dir, image_type, random_pick=True)

    @background_files_locked
    def _consume_cached_random_background_image_url(self, cache_dir, image_type):
        selected_url = self._get_cached_random_background_image_url(cache_dir, image_type, random_pick=True)
        if selected_url:
            _main()._mark_random_background_file_expired(cache_dir, selected_url, expired=True)
        return selected_url

    @background_files_locked
    def _consume_default_theme_background_images(self, targets=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(base_dir, _main().RANDOM_BACKGROUND_IMAGE_DIR)
        os.makedirs(cache_dir, exist_ok=True)

        normalized_targets = []
        for target in (targets or ["pc", "mobile"]):
            if target == "mobile":
                normalized_targets.append(("mobile", "mb"))
            elif target == "pc":
                normalized_targets.append(("pc", "pc"))

        if not normalized_targets:
            normalized_targets = [("pc", "pc"), ("mobile", "mb")]

        background_image_urls = {}
        refresh_image_types = []
        for key, image_type in normalized_targets:
            background_image_urls[key] = self._consume_cached_random_background_image_url(cache_dir, image_type)
            refresh_image_types.append(image_type)

        self._refresh_default_theme_background_cache_async(refresh_image_types)
        return background_image_urls

    @background_files_locked
    def _peek_default_theme_background_images(self, targets=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(base_dir, _main().RANDOM_BACKGROUND_IMAGE_DIR)
        os.makedirs(cache_dir, exist_ok=True)

        normalized_targets = []
        for target in (targets or ["pc", "mobile"]):
            if target == "mobile":
                normalized_targets.append(("mobile", "mb"))
            elif target == "pc":
                normalized_targets.append(("pc", "pc"))

        if not normalized_targets:
            normalized_targets = [("pc", "pc"), ("mobile", "mb")]

        background_image_urls = {}
        for key, image_type in normalized_targets:
            background_image_urls[key] = self._peek_cached_random_background_image_url(cache_dir, image_type)

        return background_image_urls

    def _cleanup_random_background_cache(self, cache_dir, max_cache_size_bytes=None):
        _main()._cleanup_random_background_cache(cache_dir, max_cache_size_bytes)

    def _fetch_random_background_image(self, cache_dir, api_key, image_type):
        return _main()._fetch_random_background_image(cache_dir, api_key, image_type)

    def _ensure_background_cache_count(self, cache_dir, api_key, image_type, target_count=5):
        logging.info(f"[主题背景] 确保 {image_type} 背景缓存数量至少为 {target_count} 张...")
        target_count = max(int(target_count or 0), 0)
        if target_count == 0:
            logging.info(f"[主题背景] 目标缓存数量为 0，跳过 {image_type} 背景缓存检查")
            return

        cached_urls = self._get_cached_random_background_image_urls(
            cache_dir, image_type, limit=target_count
        )
        missing_count = target_count - len(cached_urls)
        logging.info(f"[主题背景] {image_type} 背景缓存缺失 {missing_count} 张")
        for _ in range(missing_count):
            try:
                logging.info(f"[主题背景] 正在拉取新的 {image_type} 随机背景图以补足缓存...")
                self._fetch_random_background_image(cache_dir, api_key, image_type)
            except Exception as e:
                logging.warning(f"[主题背景] 补足 {image_type} 背景缓存失败: {e}")
                break
            logging.info(f"[主题背景] 已完成一次 {image_type} 背景图拉取尝试以补足缓存")
        logging.info(f"[主题背景] 已完成 {image_type} 背景缓存检查，当前缓存数量: {len(self._get_cached_random_background_image_urls(cache_dir, image_type))} 张")

    def _ensure_default_theme_background_cache(self):
        logging.info("[主题背景] 正在预下载默认主题背景缓存...")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(base_dir, _main().RANDOM_BACKGROUND_IMAGE_DIR)
        os.makedirs(cache_dir, exist_ok=True)

        config = _main()._read_config_ini(_main().CONFIG_JSON_FILE) or _main()._get_default_config()
        api_key = config.get("IP_Location", "uapipro_api_key", fallback="").strip()
        if not api_key:
            logging.info("[主题背景] 未配置 UapiPro API Key，跳过预下载缓存")
            return

        for image_type in ("pc", "mb"):
            self._ensure_background_cache_count(cache_dir, api_key, image_type, target_count=_main().BACKGROUND_CACHE_TARGET_COUNT)

    def _refresh_default_theme_background_cache_async(self, image_types=None):
        main_module = _main()
        with _main()._THEME_BACKGROUND_REFRESH_LOCK:
            if main_module._THEME_BACKGROUND_REFRESH_IN_PROGRESS:
                return
            main_module._THEME_BACKGROUND_REFRESH_IN_PROGRESS = True

        normalized_image_types = []
        for image_type in (image_types or ["pc", "mb"]):
            normalized_type = str(image_type or "").strip().lower()
            if normalized_type in ("pc", "mb") and normalized_type not in normalized_image_types:
                normalized_image_types.append(normalized_type)
        if not normalized_image_types:
            normalized_image_types = ["pc", "mb"]

        def _worker():
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                cache_dir = os.path.join(base_dir, _main().RANDOM_BACKGROUND_IMAGE_DIR)
                os.makedirs(cache_dir, exist_ok=True)

                config = _main()._read_config_ini(_main().CONFIG_JSON_FILE) or _main()._get_default_config()
                api_key = config.get("IP_Location", "uapipro_api_key", fallback="").strip()
                if not api_key:
                    return

                for image_type in normalized_image_types:
                    self._ensure_background_cache_count(
                        cache_dir,
                        api_key,
                        image_type,
                        target_count=_main().BACKGROUND_CACHE_TARGET_COUNT,
                    )
            except Exception as e:
                logging.warning(f"[主题背景] 异步刷新背景缓存失败: {e}")
            finally:
                with main_module._THEME_BACKGROUND_REFRESH_LOCK:
                    main_module._THEME_BACKGROUND_REFRESH_IN_PROGRESS = False

        threading.Thread(target=_worker, daemon=True).start()

    @background_files_locked
    def _resolve_default_theme_background_images(self, targets=None, session_uuid="", cache_dir=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        effective_cache_dir = cache_dir or os.path.join(base_dir, _main().RANDOM_BACKGROUND_IMAGE_DIR)
        os.makedirs(effective_cache_dir, exist_ok=True)

        bound_images = _main()._resolve_bound_theme_background_images(
            effective_cache_dir,
            session_uuid=session_uuid,
            targets=targets,
        )
        random_images = self._peek_default_theme_background_images(targets)

        resolved_images = dict(random_images) if isinstance(random_images, dict) else {}
        for target, image_url in bound_images.items():
            if image_url:
                resolved_images[target] = image_url
        return resolved_images

    def _inject_default_theme_background_image(
        self,
        merged_config,
        style_id,
        targets=None,
        session_uuid="",
        cache_dir=None,
    ):
        normalized_style = str(style_id or "default").strip() or "default"
        if normalized_style != "default":
            return merged_config

        config = dict(merged_config) if isinstance(merged_config, dict) else {}
        env = config.get("global_environment_variables")
        if not isinstance(env, dict):
            env = {}
            config["global_environment_variables"] = env

        background_image_urls = self._resolve_default_theme_background_images(
            targets,
            session_uuid=session_uuid,
            cache_dir=cache_dir,
        )
        pc_background_image_url = background_image_urls.get("pc", "")
        mobile_background_image_url = background_image_urls.get("mobile", "")
        if not pc_background_image_url and not mobile_background_image_url:
            return config

        if pc_background_image_url:
            env["auth_login_container_background"] = (
                "linear-gradient(rgba(255,255,255,0.10), rgba(255,255,255,0.10)), "
                f'url("{pc_background_image_url}") center / cover no-repeat fixed'
            )

        if mobile_background_image_url:
            env["mobile_auth_login_content_background"] = (
                "linear-gradient(rgba(255,255,255,0.12), rgba(255,255,255,0.12)), "
                f'url("{mobile_background_image_url}") center / cover no-repeat'
            )
        else:
            env.setdefault("mobile_auth_login_content_background", "")

        env.setdefault("mobile_auth_login_card_background", "rgba(255,255,255,0.58)")

        env.setdefault("auth_login_panel_background", "rgba(255,255,255,0.52)")
        env.setdefault("auth_login_panel_shadow", "0 20px 60px rgba(15,23,42,0.12)")
        env.setdefault("auth_login_panel_border", "rgba(255,255,255,0.24)")
        env.setdefault("mobile_auth_login_card_shadow", "0 18px 48px rgba(15,23,42,0.12)")
        return config

    def get_theme_config(self, style_id, targets=None, session_uuid="", cache_dir=None):
        """读取主题配置，默认先加载 default 再叠加目标主题"""
        default_config = self._read_theme_definition("default")
        normalized_style = str(style_id or "default").strip() or "default"
        if normalized_style == "default":
            merged_config = self._deep_merge_theme_config({}, default_config)
        else:
            merged_config = self._deep_merge_theme_config(
                default_config,
                self._read_theme_definition(normalized_style),
            )

        basic_information = merged_config.get("basic_information")
        if not isinstance(basic_information, dict):
            basic_information = {}

        basic_information["id"] = str(basic_information.get("id") or normalized_style).strip() or "default"
        basic_information["label"] = str(
            basic_information.get("label") or basic_information["id"]
        ).strip()
        basic_information["description"] = str(
            basic_information.get("description") or ""
        ).strip()
        basic_information["svg"] = str(basic_information.get("svg") or "").strip()
        merged_config["basic_information"] = basic_information

        global_environment_variables = merged_config.get("global_environment_variables")
        if not isinstance(global_environment_variables, dict):
            global_environment_variables = {}
        merged_config["global_environment_variables"] = global_environment_variables
        merged_config = self._inject_default_theme_background_image(
            merged_config,
            normalized_style,
            targets,
            session_uuid=session_uuid,
            cache_dir=cache_dir,
        )

        return merged_config

    def get_available_theme_styles(self):
        """从 ./theme 目录扫描主题定义文件"""
        theme_dir = os.path.join(os.path.dirname(__file__), _main().THEME_DIR)

        with self.lock:
            if not os.path.isdir(theme_dir):
                return []

            try:
                theme_files = sorted(
                    file_name
                    for file_name in os.listdir(theme_dir)
                    if file_name.lower().endswith(".json")
                )
            except Exception as e:
                logging.warning(f"读取主题目录失败 {theme_dir}: {e}")
                return []

            valid_styles = []
            for file_name in theme_files:
                style_id = os.path.splitext(file_name)[0]
                if style_id != "default":
                    style_id = f"theme-{style_id}"

                merged_config = self.get_theme_config(style_id)
                basic_information = merged_config.get("basic_information")
                if not isinstance(basic_information, dict):
                    continue

                theme_id = str(basic_information.get("id") or style_id).strip()
                if not theme_id:
                    continue

                valid_styles.append(
                    {
                        "id": theme_id,
                        "label": str(basic_information.get("label") or theme_id).strip(),
                        "description": str(basic_information.get("description") or "").strip(),
                        "svg": str(basic_information.get("svg") or "").strip(),
                        "global_environment_variables": merged_config.get(
                            "global_environment_variables", {}
                        ),
                    }
                )

        return valid_styles

    def get_user_file_path(self, auth_username):
        """获取用户文件路径"""
        # 修复: 强制转换为字符串，防止传入 int 类型导致 'int' object has no attribute 'encode'
        user_hash = hashlib.sha256(str(auth_username).encode()).hexdigest()
        file_path = os.path.join(_main().SYSTEM_ACCOUNTS_DIR, f"{user_hash}.json")
        logging.debug(
            f"get_user_file_path: 用户 {auth_username} 的文件路径: {file_path}"
        )
        return file_path

    # 补充缺失的辅助方法，用于 delete_user 备份
    def _get_user_accounts_file(self, auth_username):
        """获取用户的 school_accounts 文件路径"""
        user_accounts_dir = os.path.join(_main().SCHOOL_ACCOUNTS_DIR, "user_accounts")
        storage_key = _main()._auth_username_storage_key(auth_username)
        return os.path.join(user_accounts_dir, f"{storage_key}.json")

    def _load_user_school_accounts(self, auth_username):
        """加载认证用户绑定的学校账号。"""
        if not auth_username or auth_username == "guest":
            return {}

        user_accounts_file = self._get_user_accounts_file(auth_username)
        if not os.path.exists(user_accounts_file):
            return {}

        try:
            with open(user_accounts_file, "r", encoding="utf-8") as f:
                accounts = json.load(f)
        except Exception as e:
            logging.error(
                f"[用户学校账号] 读取用户 {auth_username} 的学校账号文件失败: {e}",
                exc_info=True,
            )
            return {}

        if isinstance(accounts, dict):
            return accounts

        logging.warning(
            f"[用户学校账号] 用户 {auth_username} 的学校账号文件格式无效，已按空账号处理"
        )
        return {}

    def _update_user_file_group(self, username, new_group):
        """
        (辅助函数) 更新 system_accounts 中用户JSON文件内的 group 字段。
        这确保了 permissions.json 和用户文件之间的数据一致性。
        """
        user_file = self.get_user_file_path(username)
        if os.path.exists(user_file):
            try:
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)

                if user_data.get("group") != new_group:
                    user_data["group"] = new_group
                    with open(user_file, "w", encoding="utf-8") as f:
                        json.dump(user_data, f, indent=2, ensure_ascii=False)
                    logging.debug(
                        f"[权限同步] 已更新用户文件 {os.path.basename(user_file)} 的权限组为 {new_group}"
                    )
                    return True
            except Exception as e:
                logging.error(
                    f"[权限同步] 更新用户文件 {os.path.basename(user_file)} 失败: {e}",
                    exc_info=True,
                )
        else:
            logging.warning(
                f"[权限同步] 找不到用户 {username} 的文件，无法更新其文件内的权限组。"
            )
        return False

    def _get_password_storage_method(self):
        """
        获取密码存储方式配置。
        """
        method = self.config.get(
            "Security", "password_storage", fallback="plaintext")
        logging.debug(f"_get_password_storage_method: 密码存储方式: {method}")
        return method

    def _encrypt_password(self, password):
        """
        加密密码（根据配置决定是否加密）。
        """
        method = self._get_password_storage_method()
        logging.debug(
            f"[密码加密] 开始处理密码加密 --> 加密方法: {method}, 密码长度: {len(password)}字符"
        )

        if method == "_main().bcrypt":
            try:

                salt = _main().bcrypt.gensalt()
                hashed = _main().bcrypt.hashpw(password.encode("utf-8"), salt)
                encrypted = hashed.decode("utf-8")
                logging.debug(
                    f"[密码加密] 密码已使用_main().bcrypt加密 --> 哈希长度: {len(encrypted)}字符, 哈希前缀: {encrypted[:7]}... (✓ 安全: 自动加盐，抗暴力破解)"
                )
                return encrypted
            except ImportError:
                logging.error(
                    "[密码加密] _main().bcrypt库未安装，无法使用_main().bcrypt加密。请运行: pip install _main().bcrypt"
                )
                logging.warning("[密码加密] 降级使用SHA256加密（不安全）")
                method = "encrypted"

        if method == "encrypted":
            encrypted = hashlib.sha256(password.encode()).hexdigest()
            logging.debug(
                f"[密码加密] 密码已使用SHA256加密 --> 哈希长度: {len(encrypted)}字符, 哈希值前8位: {encrypted[:8]}... (⚠️ 警告: SHA256不加盐存在安全风险，建议迁移到_main().bcrypt)"
            )
            return encrypted

        logging.warning(
            f"[密码加密] 使用明文存储密码 --> ⚠️ 严重安全警告: 明文密码存储极度不安全，强烈建议使用_main().bcrypt模式"
        )
        return password

    def _verify_password(self, input_password, stored_password):
        """
        验证用户输入的密码是否正确。
        """
        logging.debug(
            f"[密码验证] 开始验证密码 --> 输入密码长度: {len(input_password)}字符, 存储密码长度: {len(stored_password)}字符"
        )

        if stored_password.startswith("$2b$") or stored_password.startswith("$2a$"):
            try:

                result = _main().bcrypt.checkpw(
                    input_password.encode(
                        "utf-8"), stored_password.encode("utf-8")
                )
                logging.debug(
                    f"[密码验证] _main().bcrypt验证完成 --> 验证结果: {'✓ 成功' if result else '✗ 失败'} (✓ 安全: 使用_main().bcrypt.checkpw，防时序攻击)"
                )
                return result
            except ImportError:
                logging.error("[密码验证] _main().bcrypt库未安装，无法验证_main().bcrypt密码")
                return False
            except Exception as e:
                logging.error(f"[密码验证] _main().bcrypt验证失败 --> 错误: {e}")
                return False

        elif len(stored_password) == 64 and all(
            c in "0123456789abcdef" for c in stored_password.lower()
        ):
            input_hash = hashlib.sha256(input_password.encode()).hexdigest()
            result = secrets.compare_digest(input_hash, stored_password)
            logging.debug(
                f"[密码验证] SHA256哈希验证完成 --> 输入密码哈希前8位: {input_hash[:8]}..., 存储密码哈希前8位: {stored_password[:8]}..., 验证结果: {'✓ 成功' if result else '✗ 失败'} (✓ 安全: 使用secrets.compare_digest防时序攻击)"
            )
            return result

        else:
            result = secrets.compare_digest(input_password, stored_password)
            logging.warning(
                f"[密码验证] 明文密码验证完成 --> 验证结果: {'✓ 成功' if result else '✗ 失败'}"
            )
            return result

    def _log_login_attempt(
        self, auth_username, success, ip_address="", user_agent="", reason=""
    ):
        """
        记录用户登录尝试到日志文件。
        """
        logging.info(
            f"[登录审计] 登录尝试记录 --> 用户名: {auth_username}, 登录结果: {'✓ 成功' if success else '✗ 失败'}, 客户端IP: {ip_address}, User-Agent: {user_agent[:50]}{'...' if len(user_agent) > 50 else ''}, {'失败原因: ' + reason if not success else '登录成功'}"
        )

        log_entry = {
            "timestamp": time.time(),
            "datetime": datetime.datetime.now().isoformat(),
            "username": auth_username,
            "success": success,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "reason": reason,
        }

        try:
            with open(_main().LOGIN_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            logging.debug(
                f"[登录审计] 登录日志已写入文件 --> 文件路径: {_main().LOGIN_LOG_FILE}, 用户: {auth_username}, 时间戳: {log_entry['timestamp']}, 格式: JSONL (每行一个JSON对象)"
            )
        except Exception as e:
            logging.error(
                f"[登录审计] 写入登录日志失败 --> 目标文件: {_main().LOGIN_LOG_FILE}, 用户: {auth_username}, 错误类型: {type(e).__name__}, 错误详情: {e}, 注意: 日志写入失败不影响登录流程继续执行",
                exc_info=True,
            )

    def get_login_history(self, username=None, limit=100):
        """获取登录历史 - 优化：避免加载所有记录到内存"""
        if not os.path.exists(_main().LOGIN_LOG_FILE):
            return []

        history = collections.deque(maxlen=limit * 2)

        try:
            with open(_main().LOGIN_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if username is None or entry.get("username") == username:
                            history.append(entry)
                    except json.JSONDecodeError as e:
                        logging.warning(
                            f"[登录审计] 跳过损坏的日志行 --> 行内容: {line.strip()[:100]}{'...' if len(line.strip()) > 100 else ''}, JSON解析错误: {e}"
                        )
                        continue
                    except Exception as e:
                        logging.warning(
                            f"[登录审计] 处理日志行时发生错误 --> 行内容: {line.strip()[:100]}{'...' if len(line.strip()) > 100 else ''}, 错误类型: {type(e).__name__}, 错误详情: {e}"
                        )
                        continue
        except Exception as e:
            logging.error(
                f"[登录审计] 读取登录历史失败 --> 文件路径: {_main().LOGIN_LOG_FILE}, 查询用户: {username if username else '全部'}, 限制条数: {limit}, 错误类型: {type(e).__name__}, 错误详情: {e}",
                exc_info=True,
            )

        result = list(history)[-limit:]
        return result

    def check_brute_force(self, auth_username, ip_address):
        """检查暴力破解（5分钟内最多5次失败）- 优化：找到足够记录后提前退出"""
        recent_attempts = []
        current_time = time.time()
        cutoff_time = current_time - 300
        MAX_ATTEMPTS = 5

        if os.path.exists(_main().LOGIN_LOG_FILE):
            try:
                with open(_main().LOGIN_LOG_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            if entry.get("timestamp", 0) > cutoff_time:
                                if (
                                    entry.get("username") == auth_username
                                    or entry.get("ip_address") == ip_address
                                ):
                                    if not entry.get("success", False):
                                        recent_attempts.append(entry)
                                        if len(recent_attempts) >= MAX_ATTEMPTS:
                                            return (
                                                True,
                                                "登录失败次数过多，请5分钟后再试",
                                            )
                        except json.JSONDecodeError as e:
                            logging.debug(
                                f"[安全检查] 暴力破解检查时跳过损坏的日志行 --> JSON解析错误: {e}"
                            )
                            continue
                        except Exception as e:
                            logging.debug(
                                f"[安全检查] 暴力破解检查时处理日志行错误 --> 错误类型: {type(e).__name__}, 错误详情: {e}"
                            )
                            continue
            except Exception as e:
                logging.error(
                    f"[安全检查] 检查暴力破解失败 --> 目标用户: {auth_username}, IP地址: {ip_address}, 时间窗口: 5分钟, 错误类型: {type(e).__name__}, 错误详情: {e}",
                    exc_info=True,
                )

        return False, ""

    def generate_2fa_secret(self, auth_username):
        """生成2FA密钥"""
        try:

            secret = _main().pyotp.random_base32()

            user_file = self.get_user_file_path(auth_username)
            if os.path.exists(user_file):
                with self.lock:
                    with open(user_file, "r", encoding="utf-8") as f:
                        user_data = json.load(f)

                    user_data["2fa_secret"] = secret
                    user_data["2fa_enabled"] = False

                    with open(user_file, "w", encoding="utf-8") as f:
                        json.dump(user_data, f, indent=2, ensure_ascii=False)

                totp = _main().pyotp.TOTP(secret)
                uri = totp.provisioning_uri(
                    name=auth_username, issuer_name="Zelly's Personal Assistant Tools"
                )
                return {"success": True, "secret": secret, "qr_uri": uri}
            return {"success": False, "message": "用户不存在"}
        except ImportError:
            return {
                "success": False,
                "message": "2FA功能需要安装_main().pyotp库：pip install _main().pyotp",
            }

    def enable_2fa(self, auth_username, verification_code):
        """启用2FA（需要验证一次）"""
        try:

            user_file = self.get_user_file_path(auth_username)
            if os.path.exists(user_file):
                with self.lock:
                    with open(user_file, "r", encoding="utf-8") as f:
                        user_data = json.load(f)

                    secret = user_data.get("2fa_secret")
                    if not secret:
                        return {"success": False, "message": "请先生成2FA密钥"}

                    totp = _main().pyotp.TOTP(secret)
                    if totp.verify(verification_code):
                        user_data["2fa_enabled"] = True
                        with open(user_file, "w", encoding="utf-8") as f:
                            json.dump(user_data, f, indent=2,
                                      ensure_ascii=False)
                        return {"success": True, "message": "2FA已启用"}
                    return {"success": False, "message": "验证码错误"}
            return {"success": False, "message": "用户不存在"}
        except ImportError:
            return {"success": False, "message": "2FA功能需要安装_main().pyotp库"}

    def verify_2fa(self, auth_username, verification_code):
        """验证2FA代码"""
        try:

            user_file = self.get_user_file_path(auth_username)
            if os.path.exists(user_file):
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)

                if not user_data.get("2fa_enabled", False):
                    return False

                secret = user_data.get("2fa_secret")
                if not secret:
                    return False

                totp = _main().pyotp.TOTP(secret)
                return totp.verify(verification_code)
            return False
        except ImportError:
            logging.warning("2FA验证失败：_main().pyotp库未安装")
            return False

    def register_user(
        self,
        auth_username,
        auth_password,
        group="user",
        phone="",
        nickname="",
        avatar_url="",
    ):
        """
        注册新用户（已升级支持扩展字段）
        """
        if not _main()._is_safe_auth_username(auth_username):
            return {"success": False, "message": "用户名格式不正确"}
        logging.info(f"register_user: 开始注册新用户: {auth_username}, 权限组: {group}")
        print(f"[用户注册] 开始注册新用户: {auth_username}, 权限组: {group}")
        with self.lock:
            if phone:
                self.unbind_phone_from_user(
                    phone, except_username=auth_username)
            user_file = self.get_user_file_path(auth_username)
            logging.debug(f"register_user: 检查用户文件是否存在: {user_file}")
            if os.path.exists(user_file):
                logging.warning(f"register_user: 用户名已存在: {auth_username}")
                print(f"[用户注册] 用户名已存在: {auth_username}")
                return {"success": False, "message": "用户名已存在"}

            logging.debug(f"register_user: 加密密码...")
            print(f"[用户注册] 加密密码...")
            stored_password = self._encrypt_password(auth_password)

            user_data = {
                "auth_username": auth_username,
                "password": stored_password,
                "group": group,
                "created_at": time.time(),
                "last_login": None,
                "session_ids": [],
                "2fa_enabled": False,
                "2fa_secret": None,
                "avatar_url": avatar_url or "default_avatar.png",
                "max_sessions": 1,
                "theme": "light",
                "phone": phone,
                "nickname": nickname or auth_username,
                "available_runs": self.config.getint(
                    "Payment_Settings", "default_available_runs", fallback=10
                ),
            }

            logging.debug(f"register_user: 保存用户数据到文件: {user_file}")
            print(f"[用户注册] 保存用户数据到文件...")
            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

            # 更新 system_accounts/_index.json 索引
            user_hash = hashlib.sha256(str(auth_username).encode()).hexdigest()
            _main()._update_system_accounts_index(auth_username, user_hash, "add")

            logging.debug(f"register_user: 添加用户到权限组: {group}")
            self.permissions["user_groups"][auth_username] = group
            self._save_permissions()

            logging.info(
                f"新用户注册: {auth_username} (组: {group}, 手机: {phone}, 昵称: {nickname}，头像: {avatar_url}），可用运行次数: {user_data['available_runs']}"
            )
            print(f"[用户注册] ✓ 用户注册成功: {auth_username} (组: {group})")
            return {"success": True, "message": "注册成功"}

    def authenticate(
        self, auth_username, auth_password, ip_address="", user_agent="", two_fa_code=""
    ):
        """验证用户登录（支持2FA和暴力破解防护）"""
        logging.info(
            f"authenticate: 开始认证用户: {auth_username}, IP: {ip_address}")
        print(f"[用户认证] 开始认证用户: {auth_username}, IP: {ip_address}")
        with self.lock:
            if auth_username == "guest" and self.config.getboolean(
                "Guest", "allow_guest_login", fallback=True
            ):
                logging.info(f"authenticate: 游客登录成功: {auth_username}")
                print(f"[用户认证] 游客登录成功: {auth_username}")
                self._log_login_attempt(
                    auth_username, True, ip_address, user_agent, "guest_login"
                )
                return {
                    "success": True,
                    "auth_username": "guest",
                    "group": "guest",
                    "is_guest": True,
                }

            logging.debug(f"authenticate: 检查暴力破解防护: {auth_username}")
            print(f"[用户认证] 检查暴力破解: {auth_username}")
            is_locked, lock_message = self.check_brute_force(
                auth_username, ip_address)
            if is_locked:
                logging.warning(
                    f"authenticate: 用户被锁定（暴力破解防护）: {auth_username}"
                )
                print(f"[用户认证] 用户被锁定（暴力破解防护）: {auth_username}")
                self._log_login_attempt(
                    auth_username, False, ip_address, user_agent, "brute_force_locked"
                )
                return {"success": False, "message": lock_message}

            user_file = self.get_user_file_path(auth_username)
            logging.debug(f"authenticate: 检查用户文件: {user_file}")
            if not os.path.exists(user_file):
                logging.warning(f"authenticate: 用户不存在: {auth_username}")
                print(f"[用户认证] 用户不存在: {auth_username}")
                self._log_login_attempt(
                    auth_username, False, ip_address, user_agent, "user_not_found"
                )
                return {"success": False, "message": "用户不存在"}

            logging.debug(f"authenticate: 读取用户数据: {auth_username}")
            print(f"[用户认证] 读取用户数据: {auth_username}")
            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            if user_data.get("banned", False):
                logging.warning(f"authenticate: 用户已被封禁: {auth_username}")
                print(f"[用户认证] 用户已被封禁: {auth_username}")
                self._log_login_attempt(
                    auth_username, False, ip_address, user_agent, "user_banned"
                )
                return {"success": False, "message": "账号已被封禁，请联系管理员"}

            logging.debug(f"authenticate: 验证密码: {auth_username}")
            print(f"[用户认证] 验证密码: {auth_username}")
            if not self._verify_password(auth_password, user_data.get("password")):
                logging.warning(f"authenticate: 密码错误: {auth_username}")
                print(f"[用户认证] 密码错误: {auth_username}")
                self._log_login_attempt(
                    auth_username, False, ip_address, user_agent, "wrong_password"
                )
                return {"success": False, "message": "密码错误"}

            if user_data.get("2fa_enabled", False):
                logging.debug(f"authenticate: 检查2FA验证: {auth_username}")
                print(f"[用户认证] 检查2FA验证: {auth_username}")
                if not two_fa_code:
                    logging.info(f"authenticate: 需要2FA验证码: {auth_username}")
                    print(f"[用户认证] 需要2FA验证码: {auth_username}")
                    return {
                        "success": True,
                        "message": "需要2FA验证码",
                        "requires_2fa": True,
                        "auth_username": auth_username,
                    }

                if not self.verify_2fa(auth_username, two_fa_code):
                    logging.warning(f"authenticate: 2FA验证失败: {auth_username}")
                    print(f"[用户认证] 2FA验证失败: {auth_username}")
                    self._log_login_attempt(
                        auth_username, False, ip_address, user_agent, "2fa_failed"
                    )
                    return {"success": False, "message": "2FA验证码错误"}

            logging.debug(f"authenticate: 更新最后登录时间: {auth_username}")
            print(f"[用户认证] 更新最后登录时间: {auth_username}")
            user_data["last_login"] = time.time()
            user_data["last_login_ip"] = ip_address
            if "session_ids" not in user_data:
                user_data["session_ids"] = []

            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

            super_admin = self.config.get(
                "Admin", "super_admin", fallback="admin")
            if auth_username == super_admin:
                group = "super_admin"
            else:
                group = user_data.get("group", "user")

            self._log_login_attempt(
                auth_username, True, ip_address, user_agent, "success"
            )
            logging.info(
                f"用户登录: {auth_username} (组: {group}) from {ip_address}")
            print(f"[用户认证] ✓ 用户登录成功: {auth_username} (组: {group})")
            logging.info(f"authenticate: ✓ 认证成功，返回用户信息")
            return {
                "success": True,
                "auth_username": auth_username,
                "group": group,
                "is_guest": False,
                "max_sessions": user_data.get("max_sessions", 1),
                "avatar_url": user_data.get("avatar_url") or "default_avatar.png",
                "theme": user_data.get("theme", "light"),
                "session_ids": user_data.get("session_ids", []),
            }

    def resolve_password_visibility(self, auth_username):
        """
        解析调用者的"学校账号密码可见级别"。

        密码可见性共三档（高 → 低）：
            "all"  —— 持有 auto_fill_password（或属于管理员组）：
                      可查看**所有**认证用户的所有学校账号密码。
            "own"  —— 持有 view_school_account_passwords：
                      仅可查看**当前登录系统账号自己关联**的学校账号密码。
            "none" —— 两者皆无：不返回任何密码字段。

        返回值:
            str: "all" / "own" / "none"

        异常处理:
            权限数据读取异常时回退为 "none"（安全默认值），
            并与 check_permission 保持一致的判定口径。
        """
        try:
            group = self.get_user_group(auth_username)

            # 管理员组天然拥有全量可见性（与 get_initial_data 的既有判定一致）
            if group in ("admin", "super_admin"):
                return PASSWORD_VISIBILITY_ALL

            if self.check_permission(auth_username, "auto_fill_password"):
                return PASSWORD_VISIBILITY_ALL

            if self.check_permission(auth_username, "view_school_account_passwords"):
                return PASSWORD_VISIBILITY_OWN

            return PASSWORD_VISIBILITY_NONE
        except Exception as e:
            logging.error(
                f"[密码可见性] 解析用户 {auth_username} 的密码可见级别失败: {e}",
                exc_info=True,
            )
            return PASSWORD_VISIBILITY_NONE

    def check_permission(self, auth_username, permission):
        """检查用户是否有特定权限（支持差分化权限）"""
        group = self.get_user_group(auth_username)

        group_perms = (
            self.permissions["permission_groups"].get(
                group, {}).get("permissions", {})
        )
        has_permission = group_perms.get(permission, False)

        logging.debug(
            f"[权限检查] 用户 {auth_username} 的组 {group} 对权限 {permission} 的基础权限: {has_permission}"
        )

        user_custom = self.permissions.get("user_custom_permissions", {}).get(
            auth_username, {}
        )
        added_perms = user_custom.get("added", [])
        removed_perms = user_custom.get("removed", [])

        if added_perms or removed_perms:
            logging.debug(
                f"[权限检查] 用户 {auth_username} 的自定义权限 - 添加: {added_perms}, 移除: {removed_perms}"
            )

        if permission in added_perms:
            has_permission = True
            logging.debug(
                f"[权限检查] 用户 {auth_username} 通过 user_custom_permissions.added 获得权限 {permission}"
            )

        if permission in removed_perms:
            has_permission = False
            logging.debug(
                f"[权限检查] 用户 {auth_username} 通过 user_custom_permissions.removed 被撤销权限 {permission}"
            )

        logging.debug(
            f"[权限检查] 最终结果 - 用户 {auth_username} 对权限 {permission}: {has_permission}"
        )

        return has_permission

    def get_user_permissions(self, auth_username):
        """获取用户的完整权限列表（包含差分权限）"""
        group = self.get_user_group(auth_username)

        group_perms = (
            self.permissions["permission_groups"].get(
                group, {}).get("permissions", {})
        )

        user_perms = dict(group_perms)

        user_custom = self.permissions.get("user_custom_permissions", {}).get(
            auth_username, {}
        )
        added_perms = user_custom.get("added", [])
        removed_perms = user_custom.get("removed", [])

        for perm in added_perms:
            user_perms[perm] = True

        for perm in removed_perms:
            user_perms[perm] = False

        return user_perms

    def set_user_custom_permission(self, auth_username, permission, grant):
        """为用户设置自定义权限（差分化存储）

        Args:
            auth_username: 用户名
            permission: 权限名
            grant: True=授予权限, False=移除权限
        """
        with self.lock:
            if "user_custom_permissions" not in self.permissions:
                self.permissions["user_custom_permissions"] = {}

            if auth_username not in self.permissions["user_custom_permissions"]:
                self.permissions["user_custom_permissions"][auth_username] = {
                    "added": [],
                    "removed": [],
                }

            user_custom = self.permissions["user_custom_permissions"][auth_username]

            group = self.get_user_group(auth_username)
            group_perms = (
                self.permissions["permission_groups"]
                .get(group, {})
                .get("permissions", {})
            )
            base_has_permission = group_perms.get(permission, False)

            if grant:
                if not base_has_permission:
                    if permission not in user_custom["added"]:
                        user_custom["added"].append(permission)
                    if permission in user_custom["removed"]:
                        user_custom["removed"].remove(permission)
                else:
                    if permission in user_custom["removed"]:
                        user_custom["removed"].remove(permission)
            else:
                if base_has_permission:
                    if permission not in user_custom["removed"]:
                        user_custom["removed"].append(permission)
                    if permission in user_custom["added"]:
                        user_custom["added"].remove(permission)
                else:
                    if permission in user_custom["added"]:
                        user_custom["added"].remove(permission)

            self._save_permissions()

            logging.info(f"设置用户 {auth_username} 权限 {permission} = {grant}")
            return {"success": True, "message": "权限已更新"}

    def get_user_group(self, auth_username):
        """获取用户所属组"""
        super_admin = self.config.get("Admin", "super_admin", fallback="admin")
        if auth_username == super_admin:
            return "super_admin"
        return self.permissions["user_groups"].get(auth_username, "guest")

    def update_user_group(self, auth_username, new_group):
        """更新用户组（需要管理员权限）"""
        if new_group == "super_admin":
            return {"success": False, "message": "不允许将用户设置为超级管理员"}
        with self.lock:
            if new_group not in self.permissions["permission_groups"]:
                return {"success": False, "message": "权限组不存在"}

            self.permissions["user_groups"][auth_username] = new_group

            if (
                "user_custom_permissions" in self.permissions
                and auth_username in self.permissions["user_custom_permissions"]
            ):
                del self.permissions["user_custom_permissions"][auth_username]
                logging.info(
                    f"[权限管理] 用户 {auth_username} 切换到组 {new_group}，已自动清空其自定义差分权限"
                )

            self._save_permissions()

            user_file = self.get_user_file_path(auth_username)
            if os.path.exists(user_file):
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                user_data["group"] = new_group
                with open(user_file, "w", encoding="utf-8") as f:
                    json.dump(user_data, f, indent=2, ensure_ascii=False)

            return {"success": True, "message": "权限组已更新"}

    def create_permission_group(self, group_name, permissions, display_name):
        """创建新的权限组（需要超级管理员权限）"""
        with self.lock:
            if group_name in self.permissions["permission_groups"]:
                return {"success": False, "message": "权限组已存在"}

            self.permissions["permission_groups"][group_name] = {
                "name": display_name,
                "is_system": False,
                "permissions": permissions,
            }
            self._save_permissions()
            return {"success": True, "message": "权限组已创建"}

    def update_permission_group(self, group_name, permissions):
        """更新权限组（需要超级管理员权限）"""
        with self.lock:
            if group_name not in self.permissions["permission_groups"]:
                return {"success": False, "message": "权限组不存在"}

            self.permissions["permission_groups"][group_name][
                "permissions"
            ] = permissions
            self._save_permissions()
            return {"success": True, "message": "权限组已更新"}

    def delete_permission_group(self, group_name):
        """删除权限组（需要超级管理员权限）"""
        with self.lock:
            if group_name not in self.permissions["permission_groups"]:
                return {"success": False, "message": "权限组不存在"}

            group_info = self.permissions["permission_groups"][group_name]
            if group_info.get("is_system", False):
                return {"success": False, "message": "不允许删除系统预设权限组"}

            users_count = sum(
                1 for u, g in self.permissions["user_groups"].items() if g == group_name
            )
            if users_count > 0:
                return {
                    "success": False,
                    "message": f"无法删除：有 {users_count} 个用户正在使用此权限组",
                }

            del self.permissions["permission_groups"][group_name]
            self._save_permissions()

            logging.info(f"权限组已删除: {group_name}")
            return {"success": True, "message": "权限组已删除"}

    def list_users(self):
        """列出所有用户"""
        users = []
        for filename in os.listdir(_main().SYSTEM_ACCOUNTS_DIR):
            if filename == "_index.json" or not filename.endswith(".json"):
                continue

            user_file = os.path.join(_main().SYSTEM_ACCOUNTS_DIR, filename)
            try:
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)

                auth_username = user_data.get("auth_username")
                if not auth_username:
                    logging.warning(
                        f"[用户管理] 跳过缺少 auth_username 的用户文件: {user_file}"
                    )
                    continue

                last_ip = user_data.get("last_login_ip", None)
                last_city = None
                if last_ip:
                    try:
                        last_city = _main().get_ip_location(last_ip)
                    except Exception as ip_e:
                        logging.warning(f"查询IP归属地失败 {last_ip}: {ip_e}")
                        last_city = "查询失败"

                school_accounts_data = self._load_user_school_accounts(auth_username) or {}
                school_accounts = list(school_accounts_data.keys())

                users.append(
                    {
                        "auth_username": auth_username,
                        "nickname": user_data.get("nickname", ""),
                        "phone": user_data.get("phone", ""),
                        "group": user_data.get("group", "user"),
                        "created_at": user_data.get("created_at"),
                        "last_login": user_data.get("last_login"),
                        "last_login_ip": last_ip,
                        "last_login_city": last_city,
                        "2fa_enabled": user_data.get("2fa_enabled", False),
                        "banned": user_data.get("banned", False),
                        "max_sessions": user_data.get("max_sessions", 1),
                        "school_accounts": school_accounts,
                        # 添加可用执行次数字段：从用户数据中获取 available_runs，默认值为0
                        # -1 表示无限次数，0表示无剩余次数，正数表示剩余次数
                        "available_runs": user_data.get("available_runs", 0),
                    }
                )
            except Exception as e:
                logging.error(
                    f"[用户管理] 读取用户文件失败 --> 文件名: {filename}, 文件路径: {user_file}, 错误类型: {type(e).__name__}, 错误详情: {e}, 可能原因: 文件损坏、JSON格式错误或权限不足",
                    exc_info=True,
                )
        return users

    def get_all_groups(self):
        """获取所有权限组"""
        return self.permissions["permission_groups"]

    def link_session_to_user(self, auth_username, session_id):
        """关联会话ID到用户账号（用于状态恢复）"""
        if auth_username == "guest":
            return

        if not session_id or session_id == "null" or session_id.strip() == "":
            logging.debug(
                f"[会话管理] 跳过关联无效会话 --> 会话ID: '{session_id}', 目标用户: {auth_username}, 原因: 会话ID为空、null或仅包含空白字符"
            )
            return

        user_file = self.get_user_file_path(auth_username)
        if os.path.exists(user_file):
            with self.lock:
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)

                if "session_ids" not in user_data:
                    user_data["session_ids"] = []

                if session_id not in user_data["session_ids"]:
                    user_data["session_ids"].append(session_id)

                    max_sessions = user_data.get("max_sessions", 1)
                    if max_sessions > 0:
                        user_data["session_ids"] = user_data["session_ids"][
                            -max_sessions:
                        ]

                with open(user_file, "w", encoding="utf-8") as f:
                    json.dump(user_data, f, indent=2, ensure_ascii=False)

    def get_user_sessions(self, auth_username):
        """获取用户关联的会话ID列表"""
        if auth_username == "guest":
            return []

        user_file = self.get_user_file_path(auth_username)
        if os.path.exists(user_file):
            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)
            return user_data.get("session_ids", [])
        return []

    def unlink_session_from_user(self, auth_username, session_id):
        """取消会话与用户的关联"""
        if auth_username == "guest":
            return

        user_file = self.get_user_file_path(auth_username)
        if os.path.exists(user_file):
            with self.lock:
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)

                if (
                    "session_ids" in user_data
                    and session_id in user_data["session_ids"]
                ):
                    user_data["session_ids"].remove(session_id)

                    with open(user_file, "w", encoding="utf-8") as f:
                        json.dump(user_data, f, indent=2, ensure_ascii=False)

    def reset_user_password(self, auth_username, new_password):
        """重置用户密码（管理员功能）"""
        with self.lock:
            user_file = self.get_user_file_path(auth_username)
            if not os.path.exists(user_file):
                return {"success": False, "message": "用户不存在"}

            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            user_data["password"] = self._encrypt_password(new_password)

            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

            logging.info(f"管理员重置密码: {auth_username}")
            return {"success": True, "message": "密码已重置"}

    def force_disable_2fa(self, auth_username):
        """强制关闭指定用户的2FA（管理员功能）"""
        with self.lock:
            user_file = self.get_user_file_path(auth_username)
            if not os.path.exists(user_file):
                return {"success": False, "message": "用户不存在"}

            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            user_data["2fa_enabled"] = False
            # 可选：是否重置secret，通常保留secret以便用户重新开启时无需重新绑定，
            # 或者清空secret强制用户重新绑定。这里选择仅禁用。

            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

            logging.info(f"管理员强制关闭2FA: {auth_username}")
            return {"success": True, "message": "2FA已强制关闭"}

    def update_user_avatar(self, auth_username, avatar_url):
        """更新用户头像"""
        with self.lock:
            user_file = self.get_user_file_path(auth_username)
            if not os.path.exists(user_file):
                return {"success": False, "message": "用户不存在"}

            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            user_data["avatar_url"] = avatar_url

            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

            return {"success": True, "message": "头像已更新"}

    def update_user_theme(self, auth_username, theme):
        """更新用户主题偏好（存储到 system_accounts）"""
        normalized_theme = str(theme).strip().lower()
        if normalized_theme not in ["light", "dark"]:
            return {"success": False, "message": "无效的主题值"}

        with self.lock:
            user_file = self.get_user_file_path(auth_username)
            if not os.path.exists(user_file):
                return {"success": False, "message": "用户不存在"}

            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            user_data["theme"] = normalized_theme

            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

            return {
                "success": True,
                "message": "主题已更新",
                "theme": normalized_theme,
            }

    def get_user_theme(self, auth_username):
        """获取用户主题偏好（从 system_accounts 读取）"""
        user_file = self.get_user_file_path(auth_username)
        fallback_theme = "light"

        with self.lock:
            if not os.path.exists(user_file):
                return {"success": False, "message": "用户不存在", "theme": fallback_theme}

            try:
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                theme = str(user_data.get("theme", fallback_theme)).strip().lower()
                if theme not in ["light", "dark"]:
                    theme = fallback_theme
            except Exception as e:
                logging.warning(f"读取用户主题配置失败 {user_file}: {e}")
                theme = fallback_theme

            return {"success": True, "theme": theme}

    def update_max_sessions(self, auth_username, max_sessions):
        """更新用户最大会话数量

        Args:
            auth_username: 用户名
            max_sessions: 最大会话数 (1=单会话, >1=指定数量, -1=无限制)
        """
        with self.lock:
            user_file = self.get_user_file_path(auth_username)
            if not os.path.exists(user_file):
                return {"success": False, "message": "用户不存在"}

            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            user_data["max_sessions"] = max_sessions

            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

            if max_sessions == 1:
                msg = f"已设置为单会话模式：用户每次只能保持1个活跃会话"
            elif max_sessions == -1:
                msg = f"已设置为无限会话模式：用户可以创建任意数量的会话"
            else:
                msg = f"已设置最大会话数量为：{max_sessions}个，超出时将自动清理最旧的会话"

            return {"success": True, "message": msg}

    def get_available_runs(self, auth_username):
        """读取用户的可用执行次数；-1 表示无限，读取失败按 0 处理。"""
        try:
            user_file = self.get_user_file_path(auth_username)
            if not os.path.exists(user_file):
                return 0
            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)
            return int(user_data.get("available_runs", 0))
        except Exception as e:
            logging.warning(
                "读取用户 %s 的可用执行次数失败: %s", auth_username, e
            )
            return 0

    def update_available_runs(self, auth_username, available_runs):
        """
        更新用户的可用执行次数（管理员功能）

        Args:
            auth_username: 要修改的用户名
            available_runs: 新的可用次数（-1表示无限次数，0表示无剩余，正数表示剩余次数）

        Returns:
            dict: 包含success和message的字典
                {
                    "success": True/False,
                    "message": "操作结果说明"
                }
        """
        # 使用线程锁确保文件操作的原子性，防止并发修改导致数据不一致
        with self.lock:
            # 步骤1：根据用户名构建用户数据文件的完整路径
            user_file = self.get_user_file_path(auth_username)

            # 步骤2：检查用户文件是否存在
            if not os.path.exists(user_file):
                # 如果用户文件不存在，返回错误信息
                return {"success": False, "message": "用户不存在"}

            # 步骤3：从文件中读取当前的用户数据（JSON格式）
            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            # 步骤4：更新用户数据中的 available_runs 字段
            user_data["available_runs"] = available_runs

            # 步骤5：将更新后的用户数据写回文件
            # indent=2: 格式化输出，每层缩进2个空格，提高可读性
            # ensure_ascii=False: 允许保存中文字符，不转义为Unicode
            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

            # 步骤6：根据设置的次数值生成友好的提示消息
            if available_runs == -1:
                # 当设置为-1时，表示无限制使用
                msg = f"已设置为无限次数模式：用户 {auth_username} 可以无限次执行任务"
            else:
                # 正数表示具体的剩余次数
                msg = f"已成功设置用户 {auth_username} 的可用次数为：{available_runs} 次"

            # 步骤7：记录操作日志，便于后续审计和问题排查
            logging.info(
                f"[可用次数管理] 管理员更新用户可用次数 --> 用户: {auth_username}, "
                f"新次数: {available_runs} ({'无限制' if available_runs == -1 else str(available_runs) + '次'})"
            )

            # 步骤8：返回成功结果和友好提示消息
            return {"success": True, "message": msg}

    def ban_user(self, auth_username):
        """封禁用户"""
        with self.lock:
            user_file = self.get_user_file_path(auth_username)
            if not os.path.exists(user_file):
                return {"success": False, "message": "用户不存在"}

            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            user_data["banned"] = True
            user_data["banned_at"] = time.time()

            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

            logging.info(f"用户已封禁: {auth_username}")
            return {"success": True, "message": "用户已封禁"}

    def unban_user(self, auth_username):
        """解封用户"""
        with self.lock:
            user_file = self.get_user_file_path(auth_username)
            if not os.path.exists(user_file):
                return {"success": False, "message": "用户不存在"}

            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            user_data["banned"] = False
            user_data["unbanned_at"] = time.time()

            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

            logging.info(f"用户已解封: {auth_username}")
            return {"success": True, "message": "用户已解封"}

    def delete_user(self, auth_username):
        """
        删除用户（需要管理员权限）

        在删除用户之前，会将用户的所有数据（system_accounts、school_accounts、permissions）
        备份到 system_accounts/remove/ 目录中，备份文件使用 UUID 命名。
        只有备份成功后才会执行实际的删除操作。

        参数:
            auth_username (str): 要删除的用户的认证用户名

        返回:
            dict: 包含 success (bool) 和 message (str) 的字典
        """
        with self.lock:  # 使用线程锁确保线程安全，防止并发删除导致数据不一致
            # ==================== 第一步：安全性检查 ====================

            # 获取超级管理员用户名，防止删除超级管理员账号
            super_admin = self.config.get(
                "Admin", "super_admin", fallback="admin")
            if auth_username == super_admin:
                # 不允许删除超级管理员，这是系统安全的最后一道防线
                return {"success": False, "message": "不允许删除超级管理员"}

            # 获取用户的 system_accounts 文件路径
            user_file = self.get_user_file_path(auth_username)
            if not os.path.exists(user_file):
                # 用户文件不存在，说明用户已不存在或从未创建
                return {"success": False, "message": "用户不存在"}

            # ==================== 第二步：收集需要备份的数据 ====================

            try:
                # 1. 读取 system_accounts 中的用户数据
                # 这包含用户的基本信息、密码哈希、会话信息等核心数据
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                logging.info(
                    f"[删除用户备份] 已读取用户 {auth_username} 的 system_accounts 数据")
            except Exception as e:
                # 如果无法读取用户数据，则无法继续备份，返回错误
                logging.error(f"[删除用户备份] 读取用户数据失败: {e}")
                return {"success": False, "message": f"读取用户数据失败: {e}"}

            # 2. 读取用户的 school_accounts (user_accounts) 数据
            # 这包含用户绑定的学校账号信息（用户名、密码等）
            school_accounts_data = None
            school_accounts_file = self._get_user_accounts_file(auth_username)
            if os.path.exists(school_accounts_file):
                try:
                    with open(school_accounts_file, "r", encoding="utf-8") as f:
                        school_accounts_data = json.load(f)
                    logging.info(
                        f"[删除用户备份] 已读取用户 {auth_username} 的 school_accounts 数据")
                except Exception as e:
                    # 如果读取失败，记录警告但不阻止删除流程（可能用户没有学校账号）
                    logging.warning(f"[删除用户备份] 读取 school_accounts 数据失败: {e}")
                    school_accounts_data = None
            else:
                # 用户可能没有绑定任何学校账号，这是正常情况
                logging.info(
                    f"[删除用户备份] 用户 {auth_username} 没有 school_accounts 文件")

            # 3. 提取用户的权限信息（从 permissions.json）
            # 包括用户所属的用户组和自定义权限
            user_permissions = {}
            if auth_username in self.permissions.get("user_groups", {}):
                # 保存用户的用户组信息（如 admin、user 等）
                user_permissions["user_groups"] = self.permissions["user_groups"][auth_username]
            if "user_custom_permissions" in self.permissions and auth_username in self.permissions["user_custom_permissions"]:
                # 保存用户的自定义权限（如禁用某些功能、特殊访问权限等）
                user_permissions["user_custom_permissions"] = self.permissions["user_custom_permissions"][auth_username]

            if user_permissions:
                logging.info(f"[删除用户备份] 已提取用户 {auth_username} 的权限信息")
            else:
                logging.info(f"[删除用户备份] 用户 {auth_username} 没有特殊权限配置")

            # ==================== 第三步：创建备份 ====================

            # 构建备份文件的保存路径
            # 备份目录位于 Remove_Acoount/
            backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Remove_Acoount")

            # 如果备份目录不存在，则创建它（包括所有必要的父目录）
            if not os.path.exists(backup_dir):
                try:
                    os.makedirs(backup_dir, exist_ok=True)
                    logging.info(f"[删除用户备份] 创建备份目录: {backup_dir}")
                except Exception as e:
                    # 如果无法创建备份目录，则无法继续，返回错误
                    logging.error(f"[删除用户备份] 创建备份目录失败: {e}")
                    return {"success": False, "message": f"创建备份目录失败: {e}"}

            # 生成唯一的备份文件名
            # 检查 _main().SYSTEM_ACCOUNTS_DIR、Remove_Acoount/ 及历史目录中是否存在同名文件
            _legacy_remove_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "Remove_Account"
            )
            _legacy_remove_subdir = os.path.join(_main().SYSTEM_ACCOUNTS_DIR, "remove")
            backup_uuid = str(uuid.uuid4())
            while (os.path.exists(os.path.join(_main().SYSTEM_ACCOUNTS_DIR, f"{backup_uuid}.json")) or
                   os.path.exists(os.path.join(backup_dir, f"{backup_uuid}.json")) or
                   os.path.exists(os.path.join(_legacy_remove_dir, f"{backup_uuid}.json")) or
                   os.path.exists(os.path.join(_legacy_remove_subdir, f"{backup_uuid}.json"))):
                backup_uuid = str(uuid.uuid4())
            backup_filename = os.path.join(backup_dir, f"{backup_uuid}.json")

            # 构建备份数据的结构
            # 使用 ISO 8601 格式的时间戳记录删除时间
            backup_data = {
                "deleted_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),  # 删除时间（UTC时间）
                "auth_username": auth_username,  # 被删除用户的用户名
                "user_data": user_data,  # system_accounts 中的完整用户数据
                "school_accounts": school_accounts_data,  # school_accounts 中的数据（可能为 None）
                "permissions": user_permissions  # 用户的权限配置（可能为空字典）
            }

            # 将备份数据写入 JSON 文件
            try:
                with open(backup_filename, "w", encoding="utf-8") as f:
                    # 使用 indent=2 使 JSON 格式化输出，便于人工查看
                    # ensure_ascii=False 确保中文字符正常显示
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)
                logging.info(f"[删除用户备份] 备份成功: {backup_filename}")
                # 更新 Remove_Acoount/_index.json 索引
                try:
                    _ra_index_path = os.path.join(backup_dir, "_index.json")
                    _ra_deleted_at = backup_data["deleted_at"]
                    # 读取现有索引
                    if os.path.exists(_ra_index_path):
                        with open(_ra_index_path, "r", encoding="utf-8") as _f:
                            _ra_index = json.load(_f)
                    else:
                        _ra_index = {"removed_accounts": {}}
                    if "removed_accounts" not in _ra_index:
                        _ra_index["removed_accounts"] = {}
                    # 添加本次删除记录
                    _ra_index["removed_accounts"][auth_username] = {
                        "backup_file": f"{backup_uuid}.json",
                        "deleted_at": _ra_deleted_at
                    }
                    _ra_index["updated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    with open(_ra_index_path, "w", encoding="utf-8") as _f:
                        json.dump(_ra_index, _f, indent=2, ensure_ascii=False)
                    logging.info(f"[删除用户备份] Remove_Acoount/_index.json 已更新")
                except Exception as _e:
                    logging.warning(f"[删除用户备份] 更新 Remove_Acoount 索引失败: {_e}")
            except Exception as e:
                # 如果备份失败，则不执行删除操作，保护用户数据
                logging.error(f"[删除用户备份] 保存备份文件失败: {e}")
                return {"success": False, "message": f"备份失败，用户未删除: {e}"}

            # ==================== 第四步：执行删除操作 ====================
            # 只有在备份成功后，才会执行以下删除操作

            # 1. 删除 system_accounts 中的用户文件
            try:
                os.remove(user_file)
                logging.info(f"[删除用户] 已删除用户文件: {user_file}")
                # 从 system_accounts/_index.json 索引中移除该用户
                _main()._update_system_accounts_index(auth_username, None, "remove")
            except Exception as e:
                # 删除用户文件失败，记录错误并返回
                logging.error(f"[删除用户] 删除用户文件失败: {e}")
                return {"success": False, "message": f"删除用户文件失败: {e}"}

            # 2. 删除 school_accounts 中的用户文件（如果存在）
            try:
                if os.path.exists(school_accounts_file):
                    os.remove(school_accounts_file)
                    logging.info(
                        f"[删除用户] 已删除用户 {auth_username} 的 school_accounts 文件")
            except Exception as e:
                # school_accounts 删除失败不影响主流程，仅记录警告
                logging.warning(f"[删除用户] 删除 school_accounts 文件失败: {e}")

            # 3. 从 permissions.json 中删除用户的权限配置
            # 删除用户所属的用户组信息
            if auth_username in self.permissions.get("user_groups", {}):
                del self.permissions["user_groups"][auth_username]
                logging.info(f"[删除用户] 已删除用户 {auth_username} 的用户组配置")

            # 删除用户的自定义权限信息
            if (
                "user_custom_permissions" in self.permissions
                and auth_username in self.permissions["user_custom_permissions"]
            ):
                del self.permissions["user_custom_permissions"][auth_username]
                logging.info(f"[删除用户] 已删除用户 {auth_username} 的自定义权限配置")

            # 4. 保存更新后的权限配置到文件
            try:
                self._save_permissions()
                logging.info(f"[删除用户] 权限配置已保存")
            except Exception as e:
                # 权限保存失败，记录警告（不影响删除操作的成功）
                logging.warning(f"[删除用户] 保存权限配置失败: {e}")

            # ==================== 第五步：返回成功结果 ====================

            # 记录删除操作成功，包含备份文件路径供管理员参考
            logging.info(
                f"[删除用户] 用户 {auth_username} 已成功删除，备份文件: {backup_filename}")
            return {
                "success": True,
                "message": f"用户已删除，备份文件: {os.path.basename(backup_filename)}"
            }

    def get_user_details(self, auth_username):
        """获取用户详细信息"""
        user_file = self.get_user_file_path(auth_username)
        if not os.path.exists(user_file):
            return None

        with open(user_file, "r", encoding="utf-8") as f:
            user_data = json.load(f)

        return {
            "auth_username": user_data["auth_username"],
            "group": user_data.get("group", "user"),
            "created_at": user_data.get("created_at"),
            "last_login": user_data.get("last_login"),
            "2fa_enabled": user_data.get("2fa_enabled", False),
            "avatar_url": user_data.get("avatar_url") or "default_avatar.png",
            "max_sessions": user_data.get("max_sessions", 1),
            "theme": user_data.get("theme", "light"),
            "session_ids": user_data.get("session_ids", []),
            "nickname": user_data.get("nickname", user_data["auth_username"]),
            "phone": user_data.get("phone", ""),
            "last_used_school_account": user_data.get(
                "last_used_school_account", ""
            ),  # 新增字段
            # 新增字段：可用运行次数
            "available_runs": user_data.get("available_runs", 0),
            # 账号注销等待期状态
            "account_cancellation": user_data.get("account_cancellation"),
        }

    def set_account_cancellation_pending(self, auth_username, wait_hours=24):
        """为用户设置账号注销等待期状态。"""
        with self.lock:
            user_file = self.get_user_file_path(auth_username)
            if not os.path.exists(user_file):
                return {"success": False, "message": "用户不存在"}
            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            now_ts = int(time.time())
            execute_at = now_ts + int(wait_hours * 3600)
            user_data["account_cancellation"] = {
                "status": "pending",
                "requested_at": now_ts,
                "execute_at": execute_at,
            }
            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)
            return {"success": True, "execute_at": execute_at}

    def get_account_cancellation_status(self, auth_username):
        """读取用户账号注销状态。"""
        user_file = self.get_user_file_path(auth_username)
        if not os.path.exists(user_file):
            return None
        with open(user_file, "r", encoding="utf-8") as f:
            user_data = json.load(f)
        return user_data.get("account_cancellation")

    def update_user_last_school_account(self, auth_username, school_username):
        """更新用户最后使用的学校账号"""
        if not auth_username or auth_username == "guest":
            return

        user_file = self.get_user_file_path(auth_username)
        if os.path.exists(user_file):
            with self.lock:
                try:
                    with open(user_file, "r", encoding="utf-8") as f:
                        user_data = json.load(f)

                    user_data["last_used_school_account"] = school_username

                    with open(user_file, "w", encoding="utf-8") as f:
                        json.dump(user_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logging.error(
                        f"更新用户 {auth_username} 的 last_used_school_account 失败: {e}"
                    )

    def check_single_session_enforcement(self, auth_username, new_session_id):
        """检查并强制执行会话数量限制"""
        if auth_username == "guest":
            return [], ""

        user_file = self.get_user_file_path(auth_username)
        if not os.path.exists(user_file):
            return [], ""

        with self.lock:
            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            max_sessions = user_data.get("max_sessions", 1)
            old_sessions = user_data.get("session_ids", [])

            if max_sessions == -1:
                return [], ""

            current_count = len(old_sessions)
            if current_count >= max_sessions:
                keep_count = max(int(max_sessions) - 1, 0)
                sessions_to_remove = (
                    old_sessions[:-keep_count] if keep_count else list(old_sessions)
                )
                remaining_sessions = old_sessions[-keep_count:] if keep_count else []
                user_data["session_ids"] = remaining_sessions + [new_session_id]

                with open(user_file, "w", encoding="utf-8") as f:
                    json.dump(user_data, f, indent=2, ensure_ascii=False)

                valid_sessions_to_remove = [
                    s
                    for s in sessions_to_remove
                    if s and s != "null" and s.strip() != ""
                ]
                message = ""
                if len(valid_sessions_to_remove) > 0:
                    message = f"已达到最大会话数量限制({max_sessions}个)，已自动清理{len(valid_sessions_to_remove)}个最旧的会话"
                return valid_sessions_to_remove, message
            else:
                return [], ""

    def log_audit(
        self, auth_username, action, details="", ip_address="", session_id=""
    ):
        """记录审计日志"""
        audit_entry = {
            "timestamp": time.time(),
            "datetime": datetime.datetime.now().isoformat(),
            "username": auth_username,
            "action": action,
            "details": details,
            "ip_address": ip_address,
            "session_id": session_id,
        }

        try:
            with open(_main().AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logging.error(f"记录审计日志失败: {e}")

    def get_audit_logs(self, username=None, action=None, limit=100):
        """获取审计日志"""
        if not os.path.exists(_main().AUDIT_LOG_FILE):
            return []

        logs = []
        try:
            with open(_main().AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if (not username or entry.get("username") == username) and (
                            not action or entry.get("action") == action
                        ):
                            logs.append(entry)
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logging.debug(f"[审计日志] 跳过无效日志行: {e}")
                        continue
        except Exception as e:
            logging.error(f"读取审计日志失败: {e}")

        return logs[-limit:]

    def _synchronize_super_admin_permissions(self):
        """
        [启动检查] 同步 config.ini 中的 super_admin 与 permissions.json 中的权限组。
        """
        logging.info(
            "[权限同步] 开始检查 config.ini 与 permissions.json 的 super_admin 一致性..."
        )

        try:
            super_admin_username = self.config.get(
                "Admin", "super_admin", fallback="admin"
            )
            if not super_admin_username:
                logging.error(
                    "[权限同步] config.ini 中 [Admin]super_admin 未配置，同步中止。"
                )
                return

            with self.lock:
                changes_made = False

                if "user_groups" not in self.permissions:
                    self.permissions["user_groups"] = {}

                user_groups = self.permissions["user_groups"]

                for username, group in user_groups.copy().items():

                    if group == "super_admin" and username != super_admin_username:
                        user_groups[username] = "admin"
                        self._update_user_file_group(username, "admin")
                        logging.warning(
                            f"[权限同步] 用户 '{username}' 在 permissions.json 中是 super_admin，"
                            f"但他不是 config.ini 中指定的超管 ('{super_admin_username}')。"
                            f"已自动降级为 'admin'。"
                        )
                        changes_made = True

                    elif username == super_admin_username and group != "super_admin":
                        user_groups[username] = "super_admin"
                        self._update_user_file_group(username, "super_admin")
                        logging.info(
                            f"[权限同步] 用户 '{username}' 是 config.ini 指定的超管，"
                            f"但在 permissions.json 中是 '{group}'。已自动升级为 'super_admin'。"
                        )
                        changes_made = True

                if super_admin_username not in user_groups:
                    user_groups[super_admin_username] = "super_admin"
                    self._update_user_file_group(
                        super_admin_username, "super_admin")  #
                    logging.info(
                        f"[权限同步] config.ini 指定的超管 '{super_admin_username}' "
                        f"不在 permissions.json 中。已自动添加为 'super_admin'。"
                    )
                    changes_made = True

                if changes_made:
                    self._save_permissions()  #
                    logging.info("[权限同步] 权限数据已更新并保存。")
                else:
                    logging.info("[权限同步] 权限一致，无需更新。")

        except Exception as e:
            logging.error(
                f"[权限同步] 同步 super_admin 权限时发生严重错误: {e}", exc_info=True
            )


# ==============================================================================
# Token管理系统
# ==============================================================================


GUEST_SESSION_CREATION_LOCK = threading.RLock()
