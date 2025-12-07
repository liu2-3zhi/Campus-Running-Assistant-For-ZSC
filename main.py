# 跑步助手
# 这是一个基于Flask的Web应用，用于模拟跑步任务的执行


from __future__ import annotations

_import_failures = []
_log_buffer = []


def _buffer_log(level, message):
    """
    暂存日志到缓冲区，同时打印到控制台。
    """
    print(message)
    _log_buffer.append((level, message))


def _try_import_builtin(module_name, display_name=None, use_print=False):
    """
    尝试导入内置模块，失败时记录但不立即退出。
    """
    if display_name is None:
        display_name = module_name

    try:
        module = __import__(module_name)
        _buffer_log("INFO", f"[导入检查] ✓ {display_name} 导入成功")
        return module
    except ImportError as e:
        _import_failures.append(
            {"module": display_name, "type": "builtin", "error": str(e)}
        )
        _buffer_log("ERROR", f"[导入检查] ✗ {display_name} 导入失败: {e}")
        return None


_buffer_log("INFO", "[导入检查] 开始导入Python内置模块...")
logging = _try_import_builtin("logging", None, True)
sys = _try_import_builtin("sys")
os = _try_import_builtin("os")
re = _try_import_builtin("re")
time = _try_import_builtin("time")
threading = _try_import_builtin("threading")
hashlib = _try_import_builtin("hashlib")
json = _try_import_builtin("json")
configparser = _try_import_builtin("configparser")
datetime = _try_import_builtin("datetime")
traceback = _try_import_builtin("traceback")
zipfile = _try_import_builtin("zipfile")
random = _try_import_builtin("random")
argparse = _try_import_builtin("argparse")
gc = _try_import_builtin("gc")
heapq = _try_import_builtin("heapq")

if _import_failures:
    _buffer_log("ERROR", f"\n{'='*70}")
    _buffer_log("ERROR", f"[致命错误] 内置模块导入失败")
    _buffer_log("ERROR", f"{'='*70}")
    _buffer_log("ERROR", f"\n检测到 {len(_import_failures)} 个内置模块导入失败：\n")
    for i, failure in enumerate(_import_failures, 1):
        _buffer_log("ERROR", f"  {i}. {failure['module']}")
        _buffer_log("ERROR", f"     错误: {failure['error']}\n")
    _buffer_log("ERROR", "这通常表示您的 Python 环境已损坏。")
    _buffer_log("ERROR", "建议重新安装 Python 或修复当前安装。")
    _buffer_log(f"{'='*70}\n")
    _import_failures.clear()
    if sys:
        sys.exit(1)
    else:
        exit(1)

_buffer_log("INFO", "[导入检查] ✓ 所有内置模块导入成功\n")
_import_failures.clear()

if sys and sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        import codecs

        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


def import_standard_libraries():
    """
    逐步导入所有必需的标准库。
    """
    logging.info("=" * 80)
    logging.info("开始检查并导入 Python 标准库...")
    logging.info("[依赖检查] 正在导入 Python 标准库...")

    std_libs = [
        ("ssl", "import ssl"),
        ("eventlet", "import eventlet"),
        ("eventlet.wsgi", "import eventlet.wsgi"),
        ("argparse", "import argparse"),
        ("base64", "import base64"),
        ("bisect", "import bisect"),
        ("collections", "import collections"),
        ("configparser", "import configparser"),
        ("copy", "import copy"),
        ("csv", "import csv"),
        ("datetime", "import datetime"),
        ("hashlib", "import hashlib"),
        ("json", "import json"),
        ("math", "import math"),
        ("pickle", "import pickle"),
        ("queue", "import queue"),
        ("random", "import random"),
        ("re", "import re"),
        ("secrets", "import secrets"),
        ("socket", "import socket"),
        ("threading", "import threading"),
        ("time", "import time"),
        ("traceback", "import traceback"),
        ("urllib", "import urllib.parse"),
        ("uuid", "import uuid"),
        ("warnings", "import warnings"),
        ("atexit", "import atexit"),
        ("io", "import io"),
        ("zipfile", "import zipfile"),
        ("functools", "import functools"),
        ("ipaddress", "import ipaddress"),
        ("string", "import string"),
    ]

    failed_imports = []

    for name, import_cmd in std_libs:
        try:
            logging.info(f"  -> 正在导入 {name}...")
            logging.info(f"[依赖检查]   -> {name}...")
            exec(import_cmd, globals())
            logging.info(f"  ✓ {name} 导入成功")
            logging.info("✓")
        except ImportError as e:
            logging.error(f"  ✗ {name} 导入失败: {e}")
            logging.error(f"✗ ({e})")
            failed_imports.append({"name": name, "error": str(e)})

    if sys.platform != "win32":
        try:
            logging.info("  -> 正在导入 fcntl (非Windows)...")
            logging.info("[依赖检查]   -> fcntl (非Windows)...")
            import fcntl

            globals()["fcntl"] = fcntl
            logging.info("  ✓ fcntl 导入成功")
            logging.info("✓")
        except ImportError as e:
            logging.error(f"  ✗ fcntl 导入失败: {e}")
            logging.error(f"✗ ({e})")
            failed_imports.append({"name": "fcntl", "error": str(e)})
    else:
        logging.warning("  -> fcntl 模块在 Windows 平台不可用，已跳过。")
        logging.info("[依赖检查]   -> fcntl (Windows平台跳过)")
    if "eventlet" in globals():
        try:
            logging.info("  -> 正在应用 eventlet.monkey_patch()...")
            logging.info("[依赖检查]   -> eventlet.monkey_patch()...")
            eventlet.monkey_patch()
            logging.info("  ✓ eventlet.monkey_patch() 应用成功")
            logging.info("✓")
        except Exception as e:
            logging.error(f"  ✗ eventlet.monkey_patch() 应用失败: {e}")
            logging.error(f"✗ ({e})")
            failed_imports.append(
                {
                    "name": "eventlet.monkey_patch()",
                    "pip_name": "eventlet",
                    "error": str(e),
                }
            )

    if failed_imports:
        logging.critical(f"标准库导入失败，共 {len(failed_imports)} 个模块")
        print(f"\n{'='*70}")
        print(f"[致命错误] Python 标准库导入失败")
        print(f"{'='*70}")
        print(f"\n检测到 {len(failed_imports)} 个标准库导入失败：\n")
        for i, failure in enumerate(failed_imports, 1):
            print(f"  {i}. {failure['name']}")
            print(f"     错误: {failure['error']}\n")
        print("这可能表示您的 Python 环境已损坏。")
        print("请检查您的 Python 安装或尝试重新安装 Python。")
        print(f"{'='*70}\n")
        sys.exit(1)

    print("[依赖检查] ✓ 所有标准库导入成功！")
    logging.info("所有标准库导入成功！")


def import_core_third_party():
    """
    导入 'check_and_import_dependencies' 未涵盖的核心第三方库。
    """
    logging.info("=" * 80)
    logging.info("开始检查并导入核心第三方库 (Pillow, bcrypt, Flask-SocketIO)...")
    print("[依赖检查] 正在导入核心第三方库...")

    core_libs = [
        ("PIL (Pillow)", "from PIL import Image", "Pillow"),
        ("bcrypt", "import bcrypt", "bcrypt"),
        (
            "Flask-SocketIO",
            "from flask_socketio import SocketIO, emit, join_room, leave_room",
            "Flask-SocketIO",
        ),
        ("eventlet", "import eventlet", "eventlet"),
    ]

    failed_imports = []

    for display_name, import_cmd, pip_name in core_libs:
        try:
            logging.info(f"  -> 正在导入 {display_name}...")
            print(f"[依赖检查]   -> {display_name}...", end=" ")
            exec(import_cmd, globals())
            logging.info(f"  ✓ {display_name} 导入成功")
            print("✓")
        except ImportError as e:
            logging.error(f"  ✗ {display_name} 导入失败: {e}")
            print(f"✗ ({e})")
            failed_imports.append(
                {"name": display_name, "pip_name": pip_name, "error": str(e)}
            )

    if failed_imports:
        logging.critical(f"核心第三方库导入失败，共 {len(failed_imports)} 个模块")
        pip_install_list = " ".join([f["pip_name"] for f in failed_imports])

        print(f"\n{'='*70}")
        print(f"[依赖缺失错误] 核心第三方库导入失败")
        print(f"{'='*70}")
        print(f"\n检测到 {len(failed_imports)} 个核心库导入失败：\n")
        for i, failure in enumerate(failed_imports, 1):
            print(f"  {i}. {failure['name']} (pip包名: {failure['pip_name']})")
            print(f"     错误: {failure['error']}\n")
        print("请在您的终端（命令行）中运行以下命令来安装缺失的库:")
        print(f"\n  pip install {pip_install_list}\n")
        print("如果您使用的是 pip3，请运行:")
        print(f"\n  pip3 install {pip_install_list}\n")
        print(f"{'='*70}\n")
        sys.exit(1)

    print("[依赖检查] ✓ 核心第三方库导入成功！")
    logging.info("核心第三方库导入成功！")


def check_and_import_dependencies():
    """
    检查并导入所有主要的第三方库 (Flask, requests, playwright 等)。
    收集所有导入失败的模块，最后统一报告并提供安装命令。
    """
    logging.info("=" * 80)
    logging.info("开始检查并导入主要应用依赖库...")
    print("[依赖检查] 开始检查并导入主要应用依赖库...")

    global Flask, render_template_string, session, redirect, url_for, request, jsonify, make_response, g, send_file
    global CORS, pyotp, requests, openpyxl, xlrd, xlwt, chardet, sync_playwright, np
    global cssutils, playwright_available

    global cryptography, socketio

    (
        Flask,
        render_template_string,
        session,
        redirect,
        url_for,
        request,
        jsonify,
        make_response,
        g,
    ) = (None,) * 9
    (
        CORS,
        pyotp,
        requests,
        openpyxl,
        xlrd,
        xlwt,
        chardet,
        sync_playwright,
        np,
        cssutils,
    ) = (None,) * 10
    playwright_available = False

    cryptography = None

    socketio = None

    dependencies = [
        (
            "Flask Web框架",
            "from flask import Flask, render_template_string, session, redirect, url_for, request, jsonify, make_response, g, send_file, send_from_directory",
            "Flask",
        ),
        ("Flask CORS", "from flask_cors import CORS", "flask-cors"),
        ("pyotp (一次性密码)", "import pyotp", "pyotp"),
        ("requests (HTTP库)", "import requests", "requests"),
        ("openpyxl (Excel .xlsx)", "import openpyxl", "openpyxl"),
        ("xlrd (Excel .xls读取)", "import xlrd", "xlrd"),
        ("xlwt (Excel .xls写入)", "import xlwt", "xlwt"),
        ("chardet (编码检测)", "import chardet", "chardet"),
        (
            "Playwright (浏览器自动化)",
            "from playwright.sync_api import sync_playwright",
            "playwright",
        ),
        ("NumPy (科学计算)", "import numpy as np", "numpy"),
        ("cssutils (CSS解析)", "import cssutils", "cssutils"),
        ("cryptography (SSL/加密)", "import cryptography", "cryptography"),
        ("BeautifulSoup (HTML解析)", "from bs4 import BeautifulSoup", "beautifulsoup4"),
    ]

    failed_imports = []

    for display_name, import_cmd, pip_name in dependencies:
        try:
            logging.info(f"  -> 正在导入 {display_name}...")
            print(f"[依赖检查]   -> {display_name}...", end=" ")
            exec(import_cmd, globals())
            logging.info(f"  ✓ {display_name} 导入成功")
            print("✓")

            if pip_name == "playwright":
                playwright_available = True

        except ImportError as e:
            logging.error(f"  ✗ {display_name} 导入失败: {e}")
            print(f"✗ ({e})")
            failed_imports.append(
                {"name": display_name, "pip_name": pip_name, "error": str(e)}
            )

    if failed_imports:
        logging.critical(f"主要应用依赖导入失败，共 {len(failed_imports)} 个模块")
        pip_install_list = " ".join([f["pip_name"] for f in failed_imports])

        print(f"\n{'='*70}")
        print(f"[依赖缺失错误] 主要应用依赖导入失败")
        print(f"{'='*70}")
        print(f"\n检测到 {len(failed_imports)} 个依赖库导入失败：\n")
        for i, failure in enumerate(failed_imports, 1):
            print(f"  {i}. {failure['name']} (pip包名: {failure['pip_name']})")
            print(f"     错误: {failure['error']}\n")
        print("请在您的终端（命令行）中运行以下命令来安装 *所有* 缺失的依赖:")
        print(f"\n  pip install {pip_install_list}\n")
        print("如果您使用的是 pip3，请运行:")
        print(f"\n  pip3 install {pip_install_list}\n")

        if any(f["pip_name"] == "playwright" for f in failed_imports):
            print("--- 特别提示：关于 'playwright' ---")
            print("playwright 库在首次安装后，还需要安装浏览器驱动。")
            print("请在安装完 pip 包后，额外运行一次:")
            print("  playwright install chromium")
            print("--------------------------------------\n")

        print(f"{'='*70}\n")
        sys.exit(1)

    logging.info("所有主要应用依赖库导入完成！")
    print("[依赖检查] ✓ 所有主要应用依赖库导入完成！")
    logging.info("=" * 80)


def initialize_global_variables():
    """
    初始化所有全局变量和应用状态。
    """
    logging.info("开始初始化全局变量...")

    global auth_system, token_manager, html_content
    global web_sessions, web_sessions_lock, session_file_locks, session_file_locks_lock
    global session_activity, session_activity_lock
    global chrome_pool, background_task_manager
    global MAX_MEMORY_SESSIONS  # <--- [修正] 添加这一行，声明为全局变量

    auth_system = AuthSystem()
    token_manager = TokenManager(TOKENS_STORAGE_DIR)
    logging.info("认证系统和Token管理器已创建。")

    html_content = ""
    try:
        html_path = "index.html"

        with open(html_path, "r", encoding="utf-8") as file:
            html_content = file.read()
        logging.info("成功读取 index.html 文件！")

    except FileNotFoundError:
        logging.error(f"错误: 未在路径 '{html_path}' 中找到 'index.html' 文件。")
        sys.exit(1)
    except Exception as e:
        logging.error(f"读取文件时发生错误: {e}", exc_info=True)
        sys.exit(1)

    web_sessions = {}
    web_sessions_lock = threading.Lock()

    MAX_MEMORY_SESSIONS = 1000

    session_file_locks = {}
    session_file_locks_lock = threading.Lock()

    session_activity = {}
    session_activity_lock = threading.Lock()

    global browsing_activity, browsing_activity_lock
    browsing_activity = {}
    browsing_activity_lock = threading.Lock()

    logging.info("会话存储和锁已初始化。")

    chrome_pool = None
    background_task_manager = None
    logging.info("浏览器池和任务管理器已初始化为 None。")

    logging.info("全局变量初始化完成。")


# ==============================================================================
#  1. 日志系统配置
# ==============================================================================


class NoColorFileFormatter(logging.Formatter):
    """
    自定义日志格式化程序，用于在写入文件前去除ANSI颜色代码。
    """

    ansi_escape_regex = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def format(self, record):
        """
        格式化日志记录并移除颜色代码。
        """
        original_message = super().format(record)
        cleaned_message = self.ansi_escape_regex.sub("", original_message)
        return cleaned_message


class CustomLogHandler(logging.FileHandler):
    """
    自定义日志处理器，实现文件大小检查和轮转。
    """

    def __init__(
        self, filename, mode="a", encoding="utf-8", max_bytes=10 * 1024 * 1024
    ):
        """
        初始化自定义日志处理器。
        """
        self.max_bytes = max_bytes
        self.base_filename = filename
        super().__init__(filename, mode, encoding)

    def emit(self, record):
        """
        写入日志记录前检查文件大小。
        """
        try:

            if self.stream and os.path.exists(self.baseFilename):
                self.stream.flush()
                if os.path.getsize(self.baseFilename) >= self.max_bytes:
                    self.do_rollover()

            super().emit(record)

        except Exception:
            self.handleError(record)

    def do_rollover(self):
        """
        执行标准的日志轮转。
        """
        if self.stream:
            self.stream.close()
            self.stream = None

        log_dir = os.path.dirname(self.baseFilename)
        base_name = "zx-slm-tool"

        max_backup_count = 10

        for i in range(max_backup_count, 0, -1):
            old_log = os.path.join(log_dir, f"{base_name}-{i:02d}.log")

            if i == max_backup_count:
                if os.path.exists(old_log):
                    try:
                        os.remove(old_log)
                        print(
                            f"[日志轮转] 已删除最旧的日志文件: {os.path.basename(old_log)}"
                        )
                    except Exception as e:
                        print(f"[日志轮转] 删除 {os.path.basename(old_log)} 失败: {e}")
            else:
                if os.path.exists(old_log):
                    new_log = os.path.join(log_dir, f"{base_name}-{i+1:02d}.log")
                    try:
                        os.rename(old_log, new_log)
                        print(
                            f"[日志轮转] {os.path.basename(old_log)} -> {os.path.basename(new_log)}"
                        )
                    except Exception as e:
                        print(
                            f"[日志轮转] 重命名 {os.path.basename(old_log)} 失败: {e}"
                        )

        first_backup = os.path.join(log_dir, f"{base_name}-01.log")
        try:
            if os.path.exists(first_backup):
                os.remove(first_backup)

            os.rename(self.baseFilename, first_backup)
            print(
                f"[日志轮转] {os.path.basename(self.baseFilename)} -> {os.path.basename(first_backup)}"
            )
        except Exception as e:
            print(f"[日志轮转] 轮转主日志文件失败: {e}")

        self.stream = self._open()


def archive_old_logs():
    """
    归档旧的日志文件。
    """

    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir, exist_ok=True)
        print(f"[日志归档] 创建归档目录: {archive_dir}")

    log_files_to_archive = []
    for filename in os.listdir(log_dir):
        if filename == "zx-slm-tool.log" or (
            filename.startswith("zx-slm-tool-") and filename.endswith(".log")
        ):
            log_path = os.path.join(log_dir, filename)
            if os.path.isfile(log_path) and os.path.getsize(log_path) > 0:
                log_files_to_archive.append((log_path, filename))

    if not log_files_to_archive:
        print(f"[日志归档] 没有需要归档的日志文件")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    archive_filename = f"{timestamp}.zip"
    archive_path = os.path.join(archive_dir, archive_filename)

    try:
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for log_path, filename in log_files_to_archive:
                zipf.write(log_path, filename)
                print(f"[日志归档] 已压缩: {filename}")

        for log_path, filename in log_files_to_archive:
            os.remove(log_path)
            print(f"[日志归档] 已删除原文件: {filename}")

        print(f"[日志归档] 归档完成: {archive_path}")

        gc.collect()

    except Exception as e:
        print(f"[日志归档] 归档失败: {e}")

        traceback.print_exc()


def cleanup_archive_directory(archive_dir, max_size_mb):
    """
    清理归档目录，确保不超过指定大小。

    """
    if max_size_mb <= 0:
        return

    if not os.path.exists(archive_dir):
        return

    try:
        archive_files = []
        total_size = 0

        for filename in os.listdir(archive_dir):
            if filename.endswith(".zip"):
                file_path = os.path.join(archive_dir, filename)
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    mtime = os.path.getmtime(file_path)
                    archive_files.append((file_path, filename, file_size, mtime))
                    total_size += file_size

        max_size_bytes = max_size_mb * 1024 * 1024
        current_size_mb = total_size / (1024 * 1024)

        if total_size <= max_size_bytes:
            print(
                f"[归档清理] 归档目录大小: {current_size_mb:.2f}MB / {max_size_mb}MB (无需清理)"
            )
            return

        print(
            f"[归档清理] 归档目录大小: {current_size_mb:.2f}MB 超过限制 {max_size_mb}MB，开始清理..."
        )

        archive_files.sort(key=lambda x: x[3])

        deleted_count = 0
        for file_path, filename, file_size, _ in archive_files:
            if total_size <= max_size_bytes:
                break

            os.remove(file_path)
            total_size -= file_size
            deleted_count += 1
            print(f"[归档清理] 已删除: {filename} ({file_size / (1024 * 1024):.2f}MB)")

        final_size_mb = total_size / (1024 * 1024)
        print(
            f"[归档清理] 清理完成，删除了 {deleted_count} 个文件，当前大小: {final_size_mb:.2f}MB"
        )

        if deleted_count > 0:
            gc.collect()

    except Exception as e:
        print(f"[归档清理] 清理失败: {e}")

        traceback.print_exc()


def setup_logging():
    """
    配置详细的日志系统（带自定义轮转逻辑）。
    """
    log_rotation_size_mb = 10
    archive_max_size_mb = 500
    global log_dir, archive_dir
    log_dir = "logs"
    archive_dir = os.path.join(log_dir, "archive")

    try:
        if os.path.exists("config.ini"):
            config = configparser.ConfigParser()
            config.read("config.ini", encoding="utf-8")
            if "Logging" in config:
                log_rotation_size_mb = config.getint(
                    "Logging", "log_rotation_size_mb", fallback=10
                )
                archive_max_size_mb = config.getint(
                    "Logging", "archive_max_size_mb", fallback=500
                )
                log_dir = config.get("Logging", "log_dir", fallback="logs")
                archive_dir = config.get(
                    "Logging", "archive_dir", fallback="logs/archive"
                )
    except Exception as e:
        print(f"[日志系统] 读取配置失败，使用默认值: {e}")

    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        print(f"[日志系统] 创建日志目录: {log_dir}")

    archive_old_logs()

    cleanup_archive_directory(archive_dir, archive_max_size_mb)

    log_file = os.path.join(log_dir, "zx-slm-tool.log")

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    logger.handlers.clear()

    log_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] [%(funcName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    max_bytes = log_rotation_size_mb * 1024 * 1024
    file_handler = CustomLogHandler(
        log_file, mode="a", encoding="utf-8", max_bytes=max_bytes
    )
    file_handler.setLevel(logging.DEBUG)

    no_color_formatter = NoColorFileFormatter(
        log_format._fmt, datefmt=log_format.datefmt
    )
    file_handler.setFormatter(no_color_formatter)

    logger.addHandler(file_handler)

    warning_log_file = os.path.join(log_dir, "zx-slm-tool-WARNING.log")

    warning_file_handler = CustomLogHandler(
        warning_log_file,
        mode="a",
        encoding="utf-8",
        max_bytes=max_bytes,
    )

    warning_file_handler.setLevel(logging.WARNING)

    warning_no_color_formatter = NoColorFileFormatter(
        log_format._fmt,
        datefmt=log_format.datefmt,
    )
    warning_file_handler.setFormatter(warning_no_color_formatter)

    logger.addHandler(warning_file_handler)
    error_log_file = os.path.join(log_dir, "zx-slm-tool-ERROR.log")

    error_file_handler = CustomLogHandler(
        error_log_file,
        mode="a",
        encoding="utf-8",
        max_bytes=max_bytes,
    )

    error_file_handler.setLevel(logging.ERROR)

    error_no_color_formatter = NoColorFileFormatter(
        log_format._fmt,
        datefmt=log_format.datefmt,
    )
    error_file_handler.setFormatter(error_no_color_formatter)

    logger.addHandler(error_file_handler)
    global _log_buffer
    if _log_buffer:
        for level_str, msg in _log_buffer:
            level_num = getattr(logging, level_str.upper(), logging.INFO)
            logger.log(level_num, msg.rstrip())

        _log_buffer.clear()
        gc.collect()

    logging.info("=" * 80)
    logging.info("日志系统初始化完成！")
    logging.info(f"日志文件: {log_file}")
    logging.info(f"警告日志文件: {warning_log_file}")
    logging.info(f"错误日志文件: {error_log_file}")
    logging.info(f"日志级别: DEBUG (所有级别)")
    logging.info(f"日志轮转: 单文件最大{log_rotation_size_mb}MB")
    logging.info(
        f"归档目录: {archive_dir}, 最大{archive_max_size_mb}MB{'（不限制）' if archive_max_size_mb == 0 else ''}"
    )
    logging.info("=" * 80)

    return logger


def auto_init_system():
    """
    自动初始化系统，创建所有必需的文件和目录。
    """
    logging.info("=" * 80)
    logging.info("开始自动初始化系统...")
    print("[系统初始化] 开始自动初始化系统...")

    try:
        logging.info("步骤1: 创建必需的目录...")
        print("[系统初始化] 创建必需的目录...")
        _create_directories()

        logging.info("步骤2: 创建/更新配置文件...")
        print("[系统初始化] 创建/更新配置文件...")
        _create_config_ini()

        logging.info("步骤3: 创建权限配置文件...")
        print("[系统初始化] 创建权限配置文件...")
        _create_permissions_json()

        logging.info("步骤4: 创建默认管理员账号...")
        print("[系统初始化] 创建默认管理员账号...")
        _create_default_admin()

        logging.info("系统初始化完成！")
        logging.info("=" * 80)
        print("[系统初始化] 系统初始化完成！")

    except Exception as e:
        logging.error(f"系统初始化失败: {e}", exc_info=True)
        print(f"[系统初始化] 错误: 系统初始化失败 - {e}")


SCHOOL_ACCOUNTS_DIR = "school_accounts"
SYSTEM_ACCOUNTS_DIR = "system_accounts"
LOGIN_LOGS_DIR = "logs"
SESSION_STORAGE_DIR = "sessions"
TOKENS_STORAGE_DIR = "tokens"
CONFIG_FILE = "config.ini"
PERMISSIONS_FILE = "permissions.json"
SESSION_INDEX_FILE = None
LOGIN_LOG_FILE = None
AUDIT_LOG_FILE = None


def _create_directories():
    """
    创建程序运行所需的目录结构，目录路径从 config.ini 配置文件读取。
    """
    global SCHOOL_ACCOUNTS_DIR, SYSTEM_ACCOUNTS_DIR, LOGIN_LOGS_DIR
    global SESSION_STORAGE_DIR, TOKENS_STORAGE_DIR
    global SESSION_INDEX_FILE, LOGIN_LOG_FILE, AUDIT_LOG_FILE

    default_dirs = {
        "school_accounts_dir": "school_accounts",
        "system_accounts_dir": "system_accounts",
        "log_dir": "logs",
        "sessions_dir": "sessions",
        "tokens_dir": "tokens",
    }

    config_file = os.path.join(os.path.dirname(__file__), "config.ini")
    if os.path.exists(config_file):
        try:
            config = configparser.ConfigParser()
            config.read(config_file, encoding="utf-8")

            if config.has_section("System"):
                default_dirs["school_accounts_dir"] = config.get(
                    "System",
                    "school_accounts_dir",
                    fallback=default_dirs["school_accounts_dir"],
                )
                default_dirs["system_accounts_dir"] = config.get(
                    "System",
                    "system_accounts_dir",
                    fallback=default_dirs["system_accounts_dir"],
                )
                default_dirs["sessions_dir"] = config.get(
                    "System", "sessions_dir", fallback=default_dirs["sessions_dir"]
                )
                default_dirs["tokens_dir"] = config.get(
                    "System", "tokens_dir", fallback=default_dirs["tokens_dir"]
                )

            if config.has_section("Logging"):
                default_dirs["log_dir"] = config.get(
                    "Logging", "log_dir", fallback=default_dirs["log_dir"]
                )

            print(f"[配置读取] 成功从 config.ini 读取目录配置")
        except Exception as e:
            print(f"[配置读取] 警告: 读取 config.ini 失败，使用默认配置: {e}")
    else:
        print(f"[配置读取] config.ini 不存在，使用默认目录配置")

    base_dir = os.path.dirname(__file__)
    SCHOOL_ACCOUNTS_DIR = os.path.join(base_dir, default_dirs["school_accounts_dir"])
    SYSTEM_ACCOUNTS_DIR = os.path.join(base_dir, default_dirs["system_accounts_dir"])
    LOGIN_LOGS_DIR = os.path.join(base_dir, default_dirs["log_dir"])
    SESSION_STORAGE_DIR = os.path.join(base_dir, default_dirs["sessions_dir"])
    TOKENS_STORAGE_DIR = os.path.join(base_dir, default_dirs["tokens_dir"])

    directories = {
        "school_accounts": SCHOOL_ACCOUNTS_DIR,
        "system_accounts": SYSTEM_ACCOUNTS_DIR,
        "logs": LOGIN_LOGS_DIR,
        "sessions": SESSION_STORAGE_DIR,
        "tokens": TOKENS_STORAGE_DIR,
    }

    for name, directory in directories.items():
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"[目录创建] 创建目录: {name} -> {directory}")
            logging.info(f"[系统初始化] 创建目录: {name} -> {directory}")
        else:
            print(f"[目录创建] 目录已存在: {name} -> {directory}")

    user_accounts_dir = os.path.join(SCHOOL_ACCOUNTS_DIR, "user_accounts")
    if not os.path.exists(user_accounts_dir):
        os.makedirs(user_accounts_dir, exist_ok=True)
        print(f"[目录创建] 创建目录: user_accounts -> {user_accounts_dir}")
        logging.info(f"[系统初始化] 创建目录: user_accounts -> {user_accounts_dir}")
    else:
        print(f"[目录创建] 目录已存在: user_accounts -> {user_accounts_dir}")

    SESSION_INDEX_FILE = os.path.join(SESSION_STORAGE_DIR, "_index.json")
    LOGIN_LOG_FILE = os.path.join(LOGIN_LOGS_DIR, "login_history.jsonl")
    AUDIT_LOG_FILE = os.path.join(LOGIN_LOGS_DIR, "audit.jsonl")

    print(f"[目录创建] 所有目录创建完成")


def _get_default_config():
    """
    获取默认配置项字典。
    """
    config = configparser.ConfigParser()

    config["Admin"] = {"super_admin": "admin"}

    config["Guest"] = {"allow_guest_login": "true"}

    config["System"] = {
        "session_expiry_days": "7",
        "school_accounts_dir": "school_accounts",
        "system_accounts_dir": "system_accounts",
        "sessions_dir": "sessions",
        "tokens_dir": "tokens",
        "permissions_file": "permissions.json",
        "session_monitor_check_interval": "60",
        "session_inactivity_timeout": "300",
    }

    config["Logging"] = {
        "log_rotation_size_mb": "10",
        "archive_max_size_mb": "500",
        "log_dir": "logs",
        "archive_dir": "logs/archive",
    }

    config["Security"] = {
        "password_storage": "plaintext",
        "brute_force_protection": "true",
        "login_log_retention_days": "90",
    }

    config["Map"] = {
        "amap_js_key": "",
    }

    config["API"] = {
        "ip_api_key": "",
    }

    config["Captcha"] = {
        "length": "4",
        "scale_factor": "2",
        "noise_level": "0.08",
    }

    config["Features"] = {
        "enable_phone_modification": "false",
        "enable_phone_login": "false",
        "enable_phone_registration_verify": "false",
        "enable_sms_service": "false",
    }

    config["SMS_Service_SMSBao"] = {
        "username": "",
        "api_key": "",
        "signature": "【电科大跑步助手】",
        "template_register": "您的验证码是：{code}，{minutes}分钟内有效。",
        "code_expire_minutes": "5",
        "send_interval_seconds": "180",
        "rate_limit_per_account_day": "10",
        "rate_limit_per_ip_day": "20",
        "rate_limit_per_phone_day": "5",
    }

    return config


def _write_config_with_comments(config_obj, filepath):
    """
    将配置写入文件，包含详细的中文注释。

    由于ConfigParser不保留注释，这个函数手动写入带注释的配置文件。
    """
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# ========================================\n")
        f.write("# 跑步工具配置文件\n")
        f.write("# ========================================\n")
        f.write("# 说明：修改配置后需要重启程序生效\n")
        f.write("# ========================================\n\n")

        # [修复] 写入 [Config] 节，确保 theme_style 等全局参数被持久化
        if config_obj.has_section("Config") or config_obj.has_option(
            "Config", "theme_style"
        ):
            f.write("[Config]\n")
            f.write("# 全局配置参数 (主题、自动签到等)\n")

            # 优先写入已知的重要参数
            known_keys = [
                "theme_base_color",
                "theme_style",
                "auto_attendance_refresh_s",
                "attendance_user_radius_m",
            ]

            # 如果config_obj中有这些节，则写入
            if config_obj.has_section("Config"):
                for key, value in config_obj.items("Config"):
                    f.write(f"{key} = {value}\n")
            f.write("\n")

        f.write("[Admin]\n")
        f.write("# 超级管理员账号名称（有且只有一个）\n")
        f.write("# 注意：super_admin 只能在此配置文件中设置，不能在界面创建\n")
        f.write("# 默认账号: admin，默认密码: admin（首次登录后请立即修改）\n")
        f.write(
            f"super_admin = {config_obj.get('Admin', 'super_admin', fallback='admin')}\n\n"
        )

        f.write("[Guest]\n")
        f.write("# 是否允许游客登录（true/false）\n")
        f.write("# true：允许未注册用户以游客身份使用系统（权限受限）\n")
        f.write("# false：禁止游客登录，所有用户必须注册\n")
        f.write(
            f"allow_guest_login = {config_obj.get('Guest', 'allow_guest_login', fallback='true')}\n\n"
        )

        f.write("[System]\n")
        f.write("# 会话过期时间（天）\n")
        f.write("# 超过此时间未访问的会话将自动清理\n")
        f.write(
            f"session_expiry_days = {config_obj.get('System', 'session_expiry_days', fallback='7')}\n"
        )
        f.write("# 学校账号数据存储目录\n")
        f.write(
            f"school_accounts_dir = {config_obj.get('System', 'school_accounts_dir', fallback='school_accounts')}\n"
        )
        f.write("# 系统账号数据存储目录\n")
        f.write(
            f"system_accounts_dir = {config_obj.get('System', 'system_accounts_dir', fallback='system_accounts')}\n"
        )
        f.write("# 权限配置文件路径\n")
        f.write(
            f"permissions_file = {config_obj.get('System', 'permissions_file', fallback='permissions.json')}\n"
        )

        f.write("# 会话持久化数据存储目录\n")
        f.write(
            f"sessions_dir = {config_obj.get('System', 'sessions_dir', fallback='sessions')}\n"
        )
        f.write("# API令牌数据存储目录\n")
        f.write(
            f"tokens_dir = {config_obj.get('System', 'tokens_dir', fallback='tokens')}\n"
        )

        f.write("# 会话监控检查间隔时间（秒）\n")
        f.write("# 系统每隔此时间检查一次会话活跃状态，默认60秒\n")
        f.write(
            f"session_monitor_check_interval = {config_obj.get('System', 'session_monitor_check_interval', fallback='60')}\n"
        )
        f.write("# 会话不活跃超时时间（秒）\n")
        f.write(
            "# 会话超过此时间无活动（且无正在执行的任务）将被自动清理，默认300秒（5分钟）\n"
        )
        f.write(
            f"session_inactivity_timeout = {config_obj.get('System', 'session_inactivity_timeout', fallback='300')}\n\n"
        )

        # [Logging] 配置
        f.write("[Logging]\n")
        f.write("# 单个日志文件最大大小（MB）\n")
        f.write("# 超过此大小时会自动轮转到新文件（如 zx-slm-tool-01.log）\n")
        f.write(
            f"log_rotation_size_mb = {config_obj.get('Logging', 'log_rotation_size_mb', fallback='10')}\n"
        )
        f.write("# 归档目录最大大小（MB）\n")
        f.write("# 超过此大小时会删除最早的归档文件，设置为0表示不限制\n")
        f.write(
            f"archive_max_size_mb = {config_obj.get('Logging', 'archive_max_size_mb', fallback='500')}\n"
        )
        f.write("# 日志文件存储目录\n")
        f.write(f"log_dir = {config_obj.get('Logging', 'log_dir', fallback='logs')}\n")
        f.write("# 日志归档目录（启动时会自动压缩旧日志到此目录）\n")
        f.write(
            f"archive_dir = {config_obj.get('Logging', 'archive_dir', fallback='logs/archive')}\n\n"
        )

        # [Security] 配置
        f.write("[Security]\n")
        f.write("# 密码存储方式（plaintext/sha256/bcrypt）\n")
        f.write("# plaintext：明文存储（不推荐，仅用于测试）\n")
        f.write("# sha256：SHA256哈希（已弃用，不够安全）\n")
        f.write("# bcrypt：bcrypt加密（推荐，自动加盐，抗暴力破解）\n")
        f.write(
            f"password_storage = {config_obj.get('Security', 'password_storage', fallback='plaintext')}\n"
        )
        f.write("# 是否启用暴力破解防护（true/false）\n")
        f.write("# true：启用登录尝试限制和账号临时锁定\n")
        f.write(
            f"brute_force_protection = {config_obj.get('Security', 'brute_force_protection', fallback='true')}\n"
        )
        f.write("# 登录日志保留天数\n")
        f.write("# 超过此时间的登录审计日志将被清理\n")
        f.write(
            f"login_log_retention_days = {config_obj.get('Security', 'login_log_retention_days', fallback='90')}\n\n"
        )

        # [Map] 配置
        f.write("[Map]\n")
        f.write("# 高德地图 JS API 密钥\n")
        f.write("# 用于前端地图显示，请在高德开放平台申请：https://console.amap.com/\n")
        f.write("# 申请类型：Web端(JS API)，服务平台：Web端\n")
        f.write(
            f"amap_js_key = {config_obj.get('Map', 'amap_js_key', fallback='')}\n\n"
        )

        # ========================================
        # [API] 第三方API配置
        # ========================================
        f.write("# ========================================\n")
        f.write("# [API] 第三方API配置\n")
        f.write("# ========================================\n")
        f.write("[API]\n")
        f.write("# IP地理位置查询API密钥（可选）\n")
        f.write("# 用于获取用户登录IP的地理位置信息\n")
        f.write("# 留空则使用免费接口（有频率限制）\n")
        f.write(f"ip_api_key = {config_obj.get('API', 'ip_api_key', fallback='')}\n")
        f.write(
            "# 注意：验证码已改用本地生成器（见[Captcha]节），不再需要第三方API密钥\n\n"
        )

        # ========================================
        # [Captcha] 本地验证码生成器配置
        # ========================================
        f.write("# ========================================\n")
        f.write("# [Captcha] 本地验证码生成器配置\n")
        f.write("# ========================================\n")
        f.write("# 使用MicroPixelCaptcha生成黑白像素风格验证码\n")
        f.write("# 无需第三方API，更稳定、更安全、响应更快\n")
        f.write("# ========================================\n\n")
        f.write("[Captcha]\n")
        f.write("# 验证码字符数（3-6）\n")
        f.write(f"length = {config_obj.get('Captcha', 'length', fallback='4')}\n")
        f.write("# 像素细分倍数（2-4）\n")
        f.write(
            f"scale_factor = {config_obj.get('Captcha', 'scale_factor', fallback='2')}\n"
        )
        f.write("# 噪点比例（0.0-0.3）\n")
        f.write(
            f"noise_level = {config_obj.get('Captcha', 'noise_level', fallback='0.08')}\n\n"
        )

        # [Features] 功能开关配置
        f.write("[Features]\n")
        f.write("# 是否允许用户修改手机号（true/false）\n")
        f.write("# true：用户可在个人资料中修改手机号\n")
        f.write(
            f"enable_phone_modification = {config_obj.get('Features', 'enable_phone_modification', fallback='false')}\n"
        )
        f.write("# 是否支持手机号登录（true/false）\n")
        f.write("# true：用户可使用手机号+密码登录（手机号作为login_id）\n")
        f.write(
            f"enable_phone_login = {config_obj.get('Features', 'enable_phone_login', fallback='false')}\n"
        )
        f.write("# 注册时是否需要短信验证（true/false）\n")
        f.write("# true：用户注册时必须填写手机号并通过短信验证码验证\n")
        f.write(
            f"enable_phone_registration_verify = {config_obj.get('Features', 'enable_phone_registration_verify', fallback='false')}\n"
        )
        f.write("# 短信服务总开关（true/false）\n")
        f.write("# false：关闭所有短信功能，即使其他选项为true也不会发送短信\n")
        f.write(
            f"enable_sms_service = {config_obj.get('Features', 'enable_sms_service', fallback='false')}\n\n"
        )

        # [SMS_Service_SMSBao] 短信宝服务配置
        f.write("[SMS_Service_SMSBao]\n")
        f.write("# 短信宝服务配置（官网：https://www.smsbao.com/）\n")
        f.write("# 用于发送验证码、通知等短信\n")
        f.write("# 注意：使用前需要在短信宝注册账号并充值\n")
        f.write("# 短信宝账户用户名\n")
        f.write(
            f"username = {config_obj.get('SMS_Service_SMSBao', 'username', fallback='')}\n"
        )
        f.write("# 短信宝API密钥（在短信宝后台获取）\n")
        f.write(
            f"api_key = {config_obj.get('SMS_Service_SMSBao', 'api_key', fallback='')}\n"
        )
        f.write("# 短信签名（需提前在短信宝审核通过，格式：【签名内容】）\n")
        f.write(
            f"signature = {config_obj.get('SMS_Service_SMSBao', 'signature', fallback='【电科大跑步助手】')}\n"
        )
        f.write(
            "# 注册验证码短信模板（{code}会被替换为验证码，{minutes}会被替换为有效期分钟数）\n"
        )
        f.write(
            f"template_register = {config_obj.get('SMS_Service_SMSBao', 'template_register', fallback='您的验证码是：{{code}}，{{minutes}}分钟内有效。')}\n"
        )
        f.write("# 验证码有效期（分钟），默认5分钟，管理员可根据需要修改\n")
        f.write(
            f"code_expire_minutes = {config_obj.get('SMS_Service_SMSBao', 'code_expire_minutes', fallback='5')}\n"
        )
        f.write("# 发送间隔（秒），默认180秒（3分钟），防止频繁发送，增强安全性\n")
        f.write(
            f"send_interval_seconds = {config_obj.get('SMS_Service_SMSBao', 'send_interval_seconds', fallback='180')}\n"
        )
        f.write("# 单个账号每天最多发送次数（防止滥用）\n")
        f.write(
            f"rate_limit_per_account_day = {config_obj.get('SMS_Service_SMSBao', 'rate_limit_per_account_day', fallback='10')}\n"
        )
        f.write("# 单个IP每天最多发送次数（防止攻击）\n")
        f.write(
            f"rate_limit_per_ip_day = {config_obj.get('SMS_Service_SMSBao', 'rate_limit_per_ip_day', fallback='20')}\n"
        )
        f.write("# 单个手机号每天最多发送次数（防止骚扰）\n")
        f.write(
            f"rate_limit_per_phone_day = {config_obj.get('SMS_Service_SMSBao', 'rate_limit_per_phone_day', fallback='5')}\n\n"
        )

        # [SSL] 配置 - 新增SSL配置节的写入逻辑
        f.write("[SSL]\n")
        f.write("# SSL/HTTPS 配置\n")
        f.write("# 是否启用SSL（true/false）\n")
        f.write("# true：启用HTTPS协议访问\n")
        f.write("# false：使用HTTP协议访问\n")
        f.write(
            f"ssl_enabled = {config_obj.get('SSL', 'ssl_enabled', fallback='false')}\n"
        )
        f.write("# SSL证书文件路径\n")
        f.write("# 用于HTTPS服务的证书文件（PEM格式）\n")
        f.write(
            f"ssl_cert_path = {config_obj.get('SSL', 'ssl_cert_path', fallback='ssl/fullchain.pem')}\n"
        )
        f.write("# SSL私钥文件路径\n")
        f.write("# 用于HTTPS服务的私钥文件（KEY格式）\n")
        f.write(
            f"ssl_key_path = {config_obj.get('SSL', 'ssl_key_path', fallback='ssl/privkey.key')}\n"
        )
        f.write("# 是否仅允许HTTPS访问（true/false）\n")
        f.write("# true：禁止HTTP访问，所有HTTP请求将被重定向到HTTPS\n")
        f.write("# false：同时允许HTTP和HTTPS访问\n")
        f.write(
            "# 由于端口具有绑定优先级，只要开启HTTPS，但未开启此选项，HTTP可能仍然无法访问\n"
        )
        f.write(
            f"https_only = {config_obj.get('SSL', 'https_only', fallback='false')}\n\n"
        )


def _create_config_ini():
    """创建或更新config.ini配置文件（兼容旧版本，自动补全缺失参数）"""
    default_config = _get_default_config()

    if os.path.exists("config.ini"):
        print("[配置文件] config.ini 已存在，检查是否需要更新...")
        existing_config = configparser.ConfigParser()
        try:
            existing_config.optionxform = str
            existing_config.read("config.ini", encoding="utf-8")
        except configparser.DuplicateOptionError as e:
            print(f"\n[错误] 配置文件 'config.ini' 格式错误，请手动修复:")
            print(f"  - 文件中存在重复的配置项: {e}")
            print(
                f"  - 请打开 config.ini 文件，找到 [{e.section}] 部分，确保 '{e.option}' 只出现一次（不区分大小写）。"
            )
            print(f"  - 修复后重新运行程序。")
            logging.error(f"配置文件读取失败，存在重复项: {e}")
        updated = False
        for section in default_config.sections():
            if not existing_config.has_section(section):
                existing_config.add_section(section)
                updated = True
                print(f"[配置文件] 添加新的配置节: {section}")
                for key, value in default_config.items(section):
                    existing_config.set(section, key, value)
                    print(f"[配置文件] 为新节添加配置项: [{section}] {key} = {value}")
            else:
                existing_keys_lower = {
                    k.lower() for k in existing_config.options(section)
                }
                for key, value in default_config.items(section):
                    if key.lower() not in existing_keys_lower:
                        existing_config.set(section, key, value)
                        updated = True
                        print(
                            f"[配置文件] 添加缺失的配置项: [{section}] {key} = {value}"
                        )

        if updated:
            try:
                _write_config_with_comments(existing_config, "config.ini")
                logging.info("配置文件已更新：自动补全缺失参数")
                print("[配置文件] 配置文件已更新并保存（包含详细注释）")
            except Exception as e:
                print(f"[错误] 保存更新后的 config.ini 失败: {e}")
                logging.error(f"保存更新后的 config.ini 失败: {e}")
        else:
            print("[配置文件] 配置文件无需更新")
    else:
        print("[配置文件] config.ini 不存在，创建新配置文件...")
        _write_config_with_comments(default_config, "config.ini")
        print("[配置文件] 配置文件创建完成（包含详细注释）")


def _create_permissions_json():
    """创建默认的permissions.json权限配置文件"""
    if os.path.exists("permissions.json"):
        print("[权限配置] permissions.json 已存在，跳过创建")
        return

    print("[权限配置] 创建新的 permissions.json 文件...")
    permissions = {
        "permission_groups": {
            "guest": {
                "name": "游客",
                "is_system": True,
                "permissions": {
                    "view_tasks": True,
                    "create_tasks": False,
                    "delete_tasks": False,
                    "start_tasks": True,
                    "stop_tasks": True,
                    "view_map": True,
                    "record_path": True,
                    "auto_generate_path": True,
                    "view_notifications": True,
                    "mark_notifications_read": False,
                    "view_user_details": True,
                    "modify_user_settings": False,
                    "execute_multi_account": False,
                    "use_attendance": False,
                    "view_logs": False,
                    "clear_logs": False,
                    "auto_fill_password": False,
                    "import_offline": True,
                    "export_data": True,
                    "modify_params": True,
                    "manage_own_sessions": False,
                    "use_login_button": True,
                    "use_multi_account_button": False,
                    "use_import_button": False,
                    "view_messages": True,
                    "post_messages": True,
                    "delete_own_messages": False,
                    "delete_any_messages": False,
                    "modify_config": False,
                },
            },
            "user": {
                "name": "普通用户",
                "is_system": True,
                "permissions": {
                    "view_tasks": True,
                    "create_tasks": True,
                    "delete_tasks": True,
                    "start_tasks": True,
                    "stop_tasks": True,
                    "view_map": True,
                    "record_path": True,
                    "auto_generate_path": True,
                    "view_notifications": True,
                    "mark_notifications_read": True,
                    "view_user_details": True,
                    "modify_user_settings": True,
                    "execute_multi_account": True,
                    "use_attendance": True,
                    "view_logs": False,
                    "clear_logs": False,
                    "auto_fill_password": False,
                    "import_offline": True,
                    "export_data": True,
                    "modify_params": True,
                    "manage_own_sessions": True,
                    "use_login_button": True,
                    "use_multi_account_button": False,
                    "use_import_button": False,
                    "view_messages": True,
                    "post_messages": True,
                    "delete_own_messages": True,
                    "delete_any_messages": False,
                    "modify_config": True,
                    "view_session_details": True,
                },
            },
            "admin": {
                "name": "管理员",
                "is_system": True,
                "permissions": {
                    "view_tasks": True,
                    "create_tasks": True,
                    "delete_tasks": True,
                    "start_tasks": True,
                    "stop_tasks": True,
                    "view_map": True,
                    "record_path": True,
                    "auto_generate_path": True,
                    "view_notifications": True,
                    "mark_notifications_read": True,
                    "view_user_details": True,
                    "modify_user_settings": True,
                    "execute_multi_account": True,
                    "use_attendance": True,
                    "view_logs": True,
                    "clear_logs": True,
                    "manage_users": True,
                    "manage_permissions": True,
                    "reset_user_password": True,
                    "view_audit_logs": True,
                    "view_all_sessions": True,
                    "force_logout_users": True,
                    "auto_fill_password": True,
                    "import_offline": True,
                    "export_data": True,
                    "modify_params": True,
                    "manage_own_sessions": True,
                    "manage_user_sessions": True,
                    "view_session_details": True,
                    "use_login_button": True,
                    "use_multi_account_button": True,
                    "use_import_button": True,
                    "view_messages": True,
                    "post_messages": True,
                    "delete_own_messages": True,
                    "delete_any_messages": True,
                    "view_captcha_history": True,
                    "modify_config": True,
                },
            },
            "super_admin": {
                "name": "超级管理员",
                "is_system": True,
                "permissions": {
                    "view_tasks": True,
                    "create_tasks": True,
                    "delete_tasks": True,
                    "start_tasks": True,
                    "stop_tasks": True,
                    "view_map": True,
                    "record_path": True,
                    "auto_generate_path": True,
                    "view_notifications": True,
                    "mark_notifications_read": True,
                    "view_user_details": True,
                    "modify_user_settings": True,
                    "execute_multi_account": True,
                    "use_attendance": True,
                    "view_logs": True,
                    "clear_logs": True,
                    "manage_users": True,
                    "manage_permissions": True,
                    "reset_user_password": True,
                    "view_audit_logs": True,
                    "view_all_sessions": True,
                    "force_logout_users": True,
                    "manage_system": True,
                    "create_permission_groups": True,
                    "delete_permission_groups": True,
                    "modify_permission_groups": True,
                    "auto_fill_password": True,
                    "import_offline": True,
                    "export_data": True,
                    "modify_params": True,
                    "manage_own_sessions": True,
                    "manage_user_sessions": True,
                    "view_captcha_history": True,
                    "view_session_details": True,
                    "god_mode": True,
                    "use_login_button": True,
                    "use_multi_account_button": True,
                    "use_import_button": True,
                    "view_messages": True,
                    "post_messages": True,
                    "delete_own_messages": True,
                    "delete_any_messages": True,
                    "modify_config": True,
                },
            },
        },
        "user_groups": {},
        "user_custom_permissions": {},
    }

    with open("permissions.json", "w", encoding="utf-8") as f:
        json.dump(permissions, f, indent=2, ensure_ascii=False)
    print("[权限配置] permissions.json 文件创建完成")


def _create_default_admin():
    """创建默认的管理员账号"""
    admin_dir = "system_accounts"
    if not os.path.exists(admin_dir):
        os.makedirs(admin_dir, exist_ok=True)
        print(f"[管理员账号] 创建目录: {admin_dir}")

    username = "admin"
    filename = hashlib.sha256(username.encode()).hexdigest()
    admin_file = os.path.join(admin_dir, f"{filename}.json")

    if os.path.exists(admin_file):
        print("[管理员账号] 默认管理员账号已存在，跳过创建")
        logging.info(
            f"[系统初始化] 管理员账号已存在 --> 文件路径: {admin_file}, 跳过创建流程"
        )
        return

    print("[管理员账号] 创建默认管理员账号 (用户名: admin, 密码: admin)...")
    logging.info(
        f"[系统初始化] 开始创建默认管理员账号 --> 用户名: admin, 密码: admin (⚠️ 建议首次登录后立即修改), 权限组: super_admin, 文件路径: {admin_file}"
    )
    admin_data = {
        "auth_username": "admin",
        "password": "admin",
        "group": "super_admin",
        "created_at": time.time(),
        "last_login": None,
        "session_ids": [],
        "2fa_enabled": False,
        "2fa_secret": None,
        "avatar_url": "default_avatar.png",
        "max_sessions": -1,
        "theme": "light",
        "phone": "",
        "nickname": "超级管理员",
    }

    with open(admin_file, "w", encoding="utf-8") as f:
        json.dump(admin_data, f, indent=2, ensure_ascii=False)
    print("[管理员账号] 默认管理员账号创建完成")
    logging.info(
        f"[系统初始化] 管理员账号创建成功 --> 文件路径: {admin_file}, 账号信息: 用户名=admin, 权限组=super_admin, 双因素认证=未启用, 最大会话数=无限制, 主题=light"
    )


def get_session_file_path(session_id: str) -> str:
    """根据 session_id (UUID) 计算会话文件的完整路径"""
    session_hash = hashlib.sha256(session_id.encode()).hexdigest()
    return os.path.join(SESSION_STORAGE_DIR, f"{session_hash}.json")


# ==============================================================================
# 认证和权限管理系统
# ==============================================================================


class AuthSystem:
    """用户认证和权限管理系统"""

    def __init__(self):
        logging.info("=" * 80)
        logging.info("初始化AuthSystem认证系统...")
        self.config = self._load_config()
        logging.info("配置文件已加载")
        self.permissions = self._load_permissions()
        logging.info("权限配置已加载")
        self.lock = threading.Lock()
        logging.info("线程锁已创建（使用threading.Lock）")
        self._synchronize_super_admin_permissions()
        logging.info("AuthSystem初始化完成")
        logging.info("=" * 80)

    def _load_config(self):
        """加载配置文件（增强：处理重复项错误并提示用户修复）"""
        logging.debug("_load_config: 开始加载配置文件...")
        try:
            _create_config_ini()
        except configparser.DuplicateOptionError as e:
            logging.error(
                f"[系统初始化] 配置文件检查失败 --> 错误类型: {type(e).__name__}, 错误详情: {e}, 可能原因: 配置文件损坏或存在重复选项",
                exc_info=True,
            )
            print(
                f"\n[严重错误] 配置文件 ('config.ini') 已损坏。请修复上述提到的重复选项，然后重新启动程序。"
            )
            sys.exit(1)
        except Exception as e:
            logging.error(
                f"[系统初始化] 配置文件检查时发生未知错误 --> 错误类型: {type(e).__name__}, 错误详情: {e}",
                exc_info=True,
            )
            print(
                f"\n[严重错误] 检查配置文件 'config.ini' 时发生意外错误: {e}\n请检查文件格式是否正确，然后重新启动程序。"
            )
            sys.exit(1)

        config = configparser.ConfigParser()
        config.optionxform = str
        try:
            config.read(CONFIG_FILE, encoding="utf-8")
            logging.debug(
                f"_load_config: 配置文件加载完成，配置节: {list(config.sections())}"
            )
            return config
        except configparser.DuplicateOptionError as e:
            logging.error(
                f"加载配置文件 '{CONFIG_FILE}' 失败，存在重复的配置项: {e}",
                exc_info=True,
            )
            print(f"\n{'='*60}")
            print(f"[配置文件错误] 无法加载 config.ini 文件！")
            print(
                f"  错误原因: 在区域 [{e.section}] 中发现重复的选项 '{e.option}' (不区分大小写)."
            )
            print(f"  错误位置: 大约在文件的第 {e.lineno} 行附近.")
            print(f"\n  请手动打开文件 '{CONFIG_FILE}' 并进行以下操作:")
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
                f"加载配置文件 '{CONFIG_FILE}' 时发生未知错误: {e}", exc_info=True
            )
            print(f"\n[配置文件错误] 读取 config.ini 文件时发生意外错误: {e}")
            print(f"  请检查文件是否存在、是否有读取权限以及格式是否基本正确。")
            sys.exit(1)

    def find_user_by_phone(self, phone):
        """
        遍历所有系统账号，查找绑定了特定手机号的用户。
        """
        accounts_dir = SYSTEM_ACCOUNTS_DIR
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
                                json.dump(user_data, f, indent=2, ensure_ascii=False)
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
        """加载权限配置"""
        logging.debug(f"_load_permissions: 检查权限文件: {PERMISSIONS_FILE}")
        if os.path.exists(PERMISSIONS_FILE):
            with open(PERMISSIONS_FILE, "r", encoding="utf-8") as f:
                perms = json.load(f)
            logging.debug(
                f"_load_permissions: 权限配置已加载，权限组数: {len(perms.get('permission_groups', {}))}, 用户组数: {len(perms.get('user_groups', {}))}"
            )
            return perms
        logging.debug("_load_permissions: 权限文件不存在，使用默认配置")
        return {"permission_groups": {}, "user_groups": {}}

    def _save_permissions(self):
        """保存权限配置"""
        logging.debug("_save_permissions: 保存权限配置到文件...")
        with open(PERMISSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.permissions, f, indent=2, ensure_ascii=False)
        logging.debug(f"_save_permissions: 权限配置已保存到 {PERMISSIONS_FILE}")

    def get_user_file_path(self, auth_username):
        """获取用户文件路径"""
        # 修复: 强制转换为字符串，防止传入 int 类型导致 'int' object has no attribute 'encode'
        user_hash = hashlib.sha256(str(auth_username).encode()).hexdigest()
        file_path = os.path.join(SYSTEM_ACCOUNTS_DIR, f"{user_hash}.json")
        logging.debug(
            f"get_user_file_path: 用户 {auth_username} 的文件路径: {file_path}"
        )
        return file_path

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
        method = self.config.get("Security", "password_storage", fallback="plaintext")
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

        if method == "bcrypt":
            try:

                salt = bcrypt.gensalt()
                hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
                encrypted = hashed.decode("utf-8")
                logging.debug(
                    f"[密码加密] 密码已使用bcrypt加密 --> 哈希长度: {len(encrypted)}字符, 哈希前缀: {encrypted[:7]}... (✓ 安全: 自动加盐，抗暴力破解)"
                )
                return encrypted
            except ImportError:
                logging.error(
                    "[密码加密] bcrypt库未安装，无法使用bcrypt加密。请运行: pip install bcrypt"
                )
                logging.warning("[密码加密] 降级使用SHA256加密（不安全）")
                method = "encrypted"

        if method == "encrypted":
            encrypted = hashlib.sha256(password.encode()).hexdigest()
            logging.debug(
                f"[密码加密] 密码已使用SHA256加密 --> 哈希长度: {len(encrypted)}字符, 哈希值前8位: {encrypted[:8]}... (⚠️ 警告: SHA256不加盐存在安全风险，建议迁移到bcrypt)"
            )
            return encrypted

        logging.warning(
            f"[密码加密] 使用明文存储密码 --> ⚠️ 严重安全警告: 明文密码存储极度不安全，强烈建议使用bcrypt模式"
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

                result = bcrypt.checkpw(
                    input_password.encode("utf-8"), stored_password.encode("utf-8")
                )
                logging.debug(
                    f"[密码验证] bcrypt验证完成 --> 验证结果: {'✓ 成功' if result else '✗ 失败'} (✓ 安全: 使用bcrypt.checkpw，防时序攻击)"
                )
                return result
            except ImportError:
                logging.error("[密码验证] bcrypt库未安装，无法验证bcrypt密码")
                return False
            except Exception as e:
                logging.error(f"[密码验证] bcrypt验证失败 --> 错误: {e}")
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
            with open(LOGIN_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            logging.debug(
                f"[登录审计] 登录日志已写入文件 --> 文件路径: {LOGIN_LOG_FILE}, 用户: {auth_username}, 时间戳: {log_entry['timestamp']}, 格式: JSONL (每行一个JSON对象)"
            )
        except Exception as e:
            logging.error(
                f"[登录审计] 写入登录日志失败 --> 目标文件: {LOGIN_LOG_FILE}, 用户: {auth_username}, 错误类型: {type(e).__name__}, 错误详情: {e}, 注意: 日志写入失败不影响登录流程继续执行",
                exc_info=True,
            )

    def get_login_history(self, username=None, limit=100):
        """获取登录历史 - 优化：避免加载所有记录到内存"""
        if not os.path.exists(LOGIN_LOG_FILE):
            return []

        history = collections.deque(maxlen=limit * 2)

        try:
            with open(LOGIN_LOG_FILE, "r", encoding="utf-8") as f:
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
                f"[登录审计] 读取登录历史失败 --> 文件路径: {LOGIN_LOG_FILE}, 查询用户: {username if username else '全部'}, 限制条数: {limit}, 错误类型: {type(e).__name__}, 错误详情: {e}",
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

        if os.path.exists(LOGIN_LOG_FILE):
            try:
                with open(LOGIN_LOG_FILE, "r", encoding="utf-8") as f:
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

            secret = pyotp.random_base32()

            user_file = self.get_user_file_path(auth_username)
            if os.path.exists(user_file):
                with self.lock:
                    with open(user_file, "r", encoding="utf-8") as f:
                        user_data = json.load(f)

                    user_data["2fa_secret"] = secret
                    user_data["2fa_enabled"] = False

                    with open(user_file, "w", encoding="utf-8") as f:
                        json.dump(user_data, f, indent=2, ensure_ascii=False)

                totp = pyotp.TOTP(secret)
                uri = totp.provisioning_uri(
                    name=auth_username, issuer_name="Zelly's Personal Assistant Tools"
                )
                return {"success": True, "secret": secret, "qr_uri": uri}
            return {"success": False, "message": "用户不存在"}
        except ImportError:
            return {
                "success": False,
                "message": "2FA功能需要安装pyotp库：pip install pyotp",
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

                    totp = pyotp.TOTP(secret)
                    if totp.verify(verification_code):
                        user_data["2fa_enabled"] = True
                        with open(user_file, "w", encoding="utf-8") as f:
                            json.dump(user_data, f, indent=2, ensure_ascii=False)
                        return {"success": True, "message": "2FA已启用"}
                    return {"success": False, "message": "验证码错误"}
            return {"success": False, "message": "用户不存在"}
        except ImportError:
            return {"success": False, "message": "2FA功能需要安装pyotp库"}

    def verify_2fa(self, auth_username, verification_code):
        """验证2FA代码"""
        try:

            user_file = self.get_user_file_path(auth_username)
            if os.path.exists(user_file):
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)

                if not user_data.get("2fa_enabled", False):
                    return True

                secret = user_data.get("2fa_secret")
                if not secret:
                    return False

                totp = pyotp.TOTP(secret)
                return totp.verify(verification_code)
            return False
        except ImportError:
            logging.warning("2FA验证失败：pyotp库未安装")
            return True

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
        logging.info(f"register_user: 开始注册新用户: {auth_username}, 权限组: {group}")
        print(f"[用户注册] 开始注册新用户: {auth_username}, 权限组: {group}")
        with self.lock:
            if phone:
                self.unbind_phone_from_user(phone, except_username=auth_username)
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
            }

            logging.debug(f"register_user: 保存用户数据到文件: {user_file}")
            print(f"[用户注册] 保存用户数据到文件...")
            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

            logging.debug(f"register_user: 添加用户到权限组: {group}")
            self.permissions["user_groups"][auth_username] = group
            self._save_permissions()

            logging.info(
                f"新用户注册: {auth_username} (组: {group}, 手机: {phone}, 昵称: {nickname})"
            )
            print(f"[用户注册] ✓ 用户注册成功: {auth_username} (组: {group})")
            return {"success": True, "message": "注册成功"}

    def authenticate(
        self, auth_username, auth_password, ip_address="", user_agent="", two_fa_code=""
    ):
        """验证用户登录（支持2FA和暴力破解防护）"""
        logging.info(f"authenticate: 开始认证用户: {auth_username}, IP: {ip_address}")
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
            is_locked, lock_message = self.check_brute_force(auth_username, ip_address)
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

            super_admin = self.config.get("Admin", "super_admin", fallback="admin")
            if auth_username == super_admin:
                group = "super_admin"
            else:
                group = user_data.get("group", "user")

            self._log_login_attempt(
                auth_username, True, ip_address, user_agent, "success"
            )
            logging.info(f"用户登录: {auth_username} (组: {group}) from {ip_address}")
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

    def check_permission(self, auth_username, permission):
        """检查用户是否有特定权限（支持差分化权限）"""
        group = self.get_user_group(auth_username)

        group_perms = (
            self.permissions["permission_groups"].get(group, {}).get("permissions", {})
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
            self.permissions["permission_groups"].get(group, {}).get("permissions", {})
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
        for filename in os.listdir(SYSTEM_ACCOUNTS_DIR):
            if filename.endswith(".json"):
                user_file = os.path.join(SYSTEM_ACCOUNTS_DIR, filename)
                try:
                    with open(user_file, "r", encoding="utf-8") as f:
                        user_data = json.load(f)

                    last_ip = user_data.get("last_login_ip", None)
                    last_city = None
                    if last_ip:
                        try:
                            last_city = get_ip_location(last_ip)
                        except Exception as ip_e:
                            logging.warning(f"查询IP归属地失败 {last_ip}: {ip_e}")
                            last_city = "查询失败"

                    users.append(
                        {
                            "auth_username": user_data["auth_username"],
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
        """更新用户主题偏好"""
        with self.lock:
            user_file = self.get_user_file_path(auth_username)
            if not os.path.exists(user_file):
                return {"success": False, "message": "用户不存在"}

            with open(user_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            user_data["theme"] = theme

            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

            return {"success": True, "message": "主题已更新"}

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
        """删除用户（需要管理员权限）"""
        with self.lock:
            super_admin = self.config.get("Admin", "super_admin", fallback="admin")
            if auth_username == super_admin:
                return {"success": False, "message": "不允许删除超级管理员"}

            user_file = self.get_user_file_path(auth_username)
            if not os.path.exists(user_file):
                return {"success": False, "message": "用户不存在"}

            try:
                os.remove(user_file)
            except Exception as e:
                logging.error(f"删除用户文件失败: {e}")
                return {"success": False, "message": f"删除失败: {e}"}

            try:
                school_accounts_file = self._get_user_accounts_file(auth_username)
                if os.path.exists(school_accounts_file):
                    os.remove(school_accounts_file)
                    logging.info(f"已删除用户 {auth_username} 的 school accounts 文件")
            except Exception as e:
                logging.error(
                    f"删除用户 {auth_username} 的 school accounts 文件失败: {e}"
                )

            if auth_username in self.permissions.get("user_groups", {}):
                del self.permissions["user_groups"][auth_username]

            if (
                "user_custom_permissions" in self.permissions
                and auth_username in self.permissions["user_custom_permissions"]
            ):
                del self.permissions["user_custom_permissions"][auth_username]

            self._save_permissions()

            logging.info(f"用户已删除: {auth_username}")
            return {"success": True, "message": "用户已删除"}

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
            "last_used_school_account": user_data.get("last_used_school_account", ""), # 新增字段
        }

    def update_user_last_school_account(self, auth_username, school_username):
        """更新用户最后使用的学校账号"""
        if not auth_username or auth_username == 'guest':
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
                    logging.error(f"更新用户 {auth_username} 的 last_used_school_account 失败: {e}")

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
            if current_count > max_sessions:
                sessions_to_remove = old_sessions[: current_count - max_sessions + 1]
                remaining_sessions = old_sessions[current_count - max_sessions + 1 :]
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
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logging.error(f"记录审计日志失败: {e}")

    def get_audit_logs(self, username=None, action=None, limit=100):
        """获取审计日志"""
        if not os.path.exists(AUDIT_LOG_FILE):
            return []

        logs = []
        try:
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
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
                    self._update_user_file_group(super_admin_username, "super_admin")  #
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


class TokenManager:
    """管理用户登录令牌的系统"""

    def __init__(self, tokens_dir):
        logging.info("=" * 80)
        logging.info(f"TokenManager: 初始化令牌管理器，目录: {tokens_dir}")
        self.tokens_dir = tokens_dir
        self.lock = threading.Lock()
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
        logging.debug(f"_get_token_file_path: 用户 {username} 的令牌文件: {file_path}")
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

        except Exception as e:
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


class AccountSession:
    """封装单个账号的所有运行时数据、状态和操作"""

    def __init__(self, username, password, api_bridge, tag=None):
        self.username: str = username
        self.password: str = password
        self.api_bridge = api_bridge
        self.window = api_bridge.window

        self.api_client = ApiClient(self)
        self.user_data = UserData()
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

    def log(self, message: str):
        """为日志自动添加账号前缀"""
        self.api_bridge.log(f"[{self.username}] {message}")


class ApiClient:
    """处理与后端服务器网络请求的类"""

    BASE_URL = "https://zslf.zsc.edu.cn"
    API_VERSION = 66

    def __init__(self, owner_instance):
        self.session = requests.Session()
        self.app = owner_instance
        logging.debug("ApiClient已初始化，创建了新的requests.Session会话实例")

    def _get_headers(self) -> dict:
        """构建请求头，包含认证信息和设备信息"""
        headers = {
            "Connection": "keep-alive",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "com.zx.slm",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": self.app.device_ua,
        }
        try:
            auth_token = self.session.cookies.get_dict().get("shiroCookie")
        except requests.cookies.CookieConflictError:
            logging.warning(
                "CookieConflictError 即使在使用 get_dict() 时也发生，尝试手动查找..."
            )
            auth_token = None
            for cookie in self.session.cookies:
                if cookie.name == "shiroCookie":
                    auth_token = cookie.value
                    logging.warning(f"手动查找到 'shiroCookie': {auth_token[:10]}...")
                    break

        if auth_token:
            logging.debug(
                f"使用shiroCookie作为认证令牌进行Authorization请求头设置: {auth_token}"
            )
            headers["Authorization"] = auth_token
        else:
            logging.debug("未找到shiroCookie认证令牌，将不会设置Authorization请求头")
        return headers

    def _request(
        self,
        method: str,
        url: str,
        data: dict = None,
        params: dict = None,
        is_post_str=False,
        force_content_type: str = None,
    ) -> requests.Response | None:
        """统一的网络请求方法（增强：支持取消）"""

        log_func = self.app.log if hasattr(self.app, "log") else self.app.api_bridge.log
        is_offline = (
            self.app.is_offline_mode
            if hasattr(self.app, "is_offline_mode")
            else self.app.api_bridge.is_offline_mode
        )

        cancel_requested = False

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

        retries = 3
        connect_timeout = 5
        read_timeout = 10

        log_data = data
        if is_post_str and isinstance(data, str) and len(data) > 500:
            log_data = (
                data[:500] + "... (已截断，完整数据长度: " + str(len(data)) + " 字节)"
            )

        logging.debug(
            f"[网络请求] 准备发起HTTP请求 --> 请求方法: {method.upper()}, 目标URL: {url}, 重试次数配置: {retries}次, 连接超时: {connect_timeout}秒, 读取超时: {read_timeout}秒\n[请求数据]: {log_data}"
        )

        for attempt in range(retries):
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
                        post_data_bytes = urllib.parse.urlencode(data or {}).encode(
                            "utf-8"
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
                    f"[网络请求] 收到服务器响应 <-- 状态码: {resp.status_code} ({resp.reason}), 来源URL: {url}, 响应头: {dict(resp.headers)}, 响应内容长度: {len(resp.content)} 字节"
                )
                resp.raise_for_status()
                return resp

            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as net_err:
                log_func(f"网络连接失败 (第{attempt+1}/{retries}次): {net_err}")
                logging.error(
                    f"[网络请求] 网络连接失败 --> 重试次数: 第{attempt+1}次/共{retries}次, 请求方法: {method.upper()}, 目标URL: {url}, 错误类型: {type(net_err).__name__}, 错误详情: {net_err}, 连接超时配置: {connect_timeout}秒, 读取超时配置: {read_timeout}秒",
                    exc_info=False,
                )
                if attempt + 1 == retries:
                    log_func(f"网络连接最终失败: 无法连接到服务器 {self.BASE_URL}")
                    logging.error(
                        f"[网络请求] 网络连接最终失败 --> 已达到最大重试次数({retries}次), 目标服务器: {self.BASE_URL}, 无法建立连接"
                    )
                    return None
                logging.info(
                    f"[网络请求] 准备重试 --> 等待1.5秒后进行第{attempt+2}次请求尝试"
                )
                time.sleep(1.5)
                continue

            except requests.exceptions.HTTPError as http_err:
                log_func(
                    f"服务器返回错误 (第{attempt+1}次): {http_err.response.status_code}"
                )
                logging.error(
                    f"[网络请求] HTTP错误 --> 重试次数: 第{attempt+1}次/共{retries}次, 请求方法: {method.upper()}, 目标URL: {url}, HTTP状态码: {http_err.response.status_code}, 状态描述: {http_err.response.reason}, 服务器响应内容: {http_err.response.text[:200]}{'...(已截断)' if len(http_err.response.text) > 200 else ''}",
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
                time.sleep(1.5)
                continue

            except requests.exceptions.RequestException as req_err:
                log_func(f"请求发生意外错误 (第{attempt+1}次): {req_err}")
                logging.error(
                    f"[网络请求] 意外的请求异常 --> 重试次数: 第{attempt+1}次/共{retries}次, 请求方法: {method.upper()}, 目标URL: {url}, 异常类型: {type(req_err).__name__}, 异常详情: {req_err}, 完整堆栈信息如下:",
                    exc_info=True,
                )
                if attempt + 1 == retries:
                    log_func(f"请求最终失败: {req_err}")
                    logging.error(
                        f"[网络请求] 请求最终失败 --> 已达到最大重试次数({retries}次), 所有重试均失败, 异常信息: {req_err}"
                    )
                    return None
                logging.info(
                    f"[网络请求] 准备重试 --> 等待1.5秒后进行第{attempt+2}次请求尝试"
                )
                time.sleep(1.5)
                continue

        return None

    def _json(self, resp: requests.Response | None) -> dict | None:
        """安全地将Response对象解析为JSON字典"""
        log_func = self.app.log if hasattr(self.app, "log") else self.app.api_bridge.log
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
                    f"[JSON解析] JSON解码失败 --> 响应状态码: {resp.status_code}, 响应内容类型: {resp.headers.get('Content-Type', '未知')}, 解码错误位置: 第{e.lineno}行第{e.colno}列, 响应文本内容(前500字符): {resp.text[:500]}{'...(已截断)' if len(resp.text) > 500 else ''}, 错误详情: {e}"
                )
                return None
        logging.debug(f"[JSON解析] 响应对象为空，无法解析JSON")
        return None

    def login(self, username, password):
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}/app/login",
                {
                    "username": username,
                    "password": password,
                    "appVersion": self.API_VERSION,
                },
            )
        )

    def get_run_list(self, user_id, offset=0):
        return self._json(
            self._request(
                "GET",
                f"{self.BASE_URL}:9097/run/errand/getErrandList",
                {
                    "userId": user_id,
                    "offset": offset,
                    "limit": 10,
                    "appVersion": self.API_VERSION,
                },
            )
        )

    def get_run_details(self, errand_id, user_id, errand_schedule_id):
        return self._json(
            self._request(
                "GET",
                f"{self.BASE_URL}:9097/run/errand/getErrandDetail",
                {
                    "errandId": errand_id,
                    "userId": user_id,
                    "errandScheduleId": errand_schedule_id,
                    "appVersion": self.API_VERSION,
                },
            )
        )

    def get_run_history_list(self, user_id, errand_schedule_id):
        return self._json(
            self._request(
                "GET",
                f"{self.BASE_URL}:9097/run/errand/getUserErrandTrackRecord",
                {
                    "errandScheduleId": errand_schedule_id,
                    "userId": user_id,
                    "offset": 0,
                    "limit": 20,
                    "appVersion": self.API_VERSION,
                },
            )
        )

    def get_history_track_by_trid(self, trid):
        return self._json(
            self._request(
                "GET",
                f"{self.BASE_URL}:9097/run/errand/getTrackByTrid",
                {"trid": trid, "appVersion": self.API_VERSION},
            )
        )

    def submit_run_track(self, payload_str):
        return self._json(
            self._request(
                "POST",
                f"{self.BASE_URL}:9097/run/errand/addErrandTrack",
                payload_str,
                is_post_str=True,
            )
        )

    def get_run_info_by_trid(self, trid):
        return self._json(
            self._request(
                "GET",
                f"{self.BASE_URL}:9097/run/errand/getTrackRecordByTrid",
                {"trid": trid, "appVersion": self.API_VERSION},
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
        """生成一个随机的、模拟安卓设备的User-Agent字符串"""
        build_texts = [
            "TD1A.221105.001.A1",
            "TP1A.221005.003",
            "SQ3A.220705.004",
            "SP2A.220505.008",
            "SQ1D.220205.004",
            "RP1A.201005.004",
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
        ]
        android_version_map = {"T": 13, "S": 12, "R": 11, "Q": 10, "P": 9}
        random_build = random.choice(build_texts)
        build_letter = random_build.split(".")[0][0]
        android_version = android_version_map.get(build_letter, 13)
        chrome_version = f"Chrome/{random.randint(100, 120)}.0.{random.randint(4000, 6000)}.{random.randint(100, 200)}"
        return f"Mozilla/5.0 (Linux; Android {android_version}; {random.choice(phone_models)} Build/{random_build}; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 {chrome_version} Mobile Safari/537.36"

    def get_roll_call_info(self, roll_call_id, user_id):
        """获取指定签到活动的信息"""
        params = {"id": roll_call_id, "userId": user_id, "appVersion": self.API_VERSION}
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


# ==============================================================================
# 3. 后端主逻辑 (Backend API Bridge)
#    作为Python后端和WebView前端之间的桥梁，处理所有业务逻辑。
# ==============================================================================


class Api:
    """此类的方法会暴露给WebView前端的JavaScript调用"""

    def __init__(self, args):
        self.args = args
        self.window = None
        self.path_gen_callbacks = {}

        self.run_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.user_dir = SCHOOL_ACCOUNTS_DIR
        os.makedirs(self.user_dir, exist_ok=True)
        self.config_path = os.path.join(self.run_dir, "config.ini")
        self.user_config_path = self.config_path

        self.api_client = ApiClient(self)

        self._init_state_variables()

        # [优化] 将提交队列和线程池提升为类级别(Api._xxx)，实现全局单例
        # 避免每次实例化 Api (如读取配置时) 都重复创建 20 个线程
        
        # 初始化类级别的锁，防止并发初始化冲突
        if not hasattr(Api, "_submission_init_lock"):
            Api._submission_init_lock = threading.Lock()

        with Api._submission_init_lock:
            # 1. 初始化类级别的队列和事件
            if not hasattr(Api, "_static_submission_queue") or Api._static_submission_queue is None:
                Api._static_submission_queue = queue.Queue()
            
            if not hasattr(Api, "_static_submission_stop") or Api._static_submission_stop is None:
                Api._static_submission_stop = threading.Event()

            if not hasattr(Api, "_static_submission_threads"):
                Api._static_submission_threads = []

            # 2. 将当前实例的属性指向类级别的对象 (实现复用)
            self._submission_queue = Api._static_submission_queue
            self._submission_worker_stop = Api._static_submission_stop
            self._submission_worker_threads = Api._static_submission_threads

            # 3. 清理已死亡的线程
            Api._static_submission_threads[:] = [t for t in Api._static_submission_threads if t.is_alive()]
            
            # 4. 检查并补充线程 (全局只维护 20 个)
            MAX_SUBMISSION_CONCURRENCY = 20
            current_threads = len(Api._static_submission_threads)
            
            if current_threads < MAX_SUBMISSION_CONCURRENCY:
                threads_to_start = MAX_SUBMISSION_CONCURRENCY - current_threads
                # 仅在确实需要启动新线程时才记录日志，避免刷屏
                if threads_to_start > 0:
                    for i in range(threads_to_start):
                        t = threading.Thread(
                            target=Api._submission_worker_static,  # [修正] 使用静态方法，不绑定self
                            args=(Api._static_submission_queue, Api._static_submission_stop), # [修正] 显式传递参数
                            name=f"SubmissionWorker-{len(Api._static_submission_threads) + 1}",
                            daemon=True,
                        )
                        t.start()
                        Api._static_submission_threads.append(t)
                    logging.info(f"已启动 {threads_to_start} 个数据提交工作线程 (全局池共 {len(Api._static_submission_threads)} 个)")

    def _init_state_variables(self):
        """初始化或重置应用的所有状态变量"""
        self.device_ua = ""
        self.is_offline_mode = False
        self.user_data = UserData()
        self.all_run_data: list[RunData] = []
        self.current_run_idx = -1
        self.stop_run_flag = threading.Event()
        self.stop_run_flag.set()
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
            "task_gap_max_s": 3600,
            "api_fallback_line": False,
            "api_retries": 2,
            "api_retry_delay_s": 0.5,
            "ignore_task_time": True,
            "theme_base_color": "#7dd3fc",
            "theme_style": "default",
            "min_time_m": 20,
            "max_time_m": 30,
            "min_dist_m": 2000,
            "auto_attendance_enabled": False,
            "auto_attendance_refresh_s": 30,
            "attendance_user_radius_m": 40,
            "amap_js_key": "",
        }

        self.server_attendance_radius_m = 0.0
        self.last_radius_fetch_time = 0

        self.auto_refresh_thread: threading.Thread | None = None
        self.stop_auto_refresh = threading.Event()
        self.stop_auto_refresh.set()

        self.multi_auto_refresh_thread: threading.Thread | None = None
        self.stop_multi_auto_refresh = threading.Event()
        self.stop_multi_auto_refresh.set()

        self.params = self.global_params.copy()

        self._first_center_done = False

        self.is_multi_account_mode = False
        if hasattr(self, "accounts"):
            for acc in self.accounts.values():
                if acc.worker_thread and acc.worker_thread.is_alive():
                    acc.stop_event.set()
        self.accounts: dict[str, AccountSession] = {}
        self.multi_run_stop_flag = threading.Event()
        self.multi_run_stop_flag.set()

        self._load_tasks_lock = threading.RLock()
        self._load_tasks_inflight = False
        self.multi_run_only_incomplete = True

    def set_multi_run_only_incomplete(self, flag: bool):
        """
        设置多账号模式下“仅执行未完成”的全局开关，并立即刷新全局按钮。
        """
        try:
            self.multi_run_only_incomplete = bool(flag)
            self._update_multi_global_buttons()
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def log(self, message):
        """将日志消息通过 WebSocket 发送到前端界面显示"""
        session_id = getattr(self, "_web_session_id", None)
        logging.info(message)
        if session_id and socketio:
            try:
                socketio.emit("log_message", {"msg": str(message)}, room=session_id)
            except Exception as e:
                logging.error(
                    f"WebSocket emit log failed for session {session_id[:8]}: {e}"
                )
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
        if chardet:
            det = chardet.detect(raw) or {}
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

        参数:
            auth_username: 认证用户名（system_accounts中的用户名）

        返回:
            文件路径字符串
        """
        user_accounts_dir = os.path.join(SCHOOL_ACCOUNTS_DIR, "user_accounts")
        return os.path.join(user_accounts_dir, f"{auth_username}.json")

    def _load_user_school_accounts(self, auth_username):
        """
        加载指定认证用户的所有 school_account 账户密码和UA。

        参数:
            auth_username: 认证用户名

        返回:
            字典，格式为 {school_username: {"password": "xxx", "ua": "xxx"}, ...}
            或旧格式 {school_username: password, ...}（向后兼容）
        """
        if not auth_username or auth_username == "guest":
            return {}

        file_path = self._get_user_accounts_file(auth_username)
        if not os.path.exists(file_path):
            return {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logging.debug(
                f"成功加载用户 {auth_username} 的 school_accounts，共 {len(data)} 个账户"
            )
            return data
        except Exception as e:
            logging.error(
                f"加载用户 {auth_username} 的 school_accounts 失败: {e}", exc_info=True
            )
            return {}

    def _save_user_school_accounts(self, auth_username, accounts_dict):
        """
        保存指定认证用户的所有 school_account 账户密码和UA。

        参数:
            auth_username: 认证用户名
            accounts_dict: 字典，格式为 {school_username: {"password": "xxx", "ua": "xxx"}, ...}
        """
        if not auth_username or auth_username == "guest":
            logging.debug("游客用户不保存 school_accounts")
            return

        file_path = self._get_user_accounts_file(auth_username)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(accounts_dict, f, ensure_ascii=False, indent=2)
            logging.debug(
                f"成功保存用户 {auth_username} 的 school_accounts，共 {len(accounts_dict)} 个账户"
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

        accounts[school_username] = {"password": password, "ua": ua if ua else ""}
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

    def _save_config(self, username, password=None, ua=None):
        """保存指定用户的配置到 user/<username>.ini；当 password 为 None 时保留现有密码；当 ua 为 None 时保留现有 UA。同时更新主 config.ini 的 LastUser 和 amap_js_key。"""
        logging.debug(
            f"Saving config: username={username!r}, password provided: {password is not None}, ua provided: {ua is not None}"
        )

        user_ini_path = os.path.join(self.user_dir, f"{username}.ini")

        self.normalize_chinese_config_to_english(user_ini_path)
        cfg_to_save = configparser.RawConfigParser()
        cfg_to_save.optionxform = str
        if os.path.exists(user_ini_path):
            try:
                cfg_to_save.read(user_ini_path, encoding="utf-8")
            except Exception as e:
                logging.warning(
                    f"读取旧配置文件 {user_ini_path} 失败: {e}, 将创建新的。"
                )

        if not cfg_to_save.has_section("Config"):
            cfg_to_save.add_section("Config")
        if not cfg_to_save.has_section("System"):
            cfg_to_save.add_section("System")

        cfg_to_save.set("Config", "Username", username)
        if password is not None:
            cfg_to_save.set("Config", "Password", password)
        else:
            if not cfg_to_save.has_option("Config", "Password"):
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
                                            "Config", "Password", recovered_password
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
            cfg_to_save.set("System", "UA", ua)
        params_to_save = self.params
        if self.is_multi_account_mode and username in self.accounts:
            params_to_save = self.accounts[username].params
        for k, v in params_to_save.items():
            if k in self.global_params and k != "amap_js_key":
                cfg_to_save.set("Config", k, str(v))

        try:
            with open(user_ini_path, "w", encoding="utf-8") as f:
                cfg_to_save.write(f)
            logging.debug(f"Saved user config for {username} -> {user_ini_path}")
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

        main_cfg = configparser.RawConfigParser()
        main_cfg.optionxform = str

        if os.path.exists(self.config_path):
            try:
                main_cfg.read(self.config_path, encoding="utf-8")
            except Exception as e:
                logging.warning(
                    f"读取主配置文件 {self.config_path} 失败: {e}, 将创建新的。"
                )

        # [修正] 不再将 LastUser 写入 config.ini，而是更新到系统账号文件
        if hasattr(self, "auth_username") and self.auth_username and self.auth_username != "guest":
            if 'auth_system' in globals():
                auth_system.update_user_last_school_account(self.auth_username, username)
                logging.debug(f"已更新用户 {self.auth_username} 的最后使用学校账号为: {username}")

        # 下面仅保留必要的全局配置写入（如 Map Key）
        if not main_cfg.has_section("Map"):
            main_cfg.add_section("Map")

        amap_key_in_memory = self.global_params.get("amap_js_key", "").strip()
        amap_key_in_file = main_cfg.get("Map", "amap_js_key", fallback="").strip()

        if amap_key_in_memory:
            main_cfg.set("Map", "amap_js_key", amap_key_in_memory)
        elif amap_key_in_file:
            self.global_params["amap_js_key"] = amap_key_in_file
        else:
            main_cfg.set("Map", "amap_js_key", "")

        # 只有当确实有内容变更需要写入 config.ini 时才写入 (这里主要是 Map Key)
        # 如果只是更新了用户配置，没必要每次都覆写 config.ini
        try:
            _write_config_with_comments(main_cfg, self.config_path)
            logging.debug(f"更新主配置文件 {self.config_path} 成功 (Map Key)")
        except Exception as e:
            logging.error(f"写入主配置文件 {self.config_path} 失败: {e}", exc_info=True)

    def _load_global_config(self):
        """从主 config.ini 加载全局配置（优先读取新版 Map.amap_js_key，兼容旧版 System.AmapJsKey）"""
        if not os.path.exists(self.config_path):
            return
        cfg = configparser.RawConfigParser()
        cfg.optionxform = str
        try:
            cfg.read(self.config_path, encoding="utf-8")

            amap_key = cfg.get("Map", "amap_js_key", fallback="")

            if not amap_key:
                amap_key = cfg.get("System", "AmapJsKey", fallback="")
                if amap_key:
                    if not cfg.has_section("Map"):
                        cfg.add_section("Map")
                    cfg.set("Map", "amap_js_key", amap_key)
                    with open(self.config_path, "w", encoding="utf-8") as f:
                        cfg.write(f)
                    logging.info("已将AmapJsKey从旧版[System]迁移到新版[Map]")

            self.global_params["amap_js_key"] = amap_key

            # [修正] 加载全局主题配置 (仅当配置文件中存在时才覆盖内存中的值)
            if cfg.has_option("Config", "theme_base_color"):
                self.global_params["theme_base_color"] = cfg.get(
                    "Config", "theme_base_color"
                )

            if cfg.has_option("Config", "theme_style"):
                self.global_params["theme_style"] = cfg.get("Config", "theme_style")

            # [修正] auto_attendance_enabled 不再从全局配置文件读取，而是依赖会话持久化或默认值
            # 仅保留刷新间隔和半径作为全局默认值（如果需要的话），或者也完全移除
            # 这里根据指示移除 enabled 的读取
            
            if cfg.has_option("Config", "auto_attendance_refresh_s"):
                self.global_params["auto_attendance_refresh_s"] = cfg.getint(
                    "Config", "auto_attendance_refresh_s"
                )

            if cfg.has_option("Config", "attendance_user_radius_m"):
                self.global_params["attendance_user_radius_m"] = cfg.getint(
                    "Config", "attendance_user_radius_m"
                )

            logging.info(
                f"Loaded global config: AmapKey={'Yes' if amap_key else 'No'}, Theme={self.global_params.get('theme_base_color')}"
            )
        except Exception as e:
            logging.error(
                f"加载全局配置文件 {self.config_path} 失败: {e}", exc_info=True
            )

    def _load_config(self, username):
        """从.ini文件加载指定用户的配置"""
        self.user_config_path = os.path.join(self.user_dir, f"{username}.ini")
        if not os.path.exists(self.user_config_path):
            return None

        self.normalize_chinese_config_to_english(self.user_config_path)

        cfg = configparser.ConfigParser(strict=False)
        try:
            cfg.read(self.user_config_path, encoding="utf-8")
        except Exception as e:
            logging.warning(f"解析用户配置文件 {username} 时出错 (已忽略): {e}")

        password = cfg.get("Config", "Password", fallback="")
        if not password:
            try:
                with open(
                    self.user_config_path, "r", encoding="utf-8", errors="ignore"
                ) as rf:
                    for line in rf:
                        clean_line = line.strip()
                        temp_line_for_check = clean_line.lower().replace(" ", "")
                        if temp_line_for_check.startswith(
                            "password="
                        ) or temp_line_for_check.startswith("密码="):
                            parts = clean_line.split("=", 1)
                            if len(parts) == 2:
                                password = parts[1].strip()
                                if password:
                                    break
            except Exception:
                pass

        ua = None

        if hasattr(self, "auth_username") and self.auth_username:
            school_password = self._get_school_account_password(
                self.auth_username, username
            )
            school_ua = self._get_school_account_ua(self.auth_username, username)
            if school_password:
                password = school_password
                logging.debug(
                    f"从用户 {self.auth_username} 的 school_accounts 加载了 {username} 的密码"
                )
            if school_ua:
                ua = school_ua
                logging.debug(
                    f"从用户 {self.auth_username} 的 school_accounts 加载了 {username} 的UA"
                )

        target_params = self.params
        if self.is_multi_account_mode and username in self.accounts:
            target_params = self.accounts[username].params

        if not ua:
            ua = cfg.get("System", "UA", fallback="")
        if self.is_multi_account_mode and username in self.accounts:
            self.accounts[username].device_ua = ua
        else:
            self.device_ua = ua

        for k in self.global_params:
            if k in target_params:
                try:
                    if cfg.has_option("Config", k):
                        val_str = cfg.get("Config", k)
                        original_type = type(target_params[k])
                        if original_type is bool:
                            target_params[k] = val_str.lower() in (
                                "true",
                                "1",
                                "t",
                                "yes",
                            )
                        else:
                            target_params[k] = original_type(val_str)
                except ValueError:
                    logging.warning(
                        f"Could not parse config value for '{k}' for user {username}. Using default."
                    )
                    pass
        logging.debug(f"已成功加载用户配置: {username}")
        return password

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

        cfg = configparser.ConfigParser()
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

    def get_initial_data(self):
        """应用启动时由前端调用，获取初始用户列表和最后登录用户"""

        try:
            session_id = getattr(self, "_web_session_id", None)
            if session_id:
                with browsing_activity_lock:
                    browsing_activity[session_id] = time.time()
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
                has_view_all_permission = False

                if auth_group in ["admin", "super_admin"]:
                    has_view_all_permission = True
                    logging.debug(
                        f"用户 {auth_username} 是管理员，拥有查看所有账户的权限"
                    )
                elif hasattr(self, "auth_system"):
                    try:
                        has_view_all_permission = auth_system.check_permission(
                            auth_username, "auto_fill_password"
                        )
                        if has_view_all_permission:
                            logging.debug(
                                f"用户 {auth_username} 通过自定义权限获得了查看所有账户的权限"
                            )
                    except Exception as e:
                        logging.warning(
                            f"检查用户 {auth_username} 的 auto_fill_password 权限时出错: {e}"
                        )
                        pass

                if has_view_all_permission:
                    users = all_users
                    logging.debug(
                        f"用户 {auth_username} 有权限，返回所有 {len(users)} 个学校账户"
                    )
                else:
                    users = []

                    school_accounts = self._load_user_school_accounts(auth_username)

                    if school_accounts:
                        users = list(school_accounts.keys())
                        logging.debug(
                            f"普通用户 {auth_username} 无全局权限，返回其自己的 {len(users)} 个学校账户"
                        )
                    else:
                        logging.debug(f"普通用户 {auth_username} 还没有任何学校账户")
            else:
                users = all_users
                logging.debug(
                    f"未认证用户请求 get_initial_data，返回所有 {len(users)} 个账户（向后兼容）"
                )

            cfg = configparser.RawConfigParser()
            cfg.optionxform = str
            cfg.read(self.config_path, encoding="utf-8")

            # [修正] LastUser 不再从 config.ini 读取，而是从当前登录用户的系统账号信息中获取
            last_user = ""
            
            # 尝试获取当前认证用户的 last_used_school_account
            auth_username = getattr(self, "auth_username", None)
            is_guest = getattr(self, "is_guest", False)
            
            if auth_username and not is_guest and 'auth_system' in globals():
                try:
                    details = auth_system.get_user_details(auth_username)
                    if details:
                        last_user = details.get("last_used_school_account", "")
                except Exception as e:
                    logging.warning(f"获取用户 {auth_username} 的 LastUser 失败: {e}")

            # 验证 last_user 是否有效
            if last_user and last_user not in all_users:
                logging.debug(f"LastUser '{last_user}' 不在可用列表中，已忽略。")
                last_user = ""
                try:
                    with open(self.config_path, "w", encoding="utf-8") as f:
                        cfg.write(f)
                except Exception as e:
                    logging.error(f"写回 config.ini 失败：{e}", exc_info=True)
                last_user = ""

            self._load_global_config()

            is_logged_in = hasattr(self, "login_success") and self.login_success
            user_info = None
            if is_logged_in and hasattr(self, "user_info"):
                user_info = self.user_info

            logging.debug(
                f"Initial users={users}, last user={last_user}, logged_in={is_logged_in}"
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
            logging.debug(f"【本地验证码】加载验证码设置: {captcha_settings}")

            response_data = {
                "success": True,
                "users": users,
                "lastUser": last_user,
                "amap_key": self.global_params.get("amap_js_key", ""),
                "isLoggedIn": is_logged_in,
                "userInfo": user_info,
                "is_authenticated": is_authenticated,
                "auth_username": auth_username,
                "auth_group": auth_group,
                "is_guest": is_guest,
                "is_multi_account_mode": getattr(self, "is_multi_account_mode", False),
                "captcha_settings": captcha_settings,
            }

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
                "message": "后端无法连接服务器，已切换到离线模式",
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
                session_file = get_session_file_path(current_session_id)
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
                return jsonify(
                    {
                        "success": True,
                        "sessions": guest_session_info,
                        "max_sessions": -1,
                    }
                )
            else:
                return {"success": True, "sessions": []}

        try:
            session_ids = auth_system.get_user_sessions(auth_username)
            logging.debug(
                f"Found {len(session_ids)} linked session IDs for user {auth_username}"
            )

            sessions_info = []
            current_session_id = getattr(self, "_web_session_id", None)

            for sid in session_ids:
                session_file = get_session_file_path(sid)
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
                                    "is_current": sid == session_id,
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

    def save_amap_key(self, api_key: str):
        """由JS调用，保存高德地图API Key到主配置文件"""
        try:
            self.global_params["amap_js_key"] = api_key
            cfg = configparser.RawConfigParser()
            cfg.optionxform = str
            if os.path.exists(self.config_path):
                cfg.read(self.config_path, encoding="utf-8")

            if not cfg.has_section("Map"):
                cfg.add_section("Map")
            cfg.set("Map", "amap_js_key", api_key)

            _write_config_with_comments(cfg, self.config_path)

            self.log("高德地图API Key已保存。")
            logging.info("已成功保存新的高德地图JavaScript API密钥")
            return {"success": True}
        except Exception as e:
            self.log(f"保存高德地图API Key失败: {e}")
            logging.error(f"保存高德地图JavaScript API密钥失败: {e}")
            return {"success": False, "message": str(e)}
        except Exception as e:
            self.log(f"API Key保存失败: {e}")
            logging.error(
                f"保存高德地图JavaScript API密钥时发生异常: {e}", exc_info=True
            )
            return {"success": False, "message": str(e)}

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
        is_authenticated = hasattr(self, "is_authenticated") and self.is_authenticated
        if is_authenticated and auth_username and not is_guest:
            has_view_all_permission = False

            if auth_group in ["admin", "super_admin"]:
                has_view_all_permission = True
                logging.debug(f"用户 {auth_username} 是管理员，可以查看所有账户密码")
            elif hasattr(self, "auth_system"):
                try:
                    has_view_all_permission = auth_system.check_permission(
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
                school_accounts = self._load_user_school_accounts(auth_username)

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

        password = self._load_config(username)

        if password is None:
            ua = ""
        else:
            ua = self.device_ua or ""

        logging.debug(
            f"on_user_selected: username={username}, ua={ua}, password={'***' if password else 'empty'}"
        )

        info = {"name": self.user_data.name, "student_id": self.user_data.student_id}

        return {
            "password": password or "",
            "ua": ua,
            "params": self.params,
            "userInfo": info,
        }

    def generate_new_ua(self):
        """生成一个新的UA并保存"""
        logging.info("API调用: generate_new_ua - 生成新的随机User-Agent字符串")
        self.device_ua = ApiClient.generate_random_ua()
        cfg = configparser.ConfigParser()
        if os.path.exists(self.user_config_path):
            cfg.read(self.user_config_path, encoding="utf-8")
            if not cfg.has_section("System"):
                cfg.add_section("System")
            cfg.set("System", "UA", self.device_ua)
            with open(self.user_config_path, "w", encoding="utf-8") as f:
                cfg.write(f)
        logging.info(f"已成功生成新的User-Agent字符串: {self.device_ua}")
        return self.device_ua

    def login(self, username, password):
        logging.info(f"API调用: login - 用户登录请求，用户名: '{username}'")
        if not username or not password:
            return {"success": False, "message": "用户名和密码不能为空！"}

        self.log("正在登录...")
        logging.debug(f"正在尝试为用户进行登录认证: 用户名={username}")
        self.user_data = UserData()
        input_username = username
        if not self.device_ua:
            self.device_ua = ApiClient.generate_random_ua()

        resp = self.api_client.login(input_username, password)
        if not resp or not resp.get("success"):
            msg = (
                resp.get("message", "未知错误")
                if resp
                else "网络连接失败，无法连接到学校服务器。"
            )
            self.log(f"服务器反馈登录失败：{msg}")
            logging.warning(f"用户登录失败: {msg}")
            return {"success": False, "message": msg}

        self.log("登录成功，正在解析用户信息...")
        data = resp.get("data", {})
        user_info = data.get("userInfo", {})
        dept_info = data.get("deptInfo", {})
        ud = self.user_data

        ud.name = user_info.get("name", "")
        ud.phone = user_info.get("phone", "")
        ud.student_id = user_info.get("account", "")
        ud.id = user_info.get("id", "")
        ud.username = ud.student_id or input_username

        ud.registration_time = user_info.get("createtime", "")
        ud.first_login_time = user_info.get("firstlogin", "")
        ud.id_card = user_info.get("iDcard", "")
        ud.current_login_time = user_info.get("logintime", "")
        ud.last_login_time = dept_info.get("logintime", "")
        ud.gender = dept_info.get("sexValue", "")
        ud.school_name = dept_info.get("schoolName", "")
        ud.attribute_type = dept_info.get("typeValue", "")

        try:
            if ud.username and os.path.exists(self.user_dir):
                backup_filename = f"{ud.username}_backup.json"
                backup_filepath = os.path.join(self.user_dir, backup_filename)

                backup_data = {
                    "userInfo": user_info,
                    "deptInfo": dept_info,
                    "backup_timestamp": time.time(),
                }

                with open(backup_filepath, "w", encoding="utf-8") as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)

                logging.info(f"已成功备份 user_info 到: {backup_filepath}")
            elif not ud.username:
                logging.warning("备份 user_info 失败：无法确定用户名(学号)")

        except Exception as e:
            logging.error(f"备份 user_info 失败: {e}", exc_info=True)
        self._save_config(ud.username, password, self.device_ua)

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
            self._fetch_server_attendance_radius_if_needed(self.api_client, None)
        except Exception as e:
            self.log(f"获取签到半径失败: {e}")
            logging.warning(f"Failed to fetch attendance radius post-login: {e}")

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
        try:
            self.stop_auto_refresh.clear()
            if (
                self.auto_refresh_thread is None
                or not self.auto_refresh_thread.is_alive()
            ):
                self.auto_refresh_thread = threading.Thread(
                    target=self._auto_refresh_worker, daemon=True
                )
                self.auto_refresh_thread.start()
        except Exception as e:
            self.log(f"启动自动刷新线程失败: {e}")

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

        auth_group = getattr(self, "auth_group", "guest")

        return {
            "success": True,
            "userInfo": user_info_dict,
            "ua": self.device_ua,
            "amap_key": self.global_params.get("amap_js_key", ""),
            "auth_group": auth_group,
            "cached_notifications": cached_notifications,
        }

    def logout(self):
        """处理注销逻辑"""
        logging.info("API调用: logout - 用户注销登出操作")
        self.log("已注销。")
        logging.info("用户已成功登出，正在清除会话和状态数据")
        try:
            self.stop_auto_refresh.set()
            if self.auto_refresh_thread and self.auto_refresh_thread.is_alive():
                self.auto_refresh_thread.join(timeout=1.0)
            self.auto_refresh_thread = None
        except Exception as e:
            logging.warning(f"停止自动刷新线程失败: {e}")

        self.login_success = False
        self.user_info = None

        self._init_state_variables()
        self._load_global_config()
        self.api_client.session.cookies.clear()
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
                logging.debug("load_tasks skipped: another refresh is in-flight.")
                tasks_for_js = []
                for run in self.all_run_data:
                    task_dict = run.__dict__.copy()
                    task_dict["info_text"] = self._get_task_info_text(run)
                    tasks_for_js.append(task_dict)
                return {"success": True, "tasks": tasks_for_js}

            self._load_tasks_inflight = True
            try:
                self.log("正在获取任务列表...")
                logging.debug("正在从服务器获取任务运行列表数据")

                self.all_run_data = []
                seen_keys: set[str] = set()
                offset = 0
                dup_count = 0

                while True:
                    resp = self.api_client.get_run_list(self.user_data.id, offset)
                    if not resp or not resp.get("success"):
                        self.log("获取任务列表失败。")
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

                        run = RunData()
                        run.run_name = td.get("eName")

                        try:
                            run.status = int(td.get("isExecute") or 0)
                        except (TypeError, ValueError):
                            run.status = (
                                1 if str(td.get("isExecute")).strip() == "1" else 0
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

                self.log(f"任务列表加载完毕，共 {len(self.all_run_data)} 项。")
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

    def _get_task_info_text(self, run: RunData) -> str:
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
                except Exception:
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

        self.log(f"正在加载任务详情...")
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
                                temp_coords.append((float(pt[0]), float(pt[1])))
                            except (TypeError, ValueError):
                                logging.warning(
                                    f"Invalid coordinate in recommended path: {pt}"
                                )
                    if i < len(walk_paths) - 1:
                        temp_coords.append((0.0, 0.0))
            run_data.recommended_coords = temp_coords
            run_data.details_fetched = True
            self.log("任务详情加载成功。")
            logging.debug(
                f"任务详情获取成功: 目标点数量={len(run_data.target_points)}, 推荐路径点数量={len(run_data.recommended_coords)}"
            )
            task_dict = run_data.__dict__.copy()
            task_dict["target_range_m"] = self.target_range_m
            return {"success": True, "details": task_dict}
        else:
            self.log("获取任务详情失败。")
            logging.warning("从服务器获取任务详情失败")
            return {"success": False, "message": "获取任务详情失败"}

    def set_draft_path(self, coords):
        """接收前端手动绘制的草稿路径"""

        if coords is None:
            coords_len = 0
            logging.info(f"API调用: set_draft_path - 接收到空的(None)草稿路径")
        else:
            try:
                coords_len = len(coords)
            except TypeError:
                logging.error(
                    f"set_draft_path 失败：coords 参数不是一个列表: {type(coords)}",
                    exc_info=True,
                )
                return {"success": False, "message": "无效的路径数据格式"}

        logging.info(f"API调用: set_draft_path - 设置草稿路径，点数: {coords_len}")

        if not (0 <= self.current_run_idx < len(self.all_run_data)):
            logging.warning(
                f"set_draft_path 失败：任务索引无效 (Index: {self.current_run_idx}, List length: {len(self.all_run_data)})"
            )
            return {"success": False, "message": "未选择任务或任务列表已失效"}

        try:
            run = self.all_run_data[self.current_run_idx]

            draft_coords_list = []
            if coords:
                for c in coords:
                    if not isinstance(c, dict):
                        logging.warning(
                            f"set_draft_path: 跳过无效的坐标点（非字典）: {c}"
                        )
                        continue

                    lng = c.get("lng")
                    lat = c.get("lat")

                    if lng is None or lat is None:
                        logging.warning(
                            f"set_draft_path: 跳过无效的坐标点（缺少lng或lat）: {c}"
                        )
                        continue

                    draft_coords_list.append((lng, lat, c.get("isKey", 0)))

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
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
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

        if np is not None:
            try:
                lons = np.array([c[0] for c in coords])
                lats = np.array([c[1] for c in coords])

                delta_lons = np.diff(lons)
                delta_lats = np.diff(lats)

                lat1_rad = np.radians(lats[:-1])
                lat2_rad = np.radians(lats[1:])
                delta_lat_rad = np.radians(delta_lats)
                delta_lon_rad = np.radians(delta_lons)

                R = 6371000
                a = (
                    np.sin(delta_lat_rad / 2) ** 2
                    + np.cos(lat1_rad)
                    * np.cos(lat2_rad)
                    * np.sin(delta_lon_rad / 2) ** 2
                )
                c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
                distances = R * c

                return np.sum(distances)
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

        self.log("正在处理路径...")
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
                        seg_start_gps[0] + ratio * (seg_end_gps[0] - seg_start_gps[0]),
                        seg_start_gps[1] + ratio * (seg_end_gps[1] - seg_start_gps[1]),
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
        self.log(f"处理完成。")
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
        self, run_data: RunData, current_lon: float, current_lat: float
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

        dist = self._calculate_distance_m(current_lon, current_lat, tar_lon, tar_lat)

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

    def start_single_run(self):
        """开始执行单个任务"""
        logging.info("API调用: start_single_run - 开始执行单个任务")
        if not self.stop_run_flag.is_set():
            return {"success": False, "message": "已有任务在运行"}
        if (
            self.current_run_idx == -1
            or not self.all_run_data[self.current_run_idx].run_coords
        ):
            return {"success": False, "message": "请选择任务并生成路线"}

        self.stop_run_flag.clear()
        run_data = self.all_run_data[self.current_run_idx]
        run_data.target_sequence = 0
        run_data.is_in_target_zone = False
        self._first_center_done = False

        logging.info(f"正在启动单任务执行: 任务名称={run_data.run_name}")
        threading.Thread(
            target=self._run_submission_thread,
            args=(run_data, self.current_run_idx, self.api_client, False),
            daemon=True,
        ).start()
        return {"success": True}

    def stop_run(self):
        """停止当前所有正在执行的任务"""
        logging.info("API调用: stop_run - 停止当前所有正在执行的任务")
        self.log("正在停止任务...")
        logging.info("已收到停止运行任务的信号")
        self.stop_run_flag.set()
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
        run_data: RunData,
        chunk,
        start_time,
        is_finish,
        chunk_start_index,
        client: ApiClient,
        user: UserData,
    ):
        """将一小块轨迹数据提交到服务器"""
        log_func = (
            client.app.log if hasattr(client.app, "log") else client.app.api_bridge.log
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
                    "locatetime": str(int(time.time() * 1000)),
                    "dis": f"{distance:.1f}",
                    "count": str(int(time_elapsed_before_chunk_ms / 1000)),
                }
            )
            last_point_gps = (lon, lat, dur_ms)
            chunk_total_dist += distance
            chunk_total_dur += dur_ms

        payload = {
            "scheduleId": run_data.errand_schedule,
            "userId": user.id,
            "userName": user.name or "",
            "runLength": str(int(chunk_total_dist)),
            "runTime": str(chunk_total_dur),
            "startPoint": "",
            "endPoint": "",
            "startTime": start_time,
            "trid": run_data.trid,
            "sid": "",
            "tid": "",
            "speed": (
                f"{(run_data.total_run_distance_m / run_data.total_run_time_s):.2f}"
                if run_data.total_run_time_s > 0
                else ""
            ),
            "finishType": "1" if is_finish else "0",
            "coordinate": json.dumps(coords_list, separators=(",", ":")),
            "appVersion": ApiClient.API_VERSION,
        }

        if is_finish:
            payload["endTime"] = str(int(time.time() * 1000))

        payload_str = urllib.parse.urlencode(payload)

        logging.debug(
            f"[{user.name}] 正在入队提交数据包, 大小: {len(payload_str)} 字节"
        )

        resp = self._enqueue_submission(client, payload_str, wait_timeout=60.0)
        success = bool(resp and resp.get("success"))

        msg = resp.get("message") if resp else "请求无响应或超时"
        if not success:
            log_func(f"数据提交失败: {msg}")
            logging.error(f"[{user.name}] 数据提交失败详情: {resp}")
        else:
            log_func(f"数据提交成功。")
            logging.debug(f"[{user.name}] 数据提交成功: {msg}")

        return success

    # ===================== 提交队列：串行化所有数据包提交 =====================
    @staticmethod
    def _submission_worker_static(submission_queue, stop_event):
        """后台工作线程：从队列取出提交任务并串行执行。(静态方法，防止绑定实例)"""
        logging.debug("[SubmissionWorker] 提交队列工作线程已启动")  # [修正] 改为DEBUG级别，防止启动时刷屏
        
        while not stop_event.is_set():
            try:
                # 1. 获取任务
                try:
                    task = submission_queue.get(timeout=1.0)
                except queue.Empty: # 使用 queue.Empty 捕获超时
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
                        task["response"] = {"success": False, "message": "Invalid task data"}

                except Exception as e:
                    logging.error(f"[SubmissionWorker] 任务执行内部错误: {e}", exc_info=True)
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
                logging.critical(f"[SubmissionWorker] 线程主循环发生未捕获异常: {outer_e}", exc_info=True)
                time.sleep(5) # 出错后冷却，防止死循环刷日志

    def _enqueue_submission(
        self, client: ApiClient, payload_str: str, wait_timeout: float = 30.0
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
            logging.debug(f"Enqueue submit task. Queue size before push: {qsize}")
        except Exception:
            pass
        self._submission_queue.put(task)
        signaled = task["event"].wait(timeout=wait_timeout)
        if not signaled:
            logging.warning("提交队列等待超时。")
            return None
        return task.get("response")

    def _finalize_run(self, run_data: RunData, task_index: int, client: ApiClient):
        """在所有数据提交后，查询服务器确认任务是否已标记为完成"""
        log_func = (
            client.app.log if hasattr(client.app, "log") else client.app.api_bridge.log
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
                    session_id = getattr(self, "_web_session_id", None)
                    if socketio and session_id and task_index != -1:
                        try:
                            socketio.emit(
                                "task_completed",
                                {"task_index": task_index},
                                room=session_id,
                            )
                        except Exception as e:
                            logging.error(f"SocketIO发送'task_completed'事件失败: {e}")
                    return
            time.sleep(1)
        log_func("暂未确认完成，请稍后刷新。")
        logging.warning(f"任务完成状态确认失败: 任务名称={run_data.run_name}")

    def _run_submission_thread(
        self,
        run_data: RunData,
        task_index: int,
        client: ApiClient,
        is_all: bool,
        finished_event: threading.Event | None = None,
    ):
        """模拟跑步和提交数据的主线程函数"""
        log_func = (
            client.app.log if hasattr(client.app, "log") else client.app.api_bridge.log
        )
        user_data = (
            client.app.user_data if hasattr(client.app, "user_data") else self.user_data
        )
        stop_flag = (
            client.app.stop_event
            if hasattr(client.app, "stop_event")
            else self.stop_run_flag
        )

        sio = globals().get("socketio") if "socketio" not in globals() else socketio

        session_id = getattr(self, "_web_session_id", None)
        last_auto_save_time = time.time()

        try:
            log_func("开始执行任务。")
            logging.info(f"任务提交线程已启动: 任务名称={run_data.run_name}")

            run_data.trid = f"{user_data.student_id}{int(time.time() * 1000)}"
            start_time_ms = str(int(time.time() * 1000))
            run_data.distance_covered_m = 0.0
            last_point_gps = run_data.run_coords[0]
            submission_successful = True

            point_index = 0

            for i in range(0, len(run_data.run_coords), 40):
                if stop_flag.is_set():
                    log_func("任务已中止。")
                    logging.info("检测到停止标志，正在中止任务运行")
                    break

                chunk = run_data.run_coords[i : i + 40]

                for lon, lat, dur_ms in chunk:
                    if stop_flag.wait(timeout=dur_ms / 1000.0):
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
                                "web_sessions_lock" in globals()
                                and "web_sessions" in globals()
                            ):
                                with web_sessions_lock:
                                    if current_session_id in web_sessions:
                                        save_session_state(
                                            current_session_id,
                                            web_sessions[current_session_id],
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

                is_final_chunk = i + 40 >= len(run_data.run_coords)

                max_attempts = 3
                attempt = 1
                chunk_submitted = False
                while attempt <= max_attempts:
                    if self._submit_chunk(
                        run_data,
                        chunk,
                        start_time_ms,
                        is_final_chunk,
                        i,
                        client,
                        user_data,
                    ):
                        chunk_submitted = True
                        break

                    submission_successful = False
                    if self.is_offline_mode:
                        logging.error(
                            f"[离线测试模式] 模拟提交失败，尝试 {attempt}/{max_attempts}"
                        )
                    else:
                        logging.warning(f"数据提交失败，重试 {attempt}/{max_attempts}")
                        if stop_flag.wait(timeout=1.0):
                            submission_successful = False
                            log_func("检测到停止信号，已取消重试")
                            break
                    attempt += 1

                if not chunk_submitted:
                    logging.error(
                        f"数据提交在 {max_attempts} 次尝试后仍然失败，任务中止"
                    )
                    break

            if not stop_flag.is_set() and submission_successful:
                log_func("任务执行完毕，等待确认...")
                logging.info("任务运行执行完毕，等待最终确认")
                time.sleep(3)
                self._finalize_run(run_data, task_index, client)

                if session_id:
                    try:
                        if (
                            "web_sessions_lock" in globals()
                            and "web_sessions" in globals()
                        ):
                            with web_sessions_lock:
                                if session_id in web_sessions:
                                    save_session_state(
                                        session_id,
                                        web_sessions[session_id],
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
                        sio.emit("run_stopped", {}, room=session_id)
                    except Exception as e:
                        logging.error(f"SocketIO发送'run_stopped'运行停止事件失败: {e}")

            if finished_event:
                finished_event.set()
            logging.info(f"Submission thread finished for task: {run_data.run_name}")

    def _get_path_for_distance(self, path, cumulative_distances, target_dist):
        """如果路径总长不足，则通过来回走的方式凑足目标距离"""
        total_len = cumulative_distances[-1]
        final_path = list(path)
        if 0 < total_len < target_dist:
            rem = target_dist - total_len
            rev = path[::-1]
            acc = 0.0
            for i in range(len(rev) - 1):
                seg = self._calculate_distance_m(
                    rev[i][0], rev[i][1], rev[i + 1][0], rev[i + 1][1]
                )
                if acc + seg < rem:
                    final_path.append(rev[i + 1])
                    acc += seg
                else:
                    ratio = (rem - acc) / seg if seg > 0 else 0
                    s, e = rev[i], rev[i + 1]
                    final_path.append(
                        (s[0] + (e[0] - s[0]) * ratio, s[1] + (e[1] - s[1]) * ratio)
                    )
                    break
        return final_path

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

    def auto_generate_path_with_api(self, api_path_coords, min_t_m, max_t_m, min_d_m):
        """接收由前端JS API规划好的路径点，并生成模拟数据"""
        logging.info(
            f"API CALL: auto_generate_path_with_api with {len(api_path_coords)} points"
        )
        if self.current_run_idx == -1:
            return {"success": False, "message": "请先选择任务"}
        run = self.all_run_data[self.current_run_idx]

        self.log("收到JS API路径，正在生成模拟数据...")
        logging.info(
            f"Auto-generating path from {len(api_path_coords)} Amap API points."
        )
        if not api_path_coords or len(api_path_coords) < 2:
            return {"success": False, "message": "高德API未能返回有效路径"}

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

        target_time_s = random.uniform(min_t_m * 60, max_t_m * 60)
        target_dist_m = random.uniform(min_d_m, min_d_m * 1.15)

        cumulative = [0.0]
        for i in range(len(final_path_dedup) - 1):
            cumulative.append(
                cumulative[-1]
                + self._calculate_distance_m(
                    final_path_dedup[i][0],
                    final_path_dedup[i][1],
                    final_path_dedup[i + 1][0],
                    final_path_dedup[i + 1][1],
                )
            )

        final_geo_path = self._get_path_for_distance(
            final_path_dedup, cumulative, target_dist_m
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
                    self.params["interval_ms"] * 0.9, self.params["interval_ms"] * 1.1
                )
                / 1000.0,
                target_time_s - t_elapsed,
            )
            if interval <= 0.1:
                break

            d_covered = min(
                d_covered + random.uniform(avg_speed * 0.9, avg_speed * 1.1) * interval,
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

        run.run_coords = run_coords
        run.total_run_time_s = t_elapsed
        run.total_run_distance_m = d_covered

        self.log("自动生成完成。")
        logging.info(
            f"Auto-generated path: points={len(run.run_coords)}, dist={d_covered:.1f}, time={t_elapsed:.1f}"
        )
        return {
            "success": True,
            "run_coords": run.run_coords,
            "total_dist": d_covered,
            "total_time": t_elapsed,
        }

    def start_all_runs(self, ignore_completed, auto_generate):
        """开始执行所有符合条件的任务"""
        logging.info(
            f"API CALL: start_all_runs (ignore_completed={ignore_completed}, auto_generate={auto_generate})"
        )
        if not self.stop_run_flag.is_set():
            return {"success": False, "message": "已有任务在运行"}

        tasks_to_run = []
        for i, d in enumerate(self.all_run_data):
            if d.status == 1 and not ignore_completed:
                continue

            is_expired = False
            is_not_started = False
            now = datetime.datetime.now()
            ignore_time = self.params.get("ignore_task_time", True)

            try:
                if d.end_time:
                    end_dt = self._try_parse_dt(d.end_time)
                    if ignore_time:
                        is_expired = end_dt.date() < now.date()
                    else:
                        is_expired = end_dt < now
            except (ValueError, TypeError):
                is_expired = False

            try:
                if d.start_time:
                    start_dt = self._try_parse_dt(d.start_time)
                    if ignore_time:
                        is_not_started = now.date() < start_dt.date()
                    else:
                        is_not_started = now < start_dt
            except (ValueError, TypeError):
                is_not_started = False

            if is_expired or is_not_started:
                continue

            if auto_generate or d.run_coords:
                tasks_to_run.append(i)

        if not tasks_to_run:
            msg = "没有符合条件的可执行任务。"
            if not auto_generate:
                msg += " (提示: 勾选'全部自动生成'可以为没有路线的任务自动规划)"
            return {"success": False, "message": msg}

        queue = collections.deque(tasks_to_run)
        self.stop_run_flag.clear()
        logging.info(
            f"Starting 'run all' process. Queue={list(queue)}, auto-generate={auto_generate}"
        )
        threading.Thread(
            target=self._run_all_tasks_manager, args=(queue, auto_generate), daemon=True
        ).start()
        return {"success": True}

    def _run_all_tasks_manager(self, queue: collections.deque, auto_gen_enabled: bool):
        """管理“执行所有”任务队列的线程函数"""
        self.log("开始执行所有任务。")
        if self.window:
            self.window.evaluate_js("onAllRunsToggled(true)")
        is_first_task = True

        tasks_executed_count = 0

        while queue:
            if self.stop_run_flag.is_set():
                break

            idx = queue.popleft()
            run_data = self.all_run_data[idx]
            self.current_run_idx = idx

            if self.window:
                self.window.evaluate_js(f"selectTaskFromBackend({idx})")
            time.sleep(1.2)

            if not run_data.run_coords and auto_gen_enabled:
                self.log(f"正在为任务 '{run_data.run_name}' 自动生成路线...")
                logging.info(
                    f"Auto-generating path for task in 'run all' mode: {run_data.run_name}"
                )

                if not run_data.details_fetched:
                    details_resp = self.get_task_details(idx)
                    if not details_resp.get("success"):
                        self.log("获取详情失败，跳过。")
                        logging.warning(
                            f"Skipping task {run_data.run_name}: failed to get details."
                        )
                        continue
                    run_data = self.all_run_data[idx]

                if not run_data.target_points:
                    self.log(f"跳过: 任务 '{run_data.run_name}' 无打卡点")
                    logging.warning(
                        f"[Task Skipped] No checkpoints for task {run_data.run_name}, cannot auto-generate path."
                    )
                    continue

                try:
                    self.log("调用高德API进行路径规划...")
                    callback_key = f"single_{idx}_{int(time.time() * 1000)}"
                    path_result: dict = {}
                    completion_event = threading.Event()
                    self.path_gen_callbacks[callback_key] = (
                        path_result,
                        completion_event,
                    )

                    waypoints = run_data.target_points
                    if self.window:
                        self.window.evaluate_js(
                            f'triggerPathGenerationForPy("{callback_key}", {json.dumps(waypoints)})'
                        )

                    path_received = completion_event.wait(timeout=120)
                    if "path" not in path_result:
                        error_msg = path_result.get("error", "超时或未知错误")
                        self.log(f"路径规划失败或超时：{error_msg}，跳过此任务。")
                        logging.warning(
                            f"Path planning failed for task {run_data.run_name}: {error_msg}"
                        )
                        if callback_key in self.path_gen_callbacks:
                            self.path_gen_callbacks.pop(callback_key, None)
                        continue

                    api_path_coords = path_result["path"]
                    self.log(
                        f"路径规划成功，共 {len(api_path_coords)} 个点，正在生成模拟数据..."
                    )

                    p = self.params
                    gen_resp = self.auto_generate_path_with_api(
                        api_path_coords,
                        p.get("min_time_m", 20),
                        p.get("max_time_m", 30),
                        p.get("min_dist_m", 2000),
                    )
                    if not gen_resp.get("success"):
                        self.log(
                            f"自动生成失败：{gen_resp.get('message', '未知错误')}，跳过。"
                        )
                        logging.warning(
                            f"Auto-generation failed for task {run_data.run_name}: {gen_resp}"
                        )
                        continue

                    run_data.run_coords = gen_resp["run_coords"]
                    run_data.total_run_distance_m = gen_resp["total_dist"]
                    run_data.total_run_time_s = gen_resp["total_time"]

                except Exception as e:
                    self.log(f"自动生成失败，跳过：{e}")
                    logging.error(
                        f"Auto-generation failed for {run_data.run_name}: {e}",
                        exc_info=True,
                    )
                    continue

                self.log("路径已生成，正在更新界面...")
                if self.window:
                    self.window.evaluate_js(f"forceRefreshTaskUI({idx})")
                time.sleep(1.0)

            if not run_data.run_coords:
                self.log(f"任务 '{run_data.run_name}' 无可用路线，跳过。")
                logging.warning(
                    f"Skipping task {run_data.run_name}: no route available."
                )
                continue

            if not is_first_task:
                wait_time = random.uniform(
                    self.params["task_gap_min_s"], self.params["task_gap_max_s"]
                )
                self.log(f"任务间等待中...")
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
            self.log("所有任务均被跳过，未执行任何操作。")
        else:
            self.log("所有任务执行结束。")

        self.stop_run_flag.set()
        if self.window:
            self.window.evaluate_js("onAllRunsToggled(false)")

    def get_task_history(self, index):
        """获取任务的历史跑步记录"""
        logging.info(
            f"API调用: get_task_history - 获取任务历史跑步记录，任务索引: {index}"
        )
        if not (0 <= index < len(self.all_run_data)):
            return {"success": False, "message": "任务索引无效"}
        run_data = self.all_run_data[index]
        self.log("正在获取历史记录...")
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
            self.log(f"历史记录已加载。")
            logging.debug(f"已成功加载 {len(records)} 条历史记录")
            return {"success": True, "history": history_list}
        return {"success": False, "message": "获取历史记录失败"}

    def get_historical_track(self, trid):
        """根据轨迹ID获取历史轨迹坐标点"""
        logging.info(
            f"API调用: get_historical_track - 根据轨迹ID获取历史轨迹，trid: {trid}"
        )
        self.log("正在加载历史轨迹...")
        logging.debug(f"正在加载历史运动轨迹数据，轨迹ID: trid={trid}")
        resp = self.api_client.get_history_track_by_trid(trid)
        if resp and resp.get("success"):
            coords = []
            for track_point_list in resp.get("data", {}).get("trackPointList", []):
                try:
                    coords_list = json.loads(track_point_list.get("coordinate", "[]"))
                    for item in coords_list:
                        lon, lat = map(float, item.get("location", "0,0").split(","))
                        coords.append((lon, lat))
                except (json.JSONDecodeError, ValueError):
                    continue
            self.log("历史轨迹加载成功。")
            logging.debug(f"历史轨迹数据加载成功，包含 {len(coords)} 个坐标点")
            return {"success": True, "coords": coords}
        self.log("加载历史轨迹失败。")
        logging.warning("加载历史运动轨迹数据失败")
        return {"success": False, "message": "加载历史轨迹失败"}

    def update_param(self, key, value):
        """更新并保存单个参数"""
        logging.info(f"API调用: update_param - 更新参数，键: {key}, 值: {value}")

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

                # [修正] 如果是全局配置项，立即保存到 config.ini
                # auto_attendance_enabled 已移除，它将仅保存在会话中
                global_keys = [
                    "theme_base_color",
                    "theme_style",
                    "auto_attendance_refresh_s",
                    "attendance_user_radius_m",
                ]
                if key in global_keys:
                    try:
                        main_cfg = configparser.RawConfigParser()
                        main_cfg.optionxform = str
                        if os.path.exists(self.config_path):
                            main_cfg.read(self.config_path, encoding="utf-8")

                        if not main_cfg.has_section("Config"):
                            main_cfg.add_section("Config")

                        main_cfg.set("Config", key, str(target_params[key]))

                        _write_config_with_comments(main_cfg, self.config_path)
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
                    cfg = configparser.ConfigParser()
                    cfg.read(self.config_path, encoding="utf-8")
                    username_to_update = cfg.get("Config", "LastUser", fallback=None)

                if username_to_update and not self.is_multi_account_mode:
                    self._save_config(username_to_update)

                logging.debug(f"参数已更新: 参数名={key}, 新值={target_params[key]}")

                if (
                    key in ("auto_attendance_enabled", "auto_attendance_refresh_s")
                    and not self.is_multi_account_mode
                ):
                    self.stop_auto_refresh.set()
                    if self.auto_refresh_thread and self.auto_refresh_thread.is_alive():
                        self.auto_refresh_thread.join(timeout=1.0)

                    if self.params.get("auto_attendance_enabled", False):
                        self.stop_auto_refresh.clear()
                        self.auto_refresh_thread = threading.Thread(
                            target=self._auto_refresh_worker, daemon=True
                        )
                        self.auto_refresh_thread.start()
                        self.log("自动刷新设置已更新并重启。")

                return {"success": True}
            except (ValueError, TypeError) as e:
                return {"success": False, "message": str(e)}
        return {"success": False, "message": "Unknown parameter"}

    def get_params(self):
        """
        获取当前参数配置
        """
        try:
            if self.is_multi_account_mode:
                return self.global_params.copy()
            else:
                return self.params.copy()
        except Exception as e:
            logging.error(f"获取参数失败: {e}", exc_info=True)
            return {
                "theme_base_color": "#7dd3fc",
                "theme_style": "default",
                "auto_attendance_enabled": False,
                "auto_attendance_refresh_s": 30,
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

            prev_user = copy.deepcopy(getattr(self, "user_data", UserData()))

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

            self.user_data = prev_user if prev_user else UserData()
            if not (self.user_data.name or "").strip():
                self.user_data.name = "离线调试"
            if not (self.user_data.student_id or "").strip():
                self.user_data.student_id = "NULL"

            logging.info(
                f"用户信息: {self.user_data.name} ({self.user_data.student_id})"
            )

            self.device_ua = None

            debug_run = RunData()
            debug_run.run_name = data.get("task_name", "调试任务 (离线)")
            debug_run.errand_id = data.get("errand_id", "debug_id")
            debug_run.errand_schedule = data.get("errand_schedule", "debug_schedule")
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

            self.log("离线数据已导入。")
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
            self.log("导入失败。")
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
        if background_task_manager:
            with background_task_manager.lock:
                # 遍历所有任务，检查是否有状态为 "running" 的任务
                for session_id, task in background_task_manager.tasks.items():
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
            if self.window:
                try:
                    self.window.evaluate_js("onRunStopped()")
                except Exception:
                    pass
        except Exception:
            logging.debug(
                "enter_multi_account_mode pre-stop single failed (non-fatal)."
            )

        self.log("进入多账号模式。")
        self.is_multi_account_mode = True
        self._update_multi_global_buttons()

        session_id = getattr(self, "_web_session_id", None)
        if session_id and socketio:
            try:
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
                socketio.emit(
                    "accounts_updated", {"accounts": accounts_data}, room=session_id
                )
            except Exception as e:
                logging.error(f"Failed to emit accounts_updated on mode entry: {e}")

        try:
            self.stop_multi_auto_refresh.clear()
            if (
                self.multi_auto_refresh_thread is None
                or not self.multi_auto_refresh_thread.is_alive()
            ):
                self.multi_auto_refresh_thread = threading.Thread(
                    target=self._multi_auto_attendance_worker, daemon=True
                )
                self.multi_auto_refresh_thread.start()
        except Exception as e:
            self.log(f"启动多账号自动刷新线程失败: {e}")

        if session_id:
            try:
                save_session_state(session_id, self, force_save=True)
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

        self._init_state_variables()
        self._load_global_config()
        self.log("已退出多账号模式。")

        session_id = getattr(self, "_web_session_id", None)
        if session_id:
            try:
                save_session_state(session_id, self, force_save=True)
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
            logging.debug("enter_single_account_mode: stop multi failed (non-fatal).")

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
        self.log("进入单账号模式。")
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
            "school_account_logged_in": getattr(self, "login_success", False),
            "is_offline_mode": getattr(self, "is_offline_mode", False),
        }

        if getattr(self, "is_multi_account_mode", False):
            mode_info["multi_account_count"] = len(getattr(self, "accounts", {}))
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
            mode_info["selected_task_index"] = getattr(self, "current_run_idx", -1)

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
        all_users = sorted(
            [
                os.path.splitext(f)[0]
                for f in os.listdir(self.user_dir)
                if f.endswith(".ini")
            ]
        )

        filtered_users = []

        if hasattr(self, "auth_username") and self.auth_username:
            school_accounts = self._load_user_school_accounts(self.auth_username)

            for username in all_users:
                if username in school_accounts:
                    filtered_users.append(username)

            logging.debug(
                f"用户 {self.auth_username} 可访问的配置用户: {len(filtered_users)}/{len(all_users)}"
            )
        else:
            logging.warning("multi_get_all_config_users: 没有认证用户信息，返回空列表")

        return {"users": filtered_users}

    def multi_load_accounts_from_config(self):
        """模式一：从所有.ini配置文件加载账号"""
        self.log("正在从配置文件加载账号列表...")
        users = sorted(
            [
                os.path.splitext(f)[0]
                for f in os.listdir(self.user_dir)
                if f.endswith(".ini")
            ]
        )
        loaded_count = 0
        accounts_missing_password = []
        for username in users:
            if username not in self.accounts:
                add_result = self.multi_add_account(username, "")
                if add_result and add_result.get("action") == "request_password":
                    accounts_missing_password.append(
                        {
                            "username": add_result.get("username"),
                            "tag": add_result.get("tag"),
                        }
                    )
                elif add_result and add_result.get("success"):
                    loaded_count += 1
        self.log(f"已加载 {loaded_count} 个账号。")
        if accounts_missing_password:
            self.log(
                f"发现 {len(accounts_missing_password)} 个账号缺少密码，等待用户手动添加。"
            )
        self._update_multi_global_buttons()
        final_status = self.multi_get_all_accounts_status()
        final_status["accounts_missing_password"] = accounts_missing_password
        return final_status

    def multi_add_account(self, username, password, tag=None, params=None):
        """模式二：手动或选择性添加账号"""
        if username in self.accounts:
            acc = self.accounts[username]

            if params and isinstance(params, dict):
                for k, v in params.items():
                    if k in acc.params:
                        acc.params[k] = v

            if password and acc.password != password:
                acc.password = password
                self._save_config(username, password)
                self.log(f"已更新账号 [{username}] 的密码。")
            else:
                self.log(f"账号 [{username}] 已存在，正在从配置文件刷新...")
                reloaded_password = self._load_config(username)
                if reloaded_password:
                    acc.password = reloaded_password

            if tag is not None:
                acc.tag = str(tag)
                self._save_account_tag(username, acc.tag)
                self.log(f"已更新账号 [{username}] 的标记：{acc.tag}。")

            try:
                self._update_account_status_js(acc, status_text="刷新中...")
                try:
                    acc.api_client.session.cookies.clear()
                except Exception:
                    pass
                acc.user_data.id = ""
                threading.Thread(
                    target=self._multi_refresh_worker, args=(acc,), daemon=True
                ).start()
            except Exception:
                logging.error(f"更新账号后触发刷新失败: {traceback.format_exc()}")
            self._update_multi_global_buttons()
            return self.multi_get_all_accounts_status([{"success": True}])

        loaded_tag = self._load_account_tag(username)
        final_tag = tag if tag is not None else (loaded_tag if loaded_tag else "")
        self.accounts[username] = AccountSession(
            username, password, self, tag=final_tag
        )

        loaded_password = self._load_config(username)

        if not self.accounts[username].device_ua:
            self.accounts[username].device_ua = ApiClient.generate_random_ua()

        final_password = password or (loaded_password or "")
        self.accounts[username].password = final_password

        if not final_password:
            try:
                del self.accounts[username]
            except Exception:
                pass
            self.log(f"账号 {username} 缺少密码，已弹出输入框以完善密码。")
            return {
                "success": False,
                "message": "缺少密码",
                "action": "request_password",
                "username": username,
                "tag": final_tag,
            }

        ini_path = os.path.join(self.user_dir, f"{username}.ini")
        needs_verification = False

        if password and loaded_password and password != loaded_password:
            needs_verification = True
            self.log(f"账号 {username} 密码与配置文件不一致，需要首次登录验证。")
        elif password and not loaded_password:
            needs_verification = True
            self.log(f"账号 {username} 是新添加的账号，需要首次登录验证。")

        if needs_verification:
            self.accounts[username].is_first_login_verified = False
            self.accounts[username].is_verifying = True
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
                self._save_config(
                    username,
                    self.accounts[username].password,
                    self.accounts[username].device_ua,
                )
            except Exception:
                logging.warning(f"保存配置失败（将继续运行）：{traceback.format_exc()}")

        self.log(f"已添加账号: {username}")
        self._update_multi_global_buttons()

        session_id = getattr(self, "_web_session_id", None)
        if session_id and socketio:
            try:
                current_accounts = self.multi_get_all_accounts_status().get(
                    "accounts", []
                )
                socketio.emit(
                    "accounts_updated", {"accounts": current_accounts}, room=session_id
                )
            except Exception as e:
                logging.error(f"SocketIO emit 'accounts_updated' failed: {e}")

        try:
            threading.Thread(
                target=self._multi_refresh_worker,
                args=(self.accounts[username],),
                daemon=True,
            ).start()
        except Exception:
            logging.error(f"启动刷新线程失败: {traceback.format_exc()}")

        if hasattr(self, "_web_session_id") and self._web_session_id:
            save_session_state(self._web_session_id, self, force_save=True)

        return self.multi_get_all_accounts_status([{"success": True}])

    def multi_remove_account(self, username):
        """移除一个账号"""
        if username in self.accounts:
            if (
                self.accounts[username].worker_thread
                and self.accounts[username].worker_thread.is_alive()
            ):
                self.accounts[username].stop_event.set()
            del self.accounts[username]
            self.log(f"已移除账号: {username}")
        self._update_multi_global_buttons()
        if hasattr(self, "_web_session_id") and self._web_session_id:
            save_session_state(self._web_session_id, self, force_save=True)
        return self.multi_get_all_accounts_status()

    def multi_refresh_all_statuses(self):
        """(多线程)刷新所有账号的任务状态和统计信息"""
        session_uuid = session.get("uuid", "unknown")
        logging.info(
            f"[多账号自动刷新] 收到刷新请求，会话UUID: {session_uuid}, 当前账号数量: {len(self.accounts) if self.accounts else 0}"
        )

        if not self.accounts:
            self.log("账号列表为空，无需刷新。")
            return {"success": True}

        self.log("正在刷新所有账号状态...")
        for acc in self.accounts.values():
            is_running = bool(acc.worker_thread and acc.worker_thread.is_alive())
            if not is_running:
                self._update_account_status_js(acc, status_text="刷新中...")
            threading.Thread(
                target=self._multi_refresh_worker,
                args=(acc, True if is_running else False),
                daemon=True,
            ).start()

        self._update_multi_global_buttons()
        return {"success": True}

    def multi_refresh_single_status(self, username: str):
        """刷新指定账号的状态与摘要（单账号）"""
        if username not in self.accounts:
            return {"success": False, "message": "账号不存在"}
        acc = self.accounts[username]

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

    def _multi_refresh_worker(self, acc: AccountSession, preserve_status: bool = False):
        """用于刷新的单个账号工作线程
        - preserve_status=True 时：若账号正在运行，不改写 status_text，只更新 name 与 summary
        """
        try:
            acc.last_refresh_time = time.time()

            preserve_now = preserve_status and bool(
                acc.worker_thread and acc.worker_thread.is_alive()
            )

            if not acc.user_data.id:
                if not acc.device_ua:
                    acc.device_ua = ApiClient.generate_random_ua()

                if not acc.is_first_login_verified:
                    acc.is_verifying = True
                    if not preserve_now:
                        self._update_account_status_js(acc, status_text="首次验证中...")

                login_resp = self._queued_login(
                    acc, respect_global_stop=False, ignore_all_stops=True
                )
                if not login_resp or not login_resp.get("success"):
                    # 获取实际的错误信息，而不是假设密码错误
                    fail_msg = login_resp.get("message", "未知错误") if login_resp else "网络请求无响应"
                    
                    if not acc.is_first_login_verified:
                        acc.is_verifying = False
                        acc.is_first_login_verified = False
                        if not preserve_now:
                            # 显示具体的错误信息
                            self._update_account_status_js(
                                acc, status_text=f"验证失败: {fail_msg}"
                            )
                        acc.log(f"首次登录验证失败: {fail_msg}")
                    else:
                        if not preserve_now:
                            # 已验证过的账号刷新失败，也显示具体原因
                            self._update_account_status_js(
                                acc, status_text=f"刷新失败: {fail_msg}"
                            )
                    return

                data = login_resp.get("data", {})
                user_info = data.get("userInfo", {})
                acc.user_data.name = user_info.get("name", "")
                acc.user_data.id = user_info.get("id", "")
                acc.user_data.student_id = user_info.get("account", "")

                if not acc.is_first_login_verified:
                    acc.is_first_login_verified = True
                    acc.is_verifying = False
                    try:
                        self._save_config(acc.username, acc.password, acc.device_ua)
                        acc.log(f"首次登录验证成功，密码已保存到配置文件。")
                    except Exception as e:
                        logging.error(f"保存密码到配置文件失败: {e}", exc_info=True)
                else:
                    ini_path = os.path.join(self.user_dir, f"{acc.username}.ini")
                    if os.path.exists(ini_path):
                        self._save_config(acc.username)

                self._update_account_status_js(
                    acc, name=acc.user_data.name, status_text="获取数据..."
                )

            self._multi_fetch_and_summarize_tasks(acc)

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

            acc.log("状态刷新完成。")

            if (
                not preserve_now
                and hasattr(self, "_web_session_id")
                and self._web_session_id
            ):

                def delayed_save():
                    time.sleep(2)
                    try:
                        save_session_state(self._web_session_id, self, force_save=True)
                        logging.debug(f"账号 {acc.username} 刷新完成后已保存会话状态")
                    except Exception as e:
                        logging.error(f"延迟保存会话状态失败: {e}")

                threading.Thread(target=delayed_save, daemon=True).start()

        except Exception as e:
            logging.error(f"Error refreshing {acc.username}: {traceback.format_exc()}")
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

        self.log(f"移除了 {removed_count} 个选定账号。")
        self._update_multi_global_buttons()
        if hasattr(self, "_web_session_id") and self._web_session_id:
            save_session_state(self._web_session_id, self, force_save=True)

        return self.multi_get_all_accounts_status()

    def multi_remove_all_accounts(self):
        """一键移除所有账号"""
        if not self.accounts:
            return self.multi_get_all_accounts_status()

        self.multi_stop_all_accounts()

        count = len(self.accounts)
        self.accounts.clear()
        self.log(f"已移除全部 {count} 个账号。")
        self._update_multi_global_buttons()
        if hasattr(self, "_web_session_id") and self._web_session_id:
            save_session_state(self._web_session_id, self, force_save=True)
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

            is_running = bool(acc.worker_thread and acc.worker_thread.is_alive())
            current_pos = getattr(acc, "current_position", None) if is_running else None

            status_list.append(
                {
                    "username": acc.username,
                    "name": acc.user_data.name or "---",
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

    def multi_download_import_template(self):
        """下载导入模板（账号、密码、标记），支持 Web模式直接返回文件内容"""
        try:
            headers = ["账号", "密码", "标记"]

            wb = openpyxl.Workbook()
            sh = wb.active
            sh.title = "模板"
            sh.append(headers)

            output = io.BytesIO()
            wb.save(output)
            output.seek(0)

            file_content = base64.b64encode(output.read()).decode("utf-8")
            filename = f"账号导入模板_{datetime.datetime.now().strftime('%Y%m%d')}.xlsx"

            self.log(f"模板已生成：{filename}")
            return {
                "success": True,
                "filename": filename,
                "content": file_content,
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        except Exception as e:
            self.log(f"模板生成失败：{e}")
            logging.error(f"Template generation failed: {traceback.format_exc()}")
            return {"success": False, "message": f"生成失败: {e}"}

    def multi_import_accounts(self, filename, base64_content):
        """从文件导入账号密码，支持 .xlsx/.xls/.csv（仅Web模式，从内存流处理）

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

        try:
            imported = 0
            seen_usernames: set[str] = set()

            if ext == ".xlsx":
                try:
                    wb = openpyxl.load_workbook(
                        file_stream, data_only=True, read_only=True, keep_links=False
                    )
                except TypeError as e:
                    warnings.warn(f"样式解析失败，已忽略样式: {e}")
                    file_stream.seek(0)
                    wb = openpyxl.load_workbook(
                        file_stream,
                        data_only=True,
                        read_only=True,
                        keep_links=False,
                        keep_vba=False,
                    )

                sh = wb.active
                skipped_no_password = []
                for row in sh.iter_rows(min_row=2, values_only=True):
                    if not row or len(row) < 1:
                        continue
                    username = str(row[0] or "").strip()
                    password = str(row[1] or "").strip() if len(row) > 1 else ""
                    tag = None
                    if len(row) > 2 and row[2]:
                        tag = str(row[2]).strip()

                    if not username:
                        continue
                    if username in seen_usernames:
                        continue
                    seen_usernames.add(username)

                    loaded_password = self._load_config(username)
                    final_password = password or (loaded_password or "")

                    if not final_password:
                        skipped_no_password.append(username)
                        continue

                    self.multi_add_account(username, final_password, tag=tag)
                    imported += 1

            elif ext == ".xls":
                file_stream.seek(0)
                book = xlrd.open_workbook(file_contents=file_stream.read())
                sh = book.sheet_by_index(0)
                skipped_no_password = []
                for r in range(1, sh.nrows):
                    username = str(sh.cell_value(r, 0) or "").strip()
                    password = ""
                    if sh.ncols >= 2:
                        password = str(sh.cell_value(r, 1) or "").strip()
                    tag = None
                    if sh.ncols >= 3:
                        tag_val = sh.cell_value(r, 2)
                        if tag_val:
                            tag = str(tag_val).strip()

                    if username:
                        if username in seen_usernames:
                            continue
                        seen_usernames.add(username)

                        loaded_password = self._load_config(username)
                        final_password = password or (loaded_password or "")
                        if not final_password:
                            skipped_no_password.append(username)
                            continue

                        self.multi_add_account(username, final_password, tag=tag)
                        imported += 1

            elif ext == ".csv":
                skipped_no_password = []
                file_stream.seek(0)
                text_stream = io.TextIOWrapper(
                    file_stream, encoding="utf-8-sig", newline=""
                )
                reader = csv.reader(text_stream)

                first_row = True
                for row in reader:
                    if not row or len(row) < 1:
                        continue
                    if first_row and str(row[0]).strip() in (
                        "账号",
                        "用户名",
                        "username",
                        "user",
                    ):
                        first_row = False
                        continue
                    first_row = False
                    username = (row[0] or "").strip()
                    password = (row[1] or "").strip() if len(row) > 1 else ""
                    tag = None
                    if len(row) > 2 and row[2]:
                        tag = row[2].strip()

                    if username:
                        if username in seen_usernames:
                            continue
                        seen_usernames.add(username)

                        loaded_password = self._load_config(username)
                        final_password = password or (loaded_password or "")
                        if not final_password:
                            skipped_no_password.append(username)
                            continue

                        self.multi_add_account(username, final_password, tag=tag)
                        imported += 1

            else:
                return {"success": False, "message": f"不支持的导入格式: {ext}"}

            self.log(f"成功导入 {imported} 个账号。")
            if skipped_no_password:
                msg = "以下账号缺少密码，已跳过导入。请在多账号控制台手动添加并输入密码：\n" + "\n".join(
                    skipped_no_password[:20]
                )
                try:
                    if self.window:
                        self.window.evaluate_js(f"alert({json.dumps(msg)})")
                except Exception:
                    logging.debug("Alert skipped_no_password failed (non-fatal).")
                self.log(
                    f"缺少密码的账号（共 {len(skipped_no_password)}）：{', '.join(skipped_no_password)}"
                )

            return self.multi_get_all_accounts_status()

        except Exception as e:
            self.log(f"导入失败: {e}")
            logging.error(f"导入多账号配置失败，详细错误信息: {traceback.format_exc()}")
            return {"success": False, "message": f"导入失败: {e}"}

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

            wb = openpyxl.Workbook()
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

            self.log(f"汇总信息已导出到 {filename}")
            return {
                "success": True,
                "filename": filename,
                "content": file_content,
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        except Exception as e:
            self.log(f"导出失败: {e}")
            logging.error(f"Export accounts summary failed: {traceback.format_exc()}")
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

                self._save_config(username, self.accounts[username].password)
                self.log(f"已更新账号 [{username}] 的参数 {key}。")

                if hasattr(self, "_web_session_id") and self._web_session_id:
                    save_session_state(self._web_session_id, self, force_save=True)

                return {"success": True}
            except (ValueError, TypeError) as e:
                return {"success": False, "message": str(e)}
        return {"success": False, "message": "Unknown parameter"}

    def multi_start_single_account(self, username, run_only_incomplete: bool = True):
        """
        启动指定账号的任务执行线程。
        """
        if username not in self.accounts:
            return {"success": False, "message": "账号不存在"}
        acc = self.accounts[username]
        if acc.worker_thread and acc.worker_thread.is_alive():
            self.log(f"账号 {username} 已在运行中。")
            return {"success": False, "message": "该账号已在运行"}

        acc.stop_event.clear()
        if self.multi_run_stop_flag.is_set():
            self.multi_run_stop_flag.clear()
        acc.worker_thread = threading.Thread(
            target=self._multi_account_worker,
            args=(acc, 0, bool(run_only_incomplete)),
            daemon=True,
        )
        acc.worker_thread.start()
        self.log(f"已启动账号: {username}")
        self._update_account_status_js(acc, status_text="排队等待...")
        self._update_multi_global_buttons()
        return {"success": True}

    def multi_stop_single_account(self, username):
        """
        停止指定账号的任务执行线程。
        """
        acc = self.accounts.get(username)
        if not acc:
            return {"success": False, "message": f"账号 {username} 不存在"}

        if acc.worker_thread and acc.worker_thread.is_alive():
            acc.stop_event.set()
            self.log(f"已向账号 {username} 发送停止信号。")
            self._update_account_status_js(acc, status_text="正在停止...")
            self._update_multi_global_buttons()

            def _watch_stop():
                try:
                    while acc.worker_thread and acc.worker_thread.is_alive():
                        time.sleep(0.2)
                    acc.worker_thread = None
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
        self, min_delay, max_delay, use_delay, run_only_incomplete
    ):
        """一键启动所有账号的任务"""
        if not self.accounts:
            self.log("账号列表为空，无法开始。请先添加账号。")
            return {
                "success": False,
                "message": "账号列表为空，无法开始。请先添加账号。",
            }

        total_accounts = len(self.accounts)
        running_count = sum(
            1
            for acc in self.accounts.values()
            if acc.worker_thread and acc.worker_thread.is_alive()
        )
        if total_accounts > 0 and running_count == total_accounts:
            return {"success": False, "message": "任务已在运行中"}

        self.log("开始执行所有账号...")
        self._update_multi_global_buttons()
        if self.multi_run_stop_flag.is_set():
            self.multi_run_stop_flag.clear()

        account_list = list(self.accounts.values())
        num_accounts = len(account_list)
        delays = [0] * num_accounts

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

        started_threads = 0
        for i, acc in enumerate(account_list):
            if acc.worker_thread and acc.worker_thread.is_alive():
                acc.log("已在运行，本次'全部开始'将跳过此账号。")
                continue

            delay = delays[i] if use_delay else 0
            acc.stop_event.clear()
            acc.worker_thread = threading.Thread(
                target=self._multi_account_worker,
                args=(acc, delay, run_only_incomplete),
                daemon=True,
            )
            acc.worker_thread.start()
            started_threads += 1

        if started_threads == 0:

            self.log("当前没有可启动的账号任务。")
            return {"success": False, "message": "当前没有可启动的账号任务。"}

        self._update_multi_global_buttons()
        return {"success": True}

    def multi_stop_all_accounts(self):
        """停止所有账号的运行"""
        logging.info("API调用: multi_stop_all_accounts - 停止所有多账号任务的运行")
        if not self.accounts:
            self.log("当前无账号，无需停止。")
            self.multi_run_stop_flag.set()
            return {"success": False, "message": "当前无账号，无需停止。"}

        if self.multi_run_stop_flag.is_set():
            return {"success": True}

        self.log("正在发送停止信号...")
        self.multi_run_stop_flag.set()
        for acc in self.accounts.values():
            acc.stop_event.set()
        self._update_multi_global_buttons()
        self.log("所有任务将在当前步骤完成后停止。")
        self._update_multi_global_buttons()

        time.sleep(1)

        self._update_multi_global_buttons()
        return {"success": True}

    def _update_account_status_js(
        self,
        acc: AccountSession,
        status_text: str = None,
        summary: dict = None,
        name: str = None,
        progress_pct: int | None = None,
        progress_text: str | None = None,
        progress_extra: str | None = None,
    ):
        """一个辅助函数，用于向前端发送状态更新"""
        session_id = getattr(self, "_web_session_id", None)
        if not session_id or not socketio:
            logging.debug(
                f"跳过账号状态更新（_update_account_status_js），账号: {acc.username}，原因: 缺少会话ID或socketio未初始化"
            )
            return

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

        if update_data:
            try:
                socketio.emit(
                    "multi_status_update",
                    {"username": acc.username, "data": update_data},
                    room=session_id,
                )
                time.sleep(0.001)
            except Exception as e:
                logging.error(f"SocketIO emit 'multi_status_update' failed: {e}")

        self._update_multi_global_buttons()

    def _update_multi_global_buttons(self):
        """根据当前多账号状态刷新“全部开始/全部停止/返回登录页”按钮的可用性"""
        session_id = getattr(self, "_web_session_id", None)
        if not session_id or not socketio:
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
                (executable > 0) if self.multi_run_only_incomplete else (candidates > 0)
            )
            if has_tasks:
                active_accounts.append(acc)

        total_active = len(active_accounts)
        running_count = sum(
            1
            for acc in active_accounts
            if acc.worker_thread and acc.worker_thread.is_alive()
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
            socketio.emit(
                "multi_global_buttons_update",
                {
                    "start_disabled": start_disabled,
                    "stop_disabled": stop_disabled,
                    "exit_disabled": exit_disabled,
                },
                room=session_id,
            )
        except Exception as e:
            logging.error(f"SocketIO emit 'multi_global_buttons_update' failed: {e}")

    def _queued_login(
        self,
        acc: AccountSession,
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
                    from eventlet import patcher

                    native_threading = patcher.original("threading")
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

    def _multi_fetch_and_summarize_tasks(self, acc: AccountSession):
        """(辅助函数) 为单个账号获取任务列表并计算统计信息（按任务ID去重）"""
        acc.all_run_data = []
        seen_keys: set[str] = set()
        offset = 0
        dup_count = 0

        while True:
            if acc.stop_event.is_set():
                return
            resp = acc.api_client.get_run_list(acc.user_data.id, offset)
            if not resp or not resp.get("success"):
                acc.log("获取任务列表失败。")
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

                run = RunData()
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
                acc.all_run_data.append(run)

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

        total = len(acc.all_run_data)
        completed = 0
        expired = 0
        executable = 0
        not_started = 0

        now = datetime.datetime.now()
        ignore_time = acc.params.get("ignore_task_time", True)

        for r in acc.all_run_data:
            if r.status == 1:
                completed += 1
                if self.multi_run_only_incomplete:
                    continue

            start_dt, end_dt = None, None
            try:
                if r.start_time:
                    start_dt = datetime.datetime.strptime(
                        r.start_time, "%Y-%m-%d %H:%M:%S"
                    )
            except (ValueError, TypeError):
                start_dt = None
            try:
                if r.end_time:
                    end_dt = datetime.datetime.strptime(r.end_time, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                end_dt = None

            if end_dt:
                is_expired = end_dt.date() < now.date() if ignore_time else end_dt < now
                if is_expired:
                    expired += 1
                    continue

            if start_dt:
                is_not_started = (
                    now.date() < start_dt.date() if ignore_time else now < start_dt
                )
                if is_not_started:
                    not_started += 1
                    continue

            executable += 1

        acc.summary.update(
            {
                "total": total,
                "completed": completed,
                "pending": total - completed,
                "not_started": not_started,
                "executable": executable,
                "expired": expired,
            }
        )

        acc.has_pending_tasks = executable > 0

    def _multi_fetch_attendance_stats(self, acc: AccountSession):
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
                    acc.log(f"获取通知列表失败 (Offset: {offset})")
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

                        if status == -1:
                            att_expired += 1
                        elif status != -1 and (finished == 1 or finished is True):
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
            acc.log(f"刷新签到统计时出错: {e}")
            logging.error(
                f"[{acc.username}] Failed to fetch attendance stats: {e}", exc_info=True
            )

    def multi_path_generation_callback(self, username: str, success: bool, data: any):
        """接收来自JS的路径规划结果并唤醒对应线程"""
        if username in self.path_gen_callbacks:
            path_result, completion_event = self.path_gen_callbacks.pop(username)
            if success:
                path_result["path"] = data
            else:
                path_result["error"] = data
            completion_event.set()

    def _multi_account_worker(
        self, acc: AccountSession, delay: float, run_only_incomplete: bool
    ):
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
                acc.log(
                    f"距离上次刷新仅 {time_since_last_refresh:.1f} 秒，跳过重复刷新，直接使用已有数据。"
                )
            else:
                self._update_account_status_js(acc, status_text="登录中...")
                if not acc.device_ua:
                    acc.device_ua = ApiClient.generate_random_ua()

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
                    self._update_account_status_js(acc, status_text=f"登录失败: {msg}")
                    return

                data = login_resp.get("data", {})
                user_info = data.get("userInfo", {})
                acc.user_data.name = user_info.get("name", "")
                acc.user_data.id = user_info.get("id", "")
                acc.user_data.student_id = user_info.get("account", "")
                acc.log("登录成功。")
                self._update_account_status_js(
                    acc, status_text="分析任务", name=acc.user_data.name
                )

                if self.multi_run_stop_flag.is_set() or acc.stop_event.is_set():
                    self._update_account_status_js(acc, status_text="已中止")
                    return

                self._multi_fetch_and_summarize_tasks(acc)
                self._update_account_status_js(acc, summary=acc.summary)

                acc.last_refresh_time = time.time()

            tasks_to_run_candidates = []
            now = datetime.datetime.now()
            ignore_time = acc.params.get("ignore_task_time", True)
            acc.log(
                f"分析任务参数: ignore_task_time={ignore_time}, run_only_incomplete={run_only_incomplete}"
            )
            for r in acc.all_run_data:
                start_dt = None
                end_dt = None
                try:
                    if r.start_time:
                        start_dt = datetime.datetime.strptime(
                            r.start_time, "%Y-%m-%d %H:%M:%S"
                        )
                except (ValueError, TypeError):
                    start_dt = None
                try:
                    if r.end_time:
                        end_dt = datetime.datetime.strptime(
                            r.end_time, "%Y-%m-%d %H:%M:%S"
                        )
                except (ValueError, TypeError):
                    end_dt = None

                if end_dt:
                    is_expired = (
                        end_dt.date() < now.date() if ignore_time else end_dt < now
                    )
                    if is_expired:
                        continue

                if start_dt:
                    is_not_started = (
                        now.date() < start_dt.date() if ignore_time else now < start_dt
                    )
                    if is_not_started:
                        continue

                tasks_to_run_candidates.append(r)

            tasks_to_run = (
                [t for t in tasks_to_run_candidates if t.status == 0]
                if run_only_incomplete
                else tasks_to_run_candidates
            )

            acc.log(
                f"任务筛选结果: 候选任务={len(tasks_to_run_candidates)}, 待执行任务={len(tasks_to_run)}"
            )

            if not tasks_to_run:
                self._update_account_status_js(acc, status_text="无任务可执行")
                self._update_multi_global_buttons()
                return
            else:
                acc.has_pending_tasks = True

            tasks_executed_count = 0

            if delay > 0:
                end_time = time.time() + delay
                while time.time() < end_time:
                    if acc.stop_event.is_set() or self.multi_run_stop_flag.is_set():
                        self._update_account_status_js(acc, status_text="已中止")
                        self._update_multi_global_buttons()
                        return
                    remaining = end_time - time.time()
                    self._update_account_status_js(
                        acc, status_text=f"延迟 {remaining:.0f}s"
                    )
                    time.sleep(1)

            for i, run_data in enumerate(tasks_to_run):
                if self.multi_run_stop_flag.is_set() or acc.stop_event.is_set():
                    self._update_account_status_js(acc, status_text="已中止")
                    self._update_multi_global_buttons()
                    break

                task_name_short = (
                    run_data.run_name[:10] + "..."
                    if len(run_data.run_name) > 10
                    else run_data.run_name
                )

                self._update_account_status_js(
                    acc,
                    status_text=f"运行 {i+1}/{len(tasks_to_run)}: {task_name_short}",
                    progress_pct=0,
                    progress_text=f"运行 {i+1}/{len(tasks_to_run)}: {task_name_short} · 0%",
                    progress_extra="",
                )

                acc.log(f"开始执行任务: {run_data.run_name}")

                if self.multi_run_stop_flag.is_set() or acc.stop_event.is_set():
                    self._update_account_status_js(acc, status_text="已中止")
                    break

                details_resp = acc.api_client.get_run_details(
                    run_data.errand_id, acc.user_data.id, run_data.errand_schedule
                )
                if not (details_resp and details_resp.get("success")):
                    acc.log(f"获取任务详情失败，跳过。")
                    continue

                details = details_resp.get("data", {}).get("errandDetail", {})
                waypoints = [
                    (float(p["lon"]), float(p["lat"]))
                    for p in details.get("geoCoorList", [])
                    if p.get("lon") is not None
                ]
                if not waypoints:
                    task_name = details.get("title", run_data.run_name)
                    acc.log(f"跳过: 任务 '{task_name}' 无打卡点")
                    continue
                run_data.target_points = waypoints

                api_path_coords = None

                global chrome_pool
                if not chrome_pool:
                    acc.log("错误: Chrome浏览器池不可用，无法进行路径规划。")
                    continue

                try:
                    acc.log("正在调用高德地图API进行路径规划...")

                    session_id = getattr(self, "_web_session_id", None)
                    if not session_id:
                        acc.log(
                            "错误: 无法获取会话ID（_web_session_id 属性不存在），跳过任务。"
                        )
                        logging.error(
                            f"多账号模式缺少 _web_session_id 属性，账号: {acc.username}"
                        )
                        continue

                    if not hasattr(self, "_amap_key_cached"):
                        config = configparser.ConfigParser()
                        config.read(CONFIG_FILE, encoding="utf-8")
                        self._amap_key_cached = config.get(
                            "Map", "amap_js_key", fallback=""
                        )
                        logging.info(f"已加载高德地图API密钥配置（缓存至实例）")

                    amap_key = self._amap_key_cached
                    if not amap_key:
                        acc.log("错误: 未配置高德地图API密钥，请在config.ini中设置。")
                        continue

                    ctx = chrome_pool.get_context(session_id)
                    page = ctx["page"]

                    amap_loaded = False
                    try:
                        amap_loaded = page.evaluate("typeof AMapLoader !== 'undefined'")
                    except Exception as e:
                        logging.debug(f"检查AMap SDK时出错（可能尚未加载）: {e}")

                    if not amap_loaded:
                        page.goto("about:blank")
                        page.set_content(
                            """
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta charset="utf-8">
                            <script type="text/javascript" src="https://webapi.amap.com/loader.js"></script>
                        </head>
                        <body></body>
                        </html>
                        """
                        )

                        try:
                            page.wait_for_function(
                                "typeof AMapLoader !== 'undefined'", timeout=10000
                            )
                        except Exception as e:
                            acc.log(f"错误: 加载高德地图SDK超时或失败: {str(e)}")
                            continue

                    path_coords = chrome_pool.execute_js(
                        session_id,
                        """
                        (async (arg) => {
                            const waypointsPy = arg[0];
                            const apiKey = arg[1];
                            const pythonParams = arg[2];

                            async function planPath(waypointsPy, apiKey, pythonParams) {
                                if (typeof AMapLoader === 'undefined') {
                                    return {error: 'AMapLoader not loaded'};
                                }

                                try {
                                    await AMapLoader.load({
                                        "key": apiKey,
                                        "version": "2.0",
                                        "plugins": ["AMap.Walking"]
                                    });
                                } catch (e) {
                                    return {error: 'AMapLoader.load failed: ' + (e ? e.message : 'Unknown error')};
                                }

                                if (typeof AMap.Walking === 'undefined') {
                                    return {error: 'AMap.Walking plugin failed to load'};
                                }

                                const useFallback = pythonParams.api_fallback_line ?? false;
                                const maxRetries = pythonParams.api_retries ?? 2;
                                const retryDelayMs = (pythonParams.api_retry_delay_s ?? 0.5) * 1000;
                                const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

                                const searchSegment = (start, end, walkingInstance) => new Promise((resolve) => {
                                    walkingInstance.search(start, end, (status, result) => {
                                        if (status === 'complete' && result.routes?.length > 0) {
                                            const p = []; 
                                            result.routes[0].steps.forEach(s => s.path.forEach(pt => p.push({ lng: pt.lng, lat: pt.lat })));
                                            resolve({ path: p });
                                        } else {
                                            let errorInfo = 'Unknown Error';
                                            if (status === 'error') {
                                                errorInfo = result?.info || status;
                                            } else if (status === 'no_data') {
                                                errorInfo = 'No path found (no_data)';
                                            } else {
                                                errorInfo = status;
                                            }
                                            resolve({ error: 'Path planning failed: ' + errorInfo });
                                        }
                                    });
                                });

                                const all_path = [];
                                const waypoints = waypointsPy.map(p => new AMap.LngLat(p[0], p[1]));
                                const walking = new AMap.Walking({ map: null, panel: "", hideMarkers: true });

                                if (waypoints.length < 2) {
                                    return {error: 'Waypoints must be at least 2.'};
                                }

                                for (let i = 0; i < waypoints.length - 1; i++) {
                                    const realStart = waypoints[i];
                                    const realEnd = waypoints[i + 1];
                                    
                                    let attempts = 0;
                                    let segmentResult = null;
                                    let segmentPath = null;

                                    while (attempts <= maxRetries) {
                                        if (attempts > 0) {
                                            await sleep(retryDelayMs);
                                        }
                                        
                                        segmentResult = await searchSegment(realStart, realEnd, walking);
                                        
                                        if (segmentResult.path) {
                                            segmentPath = segmentResult.path;
                                            break;
                                        }
                                        
                                        attempts++;
                                    }

                                    if (segmentPath) {
                                        const areCoordsEqual = (c1, c2) => Math.abs(c1.lng - c2.lng) < 1e-6 && Math.abs(c1.lat - c2.lat) < 1e-6;
                                        if (i > 0) {
                                            all_path.push(...segmentPath.slice(1));
                                        } else {
                                            all_path.push(...segmentPath);
                                        }
                                        if (i === waypoints.length - 2) { 
                                            if (segmentPath.length > 0 && !areCoordsEqual(segmentPath[segmentPath.length - 1], { lng: realEnd.lng, lat: realEnd.lat })) {
                                                all_path.push({ lng: realEnd.lng, lat: realEnd.lat });
                                            }
                                        }
                                    } else {
                                        if (useFallback) {
                                            const lastPoint = all_path.length > 0 ? all_path[all_path.length - 1] : null;
                                            if (!lastPoint || (Math.abs(lastPoint.lng - realStart.lng) > 1e-6 || Math.abs(lastPoint.lat - realStart.lat) > 1e-6)) {
                                                all_path.push({ lng: realStart.lng, lat: realStart.lat });
                                            }
                                            all_path.push({ lng: realEnd.lng, lat: realEnd.lat });
                                        } else {
                                            return {error: `Segment ${i+1} failed after ${maxRetries+1} attempts: ${segmentResult.error}`};
                                        }
                                    }
                                }
                                
                                return {path: all_path};
                            }

                            return await planPath(waypointsPy, apiKey, pythonParams);
                        })
                        """,
                        waypoints,
                        amap_key,
                        acc.params,
                    )

                    if path_coords and "path" in path_coords:
                        api_path_coords = path_coords["path"]
                        acc.log(f"路径规划成功。")
                    else:
                        error_msg = (
                            path_coords.get("error", "未知错误")
                            if path_coords
                            else "无响应"
                        )
                        acc.log(f"路径规划失败: {error_msg}")
                        continue

                except Exception as e:
                    logging.error(f"Chrome浏览器池路径规划失败: {e}", exc_info=True)
                    acc.log(f"路径规划异常: {str(e)}")
                    continue

                if not api_path_coords:
                    acc.log("路径规划失败，跳过任务。")
                    continue

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
                        continue
                    coord = (longitude, p["lat"])
                    if coord != last_coord:
                        final_path_dedup.append(coord)
                        last_coord = coord

                if not final_path_dedup:
                    acc.log("路径处理失败：无有效坐标点。")
                    continue

                logging.debug(
                    f"[{acc.username}] 路径去重后点数: {len(final_path_dedup)}"
                )

                target_time_s = random.uniform(min_t_m * 60, max_t_m * 60)
                target_dist_m = random.uniform(min_d_m, min_d_m * 1.15)
                cumulative = [0.0]
                for idx_c in range(len(final_path_dedup) - 1):
                    cumulative.append(
                        cumulative[-1]
                        + self._calculate_distance_m(
                            final_path_dedup[idx_c][0],
                            final_path_dedup[idx_c][1],
                            final_path_dedup[idx_c + 1][0],
                            final_path_dedup[idx_c + 1][1],
                        )
                    )

                final_geo_path = self._get_path_for_distance(
                    final_path_dedup, cumulative, target_dist_m
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
                    acc.log("路径计算距离为0，跳过。")
                    continue

                acc.log(
                    f"路径计算完成: 目标距离 {actual_total_dist:.1f}m, 目标耗时 {target_time_s:.1f}s"
                )

                avg_speed = actual_total_dist / target_time_s
                new_run_coords = []
                start = final_geo_path[0]
                new_run_coords.append(
                    self._gps_random_offset(start[0], start[1], acc.params) + (0,)
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
                        + random.uniform(avg_speed * 0.9, avg_speed * 1.1) * interval,
                        actual_total_dist,
                    )
                    lon, lat = self._get_point_at_distance(
                        final_geo_path, final_cumulative, d_covered
                    )
                    lon_o, lat_o = self._gps_random_offset(lon, lat, acc.params)
                    new_run_coords.append((lon_o, lat_o, int(interval * 1000)))
                    t_elapsed += interval
                    if d_covered >= actual_total_dist:
                        break

                run_data.run_coords = new_run_coords
                run_data.total_run_distance_m = d_covered
                run_data.total_run_time_s = t_elapsed

                acc.log(f"已生成模拟轨迹: {len(new_run_coords)} 个GPS点")

                tasks_executed_count += 1

                run_data.trid = f"{acc.user_data.student_id}{int(time.time() * 1000)}"
                start_time_ms = str(int(time.time() * 1000))
                submission_successful = True
                total_points = max(1, len(run_data.run_coords))

                if total_points <= 1:
                    acc.log("警告: 生成的轨迹点数过少，无法执行任务。")
                    continue

                for chunk_idx in range(0, len(run_data.run_coords), 40):
                    logging.debug(
                        f"[{acc.username}] 执行进度: {chunk_idx}/{len(run_data.run_coords)}"
                    )
                    if self.multi_run_stop_flag.is_set() or acc.stop_event.is_set():
                        submission_successful = False
                        break

                    chunk = run_data.run_coords[chunk_idx : chunk_idx + 40]
                    processed_points = chunk_idx
                    for lon, lat, dur_ms in chunk:
                        if self.multi_run_stop_flag.is_set() or acc.stop_event.is_set():
                            submission_successful = False
                            break

                        session_id = getattr(self, "_web_session_id", None)

                        acc.current_position = {"lon": lon, "lat": lat}

                        if session_id and socketio:
                            try:
                                socketio.emit(
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

                        if acc.stop_event.wait(timeout=dur_ms / 1000.0):
                            submission_successful = False
                            break

                        processed_points += 1
                        try:
                            pct = int(processed_points * 100 / total_points)
                            self._update_account_status_js(
                                acc,
                                progress_pct=pct,
                                progress_text=f"运行 {i+1}/{len(tasks_to_run)}: {task_name_short} · {pct}%",
                                progress_extra=f"{processed_points}/{total_points} 点",
                            )
                        except Exception:
                            pass

                    if not submission_successful:
                        break

                    is_final_chunk = chunk_idx + 40 >= len(run_data.run_coords)
                    if not self._submit_chunk(
                        run_data,
                        chunk,
                        start_time_ms,
                        is_final_chunk,
                        chunk_idx,
                        acc.api_client,
                        acc.user_data,
                    ):
                        submission_successful = False
                        break

                if submission_successful:
                    acc.log(f"任务 {run_data.run_name} 数据提交完毕，等待服务器确认...")
                    time.sleep(3)
                    self._finalize_run(run_data, -1, acc.api_client)
                    run_data.status = 1
                    self._multi_fetch_and_summarize_tasks(acc)
                    self._update_account_status_js(acc, summary=acc.summary)
                    acc.log(f"任务 {run_data.run_name} 执行流程完成。")
                    self._update_account_status_js(
                        acc,
                        status_text="任务已完成",
                        progress_pct=100,
                        progress_text=f"运行 {i+1}/{len(tasks_to_run)}: {task_name_short} · 100%",
                        progress_extra="",
                    )
                else:
                    acc.log(f"任务 {run_data.run_name} 执行被中止。")
                    self._update_account_status_js(acc, status_text="已中止")

                if i < len(tasks_to_run) - 1:
                    wait_time = random.uniform(
                        acc.params["task_gap_min_s"], acc.params["task_gap_max_s"]
                    )
                    should_break_worker = False
                    end_time = time.time() + wait_time
                    while time.time() < end_time:
                        if acc.stop_event.is_set() or self.multi_run_stop_flag.is_set():
                            should_break_worker = True
                            break
                        remaining = end_time - time.time()
                        self._update_account_status_js(
                            acc, status_text=f"等待 {remaining:.0f}s"
                        )
                        time.sleep(1)
                    if should_break_worker:
                        self._update_account_status_js(acc, status_text="已中止")
                        break

            if not acc.stop_event.is_set():
                if tasks_executed_count == 0:
                    self._update_account_status_js(
                        acc,
                        status_text="无任务可执行",
                        progress_pct=100,
                        progress_text="无任务可执行",
                        progress_extra="",
                    )

                else:
                    self._update_account_status_js(acc, status_text="全部完成")

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
                            self._update_account_status_js(acc, status_text="待命")

            except Exception:
                logging.debug(
                    "Finalize worker status update failed (non-fatal).", exc_info=True
                )
            finally:
                self._update_multi_global_buttons()

    def _get_device_sign_code(self, username):
        """生成或获取设备标识码 (signCode)"""
        return str(uuid.uuid4())

    def _fetch_server_attendance_radius_if_needed(
        self, client: ApiClient, acc: AccountSession | None = None
    ):
        """
        (辅助函数) 检查并获取服务器签到半径。
        - 单账号模式: 缓存到 self.server_attendance_radius_m
        - 多账号模式: 缓存到 acc.server_attendance_radius_m
        """
        log_func = acc.log if acc else self.log
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
            logging.error(f"Failed to fetch attendance radius: {e}", exc_info=True)

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
        acc: AccountSession | None = None,
    ):
        """
        (已重构) 触发签到流程。
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
            log_func = acc.log
            user = acc.user_data
            params = acc.params
        elif not self.is_multi_account_mode:
            client = self.api_client
            log_func = self.log
            user = self.user_data
            params = self.params
        else:
            self.log("trigger_attendance 在多账号模式下被错误调用（未传入acc）")
            return {"success": False, "message": "多账号模式内部错误"}

        if not user.id:
            log_func("用户未登录，无法签到。")
            return {"success": False, "message": "用户未登录"}

        log_func(f"正在处理签到: {roll_call_id}")

        server_radius_m = self._fetch_server_attendance_radius_if_needed(client, acc)
        is_precise_checkin = server_radius_m <= 0

        try:
            info_resp = client.get_roll_call_info(roll_call_id, user.id)
            if info_resp and info_resp.get("success"):
                data = info_resp.get("data", {})
                roll_call_info = data.get("rollCallInfo", {})

                status = roll_call_info.get("status")
                finished = data.get("attendFinish")
            if status == -1:
                if not is_makeup:
                    log_func("此签到任务已过期（status=-1）。")
                    return {"success": False, "message": "任务已过期"}
                else:
                    log_func(f"任务 {roll_call_id} 已过期，正在尝试[补签]...")

                if status != -1 and (finished == 1 or finished is True):
                    log_func("你已经签到过了 (status!=-1 and attendFinish=1)。")
                    return {"success": True, "message": "已签到"}

                log_func("任务状态：待签到。")

            else:
                log_func("获取签到信息失败，将继续尝试签到...")
        except Exception as e:
            log_func(f"检查签到状态时出错: {e}，将继续尝试...")
            logging.error(f"Error checking roll call status: {e}", exc_info=True)

        final_lon, final_lat = 0.0, 0.0
        target_lon, target_lat = target_coords

        if location_choice == "specific" and specific_coords:
            final_lon, final_lat = specific_coords
            log_func(f"使用指定坐标签到: ({final_lon:.6f}, {final_lat:.6f})")

        elif location_choice == "random":
            radius_for_random = 0.0

            if not is_precise_checkin:
                user_radius_m = params.get("attendance_user_radius_m", 40)
                radius_for_random = max(0.0, min(user_radius_m, server_radius_m))

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
            log_func("使用[补签]负载提交...")
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
            log_func("使用[正常签到]负载提交...")

        try:
            log_func("正在提交签到...")
            submit_resp = client.submit_attendance(payload)
            if submit_resp and submit_resp.get("success"):
                log_func("签到成功！")
                logging.info(f"Attendance submitted successfully for {roll_call_id}")
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
                unread_count = count_resp.get("data", {}).get("unreadNumber", 0)

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
                        self.log("获取通知列表时失败。")
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
                        self.log("获取通知列表时失败。")
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

                            if status == -1:
                                notice["attendance_code"] = -1
                            elif status != -1 and (finished == 1 or finished is True):
                                notice["attendance_code"] = 1
                            else:
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
                    peek_notices = peek_resp.get("data", {}).get("noticeList", [])
                    has_more = len(peek_notices) > 0

            if not is_auto_refresh:
                self.log(
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
            self.log(f"获取通知失败: {e}")
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

    def _auto_refresh_worker(self):
        """(单账号) 后台自动刷新通知和签到的线程 (已修复)"""
        while not self.stop_auto_refresh.is_set():
            try:
                if not self.user_data.id or self.is_multi_account_mode:
                    if self.stop_auto_refresh.wait(timeout=5.0):
                        break
                    continue
                refresh_interval_s = self.params.get("auto_attendance_refresh_s", 30)
                refresh_interval_s = max(15, refresh_interval_s)
                if self.is_multi_account_mode or not self.user_data.id:
                    continue
                is_enabled = self.params.get("auto_attendance_enabled", False)
                if is_enabled:
                    self.log("(后台) 自动签到已启用，正在检查...")
                    self._check_and_trigger_auto_attendance(self)
                    self.log("正在自动刷新通知 (后台)...")
                    result = self.get_notifications(is_auto_refresh=True)
                    if result.get("success"):
                        session_id = getattr(self, "_web_session_id", None)
                        if session_id and "socketio" in globals():
                            try:
                                globals()["socketio"].emit(
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
                    pass

                self.log(f"自动刷新完成，等待 {refresh_interval_s} 秒后再次刷新...")
                if self.stop_auto_refresh.wait(timeout=refresh_interval_s):
                    break

            except Exception as e:
                self.log(f"自动刷新线程出错: {e}")
                logging.error(f"Auto-refresh worker error: {e}", exc_info=True)
                if self.stop_auto_refresh.wait(timeout=60):
                    break

        logging.info("Auto-refresh worker stopped.")

    def _check_and_trigger_auto_attendance(self, context: "Api | AccountSession"):
        """
        (辅助函数) 检查并执行单个上下文(Api或AccountSession)的自动签到。
        """
        if isinstance(context, AccountSession):
            client = context.api_client
            log_func = context.log
            user = context.user_data
            params = context.params
            if not params.get("auto_attendance_enabled", False):
                return
        else:
            client = self.api_client
            log_func = self.log
            user = self.user_data
            params = self.params
            if not params.get("auto_attendance_enabled", False):
                return

        if not user.id:
            log_func("用户未登录，跳过自动签到。")
            return

        log_func("(后台) 正在检查自动签到任务...")

        try:
            list_resp = client.get_notice_list(offset=0, limit=20, type_id=0)
            if not (list_resp and list_resp.get("success")):
                log_func("获取通知列表失败，跳过自动签到。")
                return

            notices = list_resp.get("data", {}).get("noticeList", [])
            if not notices:
                log_func("(后台) 通知列表为空。")
                return

            triggered_count = 0
            for notice in notices:
                is_attendance = notice.get(
                    "image"
                ) == "attendance" or "签到" in notice.get("title", "")
                if not (is_attendance and notice.get("id")):
                    continue

                roll_call_id = notice["id"]
                info_resp = client.get_roll_call_info(roll_call_id, user.id)

                status = -2
                finished = 0
                if info_resp and info_resp.get("success"):
                    data = info_resp.get("data", {})
                    roll_call_info = data.get("rollCallInfo", {})
                    status = roll_call_info.get("status")
                    finished = data.get("attendFinish")
                if status != -1 and not (finished == 1 or finished is True):
                    log_func(
                        f"检测到待签到任务 '{notice.get('title')}'，正在自动签到..."
                    )
                    coords_str = notice.get("updateBy", "").split(",")
                    if len(coords_str) == 2:
                        try:
                            target_lat, target_lon = float(coords_str[0]), float(
                                coords_str[1]
                            )
                            target_coords = (target_lon, target_lat)
                            auto_result = self.trigger_attendance(
                                roll_call_id,
                                target_coords,
                                "random",
                                specific_coords=None,
                                is_makeup=False,
                                acc=(
                                    context
                                    if isinstance(context, AccountSession)
                                    else None
                                ),
                            )

                            if auto_result.get("success"):
                                log_func(f"自动签到 '{notice.get('title')}' 成功。")
                                triggered_count += 1
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

        except Exception as e:
            log_func(f"自动签到检查时出错: {e}")
            logging.error(
                f"[_check_and_trigger_auto_attendance] Error: {e}", exc_info=True
            )

    def _multi_auto_attendance_worker(self):
        """(多账号) 后台自动刷新和签到所有账号的线程"""
        while not self.stop_multi_auto_refresh.wait(timeout=1.0):
            try:
                if (
                    not self.is_multi_account_mode
                    or not self.global_params.get("auto_attendance_enabled", False)
                    or not self.accounts
                ):
                    time.sleep(5)
                    continue

                refresh_interval_s = self.global_params.get("auto_attendance_refresh_s")

                self.log(f"(多账号) 自动签到: 等待 {refresh_interval_s} 秒...")
                if self.stop_multi_auto_refresh.wait(timeout=refresh_interval_s):
                    break

                if not self.is_multi_account_mode or not self.global_params.get(
                    "auto_attendance_enabled", False
                ):
                    continue

                self.log("(多账号) 正在为所有账号执行后台签到检查...")

                accounts_to_check = list(self.accounts.values())

                for acc in accounts_to_check:
                    if self.stop_multi_auto_refresh.is_set():
                        break
                    if acc.params.get("auto_attendance_enabled", False):
                        if acc.user_data.id:
                            self._check_and_trigger_auto_attendance(acc)
                            self._multi_fetch_attendance_stats(acc)
                            self._update_account_status_js(acc, summary=acc.summary)
                            time.sleep(random.uniform(1.0, 3.0))
                        else:

                            acc.log("(后台) 尚未登录，跳过自动签到检查。")
                    else:

                        acc.log("(后台) 自动签到未在此账号上启用，跳过。")

            except Exception as e:
                self.log(f"(多账号) 自动签到线程出错: {e}")
                logging.error(f"Multi-auto-attendance worker error: {e}", exc_info=True)
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


# ==============================================================================
# 4. 前端界面 (HTML/CSS/JS)
# ==============================================================================


def resource_path(relative_path):
    """获取资源文件的绝对路径，兼容 PyInstaller 打包和开发环境"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def check_port_available(host, port):
    """检查端口是否可用"""

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False


IP_CACHE_FILE = os.path.join("logs", "ip_location_cache.json")
ip_location_cache = {}
ip_cache_lock = threading.Lock()
CACHE_DURATION_SECONDS = 86400


def _load_ip_cache():
    """启动时加载IP归属地缓存文件"""
    global ip_location_cache
    if not os.path.exists(IP_CACHE_FILE):
        logging.info("[IP缓存] 缓存文件不存在，将创建新缓存")
        return

    with ip_cache_lock:
        try:
            with open(IP_CACHE_FILE, "r", encoding="utf-8") as f:
                ip_location_cache = json.load(f)
            logging.info(f"[IP缓存] 成功加载 {len(ip_location_cache)} 条IP缓存记录")
        except (json.JSONDecodeError, OSError) as e:
            logging.warning(f"[IP缓存] 加载缓存文件失败: {e}，将创建新缓存")
            ip_location_cache = {}


def _save_ip_cache():
    """保存IP归属地缓存到文件（线程安全）"""
    with ip_cache_lock:
        try:
            os.makedirs(os.path.dirname(IP_CACHE_FILE), exist_ok=True)
            cache_copy = ip_location_cache.copy()

            with open(IP_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache_copy, f, indent=2, ensure_ascii=False)
            logging.debug("[IP缓存] IP缓存已保存到文件")
        except OSError as e:
            logging.error(f"[IP缓存] 保存缓存文件失败: {e}")
        except Exception as e:
            logging.error(f"[IP缓存] 序列化缓存数据失败: {e}")


def update_session_activity(session_id):
    """更新会话活动时间"""
    with session_activity_lock:
        session_activity[session_id] = time.time()


def update_session_activity(session_id):
    """更新会话活动时间（线程安全）"""
    if not session_id:
        return
    with session_activity_lock:
        session_activity[session_id] = time.time()
        logging.debug(f"[会话活跃] 更新会话 {session_id} 的活跃时间")


def cleanup_session(session_id, reason="manual"):
    """清理指定会话（支持指定原因）"""
    if not session_id or session_id == "null" or session_id.strip() == "":
        logging.debug(f"跳过清理无效会话ID: '{session_id}'")
        return

    logging.info(f"清理会话: {session_id} (原因: {reason})")
    cleanup_inactive_session(session_id)


def cleanup_inactive_session(session_id):
    """清理不活跃的会话"""
    if not session_id or session_id == "null" or session_id.strip() == "":
        logging.debug(f"跳过清理无效会话ID: '{session_id}'")
        return

    try:
        logging.info(f"清理不活跃会话: {session_id}")
        with web_sessions_lock:
            if session_id in web_sessions:
                api_instance = web_sessions[session_id]
                if hasattr(api_instance, "stop_run_flag"):
                    api_instance.stop_run_flag.set()
                if hasattr(api_instance, "auth_username") and not getattr(
                    api_instance, "is_guest", True
                ):
                    username = api_instance.auth_username
                    is_browsing = False
                    try:
                        timeout = 300
                        if os.path.exists(CONFIG_FILE):
                            cfg = configparser.ConfigParser()
                            cfg.read(CONFIG_FILE, encoding="utf-8")
                            timeout = cfg.getint(
                                "System", "session_inactivity_timeout", fallback=300
                            )
                        user_sids = auth_system.get_user_sessions(username)
                        current_ts = time.time()
                        with browsing_activity_lock:
                            for sid in user_sids:
                                if sid == session_id:
                                    continue

                                last_browse_ts = browsing_activity.get(sid, 0)
                                if current_ts - last_browse_ts < timeout:
                                    is_browsing = True
                                    break
                    except Exception as e:
                        logging.error(f"检查浏览状态失败: {e}")

                    auth_system.unlink_session_from_user(username, session_id)
                    if not is_browsing:
                        token_manager.invalidate_token(username, session_id)
                        logging.info(
                            f"已使用户 {username} 的会话 {session_id} 的token失效 (无其他浏览行为)"
                        )
                    else:
                        logging.info(
                            f"用户 {username} 仍在其他页面浏览，跳过 Token 失效，仅清理过期会话 {session_id}"
                        )

                del web_sessions[session_id]
        session_hash = hashlib.sha256(session_id.encode()).hexdigest()
        session_file = os.path.join(SESSION_STORAGE_DIR, f"{session_hash}.json")
        if os.path.exists(session_file):
            os.remove(session_file)
            logging.info(f"已删除会话文件: {session_hash}")
        with session_activity_lock:
            if session_id in session_activity:
                del session_activity[session_id]
        with browsing_activity_lock:
            if session_id in browsing_activity:
                del browsing_activity[session_id]
        index = _load_session_index()
        if session_id in index:
            del index[session_id]
            _save_session_index(index)

        logging.info(f"会话清理完成: {session_id}")
    except Exception as e:
        logging.error(f"清理会话失败 {session_id} {e}")


def monitor_session_inactivity():
    """
    监控会话不活跃状态并清理
    """
    check_interval = 60
    inactivity_timeout = 300

    try:
        if os.path.exists("config.ini"):
            config = configparser.ConfigParser()
            config.read("config.ini", encoding="utf-8")
            if config.has_section("System"):
                check_interval = config.getint(
                    "System", "session_monitor_check_interval", fallback=60
                )
                inactivity_timeout = config.getint(
                    "System", "session_inactivity_timeout", fallback=300
                )
    except Exception as e:
        logging.warning(f"读取会话监控配置失败，使用默认值: {e}")

    while True:
        try:
            time.sleep(check_interval)
            current_time = time.time()
            inactive_sessions_to_cleanup = []
            active_sessions_to_update = []
            with web_sessions_lock:
                sessions_snapshot = list(web_sessions.items())

            for session_id, api_instance in sessions_snapshot:
                if not api_instance:
                    continue
                with session_activity_lock:
                    if session_id not in session_activity:
                        session_activity[session_id] = current_time
                    last_activity = session_activity[session_id]

                has_background_activity = False
                if (
                    hasattr(api_instance, "stop_run_flag")
                    and not api_instance.stop_run_flag.is_set()
                ):
                    has_background_activity = True
                    logging.debug(f"[会话监控] {session_id} 单账号跑步任务执行中")
                if (
                    hasattr(api_instance, "multi_run_stop_flag")
                    and not api_instance.multi_run_stop_flag.is_set()
                ):
                    has_background_activity = True
                    logging.debug(f"[会话监控] {session_id} 多账号跑步任务执行中")
                is_multi = getattr(api_instance, "is_multi_account_mode", False)

                if is_multi:
                    accounts = getattr(api_instance, "accounts", {})
                    global_params = getattr(api_instance, "multi_global_params", {})
                    auto_attendance = global_params.get(
                        "auto_attendance_enabled", False
                    )
                    logging.debug(
                        f"[会话监控] {session_id} 多账号模式自动签到状态: {auto_attendance}, 账号数: {len(accounts)}"
                    )
                    if accounts and auto_attendance:
                        has_background_activity = True
                        logging.debug(f"[会话监控] {session_id} 多账号自动签到开启中")
                else:
                    params = getattr(api_instance, "params", {})
                    auto_attendance = params.get("auto_attendance_enabled", False)
                    logging.debug(
                        f"[会话监控] {session_id} 单账号模式自动签到状态: {auto_attendance}"
                    )

                    if auto_attendance:
                        has_background_activity = True
                        logging.debug(f"[会话监控] {session_id} 单账号自动签到开启中")

                # --- 结果处理 ---
                if has_background_activity:
                    active_sessions_to_update.append(session_id)
                    logging.debug(f"[会话监控] {session_id} 有后台任务，更新活跃时间")
                elif (current_time - last_activity) > inactivity_timeout:
                    logging.debug(f"[会话监控] {session_id} 超过不活跃超时阈值")
                    inactive_sessions_to_cleanup.append(session_id)
                else:
                    logging.debug(
                        f"[会话监控] {session_id} 仍在活跃期内，上次活跃时间: {current_time - last_activity:.1f}秒前"
                    )

            if active_sessions_to_update:
                with session_activity_lock:
                    for sid in active_sessions_to_update:
                        session_activity[sid] = current_time

            if inactive_sessions_to_cleanup:
                logging.info(
                    f"[会话监控] 发现 {len(inactive_sessions_to_cleanup)} 个超时且无后台任务的会话，准备清理"
                )
                for sid in inactive_sessions_to_cleanup:
                    cleanup_inactive_session(sid)

        except Exception as e:
            logging.error(f"会话监控线程错误: {e}", exc_info=True)


def start_session_monitor():
    """启动会话不活跃监控"""
    monitor_thread = threading.Thread(target=monitor_session_inactivity, daemon=True)
    monitor_thread.start()
    logging.info("会话监控线程已启动")


def _load_session_index():
    """加载会话索引文件"""
    try:
        if os.path.exists(SESSION_INDEX_FILE):
            with open(SESSION_INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.warning(f"加载会话索引失败: {e}")
    return {}


def _save_session_index(index):
    """保存会话索引文件"""
    try:
        with open(SESSION_INDEX_FILE, "w", encoding="utf-8") as f:
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
    if not session_id or session_id == "null":
        logging.warning(f"拒绝保存会话：无效的 session_id: '{session_id}'")
        return
    try:
        session_hash = hashlib.sha256(session_id.encode()).hexdigest()
        session_file = os.path.join(SESSION_STORAGE_DIR, f"{session_hash}.json")
        with session_file_locks_lock:
            if session_hash not in session_file_locks:
                session_file_locks[session_hash] = threading.Lock()
            file_lock = session_file_locks[session_hash]
        with file_lock:
            if not force_save:
                last_save_time = getattr(api_instance, "_last_session_save_time", 0)
                if time.time() - last_save_time < 2.0:
                    return
            api_instance._last_session_save_time = time.time()
            state = {
                "session_id": session_id,
                "school_account_logged_in": getattr(
                    api_instance, "login_success", False
                ),
                "login_success": getattr(api_instance, "login_success", False),
                "user_info": getattr(api_instance, "user_info", None),
                "created_at": getattr(api_instance, "_session_created_at", time.time()),
                "last_accessed": time.time(),
                "last_saved": time.time(),
            }
            if hasattr(api_instance, "auth_username"):
                state["auth_username"] = api_instance.auth_username
                state["auth_group"] = getattr(api_instance, "auth_group", "guest")
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
            state["is_offline_mode"] = getattr(api_instance, "is_offline_mode", False)

            if (
                hasattr(api_instance, "api_client")
                and api_instance.api_client.session.cookies
            ):
                try:
                    state["api_cookies"] = requests.utils.dict_from_cookiejar(
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
                            "school_account_logged_in": bool(
                                getattr(account_session, "user_data", None)
                                and getattr(account_session.user_data, "id", "")
                            )
                            and getattr(
                                account_session, "is_first_login_verified", False
                            ),
                            "summary": getattr(account_session, "summary", {}),
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
                            "school_account_logged_in": bool(
                                getattr(account_session, "user_data", None)
                                and getattr(account_session.user_data, "id", "")
                            )
                            and getattr(
                                account_session, "is_first_login_verified", False
                            ),
                            "summary": getattr(account_session, "summary", {}),
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
                        if getattr(acc, "login_success", False)
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
            index = _load_session_index()
            index[session_id] = session_hash
            _save_session_index(index)

            tasks_count = len(state.get("loaded_tasks", []))
            logging.debug(
                f"会话状态已保存: {session_id} (任务数:{tasks_count}, 选中索引:{state.get('current_run_idx', -1)})"
            )
    except Exception as e:
        logging.error(f"保存会话状态失败: {e}", exc_info=True)


def load_session_state(session_id):
    """从文件加载会话状态"""
    try:
        index = _load_session_index()
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

        session_file = os.path.join(SESSION_STORAGE_DIR, f"{session_hash}.json")

        if os.path.exists(session_file):
            with session_file_locks_lock:
                if session_hash not in session_file_locks:
                    session_file_locks[session_hash] = threading.Lock()
                file_lock = session_file_locks[session_hash]
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
        if not os.path.exists(SESSION_STORAGE_DIR):
            return

        max_age_days = 7
        max_age_seconds = max_age_days * 86400
        current_time = time.time()
        cleaned_count = 0
        error_count = 0

        logging.info(f"[会话清理] 开始清理过期会话 --> 最大保留期限: {max_age_days}天")

        for filename in os.listdir(SESSION_STORAGE_DIR):
            if not filename.endswith(".json") or filename == "_index.json":
                continue

            session_file = os.path.join(SESSION_STORAGE_DIR, filename)

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
            api_instance.is_authenticated = state.get("is_authenticated", False)
        if "login_success" in state:
            api_instance.login_success = state["login_success"]
        if "user_info" in state:
            api_instance.user_info = state["user_info"]
        if "params" in state:
            api_instance.params = state["params"]
        if "device_ua" in state:
            api_instance.device_ua = state["device_ua"]
        if "cached_notifications" in state:
            api_instance.cached_notifications = state["cached_notifications"]
        if "user_data" in state:
            user_data_dict = state["user_data"]
            api_instance.user_data.name = user_data_dict.get("name", "")
            api_instance.user_data.phone = user_data_dict.get("phone", "")
            api_instance.user_data.student_id = user_data_dict.get("student_id", "")
            api_instance.user_data.id = user_data_dict.get("id", "")
            api_instance.user_data.username = user_data_dict.get("username", "")
            api_instance.user_data.gender = user_data_dict.get("gender", "")
            api_instance.user_data.school_name = user_data_dict.get("school_name", "")
        if "loaded_tasks" in state:
            api_instance.all_run_data = []
            for task_dict in state["loaded_tasks"]:
                run_data = RunData()
                run_data.run_name = task_dict.get("run_name", "")
                run_data.errand_id = task_dict.get("errand_id", "")
                run_data.errand_schedule = task_dict.get("errand_schedule", "")
                run_data.status = task_dict.get("status", 0)
                run_data.start_time = task_dict.get("start_time", "")
                run_data.end_time = task_dict.get("end_time", "")
                run_data.upload_time = task_dict.get("upload_time", "")
                run_data.total_run_time_s = task_dict.get("total_run_time_s", 0.0)
                run_data.total_run_distance_m = task_dict.get(
                    "total_run_distance_m", 0.0
                )
                run_data.target_points = [
                    tuple(p) for p in task_dict.get("target_points", [])
                ]
                run_data.target_point_names = task_dict.get("target_point_names", "")
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
                run_data.is_in_target_zone = task_dict.get("is_in_target_zone", False)
                run_data.trid = task_dict.get("trid", "")
                run_data.details_fetched = task_dict.get("details_fetched", False)
                run_data.distance_covered_m = task_dict.get("distance_covered_m", 0.0)

                api_instance.all_run_data.append(run_data)
        if "current_run_idx" in state:
            api_instance.current_run_idx = state["current_run_idx"]
        if "is_offline_mode" in state:
            api_instance.is_offline_mode = state["is_offline_mode"]
        if "is_multi_account_mode" in state:
            api_instance.is_multi_account_mode = state["is_multi_account_mode"]
            if state["is_multi_account_mode"]:
                if "multi_global_params" in state:
                    api_instance.global_params = state["multi_global_params"]
                if "multi_account_states" in state:
                    multi_account_states = state["multi_account_states"]

                    logging.info(
                        f"会话恢复：找到 {len(multi_account_states)} 个账号状态，正在重建..."
                    )

                    for username, account_state in multi_account_states.items():
                        if username not in api_instance.accounts:
                            try:
                                loaded_password = api_instance._load_config(username)
                                loaded_tag = api_instance._load_account_tag(username)
                                acc = AccountSession(
                                    username=username,
                                    password=loaded_password or "",
                                    api_bridge=api_instance,
                                    tag=loaded_tag or "",
                                )
                                acc.status_text = account_state.get(
                                    "status_text", "待命"
                                )
                                acc.params = account_state.get("params", acc.params)
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
                                if account_state.get("school_account_logged_in", False):
                                    acc.login_success = True
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
                    requests.utils.cookiejar_from_dict(cookies_dict)
                )
                logging.info(
                    f"会话恢复: 成功恢复 {len(cookies_dict)} 个 API Cookies (shiroCookie等)。"
                )
            except Exception as e:
                logging.warning(f"会话恢复: 恢复 API Cookies 失败: {e}")
        if not api_instance.is_multi_account_mode and api_instance.params.get(
            "auto_attendance_enabled", False
        ):
            api_instance.stop_auto_refresh.clear()
            api_instance.auto_refresh_thread = threading.Thread(
                target=api_instance._auto_refresh_worker, daemon=True
            )
            api_instance.auto_refresh_thread.start()
            logging.info(f"会话恢复: 已重启单账号自动签到后台线程")
        if api_instance.is_multi_account_mode and api_instance.global_params.get(
            "auto_attendance_enabled", False
        ):
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


def get_captcha_original_width(html_content):
    """
    【移动端验证码缩放】获取验证码的原始宽度
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        container = soup.find("div")
        if not container:
            return None

        spans = container.find_all("span")
        if not spans:
            return None

        pixel_classes = list(set([s.get("class")[0] for s in spans if s.get("class")]))
        if not pixel_classes:
            return None
        first_line_spans = 0
        for child in container.contents:
            if child.name == "br":
                break
            if child.name == "span":
                first_line_spans += 1

        num_cols = first_line_spans
        if num_cols == 0:
            return None
        style_tag = soup.find("style")
        if not style_tag:
            return None

        css_text = style_tag.string
        sample_pixel_class = pixel_classes[0]
        container_class = container.get("class")[0]
        w_match = re.search(
            rf"\.{container_class}\s+span[^}}]*width\s*:\s*(\d+(\.\d+)?)px", css_text
        )

        if not w_match:
            w_match = re.search(
                rf"\.{sample_pixel_class}[^}}]*width\s*:\s*(\d+(\.\d+)?)px", css_text
            )

        if not w_match:
            return None

        old_pixel_w = float(w_match.group(1))
        original_width = num_cols * old_pixel_w

        logging.debug(
            f"[get_captcha_original_width] 列数={num_cols}, 像素宽度={old_pixel_w}px, 总宽度={original_width}px"
        )

        return original_width

    except Exception as e:
        logging.error(f"[get_captcha_original_width] 解析失败: {e}")
        return None


def resize_captcha_html(html_content, target_width):
    """
    自动分析并调整像素验证码HTML的大小 (Grid Layout 增强版 - 修正Padding/Border计算)。
    """
    try:
        target_width = float(target_width)
        soup = BeautifulSoup(html_content, "html.parser")
        container = soup.find("div")
        if not container:
            logging.warning("[resize_captcha_html] 无法找到容器 div")
            return html_content

        container_class = container.get("class")[0]
        style_tag = soup.find("style")
        if not style_tag:
            return html_content

        css_text = style_tag.string
        num_cols = 0
        old_pixel_w = 0.0
        old_pixel_h = 0.0
        old_gap = 0.0
        grid_match = re.search(
            r"grid-template-columns\s*:\s*repeat\(\s*(\d+)\s*,\s*(\d+(?:\.\d+)?)\s*px\s*\)",
            css_text,
            re.IGNORECASE,
        )

        if grid_match:
            num_cols = int(grid_match.group(1))
            old_pixel_w = float(grid_match.group(2))
            logging.info(
                f"[验证码缩放] 检测到 CSS Grid 布局: {num_cols} 列, 原始宽 {old_pixel_w}px"
            )
        else:
            pass

        if num_cols == 0:
            logging.error("[resize_captcha_html] 无法解析列数，跳过缩放")
            return html_content
        gap_match = re.search(
            rf"\.{container_class}\s*\{{.*?\bgap\s*:\s*(\d+(?:\.\d+)?)px",
            css_text,
            re.DOTALL | re.IGNORECASE,
        )
        if gap_match:
            old_gap = float(gap_match.group(1))
        h_match = re.search(
            rf"\.{container_class}\s+span[^}}]*?height\s*:\s*(\d+(\.\d+)?)px",
            css_text,
            re.IGNORECASE,
        )
        if h_match:
            old_pixel_h = float(h_match.group(1))
        else:
            old_pixel_h = old_pixel_w
        padding_w = 0.0
        border_w = 0.0
        pad_match = re.search(
            rf"\.{container_class}\s*\{{.*?\bpadding\s*:\s*(\d+(?:\.\d+)?)px",
            css_text,
            re.DOTALL | re.IGNORECASE,
        )
        if pad_match:
            padding_w = float(pad_match.group(1)) * 2
        bor_match = re.search(
            rf"\.{container_class}\s*\{{.*?\bborder\s*:\s*(\d+(?:\.\d+)?)px",
            css_text,
            re.DOTALL | re.IGNORECASE,
        )
        if bor_match:
            border_w = float(bor_match.group(1)) * 2
        original_grid_width = (num_cols * old_pixel_w) + ((num_cols - 1) * old_gap)

        if original_grid_width <= 0:
            return html_content
        available_grid_width = target_width - padding_w - border_w

        if available_grid_width <= 0:
            logging.warning(f"[验证码缩放] 目标宽度过小，无法容纳Padding/Border")
            return html_content
        scale_ratio = available_grid_width / original_grid_width
        if scale_ratio >= 1.0:
            logging.info(
                f"[验证码缩放] 目标宽度 ({target_width}px) 足以容纳原始尺寸，跳过放大 (Ratio: {scale_ratio:.2f})"
            )
            return html_content
        new_pixel_w = old_pixel_w * scale_ratio
        new_pixel_h = old_pixel_h * scale_ratio
        new_gap = old_gap * scale_ratio

        logging.info(
            f"[验证码缩放] Scaling: {scale_ratio:.4f} | Pad/Bor: {padding_w}/{border_w} | Target Grid: {available_grid_width:.2f}px"
        )
        new_css = css_text
        new_css = re.sub(
            r"(grid-template-columns\s*:\s*repeat\(\s*\d+\s*,\s*)(\d+(?:\.\d+)?)px",
            rf"\g<1>{new_pixel_w:.4f}px",
            new_css,
            flags=re.IGNORECASE,
        )
        if old_gap >= 0:
            new_css = re.sub(
                rf"(\.{container_class}\s*\{{.*?\bgap\s*:\s*)(\d+(?:\.\d+)?)px",
                rf"\g<1>{new_gap:.4f}px",
                new_css,
                flags=re.DOTALL | re.IGNORECASE,
            )
        new_css = re.sub(
            rf"(\.{container_class}\s+span[^}}]*?width\s*:\s*)(\d+(\.\d+)?)px",
            rf"\g<1>{new_pixel_w:.4f}px",
            new_css,
            flags=re.IGNORECASE,
        )
        new_css = re.sub(
            rf"(\.{container_class}\s+span[^}}]*?height\s*:\s*)(\d+(\.\d+)?)px",
            rf"\g<1>{new_pixel_h:.4f}px",
            new_css,
            flags=re.IGNORECASE,
        )
        spans = container.find_all("span")
        pixel_classes = set([s.get("class")[0] for s in spans if s.get("class")])

        for p_class in pixel_classes:
            new_css = re.sub(
                rf"(\.{p_class}[^}}]*?(?<![-\w])width\s*:\s*)(\d+(\.\d+)?)px",
                rf"\g<1>{new_pixel_w:.4f}px",
                new_css,
                flags=re.IGNORECASE,
            )
            new_css = re.sub(
                rf"(\.{p_class}[^}}]*?(?<![-\w])height\s*:\s*)(\d+(\.\d+)?)px",
                rf"\g<1>{new_pixel_h:.4f}px",
                new_css,
                flags=re.IGNORECASE,
            )

        style_tag.string = new_css
        return str(soup)

    except Exception as e:
        logging.error(f"[resize_captcha_html] 调整失败: {e}", exc_info=True)
        return html_content


def load_all_sessions(args):
    """启动时加载所有持久化会话"""
    if not os.path.exists(SESSION_STORAGE_DIR):
        return
    index = _load_session_index()
    new_index = {}

    successful_sessions = {}

    loaded_count = 0
    for filename in os.listdir(SESSION_STORAGE_DIR):
        if filename == "_index.json":
            continue

        if filename.endswith(".json"):
            session_file = os.path.join(SESSION_STORAGE_DIR, filename)
            session_id = None
            session_hash = filename[:-5]
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    state = json.load(f)

                session_id = state.get("session_id")
                if not session_id:
                    raise ValueError(f"文件 {filename} 缺少 session_id")
                last_accessed = state.get("last_accessed", 0)
                if time.time() - last_accessed > 7 * 24 * 3600:
                    logging.info(
                        f"清理过期会话: {session_id[:8]}... (文件: {filename})"
                    )
                    try:
                        os.remove(session_file)
                    except Exception as remove_err:
                        logging.error(f"删除过期会话文件 {filename} 失败: {remove_err}")
                    continue
                api_instance = Api(args)
                api_instance._session_created_at = state.get("created_at", time.time())
                api_instance._web_session_id = session_id
                restore_session_to_api_instance(api_instance, state)
                logging.info(
                    f"成功恢复会话: {session_id}... (用户: {api_instance.auth_username if hasattr(api_instance, 'auth_username') else 'Unknown'}, 文件: {filename})"
                )
                web_sessions[session_id] = api_instance
                session_activity[session_id] = last_accessed
                successful_sessions[session_id] = session_hash
                loaded_count += 1

            except (
                json.JSONDecodeError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
            ) as e:
                logging.error(
                    f"加载或恢复会话文件 {filename} 失败: {e}", exc_info=False
                )
                logging.warning(f"将删除损坏的/无法恢复的会话文件: {filename}")
                try:
                    os.remove(session_file)
                except Exception as remove_err:
                    logging.error(f"删除损坏的会话文件 {filename} 失败: {remove_err}")
                continue
            except Exception as e:
                logging.error(
                    f"处理会话文件 {filename} 时发生未知错误: {e}", exc_info=True
                )
                try:
                    os.remove(session_file)
                except Exception as remove_err:
                    logging.error(
                        f"删除未知错误的会话文件 {filename} 失败: {remove_err}"
                    )
                continue
    if successful_sessions:
        _save_session_index(successful_sessions)
        logging.info(f"会话索引已更新，包含 {len(successful_sessions)} 个有效会话")
    elif not any(
        f.endswith(".json") and f != "_index.json"
        for f in os.listdir(SESSION_STORAGE_DIR)
    ):
        _save_session_index({})
        logging.info("会话目录为空，已清空会话索引。")
    if new_index:
        _save_session_index(new_index)
        logging.debug(f"会话索引已更新，包含 {len(new_index)} 个有效会话")

    if loaded_count > 0:
        logging.info(f"共加载 {loaded_count} 个持久化会话")


class BackgroundTaskManager:
    """管理服务器端后台任务执行"""

    def __init__(self):
        self.tasks = {}
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
        except Exception as e:
            logging.error(f"保存后台任务状态失败: {e}")

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
        """启动后台任务执行"""
        with self.lock:
            task_state = {
                "session_id": session_id,
                "total_tasks": len(task_indices),
                "completed_tasks": 0,
                "current_task_index": 0,
                "task_indices": task_indices,
                "auto_generate": auto_generate,
                "status": "running",
                "start_time": time.time(),
                "last_update": time.time(),
                "progress_percent": 0,
                "current_task_progress": 0,
                "singleProcessedPoints": 0,
                "singleTotalPoints": 0,
            }

            self.tasks[session_id] = task_state
            self.save_task_state(session_id, task_state)
            thread = threading.Thread(
                target=self._execute_tasks_background,
                args=(session_id, api_instance, task_indices, auto_generate),
                daemon=True,
            )
            thread.start()

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
                            details_resp = api_instance.get_task_details(task_idx)
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
                        amap_key = ""
                        try:
                            if os.path.exists(CONFIG_FILE):
                                cfg = configparser.ConfigParser()
                                cfg.read(CONFIG_FILE, encoding="utf-8")
                                amap_key = cfg.get("Map", "amap_js_key", fallback="")
                                if not amap_key:
                                    amap_key = cfg.get(
                                        "System", "AmapJsKey", fallback=""
                                    )

                            if amap_key:
                                logging.info(f"已从 {CONFIG_FILE} 实时加载 AMap Key。")
                            else:
                                logging.error(
                                    f"无法为 {run_data.run_name} 自动规划路径：实时读取 {CONFIG_FILE} 失败，[Map] -> amap_js_key 缺失或为空。"
                                )
                                with self.lock:
                                    task_state["status"] = "error"
                                    task_state["error"] = (
                                        "缺少高德地图API Key (实时读取失败)"
                                    )
                                    self.save_task_state(session_id, task_state)
                                continue

                        except Exception as e:
                            logging.error(
                                f"实时读取 AMap Key 时发生错误: {e}", exc_info=True
                            )
                            with self.lock:
                                task_state["status"] = "error"
                                task_state["error"] = f"读取Config.ini失败: {e}"
                                self.save_task_state(session_id, task_state)
                            continue

                        global chrome_pool
                        if not chrome_pool:
                            logging.error("Chrome浏览器池不可用，无法进行路径规划！")
                            continue

                        if chrome_pool:
                            try:
                                logging.info(
                                    f"正在获取Chrome浏览器上下文，会话ID前缀: {session_id[:8]}..."
                                )
                                ctx = chrome_pool.get_context(session_id)
                                page = ctx["page"]
                                logging.info("Chrome浏览器上下文获取成功")
                                logging.info("正在向Chrome页面加载高德地图SDK...")
                                page.goto("about:blank")
                                page.set_content(
                                    """
                                <!DOCTYPE html>
                                <html>
                                <head>
                                    <meta charset="utf-8">
                                    <script type="text/javascript" src="https://webapi.amap.com/loader.js"></script>
                                </head>
                                <body></body>
                                </html>
                                """
                                )
                                logging.info(
                                    "等待高德地图加载器(AMapLoader)加载完成..."
                                )
                                page.wait_for_function(
                                    "typeof AMapLoader !== 'undefined'", timeout=10000
                                )
                                logging.info("高德地图加载器在Chrome上下文中加载成功")
                                logging.info(
                                    f"正在Chrome浏览器中执行路径规划JavaScript代码..."
                                )
                                path_coords = chrome_pool.execute_js(
                                    session_id,
                                    """
                                    (async (arg) => {
                                        const waypointsPy = arg[0]; // 这是Python传入的 [[lon, lat], ...]
                                        const apiKey = arg[1];
                                        const pythonParams = arg[2]; // <--- 读取 Python 传入的参数

                                        // 1. 定义辅助函数 (planPath)
                                        async function planPath(waypointsPy, apiKey, pythonParams) {
                                            
                                            // 1.1 确保 AMapLoader (来自 loader.js) 存在
                                            if (typeof AMapLoader === 'undefined') {
                                                return {error: 'AMapLoader not loaded'};
                                            }

                                            // 1.2 调用 AMapLoader.load 并传入 key
                                            try {
                                                await AMapLoader.load({
                                                    "key": apiKey,
                                                    "version": "2.0",
                                                    "plugins": ["AMap.Walking"]
                                                });
                                            } catch (e) {
                                                return {error: 'AMapLoader.load failed: ' + (e ? e.message : 'Unknown error')};
                                            }

                                            // 1.3 检查 AMap.Walking 插件是否真的加载成功
                                            if (typeof AMap.Walking === 'undefined') {
                                                return {error: 'AMap.Walking plugin failed to load'};
                                            }

                                            // 1.4 ★ 步骤 2 修复：从 pythonParams 读取重试和回退设置
                                            const useFallback = pythonParams.api_fallback_line ?? false;
                                            const maxRetries = pythonParams.api_retries ?? 2;
                                            const retryDelayMs = (pythonParams.api_retry_delay_s ?? 0.5) * 1000;
                                            const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

                                            // 1.5 定义分段搜索函数 (同 index.html)
                                            const searchSegment = (start, end, walkingInstance) => new Promise((resolve) => {
                                                walkingInstance.search(start, end, (status, result) => {
                                                    if (status === 'complete' && result.routes?.length > 0) {
                                                        const p = []; 
                                                        result.routes[0].steps.forEach(s => s.path.forEach(pt => p.push({ lng: pt.lng, lat: pt.lat })));
                                                        resolve({ path: p }); // 返回成功路径
                                                    } else {
                                                        let errorInfo = 'Unknown Error';
                                                        if (status === 'error') {
                                                            if (result && result.info) {
                                                                errorInfo = result.info;
                                                            } else if (result) {
                                                                try { errorInfo = JSON.stringify(result); } catch (e) { errorInfo = result.toString(); }
                                                            } else {
                                                                errorInfo = status;
                                                            }
                                                        } else if (status === 'no_data') {
                                                            errorInfo = 'No path found (no_data)';
                                                        } else {
                                                            errorInfo = status; // 如 "CUQPS_HAS_EXCEEDED_THE_LIMIT"
                                                        }
                                                        resolve({ error: 'Path planning failed: ' + errorInfo }); // 返回错误
                                                    }
                                                });
                                            });

                                            // 1.6 ★ 步骤 2 修复：迭代执行路径规划 (增加重试循环)
                                            const all_path = [];
                                            const waypoints = waypointsPy.map(p => new AMap.LngLat(p[0], p[1]));
                                            const walking = new AMap.Walking({ map: null, panel: "", hideMarkers: true });

                                            if (waypoints.length < 2) {
                                                return {error: 'Waypoints must be at least 2.'};
                                            }

                                            for (let i = 0; i < waypoints.length - 1; i++) {
                                                const realStart = waypoints[i];
                                                const realEnd = waypoints[i + 1];
                                                
                                                let attempts = 0;
                                                let segmentResult = null;
                                                let segmentPath = null; // 存储成功的路径

                                                // --- 增加重试循环 (来自 index.html) ---
                                                while (attempts <= maxRetries) {
                                                    if (attempts > 0) {
                                                        await sleep(retryDelayMs); // 等待后重试
                                                    }
                                                    
                                                    segmentResult = await searchSegment(realStart, realEnd, walking);
                                                    
                                                    if (segmentResult.path) { // 检查 .path 是否存在 (成功)
                                                        segmentPath = segmentResult.path;
                                                        break; // 成功，退出重试循环
                                                    }
                                                    
                                                    // 失败，记录最后一次错误 (将在重试用尽时使用)
                                                    // (不需要 console.log，Python端会记录最终错误)
                                                    
                                                    attempts++;
                                                }
                                                // --- 结束重试循环 ---

                                                if (segmentPath) {
                                                    // 成功: 拼接路径
                                                    const areCoordsEqual = (c1, c2) => Math.abs(c1.lng - c2.lng) < 1e-6 && Math.abs(c1.lat - c2.lat) < 1e-6;
                                                    if (i > 0) {
                                                        all_path.push(...segmentPath.slice(1));
                                                    } else {
                                                        all_path.push(...segmentPath);
                                                    }
                                                    if (i === waypoints.length - 2) { 
                                                        if (segmentPath.length > 0 && !areCoordsEqual(segmentPath[segmentPath.length - 1], { lng: realEnd.lng, lat: realEnd.lat })) {
                                                            all_path.push({ lng: realEnd.lng, lat: realEnd.lat });
                                                        }
                                                    }
                                                } else {
                                                    // 失败: 检查回退
                                                    if (useFallback) {
                                                        // 使用直线回退 (确保连接性)
                                                        const lastPoint = all_path.length > 0 ? all_path[all_path.length - 1] : null;
                                                        if (!lastPoint || (Math.abs(lastPoint.lng - realStart.lng) > 1e-6 || Math.abs(lastPoint.lat - realStart.lat) > 1e-6)) {
                                                            all_path.push({ lng: realStart.lng, lat: realStart.lat });
                                                        }
                                                        all_path.push({ lng: realEnd.lng, lat: realEnd.lat });
                                                    } else {
                                                        // 不回退，整个规划失败
                                                        return {error: `Segment ${i+1} failed after ${maxRetries+1} attempts: ${segmentResult.error}`};
                                                    }
                                                }
                                            }
                                            
                                            // 成功
                                            return {path: all_path};
                                        }

                                        // 2. 调用辅助函数并返回结果
                                        return await planPath(waypointsPy, apiKey, pythonParams);
                                    })
                                    """,
                                    waypoints,
                                    amap_key,
                                    api_instance.params,
                                )

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
                                                task_state["last_update"] = time.time()
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
                                                total_points = len(run_data.run_coords)
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
                                        path_coords.get("error", "Unknown error")
                                        if path_coords
                                        else "No response from path planning"
                                    )
                                    logging.error(
                                        f"任务路径规划失败，任务名称: {run_data.run_name}，错误信息: {error_msg}"
                                    )
                                    continue
                            except Exception as e:
                                logging.error(
                                    f"Chrome浏览器池路径规划失败，任务名称: {run_data.run_name}，异常信息: {e}",
                                    exc_info=True,
                                )
                                continue
                        else:
                            logging.error("Chrome浏览器池不可用，无法进行路径规划")
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
                    total_time_s = sum(p[2] for p in run_data.run_coords) / 1000.0
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
                                task_state["elapsed_time_s"] = time.time() - start_wait
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
                with self.lock:
                    task_state["completed_tasks"] = i + 1
                    task_state["progress_percent"] = int(
                        (i + 1) / len(task_indices) * 100
                    )
                    task_state["current_task_progress"] = 100
                    task_state["last_update"] = time.time()
                    self.save_task_state(session_id, task_state)

                logging.info(
                    f"任务 {i+1}/{len(task_indices)} 已完成，会话ID前缀: {session_id[:8]}"
                )
            if tasks_executed > 0:
                with self.lock:
                    task_state["status"] = "completed"
                    task_state["last_update"] = time.time()
                    self.save_task_state(session_id, task_state)

                logging.info(f"所有后台任务已完成，会话ID前缀: {session_id[:8]}")
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

            pixels.append(f'<span class="{cls_fg if is_fg else cls_bg}"></span>')

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

    注意：由于应用使用了 eventlet.monkey_patch()，Playwright 的同步 API 无法直接在
    eventlet 的 greenlet 协作式调度环境中运行。之前使用 eventlet.tpool.execute() 的方案
    会导致 "Cannot switch to a different thread" 错误，因为 tpool 每次可能使用不同的线程，
    而 Playwright 对象是线程绑定的。

    解决方案：创建一个专用的持久化原生线程来运行所有 Playwright 操作。
    使用队列机制将操作请求发送到这个专用线程，并等待结果返回。
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
        from eventlet import patcher

        # 获取原生的 threading 模块，用于创建真正的系统线程
        self._native_threading = patcher.original("threading")
        # 获取原生的 queue 模块，用于线程间通信
        self._native_queue = patcher.original("queue")

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
                request = self._request_queue.get(timeout=self.QUEUE_POLL_TIMEOUT_SEC)
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
                        args.get("session_id"), args.get("url"), args.get("options", {})
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
                logging.error(f"Playwright 操作 {operation} 失败: {e}", exc_info=True)
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
            logging.error(f"执行 JS 失败 (session={session_id}): {e}", exc_info=True)
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
                page.set_content(html, **options) if options else page.set_content(html)
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

        这是从 eventlet greenlet 调用的方法，它将操作请求发送到专用线程的队列，
        然后等待操作完成并返回结果。

        使用 eventlet.tpool.execute() 包装 Event.wait() 调用，避免阻塞 eventlet 调度器。

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
        # 这确保在 eventlet 环境中也能正确等待
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

        # 导入 eventlet.tpool 用于在真实线程中等待结果
        # 这避免了阻塞 eventlet 的协作式调度器
        import eventlet.tpool

        # 定义等待函数，在 tpool 线程中执行
        def _wait_for_result(event, timeout_sec):
            # 使用原生 Event.wait() 等待结果
            return event.wait(timeout=timeout_sec)

        # 通过 tpool.execute() 在真实线程中等待，保持 eventlet 调度器响应
        try:
            wait_result = eventlet.tpool.execute(
                _wait_for_result, result_event, timeout
            )
        except Exception as e:
            # 如果 tpool 执行失败，记录错误并返回
            logging.error(f"等待 Playwright 操作结果时出错: {e}", exc_info=True)
            return {"success": False, "error": f"等待结果失败: {str(e)}"}

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
            logging.error(f"执行 JS 异常 (session={session_id}): {e}", exc_info=True)
            return None

    def close_context(self, session_id):
        """
        关闭指定会话的浏览器上下文（通过专用线程执行）。

        参数:
            session_id: 要关闭的会话标识符
        """
        try:
            # 向专用线程发送关闭上下文请求
            result = self._send_request("close_context", {"session_id": session_id})
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


def _cleanup_playwright():
    """
    在程序退出时清理Playwright资源。

    此函数会先调用 cleanup_thread() 清理 Playwright 资源，
    然后调用 shutdown() 停止专用工作线程。
    """
    global chrome_pool
    if chrome_pool:
        logging.info("捕获到程序退出信号，正在清理 Playwright 资源...")
        try:
            # 先清理 Playwright 资源（浏览器、上下文等）
            chrome_pool.cleanup_thread()
            # 再停止专用工作线程
            chrome_pool.shutdown()
            logging.info("Playwright浏览器自动化框架资源清理完成")
        except Exception as e:
            logging.error(f"清理 Playwright 资源时发生错误: {e}", exc_info=False)
    else:
        logging.debug("Playwright 池未初始化，无需清理。")


def start_background_auto_attendance(args):
    """
    在服务器启动时扫描所有.ini配置文件，为启用自动签到的账号启动后台工作线程。
    """
    try:
        logging.info("正在启动后台自动签到服务...")

        accounts_dir = SCHOOL_ACCOUNTS_DIR

        if not os.path.exists(accounts_dir):
            logging.warning(f"后台签到：未找到账号目录 {accounts_dir}，跳过。")
            return

        enabled_accounts = []

        for filename in os.listdir(accounts_dir):
            if filename.endswith(".ini"):
                username = os.path.splitext(filename)[0]
                try:
                    temp_api = Api(args)
                    password = temp_api._load_config(username)

                    if not password:
                        logging.debug(
                            f"后台签到：跳过账号 {username}，因为未在 {filename} 中找到密码。"
                        )
                        continue

                    if temp_api.params.get("auto_attendance_enabled", False):
                        enabled_accounts.append(
                            {
                                "username": username,
                                "password": password,
                                "params": dict(temp_api.params),
                            }
                        )
                        logging.info(f"后台签到：找到启用自动签到的账号: {username}")
                    else:
                        logging.debug(
                            f"后台签到：账号 {username} 未启用自动签到，跳过。"
                        )

                except Exception as e:
                    logging.error(
                        f"后台签到：加载账号 {username} 失败: {e}", exc_info=True
                    )

        if not enabled_accounts:
            logging.info("后台签到：未找到启用自动签到的账号。")
            return

        if len(enabled_accounts) == 1:
            account = enabled_accounts[0]
            logging.info(f"后台签到：使用单账号模式，账号: {account['username']}")

            service_api = Api(args)
            service_api.is_multi_account_mode = False
            service_api.params = account["params"]
            try:
                login_result = service_api.login(
                    account["username"], account["password"]
                )
                if login_result.get("success"):
                    logging.info(f"后台签到：账号 {account['username']} 登录成功")
                    service_api.stop_auto_refresh.clear()
                    service_api.auto_refresh_thread = threading.Thread(
                        target=service_api._auto_refresh_worker,
                        daemon=True,
                        name=f"BackgroundAttendance-{account['username']}",
                    )
                    service_api.auto_refresh_thread.start()
                    globals()["_background_service_api"] = service_api
                    logging.info(f"后台签到：单账号模式启动成功")
                else:
                    logging.error(
                        f"后台签到：账号 {account['username']} 登录失败: {login_result.get('message')}"
                    )
            except Exception as e:
                logging.error(
                    f"后台签到：账号 {account['username']} 登录时发生错误: {e}",
                    exc_info=True,
                )

        else:
            logging.info(f"后台签到：使用多账号模式，共 {len(enabled_accounts)} 个账号")

            service_api = Api(args)
            service_api.is_multi_account_mode = True
            service_api._load_global_config()
            service_api.global_params["auto_attendance_enabled"] = True
            for account in enabled_accounts:
                try:
                    acc_session = AccountSession(
                        account["username"], account["password"], service_api
                    )
                    acc_session.params = account["params"]
                    service_api.accounts[account["username"]] = acc_session
                except Exception as e:
                    logging.error(
                        f"后台签到：创建账号会话失败 {account['username']}: {e}",
                        exc_info=True,
                    )
            service_api.stop_multi_auto_refresh.clear()
            service_api.multi_auto_refresh_thread = threading.Thread(
                target=service_api._multi_auto_attendance_worker,
                daemon=True,
                name="BackgroundAttendanceWorker-Multi",
            )
            service_api.multi_auto_refresh_thread.start()
            globals()["_background_service_api"] = service_api
            logging.info(
                f"后台签到：多账号模式启动成功，已加载 {len(service_api.accounts)} 个账号"
            )

    except Exception as e:
        logging.error(f"启动后台自动签到服务时发生严重错误: {e}", exc_info=True)


# ============================================================================
# SSL/HTTPS 配置和证书管理相关函数
# 这些函数用于加载、验证和管理SSL证书，支持HTTPS服务
# ============================================================================


def load_ssl_config():
    """
    从config.ini文件加载SSL配置。
    """
    config_file = os.path.join(os.path.dirname(__file__), "config.ini")
    config = configparser.ConfigParser()
    default_config = {
        "ssl_enabled": False,
        "ssl_cert_path": "ssl/fullchain.pem",
        "ssl_key_path": "ssl/privkey.key",
        "https_only": False,
    }

    try:
        if not os.path.exists(config_file):
            logging.warning(f"配置文件 {config_file} 不存在，使用默认SSL配置（禁用）")
            return default_config
        config.read(config_file, encoding="utf-8")
        if not config.has_section("SSL"):
            logging.warning("配置文件中未找到[SSL]节，使用默认SSL配置（禁用）")
            return default_config
        ssl_config = {
            "ssl_enabled": config.getboolean("SSL", "ssl_enabled", fallback=False),
            "ssl_cert_path": config.get(
                "SSL", "ssl_cert_path", fallback="ssl/fullchain.pem"
            ),
            "ssl_key_path": config.get(
                "SSL", "ssl_key_path", fallback="ssl/privkey.key"
            ),
            "https_only": config.getboolean("SSL", "https_only", fallback=False),
        }
        logging.info(
            f"SSL配置加载成功: enabled={ssl_config['ssl_enabled']}, https_only={ssl_config['https_only']}"
        )

        return ssl_config

    except Exception as e:
        logging.error(f"加载SSL配置时发生错误: {e}，使用默认配置（禁用SSL）")
        return default_config


def save_ssl_config(ssl_config):
    """
    将SSL配置保存到config.ini文件。

    参数：
        ssl_config (dict): 包含SSL配置的字典，键应包括：
            - ssl_enabled (bool): 是否启用SSL
            - ssl_cert_path (str): 证书文件路径
            - ssl_key_path (str): 私钥文件路径
            - https_only (bool): 是否仅允许HTTPS访问

    返回值：
        bool: 保存成功返回True，失败返回False
    """
    config_file = os.path.join(os.path.dirname(__file__), "config.ini")
    config = configparser.ConfigParser()

    try:
        if os.path.exists(config_file):
            config.read(config_file, encoding="utf-8")
        else:
            logging.warning("config.ini 文件不存在，将创建新的配置文件")
            config = _get_default_config()
        if not config.has_section("SSL"):
            config.add_section("SSL")
        config.set(
            "SSL", "ssl_enabled", str(ssl_config.get("ssl_enabled", False)).lower()
        )
        config.set(
            "SSL", "ssl_cert_path", ssl_config.get("ssl_cert_path", "ssl/fullchain.pem")
        )
        config.set(
            "SSL", "ssl_key_path", ssl_config.get("ssl_key_path", "ssl/privkey.key")
        )
        config.set(
            "SSL", "https_only", str(ssl_config.get("https_only", False)).lower()
        )
        _write_config_with_comments(config, config_file)

        logging.info("SSL配置已成功保存到配置文件")
        return True

    except Exception as e:
        logging.error(f"保存SSL配置时发生错误: {e}")
        return False


def validate_ssl_certificate(cert_path, key_path):
    """
    验证SSL证书文件和密钥文件是否有效。
    """
    if not os.path.isabs(cert_path):
        cert_path = os.path.join(os.path.dirname(__file__), cert_path)
    if not os.path.isabs(key_path):
        key_path = os.path.join(os.path.dirname(__file__), key_path)
    if not os.path.exists(cert_path):
        error_msg = f"证书文件不存在: {cert_path}"
        logging.error(error_msg)
        return False, error_msg, {}
    if not os.path.exists(key_path):
        error_msg = f"密钥文件不存在: {key_path}"
        logging.error(error_msg)
        return False, error_msg, {}
    if not os.access(cert_path, os.R_OK):
        error_msg = f"证书文件不可读（权限不足）: {cert_path}"
        logging.error(error_msg)
        return False, error_msg, {}
    if not os.access(key_path, os.R_OK):
        error_msg = f"密钥文件不可读（权限不足）: {key_path}"
        logging.error(error_msg)
        return False, error_msg, {}
    try:
        with open(cert_path, "r", encoding="utf-8") as f:
            cert_content = f.read()
            if "-----BEGIN CERTIFICATE-----" not in cert_content:
                error_msg = f"证书文件格式无效（不是PEM格式）: {cert_path}"
                logging.error(error_msg)
                return False, error_msg, {}
    except Exception as e:
        error_msg = f"读取证书文件时发生错误: {e}"
        logging.error(error_msg)
        return False, error_msg, {}
    try:
        with open(key_path, "r", encoding="utf-8") as f:
            key_content = f.read()
            valid_key_headers = [
                "-----BEGIN PRIVATE KEY-----",
                "-----BEGIN RSA PRIVATE KEY-----",
                "-----BEGIN EC PRIVATE KEY-----",
                "-----BEGIN DSA PRIVATE KEY-----",
            ]
            if not any(header in key_content for header in valid_key_headers):
                error_msg = f"密钥文件格式无效（不是PEM格式）: {key_path}"
                logging.error(error_msg)
                return False, error_msg, {}
    except Exception as e:
        error_msg = f"读取密钥文件时发生错误: {e}"
        logging.error(error_msg)
        return False, error_msg, {}
    cert_info = {
        "cert_path": cert_path,
        "key_path": key_path,
        "valid": True,
        "message": "证书文件格式验证通过",
    }
    try:
        import ssl

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        cert_info["message"] = "证书和密钥验证通过，可以安全使用"
        logging.info(f"SSL证书验证成功: {cert_path}")

    except Exception as e:
        error_msg = f"SSL证书深度验证失败: {e}，但基础格式验证已通过"
        logging.warning(error_msg)
        cert_info["message"] = error_msg
    return True, "", cert_info


def get_ssl_certificate_info(cert_path):
    """
    获取SSL证书的详细信息（如有效期、颁发者、主题等）。
    """
    if not os.path.isabs(cert_path):
        cert_path = os.path.join(os.path.dirname(__file__), cert_path)
    cert_info = {}

    try:
        import ssl
        from datetime import datetime

        with open(cert_path, "rb") as f:
            cert_data = f.read()
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        cert_info = {
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
            "version": cert.version.name,
            "serial_number": str(cert.serial_number),
            "not_before": cert.not_valid_before_utc.isoformat(),
            "not_after": cert.not_valid_after_utc.isoformat(),
            "is_expired": datetime.now()
            > cert.not_valid_after_utc.replace(tzinfo=None),
        }
        try:
            san_ext = cert.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            )
            cert_info["san"] = [name.value for name in san_ext.value]
        except x509.ExtensionNotFound:
            cert_info["san"] = []

        logging.info(f"成功获取证书信息: {cert_path}")

    except ImportError:
        logging.warning("cryptography库不可用，无法获取详细的证书信息")
        cert_info = {
            "error": "需要安装cryptography库才能查看详细证书信息",
            "install_hint": "pip install cryptography",
        }
    except Exception as e:
        logging.error(f"获取证书信息时发生错误: {e}")
        cert_info = {"error": f"读取证书信息失败: {str(e)}"}

    return cert_info


def start_web_server(args_param):
    """
    启动Flask Web服务器主函数，集成SocketIO实时通信和Chrome浏览器自动化。
    """
    global chrome_pool, background_task_manager, web_sessions, web_sessions_lock, session_file_locks, session_file_locks_lock, session_activity, session_activity_lock, args
    global server_start_time
    server_start_time = time.time()
    logging.info(
        f"服务器启动时间: {datetime.datetime.fromtimestamp(server_start_time).strftime('%Y-%m-%d %H:%M:%S')}"
    )
    args = args_param
    global cache
    cache = {}
    global sms_verification_codes
    sms_verification_codes = {}
    web_sessions = {}
    web_sessions_lock = threading.Lock()
    session_file_locks = {}
    session_file_locks_lock = threading.Lock()
    session_activity = {}
    session_activity_lock = threading.Lock()
    logging.info("内存锁和会话状态已重置。")
    try:
        chrome_pool = ChromeBrowserPool(headless=getattr(args, "headless", True))
        logging.info("Chrome浏览器池初始化成功")
        atexit.register(_cleanup_playwright)
        logging.info("已注册 Playwright 退出清理函数。")
    except Exception as e:
        logging.error(f"无法初始化Chrome浏览器池: {e}")
        sys.exit(1)
    try:
        background_task_manager = BackgroundTaskManager()
        logging.info("后台任务管理器初始化成功")

        logging.info("程序启动：正在清理所有历史后台任务记录（内存和文件）...")
        cleaned_files_count = 0
        if background_task_manager and hasattr(
            background_task_manager, "task_storage_dir"
        ):
            task_dir = background_task_manager.task_storage_dir
            if os.path.exists(task_dir):
                with background_task_manager.lock:
                    background_task_manager.tasks.clear()
                for filename in os.listdir(task_dir):
                    if filename.endswith(".json"):
                        file_path = os.path.join(task_dir, filename)
                        try:
                            os.remove(file_path)
                            cleaned_files_count += 1
                        except Exception as e:
                            logging.error(f"无法删除后台任务文件 {filename}: {e}")
            logging.info(
                f"已清空后台任务管理器内存状态，并删除了 {cleaned_files_count} 个任务状态文件。"
            )
        else:
            logging.warning(
                "无法清理后台任务文件：BackgroundTaskManager 或其 task_storage_dir 未定义。"
            )

    except Exception as e:
        logging.error(f"无法初始化后台任务管理器: {e}")
        sys.exit(1)

    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    CORS(app)
    global socketio
    socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=7)

    # ===== JS/CSS 文件本地缓存系统 =====
    # 缓存目录配置
    JS_CACHE_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "cache", "cdn"
    )
    os.makedirs(JS_CACHE_DIR, exist_ok=True)

    # 需要缓存的CDN文件列表
    CDN_FILES = {
        "sweetalert2": {
            "url": "https://cdn.jsdelivr.net/npm/sweetalert2@11",
            "filename": "sweetalert2.min.js",
            "type": "js",
        },
        "qrcode": {
            "url": "https://cdn.jsdelivr.net/npm/qrcode/build/qrcode.min.js",
            "filename": "qrcode.min.js",
            "type": "js",
        },
        "cropperjs": {
            "url": "https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.js",
            "filename": "cropper.min.js",
            "type": "js",
        },
        "cropperjs-css": {
            "url": "https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.css",
            "filename": "cropper.min.css",
            "type": "css",
        },
        "tailwindcss": {
            "url": "https://cdn.tailwindcss.com",
            "filename": "tailwindcss.min.js",
            "type": "js",
        },
        "socketio": {
            "url": "https://cdn.socket.io/4.8.1/socket.io.min.js",  # 自动获取最新稳定版
            "filename": "socket.io.min.js",
            "type": "js",
            "check_latest": True,  # 标记需要检查最新版本
        },
        "google-fonts": {
            "url": "https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@600;700&family=Noto+Sans+SC:wght@400;600;700&display=swap",
            "filename": "google-fonts.css",
            "type": "css",
        },
        "amap-loader": {
            "url": "https://webapi.amap.com/loader.js",
            "filename": "amap-loader.js",
            "type": "js",
        },
    }

    # JS缓存存储
    js_cache_storage = {}
    js_cache_lock = threading.Lock()
    js_cache_last_update = {}

    # 字体文件缓存存储（用于Google Fonts的TTF文件）
    font_cache_storage = {}
    font_cache_lock = threading.Lock()

    def parse_google_fonts_css(css_content):
        """
        解析Google Fonts CSS内容，提取所有字体文件URL

        参数:
            css_content: CSS文件内容

        返回:
            字体URL列表 [(url, font_name), ...]
        """
        import re

        # 匹配 url(https://...) 格式的链接
        pattern = r"url\((https://fonts\.gstatic\.com/[^)]+)\)"
        urls = re.findall(pattern, css_content)

        # 为每个URL生成唯一的标识符（基于文件名）
        font_urls = []
        for url in urls:
            # 从URL提取文件名作为标识符
            # 例如: https://fonts.gstatic.com/s/notosanssc/v39/xxx.ttf -> notosanssc-xxx.ttf
            parts = url.split("/")
            if len(parts) >= 2:
                font_family = parts[-3] if len(parts) >= 3 else "font"
                font_file = parts[-1]
                font_key = f"{font_family}-{font_file}"
            else:
                font_key = url.split("/")[-1]
            font_urls.append((url, font_key))

        return font_urls

    def cache_google_fonts_with_ttf(css_content, key):
        """
        缓存Google Fonts CSS及其引用的所有TTF字体文件

        参数:
            css_content: CSS文件内容
            key: 缓存键名

        返回:
            处理后的CSS内容（URL已替换为本地API地址）
        """
        import re

        # 解析CSS中的字体URL
        font_urls = parse_google_fonts_css(css_content)
        logging.info(f"[CDN缓存] 发现 {len(font_urls)} 个字体文件需要缓存")

        modified_css = css_content

        for original_url, font_key in font_urls:
            # 下载字体文件（二进制模式）
            logging.info(f"[CDN缓存] 正在下载字体: {font_key}")
            font_content = fetch_cdn_file(original_url, timeout=60, binary=True)

            if font_content:
                # 缓存字体文件（二进制）
                with font_cache_lock:
                    font_cache_storage[font_key] = font_content

                # 保存到本地文件
                font_filename = font_key
                save_cached_file(font_filename, font_content, binary=True)

                # 替换CSS中的URL为本地API地址
                local_url = f"/api/cdn/font/{font_key}"
                modified_css = modified_css.replace(original_url, local_url)
                logging.info(f"[CDN缓存] 字体已缓存: {font_key}")
            else:
                logging.warning(f"[CDN缓存] 字体下载失败: {font_key}")

        return modified_css

    def load_cached_fonts():
        """
        从本地缓存加载所有字体文件
        """
        try:
            fonts_dir = JS_CACHE_DIR
            if not os.path.exists(fonts_dir):
                return

            for filename in os.listdir(fonts_dir):
                if (
                    filename.endswith(".ttf")
                    or filename.endswith(".woff")
                    or filename.endswith(".woff2")
                ):
                    filepath = os.path.join(fonts_dir, filename)
                    try:
                        with open(filepath, "rb") as f:
                            content = f.read()
                        with font_cache_lock:
                            font_cache_storage[filename] = content
                        logging.info(f"[CDN缓存] 从本地加载字体: {filename}")
                    except Exception as e:
                        logging.warning(f"[CDN缓存] 加载字体文件失败 {filename}: {e}")
        except Exception as e:
            logging.warning(f"[CDN缓存] 扫描字体缓存目录失败: {e}")

    def get_latest_socketio_version():
        """
        获取socket.io的最新稳定版本号
        """
        try:
            # 从npm registry获取最新版本
            response = requests.get(
                "https://registry.npmjs.org/socket.io-client/latest", timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                version = data.get("version", "4.8.1")
                logging.info(f"[CDN缓存] Socket.IO 最新版本: {version}")
                return version
        except Exception as e:
            logging.warning(f"[CDN缓存] 获取Socket.IO最新版本失败: {e}")
        return "4.8.1"  # 默认版本

    def fetch_cdn_file(url, timeout=30, binary=False):
        """
        从CDN获取文件内容

        参数:
            url: 文件URL
            timeout: 超时时间（秒）
            binary: 是否以二进制模式获取（用于字体文件等）
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return response.content if binary else response.text
            else:
                logging.warning(
                    f"[CDN缓存] 获取文件失败，状态码: {response.status_code}, URL: {url}"
                )
                return None
        except Exception as e:
            logging.error(f"[CDN缓存] 获取文件异常: {e}, URL: {url}")
            return None

    def load_cached_file(filename, binary=False):
        """
        从本地缓存文件加载内容

        参数:
            filename: 文件名
            binary: 是否以二进制模式读取
        """
        cache_path = os.path.join(JS_CACHE_DIR, filename)
        if os.path.exists(cache_path):
            try:
                mode = "rb" if binary else "r"
                encoding = None if binary else "utf-8"
                with open(cache_path, mode, encoding=encoding) as f:
                    return f.read()
            except Exception as e:
                logging.error(f"[CDN缓存] 读取缓存文件失败: {e}, 文件: {filename}")
        return None

    def save_cached_file(filename, content, binary=False):
        """
        保存内容到本地缓存文件

        参数:
            filename: 文件名
            content: 文件内容
            binary: 是否以二进制模式写入
        """
        cache_path = os.path.join(JS_CACHE_DIR, filename)
        try:
            mode = "wb" if binary else "w"
            encoding = None if binary else "utf-8"
            with open(cache_path, mode, encoding=encoding) as f:
                f.write(content)
            logging.info(f"[CDN缓存] 已保存缓存文件: {filename}")
            return True
        except Exception as e:
            logging.error(f"[CDN缓存] 保存缓存文件失败: {e}, 文件: {filename}")
            return False

    def update_single_cdn_file(key, config):
        """
        更新单个CDN文件的缓存
        """
        url = config["url"]
        filename = config["filename"]

        # 如果是socket.io且标记需要检查最新版本，则动态获取最新版本URL
        if config.get("check_latest") and key == "socketio":
            latest_version = get_latest_socketio_version()
            url = f"https://cdn.socket.io/{latest_version}/socket.io.min.js"
            logging.info(f"[CDN缓存] Socket.IO 使用最新版本: {latest_version}")

        logging.info(f"[CDN缓存] 正在获取: {key} ({url})")
        content = fetch_cdn_file(url)

        if content:
            # 如果是 Google Fonts，需要特殊处理：解析并缓存TTF字体文件
            if key == "google-fonts":
                logging.info(f"[CDN缓存] 正在解析Google Fonts CSS并缓存字体文件...")
                content = cache_google_fonts_with_ttf(content, key)

            with js_cache_lock:
                js_cache_storage[key] = content
                js_cache_last_update[key] = time.time()
            save_cached_file(filename, content)
            logging.info(f"[CDN缓存] 成功更新: {key}")
            return True
        else:
            # 获取失败，尝试使用本地缓存
            cached = load_cached_file(filename)
            if cached:
                with js_cache_lock:
                    if key not in js_cache_storage:
                        js_cache_storage[key] = cached
                logging.warning(f"[CDN缓存] 获取失败，使用本地缓存: {key}")
                return False
            else:
                logging.error(f"[CDN缓存] 获取失败且无本地缓存: {key}")
                return False

    def update_all_cdn_files():
        """
        更新所有CDN文件的缓存
        """
        logging.info("[CDN缓存] 开始更新所有CDN文件...")
        success_count = 0
        fail_count = 0

        for key, config in CDN_FILES.items():
            if update_single_cdn_file(key, config):
                success_count += 1
            else:
                fail_count += 1

        logging.info(f"[CDN缓存] 更新完成: 成功 {success_count}, 失败 {fail_count}")
        return success_count, fail_count

    def init_cdn_cache():
        """
        初始化CDN缓存：先尝试加载本地缓存，如果没有则从CDN获取
        """
        logging.info("[CDN缓存] 正在初始化CDN文件缓存...")

        # 先加载缓存的字体文件
        load_cached_fonts()

        for key, config in CDN_FILES.items():
            filename = config["filename"]
            # 先尝试加载本地缓存
            cached = load_cached_file(filename)
            if cached:
                with js_cache_lock:
                    js_cache_storage[key] = cached
                    js_cache_last_update[key] = os.path.getmtime(
                        os.path.join(JS_CACHE_DIR, filename)
                    )
                logging.info(f"[CDN缓存] 从本地加载: {key}")
            else:
                # 本地没有缓存，从CDN获取
                update_single_cdn_file(key, config)

        logging.info(
            f"[CDN缓存] 初始化完成，已缓存 {len(js_cache_storage)} 个JS/CSS文件, {len(font_cache_storage)} 个字体文件"
        )

    def cdn_cache_update_worker():
        """
        CDN缓存定时更新工作线程（每小时检查一次）
        """
        UPDATE_INTERVAL = 3600  # 1小时

        while True:
            try:
                time.sleep(UPDATE_INTERVAL)
                logging.info("[CDN缓存] 定时更新任务开始...")
                update_all_cdn_files()
            except Exception as e:
                logging.error(f"[CDN缓存] 定时更新任务异常: {e}")

    # 初始化CDN缓存
    init_cdn_cache()

    # 启动CDN缓存定时更新线程
    cdn_update_thread = threading.Thread(target=cdn_cache_update_worker, daemon=True)
    cdn_update_thread.start()
    logging.info("[CDN缓存] 定时更新线程已启动（每小时检查一次）")

    # ===== 登录验证装饰器 =====
    def login_required(f):
        """
        一个装饰器，用于验证用户是否已登录。
        它检查 X-Session-ID，验证会话，并将用户信息存储在 g 对象中。
        """

        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            session_id = request.headers.get("X-Session-ID", "")
            api_instance = None
            is_authenticated = False
            auth_username = None
            if session_id:
                with web_sessions_lock:
                    if session_id in web_sessions:
                        api_instance = web_sessions[session_id]
                        is_authenticated = getattr(
                            api_instance, "is_authenticated", False
                        )
                        auth_username = getattr(api_instance, "auth_username", None)
            if not is_authenticated or not api_instance or not auth_username:
                return jsonify({"success": False, "message": "未登录或会话无效"}), 401
            if getattr(api_instance, "is_guest", False):
                return jsonify({"success": False, "message": "游客无权访问此功能"}), 403
            g.user = auth_username
            g.api_instance = api_instance
            return f(*args, **kwargs)

        return decorated_function

    @app.before_request
    def check_ip_ban_before_request():
        """
        全局IP封禁检查拦截器
        """
        client_ip = request.remote_addr
        if (
            request.path.startswith("/static/")
            or request.path.startswith("/css/")
            or request.path.startswith("/js/")
            or request.path == "/health"
            or request.path.endswith(".png")
            or request.path.endswith(".jpg")
            or request.path.endswith(".ico")
        ):
            return None
        is_banned = check_ip_ban(client_ip, scope="all")

        if is_banned:
            logging.warning(
                f"[IP封禁] 全局封禁拦截：IP {client_ip} 尝试访问 {request.path}"
            )
            banned_html = (
                """
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>访问被拒绝</title>
                <style>
                    body {
                        font-family: 'Microsoft YaHei', Arial, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                        color: #333;
                    }
                    .container {
                        background: white;
                        padding: 40px;
                        border-radius: 15px;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                        text-align: center;
                        max-width: 500px;
                    }
                    h1 {
                        color: #e74c3c;
                        font-size: 48px;
                        margin: 0 0 20px 0;
                    }
                    p {
                        font-size: 18px;
                        color: #555;
                        line-height: 1.6;
                    }
                    .ip {
                        background: #f8f9fa;
                        padding: 10px;
                        border-radius: 5px;
                        font-family: monospace;
                        color: #495057;
                        margin-top: 20px;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🚫 访问被拒绝</h1>
                    <p>您的IP地址已被系统封禁。</p>
                    <p>如有疑问，请联系系统管理员。</p>
                    <div class="ip">您的IP: """
                + client_ip
                + """</div>
                </div>
            </body>
            </html>
            """
            )
            return make_response(banned_html, 403)

        return None

    # ====================
    # 认证相关API路由
    # ====================

    # ====================
    # 辅助函数：线程安全的会话管理
    # ====================

    def get_session_user_safe(
        session_id, required_permission=None, require_super_admin=False
    ):
        """
        【并发安全辅助函数】线程安全地获取会话用户信息并验证权限

        功能说明：
        1. 使用锁保护web_sessions字典的并发访问
        2. 验证会话有效性和用户认证状态
        3. 提取用户信息（在锁保护范围内）
        4. 释放锁后执行权限检查（避免长时间持锁）

        参数:
            session_id (str): 会话ID，从请求头X-Session-ID获取
            required_permission (str, optional): 需要检查的权限名称，如'manage_users'
            require_super_admin (bool, optional): 是否要求超级管理员权限

        返回:
            tuple: (success: bool, result: dict或Response)
            - 成功时: (True, {"username": str, "group": str, "api_instance": object})
            - 失败时: (False, jsonify({...})) - 可直接返回给前端的错误响应

        使用示例：
            success, result = get_session_user_safe(session_id, 'manage_users')
            if not success:
                return result  # 返回错误响应
            username = result['username']  # 使用用户信息

        线程安全说明：
        - 函数内部使用web_sessions_lock确保线程安全
        - 只在锁内访问web_sessions字典和api_instance属性
        - 耗时的权限检查操作在锁外执行，避免阻塞其他请求
        """
        with web_sessions_lock:
            if not session_id or session_id not in web_sessions:
                return False, jsonify({"success": False, "message": "未授权"}), 401
            api_instance = web_sessions[session_id]
            if not hasattr(api_instance, "auth_username"):
                return False, jsonify({"success": False, "message": "未登录"}), 401
            user_info = {
                "username": api_instance.auth_username,
                "group": getattr(api_instance, "auth_group", "user"),
                "api_instance": api_instance,
            }
        if require_super_admin:
            if user_info["group"] != "super_admin":
                return (
                    False,
                    jsonify({"success": False, "message": "仅超级管理员可执行此操作"}),
                    403,
                )
        if required_permission:
            if not auth_system.check_permission(
                user_info["username"], required_permission
            ):
                return (
                    False,
                    jsonify(
                        {
                            "success": False,
                            "message": f"权限不足：需要 {required_permission} 权限",
                        }
                    ),
                    403,
                )
        return True, user_info, 200

    @app.route("/auth/register", methods=["POST"])
    def auth_register():
        """
        用户注册API端点（已升级支持手机号、昵称、头像）。
        """
        try:
            # [修正] 使用 strict=False 允许重复项，optionxform=str 保持大小写敏感
            config = configparser.ConfigParser(strict=False)
            config.optionxform = str
            if os.path.exists(CONFIG_FILE):
                config.read(CONFIG_FILE, encoding="utf-8")
            content_type = request.headers.get("Content-Type", "").lower()

            if "application/json" in content_type:
                data = request.get_json() or {}
            else:
                data = request.form.to_dict()
            auth_username = data.get("auth_username", "").strip()
            auth_password = data.get("auth_password", "").strip()
            phone = data.get("phone", "").strip()
            nickname = data.get("nickname", "").strip()
            sms_code = data.get("sms_code", "").strip()
            captcha_input = data.get("captcha", "").strip()
            captcha_id = data.get("captcha_id", "").strip()
            is_captcha_valid, captcha_error_msg = verify_captcha(
                captcha_id, captcha_input
            )
            if not is_captcha_valid:
                return jsonify({"success": False, "message": captcha_error_msg})
            if not auth_username or not auth_password:
                return jsonify({"success": False, "message": "用户名和密码不能为空"})
            if re.search(r"[\u4e00-\u9fff]", auth_username):
                return jsonify({"success": False, "message": "用户名不能包含中文字符"})
            if phone and not re.match(r"^1[3-9]\d{9}$", phone):
                return jsonify({"success": False, "message": "手机号格式不正确"})
            if (
                config.get(
                    "Features", "enable_phone_registration_verify", fallback="false"
                ).lower()
                == "true"
            ):
                if not phone:
                    return jsonify({"success": False, "message": "注册需要填写手机号"})
                if not sms_code:
                    return jsonify({"success": False, "message": "请输入短信验证码"})
                code_verified = False
                if phone in sms_verification_codes:
                    stored_code, expires_at = sms_verification_codes[phone]

                    if time.time() > expires_at:
                        del sms_verification_codes[phone]
                        return jsonify(
                            {"success": False, "message": "验证码已过期，请重新获取"}
                        )

                    if stored_code == sms_code:
                        code_verified = True
                        del sms_verification_codes[phone]

                if not code_verified:
                    return jsonify({"success": False, "message": "验证码错误或已过期"})
            avatar_url = "default_avatar.png"
            avatar_file = request.files.get("avatar")
            avatar_sha256_hash = None

            if avatar_file and avatar_file.filename:
                allowed_extensions = {"png", "jpg", "jpeg", "gif", "webp"}
                file_ext = avatar_file.filename.rsplit(".", 1)[-1].lower()
                if file_ext not in allowed_extensions:
                    return jsonify(
                        {
                            "success": False,
                            "message": "头像文件格式不支持，请使用png/jpg/gif",
                        }
                    )

                file_content = avatar_file.read()
                max_size = 5 * 1024 * 1024
                if len(file_content) > max_size:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": "文件过大，请上传小于5MB的图片",
                            }
                        ),
                        400,
                    )

                try:
                    img = Image.open(io.BytesIO(file_content))
                    if img.mode in ("RGBA", "LA", "P"):
                        pass
                    elif img.mode != "RGB":
                        img = img.convert("RGB")
                    png_buffer = io.BytesIO()
                    img.save(png_buffer, format="PNG", optimize=True)
                    png_content = png_buffer.getvalue()
                    avatar_sha256_hash = hashlib.sha256(png_content).hexdigest()
                    images_dir = os.path.join("system_accounts", "images")
                    os.makedirs(images_dir, exist_ok=True)
                    filename = f"{avatar_sha256_hash}.png"
                    filepath = os.path.join(images_dir, filename)

                    with open(filepath, "wb") as f:
                        f.write(png_content)
                    index_file = os.path.join(images_dir, "_index.json")
                    try:
                        if os.path.exists(index_file):
                            with open(index_file, "r", encoding="utf-8") as f:
                                index_data = json.load(f)
                        else:
                            index_data = {
                                "version": "1.0",
                                "description": "用户头像索引文件",
                                "files": {},
                            }

                        ip_address = request.headers.get(
                            "X-Forwarded-For", request.remote_addr
                        )
                        index_data["files"][filename] = {
                            "username": "Guest",
                            "upload_time": time.time(),
                            "upload_time_str": datetime.datetime.now().isoformat(),
                            "ip_address": ip_address,
                            "original_filename": avatar_file.filename,
                            "file_size": len(png_content),
                            "sha256": avatar_sha256_hash,
                        }

                        with open(index_file, "w", encoding="utf-8") as f:
                            json.dump(index_data, f, indent=2, ensure_ascii=False)

                        logging.info(
                            f"访客 (注册前) 从 {ip_address} 上传头像: {filename}"
                        )
                    except Exception as e:
                        logging.error(f"注册时更新头像索引失败: {e}", exc_info=True)
                    avatar_url = f"/api/avatar/{filename}"

                except Exception as e:
                    logging.error(f"注册时处理头像失败: {e}", exc_info=True)
                    return (
                        jsonify(
                            {"success": False, "message": f"图片处理失败: {str(e)}"}
                        ),
                        500,
                    )
            result = auth_system.register_user(
                auth_username,
                auth_password,
                phone=phone,
                nickname=nickname or auth_username,
                avatar_url=avatar_url,
            )
            if result.get("success") and avatar_sha256_hash:
                try:
                    images_dir = os.path.join("system_accounts", "images")
                    index_file = os.path.join(images_dir, "_index.json")
                    filename = f"{avatar_sha256_hash}.png"

                    if os.path.exists(index_file):
                        with auth_system.lock:
                            with open(index_file, "r", encoding="utf-8") as f:
                                index_data = json.load(f)
                            if (
                                filename in index_data.get("files", {})
                                and index_data["files"][filename].get("username")
                                == "Guest"
                            ):
                                index_data["files"][filename][
                                    "username"
                                ] = auth_username

                                with open(index_file, "w", encoding="utf-8") as f:
                                    json.dump(
                                        index_data, f, indent=2, ensure_ascii=False
                                    )

                                logging.info(
                                    f"头像索引已更新：文件 {filename} 的所有者已从 'Guest' 更新为 '{auth_username}'"
                                )
                            else:
                                logging.warning(
                                    f"注册后尝试更新头像索引：未找到匹配的 'Guest' 条目 (文件: {filename})"
                                )
                except Exception as e:
                    logging.error(f"注册成功后更新头像索引失败: {e}", exc_info=True)

            return jsonify(result)

        except Exception as e:
            app.logger.error(f"[注册] 处理异常：{str(e)}")
            return jsonify({"success": False, "message": "注册失败，请稍后重试"})

    @app.route("/auth/login", methods=["POST"])
    def auth_login():
        """
        用户登录认证API端点。
        """
        global config
        # [修正] 使用 strict=False 允许重复项，optionxform=str 保持大小写敏感
        config = configparser.ConfigParser(strict=False)
        config.optionxform = str
        config.read(CONFIG_FILE, encoding="utf-8")

        data = request.get_json() or {}
        auth_phone = data.get("auth_phone", "").strip()
        auth_username = data.get("auth_username", "").strip()
        auth_password = data.get("auth_password", "").strip()
        sms_code = data.get("auth_sms_code", "").strip()
        two_fa_code = data.get("two_fa_code", "").strip()
        captcha_input = data.get("captcha", "").strip()
        captcha_id = data.get("captcha_id", "").strip()
        is_captcha_valid, captcha_error_msg = verify_captcha(captcha_id, captcha_input)
        if not is_captcha_valid:
            return jsonify({"success": False, "message": captcha_error_msg})

        session_id = request.headers.get("X-Session-ID", "")
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
        user_agent = request.headers.get("User-Agent", "")
        auth_result = None
        target_username = None
        if auth_phone and sms_code:
            target_username = auth_system.find_user_by_phone(auth_phone)
            if not target_username:
                return jsonify({"success": False, "message": "该手机号未注册"})

            logging.info(f"[登录] 模式: 手机号/验证码 (用户: {target_username})")

            if (
                config.get("Features", "enable_phone_login", fallback="false").lower()
                != "true"
            ):
                return jsonify({"success": False, "message": "手机号登录功能未启用"})
            if (
                config.get("Features", "enable_sms_service", fallback="false").lower()
                != "true"
            ):
                return jsonify({"success": False, "message": "短信服务未启用"})
            global sms_verification_codes
            stored_code_info = sms_verification_codes.get(auth_phone)
            if not stored_code_info:
                return jsonify({"success": False, "message": "请先获取验证码"})

            code_value, expires_at = stored_code_info
            if time.time() > expires_at:
                del sms_verification_codes[auth_phone]
                return jsonify(
                    {"success": False, "message": "验证码已过期，请重新获取"}
                )

            if code_value != sms_code:
                return jsonify({"success": False, "message": "验证码错误"})
            del sms_verification_codes[auth_phone]
            user_file = auth_system.get_user_file_path(target_username)
            if os.path.exists(user_file):
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)

                if user_data.get("2fa_enabled", False):
                    if not two_fa_code:
                        return jsonify(
                            {
                                "success": True,
                                "message": "需要2FA验证码",
                                "requires_2fa": True,
                                "auth_username": target_username,
                            }
                        )
                    if not auth_system.verify_2fa(target_username, two_fa_code):
                        auth_system._log_login_attempt(
                            target_username, False, ip_address, user_agent, "2fa_failed"
                        )
                        return jsonify({"success": False, "message": "2FA验证码错误"})
            auth_result = {
                "success": True,
                "auth_username": target_username,
                "group": auth_system.get_user_group(target_username),
                "is_guest": False,
                "message": "登录成功",
            }
            auth_system._log_login_attempt(
                target_username, True, ip_address, user_agent, "SMS code login"
            )
        elif auth_phone and auth_password:
            target_username = auth_system.find_user_by_phone(auth_phone)
            if not target_username:
                return jsonify({"success": False, "message": "该手机号未注册"})

            logging.info(f"[登录] 模式: 手机号/密码 (用户: {target_username})")

            if (
                config.get("Features", "enable_phone_login", fallback="false").lower()
                != "true"
            ):
                return jsonify({"success": False, "message": "手机号登录功能未启用"})
            auth_result = auth_system.authenticate(
                target_username, auth_password, ip_address, user_agent, two_fa_code
            )
        elif auth_username and auth_password:
            target_username = auth_username
            logging.info(f"[登录] 模式: 用户名/密码 (用户: {target_username})")
            auth_result = auth_system.authenticate(
                target_username, auth_password, ip_address, user_agent, two_fa_code
            )
        elif auth_username == "guest" and not auth_password:
            logging.info(f"[登录] 模式: 游客")
            auth_result = auth_system.authenticate(
                auth_username, auth_password, ip_address, user_agent, two_fa_code
            )

        else:
            return jsonify({"success": False, "message": "无效的登录凭据"})

        if not auth_result:
            return jsonify({"success": False, "message": "认证时发生未知错误"})
        if auth_result.get("requires_2fa"):
            return jsonify(auth_result)
        if not auth_result.get("success"):
            return jsonify(auth_result)
        with web_sessions_lock:
            if session_id in web_sessions:
                api_instance = web_sessions[session_id]
            else:
                api_instance = Api(args)
                api_instance._session_created_at = time.time()
                api_instance._web_session_id = session_id
                web_sessions[session_id] = api_instance

            api_instance.auth_username = auth_result["auth_username"]
            api_instance.auth_group = auth_result["group"]
            api_instance.is_guest = auth_result.get("is_guest", False)
            api_instance.is_authenticated = True
            cleanup_message = ""
            if not auth_result.get("is_guest", False):
                try:
                    old_sessions, cleanup_message = (
                        auth_system.check_single_session_enforcement(
                            auth_username, session_id
                        )
                    )
                    if old_sessions:

                        def cleanup_old_sessions_async():
                            for old_sid in old_sessions:
                                try:
                                    cleanup_session(old_sid, "session_limit_exceeded")
                                except Exception as e:
                                    logging.error(
                                        f"后台清理旧会话失败 {old_sid[:16]}...: {e}"
                                    )

                        cleanup_thread = threading.Thread(
                            target=cleanup_old_sessions_async, daemon=True
                        )
                        cleanup_thread.start()
                    auth_system.link_session_to_user(auth_username, session_id)
                    if session_id == "" or session_id is None or session_id == "null":
                        audit_details = f"登录成功"
                    else:
                        audit_details = f"登录成功，会话ID: {session_id}"
                    if cleanup_message:
                        audit_details += f"; {cleanup_message}"

                    auth_system.log_audit(
                        auth_username,
                        "user_login",
                        audit_details,
                        ip_address,
                        session_id,
                    )
                except Exception as e:
                    logging.error(f"会话管理过程出错，但继续登录流程: {e}")
                    cleanup_message = ""

            try:
                save_session_state(session_id, api_instance, force_save=True)
            except Exception as e:
                logging.error(f"保存会话状态失败: {e}")
        user_sessions = []
        max_sessions = 1
        if not auth_result.get("is_guest", False):
            try:
                user_sessions = auth_system.get_user_sessions(auth_username)
                user_details = auth_system.get_user_details(auth_username)
                if user_details:
                    max_sessions = user_details.get("max_sessions", 1)
            except Exception as e:
                logging.error(f"获取用户会话信息失败: {e}")
                user_sessions = []
                max_sessions = 1
        session_limit_info = ""
        if max_sessions == 1:
            session_limit_info = "您的账号为单会话模式，新登录将自动清理所有旧会话"
        elif max_sessions == -1:
            session_limit_info = "您的账号为无限会话模式，可以创建任意数量的会话"
        else:
            session_limit_info = f"您的账号最多可以同时保持{max_sessions}个活跃会话，超出时将自动清理最旧的会话"
        token = None
        kicked_sessions = []
        if not auth_result.get("is_guest", False) and session_id:
            try:
                token = token_manager.create_token(auth_username, session_id)
                kicked_sessions = token_manager.detect_multi_device_login(
                    auth_username, session_id
                )
                token_manager.cleanup_expired_tokens(auth_username)
                if kicked_sessions:
                    for old_sid in kicked_sessions:
                        token_manager.invalidate_token(auth_username, old_sid)
                    logging.info(
                        f"用户 {auth_username} 从新设备登录，检测到 {len(kicked_sessions)} 个其他活跃会话。"
                    )
            except Exception as e:
                logging.error(f"Token管理过程出错，但继续登录流程: {e}")
                token = None
                kicked_sessions = []

        try:
            response_data = {
                "success": True,
                "session_id": session_id,
                "auth_username": auth_result["auth_username"],
                "group": auth_result["group"],
                "is_guest": auth_result.get("is_guest", False),
                "user_sessions": user_sessions,
                "max_sessions": max_sessions,
                "session_limit_info": session_limit_info,
                "avatar_url": auth_result.get("avatar_url", ""),
                "theme": auth_result.get("theme", "light"),
                "token": token,
                "kicked_sessions_count": len(kicked_sessions),
            }
            if cleanup_message:
                response_data["cleanup_message"] = cleanup_message
            if kicked_sessions:
                response_data["multi_device_warning"] = (
                    f"检测到该账号在其他 {len(kicked_sessions)} 个设备上登录，已自动登出旧设备"
                )
            response = jsonify(response_data)
            if token:
                response.set_cookie(
                    "auth_token",
                    value=token,
                    max_age=3600,
                    httponly=True,
                    secure=False,
                    samesite="Lax",
                )

            return response
        except Exception as e:
            logging.error(f"创建登录响应失败: {e}")
            return jsonify(
                {
                    "success": True,
                    "session_id": session_id,
                    "auth_username": auth_result.get("auth_username", auth_username),
                    "group": auth_result.get("group", "user"),
                    "is_guest": False,
                }
            )

    @app.route("/auth/guest_login", methods=["POST"])
    def auth_guest_login():
        """
        游客登录API - 无需密码的快速访问入口。
        """
        session_id = request.headers.get("X-Session-ID", "")

        if not session_id:
            return jsonify({"success": False, "message": "缺少会话ID"})
        update_session_activity(session_id)
        if not auth_system.config.getboolean(
            "Guest", "allow_guest_login", fallback=True
        ):
            return jsonify({"success": False, "message": "系统不允许游客登录"})
        with web_sessions_lock:
            if session_id in web_sessions:
                api_instance = web_sessions[session_id]
            else:
                api_instance = Api(args)
                api_instance._session_created_at = time.time()
                api_instance._web_session_id = session_id
                web_sessions[session_id] = api_instance

            api_instance.auth_username = "guest"
            api_instance.auth_group = "guest"
            api_instance.is_guest = True
            api_instance.is_authenticated = True

            save_session_state(session_id, api_instance, force_save=True)

        return jsonify(
            {
                "success": True,
                "auth_username": "guest",
                "group": "guest",
                "is_guest": True,
            }
        )

    @app.route("/auth/logout", methods=["POST"])
    def auth_logout():
        """
        安全退出系统并清理所有会话数据。
        """
        session_id = request.headers.get("X-Session-ID", "")

        if not session_id:
            return jsonify({"success": False, "message": "缺少会话ID"}), 400

        username = None
        with web_sessions_lock:
            if session_id in web_sessions:
                api_instance = web_sessions[session_id]
                if hasattr(api_instance, "auth_username"):
                    username = api_instance.auth_username
                    is_guest = getattr(api_instance, "is_guest", True)
                    if not is_guest and username:
                        token_manager.invalidate_token(username, session_id)
                        logging.info(
                            f"用户 {username} 登出，session: {session_id[:16]}..."
                        )
        cleanup_session(session_id, "user_logout")
        response = jsonify({"success": True, "message": "登出成功"})
        response.set_cookie("auth_token", "", max_age=0)

        return response

    @app.route("/auth/check_permission", methods=["POST"])
    def auth_check_permission():
        """
        权限检查API - 验证用户是否拥有特定权限。
        """
        session_id = request.headers.get("X-Session-ID", "")
        data = request.get_json() or {}
        permission = data.get("permission", "")
        success, result, status_code = get_session_user_safe(session_id)
        if not success:
            return jsonify({"success": False, "has_permission": False})
        auth_username = result["username"]
        has_permission = auth_system.check_permission(auth_username, permission)
        return jsonify({"success": True, "has_permission": has_permission})

    @app.route("/auth/switch_session", methods=["POST"])
    def auth_switch_session():
        """
        会话切换API - 在多标签页间切换时更新认证token和cookie。
        """
        current_session_id = request.headers.get("X-Session-ID", "")
        data = request.get_json() or {}
        target_session_id = data.get("target_session_id", "")

        if not current_session_id or not target_session_id:
            return jsonify({"success": False, "message": "缺少会话ID参数"}), 400
        username = None
        is_guest = True
        auth_username = ""
        with web_sessions_lock:
            if current_session_id in web_sessions:
                api_instance = web_sessions[current_session_id]
                if getattr(api_instance, "is_authenticated", False):
                    username = getattr(api_instance, "auth_username", None)
                    is_guest = getattr(api_instance, "is_guest", True)

        if not username or is_guest:
            return (
                jsonify(
                    {"success": False, "message": "用户未登录或为游客，无法切换会话"}
                ),
                401,
            )
        token_from_cookie = request.cookies.get("auth_token")
        if not token_from_cookie:
            return jsonify({"success": False, "message": "缺少认证令牌(cookie)"}), 401

        is_valid, reason = token_manager.verify_token(
            username, current_session_id, token_from_cookie
        )
        if not is_valid:
            logging.warning(
                f"切换会话失败：用户 {username} 的当前会话 {current_session_id[:8]} token 无效 ({reason})"
            )
            response_data = {
                "success": False,
                "message": f"当前认证已失效({reason})，请重新登录",
                "need_login": True,
            }
            response = make_response(jsonify(response_data), 401)
            response.set_cookie("auth_token", "", max_age=0)
            return response
        new_token_for_target = token_manager.create_token(username, target_session_id)
        logging.info(
            f"用户 {username} 切换会话：为目标会话 {target_session_id[:8]} 生成新 token"
        )
        response_data = {"success": True, "message": "Token已更新，可以跳转"}
        response = make_response(jsonify(response_data))
        response.set_cookie(
            "auth_token",
            value=new_token_for_target,
            max_age=3600,
            httponly=True,
            secure=False,
            samesite="Lax",
        )
        with web_sessions_lock:
            if target_session_id not in web_sessions:
                state = load_session_state(target_session_id)
                if state:
                    target_api_instance = Api(args)
                    target_api_instance._web_session_id = target_session_id
                    restore_session_to_api_instance(target_api_instance, state)
                    web_sessions[target_session_id] = target_api_instance
                    logging.info(
                        f"切换会话时，预加载目标会话 {target_session_id[:8]} 状态成功"
                    )
                else:
                    logging.warning(
                        f"切换会话时，目标会话 {target_session_id[:8]} 状态文件不存在或加载失败，将在访问时创建"
                    )

        return response

    @app.route("/auth/admin/list_users", methods=["GET"])
    def auth_admin_list_users():
        """
        列出所有用户信息。
        """
        session_id = request.headers.get("X-Session-ID", "")
        with web_sessions_lock:
            if not session_id or session_id not in web_sessions:
                return jsonify({"success": False, "message": "未授权"})
            api_instance = web_sessions[session_id]
            if not hasattr(api_instance, "auth_username"):
                return jsonify({"success": False, "message": "未登录"})
            auth_username = api_instance.auth_username
        if not auth_system.check_permission(auth_username, "manage_users"):
            return jsonify({"success": False, "message": "权限不足"})
        users = auth_system.list_users()
        return jsonify({"success": True, "users": users})

    @app.route("/auth/admin/update_user_group", methods=["POST"])
    def auth_admin_update_user_group():
        """
        修改用户所属的权限组。
        """
        session_id = request.headers.get("X-Session-ID", "")
        data = request.get_json() or {}
        target_username = data.get("target_username", "")
        new_group = data.get("new_group", "")

        if new_group == "super_admin":
            return jsonify({"success": False, "message": "不允许分配超级管理员组"})

        super_admin = auth_system.config.get("Admin", "super_admin", fallback="admin")
        if target_username == super_admin:
            return jsonify(
                {"success": False, "message": "不允许修改超级管理员用户组的用户"}
            )
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未授权"})
        with web_sessions_lock:
            api_instance = web_sessions[session_id]
            if not hasattr(api_instance, "auth_username"):
                return jsonify({"success": False, "message": "未登录"})
            auth_username = api_instance.auth_username
        if not auth_system.check_permission(auth_username, "manage_users"):
            return jsonify({"success": False, "message": "权限不足"})
        result = auth_system.update_user_group(target_username, new_group)
        return jsonify(result)

    @app.route("/auth/admin/list_groups", methods=["GET"])
    def auth_admin_list_groups():
        """
        管理员API - 列出所有权限组及其权限配置。
        """
        session_id = request.headers.get("X-Session-ID", "")
        with web_sessions_lock:
            if not session_id or session_id not in web_sessions:
                return jsonify({"success": False, "message": "未授权"})
            api_instance = web_sessions[session_id]
            if not hasattr(api_instance, "auth_username"):
                return jsonify({"success": False, "message": "未登录"})
            auth_username = api_instance.auth_username
        if not auth_system.check_permission(auth_username, "manage_permissions"):
            return jsonify({"success": False, "message": "权限不足"})
        raw_groups = auth_system.get_all_groups()
        groups = copy.deepcopy(raw_groups)
        all_permission_keys = set()
        for g_data in groups.values():
            perms = g_data.get("permissions", {})
            all_permission_keys.update(perms.keys())
        for g_key, g_data in groups.items():
            if "permissions" not in g_data:
                g_data["permissions"] = {}

            current_perms = g_data["permissions"]
            for key in all_permission_keys:
                if key not in current_perms:
                    current_perms[key] = False

        return jsonify({"success": True, "groups": groups})

    @app.route("/auth/admin/create_group", methods=["POST"])
    def auth_admin_create_group():
        """创建权限组"""
        session_id = request.headers.get("X-Session-ID", "")
        data = request.get_json() or {}
        group_name = data.get("group_name", "").strip()
        display_name = data.get("display_name", "").strip()
        permissions = data.get("permissions", {})
        with web_sessions_lock:
            if not session_id or session_id not in web_sessions:
                return jsonify({"success": False, "message": "未授权"})
            api_instance = web_sessions[session_id]
            if not hasattr(api_instance, "auth_username"):
                return jsonify({"success": False, "message": "未登录"})
            if api_instance.auth_group != "super_admin":
                return jsonify(
                    {"success": False, "message": "仅超级管理员可创建权限组"}
                )
        if not group_name:
            return jsonify(
                {"success": False, "message": "权限组标识（group_name）不能为空"}
            )

        if not display_name:
            return jsonify(
                {"success": False, "message": "权限组名称（display_name）不能为空"}
            )
        result = auth_system.create_permission_group(
            group_name, permissions, display_name
        )
        return jsonify(result)

    @app.route("/auth/admin/update_group", methods=["POST"])
    def auth_admin_update_group():
        """更新权限组（支持group_key和group_name参数）"""
        session_id = request.headers.get("X-Session-ID", "")
        data = request.get_json() or {}
        group_name = data.get("group_key") or data.get("group_name", "")
        permissions = data.get("permissions", {})
        if group_name == "super_admin":
            return jsonify({"success": False, "message": "不允许修改超级管理员组"})
        with web_sessions_lock:
            if not session_id or session_id not in web_sessions:
                return jsonify({"success": False, "message": "未授权"})
            api_instance = web_sessions[session_id]
            if not hasattr(api_instance, "auth_username"):
                return jsonify({"success": False, "message": "未登录"})
            if api_instance.auth_group != "super_admin":
                return jsonify(
                    {"success": False, "message": "仅超级管理员可更新权限组"}
                )
        if not group_name:
            return jsonify({"success": False, "message": "权限组标识不能为空"})
        result = auth_system.update_permission_group(group_name, permissions)
        if not result.get("success", False):
            if "不存在" in result.get("message", ""):
                return jsonify(
                    {"success": False, "message": f"权限组 '{group_name}' 不存在"}
                )

        return jsonify(result)

    @app.route("/auth/admin/delete_group", methods=["POST"])
    def auth_admin_delete_group():
        """超级管理员：删除权限组"""
        session_id = request.headers.get("X-Session-ID", "")
        data = request.get_json() or {}
        group_name = data.get("group_name", "")

        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未授权"})

        api_instance = web_sessions[session_id]
        if not hasattr(api_instance, "auth_username"):
            return jsonify({"success": False, "message": "未登录"})
        if api_instance.auth_group != "super_admin":
            return jsonify({"success": False, "message": "仅超级管理员可删除权限组"})

        result = auth_system.delete_permission_group(group_name)
        return jsonify(result)

    @app.route("/auth/admin/get_user_permissions", methods=["POST"])
    def auth_admin_get_user_permissions():
        """管理员：获取用户的完整权限列表"""
        session_id = request.headers.get("X-Session-ID", "")
        data = request.get_json() or {}
        target_username = data.get("username", "")

        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未授权"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "manage_permissions"):
            return jsonify({"success": False, "message": "权限不足"}), 403

        user_current_permissions = auth_system.get_user_permissions(target_username)

        all_possible_keys = set()
        super_admin_perms = (
            auth_system.permissions["permission_groups"]
            .get("super_admin", {})
            .get("permissions", {})
        )
        all_possible_keys.update(super_admin_perms.keys())
        for g_data in auth_system.permissions["permission_groups"].values():
            all_possible_keys.update(g_data.get("permissions", {}).keys())

        all_permissions = {}
        for key in all_possible_keys:
            all_permissions[key] = user_current_permissions.get(key, False)

        group = auth_system.get_user_group(target_username)
        group_permissions = (
            auth_system.permissions["permission_groups"]
            .get(group, {})
            .get("permissions", {})
        )
        user_custom = auth_system.permissions.get("user_custom_permissions", {}).get(
            target_username, {}
        )
        added_list = user_custom.get("added", [])
        removed_list = user_custom.get("removed", [])
        added_permissions = {perm: True for perm in added_list}
        removed_permissions = {perm: True for perm in removed_list}

        return jsonify(
            {
                "success": True,
                "group": group,
                "all_permissions": all_permissions,
                "group_permissions": group_permissions,
                "added_permissions": added_permissions,
                "removed_permissions": removed_permissions,
            }
        )

    @app.route("/auth/admin/set_user_permission", methods=["POST"])
    def auth_admin_set_user_permission():
        """管理员：为用户设置自定义权限（差分化存储）"""
        session_id = request.headers.get("X-Session-ID", "")
        data = request.get_json() or {}
        target_username = data.get("username", "")

        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未授权"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "manage_permissions"):
            return jsonify({"success": False, "message": "权限不足"}), 403
        added_permissions = data.get("added_permissions", {})
        removed_permissions = data.get("removed_permissions", {})

        if added_permissions or removed_permissions:
            try:
                if "user_custom_permissions" not in auth_system.permissions:
                    auth_system.permissions["user_custom_permissions"] = {}

                auth_system.permissions["user_custom_permissions"][target_username] = {
                    "added": list(added_permissions.keys()),
                    "removed": list(removed_permissions.keys()),
                }

                auth_system._save_permissions()
                ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
                auth_system.log_audit(
                    auth_username,
                    "set_user_permissions_batch",
                    f"批量更新用户 {target_username} 的差分权限: 添加{len(added_permissions)}个, 移除{len(removed_permissions)}个",
                    ip_address,
                    session_id,
                )

                return jsonify({"success": True, "message": "权限已更新"})
            except Exception as e:
                logging.error(f"批量更新权限失败: {e}", exc_info=True)
                return (
                    jsonify({"success": False, "message": f"更新失败: {str(e)}"}),
                    500,
                )
        else:
            permission = data.get("permission", "")
            grant = data.get("grant", False)

            if not permission:
                logging.info(
                    f"管理员 {auth_username} 尝试为用户 {target_username} 设置权限时，缺少 permission 参数"
                )
                try:
                    if "user_custom_permissions" not in auth_system.permissions:
                        auth_system.permissions["user_custom_permissions"] = {}

                    auth_system.permissions["user_custom_permissions"][
                        target_username
                    ] = {"added": [], "removed": []}

                    auth_system._save_permissions()

                    ip_address = request.headers.get(
                        "X-Forwarded-For", request.remote_addr
                    )
                    auth_system.log_audit(
                        auth_username,
                        "set_user_permissions_batch",
                        f"批量更新用户 {target_username} 的差分权限: 清空用户的差分权限",
                        ip_address,
                        session_id,
                    )

                    return jsonify({"success": True, "message": "权限已更新"})
                except Exception as e:
                    logging.error(f"批量更新权限失败: {e}", exc_info=True)
                    return (
                        jsonify({"success": False, "message": f"更新失败: {str(e)}"}),
                        500,
                    )

            result = auth_system.set_user_custom_permission(
                target_username, permission, grant
            )

            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            auth_system.log_audit(
                auth_username,
                "set_user_permission",
                f'为用户 {target_username} {"授予" if grant else "移除"} 权限: {permission}',
                ip_address,
                session_id,
            )

            return jsonify(result)

    @app.route("/auth/get_config", methods=["GET"])
    def auth_get_config():
        """
        获取认证配置（用于前端显示）
        使用 _get_config_value 辅助函数安全地读取配置，避免 ValueError 崩溃
        """
        allow_guest_login = _get_config_value(
            auth_system.config,
            "Guest",
            "allow_guest_login",
            type_func=lambda x: str(x).lower() in ("true", "yes", "1", "on"),
            fallback=True,
        )
        amap_js_key = _get_config_value(
            auth_system.config,
            "Map",
            "amap_js_key",
            type_func=str,
            fallback="",
        )

        return jsonify(
            {
                "success": True,
                "allow_guest_login": allow_guest_login,
                "amap_js_key": amap_js_key,
            }
        )

    @app.route("/auth/check_uuid_type", methods=["POST"])
    def auth_check_uuid_type():
        """
        检查UUID类型：游客UUID、系统账号UUID或未知UUID
        用于实现访问控制和会话验证
        """
        data = request.json
        check_uuid = data.get("uuid", "")

        if not check_uuid:
            return jsonify({"success": False, "message": "UUID参数缺失"}), 400
        uuid_pattern = re.compile(
            r"^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$",
            re.IGNORECASE,
        )
        if not uuid_pattern.match(check_uuid):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "无效的UUID格式，请使用标准UUID v4格式",
                    }
                ),
                400,
            )
        session_file = get_session_file_path(check_uuid)
        file_exists = os.path.exists(session_file)
        logging.debug(
            # f"/auth/check_uuid_type: Checking UUID {check_uuid[:8]}..., File path: {session_file}, Exists: {file_exists}"
            f"正在检查UUID {check_uuid[:8]}...，文件路径: {session_file}，存在: {file_exists}"
        )

        if not file_exists:
            return jsonify(
                {
                    "success": True,
                    "uuid_type": "unknown",
                    "message": "UUID不存在 (文件未找到)",
                }
            )
        max_retries = 3
        retry_delay = 0.1
        fcntl = None

        for attempt in range(max_retries):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    if fcntl:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    try:
                        session_data = json.load(f)
                    finally:
                        if fcntl:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                is_guest = session_data.get("is_guest", False)
                auth_username = session_data.get("auth_username", "")

                if is_guest or auth_username == "guest":
                    return jsonify(
                        {"success": True, "uuid_type": "guest", "message": "游客UUID"}
                    )
                elif auth_username:
                    return jsonify(
                        {
                            "success": True,
                            "uuid_type": "system_account",
                            "auth_username": auth_username,
                            "message": "系统账号UUID",
                        }
                    )
                else:
                    logging.warning(
                        f"/auth/check_uuid_type: 文件 {session_file} 存在但内容无法识别用户类型 (auth_username='{auth_username}', is_guest={is_guest})，返回 unknown"
                    )
                    return jsonify(
                        {
                            "success": True,
                            "uuid_type": "unknown",
                            "message": "未知类型UUID (内容无法识别)",
                        }
                    )
            except (IOError, OSError) as e:
                if attempt < max_retries - 1:

                    time.sleep(retry_delay)
                    continue
                else:
                    logging.error(f"读取会话文件失败（已重试{max_retries}次）: {e}")
                    return (
                        jsonify(
                            {"success": False, "message": "读取会话失败，请稍后重试"}
                        ),
                        500,
                    )
            except json.JSONDecodeError as e:
                logging.error(f"会话文件JSON解析失败: {e}")
                return jsonify({"success": False, "message": "会话数据损坏"}), 500
            except Exception as e:
                logging.error(f"检查UUID类型失败: {e}")
                return (
                    jsonify({"success": False, "message": f"服务器错误: {str(e)}"}),
                    500,
                )

    @app.route("/auth/2fa/generate", methods=["POST"])
    def auth_2fa_generate():
        """生成2FA密钥"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        if not getattr(api_instance, "is_authenticated", False):
            return jsonify({"success": False, "message": "未认证"}), 401

        auth_username = getattr(api_instance, "auth_username", "")
        if auth_username == "guest":
            return jsonify({"success": False, "message": "游客不支持2FA"}), 403

        result = auth_system.generate_2fa_secret(auth_username)
        return jsonify(result)

    @app.route("/auth/2fa/enable", methods=["POST"])
    def auth_2fa_enable():
        """启用2FA"""
        data = request.get_json() or {}
        verification_code = data.get("code", "").strip()
        session_id = request.headers.get("X-Session-ID", "")

        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        if not getattr(api_instance, "is_authenticated", False):
            return jsonify({"success": False, "message": "未认证"}), 401

        auth_username = getattr(api_instance, "auth_username", "")
        result = auth_system.enable_2fa(auth_username, verification_code)
        return jsonify(result)

    @app.route("/auth/2fa/verify", methods=["POST"])
    def auth_2fa_verify():
        """测试验证2FA代码（用于用户测试2FA是否工作正常）"""
        data = request.get_json() or {}
        verification_code = data.get("code", "").strip()
        session_id = request.headers.get("X-Session-ID", "")

        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        if not getattr(api_instance, "is_authenticated", False):
            return jsonify({"success": False, "message": "未认证"}), 401

        auth_username = getattr(api_instance, "auth_username", "")
        if auth_username == "guest":
            return jsonify({"success": False, "message": "游客不支持2FA"}), 403
        if auth_system.verify_2fa(auth_username, verification_code):
            return jsonify({"success": True, "message": "验证码正确"})
        else:
            return jsonify({"success": False, "message": "验证码错误"})

    @app.route("/auth/2fa/disable", methods=["POST"])
    def auth_2fa_disable():
        """关闭2FA"""
        session_id = request.headers.get("X-Session-ID", "")

        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        if not getattr(api_instance, "is_authenticated", False):
            return jsonify({"success": False, "message": "未认证"}), 401

        auth_username = getattr(api_instance, "auth_username", "")
        if auth_username == "guest":
            return jsonify({"success": False, "message": "游客不支持2FA"}), 403
        user_file = auth_system.get_user_file_path(auth_username)
        if os.path.exists(user_file):
            try:
                with auth_system.lock:
                    with open(user_file, "r", encoding="utf-8") as f:
                        user_data = json.load(f)

                    user_data["2fa_enabled"] = False
                    with open(user_file, "w", encoding="utf-8") as f:
                        json.dump(user_data, f, indent=2, ensure_ascii=False)

                logging.info(f"用户 {auth_username} 已关闭2FA")
                return jsonify({"success": True, "message": "2FA已关闭"})
            except Exception as e:
                logging.error(f"关闭2FA失败: {e}", exc_info=True)
                return (
                    jsonify({"success": False, "message": f"关闭失败: {str(e)}"}),
                    500,
                )
        else:
            return jsonify({"success": False, "message": "用户不存在"}), 404

    @app.route("/auth/2fa/verify_login", methods=["POST"])
    def auth_2fa_verify_login():
        """验证2FA代码并完成登录（用于登录流程中的2FA验证）"""
        data = request.get_json() or {}
        auth_username = data.get("auth_username", "").strip()
        verification_code = data.get("code", "").strip()

        if not auth_username:
            return jsonify({"success": False, "message": "缺少用户名"}), 400

        if not verification_code:
            return jsonify({"success": False, "message": "缺少验证码"}), 400
        if not auth_system.verify_2fa(auth_username, verification_code):
            logging.warning(f"2FA登录验证失败: {auth_username}")
            return jsonify({"success": False, "message": "验证码错误"})
        session_id = str(uuid.uuid4())
        api_instance = Api(args)
        api_instance._session_created_at = time.time()
        api_instance._web_session_id = session_id
        api_instance.is_authenticated = True
        api_instance.auth_username = auth_username
        user_group = auth_system.get_user_group(auth_username)
        api_instance.auth_group = user_group
        is_guest = auth_username == "guest"
        api_instance.is_guest = is_guest
        web_sessions[session_id] = api_instance
        user_file = auth_system.get_user_file_path(auth_username)
        if os.path.exists(user_file):
            try:
                with auth_system.lock:
                    with open(user_file, "r", encoding="utf-8") as f:
                        user_data = json.load(f)

                    user_data["last_login"] = time.time()
                    if "session_ids" not in user_data:
                        user_data["session_ids"] = []
                    if session_id not in user_data["session_ids"]:
                        user_data["session_ids"].append(session_id)

                    with open(user_file, "w", encoding="utf-8") as f:
                        json.dump(user_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logging.error(f"更新用户登录信息失败: {e}", exc_info=True)
        token = None
        if not is_guest:
            try:
                token = token_manager.create_token(auth_username, session_id)
                token_manager.cleanup_expired_tokens(auth_username)
            except Exception as e:
                logging.error(f"Token管理过程出错: {e}")
                token = None

        logging.info(f"用户 {auth_username} 通过2FA验证登录成功")

        response_data = {
            "success": True,
            "message": "2FA验证成功",
            "session_id": session_id,
            "is_guest": is_guest,
            "token": token,
        }
        response = jsonify(response_data)
        if token:
            response.set_cookie(
                "auth_token",
                value=token,
                max_age=3600,  # 1小时
                httponly=True,
                secure=False,
                samesite="Lax",
            )

        return response

    @app.route("/auth/admin/create_user", methods=["POST"])
    def auth_admin_create_user():
        """管理员：创建新用户

        请求参数：
        - username: 用户名（必填）
        - password: 密码（必填）
        - group: 用户组（可选，默认 user）
        - phone: 手机号（可选）
        - nickname: 昵称（可选）
        - sms_code: 短信验证码（可选，如非空则进行校验）
        """
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "manage_users"):
            return jsonify({"success": False, "message": "权限不足"}), 403

        data = request.json
        new_username = data.get("username", "")
        password = data.get("password", "")
        group = data.get("group", "user")
        phone = data.get("phone", "").strip()
        nickname = data.get("nickname", "").strip()
        sms_code = data.get("sms_code", "").strip()

        if not new_username or not password:
            return jsonify({"success": False, "message": "用户名和密码不能为空"})

        # 如果填写了手机号，验证格式
        if phone:
            import re

            if not re.match(r"^1[3-9]\d{9}$", phone):
                return jsonify({"success": False, "message": "手机号格式不正确"})

        # 如果填写了验证码，进行校验（验证码非空时必须校验）
        if sms_code and phone:
            # 调用短信验证码校验逻辑
            if hasattr(auth_system, "sms_codes") and phone in auth_system.sms_codes:
                stored = auth_system.sms_codes[phone]
                import time

                if stored.get("code") != sms_code:
                    return jsonify({"success": False, "message": "验证码错误"})
                if time.time() > stored.get("expire_at", 0):
                    return jsonify({"success": False, "message": "验证码已过期"})
                # 验证成功，删除已使用的验证码
                del auth_system.sms_codes[phone]
            else:
                return jsonify({"success": False, "message": "验证码不存在或已过期"})

        result = auth_system.register_user(new_username, password, group)
        if result.get("success"):
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)

            # 如果提供了手机号，绑定到新用户
            if phone:
                try:
                    auth_system.update_user_phone(new_username, phone)
                except Exception as e:
                    print(f"[警告] 绑定手机号失败: {e}")

            # 如果提供了昵称，更新昵称
            if nickname:
                try:
                    auth_system.update_user_nickname(new_username, nickname)
                except Exception as e:
                    print(f"[警告] 更新昵称失败: {e}")

            auth_system.log_audit(
                auth_username,
                "create_user",
                f"创建新用户: {new_username} (组: {group})"
                + (f", 手机: {phone}" if phone else ""),
                ip_address,
                session_id,
            )

        return jsonify(result)

    @app.route("/auth/admin/ban_user", methods=["POST"])
    def auth_admin_ban_user():
        """管理员：封禁用户"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "manage_users"):
            return jsonify({"success": False, "message": "权限不足"}), 403

        data = request.json
        target_username = data.get("username", "")

        result = auth_system.ban_user(target_username)
        if result.get("success"):
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            auth_system.log_audit(
                auth_username,
                "ban_user",
                f"封禁用户: {target_username}",
                ip_address,
                session_id,
            )

        return jsonify(result)

    @app.route("/auth/admin/unban_user", methods=["POST"])
    def auth_admin_unban_user():
        """管理员：解封用户"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "manage_users"):
            return jsonify({"success": False, "message": "权限不足"}), 403

        data = request.json
        target_username = data.get("username", "")

        result = auth_system.unban_user(target_username)
        if result.get("success"):
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            auth_system.log_audit(
                auth_username,
                "unban_user",
                f"解封用户: {target_username}",
                ip_address,
                session_id,
            )

        return jsonify(result)

    @app.route("/auth/admin/delete_user", methods=["POST"])
    def auth_admin_delete_user():
        """管理员：删除用户"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "manage_users"):
            return jsonify({"success": False, "message": "权限不足"}), 403

        data = request.json
        target_username = data.get("username", "")

        result = auth_system.delete_user(target_username)
        if result.get("success"):
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            auth_system.log_audit(
                auth_username,
                "delete_user",
                f"删除用户: {target_username}",
                ip_address,
                session_id,
            )

        return jsonify(result)

    @app.route("/auth/admin/force_disable_2fa", methods=["POST"])
    def auth_admin_force_disable_2fa():
        """管理员：强制关闭用户2FA"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")

        # 检查权限：需要 'manage_users' 权限
        if not auth_system.check_permission(auth_username, "manage_users"):
            return jsonify({"success": False, "message": "权限不足"}), 403

        data = request.json
        # 修复: 强制转换为字符串并去除空格，处理纯数字用户名的情况
        target_username = str(data.get("target_username", "")).strip()

        if not target_username:
            return jsonify({"success": False, "message": "用户名不能为空"}), 400

        result = auth_system.force_disable_2fa(target_username)

        if result.get("success"):
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            auth_system.log_audit(
                auth_username,
                "force_disable_2fa",
                f"强制关闭用户 {target_username} 的2FA",
                ip_address,
                session_id,
            )

        return jsonify(result)

    # ============================================================
    # 【修复】添加缺失的强制登出API路由
    # ============================================================
    @app.route("/auth/admin/force_logout_user", methods=["POST"])
    def auth_admin_force_logout_user():
        """管理员：强制登出指定用户"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")

        # 检查权限：需要 'force_logout_users' 权限
        if not auth_system.check_permission(auth_username, "force_logout_users"):
            return jsonify({"success": False, "message": "权限不足"}), 403

        data = request.json
        target_username = data.get("username", "")

        if not target_username:
            return jsonify({"success": False, "message": "用户名不能为空"}), 400

        # 1. 使 Token 失效 (删除 token 文件)
        token_manager.invalidate_token(target_username)

        # 2. 查找并清理所有内存中的活跃会话
        sessions_to_kill = []
        with web_sessions_lock:
            for sid, api in web_sessions.items():
                if getattr(api, "auth_username", "") == target_username:
                    sessions_to_kill.append(sid)

        # 3. 查找用户文件记录的会话 (包括可能不在内存中但持久化的)
        try:
            stored_sessions = auth_system.get_user_sessions(target_username)
            for sid in stored_sessions:
                if sid not in sessions_to_kill:
                    sessions_to_kill.append(sid)
        except Exception as e:
            logging.warning(f"获取用户存储会话失败: {e}")

        cleaned_count = 0
        for sid in sessions_to_kill:
            # 调用全局清理函数，清理内存、文件和索引
            cleanup_session(sid, reason="admin_force_logout")
            cleaned_count += 1

        # 4. 清空用户配置文件中的会话列表
        try:
            user_file = auth_system.get_user_file_path(target_username)
            if os.path.exists(user_file):
                with auth_system.lock:
                    with open(user_file, "r", encoding="utf-8") as f:
                        user_data = json.load(f)

                    user_data["session_ids"] = []

                    with open(user_file, "w", encoding="utf-8") as f:
                        json.dump(user_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"强制登出清理用户文件失败: {e}")

        # 5. 记录审计日志
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
        auth_system.log_audit(
            auth_username,
            "force_logout_user",
            f"强制登出用户: {target_username} (清理了 {cleaned_count} 个会话)",
            ip_address,
            session_id,
        )

        logging.info(f"管理员 {auth_username} 强制登出了用户 {target_username}")
        return jsonify(
            {
                "success": True,
                "message": f"用户 {target_username} 已强制登出，清理了 {cleaned_count} 个会话",
            }
        )

    @app.route("/auth/admin/force_reset_password", methods=["POST"])
    def auth_admin_force_reset_password():
        """
        管理员API：强制重置用户密码。
        """
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "manage_users"):
            return jsonify({"success": False, "message": "权限不足"}), 403
        data = request.json
        target_username = data.get("target_username", "")
        new_password = data.get("new_password", "")

        if not target_username or not new_password:
            return jsonify({"success": False, "message": "缺少用户名或新密码"}), 400
        result = auth_system.reset_user_password(target_username, new_password)
        if result.get("success"):
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            auth_system.log_audit(
                auth_username,
                "force_reset_password",
                f"强制重置了用户 {target_username} 的密码",
                ip_address,
                session_id,
            )

        return jsonify(result)

    @app.route("/api/admin/users/<username>/basic_info", methods=["PUT"])
    def api_admin_update_user_basic_info(username):
        """
        问题8修复：管理员或用户本人：更新用户基本信息
        """
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401
        api_instance = web_sessions[session_id]
        current_username = getattr(api_instance, "auth_username", "")
        is_admin = auth_system.check_permission(current_username, "manage_users")
        if not is_admin and current_username != username:
            return (
                jsonify(
                    {"success": False, "message": "权限不足：您只能修改自己的信息"}
                ),
                403,
            )
        data = request.get_json() or {}
        nickname = data.get("nickname", "").strip()
        if not nickname:
            return jsonify({"success": False, "message": "昵称不能为空"}), 400

        try:
            user_file_path = auth_system.get_user_file_path(username)
            if not os.path.exists(user_file_path):
                return jsonify({"success": False, "message": "用户不存在"}), 404
            with open(user_file_path, "r", encoding="utf-8") as f:
                user_data = json.load(f)
            user_data["nickname"] = nickname
            with open(user_file_path, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            auth_system.log_audit(
                current_username,
                "update_basic_info",
                f"更新用户 {username} 的昵称为: {nickname}",
                ip_address,
                session_id,
            )
            return jsonify(
                {
                    "success": True,
                    "message": "基本信息更新成功",
                    "data": {"username": username, "nickname": nickname},
                }
            )

        except Exception as e:
            app.logger.error(f"[更新基本信息] 失败：{str(e)}", exc_info=True)
            return jsonify({"success": False, "message": f"更新失败: {str(e)}"}), 500

    @app.route("/auth/admin/update_user_nickname", methods=["POST"])
    @login_required
    def auth_admin_update_user_nickname():
        """
        新功能：管理员强制修改用户昵称
        """
        try:
            current_username = g.user
            if not auth_system.check_permission(current_username, "manage_users"):
                return (
                    jsonify({"success": False, "message": "权限不足：需要管理员权限"}),
                    403,
                )
            data = request.get_json() or {}
            target_username = data.get("username", "").strip()
            new_nickname = data.get("nickname", "").strip()
            if not target_username:
                return jsonify({"success": False, "message": "缺少用户名参数"}), 400

            if not new_nickname:
                return jsonify({"success": False, "message": "新昵称不能为空"}), 400
            user_file_path = auth_system.get_user_file_path(target_username)

            if not os.path.exists(user_file_path):
                return jsonify({"success": False, "message": "用户不存在"}), 404
            with auth_system.lock:
                with open(user_file_path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)

                user_data["nickname"] = new_nickname

                with open(user_file_path, "w", encoding="utf-8") as f:
                    json.dump(user_data, f, indent=2, ensure_ascii=False)
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            auth_system.log_audit(
                current_username,
                "admin_update_nickname",
                f"管理员 {current_username} 更新了用户 {target_username} 的昵称为: {new_nickname}",
                ip_address,
                g.api_instance._web_session_id if hasattr(g, "api_instance") else "",
            )
            return jsonify(
                {
                    "success": True,
                    "message": "昵称更新成功",
                    "data": {"username": target_username, "nickname": new_nickname},
                }
            )

        except Exception as e:
            app.logger.error(f"[管理员更新昵称] 失败：{str(e)}", exc_info=True)
            return jsonify({"success": False, "message": f"更新失败: {str(e)}"}), 500

    @app.route("/auth/admin/update_user_phone", methods=["POST"])
    def auth_admin_update_user_phone():
        """
        管理员更新用户手机号

        请求参数：
        - username: 目标用户名（必填）
        - new_phone: 新手机号（必填）
        - sms_code: 短信验证码（可选，如非空则进行校验）
        """
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401
        api_instance = web_sessions[session_id]
        current_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(current_username, "manage_users"):
            return (
                jsonify({"success": False, "message": "权限不足：需要管理员权限"}),
                403,
            )
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        new_phone = data.get("new_phone", "").strip()
        sms_code = data.get("sms_code", "").strip()
        if not username:
            return jsonify({"success": False, "message": "缺少用户名参数"}), 400

        if not new_phone:
            return jsonify({"success": False, "message": "新手机号不能为空"}), 400
        import re

        if not re.match(r"^1[3-9]\d{9}$", new_phone):
            return jsonify({"success": False, "message": "手机号格式不正确"}), 400

        # 如果填写了验证码，进行校验（验证码非空时必须校验）
        if sms_code:
            import time

            if hasattr(auth_system, "sms_codes") and new_phone in auth_system.sms_codes:
                stored = auth_system.sms_codes[new_phone]
                if stored.get("code") != sms_code:
                    return jsonify({"success": False, "message": "验证码错误"}), 400
                if time.time() > stored.get("expire_at", 0):
                    return jsonify({"success": False, "message": "验证码已过期"}), 400
                # 验证成功，删除已使用的验证码
                del auth_system.sms_codes[new_phone]
            else:
                return (
                    jsonify({"success": False, "message": "验证码不存在或已过期"}),
                    400,
                )

        try:
            user_file_path = auth_system.get_user_file_path(username)
            if not os.path.exists(user_file_path):
                return jsonify({"success": False, "message": "用户不存在"}), 404
            auth_system.unbind_phone_from_user(new_phone, except_username=username)
            with auth_system.lock:
                with open(user_file_path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                user_data["phone"] = new_phone
                with open(user_file_path, "w", encoding="utf-8") as f:
                    json.dump(user_data, f, indent=2, ensure_ascii=False)
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            auth_system.log_audit(
                current_username,
                "admin_update_phone",
                f"管理员 {current_username} 更新了用户 {username} 的手机号为: {new_phone}"
                + (f" (已验证)" if sms_code else " (未验证)"),
                ip_address,
                session_id,
            )
            return jsonify(
                {
                    "success": True,
                    "message": "手机号更新成功",
                    "data": {"username": username, "phone": new_phone},
                }
            )

        except Exception as e:
            app.logger.error(f"[管理员更新手机号] 失败：{str(e)}", exc_info=True)
            return jsonify({"success": False, "message": f"更新失败: {str(e)}"}), 500

    @app.route("/auth/admin/login_logs", methods=["GET"])
    def auth_admin_login_logs():
        """获取登录日志（管理员）"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_group = getattr(api_instance, "auth_group", "guest")
        if auth_group not in ["admin", "super_admin"]:
            return jsonify({"success": False, "message": "权限不足"}), 403
        username = request.args.get("username", None)
        limit = int(request.args.get("limit", 100))

        logs = auth_system.get_login_history(username, limit)
        return jsonify({"success": True, "logs": logs})

    @app.route("/auth/admin/get_user_school_accounts", methods=["GET"])
    def auth_admin_get_user_school_accounts():
        """获取指定认证用户的所有 school_account（管理员或有 auto_fill_password 权限）"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_group = getattr(api_instance, "auth_group", "guest")
        auth_username = getattr(api_instance, "auth_username", None)
        has_permission = False
        if auth_group in ["admin", "super_admin"]:
            has_permission = True
        elif auth_username:
            has_permission = auth_system.check_permission(
                auth_username, "auto_fill_password"
            )

        if not has_permission:
            return jsonify({"success": False, "message": "权限不足"}), 403
        target_username = request.args.get("username", auth_username)
        if (
            auth_group not in ["admin", "super_admin"]
            and target_username != auth_username
        ):
            return jsonify({"success": False, "message": "只能查询自己的账户"}), 403
        accounts = api_instance._load_user_school_accounts(target_username)

        return jsonify(
            {"success": True, "username": target_username, "accounts": accounts}
        )

    @app.route("/auth/admin/get_all_users_school_accounts", methods=["GET"])
    def auth_admin_get_all_users_school_accounts():
        """获取所有认证用户的 school_account 列表（管理员或有 auto_fill_password 权限）"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_group = getattr(api_instance, "auth_group", "guest")
        auth_username = getattr(api_instance, "auth_username", None)
        has_permission = False
        if auth_group in ["admin", "super_admin"]:
            has_permission = True
        elif auth_username:
            has_permission = auth_system.check_permission(
                auth_username, "auto_fill_password"
            )

        if not has_permission:
            return jsonify({"success": False, "message": "权限不足"}), 403
        user_accounts_dir = os.path.join(SCHOOL_ACCOUNTS_DIR, "user_accounts")
        all_users_accounts = {}

        if os.path.exists(user_accounts_dir):
            for filename in os.listdir(user_accounts_dir):
                if filename.endswith(".json"):
                    username = filename[:-5]
                    try:
                        file_path = os.path.join(user_accounts_dir, filename)
                        with open(file_path, "r", encoding="utf-8") as f:
                            accounts = json.load(f)
                        all_users_accounts[username] = accounts
                    except Exception as e:
                        logging.error(
                            f"读取用户 {username} 的 school_accounts 失败: {e}"
                        )

        return jsonify({"success": True, "all_accounts": all_users_accounts})

    # ========== 新增：School Account 管理API（保存/添加） ==========
    @app.route("/api/admin/school_account/save", methods=["POST"])
    def api_admin_school_account_save():
        """
        保存或添加 School Account（PC端管理面板CRUD支持）。
        """
        session_id = request.headers.get("X-Session-ID", "")

        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录或会话无效"}), 401
        api_instance = web_sessions[session_id]
        auth_group = getattr(api_instance, "auth_group", "guest")
        current_auth_username = getattr(api_instance, "auth_username", None)

        # ========== 2. 解析请求数据 ==========
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "缺少请求数据"}), 400
            auth_username = data.get("auth_username", "").strip()
            school_username = data.get("school_username", "").strip()
            password = data.get("password", "").strip()
            ua = data.get("ua", "").strip()
            if not auth_username or not school_username or not password:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "缺少必填字段：auth_username, school_username, password",
                        }
                    ),
                    400,
                )

        except Exception as e:
            logging.error(f"解析school_account保存请求失败: {e}", exc_info=True)
            return jsonify({"success": False, "message": "请求数据格式错误"}), 400
        is_admin = auth_group in ["admin", "super_admin"]
        if not is_admin and auth_username != current_auth_username:
            logging.warning(
                f"用户 {current_auth_username} 试图保存 {auth_username} 的账户，权限不足"
            )
            return (
                jsonify({"success": False, "message": "权限不足：只能保存自己的账户"}),
                403,
            )
        try:
            accounts = api_instance._load_user_school_accounts(auth_username)
            if accounts is None:
                accounts = {}

        except Exception as e:
            logging.error(
                f"加载用户 {auth_username} 的 school_accounts 失败: {e}", exc_info=True
            )
            return jsonify({"success": False, "message": "加载账户数据失败"}), 500
        is_new_account = school_username not in accounts
        accounts[school_username] = {
            "password": password,
            "ua": ua if ua else "",
        }
        action = "添加" if is_new_account else "更新"
        logging.info(
            f"{action} school_account: 认证用户={auth_username}, 学校账户={school_username}, 操作者={current_auth_username}"
        )
        try:
            api_instance._save_user_school_accounts(auth_username, accounts)
            return jsonify(
                {
                    "success": True,
                    "message": f"账户 {school_username} {action}成功",
                    "is_new": is_new_account,
                }
            )

        except Exception as e:
            logging.error(
                f"保存用户 {auth_username} 的 school_accounts 失败: {e}", exc_info=True
            )
            return jsonify({"success": False, "message": "保存账户数据失败"}), 500

    @app.route("/api/admin/school_account/delete", methods=["POST"])
    def api_admin_school_account_delete():
        """
        删除 School Account（PC端管理面板CRUD支持）。
        """
        # ========== 1. 验证会话 ==========
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录或会话无效"}), 401
        api_instance = web_sessions[session_id]
        auth_group = getattr(api_instance, "auth_group", "guest")
        current_auth_username = getattr(api_instance, "auth_username", None)
        # ========== 2. 解析请求数据 ==========
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "缺少请求数据"}), 400
            auth_username = data.get("auth_username", "").strip()
            school_username = data.get("school_username", "").strip()
            if not auth_username or not school_username:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "缺少必填字段：auth_username, school_username",
                        }
                    ),
                    400,
                )

        except Exception as e:
            logging.error(f"解析school_account删除请求失败: {e}", exc_info=True)
            return jsonify({"success": False, "message": "请求数据格式错误"}), 400
        is_admin = auth_group in ["admin", "super_admin"]
        if not is_admin and auth_username != current_auth_username:
            logging.warning(
                f"用户 {current_auth_username} 试图删除 {auth_username} 的账户 {school_username}，权限不足"
            )
            return (
                jsonify({"success": False, "message": "权限不足：只能删除自己的账户"}),
                403,
            )
        # ========== 4. 加载现有账户数据 ==========
        try:
            accounts = api_instance._load_user_school_accounts(auth_username)
            if accounts is None:
                accounts = {}

        except Exception as e:
            logging.error(
                f"加载用户 {auth_username} 的 school_accounts 失败: {e}", exc_info=True
            )
            return jsonify({"success": False, "message": "加载账户数据失败"}), 500
        # ========== 5. 删除账户 ==========
        if school_username not in accounts:
            logging.warning(
                f"试图删除不存在的账户: 认证用户={auth_username}, 学校账户={school_username}"
            )
            return (
                jsonify(
                    {"success": False, "message": f"账户 {school_username} 不存在"}
                ),
                404,
            )
        accounts.pop(school_username)
        logging.info(
            f"删除 school_account: 认证用户={auth_username}, 学校账户={school_username}, 操作者={current_auth_username}"
        )
        # ========== 6. 保存到文件 ==========
        try:
            api_instance._save_user_school_accounts(auth_username, accounts)
            return jsonify(
                {"success": True, "message": f"账户 {school_username} 删除成功"}
            )

        except Exception as e:
            logging.error(
                f"保存用户 {auth_username} 的 school_accounts 失败: {e}", exc_info=True
            )
            return jsonify({"success": False, "message": "保存账户数据失败"}), 500

    @app.route("/api/admin/school_account/update", methods=["POST"])
    def api_admin_school_account_update():
        """
        更新 School Account（PC端管理面板CRUD支持）。
        """
        # ========== 1. 验证会话 ==========
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录或会话无效"}), 401
        api_instance = web_sessions[session_id]
        auth_group = getattr(api_instance, "auth_group", "guest")
        current_auth_username = getattr(api_instance, "auth_username", None)
        # ========== 2. 解析请求数据 ==========
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "缺少请求数据"}), 400
            auth_username = data.get("auth_username", "").strip()
            school_username = data.get("school_username", "").strip()
            password = data.get("password", "").strip()
            ua = data.get("ua", "").strip()
            if not auth_username or not school_username or not password:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "缺少必填字段：auth_username, school_username, password",
                        }
                    ),
                    400,
                )
        except Exception as e:
            logging.error(f"解析school_account更新请求失败: {e}", exc_info=True)
            return jsonify({"success": False, "message": "请求数据格式错误"}), 400
        is_admin = auth_group in ["admin", "super_admin"]
        if not is_admin and auth_username != current_auth_username:
            logging.warning(
                f"用户 {current_auth_username} 试图更新 {auth_username} 的账户 {school_username}，权限不足"
            )
            return (
                jsonify({"success": False, "message": "权限不足：只能更新自己的账户"}),
                403,
            )
        # ========== 4. 加载现有账户数据 ==========
        try:
            accounts = api_instance._load_user_school_accounts(auth_username)
            if accounts is None:
                accounts = {}

        except Exception as e:
            logging.error(
                f"加载用户 {auth_username} 的 school_accounts 失败: {e}", exc_info=True
            )
            return jsonify({"success": False, "message": "加载账户数据失败"}), 500
        # ========== 5. 更新账户 ==========
        if school_username not in accounts:
            logging.warning(
                f"试图更新不存在的账户: 认证用户={auth_username}, 学校账户={school_username}"
            )
            return (
                jsonify(
                    {"success": False, "message": f"账户 {school_username} 不存在"}
                ),
                404,
            )
        accounts[school_username] = {"password": password, "ua": ua if ua else ""}
        logging.info(
            f"更新 school_account: 认证用户={auth_username}, 学校账户={school_username}, 操作者={current_auth_username}"
        )
        # ========== 6. 保存到文件 ==========
        try:
            api_instance._save_user_school_accounts(auth_username, accounts)
            return jsonify(
                {"success": True, "message": f"账户 {school_username} 更新成功"}
            )
        except Exception as e:
            logging.error(
                f"保存用户 {auth_username} 的 school_accounts 失败: {e}", exc_info=True
            )
            return jsonify({"success": False, "message": "保存账户数据失败"}), 500

    @app.route("/logs/view", methods=["GET"])
    def view_logs():
        """查看应用日志（管理员）- 分页模式"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_group = getattr(api_instance, "auth_group", "guest")
        if auth_group not in ["admin", "super_admin"]:
            return jsonify({"success": False, "message": "权限不足"}), 403
        # --- [修复] 分页参数 ---
        try:
            page = int(request.args.get("page", 1))
            limit = int(request.args.get("limit", 100))
            if page < 1:
                page = 1
            if limit < 1:
                limit = 100
            if limit > 2000:
                limit = 2000
        except ValueError:
            page = 1
            limit = 100

        all_log_content = []
        log_files = []
        if os.path.exists(LOGIN_LOGS_DIR):
            files = sorted(
                [
                    f
                    for f in os.listdir(LOGIN_LOGS_DIR)
                    if f.endswith(".log") or f.endswith(".jsonl")
                ]
            )
            for f in files:
                log_files.append(os.path.join(LOGIN_LOGS_DIR, f))
        for log_file in log_files:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    all_log_content.extend(f.readlines())
            except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
                logging.debug(f"[日志读取] 无法读取日志文件 {log_file}: {e}")
                continue
        total_lines = len(all_log_content)
        total_pages = (total_lines + limit - 1) // limit
        if page > total_pages and total_pages > 0:
            page = total_pages
        start_index = max(0, total_lines - (page * limit))
        end_index = total_lines - ((page - 1) * limit)
        paginated_logs = all_log_content[start_index:end_index]
        paginated_logs.reverse()

        return jsonify(
            {
                "success": True,
                "logs": paginated_logs,
                "pagination": {
                    "current_page": page,
                    "total_pages": total_pages,
                    "total_lines": total_lines,
                    "limit": limit,
                },
            }
        )

    @app.route("/auth/admin/reset_password", methods=["POST"])
    def auth_admin_reset_password():
        """
        重置用户密码（管理员）或修改自己的密码。
        
        支持两种身份验证方式：
        1. 原密码验证（old_password参数）
        2. 短信验证码验证（sms_code参数）
        
        修改自己密码时，至少需要提供其中一种验证方式。
        管理员重置他人密码时，需要拥有reset_user_password权限。
        """
        # 获取请求头中的会话ID，用于验证用户登录状态
        session_id = request.headers.get("X-Session-ID", "")
        # 检查会话ID是否存在且有效
        if not session_id or session_id not in web_sessions:
            # 会话无效，返回401未授权错误
            return jsonify({"success": False, "message": "未登录"}), 401

        # 从会话中获取API实例
        api_instance = web_sessions[session_id]
        # 获取当前登录用户的用户名
        auth_username = getattr(api_instance, "auth_username", "")
        # 获取当前登录用户的用户组，默认为guest
        auth_group = getattr(api_instance, "auth_group", "guest")

        # 解析请求体JSON数据
        data = request.json
        # 获取目标用户名（要重置密码的用户）
        target_username = data.get("username", "")
        # 获取新密码
        new_password = data.get("new_password", "")
        # 获取旧密码（用于原密码验证方式）
        old_password = data.get("old_password", "")
        # 新增：获取短信验证码参数（用于短信验证码验证方式）
        sms_code = data.get("sms_code", "")

        # 验证必填参数：目标用户名和新密码
        if not target_username or not new_password:
            return jsonify({"success": False, "message": "参数缺失"})
        
        # 判断是否是修改自己的密码
        is_self_change = target_username == auth_username

        if is_self_change:
            # ========== 修改自己的密码，需要验证身份 ==========
            # 支持两种验证方式：原密码 或 短信验证码
            # 至少需要提供其中一种验证方式
            # 注意：如果同时提供了两种验证方式，优先使用短信验证码
            if not old_password and not sms_code:
                return jsonify({"success": False, "message": "请提供当前密码或短信验证码"})
            
            # 获取用户信息文件路径
            user_file = auth_system.get_user_file_path(auth_username)
            # 检查用户文件是否存在
            if not os.path.exists(user_file):
                return jsonify({"success": False, "message": "用户不存在"}), 404

            try:
                # 读取用户信息文件
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                # 获取存储的密码哈希值
                stored_password = user_data.get("password")
                # 获取用户绑定的手机号（用于短信验证）
                user_phone = user_data.get("phone", "")
            except Exception as e:
                # 读取用户信息失败，记录错误日志
                logging.error(f"读取用户 {auth_username} 信息失败: {e}")
                return jsonify({"success": False, "message": "无法验证身份"}), 500
            
            # ========== 开始身份验证 ==========
            # 用于记录是否使用了短信验证码，以便在密码重置成功后删除验证码
            sms_verified_phone = None
            
            if sms_code:
                # ===== 方式一：使用短信验证码验证（优先级更高） =====
                # 当同时提供了短信验证码和原密码时，优先使用短信验证码
                # 检查用户是否已绑定手机号
                if not user_phone:
                    return jsonify({"success": False, "message": "您未绑定手机号，无法使用短信验证"}), 400
                
                # 声明使用全局的短信验证码存储字典
                global sms_verification_codes
                # 从存储中获取该手机号对应的验证码信息
                stored_code_info = sms_verification_codes.get(user_phone)
                
                # 检查是否存在该手机号的验证码
                if not stored_code_info:
                    return jsonify({"success": False, "message": "请先获取短信验证码"}), 400
                
                # 解构验证码信息：验证码内容和过期时间
                stored_code, expires_at = stored_code_info
                
                # 检查验证码是否已过期
                if time.time() > expires_at:
                    # 验证码已过期，删除已过期的验证码
                    del sms_verification_codes[user_phone]
                    return jsonify({"success": False, "message": "验证码已过期，请重新获取"}), 400
                
                # 验证输入的验证码是否正确
                if stored_code != sms_code:
                    return jsonify({"success": False, "message": "短信验证码错误"}), 400
                
                # 记录短信验证成功，但暂不删除验证码
                # 验证码将在密码重置成功后删除，确保操作原子性
                sms_verified_phone = user_phone
                # 记录验证成功日志
                logging.info(f"用户 {auth_username} 使用短信验证码成功验证身份")
            else:
                # ===== 方式二：使用原密码验证 =====
                # 调用密码验证方法，比较输入的旧密码与存储的密码哈希值
                if not auth_system._verify_password(old_password, stored_password):
                    # 密码验证失败
                    return jsonify({"success": False, "message": "当前密码错误"}), 401
        else:
            # ========== 管理员重置他人密码 ==========
            # 检查当前用户是否拥有重置他人密码的权限
            if not auth_system.check_permission(auth_username, "reset_user_password"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            # 管理员重置他人密码不使用短信验证
            sms_verified_phone = None
        
        # 调用auth_system的方法重置密码
        result = auth_system.reset_user_password(target_username, new_password)
        
        # 密码重置成功后，删除已使用的短信验证码（如果使用了短信验证）
        # 放在此处确保只有在密码重置成功后才删除验证码
        # 如果重置失败，验证码仍然有效，用户可以重试
        if sms_verified_phone and result.get("success"):
            if sms_verified_phone in sms_verification_codes:
                del sms_verification_codes[sms_verified_phone]
        
        # 返回操作结果
        return jsonify(result)

    @app.route("/auth/user/update_avatar", methods=["POST"])
    def auth_user_update_avatar():
        """更新用户头像（URL方式）"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")

        if not auth_username or auth_username == "guest":
            return jsonify({"success": False, "message": "游客无法设置头像"})

        data = request.json
        avatar_url = data.get("avatar_url", "")

        result = auth_system.update_user_avatar(auth_username, avatar_url)
        return jsonify(result)

    @app.route("/auth/user/upload_avatar", methods=["POST"])
    def auth_user_upload_avatar():
        """上传用户头像文件（multipart/form-data）"""

        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")

        if not auth_username or auth_username == "guest":
            return jsonify({"success": False, "message": "游客无法上传头像"})
        if "avatar" not in request.files:
            return jsonify({"success": False, "message": "未找到头像文件"}), 400

        file = request.files["avatar"]

        if file.filename == "":
            return jsonify({"success": False, "message": "未选择文件"}), 400
        allowed_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return (
                jsonify(
                    {"success": False, "message": "不支持的文件格式，请上传图片文件"}
                ),
                400,
            )
        file_content = file.read()
        max_size = 5 * 1024 * 1024
        if len(file_content) > max_size:
            return (
                jsonify({"success": False, "message": "文件过大，请上传小于5MB的图片"}),
                400,
            )

        try:
            img = Image.open(io.BytesIO(file_content))
            if img.mode in ("RGBA", "LA", "P"):
                pass
            elif img.mode != "RGB":
                img = img.convert("RGB")
            png_buffer = io.BytesIO()
            img.save(png_buffer, format="PNG", optimize=True)
            png_content = png_buffer.getvalue()
            sha256_hash = hashlib.sha256(png_content).hexdigest()
            images_dir = os.path.join("system_accounts", "images")
            os.makedirs(images_dir, exist_ok=True)
            filename = f"{sha256_hash}.png"
            filepath = os.path.join(images_dir, filename)

            with open(filepath, "wb") as f:
                f.write(png_content)
            index_file = os.path.join(images_dir, "_index.json")
            try:
                if os.path.exists(index_file):
                    with open(index_file, "r", encoding="utf-8") as f:
                        index_data = json.load(f)
                else:
                    index_data = {
                        "version": "1.0",
                        "description": "用户头像索引文件，记录每个文件的上传信息",
                        "files": {},
                    }
                ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
                index_data["files"][filename] = {
                    "username": auth_username,
                    "upload_time": time.time(),
                    "upload_time_str": datetime.datetime.now().isoformat(),
                    "ip_address": ip_address,
                    "original_filename": file.filename,
                    "file_size": len(png_content),
                    "sha256": sha256_hash,
                }
                with open(index_file, "w", encoding="utf-8") as f:
                    json.dump(index_data, f, indent=2, ensure_ascii=False)

                logging.info(
                    f"用户 {auth_username} 从 {ip_address} 上传头像: {filename}"
                )
            except Exception as e:
                logging.error(f"更新头像索引失败: {e}", exc_info=True)
        except Exception as e:
            return (
                jsonify({"success": False, "message": f"图片处理失败: {str(e)}"}),
                500,
            )
        avatar_url = f"/api/avatar/{filename}"
        result = auth_system.update_user_avatar(auth_username, avatar_url)

        if result.get("success"):
            return jsonify(
                {"success": True, "avatar_url": avatar_url, "message": "头像上传成功"}
            )
        else:
            try:
                os.remove(filepath)
                if os.path.exists(index_file):
                    with open(index_file, "r", encoding="utf-8") as f:
                        index_data = json.load(f)
                    if filename in index_data.get("files", {}):
                        del index_data["files"][filename]
                        with open(index_file, "w", encoding="utf-8") as f:
                            json.dump(index_data, f, indent=2, ensure_ascii=False)
            except (OSError, PermissionError) as e:
                logging.warning(f"[会话索引] 更新索引文件失败: {e}")
            return jsonify(result)

    @app.route("/default_avatar.png")
    @app.route("/static/default_avatar.png")
    def serve_default_avatar():
        """
        为 default_avatar.png 提供根路径和 /static 路径的访问。
        """
        try:
            import os

            base_dir = os.path.dirname(__file__)
            default_avatar_path = os.path.join(base_dir, "default_avatar.png")

            if os.path.exists(default_avatar_path):
                return send_file(default_avatar_path, mimetype="image/png")
            else:
                logging.warning(f"Default avatar not found at {default_avatar_path}")
                return "Default avatar not found", 404
        except NameError as e:
            logging.error(f"Serve default avatar failed: {e}. Is send_file imported?")
            return "Server configuration error", 500
        except Exception as e:
            logging.error(f"Error serving default avatar: {e}", exc_info=True)
            return "Server error", 500

    @app.route("/api/avatar/<filename>", methods=["GET"])
    def serve_avatar(filename):
        """提供头像图片服务（需要会话认证，管理员可访问）"""

        if filename == "default_avatar.png":
            return redirect("/default_avatar.png")
        session_id = (
            request.headers.get("X-Session-ID", "")
            or request.cookies.get("session_id", "")
            or request.args.get("session_id", "")
        )
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未授权访问"}), 401
        api_instance = web_sessions[session_id]
        current_username = getattr(api_instance, "auth_username", "")
        is_admin = (
            auth_system.check_permission(current_username, "manage_users")
            if current_username
            else False
        )
        if filename == "default_avatar.png":
            default_avatar_path = os.path.join(
                os.path.dirname(__file__), "default_avatar.png"
            )
            if os.path.exists(default_avatar_path):
                try:
                    return send_file(default_avatar_path, mimetype="image/png")
                except Exception as e:
                    return (
                        jsonify(
                            {"success": False, "message": f"读取默认头像失败: {str(e)}"}
                        ),
                        500,
                    )
            else:
                return jsonify({"success": False, "message": "默认头像文件不存在"}), 404
        if not filename.endswith(".png") or len(filename) != 68:
            return jsonify({"success": False, "message": "无效的文件名"}), 400
        filepath = os.path.join("system_accounts", "images", filename)
        if not os.path.exists(filepath):
            return jsonify({"success": False, "message": "头像不存在"}), 404
        try:
            return send_file(filepath, mimetype="image/png")
        except Exception as e:
            return (
                jsonify({"success": False, "message": f"读取文件失败: {str(e)}"}),
                500,
            )

    @app.route("/auth/admin/clear_user_avatar", methods=["POST"])
    def auth_admin_clear_user_avatar():
        """管理员：强制清除用户头像"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "manage_users"):
            return jsonify({"success": False, "message": "权限不足"}), 403

        data = request.json
        target_username = data.get("username", "")

        if not target_username:
            return jsonify({"success": False, "message": "缺少用户名参数"}), 400
        user_details = auth_system.get_user_details(target_username)
        if not user_details:
            return jsonify({"success": False, "message": "用户不存在"}), 404

        old_avatar_url = user_details.get("avatar_url", "")
        result = auth_system.update_user_avatar(target_username, "default_avatar.png")

        if result.get("success"):
            if old_avatar_url:
                try:
                    filename = old_avatar_url.split("/")[-1]
                    filepath = os.path.join("system_accounts", "images", filename)
                    index_file = os.path.join(
                        "system_accounts", "images", "_index.json"
                    )
                    if os.path.exists(index_file):
                        with open(index_file, "r", encoding="utf-8") as f:
                            index_data = json.load(f)

                        file_info = index_data.get("files", {}).get(filename, {})
                        if file_info.get("username") == target_username:
                            if os.path.exists(filepath):
                                os.remove(filepath)
                                logging.info(
                                    f"管理员 {auth_username} 删除了用户 {target_username} 的头像文件: {filename}"
                                )
                            if filename in index_data.get("files", {}):
                                del index_data["files"][filename]
                                with open(index_file, "w", encoding="utf-8") as f:
                                    json.dump(
                                        index_data, f, indent=2, ensure_ascii=False
                                    )
                        else:
                            logging.info(
                                f"管理员 {auth_username} 清除了用户 {target_username} 的头像URL，但文件由其他用户上传，未删除文件"
                            )

                except Exception as e:
                    logging.error(f"清除头像文件时出错: {e}", exc_info=True)
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            auth_system.log_audit(
                auth_username,
                "clear_user_avatar",
                f"强制清除用户 {target_username} 的头像",
                ip_address,
                session_id,
            )

            return jsonify(
                {"success": True, "message": f"已清除用户 {target_username} 的头像"}
            )
        else:
            return jsonify(result)

    @app.route("/auth/user/update_theme", methods=["POST"])
    def auth_user_update_theme():
        """更新用户主题"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")

        if not auth_username or auth_username == "guest":
            return jsonify({"success": False, "message": "游客无法设置主题"})

        data = request.json
        theme = data.get("theme", "light")

        result = auth_system.update_user_theme(auth_username, theme)
        return jsonify(result)

    @app.route("/api/user/profile", methods=["GET"])
    @login_required
    def api_user_profile():
        """
        获取当前用户信息 (修复前端调用 404 问题)
        """
        try:
            # 从全局对象 g 中获取当前登录的用户名
            current_username = g.user
            # 使用 auth_system 获取详细信息
            user_details = auth_system.get_user_details(current_username)
            
            if user_details:
                return jsonify({
                    "success": True,
                    "username": user_details.get("auth_username"),
                    "phone": user_details.get("phone"),
                    "nickname": user_details.get("nickname"),
                    "avatar_url": user_details.get("avatar_url"),
                    "email": user_details.get("email", ""), # 部分前端逻辑可能需要email
                    "data": user_details # 包含完整的用户数据
                })
            return jsonify({"success": False, "message": "用户数据不存在"}), 404
        except Exception as e:
            logging.error(f"[API] 获取用户资料失败: {e}", exc_info=True)
            return jsonify({"success": False, "message": f"获取资料失败: {str(e)}"}), 500

    @app.route("/auth/user/details", methods=["GET"])
    def auth_user_details():
        """获取用户详细信息"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")

        if not auth_username or auth_username == "guest":
            return jsonify({"success": False, "message": "游客无详细信息"})

        details = auth_system.get_user_details(auth_username)
        if details:
            return jsonify({"success": True, "user": details})
        return jsonify({"success": False, "message": "用户不存在"})

    @app.route("/auth/user/avatar", methods=["GET"])
    def auth_get_user_avatar():
        """根据用户名获取头像URL（管理员可查询所有用户）

        查询参数:
        - username: 用户名（可选，不提供则返回当前用户）
        """
        session_id = request.headers.get("X-Session-ID", "")
        target_username = request.args.get("username", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未授权访问"}), 401

        api_instance = web_sessions[session_id]
        if not hasattr(api_instance, "auth_username"):
            return jsonify({"success": False, "message": "未登录"}), 401

        current_username = getattr(api_instance, "auth_username", "")
        is_admin = auth_system.check_permission(current_username, "manage_users")
        if not target_username:
            target_username = current_username

            if not target_username or target_username == "guest":
                return jsonify(
                    {"success": True, "avatar_url": "", "message": "游客无头像"}
                )
        if not is_admin and target_username != current_username:
            return (
                jsonify({"success": False, "message": "权限不足，只能查询自己的头像"}),
                403,
            )
        details = auth_system.get_user_details(target_username)
        if details:
            return jsonify(
                {
                    "success": True,
                    "avatar_url": details.get("avatar_url", ""),
                    "username": target_username,
                }
            )

        return jsonify({"success": False, "message": "用户不存在", "avatar_url": ""})

    @app.route("/auth/admin/update_max_sessions", methods=["POST"])
    def auth_admin_update_max_sessions():
        """更新用户最大会话数量（管理员）"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        auth_group = getattr(api_instance, "auth_group", "guest")
        if not auth_system.check_permission(auth_username, "manage_users"):
            return jsonify({"success": False, "message": "权限不足"}), 403

        data = request.json
        target_username = data.get("username", "")
        max_sessions = data.get("max_sessions", 1)
        if not isinstance(max_sessions, int) or (
            max_sessions < 1 and max_sessions != -1
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "无效的会话数量：必须为正整数或-1（无限制）",
                    }
                ),
                400,
            )

        result = auth_system.update_max_sessions(target_username, max_sessions)
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
        auth_system.log_audit(
            auth_username,
            "update_max_sessions",
            f"修改用户 {target_username} 的最大会话数为: {max_sessions}",
            ip_address,
            session_id,
        )

        return jsonify(result)

    @app.route("/auth/user/sessions", methods=["GET"])
    def auth_user_sessions():
        """获取用户的所有会话"""
        session_id = request.headers.get("X-Session-ID", "")
        api_instance = None
        is_guest = False
        auth_username = ""

        with web_sessions_lock:
            if session_id in web_sessions:
                api_instance = web_sessions[session_id]
                is_guest = getattr(api_instance, "is_guest", False)
                auth_username = getattr(api_instance, "auth_username", "")
            else:
                state = load_session_state(session_id)
                if state:
                    is_guest = state.get("is_guest", False)
                    auth_username = state.get("auth_username", "")
                else:
                    return (
                        jsonify({"success": False, "message": "会话无效或未登录"}),
                        401,
                    )

        sessions_info = []

        if is_guest:
            logging.debug(
                f"auth_user_sessions: Handling guest session {session_id[:8]}"
            )
            session_file = get_session_file_path(session_id)
            created_at = 0
            last_activity = 0
            login_success_status = False

            if os.path.exists(session_file):
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        session_data = json.load(f)
                    created_at = session_data.get("created_at", 0)
                    last_activity = session_data.get("last_accessed", 0)
                except Exception as e:
                    logging.warning(
                        f"Failed to read guest session file {session_file}: {e}"
                    )

            sessions_info.append(
                {
                    "session_id": session_id,
                    "session_hash": hashlib.sha256(session_id.encode()).hexdigest()[
                        :16
                    ],
                    "created_at": created_at,
                    "last_activity": last_activity,
                    "is_current": True,
                    "login_success": login_success_status,
                    "user_data": {"username": "guest"},
                }
            )
            logging.debug(
                f"auth_user_sessions: Guest session info prepared: {sessions_info}"
            )
            return jsonify(
                {"success": True, "sessions": sessions_info, "max_sessions": -1}
            )

        elif auth_username:
            logging.debug(
                f"auth_user_sessions: Handling registered user {auth_username}"
            )
            session_ids = auth_system.get_user_sessions(auth_username)
            logging.debug(
                f"auth_user_sessions: Found linked session IDs for {auth_username}: {session_ids}"
            )
            user_details = auth_system.get_user_details(auth_username)
            max_sessions = user_details.get("max_sessions", 1) if user_details else 1

            for sid in session_ids:
                session_file = get_session_file_path(sid)
                if os.path.exists(session_file):
                    try:
                        with open(session_file, "r", encoding="utf-8") as f:
                            session_data = json.load(f)
                        if session_data.get("auth_username") == auth_username:
                            is_multi_mode = session_data.get(
                                "is_multi_account_mode", False
                            )
                            session_login_success = session_data.get(
                                "login_success", False
                            )

                            if is_multi_mode:
                                account_states = session_data.get(
                                    "multi_account_states", {}
                                )
                                session_login_success = any(
                                    acc.get("school_account_logged_in", False)
                                    for acc in account_states.values()
                                )

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
                                    "is_current": sid == session_id,
                                    "login_success": session_login_success,
                                    "is_multi_account_mode": is_multi_mode,
                                    "user_data": session_data.get("user_data", {}),
                                }
                            )
                    except Exception as e:
                        logging.warning(
                            f"Failed to read session file {session_file} for user {auth_username}: {e}"
                        )
                        continue
            logging.debug(
                f"auth_user_sessions: Registered user session info prepared: {len(sessions_info)} sessions"
            )
            return jsonify(
                {
                    "success": True,
                    "sessions": sessions_info,
                    "max_sessions": max_sessions,
                }
            )
        else:
            logging.warning(
                f"auth_user_sessions: Invalid state for session {session_id[:8]} - neither guest nor valid user."
            )
            return jsonify({"success": False, "message": "会话状态异常"}), 500

    @app.route("/auth/user/delete_session", methods=["POST"])
    def auth_user_delete_session():
        """删除用户的一个会话"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")

        if not auth_username or auth_username == "guest":
            return jsonify({"success": False, "message": "游客无会话管理"})

        data = request.json
        target_session_id = data.get("session_id", "")

        if not target_session_id:
            return jsonify({"success": False, "message": "会话ID缺失"})
        if target_session_id == session_id:
            return jsonify({"success": False, "message": "不能删除当前会话"})
        auth_system.unlink_session_from_user(auth_username, target_session_id)
        session_file = get_session_file_path(target_session_id)
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except (FileNotFoundError, PermissionError) as e:
                logging.debug(f"[会话删除] 删除会话文件失败: {e}")
        with web_sessions_lock:
            if target_session_id in web_sessions:
                del web_sessions[target_session_id]

        return jsonify({"success": True, "message": "会话已删除"})

    @app.route("/auth/user/create_session_persistence", methods=["POST"])
    def auth_user_create_session_persistence():
        """创建会话持久化文件（登录状态下）"""
        session_id = request.headers.get("X-Session-ID", "")

        api_instance = None
        is_guest = True

        if session_id:
            with web_sessions_lock:
                if session_id in web_sessions:
                    api_instance = web_sessions[session_id]
                    is_guest = getattr(api_instance, "is_guest", True)
                else:
                    state = load_session_state(session_id)
                    if state:
                        is_guest = state.get("is_guest", True)
        if is_guest:
            logging.warning(
                f"Attempt by guest session {session_id[:8]} to create persistent session blocked."
            )
            return (
                jsonify({"success": False, "message": "游客不允许创建额外的会话"}),
                403,
            )
        if not api_instance:
            return jsonify({"success": False, "message": "会话无效或未登录"}), 401

        auth_username = getattr(api_instance, "auth_username", "")

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        is_guest = getattr(api_instance, "is_guest", False)
        data = request.json or {}
        new_session_id = data.get("session_id", "")

        if not new_session_id:
            return jsonify({"success": False, "message": "缺少会话ID"}), 400
        uuid_pattern = re.compile(
            r"^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$",
            re.IGNORECASE,
        )
        if not uuid_pattern.match(new_session_id):
            return jsonify({"success": False, "message": "无效的UUID格式"}), 400
        new_api_instance = Api(args)
        new_api_instance._session_created_at = time.time()
        new_api_instance._web_session_id = new_session_id
        if hasattr(api_instance, "auth_username"):
            new_api_instance.auth_username = api_instance.auth_username
            new_api_instance.auth_group = getattr(api_instance, "auth_group", "guest")
            new_api_instance.is_guest = is_guest
            new_api_instance.is_authenticated = True
        if hasattr(api_instance, "params"):
            new_api_instance.params = copy.deepcopy(api_instance.params)
        if hasattr(api_instance, "device_ua"):
            new_api_instance.device_ua = api_instance.device_ua
        cleanup_message = ""
        if not is_guest and auth_username:
            old_sessions, cleanup_message = (
                auth_system.check_single_session_enforcement(
                    auth_username, new_session_id
                )
            )
            if old_sessions:

                def cleanup_old_sessions_async():
                    for old_sid in old_sessions:
                        try:
                            cleanup_session(old_sid, "session_limit_exceeded")
                        except Exception as e:
                            logging.error(f"后台清理旧会话失败 {old_sid[:16]}...: {e}")

                cleanup_thread = threading.Thread(
                    target=cleanup_old_sessions_async, daemon=True
                )
                cleanup_thread.start()
            auth_system.link_session_to_user(auth_username, new_session_id)
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            audit_details = f"创建新会话持久化文件，会话ID: {new_session_id}"
            if cleanup_message:
                audit_details += f"; {cleanup_message}"

            auth_system.log_audit(
                auth_username,
                "create_session_persistence",
                audit_details,
                ip_address,
                session_id,
            )
        with web_sessions_lock:
            web_sessions[new_session_id] = new_api_instance
            save_session_state(new_session_id, new_api_instance, force_save=True)

        response_data = {
            "success": True,
            "message": "会话持久化文件已创建",
            "session_id": new_session_id,
        }
        if cleanup_message:
            response_data["cleanup_message"] = cleanup_message

        logging.info(f"用户 {auth_username} 创建新会话持久化: {new_session_id[:32]}...")
        response = make_response(jsonify(response_data))
        if not is_guest and auth_username:
            try:
                new_token = token_manager.create_token(auth_username, new_session_id)
                logging.info(f"为新会话 {new_session_id[:8]}... 生成了 Token")
                response.set_cookie(
                    "auth_token",
                    value=new_token,
                    max_age=3600,
                    httponly=True,
                    secure=False,
                    samesite="Lax",
                )
                logging.info(
                    f"已为新会话 {new_session_id[:8]}... 设置 auth_token Cookie"
                )

            except Exception as token_err:
                logging.error(
                    f"为新会话 {new_session_id[:8]} 生成 Token 或设置 Cookie 时出错: {token_err}",
                    exc_info=True,
                )
        return response

    @app.route("/auth/admin/all_sessions", methods=["GET"])
    def auth_admin_all_sessions():
        """管理员：获取所有活跃会话（查看所有会话）"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")

        if not session_id:
            return jsonify({"success": False, "message": "缺少当前会话ID"}), 401

        with web_sessions_lock:
            if session_id not in web_sessions:
                state = load_session_state(session_id)
                if not state:
                    return (
                        jsonify({"success": False, "message": "当前会话无效或已过期"}),
                        401,
                    )
                api_instance = Api(args)
                restore_session_to_api_instance(api_instance, state)
                web_sessions[session_id] = api_instance
                logging.info(f"创建新会话时，按需恢复了发起请求的会话 {session_id[:8]}")
            else:
                api_instance = web_sessions[session_id]

        auth_username = getattr(api_instance, "auth_username", None)
        is_guest = getattr(api_instance, "is_guest", True)
        if not is_guest and auth_username:
            token_from_cookie = request.cookies.get("auth_token")
            if not token_from_cookie:
                logging.warning(
                    f"用户 {auth_username} 尝试创建会话但缺少 auth_token cookie"
                )
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "缺少认证令牌(cookie)，请重新登录",
                            "need_login": True,
                        }
                    ),
                    401,
                )

            is_valid, reason = token_manager.verify_token(
                auth_username, session_id, token_from_cookie
            )
            if not is_valid:
                logging.warning(
                    f"用户 {auth_username} 尝试创建会话但令牌无效: {reason}"
                )
                response_data = {
                    "success": False,
                    "message": f"令牌验证失败 ({reason})，请重新登录",
                    "need_login": True,
                }
                response = make_response(jsonify(response_data), 401)
                response.set_cookie("auth_token", "", max_age=0)
                return response
            else:
                token_manager.refresh_token(auth_username, session_id)
                logging.debug(
                    f"用户 {auth_username} (会话 {session_id[:8]}) Token 验证通过并已刷新"
                )
        elif not is_guest and not auth_username:
            logging.error(f"会话 {session_id[:8]} 存在但缺少用户名，无法创建新会话")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "当前会话状态异常，请重新登录",
                        "need_login": True,
                    }
                ),
                401,
            )
        if not auth_system.check_permission(auth_username, "god_mode"):
            return jsonify({"success": False, "message": "需要查看所有会话权限"}), 403
        all_sessions = []
        session_ids_in_memory = set()
        with web_sessions_lock:
            for sid, api in web_sessions.items():
                session_info = {
                    "session_id": sid,
                    "session_hash": hashlib.sha256(sid.encode()).hexdigest()[:16],
                    "auth_username": getattr(api, "auth_username", None),
                    "auth_group": getattr(api, "auth_group", "guest"),
                    "is_authenticated": getattr(api, "is_authenticated", False),
                    "is_guest": getattr(api, "is_guest", False),
                    "created_at": getattr(api, "_session_created_at", 0),
                    "login_success": getattr(api, "login_success", False),
                    "user_info": getattr(api, "user_info", {}),
                    "is_current": sid == session_id,
                    "username": getattr(api, "auth_username", None),
                }
                all_sessions.append(session_info)
                session_ids_in_memory.add(sid)
        try:
            if os.path.exists(SESSION_STORAGE_DIR):
                for filename in os.listdir(SESSION_STORAGE_DIR):
                    if filename == "_index.json" or not filename.endswith(".json"):
                        continue

                    session_file = os.path.join(SESSION_STORAGE_DIR, filename)
                    try:
                        with open(session_file, "r", encoding="utf-8") as f:
                            state = json.load(f)

                        sid = state.get("session_id")
                        if not sid or sid in session_ids_in_memory:
                            continue
                        is_multi_mode = state.get("is_multi_account_mode", False)
                        session_login_success = state.get("login_success", False)

                        if is_multi_mode:
                            account_states = state.get("multi_account_states", {})
                            session_login_success = any(
                                acc.get("school_account_logged_in", False)
                                for acc in account_states.values()
                            )
                        session_info = {
                            "session_id": sid,
                            "session_hash": hashlib.sha256(sid.encode()).hexdigest()[
                                :16
                            ],
                            "auth_username": state.get("auth_username", None),
                            "auth_group": state.get("auth_group", "guest"),
                            "is_authenticated": state.get("is_authenticated", False),
                            "is_guest": state.get("is_guest", False),
                            "created_at": state.get("created_at", 0),
                            "login_success": session_login_success,
                            "is_multi_account_mode": is_multi_mode,
                            "user_info": state.get("user_info", {}),
                            "is_current": sid == session_id,
                            "username": state.get("auth_username", None),
                        }
                        all_sessions.append(session_info)
                    except Exception as e:
                        logging.warning(f"读取会话文件 {filename} 失败: {e}")
                        continue
        except Exception as e:
            logging.error(f"扫描会话文件目录失败: {e}")

        return jsonify(
            {
                "success": True,
                "sessions": all_sessions,
                "total_count": len(all_sessions),
            }
        )

    @app.route("/auth/admin/destroy_session", methods=["POST"])
    def auth_admin_destroy_session():
        """管理员：强制销毁任意会话（查看所有会话）"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "god_mode"):
            return jsonify({"success": False, "message": "需要查看所有会话权限"}), 403

        data = request.json
        target_session_id = data.get("session_id", "")

        if not target_session_id:
            return jsonify({"success": False, "message": "会话ID缺失"})
        if target_session_id == session_id:
            return jsonify({"success": False, "message": "不能销毁当前会话"})
        target_username = "unknown"
        with web_sessions_lock:
            if target_session_id in web_sessions:
                target_api = web_sessions[target_session_id]
                target_username = getattr(target_api, "auth_username", "unknown")
        if target_username != "unknown" and target_username != "guest":
            auth_system.unlink_session_from_user(target_username, target_session_id)
        session_hash = hashlib.sha256(target_session_id.encode()).hexdigest()
        session_file = os.path.join(SESSION_STORAGE_DIR, f"{session_hash}.json")
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except (FileNotFoundError, PermissionError) as e:
                logging.debug(f"[会话强制登出] 删除会话文件失败: {e}")
        with web_sessions_lock:
            if target_session_id in web_sessions:
                del web_sessions[target_session_id]
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
        auth_system.log_audit(
            auth_username,
            "destroy_session",
            f"强制销毁用户 {target_username} 的会话: {target_session_id[:32]}...",
            ip_address,
            session_id,
        )

        return jsonify(
            {"success": True, "message": f"已销毁用户 {target_username} 的会话"}
        )

    @app.route("/auth/admin/audit_logs", methods=["GET"])
    def auth_admin_audit_logs():
        """获取审计日志（管理员）"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "view_audit_logs"):
            return jsonify({"success": False, "message": "权限不足"}), 403
        username = request.args.get("username", None)
        action = request.args.get("action", None)
        limit = int(request.args.get("limit", 100))

        logs = auth_system.get_audit_logs(username, action, limit)
        return jsonify({"success": True, "logs": logs})

    @app.route("/api/sms/send_code", methods=["POST"])
    def sms_send_code():
        """
        发送短信验证码API
        """
        try:
            # [修正] 使用 strict=False 允许重复项，optionxform=str 保持大小写敏感
            config = configparser.ConfigParser(strict=False)
            config.optionxform = str
            config.read("config.ini", encoding="utf-8")
            if (
                config.get("Features", "enable_sms_service", fallback="false").lower()
                != "true"
            ):
                return jsonify({"success": False, "message": "短信服务未启用"})
            data = request.get_json() or {}
            phone = data.get("phone", "").strip()
            scene = data.get("scene", "register").strip()
            captcha_input = data.get("captcha", "").strip()
            captcha_id = data.get("captcha_id", "").strip()

            is_captcha_valid, captcha_error_msg = verify_captcha(
                captcha_id, captcha_input
            )
            if not is_captcha_valid:
                return jsonify({"success": False, "message": captcha_error_msg})
            if not phone or not re.match(r"^1[3-9]\d{9}$", phone):
                return jsonify({"success": False, "message": "手机号格式不正确"})
            sms_interval_seconds = int(
                config.get(
                    "SMS_Service_SMSBao", "send_interval_seconds", fallback="180"
                )
            )
            last_send_key = f"sms_last_send_{phone}"
            last_send_time = cache.get(last_send_key, 0)
            current_time = time.time()

            if (
                last_send_time
                and (current_time - last_send_time) < sms_interval_seconds
            ):
                remaining_seconds = int(
                    sms_interval_seconds - (current_time - last_send_time)
                )
                return jsonify(
                    {
                        "success": False,
                        "message": f"发送过于频繁，请{remaining_seconds}秒后再试",
                        "retry_after": remaining_seconds,
                    }
                )
            client_ip = request.remote_addr
            current_date = time.strftime("%Y-%m-%d")
            ip_limit_key = f"sms_ip_{client_ip}_{current_date}"
            ip_count = cache.get(ip_limit_key, 0)
            ip_limit = int(
                config.get("SMS_Service_SMSBao", "rate_limit_per_ip_day", fallback="20")
            )
            if ip_count >= ip_limit:
                return jsonify(
                    {
                        "success": False,
                        "message": f"IP每日发送次数已达上限({ip_limit}次)",
                    }
                )
            phone_limit_key = f"sms_phone_{phone}_{current_date}"
            phone_count = cache.get(phone_limit_key, 0)
            phone_limit = int(
                config.get(
                    "SMS_Service_SMSBao", "rate_limit_per_phone_day", fallback="5"
                )
            )
            if phone_count >= phone_limit:
                return jsonify(
                    {
                        "success": False,
                        "message": f"该手机号每日发送次数已达上限({phone_limit}次)",
                    }
                )
            code = "".join([str(random.randint(0, 9)) for _ in range(6)])
            username = config.get("SMS_Service_SMSBao", "username", fallback="")
            api_key = config.get("SMS_Service_SMSBao", "api_key", fallback="")
            signature = config.get(
                "SMS_Service_SMSBao", "signature", fallback="【电科大跑步助手】"
            )
            code_expire_minutes = int(
                config.get("SMS_Service_SMSBao", "code_expire_minutes", fallback="5")
            )
            template = config.get(
                "SMS_Service_SMSBao",
                "template_register",
                fallback=f"您的验证码是：{{code}}，{code_expire_minutes}分钟内有效。",
            )

            if not username or not api_key:
                return jsonify(
                    {"success": False, "message": "短信服务配置不完整，请联系管理员"}
                )
            content = signature + template.replace("{code}", code).replace(
                "{minutes}", str(code_expire_minutes)
            )
            import urllib.parse
            import urllib.request

            url = f"http://api.smsbao.com/sms?u={username}&p={api_key}&m={phone}&c={urllib.parse.quote(content)}"

            logging.debug(f"[短信服务] 发送请求到短信宝API: {url}")

            try:
                response = urllib.request.urlopen(url, timeout=10)
                result = response.read().decode("utf-8").strip()
                if result == "0":
                    code_expire_minutes = int(
                        config.get(
                            "SMS_Service_SMSBao", "code_expire_minutes", fallback="5"
                        )
                    )
                    code_expire_seconds = code_expire_minutes * 60
                    sms_verification_codes[phone] = (
                        code,
                        time.time() + code_expire_seconds,
                    )
                    cache[ip_limit_key] = ip_count + 1
                    cache[phone_limit_key] = phone_count + 1
                    cache[last_send_key] = current_time
                    app.logger.info(
                        f"[短信服务] 向 {phone} 发送验证码成功，场景：{scene}，有效期：{code_expire_minutes}分钟"
                    )
                    try:
                        log_dir = LOGIN_LOGS_DIR
                        os.makedirs(log_dir, exist_ok=True)
                        session_id = request.headers.get("X-Session-ID", None)
                        username = None
                        if scene == "register":
                            username = f"注册用户({phone})"
                        elif scene == "modify":
                            if g and hasattr(g, "user"):
                                username = g.user
                            else:
                                username = "未知用户"
                        elif scene == "admin_modify":
                            username = data.get("target_username", "未知用户")
                        else:
                            if g and hasattr(g, "user"):
                                username = g.user
                            else:
                                username = phone
                        history_entry = {
                            "username": username,
                            "phone": phone,
                            "scene": scene,
                            "timestamp": time.time(),
                            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "content": content,
                            "ip": client_ip,
                        }
                        if (
                            session_id is not None
                            and session_id != ""
                            and session_id != "null"
                        ):
                            history_entry["session_id"] = session_id
                        history_file = os.path.join(log_dir, "sms_history.jsonl")
                        with open(history_file, "a", encoding="utf-8") as f:
                            f.write(
                                json.dumps(history_entry, ensure_ascii=False) + "\n"
                            )

                        app.logger.debug(
                            f"[短信历史] 已记录发送历史: {phone} -> {username}"
                        )
                        if scene in [
                            "admin_modify",
                            "register",
                        ]:
                            session_id = getattr(g, "api_instance", None)
                            if session_id:
                                session_id = getattr(
                                    session_id, "_web_session_id", None
                                )

                            if session_id:
                                pass
                            else:
                                logging.debug(
                                    "[SocketIO] sms_send_code：无法获取 session_id，跳过推送"
                                )

                    except Exception as e:
                        app.logger.error(f"[短信历史] 记录失败: {str(e)}")
                    return jsonify(
                        {
                            "success": True,
                            "message": f"验证码已发送，{code_expire_minutes}分钟内有效",
                            "expire_minutes": code_expire_minutes,
                            "retry_after": sms_interval_seconds,
                        }
                    )
                else:
                    error_map = {
                        "30": "密码错误",
                        "40": "账号不存在",
                        "41": "余额不足",
                        "42": "账户已过期",
                        "43": "IP地址限制",
                        "50": "内容含有敏感词",
                    }
                    detailed_error_msg = error_map.get(
                        result, f"未知错误(错误码:{result})"
                    )
                    app.logger.error(
                        f"[短信服务] 短信宝API返回错误码: {result}, 原因: {detailed_error_msg}, 手机号: {phone}"
                    )
                    return jsonify(
                        {"success": False, "message": "验证码发送失败，请稍后重试"}
                    )

            except Exception as e:
                app.logger.error(
                    f"[短信服务] API调用异常：{str(e)}, 手机号: {phone}", exc_info=True
                )
                return jsonify(
                    {"success": False, "message": "验证码发送失败，请稍后重试"}
                )

        except Exception as e:
            app.logger.error(f"[短信服务] 处理请求异常：{str(e)}", exc_info=True)
            return jsonify({"success": False, "message": "验证码发送失败，请稍后重试"})

    @app.route("/sms-reply-webhook", methods=["GET"])
    def sms_reply_webhook():
        """
        接收短信宝的用户回复推送
        """
        try:
            phone = request.args.get("m", "")
            content = request.args.get("c", "")

            if not phone or not content:
                return "0"
            try:
                import urllib.parse

                content = urllib.parse.unquote(content, encoding="utf-8")
            except:
                pass
            log_dir = LOGIN_LOGS_DIR
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "sms_replies.jsonl")

            import json

            log_entry = {
                "timestamp": time.time(),
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
                "phone": phone,
                "content": content,
                "ip": request.remote_addr,
            }

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            app.logger.info(f"[短信回复] 收到用户 {phone} 的回复：{content}")
            return "0"

        except Exception as e:
            app.logger.error(f"[短信回复] 处理异常：{str(e)}")
            return "0"

    @app.route("/api/sms/test_send", methods=["POST"])
    @login_required
    def sms_test_send():
        """
        短信测试发送API
        """
        try:
            current_user = g.user
            if not auth_system.is_super_admin(
                current_user
            ) and not auth_system.is_admin(current_user):
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "权限不足，仅管理员可使用测试功能",
                        }
                    ),
                    403,
                )
            # [修正] 使用 strict=False 允许重复项，optionxform=str 保持大小写敏感
            config = configparser.ConfigParser(strict=False)
            config.optionxform = str
            config.read("config.ini", encoding="utf-8")
            if (
                config.get("Features", "enable_sms_service", fallback="false").lower()
                != "true"
            ):
                return jsonify(
                    {"success": False, "message": "短信服务未启用，请先在配置中启用"}
                )
            data = request.get_json() or {}
            phone = data.get("phone", "").strip()
            custom_code = data.get("code", "").strip()
            if not phone or not re.match(r"^1[3-9]\d{9}$", phone):
                return jsonify({"success": False, "message": "手机号格式不正确"})
            if custom_code:
                if not re.match(r"^\d{4,8}$", custom_code):
                    return jsonify(
                        {
                            "success": False,
                            "message": "自定义验证码格式不正确，仅支持4-8位数字",
                        }
                    )
                code = custom_code
            else:
                import random

                code = "".join([str(random.randint(0, 9)) for _ in range(6)])
            username = config.get("SMS_Service_SMSBao", "username", fallback="")
            api_key = config.get("SMS_Service_SMSBao", "api_key", fallback="")
            signature = config.get(
                "SMS_Service_SMSBao", "signature", fallback="【电科大跑步助手】"
            )
            code_expire_minutes = int(
                config.get("SMS_Service_SMSBao", "code_expire_minutes", fallback="5")
            )

            if not username or not api_key:
                return jsonify(
                    {
                        "success": False,
                        "message": "短信服务配置不完整，请先完善短信宝用户名和API Key",
                    }
                )
            content = (
                signature
                + f"【测试短信】您的验证码是：{code}，{code_expire_minutes}分钟内有效。这是一条测试短信。"
            )
            import urllib.parse
            import urllib.request

            url = f"http://api.smsbao.com/sms?u={username}&p={api_key}&m={phone}&c={urllib.parse.quote(content)}"

            logging.info(f"[短信测试] 管理员 {current_user} 发送测试短信到 {phone}")

            try:
                response = urllib.request.urlopen(url, timeout=10)
                result = response.read().decode("utf-8").strip()
                if result == "0":
                    try:
                        log_dir = LOGIN_LOGS_DIR
                        os.makedirs(log_dir, exist_ok=True)

                        client_ip = request.remote_addr
                        history_entry = {
                            "username": f"{current_user}(测试)",
                            "phone": phone,
                            "scene": "admin_test",
                            "timestamp": time.time(),
                            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "content": content,
                            "ip": client_ip,
                            "test_code": code,
                        }

                        history_file = os.path.join(log_dir, "sms_history.jsonl")
                        with open(history_file, "a", encoding="utf-8") as f:
                            f.write(
                                json.dumps(history_entry, ensure_ascii=False) + "\n"
                            )

                        logging.info(
                            f"[短信测试] 已记录测试短信历史: {phone} -> 验证码: {code}"
                        )
                    except Exception as e:
                        logging.error(f"[短信测试] 记录历史失败: {str(e)}")
                    return jsonify(
                        {
                            "success": True,
                            "message": f"测试短信发送成功！验证码：{code}",
                            "code": code,
                            "phone": phone,
                        }
                    )
                else:
                    error_map = {
                        "30": "密码错误",
                        "40": "账号不存在",
                        "41": "余额不足",
                        "42": "账户已过期",
                        "43": "IP地址限制",
                        "50": "内容含有敏感词",
                    }
                    error_msg = error_map.get(result, f"未知错误(错误码:{result})")
                    logging.error(
                        f"[短信测试] 短信宝API返回错误: {result} - {error_msg}"
                    )
                    return jsonify(
                        {
                            "success": False,
                            "message": f"发送失败：{error_msg}",
                            "error_code": result,
                        }
                    )

            except Exception as e:
                logging.error(f"[短信测试] API调用异常: {str(e)}", exc_info=True)
                return jsonify({"success": False, "message": f"网络错误：{str(e)}"})

        except Exception as e:
            logging.error(f"[短信测试] 处理请求异常: {str(e)}", exc_info=True)
            return jsonify({"success": False, "message": f"处理失败：{str(e)}"})

    # ====================
    # 管理员日志查看API
    # ====================

    @app.route("/api/admin/logs/login_history", methods=["GET"])
    @login_required
    def admin_logs_login_history():
        """
        查看用户登录历史记录
        """
        try:
            current_user = g.user
            target_username = request.args.get("username", "").strip()
            limit = int(request.args.get("limit", 100))
            if not auth_system.check_permission(current_user, "manage_users"):
                if target_username and target_username != current_user:
                    return jsonify({"success": False, "message": "权限不足"}), 403
                target_username = current_user
            if not target_username:
                if not auth_system.check_permission(current_user, "manage_users"):
                    target_username = current_user
            username_to_query = target_username if target_username else None
            history = auth_system.get_login_history(username_to_query, limit)
            history.reverse()

            return jsonify(
                {
                    "success": True,
                    "logs": history,
                    "total": len(history),
                }
            )

        except Exception as e:
            app.logger.error(f"[登录历史] 查询失败：{str(e)}")
            return jsonify({"success": False, "message": "查询失败"}), 500

    @app.route("/api/admin/logs/audit", methods=["GET"])
    @login_required
    def admin_logs_audit():
        """
        查看用户审计日志（操作记录）
        """

        try:
            if not auth_system.check_permission(g.user, "view_logs"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            username = request.args.get("username", "").strip()
            action = request.args.get("action", "").strip()
            limit = int(request.args.get("limit", 100))
            logs = auth_system.get_audit_logs(username, action, limit)

            return jsonify({"success": True, "logs": logs, "total": len(logs)})

        except Exception as e:
            app.logger.error(f"[审计日志] 查询失败：{str(e)}")
            return jsonify({"success": False, "message": "查询失败"}), 500

    # ============================================================
    # 任务：系统配置API (config.ini)
    # ============================================================

    def _get_config_value(config, section, key, type_func=str, fallback=None):
        """
        辅助函数：从 configparser 安全地获取值，并应用类型转换。
        如果 key 不存在，返回 fallback。
        """
        if config.has_option(section, key):
            try:
                return type_func(config.get(section, key))
            except (ValueError, TypeError):
                return fallback
        return fallback

    @app.route("/api/admin/config/load", methods=["GET"])
    @login_required
    def admin_config_load():
        """
        加载 config.ini 中的可配置项
        权限要求: manage_system
        """
        try:
            if not auth_system.check_permission(g.user, "manage_system"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            default_config = _get_default_config()
            config = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                config.read(CONFIG_FILE, encoding="utf-8")
            else:
                config = default_config
            config_data = {
                "Guest": {
                    "allow_guest_login": _get_config_value(
                        config,
                        "Guest",
                        "allow_guest_login",
                        type_func=config.getboolean,
                        fallback=default_config.getboolean(
                            "Guest", "allow_guest_login", fallback=True
                        ),
                    )
                },
                "System": {
                    "session_expiry_days": _get_config_value(
                        config,
                        "System",
                        "session_expiry_days",
                        type_func=config.getint,
                        fallback=default_config.getint(
                            "System", "session_expiry_days", fallback=7
                        ),
                    ),
                    "school_accounts_dir": _get_config_value(
                        config,
                        "System",
                        "school_accounts_dir",
                        fallback=default_config.get(
                            "System", "school_accounts_dir", fallback="school_accounts"
                        ),
                    ),
                    "system_accounts_dir": _get_config_value(
                        config,
                        "System",
                        "system_accounts_dir",
                        fallback=default_config.get(
                            "System", "system_accounts_dir", fallback="system_accounts"
                        ),
                    ),
                    "permissions_file": _get_config_value(
                        config,
                        "System",
                        "permissions_file",
                        fallback=default_config.get(
                            "System", "permissions_file", fallback="permissions.json"
                        ),
                    ),
                    "session_monitor_check_interval": _get_config_value(
                        config,
                        "System",
                        "session_monitor_check_interval",
                        type_func=config.getint,
                        fallback=default_config.getint(
                            "System", "session_monitor_check_interval", fallback=60
                        ),
                    ),
                    "session_inactivity_timeout": _get_config_value(
                        config,
                        "System",
                        "session_inactivity_timeout",
                        type_func=config.getint,
                        fallback=default_config.getint(
                            "System", "session_inactivity_timeout", fallback=300
                        ),
                    ),
                },
                "Logging": {
                    "log_rotation_size_mb": _get_config_value(
                        config,
                        "Logging",
                        "log_rotation_size_mb",
                        type_func=config.getint,
                        fallback=default_config.getint(
                            "Logging", "log_rotation_size_mb", fallback=10
                        ),
                    ),
                    "archive_max_size_mb": _get_config_value(
                        config,
                        "Logging",
                        "archive_max_size_mb",
                        type_func=config.getint,
                        fallback=default_config.getint(
                            "Logging", "archive_max_size_mb", fallback=500
                        ),
                    ),
                    "log_dir": _get_config_value(
                        config,
                        "Logging",
                        "log_dir",
                        fallback=default_config.get(
                            "Logging", "log_dir", fallback="logs"
                        ),
                    ),
                    "archive_dir": _get_config_value(
                        config,
                        "Logging",
                        "archive_dir",
                        fallback=default_config.get(
                            "Logging", "archive_dir", fallback="logs/archive"
                        ),
                    ),
                },
                "Security": {
                    "password_storage": _get_config_value(
                        config,
                        "Security",
                        "password_storage",
                        fallback=default_config.get(
                            "Security", "password_storage", fallback="plaintext"
                        ),
                    ),
                    "brute_force_protection": _get_config_value(
                        config,
                        "Security",
                        "brute_force_protection",
                        type_func=config.getboolean,
                        fallback=default_config.getboolean(
                            "Security", "brute_force_protection", fallback=True
                        ),
                    ),
                    "login_log_retention_days": _get_config_value(
                        config,
                        "Security",
                        "login_log_retention_days",
                        type_func=config.getint,
                        fallback=default_config.getint(
                            "Security", "login_log_retention_days", fallback=90
                        ),
                    ),
                },
                "Map": {
                    "amap_js_key": _get_config_value(
                        config,
                        "Map",
                        "amap_js_key",
                        fallback=default_config.get("Map", "amap_js_key", fallback=""),
                    )
                },
                "API": {
                    "ip_api_key": _get_config_value(
                        config,
                        "API",
                        "ip_api_key",
                        fallback=default_config.get("API", "ip_api_key", fallback=""),
                    ),
                    "captcha_api_key": _get_config_value(
                        config,
                        "API",
                        "captcha_api_key",
                        fallback=default_config.get(
                            "API", "captcha_api_key", fallback=""
                        ),
                    ),
                },
            }

            return jsonify({"success": True, "config": config_data})

        except Exception as e:
            app.logger.error(f"[系统配置] 加载配置失败：{str(e)}", exc_info=True)
            return jsonify({"success": False, "message": "加载配置失败"}), 500

    @app.route("/api/admin/config/save", methods=["POST"])
    @login_required
    def admin_config_save():
        """
        保存 config.ini 中的可配置项
        权限要求: manage_system
        """
        try:
            if not auth_system.check_permission(g.user, "manage_system"):
                return jsonify({"success": False, "message": "权限不足"}), 403

            data = request.get_json() or {}
            config = configparser.ConfigParser()
            config.optionxform = str
            if os.path.exists(CONFIG_FILE):
                config.read(CONFIG_FILE, encoding="utf-8")
            else:
                config = _get_default_config()

            def ensure_section(cfg, section_name):
                if not cfg.has_section(section_name):
                    cfg.add_section(section_name)

            if "Guest" in data and "allow_guest_login" in data["Guest"]:
                ensure_section(config, "Guest")
                config.set(
                    "Guest",
                    "allow_guest_login",
                    str(data["Guest"]["allow_guest_login"]).lower(),
                )
            if "System" in data:
                ensure_section(config, "System")
                system_data = data["System"]
                for key in [
                    "session_expiry_days",
                    "school_accounts_dir",
                    "system_accounts_dir",
                    "permissions_file",
                    "session_monitor_check_interval",
                    "session_inactivity_timeout",
                ]:
                    if key in system_data:
                        config.set("System", key, str(system_data[key]))
            if "Logging" in data:
                ensure_section(config, "Logging")
                logging_data = data["Logging"]
                for key in [
                    "log_rotation_size_mb",
                    "archive_max_size_mb",
                    "log_dir",
                    "archive_dir",
                ]:
                    if key in logging_data:
                        config.set("Logging", key, str(logging_data[key]))
            if "Security" in data:
                ensure_section(config, "Security")
                security_data = data["Security"]
                if "password_storage" in security_data:
                    allowed_storage = ["plaintext", "sha256", "bcrypt"]
                    if security_data["password_storage"] in allowed_storage:
                        config.set(
                            "Security",
                            "password_storage",
                            security_data["password_storage"],
                        )
                    else:
                        return (
                            jsonify(
                                {
                                    "success": False,
                                    "message": f"无效的 password_storage 值，必须是 {allowed_storage} 之一",
                                }
                            ),
                            400,
                        )
                if "brute_force_protection" in security_data:
                    config.set(
                        "Security",
                        "brute_force_protection",
                        str(security_data["brute_force_protection"]).lower(),
                    )
                if "login_log_retention_days" in security_data:
                    config.set(
                        "Security",
                        "login_log_retention_days",
                        str(security_data["login_log_retention_days"]),
                    )
            if "Map" in data and "amap_js_key" in data["Map"]:
                ensure_section(config, "Map")
                config.set("Map", "amap_js_key", data["Map"]["amap_js_key"])
            if "API" in data:
                ensure_section(config, "API")
                api_data = data["API"]
                if "ip_api_key" in api_data:
                    config.set("API", "ip_api_key", api_data["ip_api_key"])
                if "captcha_api_key" in api_data:
                    config.set("API", "captcha_api_key", api_data["captcha_api_key"])
            _write_config_with_comments(config, CONFIG_FILE)
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            auth_system.log_audit(
                g.user,
                "update_system_config",
                "管理员更新了 config.ini 系统配置",
                ip_address,
                g.api_instance._web_session_id if hasattr(g, "api_instance") else "",
            )

            return jsonify({"success": True, "message": "系统配置已保存"})

        except Exception as e:
            app.logger.error(f"[系统配置] 保存配置失败：{str(e)}", exc_info=True)
            return jsonify({"success": False, "message": "保存配置失败"}), 500

    # ====================
    # 前端日志接收API
    # ====================

    @app.route("/api/log_frontend", methods=["POST"])
    def log_frontend():
        """接收前端日志并保存到后端日志文件（支持批量）"""
        try:
            req_data = request.get_json() or {}
            
            # 获取公共信息
            session_id = request.headers.get("X-Session-ID", "UnknownSession")
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            username = "Guest/Unknown"
            
            # 查找用户信息（只查一次锁）
            with web_sessions_lock:
                if session_id in web_sessions:
                    api_instance = web_sessions[session_id]
                    username_attr = getattr(api_instance, "auth_username", None)
                    if not username_attr and hasattr(api_instance, "user_data"):
                        username_attr = getattr(api_instance.user_data, "username", None)

                    if username_attr:
                        username = username_attr
                    elif getattr(api_instance, "is_guest", False):
                        username = "Guest"

            # 定义单条日志处理内部函数
            def process_single_log(data_item):
                level = data_item.get("level", "INFO").upper()
                message = data_item.get("message", "")
                timestamp = data_item.get("timestamp", "")
                source = data_item.get("source", "unknown")

                if not message:
                    return

                log_message = f"[前端日志][IP:{ip_address}][前端时间:{timestamp}][用户:{username}][Session Id:{session_id}][{source}] {message}"
                
                if level == "DEBUG":
                    logging.debug(log_message)
                elif level == "INFO":
                    logging.info(log_message)
                elif level == "WARNING" or level == "WARN":
                    logging.warning(log_message)
                elif level == "ERROR":
                    logging.error(log_message)
                elif level == "CRITICAL":
                    logging.critical(log_message)
                else:
                    logging.info(log_message)

            # 判断是批量模式还是单条模式
            if "batch" in req_data and isinstance(req_data["batch"], list):
                for item in req_data["batch"]:
                    process_single_log(item)
            else:
                process_single_log(req_data)

            return jsonify({"success": True})
            
        except Exception as e:
            session_id_err = request.headers.get("X-Session-ID", "UnknownSession")
            ip_address_err = request.headers.get("X-Forwarded-For", request.remote_addr)
            logging.error(
                f"[前端日志处理错误][IP:{ip_address_err}][Sess:{session_id_err[:8]}] {e}",
                exc_info=True,
            )
            return jsonify({"success": False, "message": str(e)}), 500

    @app.route("/api/auth/check_phone", methods=["POST"])
    def auth_check_phone():
        """
        检查手机号是否已被绑定。
        """
        data = request.get_json() or {}
        phone = data.get("phone", "").strip()

        if not phone or not re.match(r"^1[3-9]\d{9}$", phone):
            return jsonify({"success": False, "message": "手机号格式不正确"})

        try:
            bound_username = auth_system.find_user_by_phone(phone)

            if bound_username:
                return jsonify(
                    {"success": True, "is_bound": True, "bound_to_user": bound_username}
                )
            else:
                return jsonify({"success": True, "is_bound": False})
        except Exception as e:
            logging.error(f"[检查手机号] 失败: {e}", exc_info=True)
            return jsonify({"success": False, "message": f"服务器内部错误: {e}"}), 500

    @app.route("/api/user/update_phone", methods=["POST"])
    @login_required
    def user_update_phone():
        """
        用户修改自己的手机号。
        
        需要同时验证密码和短信验证码才能修改手机号。
        
        参数:
        - password: 当前账户密码（用于身份验证）
        - new_phone: 新的手机号码
        - sms_code: 发送到新手机号的短信验证码
        """
        try:
            # 读取系统配置文件
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE, encoding="utf-8")
            # 检查系统是否开启了手机号修改功能
            if (
                config.get(
                    "Features", "enable_phone_modification", fallback="false"
                ).lower()
                != "true"
            ):
                # 功能未开启，返回错误提示
                return jsonify(
                    {"success": False, "message": "系统未开启手机号修改功能"}
                )
            
            # 解析请求体JSON数据
            data = request.get_json() or {}
            # 获取新手机号并去除首尾空格
            new_phone = data.get("new_phone", "").strip()
            # 获取短信验证码并去除首尾空格
            sms_code = data.get("sms_code", "").strip()
            # 新增：获取密码参数并去除首尾空格
            password = data.get("password", "").strip()

            # ========== 验证新手机号格式 ==========
            # 使用正则表达式验证手机号格式（中国大陆手机号：1开头，第二位3-9，共11位）
            if not new_phone or not re.match(r"^1[3-9]\d{9}$", new_phone):
                return jsonify({"success": False, "message": "新手机号格式不正确"})

            # ========== 验证短信验证码不能为空 ==========
            if not sms_code:
                return jsonify({"success": False, "message": "请输入短信验证码"})
            
            # ========== 新增：验证密码不能为空 ==========
            if not password:
                return jsonify({"success": False, "message": "请输入当前密码进行验证"})
            
            # 获取当前登录用户的用户名
            current_username = g.user
            
            # ========== 新增：获取用户信息并验证密码 ==========
            # 获取用户信息文件路径
            user_file_path = auth_system.get_user_file_path(current_username)
            # 检查用户文件是否存在
            if not os.path.exists(user_file_path):
                return jsonify({"success": False, "message": "当前用户文件不存在"}), 404
            
            # 读取用户信息以验证密码
            with open(user_file_path, "r", encoding="utf-8") as f:
                user_data = json.load(f)
            
            # 获取存储的密码哈希值
            stored_password = user_data.get("password", "")
            # 验证输入的密码是否正确
            if not auth_system._verify_password(password, stored_password):
                # 密码验证失败
                return jsonify({"success": False, "message": "密码错误，请重新输入"})
            
            # ========== 验证短信验证码 ==========
            # 声明使用全局的短信验证码存储字典
            global sms_verification_codes
            # 从存储中获取新手机号对应的验证码信息
            stored_code_info = sms_verification_codes.get(new_phone)

            # 检查是否存在该手机号的验证码
            if not stored_code_info:
                return jsonify({"success": False, "message": "请先获取验证码"})

            # 解构验证码信息：验证码内容和过期时间
            stored_code, expires_at = stored_code_info

            # 检查验证码是否已过期
            if time.time() > expires_at:
                # 验证码已过期，删除已过期的验证码
                del sms_verification_codes[new_phone]
                return jsonify(
                    {"success": False, "message": "验证码已过期，请重新获取"}
                )

            # 验证输入的验证码是否正确
            if stored_code != sms_code:
                return jsonify({"success": False, "message": "验证码错误"})
            
            # ========== 更新手机号 ==========
            # 注意：将验证码删除操作移到所有数据库操作成功之后
            # 这样可以确保在操作失败时，用户不需要重新获取验证码
            
            # 解绑其他用户绑定的相同手机号（确保手机号唯一性）
            auth_system.unbind_phone_from_user(
                new_phone, except_username=current_username
            )
            
            # 使用锁保护文件读写操作，防止并发冲突
            with auth_system.lock:
                # 重新读取用户信息文件（防止锁等待期间数据被修改）
                with open(user_file_path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)

                # 更新手机号字段
                user_data["phone"] = new_phone

                # 将更新后的用户信息写回文件
                with open(user_file_path, "w", encoding="utf-8") as f:
                    json.dump(user_data, f, indent=2, ensure_ascii=False)
            
            # 手机号更新成功后，删除已使用的验证码（一次性使用）
            # 放在此处确保只有在所有操作成功后才删除验证码
            # 如果前面的操作失败，验证码仍然有效，用户可以重试
            del sms_verification_codes[new_phone]
            
            # 获取客户端IP地址，优先使用X-Forwarded-For头（代理场景）
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            # 记录审计日志
            auth_system.log_audit(
                current_username,
                "user_update_phone",
                f"用户 {current_username} 成功修改手机号为: {new_phone}",
                ip_address,
                g.api_instance._web_session_id,
            )

            # 返回成功响应
            return jsonify(
                {"success": True, "message": "手机号修改成功", "new_phone": new_phone}
            )

        except Exception as e:
            # 捕获所有异常，记录错误日志
            app.logger.error(f"[用户修改手机号] 失败：{str(e)}", exc_info=True)
            # 返回错误响应
            return jsonify({"success": False, "message": f"更新失败: {str(e)}"}), 500

    IP_BANS_FILE = os.path.join("logs", "ip_bans.json")

    @app.route("/api/admin/ip_bans", methods=["GET"])
    @login_required
    def get_ip_bans():
        """
        获取IP封禁列表
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            if not os.path.exists("logs"):
                os.makedirs("logs", exist_ok=True)
            if os.path.exists(IP_BANS_FILE):
                with open(IP_BANS_FILE, "r", encoding="utf-8") as f:
                    bans = json.load(f)
            else:
                bans = []

            return jsonify({"success": True, "bans": bans})
        except Exception as e:
            app.logger.error(f"[IP封禁] 获取列表失败：{str(e)}")
            return jsonify({"success": False, "message": "获取列表失败"}), 500

    @app.route("/api/admin/ip_bans", methods=["POST"])
    @login_required
    def add_ip_ban():
        """
        添加IP封禁规则
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403

            data = request.get_json() or {}
            target = data.get("target", "").strip()
            ban_type = data.get("type", "ip")
            scope = data.get("scope", "all")

            if not target:
                return jsonify({"success": False, "message": "封禁目标不能为空"})
            if not os.path.exists("logs"):
                os.makedirs("logs", exist_ok=True)
            if os.path.exists(IP_BANS_FILE):
                with open(IP_BANS_FILE, "r", encoding="utf-8") as f:
                    bans = json.load(f)
            else:
                bans = []
            new_ban = {
                "id": str(time.time()),
                "target": target,
                "type": ban_type,
                "scope": scope,
                "created_at": time.time(),
                "created_by": g.user,
            }
            bans.append(new_ban)
            os.makedirs(os.path.dirname(IP_BANS_FILE), exist_ok=True)
            with open(IP_BANS_FILE, "w", encoding="utf-8") as f:
                json.dump(bans, f, indent=2, ensure_ascii=False)

            app.logger.info(
                f"[IP封禁] {g.user} 添加封禁规则：{target} ({ban_type}, {scope})"
            )
            return jsonify({"success": True, "message": "封禁规则已添加"})
        except Exception as e:
            app.logger.error(f"[IP封禁] 添加规则失败：{str(e)}")
            return jsonify({"success": False, "message": "添加失败"}), 500

    @app.route("/api/admin/ip_bans/<ban_id>", methods=["DELETE"])
    @login_required
    def delete_ip_ban(ban_id):
        """
        删除IP封禁规则
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403

            if not os.path.exists(IP_BANS_FILE):
                return jsonify({"success": False, "message": "封禁列表不存在"})

            with open(IP_BANS_FILE, "r", encoding="utf-8") as f:
                bans = json.load(f)
            original_count = len(bans)
            bans = [b for b in bans if b["id"] != ban_id]

            if len(bans) == original_count:
                return jsonify({"success": False, "message": "封禁规则不存在"})

            with open(IP_BANS_FILE, "w", encoding="utf-8") as f:
                json.dump(bans, f, indent=2, ensure_ascii=False)

            app.logger.info(f"[IP封禁] {g.user} 删除封禁规则：{ban_id}")
            return jsonify({"success": True, "message": "封禁规则已删除"})
        except Exception as e:
            app.logger.error(f"[IP封禁] 删除规则失败：{str(e)}")
            return jsonify({"success": False, "message": "删除失败"}), 500

    @app.route("/api/admin/check_ip_ban", methods=["POST"])
    def check_ip_ban_api():
        """
        检查IP封禁状态API
        """
        try:
            client_ip = request.remote_addr
            data = request.get_json() or {}
            scope = data.get("scope", "all")
            is_banned = check_ip_ban(client_ip, scope=scope)

            return jsonify({"success": True, "is_banned": is_banned})
        except Exception as e:
            app.logger.error(f"[IP封禁] 检查失败：{str(e)}")
            return jsonify({"success": True, "is_banned": False})

    def check_ip_ban(ip_address, scope="all"):
        """
        检查IP是否被封禁
        """
        if not os.path.exists(IP_BANS_FILE):
            return False

        try:
            with open(IP_BANS_FILE, "r", encoding="utf-8") as f:
                bans = json.load(f)

            for ban in bans:
                if ban["scope"] != "all" and ban["scope"] != scope:
                    continue

                if ban["type"] == "ip":
                    if ip_address == ban["target"]:
                        return True
                elif ban["type"] == "range":
                    try:
                        start_ip_str, end_ip_str = ban["target"].split("-")
                        start_ip = int(ipaddress.ip_address(start_ip_str.strip()))
                        end_ip = int(ipaddress.ip_address(end_ip_str.strip()))
                        current_ip = int(ipaddress.ip_address(ip_address))
                        if start_ip <= current_ip <= end_ip:
                            return True
                    except (ValueError, TypeError) as e:
                        app.logger.warning(
                            f"[IP封禁] 解析IP范围失败: {ban['target']}, 错误: {e}"
                        )
                        pass
                elif ban["type"] == "city":
                    pass

            return False
        except Exception as e:
            app.logger.error(f"[IP封禁] 检查失败：{str(e)}")
            return False

    # ====================
    # 任务20：短信服务配置API
    # ====================

    @app.route("/api/admin/sms/config", methods=["GET"])
    @login_required
    def get_sms_config():
        """
        获取短信服务配置
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            config = configparser.ConfigParser()
            config.read("config.ini", encoding="utf-8")
            if "Features" not in config:
                config.add_section("Features")
            if "SMS_Service_SMSBao" not in config:
                config.add_section("SMS_Service_SMSBao")
            if not config.has_option("Features", "enable_sms_service"):
                config.set("Features", "enable_sms_service", "false")
            if not config.has_option("Features", "enable_phone_modification"):
                config.set("Features", "enable_phone_modification", "false")
            if not config.has_option("Features", "enable_phone_login"):
                config.set("Features", "enable_phone_login", "false")
            if not config.has_option("Features", "enable_phone_registration_verify"):
                config.set("Features", "enable_phone_registration_verify", "false")
            if not config.has_option("SMS_Service_SMSBao", "username"):
                config.set("SMS_Service_SMSBao", "username", "")
            if not config.has_option("SMS_Service_SMSBao", "api_key"):
                config.set("SMS_Service_SMSBao", "api_key", "")
            if not config.has_option("SMS_Service_SMSBao", "signature"):
                config.set("SMS_Service_SMSBao", "signature", "")
            if not config.has_option("SMS_Service_SMSBao", "template_register"):
                config.set("SMS_Service_SMSBao", "template_register", "")
            if not config.has_option("SMS_Service_SMSBao", "code_expire_minutes"):
                config.set("SMS_Service_SMSBao", "code_expire_minutes", "5")
            if not config.has_option(
                "SMS_Service_SMSBao", "rate_limit_per_account_day"
            ):
                config.set("SMS_Service_SMSBao", "rate_limit_per_account_day", "10")
            if not config.has_option("SMS_Service_SMSBao", "rate_limit_per_ip_day"):
                config.set("SMS_Service_SMSBao", "rate_limit_per_ip_day", "20")
            if not config.has_option("SMS_Service_SMSBao", "rate_limit_per_phone_day"):
                config.set("SMS_Service_SMSBao", "rate_limit_per_phone_day", "5")
            with open("config.ini", "w", encoding="utf-8") as f:
                config.write(f)
            sms_config = {
                "enable_sms_service": config.getboolean(
                    "Features", "enable_sms_service", fallback=False
                ),
                "enable_phone_modification": config.getboolean(
                    "Features", "enable_phone_modification", fallback=False
                ),
                "enable_phone_login": config.getboolean(
                    "Features", "enable_phone_login", fallback=False
                ),
                "enable_phone_registration_verify": config.getboolean(
                    "Features", "enable_phone_registration_verify", fallback=False
                ),
                "username": config.get("SMS_Service_SMSBao", "username", fallback=""),
                "api_key": config.get("SMS_Service_SMSBao", "api_key", fallback=""),
                "signature": config.get("SMS_Service_SMSBao", "signature", fallback=""),
                "template_register": config.get(
                    "SMS_Service_SMSBao", "template_register", fallback=""
                ),
                "code_expire_minutes": config.getint(
                    "SMS_Service_SMSBao", "code_expire_minutes", fallback=5
                ),
                "rate_limit_per_account_day": config.getint(
                    "SMS_Service_SMSBao", "rate_limit_per_account_day", fallback=10
                ),
                "rate_limit_per_ip_day": config.getint(
                    "SMS_Service_SMSBao", "rate_limit_per_ip_day", fallback=20
                ),
                "rate_limit_per_phone_day": config.getint(
                    "SMS_Service_SMSBao", "rate_limit_per_phone_day", fallback=5
                ),
            }

            return jsonify({"success": True, "config": sms_config})
        except Exception as e:
            app.logger.error(f"[短信配置] 获取配置失败：{str(e)}")
            return jsonify({"success": False, "message": "获取配置失败"}), 500

    @app.route("/api/admin/sms/config", methods=["POST"])
    @login_required
    def save_sms_config():
        """
        保存短信服务配置
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            data = request.get_json() or {}
            config = configparser.ConfigParser()
            config.read("config.ini", encoding="utf-8")
            if "Features" not in config:
                config.add_section("Features")
            config.set(
                "Features",
                "enable_sms_service",
                str(data.get("enable_sms_service", False)).lower(),
            )
            config.set(
                "Features",
                "enable_phone_modification",
                str(data.get("enable_phone_modification", False)).lower(),
            )
            config.set(
                "Features",
                "enable_phone_login",
                str(data.get("enable_phone_login", False)).lower(),
            )
            config.set(
                "Features",
                "enable_phone_registration_verify",
                str(data.get("enable_phone_registration_verify", False)).lower(),
            )
            if "SMS_Service_SMSBao" not in config:
                config.add_section("SMS_Service_SMSBao")
            config.set("SMS_Service_SMSBao", "username", data.get("username", ""))
            config.set("SMS_Service_SMSBao", "api_key", data.get("api_key", ""))
            config.set("SMS_Service_SMSBao", "signature", data.get("signature", ""))
            config.set(
                "SMS_Service_SMSBao",
                "template_register",
                data.get("template_register", ""),
            )
            config.set(
                "SMS_Service_SMSBao",
                "code_expire_minutes",
                str(data.get("code_expire_minutes", 5)),
            )
            config.set(
                "SMS_Service_SMSBao",
                "rate_limit_per_account_day",
                str(data.get("rate_limit_per_account_day", 10)),
            )
            config.set(
                "SMS_Service_SMSBao",
                "rate_limit_per_ip_day",
                str(data.get("rate_limit_per_ip_day", 20)),
            )
            config.set(
                "SMS_Service_SMSBao",
                "rate_limit_per_phone_day",
                str(data.get("rate_limit_per_phone_day", 5)),
            )
            _write_config_with_comments(config, "config.ini")
            app.logger.info(f"[短信配置] {g.user} 更新了短信服务配置")
            return jsonify({"success": True, "message": "配置已保存"})
        except Exception as e:
            app.logger.error(f"[短信配置] 保存配置失败：{str(e)}")
            return jsonify({"success": False, "message": "保存失败"}), 500

    @app.route("/api/admin/sms/check_balance", methods=["GET"])
    @login_required
    def check_sms_balance():
        """
        查询短信宝余额
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            cache_key = "sms_balance_cache"
            current_time = time.time()
            rate_limit_seconds = 120

            if cache_key in cache:
                last_request_time, cached_data = cache[cache_key]
                if (current_time - last_request_time) < rate_limit_seconds:
                    remaining_wait = int(
                        rate_limit_seconds - (current_time - last_request_time)
                    )
                    response_data = cached_data.copy()
                    response_data["message"] = (
                        f"查询过于频繁，请 {remaining_wait} 秒后再试 (返回上次结果)"
                    )

                    logging.debug(f"[短信配置] 查询余额命中速率限制，返回缓存数据。")
                    return jsonify(response_data)
            # [修正] 使用 strict=False 允许重复项，optionxform=str 保持大小写敏感
            config = configparser.ConfigParser(strict=False)
            config.optionxform = str
            config.read("config.ini", encoding="utf-8")

            username = config.get("SMS_Service_SMSBao", "username", fallback="")
            api_key = config.get("SMS_Service_SMSBao", "api_key", fallback="")

            if not username or not api_key:
                return jsonify({"success": False, "message": "短信宝配置不完整"})
            url = f"https://api.smsbao.com/query?u={username}&p={api_key}"
            logging.debug(f"[短信配置] 查询余额URL: {url}")
            response = requests.get(url, timeout=10)
            response_text = response.text.strip()
            logging.debug(f"[短信配置] 查询余额响应: {response_text}")
            lines = response_text.split("\n")
            if lines and lines[0] == "0":
                if len(lines) > 1:
                    parts = lines[1].split(",")
                    if len(parts) == 2:
                        try:
                            sent_today = int(parts[0])
                            remaining_balance = int(parts[1])
                            result_data = {
                                "success": True,
                                "balance": remaining_balance,
                                "sent_today": sent_today,
                                "message": "查询成功",
                            }
                            cache[cache_key] = (current_time, result_data)

                            return jsonify(result_data)
                        except (ValueError, IndexError):
                            return jsonify(
                                {
                                    "success": False,
                                    "message": f"查询成功，但解析余额失败: {lines[1]}",
                                }
                            )
                    else:
                        return jsonify(
                            {
                                "success": False,
                                "message": f"查询成功，但余额格式不正确: {lines[1]}",
                            }
                        )
                else:
                    return jsonify(
                        {"success": False, "message": "查询成功，但未返回余额数据"}
                    )
            else:
                status_code = lines[0] if lines else response_text
                error_codes = {
                    "30": "密码错误",
                    "40": "账号不存在",
                    "41": "余额不足",
                    "43": "IP地址限制",
                    "50": "内容含有敏感词",
                    "51": "手机号码不正确",
                }
                error_msg = error_codes.get(status_code, f"未知错误码: {status_code}")
                return jsonify({"success": False, "message": f"查询失败：{error_msg}"})
        except Exception as e:
            app.logger.error(f"[短信配置] 查询余额失败：{str(e)}")
            return jsonify({"success": False, "message": f"查询失败：{str(e)}"}), 500

    @app.route("/api/admin/sms/history", methods=["GET"])
    @login_required
    def get_sms_history():
        """
        获取短信发送历史记录
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            date_filter = request.args.get("date", "").strip()
            phone_filter = request.args.get("phone", "").strip()
            history_file = os.path.join(LOGIN_LOGS_DIR, "sms_history.jsonl")

            if not os.path.exists(history_file):
                return jsonify({"success": True, "records": []})

            records = []
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        if date_filter and not record.get("datetime", "").startswith(
                            date_filter
                        ):
                            continue
                        if phone_filter and phone_filter not in record.get("phone", ""):
                            continue

                        records.append(record)
                    except json.JSONDecodeError:
                        continue
            records.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            records = records[:100]
            _ = getattr(g, "api_instance", None)

            return jsonify({"success": True, "records": records})
        except Exception as e:
            app.logger.error(f"[短信历史] 获取历史失败：{str(e)}")
            return jsonify({"success": False, "message": "获取历史失败"}), 500

    @app.route("/api/admin/sms/verification_codes", methods=["GET"])
    @login_required
    def get_verification_codes():
        """
        获取当前有效的验证码列表
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403

            current_time = time.time()
            codes = []
            for phone, (code, expire_time) in list(sms_verification_codes.items()):
                if expire_time > current_time:
                    codes.append(
                        {
                            "phone": phone,
                            "code": code,
                            "expires_at": expire_time,
                            "expires_in": int(expire_time - current_time),
                        }
                    )
            codes.sort(key=lambda x: x["expires_at"])

            return jsonify({"success": True, "codes": codes})
        except Exception as e:
            app.logger.error(f"[验证码管理] 获取列表失败：{str(e)}")
            return jsonify({"success": False, "message": "获取列表失败"}), 500

    @app.route("/api/admin/sms/invalidate_code", methods=["POST"])
    @login_required
    def invalidate_verification_code():
        """
        使指定手机号的验证码失效
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403

            data = request.get_json() or {}
            phone = data.get("phone", "").strip()

            if not phone:
                return jsonify({"success": False, "message": "手机号不能为空"})
            if phone in sms_verification_codes:
                del sms_verification_codes[phone]
                app.logger.info(f"[验证码管理] {g.user} 使 {phone} 的验证码失效")
                _emit_verification_codes_update(g.api_instance._web_session_id)
                return jsonify({"success": True, "message": "验证码已失效"})
            else:
                return jsonify({"success": False, "message": "未找到该手机号的验证码"})
        except Exception as e:
            app.logger.error(f"[验证码管理] 使验证码失效失败：{str(e)}")
            return jsonify({"success": False, "message": "操作失败"}), 500

    @app.route("/api/admin/sms/add_manual_code", methods=["POST"])
    @login_required
    def add_manual_verification_code():
        """
        手动添加验证码（模拟发送，用于测试或紧急情况）
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403

            data = request.get_json() or {}
            phone = data.get("phone", "").strip()
            code = data.get("code", "").strip()
            if not phone or not re.match(r"^1[3-9]\d{9}$", phone):
                return jsonify({"success": False, "message": "手机号格式不正确"})
            if not code or not re.match(r"^\d{6}$", code):
                return jsonify({"success": False, "message": "验证码必须是6位数字"})
            config = configparser.ConfigParser()
            config.read("config.ini", encoding="utf-8")
            code_expire_minutes = int(
                config.get("SMS_Service_SMSBao", "code_expire_minutes", fallback="5")
            )
            code_expire_seconds = code_expire_minutes * 60
            expire_time = time.time() + code_expire_seconds
            sms_verification_codes[phone] = (code, expire_time)

            app.logger.info(
                f"[验证码管理] {g.user} 手动添加验证码: {phone} (有效期{code_expire_minutes}分钟)"
            )

            try:

                os.makedirs(log_dir, exist_ok=True)

                session_id = (
                    g.api_instance._web_session_id
                    if hasattr(g, "api_instance")
                    else None
                )
                client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
                content = f"管理员 {g.user} 手动添加的验证码: {code}，{code_expire_minutes}分钟内有效。"

                history_entry = {
                    "session_id": session_id,
                    "username": g.user,
                    "phone": phone,
                    "scene": "admin_manual_add",
                    "timestamp": time.time(),
                    "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "content": content,
                    "ip": client_ip,
                }

                history_file = os.path.join(log_dir, "sms_history.jsonl")
                with open(history_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(history_entry, ensure_ascii=False) + "\n")

                app.logger.debug(
                    f"[短信历史] 已记录手动添加验证码: {phone} -> {g.user}"
                )
            except Exception as e:
                app.logger.error(f"[短信历史] 记录手动添加验证码失败: {str(e)}")
            _emit_verification_codes_update(g.api_instance._web_session_id)

            return jsonify(
                {
                    "success": True,
                    "message": f"验证码已添加，{code_expire_minutes}分钟内有效",
                }
            )
        except Exception as e:
            app.logger.error(f"[验证码管理] 添加验证码失败：{str(e)}")
            return jsonify({"success": False, "message": "添加失败"}), 500

    # ============================================================================
    # SSL/HTTPS 管理 API
    # ============================================================================

    @app.route("/api/admin/ssl/info", methods=["GET"])
    @login_required
    def get_ssl_info():
        """
        获取当前SSL配置和证书信息。
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            current_ssl_config = load_ssl_config()
            config_info = {
                "ssl_enabled": current_ssl_config.get("ssl_enabled", False),
                "https_only": current_ssl_config.get("https_only", False),
                "cert_path": current_ssl_config.get("ssl_cert_path", ""),
                "key_path": current_ssl_config.get("ssl_key_path", ""),
            }
            cert_info = {}
            cert_path = current_ssl_config.get("ssl_cert_path", "")
            if cert_path:
                logging.info(
                    f"检测到证书路径配置: {cert_path}，正在尝试读取证书信息..."
                )
                cert_info = get_ssl_certificate_info(cert_path)
            else:
                logging.info("证书路径未配置，跳过证书信息读取。")
                cert_info = {"error": "证书路径未在 config.ini 中配置"}

            logging.info(f"[SSL管理] {g.user} 查询SSL配置和证书信息")

            return jsonify(
                {"success": True, "config": config_info, "cert_info": cert_info}
            )

        except Exception as e:
            logging.error(f"[SSL管理] 获取SSL信息失败: {e}", exc_info=True)
            return (
                jsonify({"success": False, "message": f"获取SSL信息失败: {str(e)}"}),
                500,
            )

    @app.route("/api/admin/ssl/upload", methods=["POST"])
    @login_required
    def upload_ssl_certificate():
        """
        上传SSL证书文件和密钥文件。
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            if "cert_file" not in request.files or "key_file" not in request.files:
                return (
                    jsonify(
                        {"success": False, "message": "请同时上传证书文件和密钥文件"}
                    ),
                    400,
                )

            cert_file = request.files["cert_file"]
            key_file = request.files["key_file"]
            if cert_file.filename == "" or key_file.filename == "":
                return jsonify({"success": False, "message": "文件名不能为空"}), 400
            ssl_dir = os.path.join(os.path.dirname(__file__), "ssl")
            os.makedirs(ssl_dir, exist_ok=True)
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".pem"
            ) as temp_cert:
                cert_file.save(temp_cert.name)
                temp_cert_path = temp_cert.name

            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".key"
            ) as temp_key:
                key_file.save(temp_key.name)
                temp_key_path = temp_key.name

            try:
                is_valid, error_msg, cert_info = validate_ssl_certificate(
                    temp_cert_path, temp_key_path
                )

                if not is_valid:
                    os.unlink(temp_cert_path)
                    os.unlink(temp_key_path)
                    return (
                        jsonify(
                            {"success": False, "message": f"证书验证失败: {error_msg}"}
                        ),
                        400,
                    )
                final_cert_path = os.path.join(ssl_dir, "fullchain.pem")
                final_key_path = os.path.join(ssl_dir, "privkey.key")
                if os.path.exists(final_cert_path):
                    backup_cert_path = final_cert_path + ".backup"
                    os.replace(final_cert_path, backup_cert_path)
                    logging.info(f"[SSL管理] 已备份旧证书: {backup_cert_path}")

                if os.path.exists(final_key_path):
                    backup_key_path = final_key_path + ".backup"
                    os.replace(final_key_path, backup_key_path)
                    logging.info(f"[SSL管理] 已备份旧密钥: {backup_key_path}")
                os.replace(temp_cert_path, final_cert_path)
                os.replace(temp_key_path, final_key_path)
                os.chmod(final_cert_path, 0o644)
                os.chmod(final_key_path, 0o600)

                logging.info(f"[SSL管理] {g.user} 成功上传SSL证书")

                return jsonify(
                    {
                        "success": True,
                        "message": "证书上传成功",
                        "cert_path": "ssl/fullchain.pem",
                        "key_path": "ssl/privkey.key",
                        "cert_info": cert_info,
                    }
                )

            except Exception as e:
                if os.path.exists(temp_cert_path):
                    os.unlink(temp_cert_path)
                if os.path.exists(temp_key_path):
                    os.unlink(temp_key_path)
                raise e

        except Exception as e:
            logging.error(f"[SSL管理] 上传证书失败: {e}", exc_info=True)
            return jsonify({"success": False, "message": f"上传失败: {str(e)}"}), 500

    @app.route("/api/admin/ssl/config", methods=["POST"])
    @login_required
    def update_ssl_config():
        """
        更新SSL配置（不包括证书文件，仅更新配置选项）。
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "请求数据为空"}), 400
            current_config = load_ssl_config()
            if "ssl_enabled" in data:
                current_config["ssl_enabled"] = bool(data["ssl_enabled"])

            if "https_only" in data:
                current_config["https_only"] = bool(data["https_only"])

            if "cert_path" in data and data["cert_path"]:
                current_config["ssl_cert_path"] = str(data["cert_path"])

            if "key_path" in data and data["key_path"]:
                current_config["ssl_key_path"] = str(data["key_path"])
            if current_config.get("ssl_enabled", False):
                is_valid, error_msg, _ = validate_ssl_certificate(
                    current_config["ssl_cert_path"], current_config["ssl_key_path"]
                )

                if not is_valid:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": f"证书验证失败，无法启用SSL: {error_msg}",
                            }
                        ),
                        400,
                    )
            if save_ssl_config(current_config):
                logging.info(f"[SSL管理] {g.user} 更新SSL配置: {current_config}")
                return jsonify(
                    {
                        "success": True,
                        "message": "配置已更新，需要重启服务器才能生效",
                        "config": current_config,
                    }
                )
            else:
                return jsonify({"success": False, "message": "保存配置失败"}), 500

        except Exception as e:
            logging.error(f"[SSL管理] 更新配置失败: {e}", exc_info=True)
            return (
                jsonify({"success": False, "message": f"更新配置失败: {str(e)}"}),
                500,
            )

    @app.route("/api/admin/ssl/toggle", methods=["POST"])
    @login_required
    def toggle_ssl():
        """
        快速启用/禁用SSL（开关功能）。
        """
        try:
            if not auth_system.check_permission(g.user, "manage_users"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            data = request.get_json()
            if not data or "enabled" not in data:
                return jsonify({"success": False, "message": "缺少enabled参数"}), 400

            enabled = bool(data["enabled"])
            current_config = load_ssl_config()
            if enabled:
                is_valid, error_msg, _ = validate_ssl_certificate(
                    current_config["ssl_cert_path"], current_config["ssl_key_path"]
                )

                if not is_valid:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": f"无法启用SSL，证书验证失败: {error_msg}",
                            }
                        ),
                        400,
                    )
            current_config["ssl_enabled"] = enabled
            if save_ssl_config(current_config):
                action = "启用" if enabled else "禁用"
                logging.info(f"[SSL管理] {g.user} {action}了SSL")
                return jsonify(
                    {
                        "success": True,
                        "message": f"SSL已{action}，需要重启服务器才能生效",
                        "ssl_enabled": enabled,
                    }
                )
            else:
                return jsonify({"success": False, "message": "保存配置失败"}), 500

        except Exception as e:
            logging.error(f"[SSL管理] 切换SSL状态失败: {e}", exc_info=True)
            return jsonify({"success": False, "message": f"操作失败: {str(e)}"}), 500

    # ============================================================================
    # 应用主路由
    # ============================================================================

    # 默认前端配置（集中定义，避免重复）
    DEFAULT_FRONTEND_CONFIG = {
        "sms_enabled": False,
        "reg_verify_enabled": False,
        "enable_phone_modification": False,
    }

    def get_frontend_config():
        """辅助函数：读取前端需要的功能开关配置"""
        # [修正] 使用 strict=False 允许读取包含重复项的配置文件（保留最后一个值）
        # 同时设置 optionxform=str 保持大小写敏感，防止 LastUser/lastuser 冲突
        config = configparser.ConfigParser(strict=False)
        config.optionxform = str 
        
        try:
            config.read(CONFIG_FILE, encoding="utf-8")
            
            # [修正] 读取成功后，回写配置文件以清除重复项
            # 这会利用 ConfigParser 的特性，将重复键合并为最后一个值，并重写文件
            # 注意：这依赖于全局的 _write_config_with_comments 函数
            try:
                _write_config_with_comments(config, CONFIG_FILE)
                logging.info("[配置] 已自动修复并清理配置文件中的重复项")
            except Exception as write_err:
                logging.error(f"[配置] 尝试自动修复配置文件失败: {write_err}")
                
        except Exception as e:
            logging.error(f"[配置] 读取配置文件失败 (get_frontend_config): {e}")
            # 如果读取失败，尝试使用默认配置继续，避免崩馈
            config = _get_default_config()

        sms_enabled = (
            config.get("Features", "enable_sms_service", fallback="false").lower()
            == "true"
        )
        reg_verify_enabled = (
            config.get(
                "Features", "enable_phone_registration_verify", fallback="false"
            ).lower()
            == "true"
        )

        phone_modification_enabled = (
            config.get(
                "Features", "enable_phone_modification", fallback="false"
            ).lower()
            == "true"
        )

        return {
            "sms_enabled": sms_enabled,
            "reg_verify_enabled": reg_verify_enabled,
            "enable_phone_modification": phone_modification_enabled,
        }

    # ========== 新增路由：前端配置API ==========
    @app.route("/api/frontend-config")
    def api_frontend_config():
        """
        返回前端需要的配置信息（JSON格式）
        用于客户端动态加载配置，减轻服务器端渲染压力
        """
        try:
            config = get_frontend_config()
            return jsonify(config)
        except Exception as e:
            logging.error(f"获取前端配置失败: {e}")
            # 使用集中定义的默认配置
            return jsonify(DEFAULT_FRONTEND_CONFIG), 500

    # ========== 新增路由：CDN缓存文件API ==========
    @app.route("/api/cdn/<file_key>")
    def get_cdn_cached_file(file_key):
        """
        返回本地缓存的CDN文件（JS/CSS）

        参数:
            file_key: 文件标识符，如 sweetalert2, qrcode, cropperjs, cropperjs-css

        返回:
            文件内容，并设置正确的Content-Type
        """
        try:
            with js_cache_lock:
                if file_key in js_cache_storage:
                    content = js_cache_storage[file_key]
                    file_config = CDN_FILES.get(file_key, {})
                    file_type = file_config.get("type", "js")

                    # 设置正确的Content-Type
                    if file_type == "css":
                        mimetype = "text/css"
                    else:
                        mimetype = "application/javascript"

                    response = make_response(content)
                    response.headers["Content-Type"] = mimetype
                    response.headers["Cache-Control"] = (
                        "public, max-age=3600"  # 缓存1小时
                    )
                    return response
                else:
                    logging.warning(f"[CDN缓存API] 请求的文件不存在: {file_key}")
                    return (
                        jsonify(
                            {"success": False, "message": f"文件未找到: {file_key}"}
                        ),
                        404,
                    )
        except Exception as e:
            logging.error(f"[CDN缓存API] 返回文件时发生错误: {e}", exc_info=True)
            return jsonify({"success": False, "message": "服务器内部错误"}), 500

    @app.route("/api/cdn/font/<font_key>")
    def get_cdn_cached_font(font_key):
        """
        返回本地缓存的字体文件（TTF/WOFF/WOFF2）

        参数:
            font_key: 字体文件标识符，如 notosanssc-xxx.ttf

        返回:
            字体文件内容，并设置正确的Content-Type
        """
        try:
            with font_cache_lock:
                if font_key in font_cache_storage:
                    content = font_cache_storage[font_key]

                    # 根据文件扩展名设置正确的Content-Type
                    if font_key.endswith(".woff2"):
                        mimetype = "font/woff2"
                    elif font_key.endswith(".woff"):
                        mimetype = "font/woff"
                    elif font_key.endswith(".ttf"):
                        mimetype = "font/ttf"
                    else:
                        mimetype = "application/octet-stream"

                    response = make_response(content)
                    response.headers["Content-Type"] = mimetype
                    response.headers["Cache-Control"] = (
                        "public, max-age=31536000"  # 缓存1年（字体文件很少变化）
                    )
                    response.headers["Access-Control-Allow-Origin"] = (
                        "*"  # 允许跨域访问字体
                    )
                    return response
                else:
                    logging.warning(f"[CDN缓存API] 请求的字体文件不存在: {font_key}")
                    return (
                        jsonify(
                            {"success": False, "message": f"字体文件未找到: {font_key}"}
                        ),
                        404,
                    )
        except Exception as e:
            logging.error(f"[CDN缓存API] 返回字体文件时发生错误: {e}", exc_info=True)
            return jsonify({"success": False, "message": "服务器内部错误"}), 500

    @app.route("/api/cdn/refresh", methods=["POST"])
    def refresh_cdn_cache():
        """
        手动刷新CDN缓存（管理员功能）
        """
        try:
            session_id = request.headers.get("X-Session-ID", "")
            if not session_id:
                return jsonify({"success": False, "message": "未授权"}), 401

            # 检查是否有管理员权限
            api_instance = None
            with web_sessions_lock:
                if session_id in web_sessions:
                    api_instance = web_sessions[session_id]

            if not api_instance:
                return jsonify({"success": False, "message": "会话无效"}), 401

            auth_username = getattr(api_instance, "auth_username", None)
            if not auth_username:
                return jsonify({"success": False, "message": "未登录"}), 401

            # 检查管理员权限
            if not auth_system.check_permission(auth_username, "admin_panel"):
                return jsonify({"success": False, "message": "权限不足"}), 403

            # 执行刷新
            success_count, fail_count = update_all_cdn_files()

            return jsonify(
                {
                    "success": True,
                    "message": f"CDN缓存刷新完成: 成功 {success_count}, 失败 {fail_count}",
                    "success_count": success_count,
                    "fail_count": fail_count,
                }
            )
        except Exception as e:
            logging.error(f"[CDN缓存API] 刷新缓存时发生错误: {e}", exc_info=True)
            return jsonify({"success": False, "message": "服务器内部错误"}), 500

    # ========== 新增路由：静态资源 (Scripts & Styles) ==========
    @app.route("/scripts/<path:filename>")
    def serve_scripts(filename):
        """
        服务 ./scripts 目录下的静态文件
        """
        try:
            # 获取 main.py 所在目录
            base_dir = os.path.dirname(__file__)
            script_dir = os.path.join(base_dir, 'scripts')
            # 确保目录存在
            if not os.path.exists(script_dir):
                 logging.warning(f"请求 scripts 文件但目录不存在: {script_dir}")
                 return jsonify({"success": False, "message": f"Scripts 文件 {filename} 未找到！"}), 404
            
            return send_from_directory(script_dir, filename)
        except Exception as e:
            logging.error(f"Serving script error: {e}")
            return jsonify({"success": False, "message": "File not found"}), 404

    @app.route("/styles/<path:filename>")
    def serve_styles(filename):
        """
        服务 ./styles 目录下的静态文件
        """
        try:
            # 获取 main.py 所在目录
            base_dir = os.path.dirname(__file__)
            style_dir = os.path.join(base_dir, 'styles')
            # 确保目录存在
            if not os.path.exists(style_dir):
                 logging.warning(f"请求 styles 文件但目录不存在: {style_dir}")
                 return jsonify({"success": False, "message": f"Styles 文件 {filename} 未找到！"}), 404

            return send_from_directory(style_dir, filename)
        except Exception as e:
            logging.error(f"Serving style error: {e}")
            return jsonify({"success": False, "message": "File not found"}), 404

    # ========== 新增路由：Favicon ==========
    @app.route("/favicon.ico")
    def favicon():
        """
        返回网站图标（Favicon）文件。
        """
        try:
            root_dir = os.path.dirname(__file__)
            favicon_path = os.path.join(root_dir, "favicon.ico")
            if not os.path.exists(favicon_path):
                logging.warning(f"Favicon文件不存在: {favicon_path}")
                return jsonify({"success": False, "message": "Favicon文件未找到"}), 404
            return send_file(favicon_path, mimetype="image/vnd.microsoft.icon")
        except Exception as e:
            logging.error(f"返回 favicon.ico 时发生错误: {e}", exc_info=True)
            return jsonify({"success": False, "message": "服务器内部错误"}), 500

    # ========== 新增路由：应用退出API ==========
    @app.route("/api/shutdown", methods=["POST"])
    def api_logout():
        """
        用户登出API端点。

        功能说明：
        - 从请求头中获取会话ID（X-Session-ID）
        - 删除 web_sessions 中的用户会话
        - 使用户的认证 token 失效
        - 清除相关会话数据
        - 返回 JSON 响应，包含重定向 URL 让前端跳转到根路径

        返回值：
        - 成功: {"success": True, "message": "登出成功", "redirect_url": "/"}
        - 失败: {"success": False, "message": "错误信息"}
        """
        try:
            # 从请求头中获取会话ID，这是识别用户会话的关键标识
            session_id = request.headers.get("X-Session-ID", "")

            # 获取客户端信息用于日志记录
            client_ip = request.remote_addr
            user_agent = request.headers.get("User-Agent", "Unknown")

            # 记录用户登出请求日志
            logging.info(
                f"[用户登出] 收到登出请求 - IP: {client_ip}, User-Agent: {user_agent}, Session-ID: {session_id[:16] if session_id else 'None'}..."
            )

            # 验证会话ID是否存在
            if not session_id:
                # 如果没有会话ID，仍然返回成功并提供重定向URL
                # 因为用户可能本身就没有登录，允许其跳转到首页
                logging.warning("[用户登出] 未提供会话ID，跳过会话清理")
                return jsonify(
                    {"success": True, "message": "登出成功", "redirect_url": "/"}
                )

            # 初始化用户名变量，用于后续token失效操作
            username = None

            # 使用线程锁保护 web_sessions 字典的并发访问
            with web_sessions_lock:
                # 检查会话ID是否存在于 web_sessions 中
                if session_id in web_sessions:
                    # 获取对应的API实例
                    api_instance = web_sessions[session_id]

                    # 检查是否有关联的认证用户名
                    if hasattr(api_instance, "auth_username"):
                        username = api_instance.auth_username
                        # 检查是否为访客用户，访客用户不需要使token失效
                        is_guest = getattr(api_instance, "is_guest", True)

                        # 只有非访客用户才需要使token失效
                        if not is_guest and username:
                            # 调用token管理器使该用户的token失效
                            token_manager.invalidate_token(username, session_id)
                            logging.info(
                                f"[用户登出] 用户 {username} 的 token 已失效，session: {session_id[:16]}..."
                            )

            # 调用会话清理函数，删除会话数据、会话文件等
            # 这个函数会处理 web_sessions 字典删除、会话文件删除、活动记录清理等
            cleanup_session(session_id, "user_logout")

            # 构建成功响应，包含重定向URL
            response = jsonify(
                {"success": True, "message": "登出成功", "redirect_url": "/"}
            )

            # 清除客户端的认证cookie，设置 max_age=0 使其立即过期
            response.set_cookie("auth_token", "", max_age=0)

            logging.info(f"[用户登出] 用户登出成功，已返回重定向响应")

            return response

        except Exception as e:
            # 捕获并记录任何异常
            logging.error(f"[用户登出] 处理登出请求时发生错误: {e}", exc_info=True)
            return jsonify({"success": False, "message": f"登出失败: {str(e)}"}), 500

    @app.route("/")
    def index():
        """首页：显示登录页面，等待用户认证后分配UUID"""
        app_config = get_frontend_config()
        config_script = f"""
        <script>
            window.APP_CONFIG = {json.dumps(app_config)};
        </script>
        """
        modified_html = html_content.replace("</body>", f"{config_script}</body>")

        return render_template_string(modified_html)

    @app.route("/uuid=<uuid>")
    def session_view(uuid):
        """会话页面：显示应用界面"""
        uuid_pattern = re.compile(
            r"^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$",
            re.IGNORECASE,
        )
        if not uuid or not uuid_pattern.match(uuid):
            logging.warning(
                f"无效的UUID格式或不匹配标准格式: {uuid[:40] if uuid else 'None'}..."
            )
            return redirect(url_for("index"))

        with web_sessions_lock:
            if uuid not in web_sessions:
                state = load_session_state(uuid)
                api_instance = Api(args)
                api_instance._session_created_at = time.time()
                api_instance._web_session_id = uuid

                if state and state.get("login_success"):
                    api_instance.login_success = True
                    api_instance.user_info = state.get("user_info")
                    api_instance._session_created_at = state.get(
                        "created_at", time.time()
                    )
                    restore_session_to_api_instance(api_instance, state)

                    logging.info(
                        f"从文件恢复已登录会话 : {uuid[:32]}... (用户: {state.get('user_info', {}).get('username', 'Unknown')}, 任务数: {len(api_instance.all_run_data)})"
                    )
                else:
                    logging.info(f"创建新会话 : {uuid[:32]}...")

                web_sessions[uuid] = api_instance
            else:
                api_instance = web_sessions[uuid]
                if not hasattr(api_instance, "_web_session_id"):
                    api_instance._web_session_id = uuid
                logging.debug(f"使用现有会话: {uuid[:32]}...")
        app_config = get_frontend_config()
        config_script = f"""
        <script>
            window.APP_CONFIG = {json.dumps(app_config)};
        </script>
        """
        modified_html = html_content.replace("</body>", f"{config_script}</body>")
        return render_template_string(modified_html)

#     @app.route("/JavaScript/<path:function_path>.js", methods=["GET"])
#     def serve_javascript(function_path):
#         """
#         JavaScript 函数动态加载 API 端点
#         """
#         if function_path == "JavaScript_globals":
#             return redirect("/JavaScript_globals.js")
#         try:
#             js_file_path = os.path.join(os.path.dirname(__file__), "JavaScript.js")
#             if not os.path.exists(js_file_path):
#                 logging.error(f"JavaScript.js 文件不存在: {js_file_path}")
#                 return jsonify({"error": "JavaScript file not found"}), 404
#             with open(js_file_path, "r", encoding="utf-8") as f:
#                 full_content = f.read()
#             function_name = function_path.replace("/", "_")
#             pattern = rf"(?:^|\n)(\s*(?:(?:async\s+)?function\s+{function_name}\s*\([^)]*\)|(?:const|let|var)\s+{function_name}\s*=\s*(?:function\s*\([^)]*\)|(?:async\s+)?function\s*\([^)]*\)|\([^)]*\)\s*=>))\s*{{)"

#             match = re.search(pattern, full_content, re.MULTILINE)

#             if not match:
#                 logging.warning(
#                     f"未找到精确匹配的函数 '{function_name}'，尝试模糊搜索..."
#                 )
#                 fuzzy_pattern = rf"(?:^|\n)(\s*(?:function\s+\w*{function_name}\w*\s*\([^)]*\)|(?:const|let|var)\s+\w*{function_name}\w*\s*=))"
#                 fuzzy_matches = re.finditer(
#                     fuzzy_pattern, full_content, re.MULTILINE | re.IGNORECASE
#                 )
#                 found_functions = []
#                 for m in fuzzy_matches:
#                     func_line = m.group(0).strip()
#                     found_functions.append(func_line[:50])

#                 if found_functions:
#                     suggestions = "\n".join(found_functions)
#                     logging.info(f"找到相似的函数定义:\n{suggestions}")
#                     return (
#                         jsonify(
#                             {
#                                 "error": f"Function '{function_name}' not found",
#                                 "suggestions": found_functions[:5],
#                             }
#                         ),
#                         404,
#                     )
#                 else:
#                     logging.error(f"未找到任何与 '{function_name}' 相关的函数")
#                     return (
#                         jsonify({"error": f"Function '{function_name}' not found"}),
#                         404,
#                     )
#             func_start = match.start()
#             brace_count = 0
#             in_function = False
#             func_end = func_start

#             for i in range(func_start, len(full_content)):
#                 char = full_content[i]

#                 if char == "{":
#                     brace_count += 1
#                     in_function = True
#                 elif char == "}":
#                     brace_count -= 1
#                     if in_function and brace_count == 0:
#                         func_end = i + 1
#                         break
#             function_code = full_content[func_start:func_end]
#             comments_start = func_start
#             lines_before = full_content[:func_start].split("\n")
#             comment_lines = []

#             for line in reversed(lines_before):
#                 stripped = line.strip()
#                 if (
#                     stripped.startswith("//")
#                     or stripped.startswith("/*")
#                     or stripped.startswith("*")
#                     or stripped.startswith("*/")
#                 ):
#                     comment_lines.insert(0, line)
#                 elif stripped == "":
#                     comment_lines.insert(0, line)
#                 else:
#                     break
#             if comment_lines:
#                 comments = "\n".join(comment_lines)
#                 function_code = comments + "\n" + function_code
#             response_content = f"""// ==============================================================================
# // 动态加载的 JavaScript 函数: {function_name}
# // 从 JavaScript.js 文件中提取
# // ==============================================================================

# {function_code}
# """

#             response = make_response(response_content)
#             response.headers["Content-Type"] = "application/javascript; charset=utf-8"

#             response.headers["Cache-Control"] = "public, max-age=3600"
#             file_mtime = os.path.getmtime(js_file_path)
#             last_modified = datetime.datetime.fromtimestamp(file_mtime).strftime(
#                 "%a, %d %b %Y %H:%M:%S GMT"
#             )
#             response.headers["Last-Modified"] = last_modified
#             etag = hashlib.md5(function_code.encode("utf-8")).hexdigest()
#             response.headers["ETag"] = f'"{etag}"'
#             if_modified_since = request.headers.get("If-Modified-Since")
#             if_none_match = request.headers.get("If-None-Match")
#             if (if_modified_since == last_modified) or (if_none_match == f'"{etag}"'):
#                 logging.debug(f"JavaScript 函数 '{function_name}' 使用缓存版本 (304)")
#                 return "", 304

#             logging.info(
#                 f"成功返回 JavaScript 函数: {function_name} ({len(function_code)} 字符)"
#             )
#             return response

#         except FileNotFoundError as e:
#             logging.error(f"JavaScript.js 文件未找到: {e}")
#             return jsonify({"error": "JavaScript file not found"}), 404
#         except Exception as e:
#             logging.error(f"加载 JavaScript 函数时发生错误: {e}", exc_info=True)
#             return jsonify({"error": "Internal server error"}), 500

    # @app.route("/JavaScript_globals.js", methods=["GET"])
    # def serve_javascript_globals():
    #     """
    #     返回 JavaScript 全局变量文件（优先加载）
    #     """
    #     try:
    #         js_globals_file = os.path.join(
    #             os.path.dirname(__file__), "JavaScript_globals.js"
    #         )

    #         if not os.path.exists(js_globals_file):
    #             logging.error(f"JavaScript 全局变量文件不存在: {js_globals_file}")
    #             return jsonify({"error": "JavaScript globals file not found"}), 404
    #         with open(js_globals_file, "r", encoding="utf-8") as f:
    #             original_content = f.read()
    #         minify_param = request.args.get("minify", "true").lower()
    #         should_minify = minify_param in ["true", "1", "yes", ""]
    #         if should_minify:
    #             content = original_content
    #             content_type_suffix = " (original, compression disabled)"
    #             logging.info(
    #                 f"JavaScript_globals.js 压缩功能已禁用，返回原始大小: {len(original_content)} 字节"
    #             )
    #         else:
    #             content = original_content
    #             content_type_suffix = " (original)"
    #         file_mtime = os.path.getmtime(js_globals_file)
    #         last_modified = datetime.datetime.fromtimestamp(file_mtime).strftime(
    #             "%a, %d %b %Y %H:%M:%S GMT"
    #         )

    #         etag_base = hashlib.md5(content.encode("utf-8")).hexdigest()
    #         etag = f'"{etag_base}-{"min" if should_minify else "orig"}"'
    #         if_modified_since = request.headers.get("If-Modified-Since")
    #         if_none_match = request.headers.get("If-None-Match")

    #         if (if_modified_since == last_modified) or (if_none_match == etag):
    #             logging.debug(
    #                 f"JavaScript_globals.js 使用缓存版本 (304){content_type_suffix}"
    #             )
    #             return "", 304

    #         response = make_response(content)
    #         response.headers["Content-Type"] = "application/javascript; charset=utf-8"
    #         response.headers["Cache-Control"] = "public, max-age=3600"
    #         response.headers["Last-Modified"] = last_modified
    #         response.headers["ETag"] = etag
    #         response.headers["X-Minified"] = "true" if should_minify else "false"

    #         logging.info(
    #             f"成功返回 JavaScript_globals.js{content_type_suffix} ({len(content)} 字符)"
    #         )
    #         return response

    #     except Exception as e:
    #         logging.error(f"加载 JavaScript_globals.js 时发生错误: {e}", exc_info=True)
    #         return jsonify({"error": "Internal server error"}), 500

    # @app.route("/Cascading_Style_Sheets_Web_animation.css", methods=["GET"])
    # def serve_css_animation():
    #     """
    #     返回 CSS 动画文件（优先加载）
    #     """
    #     try:
    #         css_animation_file = os.path.join(
    #             os.path.dirname(__file__), "Cascading_Style_Sheets_Web_animation.css"
    #         )

    #         if not os.path.exists(css_animation_file):
    #             logging.error(f"CSS 动画文件不存在: {css_animation_file}")
    #             return jsonify({"error": "CSS animation file not found"}), 404
    #         with open(css_animation_file, "r", encoding="utf-8") as f:
    #             original_content = f.read()
    #         minify_param = request.args.get("minify", "true").lower()
    #         should_minify = minify_param in ["true", "1", "yes", ""]
    #         if should_minify:
    #             content = original_content
    #             content_type_suffix = " (original, compression disabled)"
    #             logging.info(
    #                 f"Cascading_Style_Sheets_Web_animation.css 压缩功能已禁用，返回原始大小: {len(original_content)} 字节"
    #             )
    #         else:
    #             content = original_content
    #             content_type_suffix = " (original)"
    #         file_mtime = os.path.getmtime(css_animation_file)
    #         last_modified = datetime.datetime.fromtimestamp(file_mtime).strftime(
    #             "%a, %d %b %Y %H:%M:%S GMT"
    #         )

    #         etag_base = hashlib.md5(content.encode("utf-8")).hexdigest()
    #         etag = f'"{etag_base}-{"min" if should_minify else "orig"}"'
    #         if_modified_since = request.headers.get("If-Modified-Since")
    #         if_none_match = request.headers.get("If-None-Match")

    #         if (if_modified_since == last_modified) or (if_none_match == etag):
    #             logging.debug(
    #                 f"Cascading_Style_Sheets_Web_animation.css 使用缓存版本 (304){content_type_suffix}"
    #             )
    #             return "", 304

    #         response = make_response(content)
    #         response.headers["Content-Type"] = "text/css; charset=utf-8"
    #         response.headers["Cache-Control"] = "public, max-age=3600"
    #         response.headers["Last-Modified"] = last_modified
    #         response.headers["ETag"] = etag
    #         response.headers["X-Minified"] = "true" if should_minify else "false"

    #         logging.info(
    #             f"成功返回 Cascading_Style_Sheets_Web_animation.css{content_type_suffix} ({len(content)} 字符)"
    #         )
    #         return response

    #     except Exception as e:
    #         logging.error(
    #             f"加载 Cascading_Style_Sheets_Web_animation.css 时发生错误: {e}",
    #             exc_info=True,
    #         )
    #         return jsonify({"error": "Internal server error"}), 500

    # def get_parsed_stylesheet(css_file_path):
    #     """
    #     获取解析后的 CSS 样式表。
    #     """
    #     if not os.path.exists(css_file_path):
    #         logging.error(f"CSS 文件不存在: {css_file_path}")
    #         return None, None

    #     try:
    #         logging.info(f"正在实时解析 CSS 文件: {css_file_path}")
    #         cssutils.ser.prefs.useDefaults()
    #         cssutils.log.setLevel(logging.CRITICAL)
    #         parser = cssutils.CSSParser(validate=False)
    #         stylesheet = parser.parseFile(css_file_path, encoding="utf-8")
    #         selectors = set()
    #         for rule in stylesheet:
    #             if rule.type == cssutils.css.CSSRule.STYLE_RULE:
    #                 for selector in rule.selectorList:
    #                     selectors.add(selector.selectorText.strip())
    #         sorted_selectors = sorted(list(selectors))
    #         return stylesheet, sorted_selectors

    #     except Exception as e:
    #         logging.error(f"解析 CSS 文件时出错: {e}", exc_info=True)
    #         return None, None

    # @app.route("/css/available-selectors.list", methods=["GET"])
    # def get_available_css_selectors():
    #     """
    #     返回 Cascading_Style_Sheets.css 文件中所有可用的 CSS 选择器列表。
    #     """
    #     try:
    #         CURRENT_DIR = os.path.dirname(__file__)
    #     except NameError:
    #         CURRENT_DIR = os.getcwd()

    #     CSS_FILE_PATH = os.path.join(CURRENT_DIR, "Cascading_Style_Sheets.css")
    #     try:
    #         if not os.path.exists(CSS_FILE_PATH):
    #             return jsonify({"错误": "找不到 CSS 文件"}), 500

    #         stylesheet, selectors = get_parsed_stylesheet(CSS_FILE_PATH)

    #         if not stylesheet:
    #             return jsonify({"错误": "解析 CSS 文件失败"}), 500
    #         file_mtime = os.path.getmtime(CSS_FILE_PATH)
    #         last_modified = datetime.datetime.fromtimestamp(file_mtime).strftime(
    #             "%a, %d %b %Y %H:%M:%S GMT"
    #         )
    #         etag = f'"{hashlib.md5(str(selectors).encode("utf-8")).hexdigest()}"'
    #         if (request.headers.get("If-Modified-Since") == last_modified) or (
    #             request.headers.get("If-None-Match") == etag
    #         ):
    #             return "", 304

    #         response = make_response(jsonify(selectors))
    #         response.headers["Cache-Control"] = "public, max-age=3600"
    #         response.headers["Last-Modified"] = last_modified
    #         response.headers["ETag"] = etag

    #         logging.info(f"成功返回 {len(selectors)} 个 CSS 选择器。")
    #         return response

    #     except Exception as e:
    #         logging.error(f"获取 CSS 选择器列表时发生错误: {e}", exc_info=True)
    #         return jsonify({"error": "Internal server error"}), 500

    # @app.route("/css/<path:css_path>", methods=["GET"])
    # def serve_css(css_path):
    #     """
    #     CSS 样式分段动态加载 API 端点
    #     """
    #     try:
    #         CURRENT_DIR = os.path.dirname(__file__)
    #     except NameError:
    #         CURRENT_DIR = os.getcwd()

    #     CSS_FILE_PATH = os.path.join(CURRENT_DIR, "Cascading_Style_Sheets.css")
    #     try:
    #         if not css_path or not css_path.endswith(".css"):
    #             logging.warning(f"无效的 CSS 请求路径: {css_path}")
    #             return jsonify({"error": "Invalid path. Must end with .css"}), 404
    #         requested_selector_raw = css_path[:-4]
    #         if not os.path.exists(CSS_FILE_PATH):
    #             logging.error(f"CSS 文件不存在: {CSS_FILE_PATH}")
    #             return jsonify({"error": "CSS file not found"}), 500
    #         stylesheet, _ = get_parsed_stylesheet(CSS_FILE_PATH)

    #         if not stylesheet:
    #             return jsonify({"error": "Failed to parse CSS file"}), 500
    #         minify_param = request.args.get("minify", "true").lower()
    #         should_minify = minify_param in ["true", "1", "yes", ""]
    #         if should_minify:
    #             cssutils.ser.prefs.useMinified()
    #             content_type_suffix = " (minified)"
    #         else:
    #             cssutils.ser.prefs.useDefaults()
    #             content_type_suffix = " (original)"
    #         try:
    #             requested_selector_decoded = requested_selector_raw.replace(
    #                 "+~+", " ~ "
    #             )
    #             requested_selector_decoded = requested_selector_decoded.replace(
    #                 "+>+", " > "
    #             )
    #             requested_selector = requested_selector_decoded.replace("+", " ")

    #             if requested_selector_raw != requested_selector:
    #                 logging.debug(
    #                     f"CSS 选择器解码: '{requested_selector_raw}' -> '{requested_selector}'"
    #                 )

    #         except Exception as decode_err:
    #             logging.warning(
    #                 f"CSS 选择器解码失败: {decode_err}，将使用原始请求字符串"
    #             )
    #             requested_selector = requested_selector_raw

    #         if requested_selector == "Web_animation":
    #             return redirect("/Cascading_Style_Sheets_Web_animation.css")
    #         found_css_text = []
    #         for rule in stylesheet:
    #             if rule.type == cssutils.css.CSSRule.STYLE_RULE:
    #                 for selector in rule.selectorList:
    #                     if selector.selectorText.strip() == requested_selector:
    #                         found_css_text.append(rule.cssText)
    #                         break
    #         if not found_css_text:
    #             logging.warning(
    #                 f"CSS 规则未找到: {requested_selector} (原始请求: {css_path})"
    #             )
    #             return (
    #                 jsonify({"error": f"CSS rule '{requested_selector}' not found"}),
    #                 404,
    #             )
    #         content = "\n".join(found_css_text)
    #         file_mtime = os.path.getmtime(CSS_FILE_PATH)
    #         last_modified = datetime.datetime.fromtimestamp(file_mtime).strftime(
    #             "%a, %d %b %Y %H:%M:%S GMT"
    #         )
    #         etag_base = hashlib.md5(content.encode("utf-8")).hexdigest()
    #         etag = f'"{etag_base}-{"min" if should_minify else "orig"}"'
    #         if_modified_since = request.headers.get("If-Modified-Since")
    #         if_none_match = request.headers.get("If-None-Match")

    #         if (if_none_match == etag) or (
    #             not if_none_match and if_modified_since == last_modified
    #         ):
    #             logging.debug(f"CSS 使用缓存版本 (304){content_type_suffix}")
    #             return "", 304

    #         response = make_response(content)
    #         response.headers["Content-Type"] = "text/css; charset=utf-8"
    #         response.headers["Cache-Control"] = "public, max-age=3600"
    #         response.headers["Last-Modified"] = last_modified
    #         response.headers["ETag"] = etag
    #         response.headers["X-Minified"] = "true" if should_minify else "false"

    #         logging.info(
    #             f"成功返回 CSS{content_type_suffix} ({len(content)} 字符) for: {requested_selector}"
    #         )
    #         return response

    #     except Exception as e:
    #         logging.error(f"加载 CSS 时发生错误: {e}", exc_info=True)
    #         return jsonify({"error": "Internal server error"}), 500

    # @app.route("/html/<path:fragment_name>.json", methods=["GET"])
    # def serve_html_fragment(fragment_name):
    #     """
    #     HTML 片段动态加载 API 端点（支持自动压缩，从统一文件读取）
    #     """
    #     try:
    #         fragments_file = os.path.join(
    #             os.path.dirname(__file__), "html_fragments.html"
    #         )
    #         if not os.path.exists(fragments_file):
    #             logging.error(f"HTML 片段文件不存在: {fragments_file}")
    #             return jsonify({"error": "HTML fragments file not found"}), 500
    #         with open(fragments_file, "r", encoding="utf-8") as f:
    #             fragments_content = f.read()
    #         pattern = rf"<!-- 段落开始： {re.escape(fragment_name)} -->\s*(.*?)\s*<!-- 段落结束： {re.escape(fragment_name)} -->"
    #         match = re.search(pattern, fragments_content, re.DOTALL)

    #         if not match:
    #             logging.error(f"HTML 片段未找到: {fragment_name}")
    #             return (
    #                 jsonify({"error": f"HTML fragment '{fragment_name}' not found"}),
    #                 404,
    #             )
    #         original_content = match.group(1).strip()
    #         minify_param = request.args.get("minify", "true").lower()
    #         should_minify = minify_param in ["true", "1", "yes", ""]
    #         if should_minify:
    #             content = original_content
    #             content_type_suffix = " (original, compression disabled)"
    #             logging.info(
    #                 f"HTML 片段 {fragment_name} 压缩功能已禁用，返回原始大小: {len(original_content)} 字节"
    #             )
    #         else:
    #             content = original_content
    #             content_type_suffix = " (original)"
    #             logging.info(
    #                 f"HTML 片段 {fragment_name} 返回原始版本：{len(content)} 字节"
    #             )
    #         file_mtime = os.path.getmtime(fragments_file)
    #         last_modified = datetime.datetime.fromtimestamp(file_mtime).strftime(
    #             "%a, %d %b %Y %H:%M:%S GMT"
    #         )
    #         etag_base = hashlib.md5(content.encode("utf-8")).hexdigest()
    #         etag = f'"{etag_base}-{"min" if should_minify else "orig"}"'
    #         if_modified_since = request.headers.get("If-Modified-Since")
    #         if_none_match = request.headers.get("If-None-Match")

    #         if (if_modified_since == last_modified) or (if_none_match == etag):
    #             logging.debug(
    #                 f"HTML 片段 {fragment_name} 使用缓存版本 (304){content_type_suffix}"
    #             )
    #             return "", 304
    #         response = make_response(content)
    #         response.headers["Content-Type"] = "text/html; charset=utf-8"
    #         response.headers["Cache-Control"] = "public, max-age=3600"
    #         response.headers["Last-Modified"] = last_modified
    #         response.headers["ETag"] = etag
    #         response.headers["X-Minified"] = "true" if should_minify else "false"

    #         logging.info(
    #             f"成功返回 HTML 片段 {fragment_name}{content_type_suffix} ({len(content)} 字符)"
    #         )
    #         return response

    #     except Exception as e:
    #         logging.error(f"加载 HTML 片段时发生错误: {e}", exc_info=True)
    #         return jsonify({"error": "Internal server error"}), 500

    @app.route("/api/<path:method>", methods=["GET", "POST"])
    def api_call(method):
        """API调用端点：将前端调用转发到Python后端"""
        session_id = request.headers.get("X-Session-ID", "")

        if not session_id:
            return jsonify({"success": False, "message": "缺少会话ID"}), 401
        with web_sessions_lock:
            if session_id in web_sessions:
                api_instance = web_sessions[session_id]
                if (
                    hasattr(api_instance, "is_authenticated")
                    and api_instance.is_authenticated
                ):
                    if hasattr(api_instance, "is_guest") and not api_instance.is_guest:
                        username = getattr(api_instance, "auth_username", None)

                        if username:
                            token = request.cookies.get("auth_token")

                            if not token:
                                return (
                                    jsonify(
                                        {
                                            "success": False,
                                            "message": "未找到认证令牌，请重新登录",
                                            "need_login": True,
                                        }
                                    ),
                                    401,
                                )
                            is_valid, reason = token_manager.verify_token(
                                username, session_id, token
                            )

                            # 如果Token验证失败，检查是否是超级管理员在访问其他用户的会话
                            validated_user = username  # 默认验证的是会话拥有者
                            if not is_valid and reason == "token_mismatch":
                                try:
                                    # 获取超级管理员用户名
                                    super_admin = auth_system.config.get(
                                        "Admin", "super_admin", fallback="admin"
                                    )

                                    # 如果当前会话用户不是超管，尝试用超管身份验证Token
                                    if username != super_admin:
                                        is_admin_valid, admin_reason = (
                                            token_manager.verify_token(
                                                super_admin, session_id, token
                                            )
                                        )
                                        if is_admin_valid:
                                            is_valid = True
                                            validated_user = super_admin
                                            logging.info(
                                                f"[API鉴权] 上帝模式：允许管理员 {super_admin} 访问用户 {username} 的会话"
                                            )
                                except Exception as e:
                                    logging.error(f"[API鉴权] 上帝模式检查出错: {e}")

                            if not is_valid:
                                if reason == "token_expired":
                                    return (
                                        jsonify(
                                            {
                                                "success": False,
                                                "message": "令牌已过期，请重新登录",
                                                "need_login": True,
                                            }
                                        ),
                                        401,
                                    )
                                elif reason == "token_mismatch":
                                    return (
                                        jsonify(
                                            {
                                                "success": False,
                                                "message": "令牌验证失败，可能账号在其他设备登录",
                                                "need_login": True,
                                                "logged_out_elsewhere": True,
                                            }
                                        ),
                                        401,
                                    )
                                else:
                                    return (
                                        jsonify(
                                            {
                                                "success": False,
                                                "message": "令牌验证失败，请重新登录",
                                                "need_login": True,
                                            }
                                        ),
                                        401,
                                    )
                            # 刷新实际持有人(validated_user)的Token，而不是会话拥有者(username)的Token
                            # 否则管理员操作用户界面会导致管理员自己的Token过期或无法刷新
                            token_manager.refresh_token(validated_user, session_id)
        update_session_activity(session_id)

        with web_sessions_lock:
            if session_id not in web_sessions:
                state = load_session_state(session_id)
                if state and state.get("login_success"):
                    api_instance = Api(args)
                    api_instance._session_created_at = state.get(
                        "created_at", time.time()
                    )
                    api_instance._web_session_id = session_id

                    api_instance.login_success = True
                    api_instance.user_info = state.get("user_info")
                    restore_session_to_api_instance(api_instance, state)
                    web_sessions[session_id] = api_instance
                    logging.info(f"API调用时自动恢复会话: {session_id[:32]}...")
                else:
                    return (
                        jsonify({"success": False, "message": "会话已过期或无效"}),
                        401,
                    )
            api_instance = web_sessions[session_id]
        if request.method == "POST":
            params = request.get_json() or {}
        else:
            params = dict(request.args)
        try:
            # ============================================================
            # 权限检查：细粒度权限控制
            # ============================================================
            permission_required_methods = {
                # ===== 通知相关权限 =====
                "mark_notification_read": "mark_notifications_read",
                "mark_all_read": "mark_notifications_read",
                "get_notifications": "view_notifications",
                "get_cached_notifications": "view_notifications",
                # ===== 签到相关权限 =====
                "trigger_attendance": "use_attendance",
                # ===== 多账号管理相关权限 =====
                "enter_multi_account_mode": "execute_multi_account",
                "exit_multi_account_mode": "execute_multi_account",
                "multi_add_account": "execute_multi_account",
                "multi_remove_account": "execute_multi_account",
                "multi_remove_selected_accounts": "execute_multi_account",
                "multi_remove_all_accounts": "execute_multi_account",
                "multi_get_all_config_users": "execute_multi_account",
                "multi_load_accounts_from_config": "execute_multi_account",
                "multi_import_accounts": "execute_multi_account",
                "multi_export_accounts_summary": "execute_multi_account",
                "multi_download_import_template": "execute_multi_account",
                "multi_refresh_all_statuses": "execute_multi_account",
                "multi_refresh_single_status": "execute_multi_account",
                "multi_get_all_accounts_status": "execute_multi_account",
                "multi_get_account_params": "execute_multi_account",
                "multi_update_account_param": "execute_multi_account",
                "multi_start_single_account": "execute_multi_account",
                "multi_start_all_accounts": "execute_multi_account",
                "multi_stop_single_account": "execute_multi_account",
                "multi_stop_all_accounts": "execute_multi_account",
                # ===== 任务管理相关权限 =====
                "load_tasks": "view_tasks",
                "get_task_details": "view_tasks",
                "get_task_history": "view_tasks",
                "get_historical_track": "view_tasks",
                "get_run_status": "view_tasks",
                "create_task": "create_tasks",
                "delete_task": "delete_tasks",
                "start_single_run": "start_tasks",
                "start_all_runs": "start_tasks",
                "stop_run": "stop_tasks",
                "stop_current_run": "stop_tasks",
                "import_offline_file": "import_offline",
                "import_task_data": "import_offline",
                "export_offline_file": "export_data",
                "export_task_data": "export_data",
                "record_path": "record_path",
                "set_draft_path": "record_path",
                "clear_path": "record_path",
                "process_path": "record_path",
                "clear_current_task_draft": "record_path",
                "auto_generate_path": "auto_generate_path",
                "auto_generate_path_with_api": "auto_generate_path",
                "update_param": "modify_params",
                "generate_new_ua": "modify_params",
                "save_amap_key": "modify_params",
                # ===== 地图查看权限 =====
                "get_map_data": "view_map",
                # ===== 用户信息权限 =====
                "get_user_info": "view_user_details",
                "on_user_selected": "view_user_details",
                "update_user_settings": "modify_user_settings",
                # ===== 会话管理权限 =====
                "get_user_sessions": "manage_own_sessions",
                # ===== 日志权限 =====
                "get_logs": "view_logs",
                "clear_logs": "clear_logs",
            }

            if method in permission_required_methods:
                required_permission = permission_required_methods[method]
                if hasattr(api_instance, "auth_username"):
                    if not auth_system.check_permission(
                        api_instance.auth_username, required_permission
                    ):
                        return (
                            jsonify(
                                {
                                    "success": False,
                                    "message": f"权限不足：需要 {required_permission} 权限",
                                }
                            ),
                            403,
                        )
                else:
                    return jsonify({"success": False, "message": "请先登录认证"}), 401

            # ============================================================
            # 记录get_initial_data调用时的会话活跃时间
            # ============================================================
            if method == "get_initial_data":
                update_session_activity(session_id)
                logging.debug(
                    f"会话 {session_id} 调用 get_initial_data，更新活跃时间戳"
                )

            if hasattr(api_instance, method):
                func = getattr(api_instance, method)
                logging.debug(
                    f"API调用: 方法={method}, 参数类型={type(params)}, 参数内容={str(params)[:200]}"
                )

                if params:
                    result = (
                        func(**params) if isinstance(params, dict) else func(*params)
                    )
                else:
                    result = func()

                if method == "on_user_selected" and result and isinstance(result, dict):
                    has_auto_fill = False
                    if hasattr(api_instance, "auth_username"):
                        has_auto_fill = auth_system.check_permission(
                            api_instance.auth_username, "auto_fill_password"
                        )
                    if not has_auto_fill:
                        result["password"] = ""
                auto_save_methods = [
                    "login",
                    "logout",
                    "load_tasks",
                    "select_task",
                    "start_single_run",
                    "start_all_runs",
                    "stop_current_run",
                    "import_offline_file",
                    "export_offline_file",
                    "record_path",
                    "auto_generate_path",
                    "process_path",
                    "clear_path",
                    "update_param",
                    "generate_new_ua",
                    "enter_multi_account_mode",
                    "exit_multi_account_mode",
                    "enter_single_account_mode",
                    "multi_add_account",
                    "multi_remove_account",
                ]
                if method in auto_save_methods:
                    save_session_state(session_id, api_instance)
                    logging.debug(f"API '{method}' 调用后自动保存会话状态")
                response = jsonify(result if result is not None else {"success": True})
                if (
                    hasattr(api_instance, "is_authenticated")
                    and api_instance.is_authenticated
                ):
                    if hasattr(api_instance, "is_guest") and not api_instance.is_guest:
                        token = request.cookies.get("auth_token")
                        if token:
                            response.set_cookie(
                                "auth_token",
                                value=token,
                                max_age=3600,
                                httponly=True,
                                secure=False,
                                samesite="Lax",
                            )

                return response
            else:
                return (
                    jsonify({"success": False, "message": f"未知的API方法: {method}"}),
                    404,
                )
        except Exception as e:
            logging.error(f"API调用失败 {method}: {e}", exc_info=True)
            return jsonify({"success": False, "message": "服务器内部错误"}), 500

    @app.route("/execute_js", methods=["POST"])
    def execute_js():
        """在服务器端Chrome中执行JavaScript代码"""
        session_id = request.headers.get("X-Session-ID", "")

        if not session_id:
            return jsonify({"success": False, "message": "缺少会话ID"}), 401
        data = request.get_json() or {}
        script = data.get("script", "")
        args_list = data.get("args", [])

        if not script:
            return jsonify({"success": False, "message": "缺少script参数"}), 400

        try:
            result = chrome_pool.execute_js(session_id, script, *args_list)
            return jsonify({"success": True, "result": result})
        except Exception as e:
            logging.error(f"执行JS失败: {e}")
            return jsonify({"success": False, "message": "JS执行失败"}), 500

    @app.route("/api/background_task/start", methods=["POST"])
    def start_background_task():
        """启动后台任务执行"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "会话无效或未登录"}), 401

        data = request.get_json() or {}
        task_indices = data.get("task_indices", [])
        auto_generate = data.get("auto_generate", False)

        if not task_indices:
            return jsonify({"success": False, "message": "未指定任务"}), 400

        api_instance = web_sessions[session_id]
        result = background_task_manager.start_background_task(
            session_id, api_instance, task_indices, auto_generate
        )
        return jsonify(result)

    @app.route("/api/background_task/status", methods=["GET"])
    def get_background_task_status():
        """获取后台任务状态"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id:
            return jsonify({"success": False, "message": "缺少会话ID"}), 401

        task_status = background_task_manager.get_task_status(session_id)
        if task_status:
            return jsonify({"success": True, "task_status": task_status})
        else:
            return jsonify({"success": False, "message": "未找到后台任务"})

    @app.route("/api/background_task/stop", methods=["POST"])
    def stop_background_task():
        """停止后台任务"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "会话无效或未登录"}), 401
        try:
            with web_sessions_lock:
                if session_id in web_sessions:
                    api_instance = web_sessions[session_id]
                    if hasattr(api_instance, "stop_run_flag"):
                        api_instance.stop_run_flag.set()
                        logging.info(
                            f"已为会话 {session_id[:8]}... 设置 api_instance.stop_run_flag 停止标志"
                        )
                    else:
                        logging.warning(
                            f"会话 {session_id[:8]}... 的 Api 实例缺少 stop_run_flag 属性"
                        )
                else:
                    logging.warning(
                        f"无法在 web_sessions 中找到会话 {session_id[:8]}... 来设置停止标志"
                    )
        except Exception as e:
            logging.error(f"设置 stop_run_flag 时出错: {e}", exc_info=True)

        result = background_task_manager.stop_task(session_id)
        return jsonify(result)

    # ========== 留言板API ========== #

    @app.route("/api/messages/list", methods=["GET"])
    def get_messages():
        """获取留言列表"""
        # ============================================================
        # IP封禁检查：留言板功能专项封禁
        # ============================================================
        client_ip = request.remote_addr
        if check_ip_ban(client_ip, scope="messages_only"):
            logging.warning(
                f"[IP封禁] 留言功能封禁拦截：IP {client_ip} 尝试访问 /api/messages/list"
            )
            return (
                jsonify({"success": False, "message": "您的IP已被限制访问留言功能"}),
                403,
            )
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "view_messages"):
            return jsonify({"success": False, "message": "无权查看留言"}), 403
        messages_file = "messages.json"
        messages = []

        if os.path.exists(messages_file):
            try:
                with open(messages_file, "r", encoding="utf-8") as f:
                    messages = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logging.error(f"[留言板] 读取留言失败: {e}")
                messages = []

        # --- 实时数据扩充 ---
        enriched_messages = []
        for msg in messages:
            enriched_msg = msg.copy()

            msg_auth_username = msg.get("auth_username")
            msg_ip = msg.get("ip")
            msg_is_guest = msg.get("is_guest", True)
            enriched_msg["ip_city"] = get_ip_location(msg_ip)
            if not msg_is_guest and msg_auth_username:
                user_details = auth_system.get_user_details(msg_auth_username)
                if user_details:
                    enriched_msg["nickname"] = user_details.get(
                        "nickname", msg_auth_username
                    )
                    enriched_msg["avatar_url"] = user_details.get(
                        "avatar_url", "default_avatar.png"
                    )
                else:
                    enriched_msg["nickname"] = f"{msg_auth_username} (已注销)"
                    enriched_msg["avatar_url"] = "default_avatar.png"
            else:
                enriched_msg["nickname"] = (
                    msg.get("nickname") or msg.get("email") or "游客"
                )
                enriched_msg["avatar_url"] = "default_avatar.png"

            enriched_messages.append(enriched_msg)
        enriched_messages.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        return jsonify({"success": True, "messages": enriched_messages})

    # ============================================================
    # 任务15：IP归属地获取辅助函数
    # ============================================================
    global get_ip_location

    def get_ip_location(ip_address):
        """
        获取IP地址的地理位置信息 (带1天缓存)
        """
        if not ip_address:
            return "未知"

        current_time = time.time()
        with ip_cache_lock:
            cached_entry = ip_location_cache.get(ip_address)

        if cached_entry:
            timestamp = cached_entry.get("timestamp", 0)
            location = cached_entry.get("location")
            if (current_time - timestamp < CACHE_DURATION_SECONDS) and location:
                logging.debug(f"[IP缓存] 命中: ip={ip_address}, 位置={location}")
                return location
            else:
                logging.debug(f"[IP缓存] 过期: ip={ip_address}")
        try:
            config_file = os.path.join(os.path.dirname(__file__), "config.ini")
            api_key = ""
            if os.path.exists(config_file):
                try:
                    cfg = configparser.ConfigParser()
                    cfg.read(config_file, encoding="utf-8")
                    api_key = cfg.get("API", "ip_api_key", fallback="")
                except Exception as e:
                    logging.debug(f"[IP定位] 读取配置文件失败: {e}")

            if api_key and api_key != "your_api_key_here" and api_key.strip() != "":
                api_url = (
                    f"https://api.vore.top/api/IPdata?key={api_key}&ip={ip_address}"
                )
            else:
                api_url = f"https://api.vore.top/api/IPdata?ip={ip_address}"
            response = requests.get(api_url, timeout=5)
            data = response.json()

            code = data.get("code")
            msg = data.get("msg", "")

            if code != 200:
                logging.warning(
                    f"[IP定位] API返回错误码: code={code}, msg={msg}, ip={ip_address}"
                )
                return "未知"

            ipdata = data.get("ipdata", {})

            info1 = ipdata.get("info1", "").strip()
            info2 = ipdata.get("info2", "").strip()
            info3 = ipdata.get("info3", "").strip()
            isp = ipdata.get("isp", "").strip()

            location_parts = [info1, info2, info3, isp]

            seen = {}
            unique_parts = []

            for part in location_parts:
                if part and part not in seen:
                    seen[part] = True
                    unique_parts.append(part)

            if unique_parts:
                location_str = " ".join(unique_parts)
                logging.debug(
                    f"[IP定位] 成功获取: ip={ip_address}, 位置={location_str}"
                )
                with ip_cache_lock:
                    ip_location_cache[ip_address] = {
                        "location": location_str,
                        "timestamp": current_time,
                    }
                _save_ip_cache()

                return location_str
            else:
                logging.warning(f"[IP定位] API返回空数据: ip={ip_address}")
                return "未知"

        except requests.exceptions.Timeout:
            logging.warning(f"[IP定位] 请求超时: ip={ip_address}")
            return "未知"
        except requests.exceptions.RequestException as e:
            logging.warning(f"[IP定位] 网络请求失败: ip={ip_address}, 错误={str(e)}")
            return "未知"
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            logging.warning(f"[IP定位] 数据解析失败: ip={ip_address}, 错误={str(e)}")
            return "未知"
        except Exception as e:
            logging.error(
                f"[IP定位] 未知错误: ip={ip_address}, 错误={str(e)}", exc_info=True
            )
            return "未知"

    @app.route("/api/messages/post", methods=["POST"])
    def post_message():
        """发表留言"""
        # ============================================================
        # IP封禁检查：留言板功能专项封禁
        # ============================================================
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.remote_addr

        if check_ip_ban(client_ip, scope="messages_only"):
            logging.warning(f"[IP封禁] 留言功能封禁拦截：IP {client_ip} 尝试发表留言")
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")

        if not auth_system.check_permission(auth_username, "post_messages"):
            return jsonify({"success": False, "message": "无权发表留言"}), 403

        data = request.json
        content = data.get("content", "").strip()
        email = data.get("email", "").strip()
        nickname = data.get("nickname", "").strip()
        if not content:
            return jsonify({"success": False, "message": "留言内容不能为空"})

        if len(content) > 1000:
            return jsonify({"success": False, "message": "留言内容不能超过1000字"})
        is_guest = auth_username == "guest" or not auth_username
        if is_guest:
            if not email:
                return jsonify({"success": False, "message": "游客必须填写邮箱"})
            if not nickname:
                return jsonify({"success": False, "message": "游客必须设置昵称"})
            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_pattern, email):
                return jsonify({"success": False, "message": "邮箱格式不正确"})

        # ============================================================
        # 任务15：获取用户信息（昵称、头像）和IP归属地
        # 为留言添加更丰富的用户信息和位置信息
        # ============================================================
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.remote_addr
        ip_city = get_ip_location(client_ip)
        user_nickname = nickname
        avatar_url = "default_avatar.png"

        if not is_guest and auth_username:
            try:
                user_hash = hashlib.sha256(auth_username.encode()).hexdigest()
                user_file = os.path.join(SYSTEM_ACCOUNTS_DIR, f"{user_hash}.json")

                if os.path.exists(user_file):
                    with open(user_file, "r", encoding="utf-8") as f:
                        user_data = json.load(f)
                        user_nickname = user_data.get("nickname", auth_username)
                        avatar_url = user_data.get("avatar_url") or "default_avatar.png"
            except Exception as e:
                logging.warning(f"[留言板] 读取用户信息失败: {str(e)}")
                user_nickname = auth_username
        message = {
            "id": str(uuid.uuid4()),
            "content": content,
            "auth_username": (auth_username if not is_guest else None),
            "nickname": nickname if is_guest else None,
            "email": email if is_guest else None,
            "is_guest": is_guest,
            "timestamp": time.time(),
            "ip": client_ip,
        }
        messages_file = "messages.json"
        messages = []

        if os.path.exists(messages_file):
            try:
                with open(messages_file, "r", encoding="utf-8") as f:
                    messages = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logging.error(f"[留言板] 读取留言失败: {e}")
                messages = []
        messages.append(message)
        try:
            with open(messages_file, "w", encoding="utf-8") as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)

            logging.info(
                f"[留言板] 新留言 --> 用户: {auth_username}, 昵称: {nickname}, 内容长度: {len(content)}字"
            )
            return jsonify(
                {
                    "success": True,
                    "message": "留言发表成功",
                    "message_id": message["id"],
                }
            )
        except OSError as e:
            logging.error(f"[留言板] 保存留言失败: {e}")
            return jsonify({"success": False, "message": "保存留言失败"}), 500

    @app.route("/api/messages/delete", methods=["POST"])
    def delete_message():
        """删除留言"""
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未登录"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")

        data = request.json
        message_id = data.get("message_id", "").strip()

        if not message_id:
            return jsonify({"success": False, "message": "留言ID不能为空"})
        messages_file = "messages.json"
        messages = []

        if os.path.exists(messages_file):
            try:
                with open(messages_file, "r", encoding="utf-8") as f:
                    messages = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logging.error(f"[留言板] 读取留言失败: {e}")
                return jsonify({"success": False, "message": "读取留言失败"}), 500
        message_to_delete = None
        for msg in messages:
            if msg.get("id") == message_id:
                message_to_delete = msg
                break

        if not message_to_delete:
            return jsonify({"success": False, "message": "留言不存在"})
        can_delete_any = auth_system.check_permission(
            auth_username, "delete_any_messages"
        )
        can_delete_own = auth_system.check_permission(
            auth_username, "delete_own_messages"
        )
        is_own_message = message_to_delete.get(
            "auth_username"
        ) == auth_username and not message_to_delete.get("is_guest")

        if can_delete_any:
            pass
        elif can_delete_own and is_own_message:
            pass
        else:
            return jsonify({"success": False, "message": "无权删除此留言"}), 403
        messages = [msg for msg in messages if msg.get("id") != message_id]
        try:
            with open(messages_file, "w", encoding="utf-8") as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)

            logging.info(
                f"[留言板] 删除留言 --> 操作用户: {auth_username}, 留言ID: {message_id}"
            )
            return jsonify({"success": True, "message": "留言已删除"})
        except OSError as e:
            logging.error(f"[留言板] 保存留言失败: {e}")
            return jsonify({"success": False, "message": "保存留言失败"}), 500

    # ============================================================
    # 任务22：高德地图Key验证API
    # 用于验证用户输入的高德地图API Key是否有效
    # ============================================================
    @app.route("/api/validate_amap_key", methods=["POST"])
    def validate_amap_key():
        """
        验证高德地图API Key的有效性
        """
        try:
            data = request.get_json() or {}
            amap_key = data.get("key", "").strip()
            if not amap_key:
                return jsonify({"success": False, "message": "API Key不能为空"})
            import requests

            test_url = f"https://restapi.amap.com/v3/geocode/regeo?location=116.397428,39.90923&key={amap_key}"
            response = requests.get(test_url, timeout=5)
            result = response.json()
            if result.get("status") == "1":
                return jsonify(
                    {"success": True, "message": "API Key验证成功，该Key有效"}
                )
            else:
                error_info = result.get("info", "未知错误")
                return jsonify(
                    {"success": False, "message": f"API Key无效: {error_info}"}
                )

        except requests.exceptions.Timeout:
            return jsonify({"success": False, "message": "验证超时，请检查网络连接"})
        except requests.exceptions.RequestException as e:
            return jsonify({"success": False, "message": f"网络请求失败: {str(e)}"})
        except Exception as e:
            logging.error(f"[高德Key验证] 验证失败: {str(e)}")
            return jsonify({"success": False, "message": f"验证失败: {str(e)}"})

    # ============================================================
    # 定时提醒功能API
    # 用于管理定时提醒，在特定时间段弹出提示
    # ============================================================

    @app.route("/api/reminders/list", methods=["GET"])
    def get_reminders_list():
        """
        获取所有提醒列表
        """
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未授权访问，请先登录"}), 401
        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "view_logs"):
            return (
                jsonify(
                    {"success": False, "message": "权限不足，仅管理员可以管理提醒"}
                ),
                403,
            )

        try:
            reminders_file = "reminders.json"
            reminders = []
            if os.path.exists(reminders_file):
                with open(reminders_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    reminders = data.get("reminders", [])
            reminders.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            logging.info(
                f"[定时提醒] 用户 {auth_username} 获取提醒列表，共 {len(reminders)} 条"
            )
            return jsonify({"success": True, "reminders": reminders})

        except json.JSONDecodeError as e:
            logging.error(f"[定时提醒] JSON解析失败: {e}")
            return jsonify({"success": False, "message": "提醒数据文件格式错误"}), 500

        except Exception as e:
            logging.error(f"[定时提醒] 获取提醒列表失败: {e}", exc_info=True)
            return (
                jsonify({"success": False, "message": f"获取提醒列表失败: {str(e)}"}),
                500,
            )

    @app.route("/api/reminders/add", methods=["POST"])
    def add_reminder():
        """
        添加新提醒
        """
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未授权访问"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")
        if not auth_system.check_permission(auth_username, "view_logs"):
            return jsonify({"success": False, "message": "权限不足"}), 403

        try:
            data = request.get_json() or {}
            title = data.get("title", "").strip()
            message = data.get("message", "").strip()
            start_time = data.get("start_time", "").strip()
            end_time = data.get("end_time", "").strip()
            enabled = data.get("enabled", True)
            # ===== 数据验证 =====
            if not title:
                return jsonify({"success": False, "message": "提醒标题不能为空"})
            if len(title) > 50:
                return jsonify(
                    {"success": False, "message": "提醒标题不能超过50个字符"}
                )
            if not message:
                return jsonify({"success": False, "message": "提醒内容不能为空"})
            if len(message) > 500:
                return jsonify(
                    {"success": False, "message": "提醒内容不能超过500个字符"}
                )
            time_pattern = re.compile(r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$")
            if not time_pattern.match(start_time):
                return jsonify(
                    {
                        "success": False,
                        "message": "开始时间格式错误，应为 HH:MM（如 19:00）",
                    }
                )
            if not time_pattern.match(end_time):
                return jsonify(
                    {
                        "success": False,
                        "message": "结束时间格式错误，应为 HH:MM（如 20:00）",
                    }
                )
            if not isinstance(enabled, bool):
                enabled = bool(enabled)

            # ===== 创建提醒对象 =====

            reminder_id = str(uuid.uuid4())
            current_timestamp = time.time()

            new_reminder = {
                "id": reminder_id,
                "title": title,
                "message": message,
                "start_time": start_time,
                "end_time": end_time,
                "enabled": enabled,
                "created_at": current_timestamp,
                "updated_at": current_timestamp,
            }

            # ===== 保存到文件 =====

            reminders_file = "reminders.json"
            reminders = []
            if os.path.exists(reminders_file):
                try:
                    with open(reminders_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        reminders = data.get("reminders", [])
                except (json.JSONDecodeError, OSError):
                    reminders = []
            reminders.append(new_reminder)
            with open(reminders_file, "w", encoding="utf-8") as f:
                json.dump({"reminders": reminders}, f, indent=2, ensure_ascii=False)
            logging.info(
                f"[定时提醒] 用户 {auth_username} 添加提醒: {title} ({start_time}-{end_time})"
            )
            return jsonify(
                {"success": True, "message": "提醒添加成功", "reminder_id": reminder_id}
            )

        except Exception as e:
            logging.error(f"[定时提醒] 添加提醒失败: {e}", exc_info=True)
            return (
                jsonify({"success": False, "message": f"添加提醒失败: {str(e)}"}),
                500,
            )

    @app.route("/api/reminders/update", methods=["POST"])
    def update_reminder():
        """
        更新现有提醒
        """
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未授权访问"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")

        if not auth_system.check_permission(auth_username, "view_logs"):
            return jsonify({"success": False, "message": "权限不足"}), 403

        try:
            data = request.get_json() or {}
            reminder_id = data.get("id", "").strip()
            if not reminder_id:
                return jsonify({"success": False, "message": "提醒ID不能为空"})
            reminders_file = "reminders.json"
            if not os.path.exists(reminders_file):
                return jsonify({"success": False, "message": "提醒文件不存在"}), 404

            with open(reminders_file, "r", encoding="utf-8") as f:
                reminders_data = json.load(f)
                reminders = reminders_data.get("reminders", [])
            reminder_found = False
            for reminder in reminders:
                if reminder.get("id") == reminder_id:
                    reminder_found = True
                    if "title" in data:
                        title = data["title"].strip()
                        if not title:
                            return jsonify(
                                {"success": False, "message": "标题不能为空"}
                            )
                        if len(title) > 50:
                            return jsonify(
                                {"success": False, "message": "标题不能超过50个字符"}
                            )
                        reminder["title"] = title

                    if "message" in data:
                        message = data["message"].strip()
                        if not message:
                            return jsonify(
                                {"success": False, "message": "内容不能为空"}
                            )
                        if len(message) > 500:
                            return jsonify(
                                {"success": False, "message": "内容不能超过500个字符"}
                            )
                        reminder["message"] = message

                    if "start_time" in data:
                        start_time = data["start_time"].strip()
                        time_pattern = re.compile(r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$")
                        if not time_pattern.match(start_time):
                            return jsonify(
                                {"success": False, "message": "开始时间格式错误"}
                            )
                        reminder["start_time"] = start_time

                    if "end_time" in data:
                        end_time = data["end_time"].strip()
                        time_pattern = re.compile(r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$")
                        if not time_pattern.match(end_time):
                            return jsonify(
                                {"success": False, "message": "结束时间格式错误"}
                            )
                        reminder["end_time"] = end_time

                    if "enabled" in data:
                        reminder["enabled"] = bool(data["enabled"])
                    reminder["updated_at"] = time.time()

                    break

            if not reminder_found:
                return jsonify({"success": False, "message": "提醒不存在"}), 404
            with open(reminders_file, "w", encoding="utf-8") as f:
                json.dump({"reminders": reminders}, f, indent=2, ensure_ascii=False)

            logging.info(f"[定时提醒] 用户 {auth_username} 更新提醒: {reminder_id}")

            return jsonify({"success": True, "message": "提醒更新成功"})

        except Exception as e:
            logging.error(f"[定时提醒] 更新提醒失败: {e}", exc_info=True)
            return (
                jsonify({"success": False, "message": f"更新提醒失败: {str(e)}"}),
                500,
            )

    @app.route("/api/reminders/delete", methods=["POST"])
    def delete_reminder():
        """
        删除提醒
        """
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未授权访问"}), 401

        api_instance = web_sessions[session_id]
        auth_username = getattr(api_instance, "auth_username", "")

        if not auth_system.check_permission(auth_username, "view_logs"):
            return jsonify({"success": False, "message": "权限不足"}), 403

        try:
            data = request.get_json() or {}
            reminder_id = data.get("id", "").strip()

            if not reminder_id:
                return jsonify({"success": False, "message": "提醒ID不能为空"})
            reminders_file = "reminders.json"
            if not os.path.exists(reminders_file):
                return jsonify({"success": False, "message": "提醒文件不存在"}), 404

            with open(reminders_file, "r", encoding="utf-8") as f:
                reminders_data = json.load(f)
                reminders = reminders_data.get("reminders", [])
            original_count = len(reminders)
            reminders = [r for r in reminders if r.get("id") != reminder_id]

            if len(reminders) == original_count:
                return jsonify({"success": False, "message": "提醒不存在"}), 404

            with open(reminders_file, "w", encoding="utf-8") as f:
                json.dump({"reminders": reminders}, f, indent=2, ensure_ascii=False)

            logging.info(f"[定时提醒] 用户 {auth_username} 删除提醒: {reminder_id}")

            return jsonify({"success": True, "message": "提醒删除成功"})

        except Exception as e:
            logging.error(f"[定时提醒] 删除提醒失败: {e}", exc_info=True)
            return (
                jsonify({"success": False, "message": f"删除提醒失败: {str(e)}"}),
                500,
            )

    @app.route("/api/reminders/check", methods=["GET"])
    def check_reminders():
        """
        检查当前时间是否有需要显示的提醒
        """
        try:
            from datetime import datetime

            current_time_str = datetime.now().strftime("%H:%M")
            reminders_file = "reminders.json"
            if not os.path.exists(reminders_file):
                return jsonify({"success": True, "reminders": []})
            with open(reminders_file, "r", encoding="utf-8") as f:
                reminders_data = json.load(f)
                all_reminders = reminders_data.get("reminders", [])
            active_reminders = []
            for reminder in all_reminders:
                if not reminder.get("enabled", False):
                    continue
                start_time = reminder.get("start_time", "")
                end_time = reminder.get("end_time", "")
                if not start_time or not end_time:
                    continue
                if _is_time_in_range(current_time_str, start_time, end_time):
                    active_reminders.append(
                        {
                            "id": reminder.get("id"),
                            "title": reminder.get("title"),
                            "message": reminder.get("message"),
                        }
                    )
            return jsonify({"success": True, "reminders": active_reminders})

        except Exception as e:
            logging.error(f"[定时提醒] 检查提醒失败: {e}", exc_info=True)
            return (
                jsonify({"success": False, "message": f"检查提醒失败: {str(e)}"}),
                500,
            )

    def _is_time_in_range(current_time, start_time, end_time):
        """
        辅助函数：判断当前时间是否在指定的时间范围内
        """
        try:

            def time_to_minutes(time_str):
                """将HH:MM格式的时间转换为从00:00开始的分钟数"""
                hours, minutes = map(int, time_str.split(":"))
                return hours * 60 + minutes

            current_minutes = time_to_minutes(current_time)
            start_minutes = time_to_minutes(start_time)
            end_minutes = time_to_minutes(end_time)
            if start_minutes < end_minutes:
                return start_minutes <= current_minutes < end_minutes
            elif start_minutes > end_minutes:
                return current_minutes >= start_minutes or current_minutes < end_minutes
            else:
                return False
        except Exception as e:
            logging.warning(f"[定时提醒] 时间范围判断失败: {e}")
            return False

    # ============================================================
    # 验证码功能API
    # 用于获取和验证图形验证码，增强系统安全性
    # ============================================================

    @app.route("/api/captcha/get", methods=["GET"])
    def get_captcha():
        """
        获取验证码接口 【本地验证码生成器】
        """
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id:
            return jsonify({"success": False, "message": "缺少会话ID"}), 401

        try:
            config_file = os.path.join(os.path.dirname(__file__), "config.ini")
            length = 4
            scale_factor = 2
            noise_level = 0.08

            if os.path.exists(config_file):
                try:
                    cfg = configparser.ConfigParser()
                    cfg.read(config_file, encoding="utf-8")
                    length = int(cfg.get("Captcha", "length", fallback="4"))
                    scale_factor = int(cfg.get("Captcha", "scale_factor", fallback="2"))
                    noise_level = float(
                        cfg.get("Captcha", "noise_level", fallback="0.08")
                    )
                    logging.debug(
                        f"[本地验证码] 从config.ini读取参数: length={length}, scale_factor={scale_factor}, noise_level={noise_level}"
                    )
                except Exception as e:
                    logging.warning(f"[本地验证码] 读取配置文件失败，使用默认值: {e}")
            generator = MicroPixelCaptcha()
            captcha_code, captcha_html, captcha_width, captcha_height = (
                generator.generate(
                    length=length, scale_factor=scale_factor, noise_level=noise_level
                )
            )

            logging.debug(
                f"[本地验证码] 已生成验证码，长度={length}，答案={captcha_code}，尺寸={captcha_width}x{captcha_height}"
            )
            if not captcha_html or not captcha_code:
                logging.error(
                    f"[本地验证码] 生成数据不完整: html={bool(captcha_html)}, code={bool(captcha_code)}"
                )
                return jsonify({"success": False, "message": "验证码生成失败"}), 500
            import uuid

            captcha_id = str(uuid.uuid4())
            captchas_dir = os.path.join(LOGIN_LOGS_DIR, "captchas")
            os.makedirs(captchas_dir, exist_ok=True)
            captcha_data = {
                "id": captcha_id,
                "code": captcha_code.upper(),
                "html": captcha_html,
                "session_id": session_id,
                "timestamp": time.time(),
                "expires_at": time.time() + 600,
            }

            captcha_file = os.path.join(captchas_dir, f"{captcha_id}.json")
            with open(captcha_file, "w", encoding="utf-8") as f:
                json.dump(captcha_data, f, indent=2, ensure_ascii=False)

            def log_captcha_history(
                p_captcha_id, p_code, p_html, p_session_id, p_client_ip, p_user_agent
            ):
                try:
                    history_dir = os.path.join(LOGIN_LOGS_DIR, "captcha_history")
                    os.makedirs(history_dir, exist_ok=True)
                    history_data = {
                        "captcha_id": p_captcha_id,
                        "code": p_code.upper(),
                        "html": p_html,
                        "session_id": p_session_id,
                        "client_ip": p_client_ip,
                        "user_agent": p_user_agent,
                        "timestamp": time.time(),
                        "timestamp_readable": datetime.datetime.fromtimestamp(
                            time.time()
                        ).strftime("%Y-%m-%d %H:%M:%S"),
                        "expires_at": time.time() + 600,
                        "status": "created",
                        "verified_at": None,
                        "verified_input": None,
                    }
                    date_str = datetime.datetime.now().strftime("%Y%m%d")
                    history_file = os.path.join(
                        history_dir, f"captcha_history_{date_str}.jsonl"
                    )
                    with open(history_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(history_data, ensure_ascii=False) + "\n")

                    logging.debug(
                        f"[验证码历史] 已记录验证码请求: ID={p_captcha_id[:8]}..."
                    )
                except Exception as e:
                    logging.error(f"[验证码历史] 记录历史失败: {e}", exc_info=True)

            import threading

            client_ip_data = (
                request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
            )
            user_agent_data = request.headers.get("User-Agent", "unknown")
            threading.Thread(
                target=log_captcha_history,
                args=(
                    captcha_id,
                    captcha_code,
                    captcha_html,
                    session_id,
                    client_ip_data,
                    user_agent_data,
                ),
                daemon=True,
            ).start()

            def cleanup_expired_captchas():
                try:
                    current_time = time.time()
                    for filename in os.listdir(captchas_dir):
                        if filename.endswith(".json"):
                            file_path = os.path.join(captchas_dir, filename)
                            try:
                                with open(file_path, "r", encoding="utf-8") as f:
                                    data = json.load(f)
                                if data.get("expires_at", 0) < current_time:
                                    os.remove(file_path)
                                    logging.debug(
                                        f"[验证码清理] 删除过期验证码: {filename}"
                                    )
                            except Exception as e:
                                logging.warning(
                                    f"[验证码清理] 处理文件 {filename} 时出错: {e}"
                                )
                except Exception as e:
                    logging.error(f"[验证码清理] 清理过期验证码失败: {e}")

            import threading

            threading.Thread(target=cleanup_expired_captchas, daemon=True).start()
            if session_id and str(session_id).lower() not in ("null", "undefined", ""):
                logging.info(
                    f"[本地验证码] 已生成验证码 ID: {captcha_id} 会话: {session_id} 长度: {length} 尺寸: {captcha_width}x{captcha_height}px"
                )
            else:
                logging.info(
                    f"[本地验证码] 已生成验证码 ID: {captcha_id} 会话: 未知 长度: {length} 尺寸: {captcha_width}x{captcha_height}px"
                )
            return jsonify(
                {
                    "success": True,
                    "html": captcha_html,
                    "captcha_id": captcha_id,
                    "width": captcha_width,
                    "height": captcha_height,
                }
            )

        except ImportError as e:
            logging.error(f"[本地验证码] 导入MicroPixelCaptcha失败: {str(e)}")
            return jsonify({"success": False, "message": "验证码生成器加载失败"}), 500
        except (ValueError, KeyError, TypeError) as e:
            logging.error(f"[本地验证码] 数据处理失败: {str(e)}")
            return jsonify({"success": False, "message": "验证码数据处理错误"}), 500
        except Exception as e:
            logging.error(f"[本地验证码] 未知错误: {str(e)}", exc_info=True)
            return jsonify({"success": False, "message": "生成验证码时发生错误"}), 500

    @app.route("/api/captcha/html/<captcha_id>", methods=["GET"])
    def get_captcha_html_page(captcha_id):
        """
        获取验证码HTML页面（用于iframe嵌入）
        """

        def get_full_html_for_error(message):
            full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
        <meta charset="UTF-8">
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>跑步助手图形化验证码</title>
    <style>
        body {{
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }}
    </style>
</head>
<body>
    <p style="color: red; text-align: center; padding: 20px;">{message}</p>
</body>
</html>"""
            return full_html

        if not captcha_id:
            logging.warning("[验证码HTML页面] 请求缺少验证码ID")
            return get_full_html_for_error("验证码ID无效"), 400

        target_width = request.args.get("width", type=int, default=None)

        if target_width is not None:
            if target_width <= 0:
                logging.warning(
                    f"[移动端验证码缩放] 无效的width参数: {target_width} (必须 > 0)，使用原始HTML"
                )
                target_width = None
            elif target_width < 100:
                logging.warning(
                    f"[移动端验证码缩放] width参数过小: {target_width} (建议 >= 100)，使用原始HTML"
                )
                target_width = None

        captchas_dir = os.path.join("logs", "captchas")
        captcha_file = os.path.join(captchas_dir, f"{captcha_id}.json")

        if not os.path.exists(captcha_file):
            logging.warning(f"[验证码HTML页面] 验证码文件不存在: {captcha_id[:8]}...")
            return get_full_html_for_error("验证码不存在或已过期"), 404

        try:

            with open(captcha_file, "r", encoding="utf-8") as f:
                captcha_data = json.load(f)

            current_time = time.time()
            expires_at = captcha_data.get("expires_at", 0)
            if expires_at < current_time:
                logging.info(
                    f"[验证码HTML页面] 验证码已过期: {captcha_id[:8]}... (过期时间: {expires_at}, 当前时间: {current_time})"
                )
                return get_full_html_for_error("验证码已过期，请刷新"), 410

            captcha_html_content = captcha_data.get("html", "")

            if not captcha_html_content:
                logging.error(
                    f"[验证码HTML页面] 验证码HTML内容为空: {captcha_id[:8]}..."
                )
                return get_full_html_for_error("验证码内容不可用"), 404

            if target_width is not None:
                captcha_html_content = resize_captcha_html(
                    captcha_html_content, target_width
                )

            # ========================================
            # 构建完整的HTML5页面
            # ========================================
            full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!-- 【CDN缓存修复】禁用缓存的meta标签，确保验证码每次都是最新的 -->
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>跑步助手图形化验证码</title>
    <style>
        /* 【CDN缓存修复】响应式样式，确保验证码在iframe中正确显示 */
        body {{
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 80px;
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }}
        /* 确保验证码图片响应式显示，不超出iframe边界 */
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            image-rendering: crisp-edges; /* 优化图片渲染，避免模糊 */
        }}
    </style>
</head>
<body>
    <!-- 【CDN缓存修复】验证码HTML内容，通常是包含base64图片的<img>标签 -->
    {captcha_html_content}
</body>
</html>"""

            # ========================================
            # 设置HTTP响应头，强制禁用缓存
            # ========================================
            response = make_response(full_html)
            response.headers["Content-Type"] = "text/html; charset=utf-8"
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            logging.debug(f"[验证码HTML页面] 成功返回验证码HTML: {captcha_id}")

            return response

        except json.JSONDecodeError as e:
            logging.error(f"[验证码HTML页面] JSON解析失败: {captcha_id} - {e}")
            return (
                '<html><body><p style="color: red; text-align: center; padding: 20px;">验证码数据损坏</p></body></html>',
                500,
            )

        except IOError as e:
            logging.error(f"[验证码HTML页面] 文件读取失败: {captcha_id} - {e}")
            return (
                '<html><body><p style="color: red; text-align: center; padding: 20px;">读取验证码失败</p></body></html>',
                500,
            )

        except Exception as e:
            logging.error(
                f"[验证码HTML页面] 未知错误: {captcha_id} - {e}", exc_info=True
            )
            return (
                '<html><body><p style="color: red; text-align: center; padding: 20px;">读取验证码时发生错误</p></body></html>',
                500,
            )

    def verify_captcha(captcha_id, user_input):
        """
        验证验证码辅助函数
        """
        if not captcha_id or not captcha_id.strip():
            return False, "验证码ID不能为空"
        if not user_input or not user_input.strip():
            return False, "验证码不能为空"
        captchas_dir = os.path.join("logs", "captchas")
        captcha_file = os.path.join(captchas_dir, f"{captcha_id}.json")
        if not os.path.exists(captcha_file):
            return False, "验证码不存在或已失效"

        try:
            with open(captcha_file, "r", encoding="utf-8") as f:
                captcha_data = json.load(f)
            current_time = time.time()
            if captcha_data.get("expires_at", 0) < current_time:
                try:
                    os.remove(captcha_file)
                except Exception as e:
                    logging.warning(f"[验证码] 删除过期验证码文件失败: {e}")
                return False, "验证码已过期"
            stored_code = captcha_data.get("code", "")
            user_input_upper = user_input.strip().upper()
            is_correct = user_input_upper == stored_code

            def update_captcha_history():
                try:
                    history_dir = os.path.join("logs", "captcha_history")
                    date_str = datetime.datetime.now().strftime("%Y%m%d")
                    history_file = os.path.join(
                        history_dir, f"captcha_history_{date_str}.jsonl"
                    )
                    if os.path.exists(history_file):
                        lines = []
                        with open(history_file, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                        updated = False
                        for i, line in enumerate(lines):
                            try:
                                record = json.loads(line.strip())
                                if record.get("captcha_id") == captcha_id:
                                    record["status"] = (
                                        "verified_success"
                                        if is_correct
                                        else "verified_failed"
                                    )
                                    record["verified_at"] = time.time()
                                    record["verified_at_readable"] = (
                                        datetime.datetime.fromtimestamp(
                                            time.time()
                                        ).strftime("%Y-%m-%d %H:%M:%S")
                                    )
                                    record["verified_input"] = user_input_upper
                                    lines[i] = (
                                        json.dumps(record, ensure_ascii=False) + "\n"
                                    )
                                    updated = True
                                    break
                            except:
                                pass

                        if updated:
                            with open(history_file, "w", encoding="utf-8") as f:
                                f.writelines(lines)

                            logging.debug(
                                f"[验证码历史] 已更新验证结果: ID={captcha_id[:8]}..., 结果={'成功' if is_correct else '失败'}"
                            )
                except Exception as e:
                    logging.error(f"[验证码历史] 更新验证结果失败: {e}", exc_info=True)

            import threading

            threading.Thread(target=update_captcha_history, daemon=True).start()
            try:
                os.remove(captcha_file)
                logging.debug(f"[验证码] 已删除验证码文件: {captcha_id}")
            except Exception as e:
                logging.warning(f"[验证码] 删除验证码文件失败: {e}")
            if is_correct:
                logging.info(f"[验证码] 验证成功: ID={captcha_id[:8]}...")
                return True, ""
            else:
                logging.warning(f"[验证码] 验证失败: ID={captcha_id[:8]}...")
                return False, "验证码错误"

        except json.JSONDecodeError as e:
            logging.error(f"[验证码] JSON解析失败: {e}")
            try:
                os.remove(captcha_file)
            except:
                pass
            return False, "验证码数据损坏"

        except Exception as e:
            logging.error(f"[验证码] 验证过程出错: {e}", exc_info=True)
            return False, "验证码验证失败"

    @app.route("/api/captcha/history", methods=["GET"])
    def get_captcha_history():
        """
                获取验证码请求历史记录
        \ """
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id or session_id not in web_sessions:
            return jsonify({"success": False, "message": "未授权访问"}), 401
        api_instance = web_sessions.get(session_id)
        if not api_instance:
            return jsonify({"success": False, "message": "会话无效"}), 401

        username = getattr(api_instance, "auth_username", None)

        if not username:
            return jsonify({"success": False, "message": "未登录"}), 401
        if not auth_system.check_permission(username, "view_captcha_history"):
            return jsonify({"success": False, "message": "没有权限查看验证码历史"}), 403

        try:
            date_str = request.args.get(
                "date", datetime.datetime.now().strftime("%Y%m%d")
            )
            limit = int(request.args.get("limit", 100))
            status_filter = request.args.get("status", "")
            clean_date_str = date_str.replace("-", "")
            history_dir = os.path.join(LOGIN_LOGS_DIR, "captcha_history")
            history_file = os.path.join(
                history_dir, f"captcha_history_{clean_date_str}.jsonl"
            )

            logging.debug(f"[验证码历史] 正在读取文件: {history_file}")

            if not os.path.exists(history_file):
                logging.info(f"[验证码历史] 文件不存在: {history_file}")
                return jsonify(
                    {
                        "success": True,
                        "data": [],
                        "total": 0,
                        "message": "该日期没有验证码历史记录",
                    }
                )
            records = []
            current_time = time.time()
            expiry_threshold = 30 * 60

            line_count = 0
            parse_error_count = 0
            total_matched = 0
            target_status = status_filter
            if status_filter == "pending":
                target_status = "created"
            elif status_filter == "success":
                target_status = "verified_success"
            elif status_filter == "failed":
                target_status = "verified_failed"
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line_count += 1
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                        if record.get("status") == "created":
                            timestamp = record.get("timestamp", 0)
                            if current_time - timestamp > expiry_threshold:
                                record["status"] = "expired"
                                record["expired_at"] = timestamp + expiry_threshold
                                record["expired_at_readable"] = (
                                    datetime.datetime.fromtimestamp(
                                        timestamp + expiry_threshold
                                    ).strftime("%Y-%m-%d %H:%M:%S")
                                )
                        if status_filter and status_filter != "all":
                            if record.get("status") != target_status:
                                continue

                        total_matched += 1
                        record.pop("session_id", None)
                        records.append(record)
                    except Exception as e:
                        logging.warning(f"[验证码历史] 解析记录失败: {e}")
                        continue
            if len(records) > limit * 2:
                records = heapq.nlargest(
                    limit * 2, records, key=lambda x: x.get("timestamp", 0)
                )
            else:
                records.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            total = total_matched
            records = records[:limit]
            # 调试日志：检查返回记录中是否包含 code 字段
            # 这有助于排查"验证码内容不显示"的问题
            # 仅在 DEBUG 级别日志启用时执行统计，避免影响生产环境性能
            if records and logging.getLogger().isEnabledFor(logging.DEBUG):
                # 统计有 code 字段的记录数量
                # 使用 'code' in r 检查字段是否存在，而不是检查值是否为真
                records_with_code = sum(1 for r in records if "code" in r and r["code"])
                # 统计 code 字段为空或不存在的记录数量
                records_without_code = len(records) - records_with_code
                # 输出调试信息
                logging.debug(
                    f"[验证码历史] 字段检查: 有code={records_with_code}, 无code={records_without_code}"
                )
                # 如果存在没有 code 字段的记录，输出警告
                if records_without_code > 0:
                    logging.warning(
                        f"[验证码历史] 发现 {records_without_code} 条记录缺少code字段"
                    )
            logging.info(
                f"[验证码历史] 管理员 {username} 查询验证码历史: 日期={date_str}, 返回={len(records)}条 (总计={total}条)"
            )

            def update_expired_captchas_in_history():
                try:
                    if not os.path.exists(history_file):
                        return
                    lines = []
                    updated_count = 0
                    current_time = time.time()
                    expiry_threshold = 30 * 60
                    with open(history_file, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                record = json.loads(line.strip())
                                if record.get("status") == "created":
                                    timestamp = record.get("timestamp", 0)
                                    if current_time - timestamp > expiry_threshold:
                                        record["status"] = "expired"
                                        record["expired_at"] = (
                                            timestamp + expiry_threshold
                                        )
                                        record["expired_at_readable"] = (
                                            datetime.datetime.fromtimestamp(
                                                timestamp + expiry_threshold
                                            ).strftime("%Y-%m-%d %H:%M:%S")
                                        )
                                        updated_count += 1
                                lines.append(
                                    json.dumps(record, ensure_ascii=False) + "\n"
                                )
                            except:
                                lines.append(line)
                    if updated_count > 0:
                        with open(history_file, "w", encoding="utf-8") as f:
                            f.writelines(lines)
                        logging.info(
                            f"[验证码历史] 已永久标记 {updated_count} 个过期验证码: {date_str}"
                        )
                except Exception as e:
                    logging.error(f"[验证码历史] 更新过期验证码状态失败: {e}")

            import threading

            threading.Thread(
                target=update_expired_captchas_in_history, daemon=True
            ).start()

            return jsonify(
                {
                    "success": True,
                    "data": records,
                    "total": total,
                    "date": date_str,
                }
            )

        except Exception as e:
            logging.error(f"[验证码历史] 获取历史记录失败: {e}", exc_info=True)
            return jsonify({"success": False, "message": "获取验证码历史失败"}), 500

    # ============================================================
    # 验证码详情API
    # ============================================================
    @app.route("/api/captcha/detail/<captcha_id>", methods=["GET"])
    @login_required
    def get_captcha_detail(captcha_id):
        """
        获取单个验证码的详细信息

        权限要求：管理员 (view_captcha_history)
        """
        try:
            if not auth_system.check_permission(g.user, "view_captcha_history"):
                return jsonify({"success": False, "message": "权限不足"}), 403
            if not captcha_id or ".." in captcha_id or "/" in captcha_id:
                return jsonify({"success": False, "message": "无效的验证码ID"}), 400
            history_dir = os.path.join(LOGIN_LOGS_DIR, "captcha_history")
            if not os.path.exists(history_dir):
                return (
                    jsonify({"success": False, "message": "验证码历史目录不存在"}),
                    404,
                )

            found_record = None
            current_time = time.time()
            expiry_threshold = 30 * 60
            for filename in os.listdir(history_dir):
                if filename.endswith(".jsonl"):
                    history_file = os.path.join(history_dir, filename)
                    try:
                        with open(history_file, "r", encoding="utf-8") as f:
                            for line in f:
                                try:
                                    record = json.loads(line.strip())
                                    if record.get("captcha_id") == captcha_id:
                                        found_record = record
                                        if record.get("status") == "created":
                                            timestamp = record.get("timestamp", 0)
                                            if (
                                                current_time - timestamp
                                                > expiry_threshold
                                            ):
                                                found_record["status"] = "expired"
                                                found_record["expired_at"] = (
                                                    timestamp + expiry_threshold
                                                )
                                                found_record["expired_at_readable"] = (
                                                    datetime.datetime.fromtimestamp(
                                                        timestamp + expiry_threshold
                                                    ).strftime("%Y-%m-%d %H:%M:%S")
                                                )
                                        found_record.pop("session_id", None)
                                        return jsonify(
                                            {"success": True, "data": found_record}
                                        )
                                except json.JSONDecodeError:
                                    continue
                    except (IOError, OSError) as e:
                        logging.warning(
                            f"[验证码详情] 读取历史文件 {filename} 失败: {e}"
                        )
                        continue
            if not found_record:
                return (
                    jsonify({"success": False, "message": "未找到该验证码的详细信息"}),
                    404,
                )

        except Exception as e:
            logging.error(f"[验证码详情] 获取详情失败: {e}", exc_info=True)
            return (
                jsonify({"success": False, "message": "获取验证码详情时发生错误"}),
                500,
            )

    # ========================================
    # 【本地验证码】新增API端点
    # ========================================
    @app.route("/api/captcha/save_settings", methods=["POST"])
    @login_required
    def save_captcha_settings():
        """
        【本地验证码】保存验证码生成器设置到config.ini
        """
        try:
            # ========================================
            # 1. 权限检查：只有管理员可以修改验证码设置
            # ========================================
            if not auth_system.check_permission(g.user, "modify_config"):
                logging.warning(
                    f"【本地验证码】用户 {g.user} 尝试保存验证码设置但权限不足"
                )
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "权限不足：只有管理员可以修改验证码设置",
                        }
                    ),
                    403,
                )
            # ========================================
            # 2. 解析请求数据
            # ========================================
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "请求数据为空"}), 400
            # ========================================
            # 3. 提取并验证参数
            # ========================================
            try:
                length = int(data.get("length", 4))
                scale_factor = int(data.get("scale_factor", 2))
                noise_level = float(data.get("noise_level", 0.08))
            except (ValueError, TypeError) as e:
                logging.error(f"【本地验证码】参数类型转换失败: {e}")
                return (
                    jsonify({"success": False, "message": f"参数类型错误: {str(e)}"}),
                    400,
                )
            if not (3 <= length <= 6):
                return (
                    jsonify({"success": False, "message": "验证码长度必须在3-6之间"}),
                    400,
                )

            if not (2 <= scale_factor <= 4):
                return (
                    jsonify({"success": False, "message": "细分倍数必须在2-4之间"}),
                    400,
                )

            if not (0 <= noise_level <= 0.3):
                return (
                    jsonify({"success": False, "message": "噪点比例必须在0.0-0.3之间"}),
                    400,
                )

            logging.info(
                f"【本地验证码】用户 {g.user} 请求保存验证码设置: length={length}, scale_factor={scale_factor}, noise_level={noise_level}"
            )
            # ========================================
            # 4. 读取现有配置文件
            # ========================================
            config_file = "config.ini"
            config = configparser.ConfigParser()
            if os.path.exists(config_file):
                config.read(config_file, encoding="utf-8")
            # ========================================
            # 5. 确保[Captcha]节存在
            # ========================================
            if not config.has_section("Captcha"):
                config.add_section("Captcha")
                logging.debug("【本地验证码】[Captcha]节不存在，已创建")

            # ========================================
            # 6. 更新配置值
            # ========================================
            config.set("Captcha", "length", str(length))
            config.set("Captcha", "scale_factor", str(scale_factor))
            config.set("Captcha", "noise_level", str(noise_level))

            _write_config_with_comments(config, config_file)

            logging.info(f"【本地验证码】验证码设置已成功保存到 {config_file}")
            # ========================================
            # 8. 返回成功响应
            # ========================================
            return jsonify({"success": True, "message": "验证码设置保存成功"})
        except Exception as e:
            logging.error(f"【本地验证码】保存验证码设置失败: {e}", exc_info=True)
            return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

    @app.route("/api/captcha/test_generate", methods=["POST"])
    @login_required
    def test_generate_captcha():
        """
        【本地验证码】测试生成验证码（用于预览效果）
        """
        try:
            # ========================================
            # 1. 权限检查：只有管理员可以测试生成验证码
            # ========================================
            if not auth_system.check_permission(g.user, "modify_config"):
                logging.warning(
                    f"【本地验证码】用户 {g.user} 尝试测试生成验证码但权限不足"
                )
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "权限不足：只有管理员可以测试验证码",
                        }
                    ),
                    403,
                )

            # ========================================
            # 2. 导入本地验证码生成器
            # ========================================
            pass

            # ========================================
            # 3. 解析请求数据
            # ========================================
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "请求数据为空"}), 400

            # ========================================
            # 4. 提取并验证参数
            # ========================================
            try:
                length = int(data.get("length", 4))
                scale_factor = int(data.get("scale_factor", 2))
                noise_level = float(data.get("noise_level", 0.08))
            except (ValueError, TypeError) as e:
                logging.error(f"【本地验证码】测试生成时参数类型转换失败: {e}")
                return (
                    jsonify({"success": False, "message": f"参数类型错误: {str(e)}"}),
                    400,
                )
            if not (3 <= length <= 6):
                return (
                    jsonify({"success": False, "message": "验证码长度必须在3-6之间"}),
                    400,
                )

            if not (2 <= scale_factor <= 4):
                return (
                    jsonify({"success": False, "message": "细分倍数必须在2-4之间"}),
                    400,
                )

            if not (0 <= noise_level <= 0.3):
                return (
                    jsonify({"success": False, "message": "噪点比例必须在0.0-0.3之间"}),
                    400,
                )

            logging.info(
                f"【本地验证码】用户 {g.user} 测试生成验证码: length={length}, scale_factor={scale_factor}, noise_level={noise_level}"
            )

            # ========================================
            # 5. 生成验证码
            # ========================================
            generator = MicroPixelCaptcha()

            code, html, width, height = generator.generate(
                length=length, scale_factor=scale_factor, noise_level=noise_level
            )

            logging.debug(
                f"【本地验证码】测试验证码生成成功: code={code}, html_length={len(html)}, size={width}x{height}"
            )

            # ========================================
            # 5.1 保存到文件及历史记录 (新增逻辑)
            # ========================================
            import uuid

            captcha_id = str(uuid.uuid4())

            captchas_dir = os.path.join(LOGIN_LOGS_DIR, "captchas")
            os.makedirs(captchas_dir, exist_ok=True)

            captcha_data = {
                "id": captcha_id,
                "code": code.upper(),
                "html": html,
                "session_id": request.headers.get("X-Session-ID", "test_session"),
                "timestamp": time.time(),
                "expires_at": time.time() + 600,
            }

            captcha_file = os.path.join(captchas_dir, f"{captcha_id}.json")
            with open(captcha_file, "w", encoding="utf-8") as f:
                json.dump(captcha_data, f, indent=2, ensure_ascii=False)
            try:
                history_dir = os.path.join(LOGIN_LOGS_DIR, "captcha_history")
                os.makedirs(history_dir, exist_ok=True)

                date_str = datetime.datetime.now().strftime("%Y%m%d")
                history_file = os.path.join(
                    history_dir, f"captcha_history_{date_str}.jsonl"
                )

                history_entry = {
                    "captcha_id": captcha_id,
                    "code": code.upper(),
                    "html": html,
                    "session_id": request.headers.get("X-Session-ID", "unknown"),
                    "client_ip": request.headers.get(
                        "X-Forwarded-For", request.remote_addr
                    ),
                    "user_agent": request.headers.get("User-Agent", "unknown"),
                    "timestamp": time.time(),
                    "timestamp_readable": datetime.datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "expires_at": time.time() + 600,
                    "status": "test_generated",
                    "verified_at": None,
                    "verified_input": None,
                }

                with open(history_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(history_entry, ensure_ascii=False) + "\n")

                logging.info(f"【本地验证码】测试记录已保存: ID={captcha_id}")
            except Exception as e:
                logging.error(f"【本地验证码】保存测试历史失败: {e}")

            # ========================================
            # 6. 返回成功响应
            # ========================================
            return jsonify(
                {
                    "success": True,
                    "code": code,
                    "html": html,
                    "captcha_id": captcha_id,
                    "width": width,
                    "height": height,
                    "message": "验证码生成成功",
                }
            )

        except ImportError as e:
            logging.error(
                f"【本地验证码】导入MicroPixelCaptcha失败: {e}", exc_info=True
            )
            return (
                jsonify({"success": False, "message": f"验证码生成器不可用: {str(e)}"}),
                500,
            )
        except Exception as e:
            logging.error(f"【本地验证码】测试生成验证码失败: {e}", exc_info=True)
            return jsonify({"success": False, "message": f"生成失败: {str(e)}"}), 500

    @app.route("/health")
    def health():
        """
        健康检查端点
        """

        # ========== 记录请求开始时间（用于计算响应延迟） ==========
        request_start_time = time.time()

        # ========== 计算服务器运行时间 ==========
        current_time = time.time()
        uptime_seconds = (
            current_time - server_start_time if "server_start_time" in globals() else 0
        )

        def format_uptime(seconds):
            """
            将秒数转换为人类可读的时间格式。
            """
            days = int(seconds // 86400)
            seconds %= 86400
            hours = int(seconds // 3600)
            seconds %= 3600
            minutes = int(seconds // 60)
            seconds = int(seconds % 60)
            parts = []
            if days > 0:
                parts.append(f"{days}天")
            if hours > 0:
                parts.append(f"{hours}小时")
            if minutes > 0:
                parts.append(f"{minutes}分钟")
            if seconds > 0 or len(parts) == 0:
                parts.append(f"{seconds}秒")

            return "".join(parts)

        uptime_formatted = format_uptime(uptime_seconds)

        # ========== 获取活跃会话数 ==========
        active_sessions = len(web_sessions) - 1 if web_sessions else 0
        active_sessions = max(0, active_sessions)
        # ========== 获取后台任务数 ==========
        active_tasks = 0
        if background_task_manager:
            with background_task_manager.lock:
                active_tasks = len(background_task_manager.tasks)
        # ========== 获取Chrome上下文数（线程安全） ==========
        contexts_count = 0
        if chrome_pool and hasattr(chrome_pool, "_contexts"):
            # 使用新的专用线程模式中的 _contexts 属性
            contexts_count = len(getattr(chrome_pool, "_contexts", {}))
        # ========== 获取CDN缓存状态 ==========
        cdn_cache_status = {}
        try:
            with js_cache_lock:
                for key, config in CDN_FILES.items():
                    cdn_cache_status[key] = {
                        "type": config["type"],
                        "cached": key in js_cache_storage,
                        "last_update_time": (
                            datetime.datetime.fromtimestamp(
                                js_cache_last_update[key]
                            ).strftime("%Y-%m-%d %H:%M:%S")
                            if key in js_cache_last_update
                            else None
                        ),
                    }
        except Exception as e:
            logging.warning(f"[健康检查] 获取CDN缓存状态失败: {e}")
        # ========== 计算响应延迟 ==========
        request_end_time = time.time()
        response_time_ms = round((request_end_time - request_start_time) * 1000, 2)
        # ========== 返回健康检查信息 ==========
        return jsonify(
            {
                "status": "ok",
                "uptime_seconds": int(uptime_seconds),
                "uptime_formatted": uptime_formatted,
                "active_memory_sessions": active_sessions,
                "active_background_tasks": active_tasks,
                "current_thread_chrome_contexts": contexts_count,
                "cdn_cache": cdn_cache_status,
                "response_time_ms": response_time_ms,
            }
        )

    @socketio.on("connect")
    def handle_connect():
        session_id = request.args.get("session_id") or request.cookies.get(
            "session_id_cookie"
        )
        if not session_id:
            session_id = session.get("session_id")
        logging.info(f"WebSocket 客户端连接: {request.sid}")

    @socketio.on("join")
    def handle_join(data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception as e:
                logging.warning(
                    f"WebSocket 'join' 事件数据解析失败: {e}, 原始数据: {data}"
                )
                return
        if not isinstance(data, dict):
            logging.warning(f"WebSocket 'join' 接收到无效数据类型: {type(data)}")
            return
        session_id = data.get("session_id")
        if session_id:
            join_room(session_id)
            logging.info(f"WebSocket 客户端 {request.sid} 成功加入 {session_id}")
            emit("log_message", {"msg": "WebSocket 连接成功！"}, room=session_id)
        else:
            logging.warning(
                f"WebSocket 客户端 {request.sid} 加入房间失败：缺少 session_id。"
            )

    @socketio.on("disconnect")
    def handle_disconnect():
        logging.info(f"WebSocket 客户端断开连接: {request.sid}")

    def _emit_verification_codes_update(session_id):
        """辅助函数：向指定会话推送验证码列表更新事件"""
        if not session_id or not socketio:
            logging.debug(
                f"[SocketIO] 跳过 'verification_codes_updated' 推送（缺少 session_id 或 socketio）"
            )
            return
        try:
            socketio.emit("verification_codes_updated", {}, room=session_id)
            logging.debug(
                f"[SocketIO] 已向会话 {session_id[:8]}... 推送 'verification_codes_updated' 事件"
            )
        except Exception as e:
            logging.error(f"[SocketIO] 推送 'verification_codes_updated' 失败: {e}")

    def cleanup_sessions():
        """定期清理超过24小时无活动的会话，并强制执行内存会话数量限制"""
        while True:
            time.sleep(3600)
            try:
                current_time = time.time()
                expired_sessions = []

                with web_sessions_lock:
                    for session_id in list(web_sessions.keys()):
                        with session_activity_lock:
                            last_activity = session_activity.get(session_id, 0)
                            if current_time - last_activity > 86400:
                                expired_sessions.append(session_id)
                    remaining_sessions = len(web_sessions) - len(expired_sessions)
                    if remaining_sessions > MAX_MEMORY_SESSIONS:
                        with session_activity_lock:
                            active_sessions = [
                                sid
                                for sid in web_sessions.keys()
                                if sid not in expired_sessions
                            ]
                            sorted_sessions = sorted(
                                active_sessions,
                                key=lambda sid: session_activity.get(sid, 0),
                            )
                            sessions_to_remove = (
                                remaining_sessions - MAX_MEMORY_SESSIONS
                            )
                            for session_id in sorted_sessions[:sessions_to_remove]:
                                expired_sessions.append(session_id)
                        logging.warning(
                            f"[会话清理] 内存会话数超过限制({MAX_MEMORY_SESSIONS})，额外清理了 {sessions_to_remove} 个最旧会话"
                        )
                    for session_id in expired_sessions:
                        try:
                            if chrome_pool:
                                chrome_pool.cleanup_context(session_id)
                            if session_id in web_sessions:
                                del web_sessions[session_id]

                            with session_activity_lock:
                                if session_id in session_activity:
                                    del session_activity[session_id]
                            logging.info(f"[会话清理] 已清理会话: {session_id[:8]}...")
                        except Exception as e:
                            logging.error(
                                f"[会话清理] 清理会话 {session_id[:8]}... 时出错: {e}"
                            )

                if expired_sessions:
                    logging.info(
                        f"[会话清理] 本次清理了 {len(expired_sessions)} 个会话"
                    )
                    gc.collect()
                else:
                    with web_sessions_lock:
                        logging.debug(
                            f"[会话清理] 当前内存会话数: {len(web_sessions)}/{MAX_MEMORY_SESSIONS}"
                        )
            except Exception as e:
                logging.error(f"[会话清理] 清理过程出错: {e}", exc_info=True)

    cleanup_thread = threading.Thread(target=cleanup_sessions, daemon=True)
    cleanup_thread.start()
    logging.info("正在加载持久化会话...")
    load_all_sessions(args)
    logging.info("正在启动会话监控...")
    start_session_monitor()
    try:
        start_background_auto_attendance(args)
    except Exception as e:
        logging.error(f"启动后台自动签到服务失败: {e}", exc_info=True)

    cleaned_sessions_count = 0
    with web_sessions_lock:
        for session_id, api_instance in web_sessions.items():
            try:
                if hasattr(api_instance, "stop_run_flag") and isinstance(
                    api_instance.stop_run_flag, threading.Event
                ):
                    api_instance.stop_run_flag.set()
                if hasattr(api_instance, "multi_run_stop_flag") and isinstance(
                    api_instance.multi_run_stop_flag, threading.Event
                ):
                    api_instance.multi_run_stop_flag.set()
                if hasattr(api_instance, "stop_auto_refresh") and isinstance(
                    api_instance.stop_auto_refresh, threading.Event
                ):
                    api_instance.stop_auto_refresh.set()
                if hasattr(api_instance, "stop_multi_auto_refresh") and isinstance(
                    api_instance.stop_multi_auto_refresh, threading.Event
                ):
                    api_instance.stop_multi_auto_refresh.set()
                if getattr(api_instance, "is_multi_account_mode", False) and hasattr(
                    api_instance, "accounts"
                ):
                    for acc in api_instance.accounts.values():
                        if hasattr(acc, "stop_event") and isinstance(
                            acc.stop_event, threading.Event
                        ):
                            acc.stop_event.set()
                        acc.worker_thread = None
                        if not api_instance._should_preserve_status(
                            acc.status_text, "待命"
                        ):
                            acc.status_text = "待命"
                if hasattr(api_instance, "auto_refresh_thread"):
                    api_instance.auto_refresh_thread = None
                if hasattr(api_instance, "multi_auto_refresh_thread"):
                    api_instance.multi_auto_refresh_thread = None
                api_instance.current_run_idx = -1
                api_instance._first_center_done = False

                cleaned_sessions_count += 1
            except Exception as e:
                logging.error(f"重置会话 {session_id[:8]}... 状态时出错: {e}")

    logging.info(f"已重置 {cleaned_sessions_count} 个会话的运行状态标志。")

    logging.info("正在检查并修正持久化的后台任务状态...")
    interrupted_task_files = 0
    if background_task_manager and os.path.exists(
        background_task_manager.task_storage_dir
    ):
        try:
            for filename in os.listdir(background_task_manager.task_storage_dir):
                if filename.endswith(".json"):
                    filepath = os.path.join(
                        background_task_manager.task_storage_dir, filename
                    )
                    try:
                        task_state = None
                        with open(filepath, "r", encoding="utf-8") as f:
                            task_state = json.load(f)
                        if task_state and task_state.get("status") == "running":
                            task_state["status"] = "stopped"
                            task_state["error"] = "程序意外重启导致任务中断。"
                            task_state["last_update"] = time.time()
                            with open(filepath, "w", encoding="utf-8") as f:
                                json.dump(task_state, f, indent=2, ensure_ascii=False)
                            interrupted_task_files += 1
                            logging.debug(
                                f"已将持久化的后台任务 {filename} 状态修正为 stopped。"
                            )

                    except (IOError, json.JSONDecodeError) as e:
                        logging.warning(
                            f"处理后台任务状态文件 {filename} 时出错: {e}，跳过此文件。"
                        )
                    except Exception as e:
                        logging.error(
                            f"更新后台任务状态文件 {filename} 时发生意外错误: {e}",
                            exc_info=True,
                        )

            if interrupted_task_files > 0:
                logging.info(
                    f"已修正 {interrupted_task_files} 个持久化的 'running' 后台任务状态为 stopped。"
                )
            else:
                logging.info("未发现需要修正状态的持久化后台任务文件。")
        except Exception as e:
            logging.error(f"检查持久化后台任务状态时发生错误: {e}", exc_info=True)
    else:
        logging.info("后台任务管理器未初始化或存储目录不存在，跳过持久化状态检查。")
    if background_task_manager:
        with background_task_manager.lock:
            initial_task_count = len(background_task_manager.tasks)
            background_task_manager.tasks.clear()
            logging.info(
                f"已清空后台任务管理器的内存状态（清理了 {initial_task_count} 个任务记录）。"
            )
    # ============================================================================
    # SSL/HTTPS 配置加载和验证
    # 在启动服务器之前，加载SSL配置并验证证书（如果启用了SSL）
    # ============================================================================
    ssl_config = load_ssl_config()
    ssl_context = None
    cert_path = None
    key_path = None
    if ssl_config["ssl_enabled"]:
        logging.info("检测到SSL已启用，正在验证证书文件...")
        is_valid, error_msg, cert_info = validate_ssl_certificate(
            ssl_config["ssl_cert_path"], ssl_config["ssl_key_path"]
        )

        if not is_valid:
            print(f"\n{'='*60}")
            print(f"警告: SSL证书验证失败")
            print(f"")
            print(f"原因: {error_msg}")
            print(f"")
            print(f"系统将自动禁用SSL并切换回HTTP模式运行，以免影响服务使用。")
            print(f"配置文件 config.ini 中的 ssl_enabled 已被自动关闭。")
            print(f"{'='*60}\n")
            logging.error(f"SSL证书验证失败: {error_msg}")
            logging.info("正在自动关闭SSL配置并切换到HTTP模式...")

            # 自动关闭SSL
            ssl_config["ssl_enabled"] = False
            ssl_config["https_only"] = False
            save_ssl_config(ssl_config)
            
        # 只有当验证通过且配置仍然启用时，才尝试创建上下文
        if ssl_config["ssl_enabled"]:
            try:
                import ssl as ssl_module

                ssl_context = ssl_module.SSLContext(ssl_module.PROTOCOL_TLS_SERVER)
                cert_path = ssl_config["ssl_cert_path"]
                key_path = ssl_config["ssl_key_path"]

                if not os.path.isabs(cert_path):
                    cert_path = os.path.join(os.path.dirname(__file__), cert_path)
                if not os.path.isabs(key_path):
                    key_path = os.path.join(os.path.dirname(__file__), key_path)
                ssl_context.load_cert_chain(cert_path, key_path)
                ssl_context.options |= ssl_module.OP_NO_SSLv2
                ssl_context.options |= ssl_module.OP_NO_SSLv3
                logging.info(f"SSL上下文创建成功，使用证书: {cert_path}")
                print(f"✓ SSL/HTTPS 已启用")
                print(f"  证书文件: {cert_path}")
                print(f"  密钥文件: {key_path}")
                if ssl_config["https_only"]:
                    print(f"  ⚠ 仅HTTPS模式: 已启用（HTTP请求将被重定向）")
            except Exception as e:
                print(f"\n{'='*60}")
                print(f"警告: 创建SSL上下文失败")
                print(f"")
                print(f"详细信息: {e}")
                print(f"")
                print(f"系统将自动禁用SSL并切换回HTTP模式运行。")
                print(f"{'='*60}\n")
                logging.error(f"创建SSL上下文失败: {e}", exc_info=True)
                
                # 自动关闭SSL
                ssl_config["ssl_enabled"] = False
                ssl_config["https_only"] = False
                save_ssl_config(ssl_config)
                ssl_context = None
    
    # 二次检查：如果刚才因为错误禁用了SSL，这里会打印日志
    if not ssl_config.get("ssl_enabled", False):
         logging.info("SSL未启用（或已自动禁用），服务器将以HTTP模式运行")

    # ============================================================================
    # 添加请求钩子：处理X-Forwarded-*头和HTTPS重定向
    # 这些钩子在每个请求处理之前执行
    # ============================================================================
    @app.before_request
    def handle_forwarded_proto():
        """
        处理反向代理（如Nginx）转发的请求头。

        功能说明：
        1. 检查X-Forwarded-Proto头，识别原始请求是HTTP还是HTTPS
        2. 检查X-Forwarded-For头，获取真实客户端IP
        3. 如果启用了https_only模式且检测到HTTP请求，重定向到HTTPS

        这个函数在每个请求处理之前自动执行。
        """
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            real_ip = forwarded_for.split(",")[0].strip()
            request.environ["REMOTE_ADDR"] = real_ip
        if ssl_config.get("https_only", False) and ssl_config.get("ssl_enabled", False):
            if not forwarded_proto:
                is_https = True
            else:
                is_https = request.is_secure or forwarded_proto.lower() == "https"
            if not is_https:
                excluded_paths = ["/health", "/api/health", "/socket.io"]
                should_redirect = True
                for path in excluded_paths:
                    if request.path.startswith(path):
                        should_redirect = False
                        break
                if should_redirect:
                    url = request.url.replace("http://", "https://", 1)
                    logging.info(f"HTTP请求被重定向到HTTPS: {request.url} -> {url}")
                    from flask import redirect

                    return redirect(url, code=301)
                    return redirect(url, code=301)

    @app.after_request
    def add_security_headers(response):
        """
        为所有响应添加安全相关的HTTP头。
        """
        if ssl_config.get("ssl_enabled", False):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # ============================================================================
    # 启动服务器
    # 根据SSL配置选择HTTP或HTTPS模式
    # ============================================================================
    protocol = "https" if ssl_config.get("ssl_enabled", False) else "http"
    server_url = f"{protocol}://{args.host}:{args.port}"
    print(f"\n{'='*60}")
    print(f"  跑步助手 Web 版本已启动")
    print(f"  访问地址: {server_url}")
    if ssl_config.get("ssl_enabled", False):
        print(f"  SSL/HTTPS: 已启用 ✓")
        if ssl_config.get("https_only", False):
            print(f"  仅HTTPS模式: 已启用 ⚠")
    else:
        print(f"  SSL/HTTPS: 未启用（使用HTTP）")
    print(f"  会话持久化已启用（服务器重启后保留登录状态）")
    print(f"  JS计算在服务器端Chrome中执行，提升安全性")
    print(f"  会话监控已启用（5分钟不活跃自动清理）")
    print(f"{'='*60}\n")

    try:
        if ssl_context:
            logging.info(
                f"正在启动带有 WebSocket 和 SSL(HTTPS) 支持的 Web 服务器于 {server_url}"
            )

            try:

                logging.info(f"Eventlet 将使用 SSLContext 启动服务器...")
                logging.info(f"  证书文件: {cert_path}")
                logging.info(f"  密钥文件: {key_path}")

                # ============================================================
                # 【SSL 智能兼容层】
                # ============================================================
                class DualProtocolSocket(object):
                    def __init__(self, raw_socket, ssl_ctx, https_only=False):
                        self.sock = raw_socket
                        self.ssl_ctx = ssl_ctx
                        self.https_only = https_only

                    def __getattr__(self, name):
                        return getattr(self.sock, name)

                    def accept(self):
                        while True:
                            try:
                                client, addr = self.sock.accept()
                                try:
                                    client.settimeout(1.0)
                                    first_byte = client.recv(1, socket.MSG_PEEK)
                                    client.settimeout(None)

                                    if len(first_byte) == 0:
                                        client.close()
                                        continue
                                    if first_byte[0] == 22:
                                        secure_client = self.ssl_ctx.wrap_socket(
                                            client, server_side=True
                                        )
                                        return secure_client, addr
                                    else:
                                        if self.https_only:
                                            logging.info(
                                                f"检测到 HTTP 请求 (来自 {addr[0]})，发送 HTTPS 跳转指令..."
                                            )
                                            try:
                                                client.settimeout(0.1)
                                                client.recv(4096)
                                            except Exception:
                                                pass
                                            response = (
                                                "HTTP/1.1 200 OK\r\n"
                                                "Content-Type: text/html\r\n"
                                                "Connection: close\r\n\r\n"
                                                '<html><head><title>正在重定向到 HTTPS...</title><link rel="icon" href="/favicon.ico" type="image/x-icon" /></head>'
                                                "<body><script>window.location.protocol = 'https:';</script>"
                                                "Please wait, redirecting to HTTPS...</body></html>"
                                            )
                                            try:
                                                client.sendall(response.encode("utf-8"))
                                            except Exception:
                                                pass
                                            finally:
                                                client.close()
                                            continue
                                        else:
                                            return client, addr

                                except (socket.error, ssl.SSLError) as e:
                                    try:
                                        client.close()
                                    except:
                                        pass
                                    continue

                            except Exception as e:
                                logging.error(f"DualProtocolSocket accept error: {e}")
                                time.sleep(
                                    0.1
                                )  # [修正] 添加延时，防止错误死循环导致CPU占用100%和服务器卡死
                                continue

                server_socket = eventlet.listen((args.host, args.port))
                dual_socket = DualProtocolSocket(
                    server_socket,
                    ssl_context,
                    https_only=ssl_config.get("https_only", False),
                )
                try:
                    eventlet.wsgi.server(dual_socket, app, log_output=False)
                except KeyboardInterrupt:
                    raise
                except Exception as runtime_e:
                    logging.error(f"HTTPS 服务器运行时错误: {runtime_e}", exc_info=True)
                    try:
                        server_socket.close()
                    except:
                        pass
                    raise
            except ImportError:
                logging.error(
                    "Eventlet 模块未找到，无法启动HTTPS服务器。请运行 'pip install eventlet'"
                )
                raise
            except KeyboardInterrupt:
                raise
            except Exception as ssl_e:
                logging.error(
                    f"使用 Eventlet 启动 SSL 服务器失败: {ssl_e}", exc_info=True
                )
                print(f"\n[错误] 无法使用 eventlet 启动 HTTPS 服务器: {ssl_e}")
                print("请检查证书文件路径和权限是否正确。")
                raise
        else:
            logging.info(f"正在启动带有 WebSocket 支持的 Web 服务器于 {server_url}")
            try:
                socketio.run(app, host=args.host, port=args.port, debug=False)
            except KeyboardInterrupt:
                raise

    except KeyboardInterrupt:
        print(f"\n{'='*60}")
        print(f"  用户终止了程序 (Ctrl+C)")
        print(f"  正在清理资源并退出...")
        print(f"{'='*60}\n")
        logging.info("用户通过 Ctrl+C 停止了服务器")
        sys.exit(0)
    except OSError as e:
        if (
            "WinError 10013" in str(e)
            or "permission" in str(e).lower()
            or "访问权限" in str(e)
        ):
            print(f"\n{'='*60}")
            print(f"错误: 端口 {args.port} 被占用或无访问权限")
            print(f"")
            print(f"可能的原因：")
            print(f"  1. 端口已被其他程序使用")
            print(f"  2. Windows系统保留了该端口")
            print(f"  3. 需要管理员权限")
            print(f"")
            print(f"解决方法：")
            print(f"  方法1: 使用其他端口")
            print(f"    python main.py --port 8080")
            print(f"    python main.py --port 3000")
            print(f"")
            print(f"  方法2: 以管理员身份运行")
            print(f"    右键点击 PowerShell → 以管理员身份运行")
            print(f"")
            print(f"  方法3 (Windows): 检查并关闭占用端口的程序")
            print(f"    netstat -ano | findstr :{args.port}")
            print(f"    taskkill /PID <进程ID> /F")
            print(f"{'='*60}\n")
            logging.error(f"端口绑定失败: {e}")
        else:
            print(f"\n错误: 启动服务器失败 - {e}\n")
            logging.error(f"服务器启动失败: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        print(f"\n错误: 服务器运行时发生异常 - {e}\n")
        logging.error(f"服务器异常: {e}", exc_info=True)
        sys.exit(1)
    finally:
        pass


def main():
    """主函数，启动Web服务器模式（已弃用桌面模式）"""
    # ========== 第1步：导入内置模块 ==========
    # ========== 第2步：初始化日志系统 ==========
    try:
        setup_logging()
    except Exception as e:
        print(f"[错误] 日志系统初始化失败: {e}")
        traceback.print_exc()
        _load_ip_cache()
    # ========== 第3步：导入所有依赖库 ==========
    import_standard_libraries()
    import_core_third_party()
    check_and_import_dependencies()
    # ========== 第4步：初始化系统 ==========
    auto_init_system()
    initialize_global_variables()
    # ========== 第5步：解析命令行参数 ==========
    parser = argparse.ArgumentParser(description="跑步助手 - Web服务器模式")
    parser.add_argument(
        "--port", type=int, default=5000, help="Web服务器端口（默认5000）"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Web服务器地址（默认127.0.0.1）"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="使用无头Chrome模式（默认启用）",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="debug",
        help="设置日志级别（默认 debug）",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试日志（兼容旧参数，等同于 --log-level debug）",
    )
    args = parser.parse_args()
    # ========== 第6步：配置日志级别 ==========
    selected_level_name = "debug" if args.debug else args.log_level
    log_level = getattr(logging, selected_level_name.upper(), logging.DEBUG)

    log_format = "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(log_format))
    logging.basicConfig(level=log_level, format=log_format, handlers=[handler])
    logging.info("=" * 60)
    logging.info("跑步助手 Web 模式启动中...")
    level_name_map = {
        logging.DEBUG: "调试",
        logging.INFO: "信息",
        logging.WARNING: "警告",
        logging.ERROR: "错误",
        logging.CRITICAL: "严重",
    }
    logging.info(
        f"日志级别: {level_name_map.get(log_level, selected_level_name.upper())} ({selected_level_name.upper()})"
    )
    logging.info(f"服务器地址: {args.host}:{args.port}")
    logging.info("=" * 60)
    # ========== 第7步：检查Playwright是否可用 ==========
    if not playwright_available:
        print("\n" + "=" * 60)
        print("错误: 需要安装 Playwright 以在服务器端运行Chrome")
        print("请运行以下命令:")
        print("  pip install playwright")
        print("  python -m playwright install chromium")
        print("=" * 60 + "\n")
        sys.exit(1)
    # ========== 第8步：检查并选择可用端口 ==========
    initial_port = args.port
    DEFAULT_PORT = 5000
    if initial_port != DEFAULT_PORT:
        logging.info(f"用户已明确指定端口 {initial_port}。")
        logging.warning(f"将 *直接尝试* 绑定到端口 {initial_port}。")
        logging.warning(
            f"注意：如果此端口已被占用，或需要更高权限 (例如在 Linux/macOS 上绑定端口 80)，程序将会启动失败。"
        )
    else:
        logging.info(f"用户正在使用默认端口 {DEFAULT_PORT}。正在检查端口可用性...")
        if not check_port_available(args.host, args.port):
            logging.warning(
                f"默认端口 {args.port} 不可用或已被占用，尝试自动查找可用端口..."
            )
            found_port = None
            alternative_ports = [8080, 8000, 3000, 5001, 8888, 9000, 5005, 5050]
            for port in alternative_ports:
                logging.info(f"尝试端口 {port}...")
                if check_port_available(args.host, port):
                    found_port = port
                    logging.info(f"找到可用端口: {found_port}")
                    break
            if not found_port:
                logging.info(
                    "常用备选端口均不可用，尝试在 10000-65535 范围内查找随机可用端口..."
                )
                max_random_tries = 20
                for i in range(max_random_tries):
                    random_port = random.randint(10000, 65535)
                    if check_port_available(args.host, random_port):
                        found_port = random_port
                        logging.info(f"找到可用随机端口: {found_port}")
                        break
                    time.sleep(0.01)
            if not found_port:
                logging.error(
                    f"自动查找端口失败。默认端口 {initial_port} 及所有尝试的备选/随机端口均不可用。"
                )
                print(f"\n{'='*60}")
                print(f"错误: 无法自动找到可用的网络端口。")
                print(
                    f"请检查端口 {initial_port} 或其他常用端口是否被占用，或手动指定一个可用端口:"
                )
                print(f"  python main.py --port <可用端口号>")
                print(f"{'='*60}\n")
                sys.exit(1)
            else:
                args.port = found_port
        else:
            logging.info(f"默认端口 {DEFAULT_PORT} 可用。")
    # ========== 第9步：启动Web服务器 ==========
    logging.info("启动Web服务器模式（使用服务器端Chrome渲染）...")
    start_web_server(args)


if __name__ == "__main__":
    main()
