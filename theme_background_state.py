from __future__ import annotations

import datetime
import functools
import json
import logging
import os
import sys
import threading
import uuid


STATE_FILE_NAME = "background_state.json"
PREVIEW_TTL_SECONDS = 600
BACKGROUND_FILES_LOCK = threading.RLock()
BACKGROUND_IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".tif", ".tiff",
})
_BACKGROUND_LOG_STATE = threading.local()


def background_files_log(level, message, *args, **kwargs):
    pending = getattr(_BACKGROUND_LOG_STATE, "pending", None)
    if pending is not None:
        if kwargs.get("exc_info") is True:
            kwargs["exc_info"] = sys.exc_info()
        pending.append((level, message, args, kwargs))
    else:
        logging.log(level, message, *args, **kwargs)


def background_files_locked(function):
    @functools.wraps(function)
    def locked(*args, **kwargs):
        pending = None
        try:
            with BACKGROUND_FILES_LOCK:
                outermost = not hasattr(_BACKGROUND_LOG_STATE, "pending")
                if outermost:
                    _BACKGROUND_LOG_STATE.pending = []
                try:
                    return function(*args, **kwargs)
                finally:
                    if outermost:
                        pending = _BACKGROUND_LOG_STATE.pending
                        del _BACKGROUND_LOG_STATE.pending
        finally:
            # Logging handlers can perform maintenance; never enter them while
            # holding the background transaction lock.
            if pending is not None:
                for level, message, log_args, log_kwargs in pending:
                    logging.log(level, message, *log_args, **log_kwargs)

    return locked


def is_background_image_file(cache_dir, file_name, image_type=None):
    if not isinstance(file_name, str) or os.path.basename(file_name) != file_name:
        return False
    prefix = file_name.partition("_")[0]
    if prefix not in ("pc", "mb") or (image_type is not None and prefix != image_type):
        return False
    if os.path.splitext(file_name)[1].lower() not in BACKGROUND_IMAGE_EXTENSIONS:
        return False
    path = os.path.join(cache_dir, file_name)
    return not os.path.islink(path) and os.path.isfile(path)


def empty_state() -> dict:
    return {
        "schema_version": 2,
        "next_revision": 1,
        "assignments": {},
        "bundles": {},
        "identity_bindings": {},
        "guest_bindings": {},
        "auth_claims": {},
    }


class BackgroundStateStore:
    def __init__(self, cache_dir: str):
        self.cache_dir = os.path.abspath(cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.path = os.path.join(self.cache_dir, STATE_FILE_NAME)
        self.lock = BACKGROUND_FILES_LOCK

    def load(self, strict: bool = False) -> dict:
        with self.lock:
            if not os.path.lexists(self.path):
                return empty_state()
            if os.path.islink(self.path):
                raise ValueError("background state must be a regular file")
            with open(self.path, "r", encoding="utf-8") as fp:
                state = json.load(fp)
            if strict:
                self.validate_state(state)
            for key, value in empty_state().items():
                state.setdefault(key, value)
            return state

    @staticmethod
    def validate_state(state: dict) -> None:
        if not isinstance(state, dict) or state.get("schema_version") != 2:
            raise ValueError("invalid background state schema")
        if type(state.get("next_revision")) is not int or state["next_revision"] < 1:
            raise ValueError("invalid background state revision")
        for section in ("assignments", "bundles", "identity_bindings", "guest_bindings", "auth_claims"):
            if not isinstance(state.get(section), dict):
                raise ValueError(f"invalid background state section: {section}")
        assignments = state["assignments"]
        for assignment in assignments.values():
            if not isinstance(assignment, dict) or not isinstance(assignment.get("image_url"), str):
                raise ValueError("invalid background image assignment")
        for bundle in state["bundles"].values():
            if not isinstance(bundle, dict):
                raise ValueError("invalid background bundle")
            for target in ("pc_assignment_id", "mobile_assignment_id"):
                assignment_id = bundle.get(target)
                if not isinstance(assignment_id, str) or assignment_id not in assignments:
                    raise ValueError("background bundle assignment is missing")
        for section in ("identity_bindings", "guest_bindings", "auth_claims"):
            for binding in state[section].values():
                if not isinstance(binding, dict) or binding.get("bundle_id") not in state["bundles"]:
                    raise ValueError("background binding bundle is missing")

    def save(self, state: dict) -> None:
        with self.lock:
            temp_path = f"{self.path}.{uuid.uuid4().hex}.tmp"
            try:
                with open(temp_path, "x", encoding="utf-8") as fp:
                    json.dump(state, fp, indent=2, ensure_ascii=False)
                os.replace(temp_path, self.path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

    @staticmethod
    def _now() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    def create_bundle(
        self,
        pc_url: str,
        mobile_url: str,
        source: str,
        consume: bool = True,
    ) -> dict:
        with self.lock:
            state = self.load()
            revision = int(state.get("next_revision", 1))
            state["next_revision"] = revision + 1
            now = self._now()
            bundle_id = f"bundle_{uuid.uuid4().hex}"
            pc_assignment_id = f"asg_pc_{uuid.uuid4().hex}"
            mobile_assignment_id = f"asg_mb_{uuid.uuid4().hex}"
            state["assignments"][pc_assignment_id] = {
                "target": "pc",
                "image_url": str(pc_url or ""),
                "state": "bound",
                "created_at": now,
                "expires_at": None,
            }
            state["assignments"][mobile_assignment_id] = {
                "target": "mobile",
                "image_url": str(mobile_url or ""),
                "state": "bound",
                "created_at": now,
                "expires_at": None,
            }
            state["bundles"][bundle_id] = {
                "pc_assignment_id": pc_assignment_id,
                "mobile_assignment_id": mobile_assignment_id,
                "state": "consumed" if consume else "preview",
                "source": str(source or ""),
                "created_at": now,
                "consumed_at": now if consume else None,
                "revision": revision,
            }
            self.save(state)
            return {"bundle_id": bundle_id, **state["bundles"][bundle_id]}

    def get_bundle(self, bundle_id: str) -> dict | None:
        state = self.load()
        bundle = state.get("bundles", {}).get(str(bundle_id or ""))
        if not isinstance(bundle, dict):
            return None
        return self._expand_bundle(state, bundle_id, bundle)

    def _expand_bundle(self, state: dict, bundle_id: str, bundle: dict) -> dict:
        assignments = state.get("assignments", {})
        pc = assignments.get(bundle.get("pc_assignment_id"), {})
        mobile = assignments.get(bundle.get("mobile_assignment_id"), {})
        return {
            "bundle_id": bundle_id,
            **bundle,
            "pc_image_url": pc.get("image_url", ""),
            "mobile_image_url": mobile.get("image_url", ""),
        }

    def bind_identity(self, identity_key: str, bundle_id: str, source: str) -> dict:
        with self.lock:
            state = self.load()
            if bundle_id not in state.get("bundles", {}):
                raise KeyError("bundle_not_found")
            binding = {
                "bundle_id": bundle_id,
                "bound_at": self._now(),
                "source": str(source or ""),
            }
            state["identity_bindings"][str(identity_key)] = binding
            self.save(state)
            return dict(binding)

    def get_identity_bundle(self, identity_key: str) -> dict | None:
        state = self.load()
        binding = state.get("identity_bindings", {}).get(str(identity_key or ""))
        if not isinstance(binding, dict):
            return None
        bundle_id = str(binding.get("bundle_id") or "")
        bundle = state.get("bundles", {}).get(bundle_id)
        if not isinstance(bundle, dict):
            return None
        return {**binding, **self._expand_bundle(state, bundle_id, bundle)}

    def bind_guest_session(
        self,
        session_id: str,
        bundle_id: str,
        source: str,
    ) -> dict:
        with self.lock:
            state = self.load()
            if bundle_id not in state.get("bundles", {}):
                raise KeyError("bundle_not_found")
            binding = {
                "bundle_id": bundle_id,
                "bound_at": self._now(),
                "source": str(source or ""),
            }
            state["guest_bindings"][str(session_id)] = binding
            self.save(state)
            return dict(binding)

    def get_guest_session_bundle(self, session_id: str) -> dict | None:
        state = self.load()
        binding = state.get("guest_bindings", {}).get(str(session_id or ""))
        if not isinstance(binding, dict):
            return None
        bundle_id = str(binding.get("bundle_id") or "")
        bundle = state.get("bundles", {}).get(bundle_id)
        if not isinstance(bundle, dict):
            return None
        return {**binding, **self._expand_bundle(state, bundle_id, bundle)}

    def remove_guest_binding(self, session_id: str) -> None:
        with self.lock:
            state = self.load()
            state.get("guest_bindings", {}).pop(str(session_id), None)
            self.save(state)

    def set_auth_claim(
        self,
        auth_session_id: str,
        bundle_id: str,
        expires_at: str,
    ) -> None:
        with self.lock:
            state = self.load()
            state["auth_claims"][str(auth_session_id)] = {
                "bundle_id": str(bundle_id),
                "expires_at": str(expires_at),
            }
            self.save(state)

    def pop_auth_claim(self, auth_session_id: str) -> dict | None:
        with self.lock:
            state = self.load()
            claim = state.get("auth_claims", {}).pop(str(auth_session_id), None)
            self.save(state)
            return claim if isinstance(claim, dict) else None

    @staticmethod
    def protected_urls(state: dict) -> set[str]:
        BackgroundStateStore.validate_state(state)
        protected: set[str] = set()
        assignments = state.get("assignments", {})
        for bundle in state.get("bundles", {}).values():
            if not isinstance(bundle, dict):
                continue
            for key in ("pc_assignment_id", "mobile_assignment_id"):
                assignment = assignments.get(bundle.get(key), {})
                image_url = str(assignment.get("image_url") or "")
                if image_url:
                    protected.add(image_url)
        return protected
