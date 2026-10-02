from __future__ import annotations

import ipaddress
import logging
import os
import re


_trusted_ip_networks_cache = None
_trusted_ip_networks_cache_mtime = None


def _main():
    import main
    return main


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
    except FileNotFoundError as exc:
        load_failure = exc
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
    return any(
        ip_obj in network for network in _main()._BUILTIN_TRUSTED_PROXY_NETWORKS
    )


def _select_forwarded_client_ip(
    forwarded_for,
    peer_ip,
    trusted_networks=None,
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
        return _is_builtin_trusted_proxy_ip(
            ip_obj
        ) or trusted_matcher.matches(ip_obj)

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
    return str(peer_obj)
