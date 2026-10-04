from __future__ import annotations

import ipaddress
import logging
import re
import secrets
import threading
import time
import typing
import urllib.parse

import requests


from main_runtime import _main


def _cleanup_expired_payment_verify_probes(now_ts=None):
    current_ts = float(now_ts if now_ts is not None else time.time())
    with _main().payment_verify_probes_lock:
        expired_tokens = [
            token
            for token, probe in _main().payment_verify_probes.items()
            if float((probe or {}).get("expires_at", 0) or 0) <= current_ts
        ]
        for token in expired_tokens:
            _main().payment_verify_probes.pop(token, None)


def _create_payment_verify_probe(ttl_seconds=15):
    _cleanup_expired_payment_verify_probes()
    token = secrets.token_urlsafe(24)
    challenge = secrets.token_urlsafe(32)
    now_ts = time.time()
    with _main().payment_verify_probes_lock:
        _main().payment_verify_probes[token] = {
            "token": token,
            "challenge": challenge,
            "created_at": now_ts,
            "expires_at": now_ts + float(ttl_seconds),
            "consumed": False,
        }
    return token, challenge


def _consume_payment_verify_probe(token, challenge, now_ts=None):
    _cleanup_expired_payment_verify_probes(now_ts=now_ts)
    with _main().payment_verify_probes_lock:
        probe = _main().payment_verify_probes.get(str(token or ""))
        if not isinstance(probe, dict):
            return False
        if probe.get("consumed"):
            return False
        if str(probe.get("challenge") or "") != str(challenge or ""):
            return False
        probe["consumed"] = True
        return True


def _is_payment_verify_probe_consumed(token):
    with _main().payment_verify_probes_lock:
        probe = _main().payment_verify_probes.get(str(token or ""))
        return bool(isinstance(probe, dict) and probe.get("consumed"))


def _build_payment_verify_probe_url(base_url, token):
    normalized_base = str(base_url or "").rstrip("/")
    return f"{normalized_base}/api/payment/verify_probe/{token}"


class IPVerifier:
    """
    用于验证客户端 IP 地址是否允许访问的类。
    将 IP 缓存状态和逻辑封装在类中，以减少全局变量。
    """
    global requests
    # import ipaddress

    # 类级别常量 (属于类，不属于全局命名空间)
    CACHE_EXPIRE_SECONDS = 300

    # 定义 IPv4 私有网络地址段
    PRIVATE_IPV4_NETWORKS = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),
    ]

    # 定义 IPv6 私有网络地址段
    PRIVATE_IPV6_NETWORKS = [
        ipaddress.ip_network("fc00::/7"),
        ipaddress.ip_network("fe80::/10"),
        ipaddress.ip_network("::1/128"),
    ]

    def __init__(self):
        """
        初始化 IP 验证器实例，并设置其私有缓存和线程锁。
        """
        # 实例属性：用于存储服务器公网 IP 地址的缓存
        self._public_ip_cache:  typing.Dict[str, typing.Union[str, None]] = {
            "ipv4": None,  # 存储 IPv4 公网地址字符串
            "ipv6": None,  # 存储 IPv6 公网地址字符串
        }
        # 实例属性：记录上次更新缓存的时间戳
        self._public_ip_cache_time: float = 0
        # 实例属性：用于保护缓存读写的线程锁
        self._public_ip_cache_lock = threading.Lock()

    @staticmethod
    def parse_host_input(host_input: str) -> typing.Dict[str, typing.Optional[str]]:
        """
        解析用户输入的 host 字符串，支持多种格式。
        
        【IPv6 特别说明】
        IPv6 地址有多种等价的表示形式（压缩/非压缩），本方法会将其标准化：
        - 2001:0db8:0000:0000:0000:0000:0000:0001 → 2001:db8::1（压缩形式）
        - ::1 和 0:0:0:0:0:0:0:1 是同一个地址（环回地址）
        - ::ffff:192.0.2.1 是 IPv4-mapped IPv6 地址
        解析后的 'ip' 字段会被 ipaddress 模块标准化，确保后续对象比较的准确性。

        支持的输入格式: 
        - 纯IPv4: 127.0.0.1
        - 纯IPv6: ::1, 2001:db8::1（会被标准化）
        - 带协议的IPv4: http://127.0.0.1, https://127.0.0.1
        - 带协议和端口的IPv4: http://127.0.0.1:8080, https://127.0.0.1:8080
        - 带协议的IPv6: http://[::1], https://[2001:db8::1]（方括号会被自动去除）
        - 带协议和端口的IPv6: http://[::1]:8080, https://[2001:db8::1]:8080
        - 特殊格式（无双斜杠）: https:127.0.0.1:8080
        - IPv4-mapped IPv6: ::ffff:127.0.0.1（会被识别为 IPv6）

        Returns:
            dict: {
                'ip': 纯IP地址字符串（已标准化，不含方括号），
                'port': 端口号字符串或None,
                'scheme': 协议 ('http' 或 'https') 或 None,
                'full_url': 完整的URL（IPv6会自动加方括号）
            }
        """
        # 初始化返回结果字典
        result = {
            'ip': None,
            'port': None,
            'scheme': None,
            'full_url': None
        }

        # 输入验证：确保传入的是非空字符串
        if not host_input or not isinstance(host_input, str):
            return result

        # 去除首尾空格，避免解析错误
        host_input = host_input.strip()

        # 处理特殊格式: https:127.0.0.1:8080 或 http:127.0.0.1:8080（无双斜杠）
        # 这种格式需要转换为标准的 scheme://host:port 格式
        special_pattern = r'^(https?):([^/].*)$'
        special_match = re.match(special_pattern, host_input)
        if special_match and '://' not in host_input:
            scheme = special_match.group(1)
            rest = special_match.group(2)
            # 转换为标准格式后继续解析
            host_input = f"{scheme}://{rest}"

        # 检查是否有协议前缀（http:// 或 https://）
        has_scheme = host_input.startswith(
            'http://') or host_input.startswith('https://')

        if has_scheme:
            # 使用 urllib.parse.urlparse 解析带协议的URL
            # 优势：自动处理 IPv6 方括号、端口等复杂情况
            parsed = _main().urllib.parse.urlparse(host_input)
            result['scheme'] = parsed.scheme

            # parsed.hostname 会自动去除 IPv6 的方括号
            # 例如：http://[::1]:8080 → hostname = '::1'
            hostname = parsed.hostname
            port = parsed.port

            if hostname:
                result['ip'] = hostname  # 此时已是不含方括号的纯 IP 地址
            if port:
                result['port'] = str(port)

        else:
            # 没有协议前缀，需要手动解析 IP 和端口
            # 这部分处理纯 IP 地址或 IP:port 格式
            
            # 【IPv6 处理】格式: [IPv6]:port 或 [IPv6]
            # IPv6 地址必须用方括号包围才能明确与端口分隔
            # 例如：[::1]:8080, [2001:db8::1]:80
            ipv6_bracket_pattern = r'^\[([^\]]+)\](?::(\d+))?$'
            ipv6_bracket_match = re.match(ipv6_bracket_pattern, host_input)

            if ipv6_bracket_match:
                # 成功匹配到带方括号的 IPv6 格式
                result['ip'] = ipv6_bracket_match.group(1)  # 提取方括号内的 IPv6 地址
                if ipv6_bracket_match.group(2):
                    result['port'] = ipv6_bracket_match.group(2)  # 提取端口号（如果有）
            else:
                # 尝试判断是否是纯 IPv6 地址（无方括号，无端口）
                # 例如：::1, 2001:db8::1, ::ffff:192.0.2.1
                try:
                    # 使用 ipaddress 模块验证并标准化 IP 地址
                    # 这会将各种 IPv6 表示形式统一为标准格式
                    # 例如：0:0:0:0:0:0:0:1 → ::1
                    ip_obj = ipaddress.ip_address(host_input)
                    result['ip'] = str(ip_obj)  # 转换为标准化的字符串表示
                except ValueError:
                    # 不是纯 IP 地址，可能是 IPv4:port 格式
                    # 【IPv4 处理】格式: IPv4:port 或纯 IPv4
                    # 例如：192.168.1.1:8080, 127.0.0.1
                    ipv4_port_pattern = r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::(\d+))?$'
                    ipv4_port_match = re.match(ipv4_port_pattern, host_input)

                    if ipv4_port_match:
                        result['ip'] = ipv4_port_match.group(1)  # 提取 IPv4 地址
                        if ipv4_port_match.group(2):
                            result['port'] = ipv4_port_match.group(2)  # 提取端口号（如果有）
                    else:
                        # 最后尝试：可能是不带端口的主机名或其他格式
                        # 直接保存为 IP 字段，后续会验证其有效性
                        result['ip'] = host_input

        # 验证解析出的 IP 地址或域名是否有效
        if result['ip']:
            try:
                # 尝试使用 ipaddress 模块验证是否为标准 IP 地址
                # 【重要】这一步会将 IPv6 地址标准化为规范形式
                # 例如：2001:0db8::0001 → 2001:db8::1
                # 这确保了后续使用对象比较时的准确性
                ipaddress.ip_address(result['ip'])
            except ValueError:
                # 如果不是 IP，检查是否为合法域名
                # 域名验证：允许字母、数字、点、连字符
                # 简单的域名验证正则，涵盖大部分域名场景以及 localhost
                domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
                is_valid_domain = re.match(
                    domain_pattern, result['ip']) or result['ip'] == 'localhost'

                if is_valid_domain:
                    # 是有效的域名，保留 result['ip']（此时字段实际存储的是 hostname）
                    # build_full_url 方法会处理非 IP 的 host 字符串
                    logging.debug(f"[IP解析] 识别为域名: {result['ip']}")
                else:
                    # 既不是 IP 也不是合法域名，判定为无效
                    logging.warning(f"[IP解析] 无效的IP地址或域名: {result['ip']}")
                    result['ip'] = None

        # 构建完整的 URL（用于发起HTTP请求）
        # 【IPv6 注意】build_full_url 会自动为 IPv6 地址添加方括号
        if result['ip']:
            result['full_url'] = IPVerifier.build_full_url(
                result['ip'],
                result['port'],
                result['scheme']
            )

        return result

    @staticmethod
    def build_full_url(ip: str, port: typing.Optional[str] = None,
                       scheme: typing.Optional[str] = None) -> str:
        """
        根据 IP、端口和协议构建完整的 URL。
        
        【IPv6 特别处理】
        IPv6 地址在 URL 中必须用方括号包围，以区分冒号是地址的一部分还是端口分隔符：
        - 正确：http://[::1]:8080, http://[2001:db8::1]
        - 错误：http://::1:8080（会导致解析混淆）
        本方法会自动检测 IPv6 地址并添加方括号。

        Args:
            ip: IP地址字符串（IPv4 或 IPv6，不含方括号）
            port: 端口号字符串或 None
            scheme: 协议（'http' 或 'https'）或 None

        Returns: 
            str: 完整的 URL 字符串（IPv6 会自动加方括号）
        """
        # 默认使用 http 协议
        if not scheme:
            scheme = 'http'

        # 【IPv6 检测】检查是否是 IPv6 地址，需要用方括号包围
        try:
            # 使用 ipaddress 模块解析 IP 地址
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.version == 6:
                # 这是 IPv6 地址，必须用方括号包围
                # 例如：::1 → [::1], 2001:db8::1 → [2001:db8::1]
                host_part = f"[{ip}]"
            else:
                # 这是 IPv4 地址，直接使用
                host_part = ip
        except ValueError:
            # 不是有效的 IP 地址，可能是域名，直接使用
            host_part = ip

        # 构建完整的 URL
        if port:
            # 有端口号：scheme://host:port
            return f"{scheme}://{host_part}:{port}"
        else:
            # 无端口号：scheme://host
            return f"{scheme}://{host_part}"

    @staticmethod
    def extract_ip_from_host(host_input: str) -> typing.Optional[str]:
        """
        从 host 输入中提取纯IP地址。
        这是一个便捷方法，用于只需要IP地址的场景。

        Args:
            host_input: 用户输入的host字符串

        Returns:
            str or None: 提取出的纯IP地址，或None（如果无法解析）
        """
        parsed = IPVerifier.parse_host_input(host_input)
        return parsed. get('ip')

    @staticmethod
    def is_private_ip(ip_addr: typing.Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
        """
        检查一个 IP 地址对象是否属于私有网络地址。
        
        【IPv4 和 IPv6 全面支持】
        本方法支持以下类型的输入：
        1. IP 对象（ipaddress.IPv4Address 或 ipaddress.IPv6Address）
        2. IP 地址字符串（会自动转换为 IP 对象）
        
        【IPv6 特别处理】
        - 支持标准 IPv6 私有地址段：fc00::/7（唯一本地地址）、fe80::/10（链路本地地址）、::1/128（环回地址）
        - 支持 IPv4-mapped IPv6 地址（::ffff:x.x.x.x）：会提取内嵌的 IPv4 地址并检查其是否为私有地址
        - IPv6 地址的多种表示形式（压缩/非压缩）会被自动标准化后进行比较
        
        这是一个静态方法，不依赖于 IPVerifier 实例的状态。
        
        Args:
            ip_addr: IP 地址对象或字符串
            
        Returns:
            bool: 如果是私有地址返回 True，否则返回 False
        """
        # --- 类型兼容处理 ---
        # 如果传入的是字符串，尝试转换为 IP 对象
        if isinstance(ip_addr, str):
            try:
                # 去除可能的空格，并转换为 IP 对象
                # 这一步会自动标准化 IPv6 地址（例如：0:0:0:0:0:0:0:1 → ::1）
                ip_addr = ipaddress.ip_address(ip_addr.strip())
            except ValueError:
                # 如果传入的字符串不是有效的纯 IP 地址（可能是域名或URL）
                # 视为非私有 IP（因为无法判断域名对应的 IP 是否为私有）
                return False
        # -----------------------

        # 使用类级常量定义的私有网络地址段
        v4_nets = IPVerifier.PRIVATE_IPV4_NETWORKS
        v6_nets = IPVerifier.PRIVATE_IPV6_NETWORKS

        if ip_addr.version == 4:
            # 【IPv4 处理】检查是否在 IPv4 私有网络段内
            # 使用 IP 对象的 'in' 运算符进行网络包含性检查
            # 这比字符串比较更准确，因为它基于数值比较
            is_private = any(ip_addr in net for net in v4_nets)
            if is_private:
                logging.debug(f"[IP验证] {ip_addr} 是 IPv4 私有地址")
            return is_private

        elif ip_addr.version == 6:
            # 【IPv6 特殊情况】处理 IPv4-mapped IPv6 地址
            # IPv4-mapped IPv6 格式：::ffff:x.x.x.x
            # 这种地址实际上是 IPv4 地址的 IPv6 表示形式
            if ip_addr.ipv4_mapped:
                # 提取内嵌的 IPv4 地址对象
                ipv4_embedded = ip_addr.ipv4_mapped
                # 递归调用自身来检查内嵌的 IPv4 地址是否为私有地址
                # 例如：::ffff:192.168.1.1 → 提取 192.168.1.1 → 检查是否为私有地址
                is_private = IPVerifier.is_private_ip(ipv4_embedded)
                if is_private:
                    logging.debug(
                        f"[IP验证] {ip_addr} 是 IPv4-mapped IPv6，内嵌地址 {ipv4_embedded} 是私有地址")
                return is_private

            # 【IPv6 标准处理】检查是否在 IPv6 私有网络段内
            # 使用对象的 'in' 运算符进行网络包含性检查
            # 这会自动处理 IPv6 地址的各种表示形式（压缩/非压缩）
            # 例如：::1 和 0:0:0:0:0:0:0:1 会被识别为同一个地址
            is_private = any(ip_addr in net for net in v6_nets)
            if is_private:
                logging.debug(f"[IP验证] {ip_addr} 是 IPv6 私有地址")
            return is_private

        # 未知版本（理论上不会到达这里）
        return False

    def get_public_ip_addresses(self) -> typing.Dict:
        """
        获取服务器的 IPv4 和 IPv6 公网 IP 地址，并在有效期内直接返回缓存数据。
        只有当缓存过期时，才会执行网络请求进行更新。
        
        【IPv6 支持说明】
        本方法会分别获取服务器的 IPv4 和 IPv6 公网地址：
        - IPv4：通过 http://4.ipw.cn 获取（强制使用 IPv4）
        - IPv6：通过 http://6.ipw.cn 获取（强制使用 IPv6）
        
        【缓存机制】
        - 缓存有效期：300秒（5分钟）
        - 使用线程锁保护缓存的读写，确保线程安全
        - 如果某个协议获取失败，对应字段会设置为 None
        
        【IPv6 地址标准化】
        获取到的 IPv6 地址会经过 ipaddress 模块验证，确保格式正确。
        虽然以字符串形式存储在缓存中，但在 is_allowed_ip 方法中会转换为对象进行比较。

        Returns:
            typing.Dict: 包含 'ipv4' 和 'ipv6' 键的字典，值是 IP 字符串或 None。
            示例：{'ipv4': '203.0.113.1', 'ipv6': '2001:db8::1'}
        """
        current_time = time.time()

        # 使用实例属性（self._...）进行缓存管理
        with self._public_ip_cache_lock:

            # 检查缓存是否过期（当前时间 - 上次更新时间 < 过期时间）
            if current_time - self._public_ip_cache_time < self.CACHE_EXPIRE_SECONDS:
                logging.debug("[IP验证] 公网IP缓存在有效期内，直接返回缓存数据。")
                return self._public_ip_cache.copy()

            # 缓存过期，执行网络请求进行更新
            logging.info("[IP验证] 公网IP缓存已过期或首次获取，正在重新获取...")

            # --- 获取 IPv4 公网地址 ---
            try:
                # 向 http://4.ipw.cn 发起请求，该服务只返回 IPv4 地址
                # timeout=3: 设置3秒超时，避免长时间等待
                # 最多重试3次，每次间隔1秒，应对瞬时网络抖动
                response_v4 = None
                for _attempt_v4 in range(3):
                    try:
                        response_v4 = _main().requests.get("http://4.ipw.cn", timeout=3)
                        break
                    except Exception as _retry_e:
                        if _attempt_v4 < 2:
                            time.sleep(1)
                        else:
                            raise
                if response_v4 is not None and response_v4.status_code == 200:
                    # 提取响应文本并去除首尾空格
                    ipv4_text = response_v4.text.strip()
                    try:
                        # 验证返回的字符串是否为有效的 IP 地址
                        # 这会抛出 ValueError 如果格式无效
                        ipaddress.ip_address(ipv4_text)
                        # 验证通过，更新缓存
                        self._public_ip_cache["ipv4"] = ipv4_text
                        logging.info(f"[IP验证] 成功获取服务器公网 IPv4: {ipv4_text}")
                    except ValueError:
                        # 返回的不是有效的 IP 地址格式
                        logging.warning(f"[IP验证] 获取的 IPv4 地址格式无效: {ipv4_text}")
                        self._public_ip_cache["ipv4"] = None
                else:
                    # HTTP 状态码不是 200，获取失败
                    logging.warning(
                        f"[IP验证] 获取 IPv4 公网地址失败，状态码: {response_v4.status_code if response_v4 else 'N/A'}")
                    self._public_ip_cache["ipv4"] = None
            except Exception as e:
                # 网络异常或其他错误
                logging.warning(f"[IP验证] 获取 IPv4 公网地址异常: {str(e)}")
                self._public_ip_cache["ipv4"] = None

            # --- 获取 IPv6 公网地址 ---
            try:
                # 向 http://6.ipw.cn 发起请求，该服务只返回 IPv6 地址
                # timeout=3: 设置3秒超时，避免长时间等待
                # 最多重试3次，每次间隔1秒，应对瞬时网络抖动（部分环境 IPv6 间歇性不可达）
                response_v6 = None
                for _attempt_v6 in range(3):
                    try:
                        response_v6 = _main().requests.get("http://6.ipw.cn", timeout=3)
                        break
                    except Exception as _retry_e:
                        if _attempt_v6 < 2:
                            time.sleep(1)
                        else:
                            raise
                if response_v6 is not None and response_v6.status_code == 200:
                    # 提取响应文本并去除首尾空格
                    ipv6_text = response_v6.text.strip()
                    try:
                        # 【IPv6 验证】验证返回的字符串是否为有效的 IPv6 地址
                        # ipaddress 模块会自动标准化 IPv6 地址
                        # 例如：2001:0db8::0001 → 2001:db8::1
                        ipaddress.ip_address(ipv6_text)
                        # 验证通过，更新缓存
                        self._public_ip_cache["ipv6"] = ipv6_text
                        logging.info(f"[IP验证] 成功获取服务器公网 IPv6: {ipv6_text}")
                    except ValueError:
                        # 返回的不是有效的 IPv6 地址格式
                        logging.warning(f"[IP验证] 获取的 IPv6 地址格式无效: {ipv6_text}")
                        self._public_ip_cache["ipv6"] = None
                else:
                    # HTTP 状态码不是 200，获取失败
                    logging.warning(
                        f"[IP验证] 获取 IPv6 公网地址失败，状态码: {response_v6.status_code if response_v6 else 'N/A'}")
                    self._public_ip_cache["ipv6"] = None
            except Exception as e:
                # 网络异常或其他错误（例如：服务器不支持 IPv6）
                logging.warning(f"[IP验证] 获取 IPv6 公网地址异常: {str(e)}")
                self._public_ip_cache["ipv6"] = None

            # 更新缓存时间戳为当前时间
            self._public_ip_cache_time = current_time

            # 返回更新后的缓存数据（返回副本，避免外部修改缓存）
            return self._public_ip_cache.copy()

    def is_allowed_ip(self, client_ip_input: str) -> bool:
        """
        主入口函数：判断一个 IP 地址是否被允许访问。
        允许条件：1. 是内网IP地址。 2. 与服务器自身的公网 IP 地址相同。
        
        【IPv6 完全支持】
        本方法全面支持 IPv4 和 IPv6 地址的验证：
        - 使用 ipaddress 对象进行 IP 地址比较，而不是字符串比较
        - 这确保了 IPv6 地址的各种表示形式（压缩/非压缩）都能正确匹配
        - 例如：2001:db8::1 和 2001:0db8:0000:0000:0000:0000:0000:0001 会被识别为同一地址

        支持多种输入格式：
        - 纯IP: 127.0.0.1, ::1
        - 带协议: http://127.0.0.1, http://[::1]
        - 带端口: 127.0.0.1:8080, [::1]:8080
        - 带协议和端口: https://127.0.0.1:8080, https://[::1]:8080
        
        Args:
            client_ip_input: 客户端 IP 地址（支持多种格式）
            
        Returns:
            bool: 允许访问返回 True，拒绝访问返回 False
        """
        # 解析输入，提取纯 IP 地址字符串
        client_ip = self.extract_ip_from_host(client_ip_input)

        if not client_ip:
            logging.warning(f"[IP验证] 无法从输入中解析IP地址: {client_ip_input}")
            return False

        try:
            # 将客户端 IP 字符串转换为 IP 对象
            # 这会自动标准化 IPv6 地址（例如：::1 和 0:0:0:0:0:0:0:1 会被标准化为 ::1）
            client_ip_obj = ipaddress.ip_address(client_ip)
        except ValueError:
            logging.warning(f"[IP验证] 无效的IP地址格式: {client_ip}")
            return False

        # 1. 检查是否为内网 IP 地址（调用静态方法）
        # 传入 IP 对象，支持 IPv4 和 IPv6
        if self.is_private_ip(client_ip_obj):
            return True

        # 2. 检查是否为服务器自己的公网 IP（调用实例方法，触发缓存检查/更新）
        server_public_ips = self.get_public_ip_addresses()
        cached_ipv4 = server_public_ips.get("ipv4")
        cached_ipv6 = server_public_ips.get("ipv6")

        # 【IPv4 对象比较】检查是否匹配 IPv4 公网地址
        # 使用 IP 对象比较而不是字符串比较，确保准确性
        if cached_ipv4:
            try:
                # 将缓存的 IPv4 字符串转换为 IP 对象
                public_ipv4_obj = ipaddress.ip_address(cached_ipv4)
                # 使用对象的 == 运算符进行比较（基于数值比较）
                if client_ip_obj == public_ipv4_obj:
                    logging.info(f"[IP验证] {client_ip_obj} 是服务器自己的公网 IPv4 地址，允许访问")
                    return True
            except ValueError:
                # 缓存的 IPv4 格式无效（理论上不应该发生，因为在缓存时已经验证过）
                logging.warning(f"[IP验证] 缓存的 IPv4 地址格式无效: {cached_ipv4}")

        # 【IPv6 对象比较】检查是否匹配 IPv6 公网地址
        # 使用 IP 对象比较，自动处理 IPv6 的各种表示形式
        if cached_ipv6:
            try:
                # 将缓存的 IPv6 字符串转换为 IP 对象
                # 这会自动标准化 IPv6 地址（例如：2001:0db8::1 → 2001:db8::1）
                public_ipv6_obj = ipaddress.ip_address(cached_ipv6)
                # 使用对象的 == 运算符进行比较
                # 这确保了 ::1 和 0:0:0:0:0:0:0:1 等不同表示形式会被识别为同一地址
                if client_ip_obj == public_ipv6_obj:
                    logging.info(f"[IP验证] {client_ip_obj} 是服务器自己的公网 IPv6 地址，允许访问")
                    return True
            except ValueError:
                # 缓存的 IPv6 格式无效（理论上不应该发生）
                logging.warning(f"[IP验证] 缓存的 IPv6 地址格式无效: {cached_ipv6}")

        # 拒绝访问：既不是内网 IP，也不是服务器的公网 IP
        logging.warning(f"[IP验证] {client_ip_obj} 不是允许的IP地址，拒绝访问")
        return False

    def check_app_host(self, client_app_host: str) -> bool:
        """
        验证 client_app_host 是否真的是本服务器。

        只接受成功命中当前进程的一次性随机 probe：
        - 路径固定为 `/api/payment/verify_probe/<token>` 模式；
        - 请求体携带一次性随机 challenge；
        - 远端返回 success 仍不足以判定成功，必须同时确认本机 probe 已被消费。
        """
        parsed = self.parse_host_input(client_app_host)

        if not parsed['ip']:
            logging.warning(f"[本机验证] 无法解析host: {client_app_host}")
            return False

        base_url = parsed['full_url']

        if not base_url:
            logging.warning(f"[本机验证] 无法构建请求URL: {client_app_host}")
            return False

        logging.info(
            f"[本机验证] 解析结果 - IP: {parsed['ip']}, 端口: {parsed['port']}, 协议: {parsed['scheme']}, URL: {base_url}")

        token, challenge = _main()._create_payment_verify_probe(ttl_seconds=15)
        verify_url = _main()._build_payment_verify_probe_url(base_url, token)
        try:
            response = _main().requests.post(
                verify_url,
                json={"challenge": challenge},
                timeout=5,
            )

            if response.status_code != 200:
                logging.warning(
                    f"[本机验证] probe 请求失败 - 状态码: {response.status_code}"
                )
                return False

            try:
                response_data = response.json()
            except ValueError as e:
                logging.warning(f"[本机验证] probe 响应JSON解析失败: {str(e)}")
                return False

            if not response_data.get("success"):
                logging.warning("[本机验证] probe 接口返回失败")
                return False

            if not _main()._is_payment_verify_probe_consumed(token):
                logging.warning("[本机验证] probe 未在本机消费成功")
                return False

            logging.info(f"[本机验证] app_host probe 验证通过: {base_url}")
            return True

        except _main().requests.exceptions.Timeout:
            logging.warning(f"[本机验证] 请求超时 - {_main()._redact_sensitive_log_text(base_url)}")
            return False

        except _main().requests.exceptions.ConnectionError:
            logging.warning(f"[本机验证] 连接失败 - {_main()._redact_sensitive_log_text(base_url)}")
            return False

        except Exception as e:
            logging.error(f"[本机验证] 验证过程异常: {type(e).__name__}")
            return False

        finally:
            _cleanup_expired_payment_verify_probes()

    def check_host_has_scheme(self, client_app_host: str) -> bool:
        """
        检查 client_app_host 是否包含协议 ('http://' 或 'https://')。

        Args: 
            client_app_host:  用户输入的host字符串

        Returns: 
            bool: 如果包含协议返回True，否则返回False
        """
        if not client_app_host:
            return False

        host = client_app_host.strip().lower()

        # 检查标准格式
        if host.startswith("http://") or host.startswith("https://"):
            return True

        # 检查特殊格式 (无双斜杠): https:127.0.0.1:8080
        if re.match(r'^https?:[^/]', host):
            return True

        return False

    def normalize_host_url(self, client_app_host: str,
                           default_scheme: str = 'http',
                           default_port: typing.Optional[str] = None) -> typing.Optional[str]:
        """
        将用户输入的host标准化为完整的URL。

        Args:
            client_app_host: 用户输入的host字符串
            default_scheme: 默认协议，当输入没有协议时使用
            default_port: 默认端口，当输入没有端口时使用（可选）

        Returns: 
            str or None: 标准化后的完整URL，或None（如果无法解析）
        """
        parsed = self.parse_host_input(client_app_host)

        if not parsed['ip']:
            return None

        scheme = parsed['scheme'] or default_scheme
        port = parsed['port'] or default_port

        return self.build_full_url(parsed['ip'], port, scheme)

    def normalize_to_url(self, host_input: str,
                         default_scheme: str = 'http',
                         default_port: typing.Optional[str] = None) -> typing.Optional[str]:
        """
        将传入的字符串转换成标准的 URL 格式（不带末尾斜杠）。
        
        【IPv6 完全支持】
        本方法全面支持 IPv6 地址的标准化：
        - IPv6 地址会被自动标准化为规范形式（例如：0:0:0:0:0:0:0:1 → ::1）
        - URL 中的 IPv6 地址会自动添加方括号（例如：::1 → http://[::1]）
        - 支持 IPv4-mapped IPv6 地址（::ffff:x.x.x.x）

        输入输出示例：
        - 输入: 127.0.0.1          → 输出: http://127.0.0.1
        - 输入: http://127.0.0.1:442 → 输出: http://127.0.0.1:442
        - 输入: https://127.0.0.1   → 输出: https://127.0.0.1
        - 输入: 127.0.0.1:8080      → 输出: http://127.0.0.1:8080
        - 输入: https:127.0.0.1:8080 → 输出: https://127.0.0.1:8080
        - 输入: ::1                 → 输出: http://[::1]
        - 输入: [::1]:8080          → 输出: http://[::1]:8080
        - 输入: http://[::1]:8080   → 输出: http://[::1]:8080
        - 输入: ::ffff:192.168.1.1  → 输出: http://[::ffff:192.168.1.1]
        - 输入: 2001:0db8::0001     → 输出: http://[2001:db8::1]（已标准化）

        Args:
            host_input: 用户输入的host字符串，支持以下格式：
                - 纯IPv4: 127.0.0.1
                - 纯IPv6: ::1, 2001:db8::1（会被标准化）
                - 带协议: http://127.0.0.1, https://[::1]
                - 带端口: 127.0.0.1:8080, [::1]:8080
                - 带协议和端口: https://127.0.0.1:8080
                - 特殊格式: https:127.0.0.1:8080（无双斜杠）
                - IPv4-mapped IPv6: ::ffff:127.0.0.1
            default_scheme: 当输入没有协议时使用的默认协议，默认为 'http'
            default_port: 当输入没有端口时使用的默认端口（可选），默认为 None（不添加端口）

        Returns:
            str: 标准化后的完整 URL（不带末尾斜杠）
            None: 如果输入无法解析为有效的 IP 地址
        """
        # 解析输入（会自动标准化 IPv6 地址）
        parsed = self.parse_host_input(host_input)

        # 如果无法解析出有效 IP，返回 None
        if not parsed['ip']:
            logging.warning(f"[URL标准化] 无法解析输入: {host_input}")
            return None

        # 使用解析出的协议，如果没有则使用默认协议
        scheme = parsed['scheme'] if parsed['scheme'] else default_scheme

        # 使用解析出的端口，如果没有则使用默认端口
        port = parsed['port'] if parsed['port'] else default_port

        # 构建并返回完整 URL
        # build_full_url 会自动为 IPv6 地址添加方括号
        result = self.build_full_url(parsed['ip'], port, scheme)

        # 确保末尾没有斜杠
        if result and result.endswith('/'):
            result = result.rstrip('/')

        logging.debug(f"[URL标准化] 输入: {host_input} -> 输出: {result}")

        return result
