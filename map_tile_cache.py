"""Bounded, credential-opaque disk storage for authenticated map proxy tiles."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import base64
import binascii
import hashlib
import heapq
import itertools
import json
import logging
import math
import os
from pathlib import Path
import re
import stat
import struct
import threading
import time
import uuid


DEFAULT_TTL_SECONDS = 20 * 86400
DEFAULT_MAX_BYTES = 10 * 1000 ** 3
MAX_ENTRY_BYTES = 4 * 1024 * 1024
CLEANUP_INTERVAL_SECONDS = 300
_PROVIDERS = frozenset({"amap", "tencent", "baidu", "tianditu"})
_MAGIC = b"ZXMT1\n"
_MAX_METADATA_BYTES = 8192
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_JSONP_CALLBACK = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*\Z")
_JAVASCRIPT_MIME_TYPES = frozenset({
    "application/javascript", "text/javascript", "application/x-javascript",
    "application/ecmascript", "text/ecmascript",
})
_SAFE_VARY = frozenset({"accept", "accept-language", "accept-encoding", "origin", "referer"})


def _headers(headers):
    return {str(name).lower(): str(value) for name, value in headers.items()}


def _safe_header(value):
    return isinstance(value, str) and len(value) <= 256 and not any(ord(character) < 32 or ord(character) == 127 for character in value)


def build_tile_cache_key(provider, host, path, query, runtime_origin, headers):
    # Preserve query order, duplicates, credentials and version/style fields.
    material = [1, provider, "https", host, path, query, runtime_origin,
                sorted((str(name).lower(), str(value)) for name, value in headers.items())]
    return hashlib.sha256(json.dumps(material, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


def _http_time(value):
    try:
        return parsedate_to_datetime(value).timestamp()
    except (ValueError, TypeError, OverflowError, AttributeError):
        return None


def tile_cache_ttl(headers, *, now=None, default_ttl=DEFAULT_TTL_SECONDS):
    now = time.time() if now is None else now
    values = _headers(headers)
    if "set-cookie" in values:
        return 0
    directives = {}
    for directive in values.get("cache-control", "").split(","):
        name, _, value = directive.strip().partition("=")
        directives[name.lower()] = value.strip().strip('"')
    if any(name in directives for name in ("no-store", "no-cache", "private")):
        return 0
    vary = {field.strip().lower() for field in values.get("vary", "").split(",") if field.strip()}
    if vary - _SAFE_VARY:
        return 0
    ttl = max(0, float(default_ttl))
    age = 0
    try:
        age = max(0, int(values.get("age", "0")))
    except ValueError:
        return 0
    response_date = _http_time(values.get("date"))
    if response_date is not None:
        age = max(age, max(0, now - response_date))
    freshness = directives.get("s-maxage", directives.get("max-age"))
    if freshness is not None:
        try:
            ttl = min(ttl, max(0, int(freshness) - age))
        except ValueError:
            return 0
    elif "expires" in values:
        expires = _http_time(values["expires"])
        if expires is None:
            return 0
        ttl = min(ttl, max(0, expires - (response_date if response_date is not None else now) - age))
    return ttl if math.isfinite(ttl) else 0


def _strict_json(text):
    def distinct_fields(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("duplicate JSON field")
            result[name] = value
        return result

    def invalid_constant(_value):
        raise ValueError("invalid JSON constant")

    return json.loads(text, object_pairs_hook=distinct_fields, parse_constant=invalid_constant)


def parse_jsonp_payload(text, callback, *, max_callback_length=128):
    if (not isinstance(callback, str) or len(callback) > max_callback_length or not _JSONP_CALLBACK.fullmatch(callback)
            or any(part in {"__proto__", "prototype", "constructor", "eval", "Function", "setTimeout", "setInterval"}
                   for part in callback.split("."))):
        raise ValueError("invalid JSONP callback")

    def distinct_fields(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("duplicate JSON field")
            result[name] = value
        return result

    def invalid_constant(_value):
        raise ValueError("invalid JSON constant")

    decoder = json.JSONDecoder(object_pairs_hook=distinct_fields, parse_constant=invalid_constant)
    text = text.strip()
    prefix = re.match(r"(?:/\*\*/\s*)?(?:" + re.escape(callback) + r"\s*&&\s*)?"
                      + re.escape(callback) + r"\s*\(", text)
    if prefix is None:
        raise ValueError("unexpected JSONP callback")
    payload = text[prefix.end():]
    start = len(payload) - len(payload.lstrip())
    value, end = decoder.raw_decode(payload, start)
    cursor = end
    while cursor < len(payload) and payload[cursor] in " \t\r\n":
        cursor += 1
    if cursor >= len(payload) or payload[cursor] != ")":
        raise ValueError("invalid JSONP wrapper")
    cursor += 1
    while cursor < len(payload) and payload[cursor] in " \t\r\n":
        cursor += 1
    if cursor < len(payload) and payload[cursor] == ";":
        cursor += 1
    if payload[cursor:].strip(" \t\r\n"):
        raise ValueError("unexpected content after JSONP")
    return value


def canonical_jsonp_payload(body, callback):
    """Extract JSON without executing a vendor response or retaining its callback."""
    if not body or len(body) > MAX_ENTRY_BYTES:
        raise ValueError("invalid JSONP body size")
    value = parse_jsonp_payload(body.decode("utf-8-sig"), callback)
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _valid_format(provider, kind, context):
    if not isinstance(context, dict):
        return False
    if kind in {"raster", "vector", "either"}:
        return not context
    if kind == "tencent_batch" and provider == "tencent":
        if not context:
            return True
        allowed = {"tile_count", "jsonp_callback"}
        if set(context) - allowed:
            return False
        if "tile_count" in context and (type(context["tile_count"]) is not int or not 1 <= context["tile_count"] <= 256):
            return False
        if "jsonp_callback" in context:
            callback = context["jsonp_callback"]
            if ("tile_count" not in context or not isinstance(callback, str) or len(callback) > 128
                    or not _JSONP_CALLBACK.fullmatch(callback)):
                return False
        return True
    if kind == "baidu_pvd" and provider == "baidu":
        return not context
    return False


def is_cacheable_tile_response(status, body, content_type, kind, *, validation_context=None):
    if status != 200 or not body or len(body) > MAX_ENTRY_BYTES or kind not in {"raster", "vector", "either", "tencent_batch", "baidu_pvd"}:
        return False
    if validation_context is not None and not isinstance(validation_context, dict):
        return False
    mime = content_type.split(";", 1)[0].strip().lower()
    if kind == "baidu_pvd":
        # Current BMap v4 /pvd/ is binary despite its JavaScript MIME.
        return mime == "application/octet-stream" and len(body) > 8 and body.startswith(b"\x02\x00\x00\x00\x02\x00\x00\x00")
    if kind == "tencent_batch":
        context = validation_context or {}
        callback = context.get("jsonp_callback")
        is_jsonp = callback is not None
        if is_jsonp:
            if mime not in _JAVASCRIPT_MIME_TYPES:
                return False
        elif mime not in {"application/octet-stream", "application/json"}:
            return False
        try:
            text = body.decode("utf-8-sig")
            payload = parse_jsonp_payload(text, callback) if is_jsonp else _strict_json(text)
            if not isinstance(payload, dict) or set(payload) != {"datas"}:
                return False
            entries = payload["datas"]
            if not isinstance(entries, list) or not 1 <= len(entries) <= 256:
                return False
            expected = (validation_context or {}).get("tile_count")
            if expected is not None and len(entries) != expected:
                return False
            return all(isinstance(entry, dict) and set(entry) == {"data"} and isinstance(entry["data"], str)
                       and bool(base64.b64decode(entry["data"], validate=True)) for entry in entries)
        except (UnicodeError, ValueError, TypeError, RecursionError, binascii.Error):
            return False
    signatures = {
        "image/png": body.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": body.startswith(b"\xff\xd8\xff"),
        "image/gif": body.startswith((b"GIF87a", b"GIF89a")),
        "image/webp": len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP",
    }
    if kind in {"raster", "either"} and signatures.get(mime, False):
        return True
    if kind not in {"vector", "either"}:
        return False
    if mime not in {"application/x-protobuf", "application/protobuf", "application/vnd.mapbox-vector-tile", "application/octet-stream"}:
        return False
    # Vendors sometimes return HTTP 200 error documents with a binary MIME.
    prefix = body[:256].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if not prefix or prefix.startswith((b"{", b"[", b"<", b"null", b"error", b"callback")):
        return False
    try:
        text = prefix.decode("utf-8")
        if all(character.isprintable() or character.isspace() for character in text):
            return False
    except UnicodeDecodeError:
        pass
    return True


@dataclass(frozen=True)
class CachedTile:
    body: bytes
    content_type: str
    content_language: str = ""


@dataclass(frozen=True)
class _Entry:
    path: Path
    size: int
    created_at: float
    expires_at: float


class MapTileCache:
    def __init__(self, root, *, ttl_seconds=DEFAULT_TTL_SECONDS, max_bytes=DEFAULT_MAX_BYTES,
                 max_entries=None, max_entry_bytes=MAX_ENTRY_BYTES):
        self.root = Path(root).absolute()
        self.ttl_seconds = ttl_seconds
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self.max_entry_bytes = max_entry_bytes
        self.lock = threading.RLock()
        self.entries = OrderedDict()
        self.expirations = []
        self.temporary_files = []
        self.temporary_sizes = {}
        self.sequence = itertools.count()
        self.total_bytes = 0
        self.loaded = False
        self.index_complete = True
        self.next_cleanup = 0

    def _directory(self, provider, shard, *, create=False):
        if provider not in _PROVIDERS or not re.fullmatch(r"[a-f0-9]{2}", shard):
            raise ValueError("invalid tile namespace")
        for path in (self.root, self.root / provider, self.root / provider / shard):
            if path.is_symlink():
                raise ValueError("unsafe tile cache directory")
            if create:
                path.mkdir(exist_ok=True)
            if path.exists() and not path.is_dir():
                raise ValueError("invalid tile cache directory")
        return self.root / provider / shard

    def _path(self, provider, digest, *, create=False):
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise ValueError("invalid tile digest")
        path = self._directory(provider, digest[:2], create=create) / (digest + ".tile")
        if path.is_symlink():
            raise ValueError("unsafe tile cache entry")
        return path

    def _read(self, path, provider, *, include_body):
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            details = os.fstat(stream.fileno())
            if not stat.S_ISREG(details.st_mode) or details.st_size > self.max_entry_bytes + _MAX_METADATA_BYTES + 10:
                raise ValueError("invalid tile file size")
            if stream.read(len(_MAGIC)) != _MAGIC:
                raise ValueError("invalid tile schema")
            size_field = stream.read(4)
            if len(size_field) != 4:
                raise ValueError("incomplete tile metadata")
            size = struct.unpack("!I", size_field)[0]
            if not 0 < size <= _MAX_METADATA_BYTES:
                raise ValueError("invalid tile metadata length")
            metadata = json.loads(stream.read(size))
            created, expires = metadata["created_at"], metadata["expires_at"]
            body_size = metadata["body_length"]
            if (metadata.get("schema") != 2 or metadata.get("provider") != provider or metadata.get("cache_key") != path.stem
                    or not _valid_format(provider, metadata.get("kind"), metadata.get("validation_context"))
                    or type(created) not in (float, int) or not math.isfinite(created)
                    or type(expires) not in (float, int) or not math.isfinite(expires) or expires <= created
                    or type(body_size) is not int or not 0 < body_size <= self.max_entry_bytes
                    or body_size != details.st_size - len(_MAGIC) - 4 - size
                    or not _safe_header(metadata.get("content_type"))
                    or not _safe_header(metadata.get("content_language", ""))
                    or not _DIGEST.fullmatch(str(metadata.get("body_sha256", "")))):
                raise ValueError("invalid tile metadata")
            body = stream.read(body_size + 1) if include_body else None
            if include_body and (len(body) != body_size or hashlib.sha256(body).hexdigest() != metadata["body_sha256"]):
                raise ValueError("invalid tile body")
            if include_body and not is_cacheable_tile_response(200, body, metadata["content_type"], metadata["kind"], validation_context=metadata["validation_context"]):
                raise ValueError("invalid tile content")
            return metadata, body, details.st_size

    def _add_index(self, token, entry):
        previous = self.entries.pop(token, None)
        if previous:
            self.total_bytes -= previous.size
        self.entries[token] = entry
        self.total_bytes += entry.size
        heapq.heappush(self.expirations, (min(entry.expires_at, entry.created_at + self.ttl_seconds), next(self.sequence), token, entry))
        if len(self.expirations) > max(1000, len(self.entries) * 2):
            self.expirations = [(min(row.expires_at, row.created_at + self.ttl_seconds), next(self.sequence), key, row)
                                for key, row in self.entries.items()]
            heapq.heapify(self.expirations)

    def _remove(self, token):
        entry = self.entries.get(token)
        if entry is None:
            return True
        try:
            path = self._path(*token)
            if path != entry.path:
                return False
            if path.exists():
                if not path.is_file():
                    return False
                path.unlink()
        except (OSError, ValueError):
            return False
        self.entries.pop(token, None)
        self.total_bytes -= entry.size
        return True

    def _over_capacity(self, incoming_size=0, replacing=None):
        previous = self.entries.get(replacing)
        size = self.total_bytes + incoming_size - (previous.size if previous else 0)
        count = len(self.entries) + (1 if incoming_size else 0) - (1 if incoming_size and previous else 0)
        return size > self.max_bytes or self.max_entries is not None and count > self.max_entries

    def _make_room(self, incoming_size=0, replacing=None):
        if not self._over_capacity(incoming_size, replacing):
            return True
        # A locked/read-only file remains accounted for; inspect each candidate once.
        for token in list(self.entries):
            if token != replacing:
                self._remove(token)
            if not self._over_capacity(incoming_size, replacing):
                return True
        return False

    def _track_temporary(self, path, cleanup_at):
        directory = self._directory(path.parent.parent.name, path.parent.name)
        if path.parent != directory or path.is_symlink():
            raise ValueError("unsafe tile temporary file")
        details = path.stat()
        if not stat.S_ISREG(details.st_mode):
            raise ValueError("invalid tile temporary file")
        self.total_bytes += details.st_size - self.temporary_sizes.get(path, 0)
        self.temporary_sizes[path] = details.st_size
        heapq.heappush(self.temporary_files, (cleanup_at, str(path), path))

    def _bootstrap(self, now):
        if self.loaded:
            return
        self.loaded = True
        pending = []
        try:
            if self.root.is_symlink() or not self.root.is_dir():
                self.index_complete = not self.root.exists() and not self.root.is_symlink()
                return
            for provider in _PROVIDERS:
                directory = self.root / provider
                if directory.is_symlink() or not directory.is_dir():
                    continue
                for shard in directory.iterdir():
                    if shard.is_symlink() or not shard.is_dir() or not re.fullmatch(r"[a-f0-9]{2}", shard.name):
                        continue
                    for path in shard.iterdir():
                        if path.is_symlink() or not path.is_file():
                            continue
                        if re.fullmatch(r"[a-f0-9]{64}\.tile\.[a-f0-9]{32}\.tmp", path.name) and path.name[:2] == shard.name:
                            self._track_temporary(path, path.stat().st_mtime + CLEANUP_INTERVAL_SECONDS)
                            continue
                        digest = path.stem
                        if path.suffix != ".tile" or not _DIGEST.fullmatch(digest) or digest[:2] != shard.name:
                            continue
                        try:
                            metadata, _, size = self._read(path, provider, include_body=False)
                            entry = _Entry(path, size, metadata["created_at"], metadata["expires_at"])
                            pending.append(((provider, digest), entry))
                        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                            details = path.stat()
                            pending.append(((provider, digest), _Entry(path, details.st_size, details.st_mtime, now)))
        except (OSError, ValueError):
            self.index_complete = False
            logging.debug("[MapProxy] tile cache index unavailable")
        for token, entry in sorted(pending, key=lambda pair: pair[1].created_at):
            self._add_index(token, entry)
        self._maintain(now, force=True)

    def _maintain(self, now, *, force=False):
        if force or now >= self.next_cleanup:
            while self.temporary_files and self.temporary_files[0][0] <= now:
                _, _, path = heapq.heappop(self.temporary_files)
                removed = False
                try:
                    directory = self._directory(path.parent.parent.name, path.parent.name)
                    if path.parent == directory and not path.is_symlink():
                        if path.exists():
                            if not path.is_file():
                                raise ValueError("invalid tile temporary file")
                            path.unlink()
                        removed = True
                except (OSError, ValueError):
                    pass
                if removed:
                    self.total_bytes -= self.temporary_sizes.pop(path, 0)
                else:
                    heapq.heappush(self.temporary_files, (now + CLEANUP_INTERVAL_SECONDS, str(path), path))
            while self.expirations and self.expirations[0][0] <= now:
                _, _, token, entry = heapq.heappop(self.expirations)
                if self.entries.get(token) is entry:
                    if not self._remove(token):
                        heapq.heappush(self.expirations, (now + CLEANUP_INTERVAL_SECONDS, next(self.sequence), token, entry))
            self.next_cleanup = now + CLEANUP_INTERVAL_SECONDS
        self._make_room()

    def configure(self, *, ttl_seconds, max_bytes, now=None):
        now = time.time() if now is None else now
        with self.lock:
            ttl_changed = ttl_seconds != self.ttl_seconds
            size_changed = max_bytes != self.max_bytes
            # Apply the request snapshot before indexing an existing larger cache.
            self.ttl_seconds = ttl_seconds
            self.max_bytes = max_bytes
            self._bootstrap(now)
            if ttl_changed:
                self.expirations = [(min(entry.expires_at, entry.created_at + ttl_seconds), next(self.sequence), token, entry)
                                    for token, entry in self.entries.items()]
                heapq.heapify(self.expirations)
            if ttl_changed or size_changed:
                self._maintain(now, force=True)

    def get(self, provider, digest, *, kind=None, validation_context=None, now=None):
        now = time.time() if now is None else now
        with self.lock:
            self._bootstrap(now)
            self._maintain(now)
            token = (provider, digest)
            entry = self.entries.get(token)
            if entry is None:
                return None
            if min(entry.expires_at, entry.created_at + self.ttl_seconds) <= now:
                self._remove(token)
                return None
            try:
                path = self._path(provider, digest)
                metadata, body, _ = self._read(path, provider, include_body=True)
                if kind is not None and (metadata["kind"] != kind or metadata["validation_context"] != (validation_context or {})):
                    return None
                self.entries.move_to_end(token)
                return CachedTile(body, metadata["content_type"], metadata.get("content_language", ""))
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                self._remove(token)
                return None

    def put(self, provider, digest, body, content_type, headers, *, kind="either", validation_context=None, now=None):
        now = time.time() if now is None else now
        if provider not in _PROVIDERS or not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            return False
        if not isinstance(body, bytes) or not body or len(body) > self.max_entry_bytes:
            return False
        if validation_context is not None and not isinstance(validation_context, dict):
            return False
        context = dict(validation_context or {})
        if not _valid_format(provider, kind, context) or not is_cacheable_tile_response(200, body, content_type, kind, validation_context=context):
            return False
        with self.lock:
            self._bootstrap(now)
            if not self.index_complete:
                return False
            ttl = tile_cache_ttl(headers, now=now, default_ttl=self.ttl_seconds)
            language = _headers(headers).get("content-language", "")
            if not ttl or not _safe_header(content_type) or not _safe_header(language):
                return False
            metadata = {
                "schema": 2, "provider": provider, "cache_key": digest, "created_at": now, "expires_at": now + ttl,
                "kind": kind, "validation_context": context,
                "content_type": content_type, "content_language": language,
                "body_length": len(body), "body_sha256": hashlib.sha256(body).hexdigest(),
            }
            encoded = json.dumps(metadata, ensure_ascii=True, separators=(",", ":")).encode()
            if len(encoded) > _MAX_METADATA_BYTES:
                return False
            payload = _MAGIC + struct.pack("!I", len(encoded)) + encoded + body
            if len(payload) > self.max_bytes:
                return False
            self._maintain(now)
            if not self._make_room(len(payload), (provider, digest)):
                return False
            temporary = None
            try:
                self.root.parent.mkdir(parents=True, exist_ok=True)
                path = self._path(provider, digest, create=True)
                temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
                with open(temporary, "xb") as stream:
                    stream.write(payload)
                os.replace(temporary, path)
                self._add_index((provider, digest), _Entry(path, len(payload), now, now + ttl))
                self._maintain(now)
                return True
            except (OSError, ValueError):
                logging.debug("[MapProxy] tile cache write unavailable")
                return False
            finally:
                if temporary is not None:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        try:
                            self._track_temporary(temporary, now + CLEANUP_INTERVAL_SECONDS)
                            self._maintain(now)
                        except (OSError, ValueError):
                            self.index_complete = False
