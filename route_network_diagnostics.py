"""Bounded, credential-free direct probes after a route request times out.

These Python sockets do not reproduce Chromium's proxy or resolver path. System
DNS cannot be cancelled: a stalled lookup retains its concurrency slot until
the daemon exits, while route planning never waits for it. No HTTP is sent.
"""

import ipaddress
import importlib
from itertools import islice
import os
import sys
from time import monotonic


def _native_module(name):
    # Older deployments can monkey-patch these modules before loading us.
    try:
        from eventlet.patcher import original
        return original(name)
    except Exception:
        return importlib.import_module(name)


socket = _native_module("socket")
ssl = _native_module("ssl")
_threading = _native_module("threading")
Thread = _threading.Thread


_PROVIDER_HOSTS = {
    "amap": frozenset({"webapi.amap.com", "restapi.amap.com"}),
    "tencent": frozenset({"map.qq.com", "apis.map.qq.com"}),
    "tianditu": frozenset({"api.tianditu.gov.cn", "api.tianditu.com"}),
    "baidu": frozenset({"api.map.baidu.com"}),
}
_PROXY_VARIABLES = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
)
_PROBE_SLOTS = _threading.BoundedSemaphore(2)
_BUDGET_SECONDS = 4.0
_SOCKET_TIMEOUT_SECONDS = 1.0


def route_network_environment(include_details=False):
    """Keep the public default safe; optionally include full server-log details."""
    result = {
        "platform": sys.platform,
        "python_version": ".".join(str(value) for value in sys.version_info[:3]),
        "proxy_env_present": {name: name in os.environ for name in _PROXY_VARIABLES},
        "probe_transport": "python_direct",
        "browser_proxy_usage": "unknown",
        "proxy_env_confirms_browser_proxy": False,
    }
    if include_details:
        result["proxy_env"] = {name: os.environ[name] for name in _PROXY_VARIABLES if name in os.environ}
    return result


def select_route_probe_hosts(provider, hosts):
    """Select up to two official hosts from at most 128 untrusted input rows."""
    selected = []
    try:
        allowed = _PROVIDER_HOSTS.get(provider)
        if not allowed or isinstance(hosts, (str, bytes, dict)):
            return selected
        for host in islice(hosts, 128):
            if isinstance(host, str) and host in allowed and host not in selected:
                selected.append(host)
                if len(selected) == 2:
                    break
    except Exception:
        pass
    return selected


def _failure_fields(error, include_details=False):
    try:
        number = getattr(error, "errno", None)
    except Exception:
        number = None
    result = {
        "error_type": type(error).__name__[:80],
        "errno": number if isinstance(number, int) and not isinstance(number, bool) else None,
    }
    if include_details:
        result["error_message"] = str(error)
    return result


def _close(resource):
    if resource is not None:
        try:
            resource.close()
        except Exception:
            pass


def _selected_addresses(rows):
    selected = {}
    for family, _kind, _protocol, _canonical, address in rows:
        if family not in (socket.AF_INET, socket.AF_INET6) or family in selected:
            continue
        parsed = ipaddress.ip_address(address[0].split("%", 1)[0])
        if parsed.version != (4 if family == socket.AF_INET else 6):
            continue
        ip = str(parsed)
        target = (ip, 443) if family == socket.AF_INET else (
            ip, 443, address[2] if len(address) > 2 else 0,
            address[3] if len(address) > 3 else 0,
        )
        selected[family] = (ip, target)
        if len(selected) == 2:
            break
    return selected


def _run_probe(provider, hosts, emit, slots, include_details=False):
    started = monotonic()
    deadline = started + _BUDGET_SECONDS

    def report(phase, state, **fields):
        try:
            emit("network_probe", provider=provider, probe_transport="python_direct",
                 phase=phase, state=state, elapsed_ms=round((monotonic() - started) * 1000),
                 **fields)
        except Exception:
            pass  # A broken diagnostic sink must not change business behavior.

    def timeout():
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError()
        return min(_SOCKET_TIMEOUT_SECONDS, remaining)

    try:
        report("start", "started", environment=route_network_environment(include_details=include_details), port=443,
               budget_s=_BUDGET_SECONDS, dns_cancellable=False,
               dns_timeout_control="system", sends_http=False)
        for host in hosts:
            if monotonic() >= deadline:
                break
            dns_started = monotonic()
            report("dns", "started", host=host, dns_cancellable=False, dns_timeout_control="system")
            try:
                # getaddrinfo has no portable cancellation or per-call deadline.
                rows = socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
                selected = _selected_addresses(rows)
                addresses = [{"family": "ipv4" if family == socket.AF_INET else "ipv6", "ip": value[0]}
                             for family, value in selected.items()]
                report("dns", "ok" if selected else "error", host=host, addresses=addresses,
                       duration_ms=round((monotonic() - dns_started) * 1000),
                       dns_cancellable=False, dns_timeout_control="system")
            except Exception as error:
                report("dns", "error", host=host,
                       duration_ms=round((monotonic() - dns_started) * 1000),
                       dns_cancellable=False, dns_timeout_control="system", **_failure_fields(error, include_details))
                continue
            for family, (ip, address) in selected.items():
                if monotonic() >= deadline:
                    break
                fields = {"host": host, "family": "ipv4" if family == socket.AF_INET else "ipv6", "ip": ip}
                raw = secured = None
                stage = "tcp"
                stage_started = monotonic()
                try:
                    raw = socket.socket(family, socket.SOCK_STREAM)
                    raw.settimeout(timeout())
                    raw.connect(address)
                    report("tcp", "ok", **fields, duration_ms=round((monotonic() - stage_started) * 1000))
                    if monotonic() >= deadline:
                        break
                    stage = "tls"
                    stage_started = monotonic()
                    context = ssl.create_default_context()
                    secured = context.wrap_socket(raw, server_hostname=host, do_handshake_on_connect=False)
                    secured.settimeout(timeout())
                    secured.do_handshake()
                    report("tls", "ok", **fields, duration_ms=round((monotonic() - stage_started) * 1000))
                except Exception as error:
                    report(stage, "error", **fields,
                           duration_ms=round((monotonic() - stage_started) * 1000), **_failure_fields(error, include_details))
                finally:
                    _close(secured)
                    _close(raw)
    except Exception as error:
        report("worker", "error", **_failure_fields(error, include_details))
    finally:
        try:
            report("finished", "finished", budget_exhausted=monotonic() >= deadline,
                   dns_cancellable=False, dns_timeout_control="system", budget_s=_BUDGET_SECONDS)
        finally:
            slots.release()


def schedule_route_network_probe(provider, hosts, emit, include_details=False):
    """Start at most two bounded daemon probes; never resolve or wait here.

    False means rejected input, occupied capacity, or an unavailable worker.
    Emission happens only in the daemon so even a slow callback cannot delay
    the caller. The caller's closure retains the original route diagnostic ID.
    """
    slots = None
    acquired = False
    try:
        allowed = _PROVIDER_HOSTS.get(provider)
        if not allowed or not callable(emit) or not isinstance(hosts, (list, tuple)) or not 1 <= len(hosts) <= 2:
            return False
        if any(not isinstance(host, str) or host not in allowed for host in hosts):
            return False
        hosts = tuple(dict.fromkeys(hosts))
        slots = _PROBE_SLOTS
        acquired = slots.acquire(blocking=False)
        if not acquired:
            return False
        Thread(target=_run_probe, args=(provider, hosts, emit, slots, include_details),
               name="RouteNetworkProbe", daemon=True).start()
        return True
    except Exception:
        if acquired:
            slots.release()
        return False
