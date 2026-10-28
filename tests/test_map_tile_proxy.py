from concurrent.futures import ThreadPoolExecutor
from functools import wraps
import threading
from types import SimpleNamespace

from flask import Flask, g
import pytest
import requests

from map_request_proxy import PROXY_COOKIE_NAME, PROXY_COOKIE_PATH, _tile_kind, register_map_proxy_routes


SESSION = "11111111-1111-4111-8111-111111111111"
TILE = "/map-proxy/tianditu/https/t0.tianditu.gov.cn/vec_w/wmts?REQUEST=GetTile&TILECOL=1&TILEROW=2&TILEMATRIX=3&tk=isolated"
PNG = b"\x89PNG\r\n\x1a\n" + b"isolated-tile"


def upstream(status=200, body=PNG, headers=None):
    return SimpleNamespace(status_code=status, content=body,
                           headers={"Content-Type": "image/png", **(headers or {})}, close=lambda: None)


def make_proxy(tmp_path, transport, *, max_concurrent_requests=2):
    app = Flask(__name__)
    app.secret_key = "isolated-cache-test"
    app.testing = True
    config = {"Map": {"frontend_proxy_enabled": True}}
    allowed = [True]

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            g.user, g.session_id = "isolated-admin", SESSION
            return view(*args, **kwargs)
        return wrapped

    proxy = register_map_proxy_routes(
        app, login_required, lambda: SimpleNamespace(get=lambda section, key, fallback=None: config.get(section, {}).get(key, fallback)), lambda *_args: allowed[0],
        transport=transport, tile_cache_dir=tmp_path,
        dns_resolver=lambda _host, port, **_kwargs: [(None, None, None, None, ("8.8.8.8", port))],
        max_concurrent_requests=max_concurrent_requests,
    )
    with app.test_client() as client:
        client.set_cookie("auth_token", "isolated-token")
        assert client.post("/api/map-proxy/context", headers={"Origin": "http://localhost", "X-Session-ID": SESSION}).status_code == 200
        signed = client.get_cookie(PROXY_COOKIE_NAME, path=PROXY_COOKIE_PATH).value

    def fetch(path=TILE, *, headers=None, token="isolated-token"):
        with app.test_client() as client:
            if token:
                client.set_cookie("auth_token", token)
            client.set_cookie(PROXY_COOKIE_NAME, signed, path=PROXY_COOKIE_PATH)
            response = client.get(path, headers=headers or {})
            return response.status_code, response.data, dict(response.headers)

    return proxy, fetch, config, allowed


def test_second_tile_request_hits_disk_cache_and_keeps_browser_no_store(tmp_path):
    calls = []
    proxy, fetch, _, _ = make_proxy(tmp_path, lambda *args, **kwargs: calls.append(True) or upstream())
    assert fetch()[2]["X-Map-Cache"] == "MISS"
    result = fetch()
    assert result[:2] == (200, PNG)
    assert result[2]["X-Map-Cache"] == "HIT"
    assert result[2]["Cache-Control"] == "no-store"
    assert calls == [True]
    assert list(tmp_path.rglob("*.tile"))


def test_cached_tile_is_not_read_after_logout_revocation_or_proxy_disable(tmp_path):
    calls = []
    _, fetch, config, allowed = make_proxy(tmp_path, lambda *args, **kwargs: calls.append(True) or upstream())
    assert fetch()[0] == 200
    assert fetch(token="")[0] == 401
    allowed[0] = False
    assert fetch()[0] == 401
    allowed[0] = True
    config["Map"]["frontend_proxy_enabled"] = False
    assert fetch()[0] == 404
    assert calls == [True]


def test_changed_origin_and_key_do_not_reuse_cached_tile(tmp_path):
    calls = []
    _, fetch, config, _ = make_proxy(tmp_path, lambda *args, **kwargs: calls.append(True) or upstream())
    assert fetch()[0] == 200
    assert fetch(TILE.replace("tk=isolated", "tk=different"))[2]["X-Map-Cache"] == "MISS"
    config["Map"]["backend_page_origin"] = "https://different.example"
    assert fetch()[2]["X-Map-Cache"] == "MISS"
    assert len(calls) == 3


@pytest.mark.parametrize("headers", [{"Range": "bytes=0-1"}, {"If-None-Match": "isolated"}, {"If-Modified-Since": "Wed, 28 Oct 2026 00:00:00 GMT"}])
def test_conditional_and_range_requests_bypass_cache(tmp_path, headers):
    calls = []
    _, fetch, _, _ = make_proxy(tmp_path, lambda *args, **kwargs: calls.append(True) or upstream())
    fetch()
    assert fetch(headers=headers)[2]["X-Map-Cache"] == "BYPASS"
    assert len(calls) == 2


@pytest.mark.parametrize("status,body,headers", [
    (403, PNG, {}), (200, b'{"status":110}', {"Content-Type": "application/octet-stream"}),
    (200, PNG, {"Cache-Control": "no-store"}), (200, PNG, {"Set-Cookie": "isolated=not-persisted"}),
])
def test_error_or_uncacheable_response_is_not_persisted(tmp_path, status, body, headers):
    calls = []
    _, fetch, _, _ = make_proxy(tmp_path, lambda *args, **kwargs: calls.append(True) or upstream(status, body, headers))
    fetch()
    fetch()
    assert len(calls) == 2
    assert not list(tmp_path.rglob("*.tile"))


def test_concurrent_identical_tiles_share_upstream_without_using_extra_permits(tmp_path):
    release, entered = threading.Event(), threading.Event()
    calls = []

    def transport(*args, **kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return upstream()

    proxy, fetch, _, _ = make_proxy(tmp_path, transport)
    condition = threading.Condition()
    waiters = []
    original = proxy._wait_for_tile

    def observed_wait(*args):
        with condition:
            waiters.append(True)
            condition.notify_all()
        return original(*args)

    proxy._wait_for_tile = observed_wait
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(fetch)]
        assert entered.wait(2)
        futures += [executor.submit(fetch) for _ in range(5)]
        try:
            with condition:
                assert condition.wait_for(lambda: len(waiters) == 5, timeout=2)
            assert calls == [True]
            release.set()
            results = [future.result(3) for future in futures]
        finally:
            release.set()
    assert [result[0] for result in results] == [200] * 6
    assert results[0][2]["X-Map-Cache"] == "MISS"
    assert all(result[2]["X-Map-Cache"] == "COALESCED" for result in results[1:])
    assert not proxy._tile_flights


def test_identical_tile_followers_join_when_admission_capacity_is_one(tmp_path):
    release, entered = threading.Event(), threading.Event()
    calls = []

    def transport(*args, **kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return upstream()

    proxy, fetch, _, _ = make_proxy(
        tmp_path, transport, max_concurrent_requests=1
    )
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = [executor.submit(fetch)]
        assert entered.wait(2)
        futures.extend(executor.submit(fetch) for _ in range(6))
        try:
            release.set()
            results = [future.result(3) for future in futures]
        finally:
            release.set()

    assert [result[0] for result in results] == [200] * 7
    assert calls == [True]
    assert results[0][2]["X-Map-Cache"] == "MISS"
    assert all(result[2]["X-Map-Cache"] == "COALESCED" for result in results[1:])
    assert not proxy._tile_flights
    assert proxy.admission_semaphore.acquire(blocking=False)
    proxy.admission_semaphore.release()


def test_admission_is_released_before_inflight_entry_is_removed(tmp_path):
    release, entered = threading.Event(), threading.Event()

    def transport(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return upstream()

    proxy, fetch, _, _ = make_proxy(
        tmp_path, transport, max_concurrent_requests=1
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        request = executor.submit(fetch)
        assert entered.wait(2)
        flight = next(iter(proxy._tile_flights.values()))
        original_lock = proxy._tile_flight_lock
        permit_available_at_removal = []

        class ObserveFinalizationLock:
            def __enter__(self):
                original_lock.acquire()
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                original_lock.release()
                if flight.event.is_set() and flight not in proxy._tile_flights.values():
                    available = proxy.admission_semaphore.acquire(blocking=False)
                    permit_available_at_removal.append(available)
                    if available:
                        proxy.admission_semaphore.release()
                return False

        proxy._tile_flight_lock = ObserveFinalizationLock()
        release.set()
        try:
            assert request.result(3)[0] == 200
        finally:
            release.set()

    assert permit_available_at_removal == [True]
    assert not proxy._tile_flights


@pytest.mark.parametrize("path,body,headers", [
    (TILE, PNG, {"Content-Type": "image/png", "Set-Cookie": "isolated=not-persisted"}),
    ("/map-proxy/baidu/https/apimaponline0.bdimg.com/pvd/?ak=isolated&param=isolated&qt=vtile&v=1&callback=isolatedTile", b"isolatedTile({\"tile\": []});", {"Content-Type": "text/javascript"}),
])
def test_uncacheable_tile_responses_still_share_concurrent_upstream(tmp_path, path, body, headers):
    release, entered, waiting = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def transport(*args, **kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return upstream(body=body, headers=headers)

    proxy, fetch, _, _ = make_proxy(tmp_path, transport)
    original = proxy._wait_for_tile

    def observe(*args):
        waiting.set()
        return original(*args)

    proxy._wait_for_tile = observe
    with ThreadPoolExecutor(max_workers=2) as executor:
        owner = executor.submit(fetch, path)
        assert entered.wait(2)
        follower = executor.submit(fetch, path)
        try:
            assert waiting.wait(2)
            release.set()
            results = [owner.result(2), follower.result(2)]
        finally:
            release.set()
    assert calls == [True]
    assert results[0][:2] == results[1][:2] == (200, body)
    assert results[0][2]["X-Map-Cache"] == "BYPASS"
    assert results[1][2]["X-Map-Cache"] == "COALESCED"
    assert "Set-Cookie" not in results[0][2] and "Set-Cookie" not in results[1][2]
    assert not list(tmp_path.rglob("*.tile"))
    assert not proxy._tile_flights
    assert fetch(path)[2]["X-Map-Cache"] == "BYPASS"
    assert calls == [True, True]


def test_new_proxy_instance_can_read_previous_instances_disk_entry(tmp_path):
    calls = []
    _, first, _, _ = make_proxy(tmp_path, lambda *args, **kwargs: calls.append(True) or upstream())
    assert first()[2]["X-Map-Cache"] == "MISS"
    _, second, _, _ = make_proxy(tmp_path, lambda *args, **kwargs: calls.append(True) or upstream())
    assert second()[2]["X-Map-Cache"] == "HIT"
    assert calls == [True]


def test_waiter_timeout_does_not_cancel_owner_or_leak_admission(tmp_path):
    release, entered = threading.Event(), threading.Event()
    calls = []

    def transport(*args, **kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return upstream()

    proxy, fetch, _, _ = make_proxy(tmp_path, transport)
    proxy._wait_for_tile = lambda *_args: None
    with ThreadPoolExecutor(max_workers=2) as executor:
        owner = executor.submit(fetch)
        assert entered.wait(2)
        try:
            assert fetch()[0] == 504
            assert calls == [True]
            release.set()
            assert owner.result(2)[0] == 200
        finally:
            release.set()
    assert fetch()[2]["X-Map-Cache"] == "HIT"
    assert not proxy._tile_flights


def test_owner_failure_notifies_waiter_without_persisting_error_or_leaking_permits(tmp_path):
    release, entered, waiting = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def transport(*args, **kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        raise requests.ReadTimeout("isolated failure")

    proxy, fetch, _, _ = make_proxy(tmp_path, transport)
    original = proxy._wait_for_tile

    def observe(*args):
        waiting.set()
        return original(*args)

    proxy._wait_for_tile = observe
    with ThreadPoolExecutor(max_workers=2) as executor:
        owner = executor.submit(fetch)
        assert entered.wait(2)
        follower = executor.submit(fetch)
        try:
            assert waiting.wait(2)
            release.set()
            assert owner.result(2)[0] == follower.result(2)[0] == 502
        finally:
            release.set()
    assert len(calls) == 2  # The single owner retains the existing two-attempt Tianditu policy.
    assert not proxy._tile_flights
    assert not list(tmp_path.rglob("*.tile"))
    proxy.transport = lambda *args, **kwargs: upstream()
    assert fetch()[2]["X-Map-Cache"] == "MISS"


def test_reduced_runtime_quota_enforces_saved_global_limit(tmp_path):
    calls = []
    payload = PNG + b"x" * (4 * 1024 * 1024 - len(PNG))
    _, fetch, config, _ = make_proxy(tmp_path, lambda *args, **kwargs: calls.append(True) or upstream(body=payload))
    for column in (1, 2, 3):
        assert fetch(TILE.replace("TILECOL=1", f"TILECOL={column}"))[2]["X-Map-Cache"] == "MISS"
    config["Map"]["tile_cache_max_size_gb"] = "0.01"
    assert fetch()[2]["X-Map-Cache"] == "MISS"
    assert len(calls) == 4
    assert sum(path.stat().st_size for path in tmp_path.rglob("*.tile")) <= 10_000_000


@pytest.mark.parametrize("provider,host,path,query,expected", [
    ("amap", "jsapi-data1.amap.com", "/tile/current/v2/road/pbf/0/1_2_3", "auth_key=isolated", "vector"),
    ("tencent", "rt1.map.gtimg.com", "/tile", "building=1&compress=2&mapType=1&style=2&styleid=1&tiles=3_1_2,3_2_2&version=1", "tencent_batch"),
    ("tencent", "rt1.map.gtimg.com", "/tile", "tiles=3_1_2,invalid", None),
    ("tencent", "p1.map.gtimg.com", "/tile", "tiles=3_1_2,3_2_2", None),
    ("tencent", "pr.map.qq.com", "/pingd", "tiles=3_1_2", None),
    ("baidu", "apimaponline0.bdimg.com", "/starpic/", "ak=isolated&fm=1&qt=tile&u=isolated-geometry", "raster"),
    ("baidu", "apimaponline0.bdimg.com", "/pvd/", "qt=tile&u=isolated-geometry", None),
    ("baidu", "apimaponline0.bdimg.com", "/pvd/", "ak=isolated&param=isolated&qt=vtile&v=1", "baidu_pvd"),
    ("baidu", "api.map.baidu.com", "/pvd/", "ak=isolated&param=isolated&qt=vtile&v=1", None),
    ("baidu", "apimaponline0.bdimg.com", "/pvd/", "ak=isolated&param=isolated&qt=tile&v=1", None),
    ("baidu", "apimaponline0.bdimg.com", "/pvd/", "ak=isolated&param=isolated&qt=auth&v=1", None),
    ("baidu", "api.map.baidu.com", "/images/logo.png", "x=1&y=2&z=3", None),
    ("tianditu", "t0.tianditu.gov.cn", "/vec_w/wmts", "REQUEST=GetTile&TILECOL=1&TILEROW=2&TILEMATRIX=3&tk=isolated", "raster"),
    ("tianditu", "t0.tianditu.gov.cn", "/vec_w/wmts", "REQUEST=GetCapabilities&tk=isolated", None),
])
def test_tile_classification_is_scoped_to_confirmed_endpoints(provider, host, path, query, expected):
    assert _tile_kind(provider, host, path, query) == expected


@pytest.mark.parametrize("path,payload,mime", [
    ("/map-proxy/tencent/https/rt1.map.gtimg.com/tile?tiles=3_1_2,3_2_2&styleid=1&version=1", b'{"datas":[{"data":"AQID"},{"data":"BAUG"}]}', "application/octet-stream"),
    ("/map-proxy/baidu/https/apimaponline0.bdimg.com/starpic/?ak=isolated&fm=1&qt=tile&u=isolated-geometry", b"\xff\xd8\xff\xe0isolated-image\xff\xd9", "image/jpeg"),
])
def test_observed_tencent_batch_and_baidu_raster_responses_are_cached(tmp_path, path, payload, mime):
    calls = []
    _, fetch, _, _ = make_proxy(tmp_path, lambda *args, **kwargs: calls.append(True) or upstream(body=payload, headers={"Content-Type": mime, "Cache-Control": "max-age=172800"}))
    assert fetch(path)[2]["X-Map-Cache"] == "MISS"
    assert fetch(path)[2]["X-Map-Cache"] == "HIT"
    assert calls == [True]


def test_tencent_jsonp_batch_is_validated_and_cached_at_proxy_boundary(tmp_path):
    path = "/map-proxy/tencent/https/rt1.map.gtimg.com/tile?tiles=3_1_2,3_2_2&styleid=1&version=1&callback=ZXMap.tilesLoaded"
    body = b'ZXMap.tilesLoaded&&ZXMap.tilesLoaded({"datas":[{"data":"AQID"},{"data":"BAUG"}]});'
    release, entered, waiting = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def transport(*args, **kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return upstream(
            body=body,
            headers={"Content-Type": "text/javascript", "Cache-Control": "max-age=172800"},
        )

    proxy, fetch, _, _ = make_proxy(
        tmp_path,
        transport,
    )
    original = proxy._wait_for_tile

    def observe_wait(*args):
        waiting.set()
        return original(*args)

    proxy._wait_for_tile = observe_wait

    with ThreadPoolExecutor(max_workers=2) as executor:
        owner = executor.submit(fetch, path)
        assert entered.wait(2)
        follower = executor.submit(fetch, path)
        try:
            assert waiting.wait(2)
            release.set()
            first, coalesced = owner.result(2), follower.result(2)
        finally:
            release.set()
    second = fetch(path)

    assert first[:2] == coalesced[:2] == second[:2] == (200, body)
    assert first[2]["Content-Type"].startswith("text/javascript")
    assert first[2]["X-Map-Cache"] == "MISS"
    assert coalesced[2]["X-Map-Cache"] == "COALESCED"
    assert second[2]["X-Map-Cache"] == "HIT"
    assert second[2]["Cache-Control"] == "no-store"
    assert calls == [True]


def test_baidu_pvd_binary_is_not_decoded_as_javascript_and_survives_cache_restart(tmp_path):
    path = "/map-proxy/baidu/https/apimaponline0.bdimg.com/pvd/?ak=isolated&param=isolated&qt=vtile&v=1"
    payload = b"\x02\x00\x00\x00\x02\x00\x00\x00" + b"\x00\xff\xfd\x10isolated-vector"
    calls = []
    _, fetch, _, _ = make_proxy(tmp_path, lambda *args, **kwargs: calls.append(True) or upstream(body=payload, headers={"Content-Type": "text/javascript", "Cache-Control": "max-age=120"}))
    first = fetch(path)
    assert first[:2] == (200, payload)
    assert first[2]["Content-Type"] == "application/octet-stream"
    assert first[2]["X-Map-Cache"] == "MISS"
    _, restored, _, _ = make_proxy(tmp_path, lambda *args, **kwargs: pytest.fail("cache hit must not fetch upstream"))
    second = restored(path)
    assert second[:2] == (200, payload)
    assert second[2]["Content-Type"] == "application/octet-stream"
    assert second[2]["X-Map-Cache"] == "HIT"
    assert calls == [True]


def test_jsonp_callbacks_share_one_tile_flight_and_persisted_payload(tmp_path):
    path = "/map-proxy/tencent/https/rt1.map.gtimg.com/tile?tiles=3_1_2,3_2_2&styleid=1&version=1&callback="
    payload = b'{"datas":[{"data":"AQID"},{"data":"BAUG"}]}'
    release, entered, waiting = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def transport(*args, **kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return upstream(body=b"ZXMap.first(" + payload + b");", headers={"Content-Type": "text/javascript"})

    proxy, fetch, _, _ = make_proxy(tmp_path, transport)
    original = proxy._wait_for_tile

    def observe_wait(*args):
        waiting.set()
        return original(*args)

    proxy._wait_for_tile = observe_wait
    with ThreadPoolExecutor(max_workers=2) as executor:
        owner = executor.submit(fetch, path + "ZXMap.first")
        assert entered.wait(2)
        follower = executor.submit(fetch, path + "ZXMap.second")
        try:
            assert waiting.wait(2)
            release.set()
            first, second = owner.result(2), follower.result(2)
        finally:
            release.set()
    assert first[:2] == (200, b"ZXMap.first&&ZXMap.first(" + payload + b");")
    assert second[:2] == (200, b"ZXMap.second&&ZXMap.second(" + payload + b");")
    assert second[2]["X-Map-Cache"] == "COALESCED"
    _, restored, _, _ = make_proxy(tmp_path, lambda *args, **kwargs: pytest.fail("cache hit must not fetch upstream"))
    third = restored(path + "ZXMap.third")
    assert third[:2] == (200, b"ZXMap.third&&ZXMap.third(" + payload + b");")
    assert third[2]["Content-Type"].startswith("text/javascript")
    assert third[2]["X-Map-Cache"] == "HIT"
    assert calls == [True]


def test_jsonp_cache_preserves_callback_guard_after_map_unmount(tmp_path):
    import subprocess

    path = "/map-proxy/tencent/https/rt1.map.gtimg.com/tile?tiles=3_1_2&callback=ZXMap.loaded"
    body = b'ZXMap.loaded&&ZXMap.loaded({"datas":[{"data":"AQID"}]});'
    _, fetch, _, _ = make_proxy(tmp_path, lambda *args, **kwargs: upstream(body=body, headers={"Content-Type": "text/javascript"}))
    for expected_cache in ("MISS", "HIT"):
        result = fetch(path)
        assert result[2]["X-Map-Cache"] == expected_cache
        execution = subprocess.run(["node", "-e", "const ZXMap = {};\n" + result[1].decode("ascii")],
                                   capture_output=True, text=True, timeout=5)
        assert execution.returncode == 0, execution.stderr


@pytest.mark.parametrize("body", [
    b'ZXMap.first({"status":110,"message":"unauthorized"});',
    b'ZXMap.first({"datas":[{"data":"AQID"}]});alert(1)',
    b'ZXMap.first({"datas":[{"data":"AQID"}],"datas":[]});',
])
def test_invalid_jsonp_tile_is_never_saved_or_replayed_under_another_callback(tmp_path, body):
    path = "/map-proxy/tencent/https/rt1.map.gtimg.com/tile?tiles=3_1_2&callback="
    release, entered, waiting = threading.Event(), threading.Event(), threading.Event()

    def transport(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return upstream(body=body, headers={"Content-Type": "text/javascript"})

    proxy, fetch, _, _ = make_proxy(tmp_path, transport)
    original = proxy._wait_for_tile

    def observe_wait(*args):
        waiting.set()
        return original(*args)

    proxy._wait_for_tile = observe_wait
    with ThreadPoolExecutor(max_workers=2) as executor:
        owner = executor.submit(fetch, path + "ZXMap.first")
        assert entered.wait(2)
        follower = executor.submit(fetch, path + "ZXMap.second")
        try:
            assert waiting.wait(2)
            release.set()
            owner.result(2)
            second = follower.result(2)
        finally:
            release.set()
    assert b"ZXMap.first" not in second[1]
    assert second[0] == 502 or second[1].startswith(b"ZXMap.second&&ZXMap.second(")
    assert not list(tmp_path.rglob("*.tile"))
    assert not proxy._tile_flights
