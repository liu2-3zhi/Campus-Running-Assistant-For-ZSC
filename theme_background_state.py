from __future__ import annotations

import datetime
import json
import os
import threading
import uuid


STATE_FILE_NAME = "background_state.json"
PREVIEW_TTL_SECONDS = 600


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
        self.lock = threading.RLock()

    def load(self) -> dict:
        with self.lock:
            if not os.path.exists(self.path):
                return empty_state()
            with open(self.path, "r", encoding="utf-8") as fp:
                state = json.load(fp)
            for key, value in empty_state().items():
                state.setdefault(key, value)
            return state

    def save(self, state: dict) -> None:
        with self.lock:
            temp_path = f"{self.path}.{os.getpid()}.tmp"
            with open(temp_path, "w", encoding="utf-8") as fp:
                json.dump(state, fp, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.path)

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
