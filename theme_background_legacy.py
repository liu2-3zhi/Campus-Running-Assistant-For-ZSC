from __future__ import annotations

import datetime
import json
import logging
import os
import re
import uuid

from theme_background_state import background_files_locked, background_files_log


RANDOM_BACKGROUND_IMAGE_DIR = "random_background_image"
_parse_background_timestamp = datetime.datetime.fromisoformat


@background_files_locked
def _load_random_background_index(cache_dir, strict=False):
    index_path = os.path.join(cache_dir, "index.json")
    default_index = {"files": {}, "feedback": {}, "session_bindings": {}}
    try:
        if not os.path.lexists(index_path):
            return default_index
        if os.path.islink(index_path):
            raise ValueError("background index must be a regular file")
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if strict:
            _protected_legacy_background_urls(data)
        if not isinstance(data, dict):
            return default_index
        files = data.get("files") if isinstance(data.get("files"), dict) else {}
        feedback = data.get("feedback") if isinstance(data.get("feedback"), dict) else {}
        session_bindings = (
            data.get("session_bindings")
            if isinstance(data.get("session_bindings"), dict)
            else {}
        )
        return {
            "files": files,
            "feedback": feedback,
            "session_bindings": session_bindings,
        }
    except Exception as e:
        if strict:
            raise
        background_files_log(logging.WARNING, f"[主题背景] 读取背景索引失败 {index_path}: {e}")
        return default_index


def _protected_legacy_background_urls(index_data):
    if not isinstance(index_data, dict):
        raise ValueError("invalid background index")
    for key in ("files", "feedback", "session_bindings"):
        if key in index_data and not isinstance(index_data[key], dict):
            raise ValueError(f"invalid background index section: {key}")
    for entry in index_data.get("files", {}).values():
        if not isinstance(entry, dict):
            raise ValueError("invalid background index file entry")
    protected = set()
    now = datetime.datetime.now(datetime.timezone.utc)
    for session_entry in index_data.get("session_bindings", {}).values():
        if not isinstance(session_entry, dict):
            raise ValueError("invalid legacy background session")
        for binding in session_entry.values():
            if not isinstance(binding, dict) or not isinstance(binding.get("image_url"), str):
                raise ValueError("invalid legacy background binding")
            expires_at = _parse_background_timestamp(str(binding.get("expires_at") or ""))
            if expires_at.utcoffset() is None:
                raise ValueError("legacy background expiry must include a timezone")
            if expires_at > now and binding["image_url"]:
                protected.add(binding["image_url"])
    return protected


@background_files_locked
def _save_random_background_index(cache_dir, index_data):
    index_path = os.path.join(cache_dir, "index.json")
    safe_index = {
        "files": index_data.get("files", {}) if isinstance(index_data, dict) else {},
        "feedback": index_data.get("feedback", {}) if isinstance(index_data, dict) else {},
        "session_bindings": (
            index_data.get("session_bindings", {}) if isinstance(index_data, dict) else {}
        ),
    }
    temp_index_path = f"{index_path}.{uuid.uuid4().hex}.tmp"
    try:
        with open(temp_index_path, "x", encoding="utf-8") as f:
            json.dump(safe_index, f, indent=2, ensure_ascii=False)
        os.replace(temp_index_path, index_path)
    except Exception as e:
        try:
            if os.path.exists(temp_index_path):
                os.remove(temp_index_path)
        except OSError:
            pass
        background_files_log(logging.WARNING, f"[主题背景] 保存背景索引失败 {index_path}: {e}")


def _normalize_theme_background_target(target):
    return "mobile" if str(target or "").strip().lower() == "mobile" else "pc"


def _normalize_theme_background_session_uuid(session_uuid):
    normalized = str(session_uuid or "").strip()
    if not normalized:
        return ""
    if normalized.lower() in {"null", "undefined", "none"}:
        return ""
    return normalized


@background_files_locked
def _set_session_theme_background_binding(
    cache_dir,
    session_uuid,
    target,
    image_url,
    ttl_seconds=1800,
):
    normalized_session_uuid = _normalize_theme_background_session_uuid(session_uuid)
    normalized_image_url = str(image_url or "").strip()
    if not normalized_session_uuid or not normalized_image_url:
        return None

    normalized_target = _normalize_theme_background_target(target)
    index_data = _load_random_background_index(cache_dir, strict=True)
    session_bindings = index_data.setdefault("session_bindings", {})
    session_entry = session_bindings.get(normalized_session_uuid)
    if not isinstance(session_entry, dict):
        session_entry = {}
        session_bindings[normalized_session_uuid] = session_entry

    now = datetime.datetime.now(datetime.timezone.utc)
    expire_seconds = max(int(ttl_seconds or 0), 1)
    expires_at = now + datetime.timedelta(seconds=expire_seconds)

    binding_entry = {
        "image_url": normalized_image_url,
        "bound_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    session_entry[normalized_target] = binding_entry
    _save_random_background_index(cache_dir, index_data)
    return binding_entry


@background_files_locked
def _get_session_theme_background_binding(cache_dir, session_uuid, target):
    normalized_session_uuid = _normalize_theme_background_session_uuid(session_uuid)
    if not normalized_session_uuid:
        return None

    normalized_target = _normalize_theme_background_target(target)
    index_data = _load_random_background_index(cache_dir, strict=True)
    session_bindings = index_data.get("session_bindings")
    if not isinstance(session_bindings, dict):
        return None

    session_entry = session_bindings.get(normalized_session_uuid)
    if not isinstance(session_entry, dict):
        return None

    binding_entry = session_entry.get(normalized_target)
    if not isinstance(binding_entry, dict):
        return None

    expires_at_raw = binding_entry.get("expires_at")
    try:
        expires_at = _parse_background_timestamp(str(expires_at_raw or ""))
        if expires_at.utcoffset() is None:
            return None
    except Exception:
        return None

    if expires_at <= datetime.datetime.now(datetime.timezone.utc):
        session_entry.pop(normalized_target, None)
        if not session_entry:
            session_bindings.pop(normalized_session_uuid, None)
        _save_random_background_index(cache_dir, index_data)
        return None

    return binding_entry


@background_files_locked
def _resolve_theme_background_binding_decision(
    cache_dir,
    session_uuid,
    target,
    current_image_url,
    login_context=False,
    candidate_image_url="",
    ttl_seconds=1800,
):
    normalized_session_uuid = _normalize_theme_background_session_uuid(session_uuid)
    normalized_current_image_url = str(current_image_url or "").strip()
    normalized_candidate_image_url = str(candidate_image_url or "").strip()

    if not normalized_session_uuid:
        return {"action": "noop", "selected_image_url": normalized_current_image_url}

    if login_context and normalized_candidate_image_url:
        _set_session_theme_background_binding(
            cache_dir,
            session_uuid=normalized_session_uuid,
            target=target,
            image_url=normalized_candidate_image_url,
            ttl_seconds=ttl_seconds,
        )
        return {
            "action": "override_binding",
            "selected_image_url": normalized_candidate_image_url,
        }

    existing_binding = _get_session_theme_background_binding(
        cache_dir,
        normalized_session_uuid,
        target,
    )
    existing_image_url = (
        str(existing_binding.get("image_url") or "")
        if isinstance(existing_binding, dict)
        else ""
    )
    if existing_image_url:
        return {
            "action": "reuse_existing",
            "selected_image_url": existing_image_url,
        }

    if normalized_current_image_url:
        _set_session_theme_background_binding(
            cache_dir,
            session_uuid=normalized_session_uuid,
            target=target,
            image_url=normalized_current_image_url,
            ttl_seconds=ttl_seconds,
        )
        return {
            "action": "bind_new",
            "selected_image_url": normalized_current_image_url,
        }

    return {"action": "noop", "selected_image_url": ""}


@background_files_locked
def _resolve_bound_theme_background_images(cache_dir, session_uuid, targets=None):
    normalized_session_uuid = _normalize_theme_background_session_uuid(session_uuid)
    if not normalized_session_uuid:
        return {}

    normalized_targets = []
    for target in (targets or ["pc", "mobile"]):
        normalized_target = _normalize_theme_background_target(target)
        if normalized_target not in normalized_targets:
            normalized_targets.append(normalized_target)

    if not normalized_targets:
        normalized_targets = ["pc", "mobile"]

    resolved = {}
    for target in normalized_targets:
        binding = _get_session_theme_background_binding(
            cache_dir,
            normalized_session_uuid,
            target,
        )
        image_url = str(binding.get("image_url") or "") if isinstance(binding, dict) else ""
        if image_url:
            resolved[target] = image_url
    return resolved


def _parse_random_background_file_name(file_name):
    normalized_name = str(file_name or "").strip()
    if not normalized_name or normalized_name == "index.json":
        return "", ""
    prefix, _, _ = normalized_name.partition("_")
    image_type = prefix if prefix in ("pc", "mb") else ""
    return normalized_name, image_type


@background_files_locked
def _get_random_background_index_entry(cache_dir, file_name):
    normalized_name, image_type = _parse_random_background_file_name(file_name)
    if not normalized_name:
        return None, ""
    index_data = _load_random_background_index(cache_dir, strict=True)
    files = index_data.setdefault("files", {})
    entry = files.get(normalized_name) if isinstance(files.get(normalized_name), dict) else None
    changed = False
    if not isinstance(entry, dict):
        entry = {"expired": False}
        changed = True
    if "image_type" not in entry and image_type:
        entry["image_type"] = image_type
        changed = True
    if "expired" not in entry:
        entry["expired"] = False
        changed = True
    if changed:
        files[normalized_name] = entry
        _save_random_background_index(cache_dir, index_data)
    return entry, normalized_name


@background_files_locked
def _mark_random_background_file_state(cache_dir, file_name, **fields):
    normalized_name, image_type = _parse_random_background_file_name(file_name)
    if not normalized_name:
        return
    index_data = _load_random_background_index(cache_dir, strict=True)
    files = index_data.setdefault("files", {})
    entry = files.get(normalized_name) if isinstance(files.get(normalized_name), dict) else {}
    entry.update(fields)
    entry.setdefault("expired", False)
    entry.setdefault("image_type", image_type)
    files[normalized_name] = entry
    _save_random_background_index(cache_dir, index_data)


def _mark_random_background_file_expired(cache_dir, image_url, expired=True):
    normalized_url = str(image_url or "").strip()
    prefix = f"/theme-assets/{RANDOM_BACKGROUND_IMAGE_DIR}/"
    if not normalized_url.startswith(prefix):
        return
    file_name = normalized_url[len(prefix):]
    _mark_random_background_file_state(
        cache_dir,
        file_name,
        expired=bool(expired),
        expired_at=datetime.datetime.now().isoformat(timespec="seconds") if expired else None,
        last_used_at=datetime.datetime.now().isoformat(timespec="seconds"),
    )


def _reset_random_background_file_expired(cache_dir, image_url):
    normalized_url = str(image_url or "").strip()
    prefix = f"/theme-assets/{RANDOM_BACKGROUND_IMAGE_DIR}/"
    if not normalized_url.startswith(prefix):
        return
    file_name = normalized_url[len(prefix):]
    _mark_random_background_file_state(
        cache_dir,
        file_name,
        expired=False,
        expired_at=None,
    )


def _extract_background_image_url_from_value(background_value):
    normalized_value = str(background_value or "")
    match = re.search(r'url\(["\']?(/theme-assets/[^"\')]+)["\']?\)', normalized_value, re.IGNORECASE)
    return match.group(1) if match else ""
