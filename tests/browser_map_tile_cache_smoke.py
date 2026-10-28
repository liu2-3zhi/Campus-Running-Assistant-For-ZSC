"""Helpers for opt-in real map tile cache checks; never persist request URLs."""

import hashlib
import json
import re
import base64
import binascii
from concurrent.futures import ThreadPoolExecutor
import threading
from urllib.parse import parse_qsl, urlsplit

import requests

from map_request_proxy import _strip_control_query
from map_tile_cache import is_cacheable_tile_response


def evaluate_tile_probe(row):
    return bool(row.get("statuses") == [200, 200]
                and row.get("cache_states", [None, None])[-1] == "HIT"
                and row.get("same_body") and row.get("size", 0) > 0
                and row.get("second_upstream_calls") == 0)


def evaluate_tile_cache_policy(row):
    if evaluate_tile_probe(row):
        return True
    return bool(row.get("statuses") == [200, 200]
                and row.get("cache_states") == ["BYPASS", "BYPASS"]
                and row.get("same_body") and row.get("size", 0) > 0
                and row.get("second_upstream_calls") == 1
                and row.get("bypass_reason") in {"set_cookie", "upstream_cache_policy"})


def describe_tile_response(response):
    parsed = urlsplit(response.url)
    parts = parsed.path.split("/", 5)
    if len(parts) != 6 or parts[1] != "map-proxy":
        return None
    mime = response.headers.get("content-type", "").split(";")[0].lower()
    if not (mime.startswith("image/") or mime in (
        "application/x-protobuf", "application/vnd.mapbox-vector-tile",
        "application/octet-stream", "application/x-pbf", "application/protobuf",
    ) or (parts[2] == "baidu" and parts[5] == "pvd/" and "javascript" in mime)):
        return None
    return {"host": parts[4], "path": "/" + parts[5], "status": response.status,
            "mime": mime, "query_fields": sorted({key for key, _ in parse_qsl(parsed.query)}),
            "proxy_cache_policy": response.headers.get("cache-control", ""),
            "cache_state": response.headers.get("x-map-cache", "")}


def probe_tile_cache(page, responses, upstream_counts, sanitize=lambda value: value, *, upstream_policies=None):
    observed, probes, seen = [], [], set()
    for response in responses:
        info = describe_tile_response(response)
        if info is None or response.url in seen:
            continue
        info["path"] = sanitize(info["path"])
        seen.add(response.url)
        observed.append(info)
        if response.status != 200 or len(probes) >= 4:
            continue
        if info["cache_state"] == "BYPASS" and not any(
            name in info["path"].lower() for name in ("tile", "wmts", "dataserver", "/pvd", "/shad")
        ):
            continue
        parsed = urlsplit(response.url)
        parts = parsed.path.split("/", 5)
        query = _strip_control_query(parsed.query)
        upstream = "https://" + parts[4] + "/" + parts[5] + ("?" + query if query else "")
        digest = hashlib.sha256(upstream.encode()).hexdigest()
        original_headers = response.request.all_headers()
        headers = {key: value for key, value in original_headers.items() if key in ("accept", "accept-language")}
        first = page.request.get(response.url, headers=headers, timeout=20000)
        before = upstream_counts.get(digest, 0)
        second = page.request.get(response.url, headers=headers, timeout=20000)
        first_body, second_body = first.body(), second.body()
        try:
            payload = json.loads(second_body)
            body_shape = safe_shape(payload)
            if isinstance(payload, dict):
                body_shape["fields"] = {name: type(value).__name__ for name, value in payload.items() if re_safe_name(name)}
            elif isinstance(payload, list):
                body_shape["length"] = len(payload)
                if payload and isinstance(payload[0], dict):
                    body_shape["item_fields"] = {name: type(value).__name__ for name, value in payload[0].items() if re_safe_name(name)}
        except (ValueError, UnicodeError):
            body_shape = {"type": "non_json"}
            try:
                text = second_body.decode("utf-8")
                if all(character.isprintable() or character in "\r\n\t" for character in text[:256]):
                    skeleton = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', "STR", text)
                    body_shape["prefix_shape"] = sanitize(re.sub(r"[0-9]+", "N", skeleton))[:240]
                start = next(index for index, character in enumerate(text) if character in "{[")
                payload, consumed = json.JSONDecoder().raw_decode(text[start:])
                prefix = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', "STR", text[:start])
                body_shape = {"type": "json_wrapper", "prefix_shape": sanitize(re.sub(r"[0-9]+", "N", prefix))[:160],
                              "suffix_shape": sanitize(text[start + consumed:])[:40], "payload": safe_shape(payload)}
                if isinstance(payload, dict):
                    body_shape["fields"] = {name: type(value).__name__ for name, value in payload.items() if re_safe_name(name)}
                elif isinstance(payload, list):
                    body_shape["length"] = len(payload)
                    if payload and isinstance(payload[0], dict):
                        body_shape["item_fields"] = {name: type(value).__name__ for name, value in payload[0].items() if re_safe_name(name)}
            except (ValueError, UnicodeError, StopIteration):
                pass
        row = {**info, "statuses": [first.status, second.status],
               "cache_states": [first.headers.get("x-map-cache"), second.headers.get("x-map-cache")],
               "same_body": first_body == second_body, "size": len(second_body),
               "binary_format_accepted": is_cacheable_tile_response(200, second_body, info["mime"], "either"),
               "body_shape": body_shape,
               "second_upstream_calls": upstream_counts.get(digest, 0) - before}
        row["passed"] = evaluate_tile_probe(row)
        policy = (upstream_policies or {}).get(digest, {})
        if policy.get("sets_cookie"):
            row["bypass_reason"] = "set_cookie"
        elif policy.get("effective_ttl_seconds") == 0:
            row["bypass_reason"] = "upstream_cache_policy"
        row["policy_pass"] = evaluate_tile_cache_policy(row)
        if not probes:
            cookies = {item["name"]: item["value"] for item in page.context.cookies()}
            assert parsed.hostname == "127.0.0.1", "concurrency probes must use only the isolated server"
            gate = threading.Barrier(4)
            concurrent_headers = {**headers, "Accept-Language": "zh-CN,zx-cache-probe;q=0.1"}
            baseline = upstream_counts.get(digest, 0)
            def fetch_same_tile():
                gate.wait(timeout=5)
                with requests.Session() as client:
                    client.trust_env = False
                    with client.get(response.url, headers=concurrent_headers, cookies=cookies, timeout=20) as result:
                        return result.status_code, result.headers.get("X-Map-Cache"), result.content
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(lambda _: fetch_same_tile(), range(4)))
            row["concurrent_cache_states"] = [result[1] for result in results]
            row["concurrent_upstream_calls"] = upstream_counts.get(digest, 0) - baseline
            row["concurrent_same_body"] = all(result[0] == 200 and result[2] == results[0][2] for result in results)
            row["concurrent_pass"] = row["concurrent_same_body"] and row["concurrent_upstream_calls"] == 1 and "COALESCED" in row["concurrent_cache_states"]
        probes.append(row)
        first.dispose()
        second.dispose()
    return {"observed_binary_resources": observed[:40], "tile_cache_checks": probes,
            "tile_cache_pass": bool(probes) and all(row["passed"] and row.get("concurrent_pass", True) for row in probes),
            "tile_cache_policy_pass": bool(probes) and all(row["policy_pass"] and row.get("concurrent_pass", True) for row in probes)}


def re_safe_name(value):
    return isinstance(value, str) and value.isascii() and value.replace("_", "").isalpha() and len(value) <= 32


def safe_shape(value, depth=0):
    result = {"type": type(value).__name__}
    if isinstance(value, str):
        result["length"] = len(value)
        try:
            decoded = base64.b64decode(value, validate=True)
            result["base64_nonempty"] = bool(decoded)
        except (ValueError, binascii.Error):
            result["base64_nonempty"] = False
    if isinstance(value, dict) and depth < 3:
        result["members"] = {name: safe_shape(child, depth + 1) for name, child in list(value.items())[:20] if re_safe_name(name)}
    elif isinstance(value, list):
        result["length"] = len(value)
        if depth < 3:
            result["items"] = [safe_shape(child, depth + 1) for child in value[:2]]
    return result
