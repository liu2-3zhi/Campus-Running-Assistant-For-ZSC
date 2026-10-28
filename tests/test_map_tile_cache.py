import pytest
import os

from map_tile_cache import (
    MapTileCache,
    build_tile_cache_key,
    is_cacheable_tile_response,
    tile_cache_ttl,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"isolated-tile"


def key(provider="amap", query="key=isolated&x=1", origin="https://authorized.example", headers=None):
    return build_tile_cache_key(
        provider, "tiles.example", "/tile", query, origin,
        headers or {"Accept": "image/png", "Accept-Language": "zh-CN"},
    )


def test_cache_survives_new_instance_without_persisting_credentials(tmp_path):
    cache = MapTileCache(tmp_path)
    assert cache.put("amap", key(), PNG, "image/png", {}, now=100)
    restored = MapTileCache(tmp_path)
    tile = restored.get("amap", key(), now=101)
    assert tile.body == PNG
    assert tile.content_type == "image/png"
    for path in tmp_path.rglob("*"):
        assert "isolated" not in path.name
        if path.is_file():
            assert b"authorized.example" not in path.read_bytes()
            assert b"key=isolated" not in path.read_bytes()


@pytest.mark.parametrize("changed", [
    {"provider": "tencent"}, {"query": "key=different&x=1"},
    {"query": "key=isolated&x=2"}, {"query": "x=1&key=isolated"},
    {"origin": "https://other.example"}, {"headers": {"Accept": "image/webp"}},
])
def test_cache_keys_preserve_provider_credential_origin_and_representation(changed):
    assert key(**changed) != key()


def test_expiry_and_hits_do_not_rewrite_disk_files(tmp_path):
    cache = MapTileCache(tmp_path)
    cache.put("amap", key(), PNG, "image/png", {}, now=100)
    path = next(tmp_path.rglob("*.tile"))
    before = path.stat().st_mtime_ns
    assert cache.get("amap", key(), now=101).body == PNG
    assert path.stat().st_mtime_ns == before
    assert cache.get("amap", key(), now=20 * 86400 + 101) is None


def test_global_disk_limit_preserves_provider_namespaces(tmp_path):
    cache = MapTileCache(tmp_path, max_entries=2, max_bytes=4096)
    cache.put("amap", key(), PNG, "image/png", {}, now=100)
    cache.put("tencent", key("tencent"), PNG, "image/png", {}, now=100)
    cache.put("amap", key(query="key=isolated&x=2"), PNG, "image/png", {}, now=101)
    assert cache.get("amap", key(), now=102) is None
    assert cache.get("tencent", key("tencent"), now=102) is not None
    assert len(list(tmp_path.rglob("*.tile"))) == 2


def test_corrupt_and_symlinked_entries_are_not_served(tmp_path):
    cache = MapTileCache(tmp_path)
    cache.put("amap", key(), PNG, "image/png", {}, now=100)
    path = next(tmp_path.rglob("*.tile"))
    path.write_bytes(b"broken")
    assert cache.get("amap", key(), now=101) is None
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    try:
        (outside / "untouched").write_bytes(b"safe")
        provider_path = tmp_path / "baidu"
        try:
            provider_path.symlink_to(outside, target_is_directory=True)
        except OSError:
            return  # Windows may not grant symlink creation to this user.
        assert not cache.put("baidu", key("baidu"), PNG, "image/png", {}, now=100)
        assert (outside / "untouched").read_bytes() == b"safe"
    finally:
        (outside / "untouched").unlink()
        outside.rmdir()


@pytest.mark.parametrize("headers,expected", [
    ({}, 20 * 86400), ({"Cache-Control": "max-age=120", "Age": "20"}, 100),
    ({"Cache-Control": "public, s-maxage=60, max-age=120"}, 60),
    ({"Cache-Control": "no-store"}, 0), ({"Cache-Control": "no-cache"}, 0),
    ({"Cache-Control": "private"}, 0), ({"Cache-Control": "max-age=0"}, 0),
    ({"Set-Cookie": "anonymous=not-persisted"}, 0), ({"Vary": "*"}, 0),
    ({"Vary": "X-Unhandled"}, 0),
])
def test_upstream_cache_policy_is_respected(headers, expected):
    assert tile_cache_ttl(headers, now=100) == expected


@pytest.mark.parametrize("status,body,mime,kind,expected", [
    (200, PNG, "image/png", "raster", True),
    (200, b"\x1a\x03\x0a\x01x", "application/x-protobuf", "vector", True),
    (200, b'{"status":110}', "application/octet-stream", "vector", False),
    (200, b"<error>invalid</error>", "application/octet-stream", "vector", False),
    (200, b"INVALID_USER_KEY", "application/octet-stream", "vector", False),
    (200, b'foo({"status":110});', "application/octet-stream", "vector", False),
    (200, b"not-a-png", "image/png", "raster", False),
    (200, b"", "image/png", "raster", False),
    (403, PNG, "image/png", "raster", False),
    (206, PNG, "image/png", "raster", False),
])
def test_only_successful_complete_binary_tiles_can_be_cached(status, body, mime, kind, expected):
    assert is_cacheable_tile_response(status, body, mime, kind) is expected


@pytest.mark.parametrize("body,expected", [
    (b'{"datas":[{"data":"AQID"},{"data":"BAUG"}]}', True),
    (b'{"status":110,"message":"unauthorized"}', False),
    (b'{"datas":[{"data":"AQID"}],"error":"unauthorized"}', False),
    (b'{"datas":[{"error":"unauthorized"}]}', False),
    (b'{"datas":[{"data":null}]}', False),
    (b'{"datas":[{"data":"not base64!"}]}', False),
    (b'{"datas":[{"data":""}]}', False),
    (b'{"datas":[]}', False),
    (b'{"datas":[{"data":"AQID"}],"datas":[]}', False),
    (b'{"datas":[{"data":"AQID"}]} trailing', False),
])
def test_tencent_json_batch_validation_is_strict(body, expected):
    assert is_cacheable_tile_response(200, body, "application/octet-stream", "tencent_batch") is expected


@pytest.mark.parametrize("body,expected", [
    (b'window.tilesLoaded({"datas":[{"data":"AQID"} ]});', True),
    (b'window.tilesLoaded({"datas":[{"data":"AQID"} ]})', True),
    (b'/**/window.tilesLoaded && window.tilesLoaded({"datas":[{"data":"AQID"}]});', True),
    (b'window.tilesLoaded&&window.tilesLoaded({"datas":[{"data":"AQID"}]})', True),
    (b'window.otherCallback({"datas":[{"data":"AQID"}]});', False),
    (b'window.tilesLoaded ({"datas":[{"data":"AQID"}]});', True),
    (b'window.otherCallback&&window.tilesLoaded({"datas":[{"data":"AQID"}]});', False),
    (b'window.tilesLoaded({"datas":[{"data":"AQID"}]});alert(1);', False),
    (b'alert(1);window.tilesLoaded({"datas":[{"data":"AQID"}]});', False),
    (b'window.tilesLoaded({"datas":[{"data":"AQID"}],"datas":[]});', False),
    (b'window.tilesLoaded({"datas":[{"data":"AQID"}],"n":NaN});', False),
    (b'window.tilesLoaded({"datas":[{"data":"AQID"},{"data":"BAUG"}]});', False),
])
def test_tencent_jsonp_requires_exact_callback_strict_json_and_tile_count(body, expected):
    context = {"tile_count": 1, "jsonp_callback": "window.tilesLoaded"}
    assert is_cacheable_tile_response(200, body, "application/javascript; charset=utf-8",
                                     "tencent_batch", validation_context=context) is expected


@pytest.mark.parametrize("callback", [
    "", "window.otherCallback", "window.tilesLoaded;alert(1)", "window[tilesLoaded]",
    "a" * 129, "window..tilesLoaded", "window.tilesLoaded()",
])
def test_tencent_jsonp_callback_context_must_be_a_bounded_exact_identifier_path(callback):
    assert not is_cacheable_tile_response(
        200, b'window.tilesLoaded({"datas":[{"data":"AQID"}]});',
        "application/javascript", "tencent_batch",
        validation_context={"tile_count": 1, "jsonp_callback": callback},
    )


def test_tencent_jsonp_requires_javascript_mime_and_never_uses_callback_without_context():
    body = b'window.tilesLoaded({"datas":[{"data":"AQID"}]});'
    context = {"tile_count": 1, "jsonp_callback": "window.tilesLoaded"}
    assert not is_cacheable_tile_response(200, body, "application/json", "tencent_batch", validation_context=context)
    assert not is_cacheable_tile_response(200, body, "application/javascript", "tencent_batch")
    assert not is_cacheable_tile_response(200, b'{"datas":[{"data":"AQID"}]}',
                                          "application/javascript", "tencent_batch", validation_context=context)


def test_structured_tile_format_is_persisted_and_revalidated(tmp_path):
    body = b'{"datas":[{"data":"AQID"},{"data":"BAUG"}]}'
    cache = MapTileCache(tmp_path)
    assert cache.put("tencent", key("tencent"), body, "application/octet-stream", {}, kind="tencent_batch", validation_context={"tile_count": 2}, now=100)
    restored = MapTileCache(tmp_path)
    assert restored.get("tencent", key("tencent"), kind="tencent_batch", validation_context={"tile_count": 2}, now=101).body == body
    assert restored.get("tencent", key("tencent"), kind="tencent_batch", validation_context={"tile_count": 1}, now=101) is None
    assert not cache.put("tencent", key("tencent", query="x=2"), body, "application/octet-stream", {}, kind="tencent_batch", validation_context={"tile_count": 1}, now=102)
    assert not cache.put("amap", key(), body, "application/octet-stream", {}, kind="tencent_batch", validation_context={"tile_count": 2}, now=102)


def test_tencent_jsonp_context_and_body_are_revalidated_after_restart(tmp_path):
    body = b'window.tilesLoaded({"datas":[{"data":"AQID"}]});'
    context = {"tile_count": 1, "jsonp_callback": "window.tilesLoaded"}
    cache = MapTileCache(tmp_path)
    assert cache.put("tencent", key("tencent"), body, "application/javascript", {},
                     kind="tencent_batch", validation_context=context, now=100)
    restored = MapTileCache(tmp_path)
    assert restored.get("tencent", key("tencent"), kind="tencent_batch",
                        validation_context=context, now=101).body == body
    assert restored.get("tencent", key("tencent"), kind="tencent_batch",
                        validation_context={"tile_count": 1, "jsonp_callback": "window.otherCallback"}, now=101) is None
    assert restored.get("tencent", key("tencent"), kind="tencent_batch",
                        validation_context={"tile_count": 2, "jsonp_callback": "window.tilesLoaded"}, now=101) is None


@pytest.mark.parametrize("body,expected", [
    (b"\x02\x00\x00\x00\x02\x00\x00\x00\xff\x00\xfd\x10isolated-vector", True),
    (b"\x02\x00\x00\x00\x02\x00\x00\x00", False),
    (b"\x01\x00\x00\x00\x02\x00\x00\x00\xff\x00\xfd\x10isolated-vector", False),
    (b'{"status":220,"message":"unauthorized"}', False),
    (b'BMap.callback({"tile":[]});', False),
])
def test_baidu_pvd_requires_observed_binary_signature(body, expected):
    assert is_cacheable_tile_response(200, body, "application/octet-stream", "baidu_pvd") is expected


def test_entry_size_limit_and_failed_writes_do_not_break_cache(tmp_path):
    cache = MapTileCache(tmp_path, max_entry_bytes=8)
    assert not cache.put("amap", key(), PNG, "image/png", {}, now=100)
    blocked = tmp_path / "blocked"
    blocked.write_bytes(b"not-a-directory")
    unavailable = MapTileCache(blocked)
    assert unavailable.get("amap", key(), now=100) is None
    assert not unavailable.put("amap", key(), PNG, "image/png", {}, now=100)


def test_reduced_ttl_expires_old_entries_and_later_increase_does_not_revive_them(tmp_path):
    cache = MapTileCache(tmp_path)
    cache.put("amap", key(), PNG, "image/png", {}, now=100)
    cache.configure(ttl_seconds=10, max_bytes=4096, now=111)
    assert cache.get("amap", key(), now=111) is None
    cache.configure(ttl_seconds=20 * 86400, max_bytes=4096, now=112)
    assert cache.get("amap", key(), now=112) is None


def test_reduced_total_quota_evicts_only_owned_files_without_rescanning_on_hits(tmp_path, monkeypatch):
    cache = MapTileCache(tmp_path)
    unrelated = tmp_path / "unrelated"
    unrelated.write_bytes(b"keep")
    cache.put("amap", key(), PNG, "image/png", {}, now=100)
    cache.put("tencent", key("tencent"), PNG, "image/png", {}, now=101)
    first_size = next(iter(cache.entries.values())).size
    monkeypatch.setattr(type(tmp_path), "iterdir", lambda _self: pytest.fail("unexpected disk rescan"))
    cache.configure(ttl_seconds=20 * 86400, max_bytes=first_size + 10, now=102)
    assert cache.get("amap", key(), now=102) is None
    assert cache.get("tencent", key("tencent"), now=102) is not None
    assert unrelated.read_bytes() == b"keep"


def test_upstream_date_and_expires_do_not_extend_existing_response_age():
    assert tile_cache_ttl({"Date": "Thu, 01 Jan 1970 00:01:40 GMT", "Cache-Control": "max-age=60"}, now=130) == 30
    assert tile_cache_ttl({"Date": "Thu, 01 Jan 1970 00:01:40 GMT", "Expires": "Thu, 01 Jan 1970 00:03:20 GMT"}, now=130) == 70
    assert tile_cache_ttl({"Date": "Thu, 01 Jan 1970 00:01:40 GMT", "Expires": "Thu, 01 Jan 1970 00:03:20 GMT", "Age": "80"}, now=130) == 20


def test_renaming_an_entry_to_another_tile_digest_cannot_mix_contents(tmp_path):
    cache = MapTileCache(tmp_path)
    cache.put("amap", key(), PNG, "image/png", {}, now=100)
    first = next(tmp_path.rglob("*.tile"))
    digest = key(query="key=isolated&x=3")
    destination = tmp_path / "amap" / digest[:2] / (digest + ".tile")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(first.read_bytes())
    restored = MapTileCache(tmp_path)
    assert restored.get("amap", digest, now=101) is None
    assert restored.get("amap", key(), now=101) is not None


def test_fresh_orphaned_temp_is_cleaned_later_without_rescanning_or_removing_unowned_files(tmp_path, monkeypatch):
    shard = tmp_path / "amap" / key()[:2]
    shard.mkdir(parents=True)
    orphan = shard / (key() + ".tile." + "1" * 32 + ".tmp")
    orphan.write_bytes(b"incomplete")
    os.utime(orphan, (100, 100))
    unrelated = shard / "unrelated.tmp"
    unrelated.write_bytes(b"keep")
    cache = MapTileCache(tmp_path)
    assert cache.get("amap", key(), now=101) is None
    assert orphan.exists()
    monkeypatch.setattr(type(tmp_path), "iterdir", lambda _self: pytest.fail("unexpected disk rescan"))
    assert cache.get("amap", key(), now=402) is None
    assert not orphan.exists()
    assert unrelated.read_bytes() == b"keep"


def test_locked_eviction_candidate_remains_accounted_and_new_write_is_bypassed(tmp_path, monkeypatch):
    cache = MapTileCache(tmp_path)
    assert cache.put("amap", key(), PNG, "image/png", {}, now=100)
    path = next(tmp_path.rglob("*.tile"))
    accounted = cache.total_bytes
    original_unlink = type(path).unlink
    attempts = []

    def locked_unlink(candidate, *args, **kwargs):
        if candidate == path:
            attempts.append(True)
            raise PermissionError("isolated file lock")
        return original_unlink(candidate, *args, **kwargs)

    monkeypatch.setattr(type(path), "unlink", locked_unlink)
    cache.configure(ttl_seconds=20 * 86400, max_bytes=accounted + 10, now=101)
    assert not cache.put("tencent", key("tencent"), PNG, "image/png", {}, now=102)
    assert cache.total_bytes == accounted
    assert ("amap", key()) in cache.entries
    assert list(tmp_path.rglob("*.tile")) == [path]
    assert len(attempts) == 1
    assert cache.get("amap", key(), now=103).body == PNG


def test_locked_file_does_not_prevent_eviction_of_other_candidates(tmp_path, monkeypatch):
    cache = MapTileCache(tmp_path)
    for column in (1, 2, 3):
        assert cache.put("amap", key(query=f"x={column}"), PNG, "image/png", {}, now=100 + column)
    first = cache.entries[("amap", key(query="x=1"))].path
    first_size = cache.entries[("amap", key(query="x=1"))].size
    original_unlink = type(first).unlink

    def locked_unlink(candidate, *args, **kwargs):
        if candidate == first:
            raise PermissionError("isolated file lock")
        return original_unlink(candidate, *args, **kwargs)

    monkeypatch.setattr(type(first), "unlink", locked_unlink)
    cache.configure(ttl_seconds=20 * 86400, max_bytes=first_size, now=110)
    assert list(cache.entries) == [("amap", key(query="x=1"))]
    assert cache.total_bytes == first_size
    assert not cache.put("amap", key(query="x=4"), PNG, "image/png", {}, now=111)


def test_expired_locked_entry_remains_in_quota_until_actual_deletion(tmp_path, monkeypatch):
    cache = MapTileCache(tmp_path)
    assert cache.put("amap", key(), PNG, "image/png", {"Cache-Control": "max-age=1"}, now=100)
    path = next(tmp_path.rglob("*.tile"))
    accounted = cache.total_bytes
    original_unlink = type(path).unlink
    monkeypatch.setattr(type(path), "unlink", lambda candidate, *args, **kwargs:
                        (_ for _ in ()).throw(PermissionError("isolated lock")) if candidate == path else original_unlink(candidate, *args, **kwargs))
    assert cache.get("amap", key(), now=402) is None
    assert cache.total_bytes == accounted
    assert ("amap", key()) in cache.entries
    monkeypatch.setattr(type(path), "unlink", original_unlink)
    assert cache.get("amap", key(), now=703) is None
    assert cache.total_bytes == 0


def test_incomplete_bootstrap_does_not_allow_new_unaccounted_disk_writes(tmp_path, monkeypatch):
    writer = MapTileCache(tmp_path)
    assert writer.put("amap", key(), PNG, "image/png", {}, now=100)
    shard = next((tmp_path / "amap").iterdir())
    original_iterdir = type(shard).iterdir

    def denied_iterdir(path):
        if path == shard:
            raise PermissionError("isolated directory denial")
        return original_iterdir(path)

    monkeypatch.setattr(type(shard), "iterdir", denied_iterdir)
    reader = MapTileCache(tmp_path)
    assert reader.get("amap", key(), now=101) is None
    assert not reader.index_complete
    assert not reader.put("tencent", key("tencent"), PNG, "image/png", {}, now=102)
    monkeypatch.setattr(type(shard), "iterdir", original_iterdir)
    assert len(list(tmp_path.rglob("*.tile"))) == 1
    assert MapTileCache(tmp_path).get("amap", key(), now=103) is not None


def test_locked_owned_temporary_file_remains_accounted_until_actual_cleanup(tmp_path, monkeypatch):
    shard = tmp_path / "amap" / key()[:2]
    shard.mkdir(parents=True)
    orphan = shard / (key() + ".tile." + "1" * 32 + ".tmp")
    orphan.write_bytes(b"incomplete")
    os.utime(orphan, (100, 100))
    original_unlink = type(orphan).unlink

    def locked_unlink(path, *args, **kwargs):
        if path == orphan:
            raise PermissionError("isolated temporary lock")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(type(orphan), "unlink", locked_unlink)
    cache = MapTileCache(tmp_path, max_bytes=10)
    assert cache.get("amap", key(), now=401) is None
    assert cache.total_bytes == 10
    assert orphan in cache.temporary_sizes
    assert not cache.put("amap", key(), PNG, "image/png", {}, now=402)
    monkeypatch.setattr(type(orphan), "unlink", original_unlink)
    cache.get("amap", key(), now=702)
    assert cache.total_bytes == 0
    assert not orphan.exists()


def test_failed_publish_and_failed_temp_removal_are_accounted_before_next_write(tmp_path, monkeypatch):
    original_unlink = type(tmp_path).unlink
    original_replace = os.replace
    monkeypatch.setattr(os, "replace", lambda *_args: (_ for _ in ()).throw(PermissionError("isolated publish lock")))

    def locked_unlink(path, *args, **kwargs):
        if path.suffix == ".tmp":
            raise PermissionError("isolated temporary lock")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "unlink", locked_unlink)
    cache = MapTileCache(tmp_path, max_bytes=4096)
    assert not cache.put("amap", key(), PNG, "image/png", {}, now=100)
    orphan = next(tmp_path.rglob("*.tmp"))
    assert cache.total_bytes == orphan.stat().st_size
    assert orphan in cache.temporary_sizes
    cache.configure(ttl_seconds=20 * 86400, max_bytes=cache.total_bytes, now=101)
    assert not cache.put("amap", key(query="x=2"), PNG, "image/png", {}, now=102)
    assert list(tmp_path.rglob("*.tmp")) == [orphan]
    monkeypatch.setattr(type(tmp_path), "unlink", original_unlink)
    monkeypatch.setattr(os, "replace", original_replace)
    cache.get("amap", key(), now=402)
    assert cache.total_bytes == 0
