from __future__ import annotations

import ipaddress
import io
import logging
from storage_io import open, os
from business_storage import StorageError, get_runtime
from sqlalchemy.exc import SQLAlchemyError
import re


_trusted_ip_networks_cache = None
_trusted_ip_networks_cache_mtime = None


class TrustedIpValidationError(ValueError):
    """The submitted text or revision is invalid before any database write."""


from main_runtime import _main


class _TrustedIpMatcher:
    def __init__(
        self,
        networks=(),
        ranges=(),
        wildcard_patterns=(),
        match_all=False,
        entries=(),
    ):
        self.networks = tuple(networks)
        self.ranges = tuple(ranges)
        self.wildcard_patterns = tuple(wildcard_patterns)
        self.match_all = bool(match_all)
        self.entries = tuple(entries)

    def matches(self, ip_obj):
        if isinstance(ip_obj, str):
            ip_obj = ipaddress.ip_address(ip_obj)
        if self.match_all:
            return True

        for network in self.networks:
            if ip_obj.version == network.version and ip_obj in network:
                return True

        ip_value = int(ip_obj)
        for version, start, end in self.ranges:
            if ip_obj.version == version and start <= ip_value <= end:
                return True

        if ip_obj.version == 4:
            packed = ip_obj.packed
            for pattern in self.wildcard_patterns:
                if all(
                    expected is None or packed[index] == expected
                    for index, expected in enumerate(pattern)
                ):
                    return True
        return False


def _parse_trusted_ip_entry(value):
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("empty trusted IP entry")
    if normalized == "*":
        return "all", None

    if "-" in normalized:
        start_text, end_text = (
            part.strip() for part in normalized.split("-", 1)
        )
        start_ip = ipaddress.ip_address(start_text)
        end_ip = ipaddress.ip_address(end_text)
        if start_ip.version != end_ip.version:
            raise ValueError("IP range endpoints must use the same address family")
        if int(start_ip) > int(end_ip):
            raise ValueError("IP range start must not exceed range end")
        return "range", (start_ip.version, int(start_ip), int(end_ip))

    if "*" in normalized:
        parts = normalized.split(".")
        if len(parts) > 4:
            raise ValueError("IPv4 wildcard contains too many octets")
        while len(parts) < 4:
            parts.append("*")
        pattern = []
        for part in parts:
            if part == "*":
                pattern.append(None)
                continue
            if not re.fullmatch(r"\d{1,3}", part):
                raise ValueError("invalid IPv4 wildcard octet")
            octet = int(part)
            if octet < 0 or octet > 255:
                raise ValueError("IPv4 wildcard octet out of range")
            pattern.append(octet)
        if all(item is None for item in pattern):
            return "all", None
        return "wildcard", tuple(pattern)

    return "network", ipaddress.ip_network(normalized, strict=False)


def read_trusted_ip_rules():
    """Return the versioned plain text without consulting a physical file."""
    document = get_runtime().store.get('settings', 'trusted_ips.txt')
    if document is None:
        return {'content': '', 'revision': 0}
    return {'content': document.content.decode('utf-8'), 'revision': document.revision}


def save_trusted_ip_rules(content, revision):
    """Validate the existing line syntax and atomically replace one DB record."""
    if not isinstance(content, str):
        raise TrustedIpValidationError('content 必须是纯文本字符串')
    if type(revision) is not int or revision < 0:
        raise TrustedIpValidationError('revision 必须是非负整数，请重新加载后保存')
    try:
        encoded = content.encode('utf-8')
    except UnicodeError:
        raise TrustedIpValidationError('文本包含无效的 Unicode 字符') from None
    # Universal newline handling matches the reader; the saved text itself is
    # never stripped, normalized, sorted or rewritten.
    for number, raw_line in enumerate(io.StringIO(content, newline=None), 1):
        line = raw_line.split('#', 1)[0].strip()
        if not line:
            continue
        try:
            _parse_trusted_ip_entry(line)
        except ValueError:
            raise TrustedIpValidationError(f'第 {number} 行不是有效的 IP、CIDR、IP 范围或通配符') from None
    document = get_runtime().store.put('settings', 'trusted_ips.txt', encoded,
                                       expected_revision=revision)
    global _trusted_ip_networks_cache, _trusted_ip_networks_cache_mtime
    with _main()._trusted_ip_networks_lock:
        _trusted_ip_networks_cache = None
        _trusted_ip_networks_cache_mtime = None
    return {'content': document.content.decode('utf-8'), 'revision': document.revision}


def _print_red_console_warning(message):
    try:
        print(f"\033[31m{message}\033[0m", flush=True)
    except Exception:
        pass


def _load_trusted_ip_networks(file_path=None):
    trusted_file = file_path or _main().TRUSTED_IPS_FILE
    networks = []
    ranges = []
    wildcard_patterns = []
    match_all = False
    entries = []
    wildcard_entries = []
    load_failure = None
    saw_physical_content = False

    try:
        with open(trusted_file, "r", encoding="utf-8") as file:
            for raw_line in file:
                if raw_line.strip():
                    saw_physical_content = True
                line = raw_line.split("#", 1)[0].strip()
                if not line:
                    continue
                try:
                    entry_type, entry_value = _parse_trusted_ip_entry(line)
                except ValueError:
                    logging.warning("[可信IP] 忽略无效条目: %s", line)
                    continue

                entries.append(line)
                if entry_type == "all":
                    match_all = True
                    wildcard_entries.append(line)
                elif entry_type == "wildcard":
                    wildcard_patterns.append(entry_value)
                    wildcard_entries.append(line)
                elif entry_type == "range":
                    ranges.append(entry_value)
                else:
                    networks.append(entry_value)
    except (StorageError, SQLAlchemyError):
        raise
    except Exception as exc:
        load_failure = exc
    else:
        if not saw_physical_content:
            load_failure = ValueError("文件内容为空")

    if load_failure is not None:
        warning = (
            "[可信IP警告] trusted_ips.txt 加载失败，"
            "已降级为信任全部代理来源: "
            f"{load_failure}"
        )
        _print_red_console_warning(warning)
        logging.warning(warning)
        return _TrustedIpMatcher(match_all=True)

    if wildcard_entries:
        warning = (
            "[可信IP警告] trusted_ips.txt 使用了通配符条目: "
            + ", ".join(wildcard_entries)
            + "；匹配范围内的所有地址都会被信任，请确认安全边界。"
        )
        _print_red_console_warning(warning)
        logging.warning(warning)

    return _TrustedIpMatcher(
        networks=networks,
        ranges=ranges,
        wildcard_patterns=wildcard_patterns,
        match_all=match_all,
        entries=entries,
    )


def _get_trusted_ip_networks():
    global _trusted_ip_networks_cache, _trusted_ip_networks_cache_mtime
    try:
        file_mtime = os.path.getmtime(_main().TRUSTED_IPS_FILE)
    except OSError:
        file_mtime = None
    with _main()._trusted_ip_networks_lock:
        if (
            _trusted_ip_networks_cache is None
            or file_mtime != _trusted_ip_networks_cache_mtime
        ):
            _trusted_ip_networks_cache = _load_trusted_ip_networks()
            _trusted_ip_networks_cache_mtime = file_mtime
        return _trusted_ip_networks_cache


def _is_builtin_trusted_proxy_ip(ip_obj):
    ip_obj = getattr(ip_obj, "ipv4_mapped", None) or ip_obj
    return any(
        ip_obj in network for network in _main()._BUILTIN_TRUSTED_PROXY_NETWORKS
    )


def _select_forwarded_client_ip(
    forwarded_for,
    peer_ip,
    trusted_networks=None,
    *,
    real_ip=None,
):
    peer_text = str(peer_ip or "").strip()
    try:
        peer_obj = ipaddress.ip_address(peer_text)
    except ValueError:
        return peer_text

    if trusted_networks is None:
        trusted_matcher = _get_trusted_ip_networks()
    elif isinstance(trusted_networks, _TrustedIpMatcher):
        trusted_matcher = trusted_networks
    else:
        trusted_matcher = _TrustedIpMatcher(
            networks=tuple(trusted_networks)
        )

    def _is_trusted(ip_obj):
        ipv4_mapped = getattr(ip_obj, "ipv4_mapped", None)
        return (_is_builtin_trusted_proxy_ip(ip_obj) or trusted_matcher.matches(ip_obj)
                or (ipv4_mapped is not None and trusted_matcher.matches(ipv4_mapped)))

    if not _is_trusted(peer_obj):
        return str(peer_obj)

    candidates = []
    for token in str(forwarded_for or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            candidates.append(ipaddress.ip_address(token))
        except ValueError:
            continue

    for candidate in reversed(candidates):
        if not _is_trusted(candidate):
            return str(candidate)
    if candidates:
        return str(candidates[0])
    try:
        return str(ipaddress.ip_address(str(real_ip or "").strip()))
    except ValueError:
        return str(peer_obj)


def _get_request_client_ip(request):
    key = "trusted_ip.client_ip"
    environ = request.environ
    if key not in environ:
        client_ip = _select_forwarded_client_ip(
            request.headers.get("X-Forwarded-For"),
            environ.get("REMOTE_ADDR") or request.remote_addr,
            real_ip=request.headers.get("X-Real-IP"),
        )
        environ[key] = client_ip
        if client_ip:
            environ["REMOTE_ADDR"] = client_ip
            request.remote_addr = client_ip
    return environ[key]
