from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys


def _main():
    import main
    return main


def _parse_daily_restart_time_string(time_value):
    normalized_time = str(time_value or "").strip()
    parts = normalized_time.split(":")
    if (
        len(parts) != 2
        or len(parts[0]) != 2
        or len(parts[1]) != 2
        or not parts[0].isdigit()
        or not parts[1].isdigit()
    ):
        return None, None, False

    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None, None, False

    return hour, minute, True


def _get_daily_restart_schedule_config(config=None):
    runtime_config = config or _main()._read_config_ini(_main().CONFIG_JSON_FILE) or _main()._get_default_config()
    enabled = runtime_config.getboolean(
        "Daily_Restart", "enabled", fallback=False
    )
    time_value = str(
        runtime_config.get("Daily_Restart", "time", fallback="00:00") or ""
    ).strip()
    hour, minute, valid = _parse_daily_restart_time_string(time_value)
    return {
        "enabled": enabled,
        "time": time_value,
        "hour": hour if valid else None,
        "minute": minute if valid else None,
        "valid": valid,
    }


def _get_daily_full_restart_marker_path():
    return os.path.join(_main().LOGIN_LOGS_DIR, "daily_restart_marker.json")


def _get_daily_full_restart_log_path():
    return os.path.join(_main().LOGIN_LOGS_DIR, "daily_restart.log")


def _append_daily_full_restart_log(message, now_dt=None, log_path=None):
    timestamp = (now_dt or datetime.datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    target_path = log_path or _get_daily_full_restart_log_path()
    parent_dir = os.path.dirname(target_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(target_path, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {message}\n")


def _read_daily_full_restart_marker(marker_path=None):
    target_path = marker_path or _get_daily_full_restart_marker_path()
    if not os.path.exists(target_path):
        return None
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _write_daily_full_restart_marker(marker_path=None, now_dt=None):
    target_path = marker_path or _get_daily_full_restart_marker_path()
    current_dt = now_dt or datetime.datetime.now()
    parent_dir = os.path.dirname(target_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(
            {"last_restart_date": current_dt.date().isoformat()},
            f,
            ensure_ascii=False,
        )


def _has_daily_full_restart_marker_for_date(target_date, marker_path=None):
    marker_payload = _read_daily_full_restart_marker(marker_path)
    if not marker_payload:
        return False
    return marker_payload.get("last_restart_date") == target_date.isoformat()


def _build_daily_restart_helper_command(
    old_pid,
    python_executable,
    main_script_path,
    cwd,
    restart_log_path,
    restart_marker_path,
    forwarded_argv,
):
    return [
        python_executable,
        main_script_path,
        "--daily-restart-helper",
        "--daily-restart-parent-pid",
        str(old_pid),
        "--daily-restart-python-executable",
        python_executable,
        "--daily-restart-main-script-path",
        main_script_path,
        "--daily-restart-cwd",
        cwd,
        "--daily-restart-log-path",
        restart_log_path,
        "--daily-restart-marker-path",
        restart_marker_path,
        "--daily-restart-forward-args-json",
        json.dumps(list(forwarded_argv or []), ensure_ascii=False),
    ]


def _strip_daily_restart_helper_args(argv):
    helper_value_flags = {
        "--daily-restart-parent-pid",
        "--daily-restart-python-executable",
        "--daily-restart-main-script-path",
        "--daily-restart-cwd",
        "--daily-restart-log-path",
        "--daily-restart-marker-path",
        "--daily-restart-forward-args-json",
    }
    filtered_args = []
    args_list = list(argv or [])
    index = 0

    while index < len(args_list):
        current_arg = args_list[index]
        if current_arg == "--daily-restart-helper":
            index += 1
            continue
        if current_arg in helper_value_flags:
            index += 2
            continue
        if any(
            current_arg.startswith(f"{helper_flag}=")
            for helper_flag in helper_value_flags
        ):
            index += 1
            continue
        filtered_args.append(current_arg)
        index += 1

    return filtered_args


def _run_daily_restart_helper(args):
    restart_log_path = getattr(args, "daily_restart_log_path", None)
    parent_pid = getattr(args, "daily_restart_parent_pid", None)
    python_executable = getattr(args, "daily_restart_python_executable", None)
    main_script_path = getattr(args, "daily_restart_main_script_path", None)
    restart_cwd = getattr(args, "daily_restart_cwd", None) or os.getcwd()
    forwarded_args_json = getattr(args, "daily_restart_forward_args_json", "[]")

    if not python_executable or not main_script_path or not parent_pid:
        _append_daily_full_restart_log(
            "[每日完全重启 helper] 缺少必要启动参数，放弃接棒重启",
            log_path=restart_log_path,
        )
        return False

    _append_daily_full_restart_log(
        f"[每日完全重启 helper] 已启动，等待旧进程退出 pid={parent_pid}",
        log_path=restart_log_path,
    )

    if not _main()._wait_for_process_exit(parent_pid):
        _append_daily_full_restart_log(
            f"[每日完全重启 helper] 等待旧进程退出超时 pid={parent_pid}",
            log_path=restart_log_path,
        )
        return False

    try:
        forwarded_args = json.loads(forwarded_args_json)
        if not isinstance(forwarded_args, list):
            forwarded_args = []
    except (TypeError, ValueError, json.JSONDecodeError):
        forwarded_args = []

    forwarded_args = _strip_daily_restart_helper_args(forwarded_args)
    command = [python_executable, main_script_path, *forwarded_args]
    _append_daily_full_restart_log(
        f"[每日完全重启 helper] 旧进程已退出，准备拉起新进程，cwd={restart_cwd} args={forwarded_args}",
        log_path=restart_log_path,
    )

    try:
        new_process = subprocess.Popen(command, cwd=restart_cwd)
    except Exception as exc:
        _append_daily_full_restart_log(
            f"[每日完全重启 helper] 拉起新进程失败: {exc}",
            log_path=restart_log_path,
        )
        return False

    _append_daily_full_restart_log(
        f"[每日完全重启 helper] 已拉起新进程 pid={getattr(new_process, 'pid', 'unknown')}",
        log_path=restart_log_path,
    )
    _main()._flush_all_log_handlers()
    return True


def _trigger_daily_full_restart(now_dt=None, exit_func=None):
    current_dt = now_dt or datetime.datetime.now()
    current_date = current_dt.date()
    marker_path = _get_daily_full_restart_marker_path()
    restart_log_path = _get_daily_full_restart_log_path()

    if _has_daily_full_restart_marker_for_date(current_date, marker_path):
        _append_daily_full_restart_log(
            f"[每日完全重启] {current_date.isoformat()} 已执行过，跳过重复触发",
            current_dt,
            log_path=restart_log_path,
        )
        return False

    command = _build_daily_restart_helper_command(
        old_pid=os.getpid(),
        python_executable=sys.executable,
        main_script_path=os.path.abspath(_main().__file__),
        cwd=os.getcwd(),
        restart_log_path=restart_log_path,
        restart_marker_path=marker_path,
        forwarded_argv=sys.argv[1:],
    )

    try:
        helper_process = subprocess.Popen(command, cwd=os.getcwd())
    except Exception as exc:
        _append_daily_full_restart_log(
            f"[每日完全重启] helper 启动失败，取消本次重启: {exc}",
            current_dt,
            log_path=restart_log_path,
        )
        return False

    _write_daily_full_restart_marker(marker_path, current_dt)
    _append_daily_full_restart_log(
        f"[每日完全重启] helper 已启动 pid={getattr(helper_process, 'pid', 'unknown')}，主进程准备退出",
        current_dt,
        log_path=restart_log_path,
    )
    _main()._flush_all_log_handlers()
    (exit_func or os._exit)(0)
    return True


def _get_daily_restart_config_view_data(config):
    schedule_config = _get_daily_restart_schedule_config(config)
    return {
        "enabled": schedule_config["enabled"],
        "time": schedule_config["time"] if schedule_config["time"] else "00:00",
    }


def _apply_daily_restart_config_updates(config, data):
    enabled_value = str(data.get("enabled", False)).lower()
    time_value = str(data.get("time", "00:00") or "").strip()
    _, _, valid = _parse_daily_restart_time_string(time_value)
    if not valid:
        raise ValueError("每日自动重启时间必须是合法的 HH:MM 24 小时制")

    if not config.has_section("Daily_Restart"):
        config.add_section("Daily_Restart")
    config.set("Daily_Restart", "enabled", enabled_value)
    config.set("Daily_Restart", "time", time_value)
    return config
