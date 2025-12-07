#!/usr/bin/env python3
"""
Nginx日志转发器
功能：实时监控nginx的JSON格式访问日志，并将日志条目转发到Flask应用的日志API

运行方式：
    python3 nginx_log_forwarder.py

工作原理：
    1. 使用tail -F监控nginx的JSON日志文件
    2. 解析每一行JSON格式的日志
    3. 批量发送到Flask应用的 /api/log_nginx 接口
    4. 通过Python的logging系统进行统一日志管理
"""

import json
import time
import requests
import logging
import subprocess
import sys
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
    """
    logger.info("=" * 60)
    logger.info("Nginx日志转发器启动")
    logger.info(f"监控文件: {NGINX_LOG_FILE}")
    logger.info(f"目标API: {FLASK_LOG_API}")
    logger.info(f"批量大小: {BATCH_SIZE} 条/批")
    logger.info(f"批量超时: {BATCH_TIMEOUT} 秒")
    logger.info("=" * 60)
    
    # 日志缓冲队列
    log_buffer = deque()
    last_send_time = time.time()
    
    try:
        # 等待Flask应用启动
        logger.info("等待Flask应用准备就绪...")
        retries = 0
        while retries < 30:  # 最多等待30秒
            try:
                response = requests.get("http://127.0.0.1:5000/", timeout=1)
                logger.info("Flask应用已就绪，开始转发日志")
                break
            except:
                retries += 1
                time.sleep(1)
        else:
            logger.warning("无法连接到Flask应用，但仍将继续尝试转发日志")
        
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
