from __future__ import annotations

import configparser
import datetime
import json
import logging
import os


def _main():
    import main
    return main


def _load_auto_attendance_config():
    """
    加载自动签到配置文件

    功能说明：
        从JSON文件中读取自动签到配置，包含所有启用自动签到的学校账号信息。
        如果文件不存在或解析失败，返回一个空的配置结构。

    返回值:
        dict: 配置字典，结构如下：
            {
                "enabled_accounts": {
                    "school_username": {
                        "session_uuid": "uuid-string",      # 关联的会话UUID
                        "enabled_at": "ISO8601时间戳",       # 启用时间
                        "auth_username": "所有者用户名"      # 账号所有者
                    }
                }
            }

    异常处理：
        - JSONDecodeError: 配置文件格式错误时返回空配置
        - 其他异常: 记录错误日志并返回空配置
    """
    try:
        # 检查配置文件是否存在于文件系统中
        if os.path.exists(_main().AUTO_ATTENDANCE_CONFIG_FILE):
            # 以UTF-8编码打开配置文件进行读取
            # 使用with语句确保文件正确关闭
            with open(_main().AUTO_ATTENDANCE_CONFIG_FILE, "r", encoding="utf-8") as f:
                # 从JSON文件中加载配置数据到Python字典
                config = json.load(f)

                # 确保配置结构完整，如果缺少enabled_accounts键，则添加空字典
                # 这是一个防御性编程措施，确保后续代码不会因键不存在而报错
                if "enabled_accounts" not in config:
                    config["enabled_accounts"] = {}

                # 记录成功加载的日志，显示启用账号的数量
                logging.info(
                    f"[自动签到配置] 已加载配置，共 {len(config['enabled_accounts'])} 个启用账号"
                )
                # 返回加载的配置字典
                return config
        else:
            # 配置文件不存在，这是首次运行或配置文件被删除的情况
            logging.info("[自动签到配置] 配置文件不存在，使用空配置")
            # 返回一个空的配置结构，包含空的enabled_accounts字典
            return {"enabled_accounts": {}}
    except json.JSONDecodeError as e:
        # JSON解析失败，可能是文件损坏或格式错误
        logging.error(f"[自动签到配置] 配置文件解析失败: {e}")

        # 调用通用备份函数，备份损坏的文件并重置为默认内容
        # 默认内容为空的配置结构：{"enabled_accounts": {}}
        _main()._backup_and_reset_corrupted_file(
            _main().AUTO_ATTENDANCE_CONFIG_FILE,
            {"enabled_accounts": {}},
            "json"
        )

        # 返回空配置，避免程序崩溃
        return {"enabled_accounts": {}}
    except Exception as e:
        # 捕获所有其他异常，例如权限错误、磁盘错误等
        logging.error(f"[自动签到配置] 加载配置失败: {e}")
        # 返回空配置，确保程序可以继续运行
        return {"enabled_accounts": {}}


def _save_auto_attendance_config(config):
    """
    保存自动签到配置到文件

    功能说明：
        将配置字典序列化为JSON格式并写入文件。
        使用缩进格式化，使配置文件易于人工阅读和调试。

    参数:
        config (dict): 要保存的配置字典，应包含enabled_accounts键

    返回值:
        bool: True表示保存成功，False表示保存失败

    异常处理：
        捕获所有异常并记录日志，返回False表示失败
    """
    try:
        # 确保配置结构完整，如果缺少enabled_accounts键，则添加空字典
        # 这是一个安全措施，防止保存不完整的配置
        if "enabled_accounts" not in config:
            config["enabled_accounts"] = {}

        # 确保logs目录存在
        os.makedirs(os.path.dirname(
            _main().AUTO_ATTENDANCE_CONFIG_FILE), exist_ok=True)

        # 以UTF-8编码打开配置文件进行写入
        # 使用with语句确保文件正确关闭，即使发生异常
        with open(_main().AUTO_ATTENDANCE_CONFIG_FILE, "w", encoding="utf-8") as f:
            # 将配置字典序列化为JSON格式并写入文件
            # ensure_ascii=False: 允许中文字符直接显示，不转义为\uXXXX
            # indent=2: 使用2个空格缩进，使JSON文件格式化，易于阅读
            json.dump(config, f, ensure_ascii=False, indent=2)

        # 记录成功保存的日志，显示启用账号的数量
        logging.info(
            f"[自动签到配置] 配置已保存，共 {len(config['enabled_accounts'])} 个启用账号"
        )
        # 返回True表示保存成功
        return True
    except Exception as e:
        # 捕获所有异常，例如权限错误、磁盘空间不足等
        logging.error(f"[自动签到配置] 保存配置失败: {e}")
        # 返回False表示保存失败
        return False


def _record_auto_attendance_success(school_username, params):
    """记录一次新的自动签到成功，并在达到阈值时关闭自动签到。"""
    if not params.get("auto_attendance_stop_after_success", True):
        return False

    try:
        success_limit = max(
            1, int(params.get("auto_attendance_success_limit", 1))
        )
    except (TypeError, ValueError):
        success_limit = 1

    with _main().CONFIG_JSON_LOCK:
        config = _load_auto_attendance_config()
        account_info = config.get("enabled_accounts", {}).get(school_username)
        if not account_info:
            return False

        try:
            successful_count = max(0, int(account_info.get("successful_count", 0))) + 1
        except (TypeError, ValueError):
            successful_count = 1

        account_info["successful_count"] = successful_count
        reached_limit = successful_count >= success_limit
        if reached_limit:
            del config["enabled_accounts"][school_username]

        if not _save_auto_attendance_config(config):
            return False

        if reached_limit:
            logging.info(
                f"[自动签到配置] 账号 {school_username} 已完成 {successful_count} 次签到，自动关闭自动签到"
            )
            session_uuid = account_info.get("session_uuid")
            sio = _main().globals().get("socketio")
            if session_uuid and sio:
                try:
                    sio.emit(
                        "auto_attendance_updated",
                        {
                            "enabled": False,
                            "successful_count": successful_count,
                            "success_limit": success_limit,
                        },
                        room=session_uuid,
                    )
                except Exception as e:
                    logging.warning(
                        f"[自动签到配置] 推送自动关闭状态失败: {e}"
                    )
        return reached_limit


def _enable_auto_attendance(school_username, session_uuid, auth_username):
    """
    启用指定学校账号的自动签到功能

    功能说明：
        将指定的学校账号添加到自动签到配置中，或更新已存在账号的配置。
        记录启用时间和账号所有者信息。

    参数:
        school_username (str): 学校账号的用户名（唯一标识符）
        session_uuid (str): 关联的会话UUID，用于识别登录会话
        auth_username (str): 账号所有者的认证用户名（系统登录用户名）

    返回值:
        bool: True表示启用成功，False表示启用失败

    流程：
        1. 加载当前配置
        2. 添加或更新账号配置
        3. 保存配置到文件
        4. 记录操作日志
    """
    try:
        # 加载当前的自动签到配置
        # 这个配置包含所有已启用自动签到的账号信息
        config = _load_auto_attendance_config()

        # 添加或更新指定账号的配置信息
        # 使用school_username作为键，存储账号的详细配置
        config["enabled_accounts"][school_username] = {
            # 存储关联的会话UUID，用于后续签到时识别会话
            "session_uuid": session_uuid,
            # 记录启用时间，使用UTC时间并转换为ISO8601格式（带Z后缀）
            # datetime.utcnow()获取当前UTC时间
            # .isoformat()转换为ISO8601字符串格式
            # + "Z"表示这是UTC时区时间
            "enabled_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            # 记录账号所有者的认证用户名
            "auth_username": auth_username,
            # 每次重新启用时重新累计自动签到成功次数
            "successful_count": 0,
        }

        # 保存更新后的配置到JSON文件
        # 如果保存成功，_save_auto_attendance_config返回True
        if _save_auto_attendance_config(config):
            # 记录成功启用的日志，包含学校账号、所有者和会话信息
            logging.info(
                f"[自动签到配置] 已启用自动签到 - "
                f"学校账号: {school_username}, "
                f"所有者: {auth_username}, "
                f"会话: {session_uuid}"
            )
            # 返回True表示启用成功
            return True
        # 如果保存失败，返回False
        return False
    except Exception as e:
        # 捕获所有异常，例如文件操作错误、权限问题等
        logging.error(
            f"[自动签到配置] 启用失败 - "
            f"学校账号: {school_username}, 错误: {e}"
        )
        # 返回False表示启用失败
        return False


def _disable_auto_attendance(school_username):
    """
    禁用指定学校账号的自动签到功能

    功能说明：
        从自动签到配置中移除指定的学校账号。
        如果账号不存在，也视为成功（幂等操作）。

    参数:
        school_username (str): 学校账号的用户名

    返回值:
        bool: True表示禁用成功（包括账号本来就不存在的情况），
              False表示操作失败

    幂等性：
        多次调用此函数禁用同一账号不会产生错误，都返回True
    """
    try:
        # 加载当前的自动签到配置
        config = _load_auto_attendance_config()

        # 检查指定的学校账号是否在启用账号列表中
        if school_username in config["enabled_accounts"]:
            # 账号存在，从字典中删除该账号的配置
            # 使用del语句直接删除字典中的键值对
            del config["enabled_accounts"][school_username]

            # 保存更新后的配置到JSON文件
            if _save_auto_attendance_config(config):
                # 记录成功禁用的日志
                logging.info(
                    f"[自动签到配置] 已禁用自动签到 - 学校账号: {school_username}"
                )
                # 返回True表示禁用成功
                return True
            # 如果保存失败，返回False
            return False
        else:
            # 账号本来就不存在于启用列表中
            # 这种情况也视为成功，因为最终结果符合预期（账号未启用）
            logging.info(
                f"[自动签到配置] 账号未启用自动签到 - 学校账号: {school_username}"
            )
            # 返回True表示操作成功（幂等操作）
            return True
    except Exception as e:
        # 捕获所有异常
        logging.error(
            f"[自动签到配置] 禁用失败 - "
            f"学校账号: {school_username}, 错误: {e}"
        )
        # 返回False表示禁用失败
        return False


def _is_auto_attendance_enabled(school_username):
    """
    检查指定学校账号是否启用了自动签到

    功能说明：
        查询配置文件，判断指定账号是否在启用列表中。
        若账号已启用超过 _main().AUTO_ATTENDANCE_MAX_MINUTES 分钟，则自动将其禁用并返回 False。

    参数:
        school_username (str): 学校账号的用户名

    返回值:
        bool: True表示已启用自动签到，False表示未启用、已超时自动关闭或查询失败

    异常处理：
        如果查询过程中发生异常，返回False（安全默认值）
    """
    try:
        # 加载当前的自动签到配置
        config = _load_auto_attendance_config()

        # 检查账号是否在启用列表中
        if school_username not in config["enabled_accounts"]:
            return False

        # 获取该账号的配置信息
        account_info = config["enabled_accounts"][school_username]

        # 检查是否超过最大持续时间（_main().AUTO_ATTENDANCE_MAX_MINUTES 分钟）
        enabled_at_str = account_info.get("enabled_at")
        if enabled_at_str:
            try:
                # 解析启用时间（ISO8601格式，带Z后缀表示UTC）
                enabled_at = datetime.datetime.strptime(
                    enabled_at_str, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=datetime.timezone.utc)
                # 计算已启用的时长（分钟）
                elapsed_minutes = (
                    datetime.datetime.now(datetime.timezone.utc) - enabled_at
                ).total_seconds() / 60.0

                if elapsed_minutes >= _main().AUTO_ATTENDANCE_MAX_MINUTES:
                    # 超时，自动禁用该账号的自动签到
                    logging.info(
                        f"[自动签到配置] 账号 {school_username} 已启用超过 "
                        f"{_main().AUTO_ATTENDANCE_MAX_MINUTES} 分钟（实际 {elapsed_minutes:.1f} 分钟），自动关闭自动签到"
                    )
                    _disable_auto_attendance(school_username)
                    return False
            except ValueError:
                # 时间格式解析失败，忽略超时检查，正常返回启用状态
                logging.warning(
                    f"[自动签到配置] 账号 {school_username} 的启用时间格式异常: {enabled_at_str}，跳过超时检查"
                )

        # 账号在启用列表中且未超时，返回True
        return True
    except Exception as e:
        # 捕获所有异常，例如文件读取错误
        logging.error(
            f"[自动签到配置] 检查失败 - "
            f"学校账号: {school_username}, 错误: {e}"
        )
        # 发生异常时返回False，表示未启用（安全默认值）
        return False


def _get_auto_attendance_session(school_username):
    """
    获取指定学校账号关联的会话UUID

    功能说明：
        从配置中查询指定账号关联的会话UUID。
        会话UUID用于在自动签到时识别用户的登录会话。

    参数:
        school_username (str): 学校账号的用户名

    返回值:
        str: 会话UUID字符串，如果账号未启用或不存在则返回None
        None: 账号不存在或查询失败

    使用场景：
        在执行自动签到任务时，需要获取账号关联的会话UUID，
        以便使用正确的会话上下文执行签到操作。
    """
    try:
        # 加载当前的自动签到配置
        config = _load_auto_attendance_config()
        # 检查指定的学校账号是否在启用列表中
        if school_username in config["enabled_accounts"]:
            # 账号存在，从账号配置中获取session_uuid字段
            # 使用.get()方法安全地获取值，如果键不存在返回None
            return config["enabled_accounts"][school_username].get("session_uuid")
        # 账号不存在，返回None
        return None
    except Exception as e:
        # 捕获所有异常
        logging.error(
            f"[自动签到配置] 获取会话失败 - "
            f"学校账号: {school_username}, 错误: {e}"
        )
        # 发生异常时返回None
        return None


def _get_auto_attendance_by_session(session_uuid):
    """
    根据会话UUID获取所有关联的自动签到账号

    功能说明：
        反向查询，根据会话UUID找出所有使用该会话的自动签到账号。
        一个会话可能关联多个学校账号（例如用户有多个学校账号）。

    参数:
        session_uuid (str): 会话UUID

    返回值:
        list: 学校账号用户名列表，如果没有找到或查询失败则返回空列表

    使用场景：
        当会话失效或被删除时，需要找出所有关联的自动签到账号，
        以便进行相应的清理或通知操作。
    """
    try:
        # 加载当前的自动签到配置
        config = _load_auto_attendance_config()
        # 初始化一个空列表，用于存储匹配的账号用户名
        accounts = []
        # 遍历所有启用自动签到的账号
        # items()方法返回(键, 值)对，即(school_username, info)
        for school_username, info in config["enabled_accounts"].items():
            # 检查当前账号的session_uuid是否与目标session_uuid匹配
            # 使用.get()方法安全地获取session_uuid字段
            if info.get("session_uuid") == session_uuid:
                # 匹配成功，将该账号用户名添加到结果列表
                accounts.append(school_username)
        # 返回匹配的账号列表（可能为空列表）
        return accounts
    except Exception as e:
        # 捕获所有异常
        logging.error(
            f"[自动签到配置] 根据会话查询失败 - 会话: {session_uuid}, 错误: {e}"
        )
        # 发生异常时返回空列表
        return []


def _migrate_auto_attendance_from_ini():
    """
    从INI文件迁移auto_attendance_enabled配置到JSON文件

    功能说明：
        扫描所有学校账号的INI配置文件，查找启用了auto_attendance_enabled的账号。
        这是一个向后兼容的迁移功能，用于将旧的分散配置迁移到新的集中配置。

    迁移策略：
        由于INI文件中只存储了认证用户名（auth_username），而没有学校用户名，
        因此无法立即完成迁移。采用延迟迁移策略：
        1. 扫描并记录需要迁移的账号
        2. 在用户下次登录并启用自动签到时，自动创建JSON配置
        3. 保留INI文件中的配置，直到确认迁移成功

    返回值:
        dict: 迁移统计信息
            {
                "scanned": int,    # 扫描的INI文件总数
                "migrated": int,   # 成功迁移的账号数（当前实现中为0）
                "errors": list     # 错误信息列表
            }

    执行时机：
        应在程序启动时执行一次，确保向后兼容性
    """
    try:
        # 记录迁移开始的日志
        logging.info("[自动签到配置迁移] 开始扫描INI文件进行配置迁移...")

        # 初始化统计信息字典
        stats = {
            "scanned": 0,      # 扫描的INI文件总数
            "migrated": 0,     # 成功迁移的账号数
            "errors": []       # 错误列表，每个元素是错误描述字符串
        }

        # 获取学校账号配置文件存储目录的路径
        accounts_dir = _main().SCHOOL_ACCOUNTS_DIR
        # 检查账号目录是否存在
        if not os.path.exists(accounts_dir):
            # 目录不存在，可能是首次运行，记录日志并跳过迁移
            logging.info(f"[自动签到配置迁移] 账号目录不存在: {accounts_dir}，跳过迁移")
            # 返回统计信息（全为0）
            return stats

        # 遍历账号目录中的所有文件
        for filename in os.listdir(accounts_dir):
            # 只处理.ini扩展名的文件，跳过其他文件
            if not filename.endswith(".ini"):
                continue

            # 增加扫描计数
            stats["scanned"] += 1
            # 从文件名中提取用户名（去掉.ini扩展名）
            ini_username = os.path.splitext(filename)[0]
            # 构造INI文件的完整路径
            ini_path = os.path.join(accounts_dir, filename)

            try:
                # 创建ConfigParser对象，用于读取INI文件
                cfg = configparser.RawConfigParser()
                # 设置optionxform为str，保持配置项键名的大小写
                # 默认情况下ConfigParser会将键名转换为小写
                cfg.optionxform = str
                # 读取INI文件，使用UTF-8编码
                cfg.read(ini_path, encoding="utf-8")

                # 检查INI文件中是否存在Config节
                if not cfg.has_section("Config"):
                    # 没有Config节，跳过此文件
                    continue

                # 检查Config节中是否存在auto_attendance_enabled配置项
                if not cfg.has_option("Config", "auto_attendance_enabled"):
                    # 没有此配置项，跳过此文件
                    continue

                # 读取auto_attendance_enabled配置项的值（字符串）
                auto_enabled_str = cfg.get("Config", "auto_attendance_enabled")
                # 将字符串转换为布尔值
                # 将字符串转换为小写后，检查是否为true、1、t或yes
                auto_enabled = auto_enabled_str.lower() in ("true", "1", "t", "yes")

                # 如果未启用自动签到，跳过此文件
                if not auto_enabled:
                    # 记录调试日志，说明该账号未启用自动签到
                    logging.debug(
                        f"[自动签到配置迁移] 账号 {ini_username} 未启用自动签到，跳过迁移"
                    )
                    continue

                # 发现启用了自动签到的账号，记录信息日志
                logging.info(
                    f"[自动签到配置迁移] 发现启用自动签到的账号: {ini_username}，开始迁移..."
                )

                # 为了迁移，需要学校账号用户名（school_username）
                # 但INI文件中存储的是认证用户名（ini_username），学校用户名需要登录后才能获取
                # 因此这里采用一个简化策略：
                # 1. 暂时不迁移，只记录日志
                # 2. 当用户下次登录并启用自动签到时，自动创建JSON配置
                # 3. 这样可以确保数据准确性

                # 由于无法立即获取学校用户名，我们只能在用户登录时迁移
                # 这里只记录一个待迁移的标记
                logging.info(
                    f"[自动签到配置迁移] 账号 {ini_username} 需要在下次登录时完成迁移"
                )

                # 可选：从INI文件中移除 auto_attendance_enabled 配置项
                # 但为了安全，我们保留它，直到确认迁移成功
                # 以下代码被注释掉，如果需要立即清理INI文件，可以取消注释
                # cfg.remove_option("Config", "auto_attendance_enabled")
                # with open(ini_path, "w", encoding="utf-8") as f:
                #     cfg.write(f)

            except Exception as e:
                # 处理单个INI文件时发生异常
                # 构造错误消息字符串
                error_msg = f"迁移账号 {ini_username} 失败: {e}"
                # 记录错误日志，包含异常堆栈信息
                logging.error(f"[自动签到配置迁移] {error_msg}", exc_info=True)
                # 将错误消息添加到错误列表
                stats["errors"].append(error_msg)

        # 所有INI文件扫描完成，记录迁移结果摘要
        logging.info(
            f"[自动签到配置迁移] 迁移完成 - "
            f"扫描: {stats['scanned']} 个文件, "
            f"迁移: {stats['migrated']} 个账号, "
            f"错误: {len(stats['errors'])} 个"
        )

        # 如果有错误发生，记录警告日志
        if stats["errors"]:
            logging.warning(
                f"[自动签到配置迁移] 迁移过程中出现错误: {stats['errors']}"
            )

        # 返回迁移统计信息
        return stats

    except Exception as e:
        # 整个迁移过程发生异常
        logging.error(f"[自动签到配置迁移] 迁移过程失败: {e}", exc_info=True)
        # 返回一个表示失败的统计信息
        return {"scanned": 0, "migrated": 0, "errors": [str(e)]}
