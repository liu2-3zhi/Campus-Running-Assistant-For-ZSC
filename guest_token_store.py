from __future__ import annotations

import datetime
import hashlib
import json
import os
import secrets
import threading
import time


DEFAULT_TOKEN_TTL_SECONDS = 3600
DEFAULT_TOKEN_GRACE_SECONDS = 60


class GuestTokenStore:
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        os.makedirs(self.root_dir, exist_ok=True)
        self.index_path = os.path.join(self.root_dir, "_index.json")
        self.lock = threading.RLock()

    def _token_path(self, session_id: str) -> str:
        return os.path.join(self.root_dir, f"{session_id}.json")

    def _load_index(self) -> dict:
        if not os.path.exists(self.index_path):
            return {"sessions": {}}
        with open(self.index_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        data.setdefault("sessions", {})
        return data

    def _save_index(self, data: dict) -> None:
        temp_path = f"{self.index_path}.{os.getpid()}.tmp"
        with open(temp_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2, ensure_ascii=False)
        os.replace(temp_path, self.index_path)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    def create(self, session_id: str) -> str:
        token = secrets.token_hex(256)
        now = time.time()
        record = {
            "token": token,
            "session_id": session_id,
            "principal_type": "guest",
            "username": "guest",
            "created_at": now,
            "expires_at": now + DEFAULT_TOKEN_TTL_SECONDS,
            "last_activity": now,
        }
        with self.lock:
            with open(self._token_path(session_id), "w", encoding="utf-8") as fp:
                json.dump(record, fp, indent=2, ensure_ascii=False)
            index = self._load_index()
            index["sessions"][session_id] = {
                "token_hash": self._hash_token(token),
                "created_at": now,
                "expires_at": record["expires_at"],
                "last_activity": now,
            }
            index["updated_at"] = datetime.datetime.now(
                datetime.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            self._save_index(index)
        return token

    def verify(
        self,
        session_id: str,
        token: str,
        session_active: bool,
        session_expires_at: float,
    ) -> dict:
        with self.lock:
            token_path = self._token_path(session_id)
            if not os.path.exists(token_path):
                return {"valid": False, "reason": "guest_token_missing"}
            with open(token_path, "r", encoding="utf-8") as fp:
                record = json.load(fp)
            if record.get("token") != token:
                return {"valid": False, "reason": "guest_token_invalid"}
            if not session_active:
                return {"valid": False, "reason": "guest_session_missing"}
            expired = time.time() > float(record.get("expires_at", 0))
            self.refresh(session_id, session_expires_at)
            return {
                "valid": True,
                "reason": (
                    "refreshed_for_active_session" if expired else "valid"
                ),
            }

    def refresh(self, session_id: str, session_expires_at: float) -> bool:
        with self.lock:
            token_path = self._token_path(session_id)
            if not os.path.exists(token_path):
                return False
            with open(token_path, "r", encoding="utf-8") as fp:
                record = json.load(fp)
            now = time.time()
            record["last_activity"] = now
            record["expires_at"] = max(
                now + DEFAULT_TOKEN_TTL_SECONDS,
                float(session_expires_at) + DEFAULT_TOKEN_GRACE_SECONDS,
            )
            with open(token_path, "w", encoding="utf-8") as fp:
                json.dump(record, fp, indent=2, ensure_ascii=False)
            index = self._load_index()
            entry = index["sessions"].setdefault(session_id, {})
            entry["token_hash"] = self._hash_token(record["token"])
            entry["last_activity"] = now
            entry["expires_at"] = record["expires_at"]
            self._save_index(index)
            return True

    def invalidate(self, session_id: str) -> None:
        with self.lock:
            try:
                os.remove(self._token_path(session_id))
            except FileNotFoundError:
                pass
            index = self._load_index()
            index["sessions"].pop(session_id, None)
            self._save_index(index)

    def find_session_id(self, token: str) -> str:
        token_hash = self._hash_token(token)
        index = self._load_index()
        for session_id, entry in index.get("sessions", {}).items():
            if entry.get("token_hash") == token_hash:
                return session_id
        return ""

    def find_token_for_session(self, session_id: str) -> str:
        token_path = self._token_path(session_id)
        if not os.path.exists(token_path):
            return ""
        with open(token_path, "r", encoding="utf-8") as fp:
            record = json.load(fp)
        return str(record.get("token") or "")

    def _force_expiry_for_test(self, session_id: str, expires_at: float) -> None:
        with self.lock:
            token_path = self._token_path(session_id)
            with open(token_path, "r", encoding="utf-8") as fp:
                record = json.load(fp)
            record["expires_at"] = expires_at
            with open(token_path, "w", encoding="utf-8") as fp:
                json.dump(record, fp, indent=2, ensure_ascii=False)
