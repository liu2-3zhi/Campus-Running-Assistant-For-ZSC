#!/usr/bin/env python3
"""
Nginx日志转发器
功能：实时监控nginx的JSON格式访问日志，并将日志条目转发到Flask应用的日志API

运行方式：
    python3 nginx_log_forwarder.py

工作原理：
    1. 启动UDP监听，等待Flask应用的启动通知
    2. 收到通知后发送确认响应，确保UDP握手成功
    3. 确认Flask就绪后，使用tail -F监控nginx的JSON日志文件
    4. 解析每一行JSON格式的日志
    5. 批量发送到Flask应用的 /api/log_nginx 接口
    6. 通过Python的logging系统进行统一日志管理
"""

import json
import time
import requests
import logging
import subprocess
import sys
import socket
import threading
from collections import deque

# ============================================================================
# 配置部分
# ============================================================================

# nginx JSON日志文件路径
NGINX_LOG_FILE = "/var/log/nginx/access_json.log"

# Flask应用日志API端点
FLASK_LOG_API = "http://127.0.0.1:5000/api/log_nginx"

# 批量发送配置
BATCH_SIZE = 10  # 每批最多发送的日志条数
BATCH_TIMEOUT = 2.0  # 批量发送超时时间（秒）

# 重试配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 1.0  # 重试延迟（秒）

# UDP配置
LOG_FORWARDER_UDP_PORT = 9999  # 本转发器监听的UDP端口
MAIN_UDP_PORT = 9998  # main.py监听确认响应的UDP端口
STARTUP_MESSAGE = "FLASK_STARTED"  # Flask启动通知消息
ACK_MESSAGE = "ACK_RECEIVED"  # 确认响应消息

# ============================================================================
# 日志配置
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# UDP握手相关函数
# ============================================================================

flask_ready_event = threading.Event()  # 用于通知主线程Flask已就绪


def udp_listener():
    """
    UDP监听线程，等待Flask应用的启动通知并发送确认响应

    工作流程：
    1. 监听UDP端口，等待Flask的启动通知
    2. 收到通知后，发送确认响应给Flask
    3. 设置事件标志，通知主线程可以开始处理日志
    """
    try:
        # 创建UDP socket
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(('127.0.0.1', LOG_FORWARDER_UDP_PORT))
        udp_socket.settimeout(None)  # 无超时，持续监听

        logger.info(f"[UDP监听] 已启动UDP监听线程，监听端口 {LOG_FORWARDER_UDP_PORT}")
        logger.info("[UDP监听] 等待Flask应用发送启动通知...")

        while not flask_ready_event.is_set():
            try:
                # 接收数据
                data, addr = udp_socket.recvfrom(1024)
                message = data.decode('utf-8')

                logger.info(f"[UDP监听] 收到消息: '{message}' (来自 {addr})")

                # 检查是否为启动通知
                if message == STARTUP_MESSAGE:
                    logger.info("[UDP监听] ✓ 确认收到Flask启动通知")

                    # 发送确认响应
                    udp_socket.sendto(
                        ACK_MESSAGE.encode('utf-8'),
                        addr  # 回复给发送方
                    )
                    logger.info(f"[UDP监听] ✓ 已发送确认响应到 {addr}")

                    # 设置事件标志，通知主线程Flask已就绪
                    flask_ready_event.set()
                    logger.info("[UDP监听] ✓ Flask就绪事件已设置，主线程可以开始处理日志")
                    break
                else:
                    logger.warning(f"[UDP监听] 收到未知消息，忽略: {message}")

            except socket.timeout:
                continue  # 超时后继续监听
            except Exception as e:
                logger.error(f"[UDP监听] 接收UDP消息时出错: {e}")
                time.sleep(1)

        # 关闭socket
        udp_socket.close()
        logger.info("[UDP监听] UDP监听线程结束")

    except Exception as e:
        logger.error(f"[UDP监听] UDP监听线程发生致命错误: {e}", exc_info=True)
        # 即使出错也设置事件，避免主线程永久阻塞
        flask_ready_event.set()


# ============================================================================
# 主要功能函数
# ============================================================================

def send_logs_to_flask(log_batch):
    """
    将日志批量发送到Flask应用

    参数：
        log_batch (list): 日志条目列表

    返回：
        bool: 发送是否成功
    """
    if not log_batch:
        return True

    try:
        # 构建请求数据
        payload = {"batch": log_batch}

        # 发送POST请求
        response = requests.post(
            FLASK_LOG_API,
            json=payload,
            timeout=5,
            headers={"Content-Type": "application/json"}
        )

        # 检查响应
        if response.status_code == 200:
            logger.debug(f"成功发送 {len(log_batch)} 条nginx日志到Flask")
            return True
        else:
            logger.warning(
                f"发送nginx日志失败: HTTP {response.status_code} - {response.text}"
            )
            return False

    except requests.exceptions.ConnectionError:
        logger.warning("无法连接到Flask应用，将在稍后重试")
        return False
    except requests.exceptions.Timeout:
        logger.warning("发送nginx日志超时")
        return False
    except Exception as e:
        logger.error(f"发送nginx日志时发生错误: {e}")
        return False


def parse_log_line(line):
    """
    解析一行JSON格式的nginx日志

    参数：
        line (str): 日志行文本

    返回：
        dict or None: 解析后的日志字典，解析失败返回None
    """
    try:
        # 去除首尾空白字符
        line = line.strip()
        if not line:
            return None

        # 解析JSON
        log_entry = json.loads(line)
        return log_entry

    except json.JSONDecodeError as e:
        logger.warning(f"解析日志行失败: {e} - 原始内容: {line[:100]}")
        return None
    except Exception as e:
        logger.error(f"处理日志行时发生意外错误: {e}")
        return None


def tail_nginx_log():
    """
    使用tail命令实时监控nginx日志文件

    生成器函数，逐行产出日志内容
    """
    try:
        # 使用tail -F命令跟踪日志文件（-F会在文件轮转时自动重新打开）
        process = subprocess.Popen(
            ["tail", "-F", "-n", "0", NGINX_LOG_FILE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1  # 行缓冲
        )

        logger.info(f"开始监控nginx日志文件: {NGINX_LOG_FILE}")

        # 逐行读取输出
        for line in iter(process.stdout.readline, ''):
            if line:
                yield line

    except FileNotFoundError:
        logger.error(f"找不到nginx日志文件: {NGINX_LOG_FILE}")
        logger.error("请确保nginx正在运行并且日志文件路径正确")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止日志转发器...")
        process.terminate()
        raise
    except Exception as e:
        logger.error(f"监控nginx日志时发生错误: {e}")
        if 'process' in locals():
            process.terminate()
        raise


def main():
    """
    主函数：监控nginx日志并批量转发到Flask

    工作流程：
    1. 启动UDP监听线程，等待Flask启动通知
    2. 等待Flask就绪事件
    3. 开始监控并转发nginx日志
    """
    logger.info("=" * 60)
    logger.info("Nginx日志转发器启动")
    logger.info(f"监控文件: {NGINX_LOG_FILE}")
    logger.info(f"目标API: {FLASK_LOG_API}")
    logger.info(f"批量大小: {BATCH_SIZE} 条/批")
    logger.info(f"批量超时: {BATCH_TIMEOUT} 秒")
    logger.info(f"UDP监听端口: {LOG_FORWARDER_UDP_PORT}")
    logger.info("=" * 60)

    try:
        # 第1步：启动UDP监听线程
        logger.info("[启动] 正在启动UDP监听线程...")
        udp_thread = threading.Thread(target=udp_listener, daemon=True)
        udp_thread.start()
        logger.info("[启动] UDP监听线程已启动")

        # 第2步：等待Flask应用发送启动通知
        logger.info("[启动] 等待Flask应用启动通知...")
        logger.info("[启动] (这确保Flask完全就绪后才开始处理日志，保证日志完整性)")

        # 设置超时时间为5分钟（足够长，但不会永久阻塞）
        flask_ready = flask_ready_event.wait(timeout=300)

        if not flask_ready:
            logger.error("[启动] ✗ 等待Flask启动通知超时（5分钟）")
            logger.error("[启动] Flask可能未启动或UDP通信失败")
            logger.error("[启动] 将尝试继续运行，但日志完整性可能无法保证")
        else:
            logger.info("[启动] ✓ Flask应用已就绪，UDP握手成功完成")

        # 第3步：开始处理日志
        logger.info("[启动] 开始监控和转发nginx日志...")
        logger.info("=" * 60)

        # 日志缓冲队列
        log_buffer = deque()
        last_send_time = time.time()

        # 开始监控和转发日志
        for log_line in tail_nginx_log():
            # 解析日志行
            log_entry = parse_log_line(log_line)
            if log_entry is None:
                continue

            # 添加到缓冲区
            log_buffer.append(log_entry)

            # 检查是否需要发送（达到批量大小或超时）
            current_time = time.time()
            should_send = (
                len(log_buffer) >= BATCH_SIZE or
                (log_buffer and current_time - last_send_time >= BATCH_TIMEOUT)
            )

            if should_send:
                # 将缓冲区内容转为列表
                batch = list(log_buffer)
                log_buffer.clear()

                # 发送到Flask（带重试机制）
                success = False
                for attempt in range(MAX_RETRIES):
                    if send_logs_to_flask(batch):
                        success = True
                        last_send_time = current_time
                        break
                    else:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_DELAY)

                if not success:
                    logger.error(f"发送 {len(batch)} 条日志失败，已达到最大重试次数")

    except KeyboardInterrupt:
        logger.info("\n收到中断信号，正在清理...")
        # 发送剩余的日志
        if log_buffer:
            logger.info(f"发送剩余的 {len(log_buffer)} 条日志...")
            send_logs_to_flask(list(log_buffer))
        logger.info("Nginx日志转发器已停止")
        sys.exit(0)
    except Exception as e:
        logger.error(f"日志转发器发生致命错误: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
