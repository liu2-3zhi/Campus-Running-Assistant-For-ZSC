"""Account device identities survive session snapshots without using the parent UA."""

import hashlib
import json
import threading
from types import SimpleNamespace

import pytest

import session_state


SESSION_ID = "55555555-5555-4555-8555-555555555555"
UA_A = "Mozilla/5.0 (Linux; Android 13) account-a"
UA_B = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) account-b"


class SnapshotAccount:
    def __init__(self, username, password, api_bridge, tag=""):
        self.username = username
        self.password = password
        self.device_ua = ""
        self.params = {}
        self.user_data = SimpleNamespace(id="", username="")
        self.all_run_data = []
        self.summary = {}
        self.is_first_login_verified = False


@pytest.fixture
def session_runtime(monkeypatch, tmp_path):
    refresh_started = []
    generated = []

    def generate_ua():
        ua = f"Mozilla/5.0 (Linux; Android 14) generated-{len(generated) + 1}"
        generated.append(ua)
        return ua

    class RefreshThread:
        def __init__(self, target, args=(), **_kwargs):
            self.args = args

        def start(self):
            account = self.args[0]
            refresh_started.append((account.username, account.device_ua))

    runtime = SimpleNamespace(
        SESSION_STORAGE_DIR=str(tmp_path),
        SESSION_INDEX_FILE=str(tmp_path / "_index.json"),
        session_file_locks={},
        session_file_locks_lock=threading.Lock(),
        normalize_session_uuid=lambda value: value if value == SESSION_ID else "",
        get_business_session_login_success=lambda _api: False,
        is_multi_account_logged_in=lambda _account: False,
        _load_session_index=session_state._load_session_index,
        _save_session_index=session_state._save_session_index,
        AccountSession=SnapshotAccount,
        ApiClient=SimpleNamespace(generate_random_ua=generate_ua),
        _is_auto_attendance_enabled=lambda _username: False,
    )
    monkeypatch.setattr(session_state, "_main", lambda: runtime)
    monkeypatch.setattr(
        session_state, "threading", SimpleNamespace(Lock=threading.Lock, Thread=RefreshThread)
    )

    def make_api(stored_accounts=None):
        def load_credentials(_owner, username):
            entry = (stored_accounts or {}).get(username)
            if isinstance(entry, str):
                return {"password": entry, "ua": None}
            return entry

        return SimpleNamespace(
            auth_username="test-owner",
            accounts={},
            global_params={},
            params={},
            device_ua="parent-ua-must-not-be-used",
            is_multi_account_mode=True,
            user_data=None,
            all_run_data=[],
            current_run_idx=-1,
            _load_school_account_credentials=load_credentials,
            _load_account_tag=lambda _username: "",
            _multi_refresh_worker=lambda *_args: None,
        )

    return SimpleNamespace(
        make_api=make_api, refresh_started=refresh_started, generated=generated,
        snapshot_path=tmp_path / f"{hashlib.sha256(SESSION_ID.encode()).hexdigest()}.json",
    )


def test_real_snapshot_round_trip_preserves_each_account_ua_and_verification(session_runtime):
    api = session_runtime.make_api()
    for username, ua in (("20260001", UA_A), ("20260002", UA_B)):
        account = SnapshotAccount(username, "test-password", api)
        account.device_ua = ua
        account.is_first_login_verified = True
        api.accounts[username] = account

    session_state.save_session_state(SESSION_ID, api, force_save=True)
    state = json.loads(session_runtime.snapshot_path.read_text(encoding="utf-8"))
    assert state["multi_account_states"]["20260001"]["device_ua"] == UA_A
    assert state["multi_account_states"]["20260002"]["device_ua"] == UA_B
    assert state["multi_account_states"]["20260001"]["is_first_login_verified"] is True

    restored = session_runtime.make_api({
        "20260001": {"password": "test-a", "ua": "different-stored-a"},
        "20260002": {"password": "test-b", "ua": "different-stored-b"},
    })
    session_state.restore_session_to_api_instance(restored, state)

    assert restored.accounts["20260001"].device_ua == UA_A
    assert restored.accounts["20260002"].device_ua == UA_B
    assert restored.accounts["20260001"].is_first_login_verified is True
    assert restored.accounts["20260002"].password == "test-b"
    assert session_runtime.refresh_started == [("20260001", UA_A), ("20260002", UA_B)]
    assert session_runtime.generated == []
    assert restored.device_ua == "parent-ua-must-not-be-used"


def test_old_snapshot_restores_stored_ua_and_generates_for_legacy_password_entry(session_runtime):
    api = session_runtime.make_api({
        "20260001": {"password": "test-a", "ua": UA_A},
        "20260002": "legacy-test-password",
        "20260003": {"password": "test-c"},
    })
    session_state.restore_session_to_api_instance(api, {
        "is_multi_account_mode": True,
        "multi_account_states": {"20260001": {}, "20260002": {}, "20260003": {}},
    })

    assert set(api.accounts) == {"20260001", "20260002", "20260003"}
    assert api.accounts["20260001"].device_ua == UA_A
    assert api.accounts["20260002"].password == "legacy-test-password"
    assert len(session_runtime.generated) == 2
    assert api.accounts["20260002"].device_ua == session_runtime.generated[0]
    assert api.accounts["20260003"].device_ua == session_runtime.generated[1]
    assert len({ua for _, ua in session_runtime.refresh_started}) == 3
    assert all(ua != api.device_ua for _, ua in session_runtime.refresh_started)


@pytest.mark.parametrize("invalid_ua", [None, "", " null ", "None", "undefined", 123])
def test_invalid_snapshot_ua_uses_the_same_accounts_stored_ua(session_runtime, invalid_ua):
    api = session_runtime.make_api({"20260001": {"password": "test-a", "ua": UA_A}})
    session_state.restore_session_to_api_instance(api, {
        "is_multi_account_mode": True,
        "multi_account_states": {"20260001": {"device_ua": invalid_ua}},
    })

    assert api.accounts["20260001"].device_ua == UA_A
    assert session_runtime.refresh_started == [("20260001", UA_A)]
    assert session_runtime.generated == []


def test_existing_account_preserves_own_ua_and_empty_account_gets_snapshot_ua(session_runtime):
    api = session_runtime.make_api()
    existing = SnapshotAccount("20260001", "test-a", api)
    existing.device_ua = UA_A
    empty = SnapshotAccount("20260002", "test-b", api)
    api.accounts = {existing.username: existing, empty.username: empty}

    session_state.restore_session_to_api_instance(api, {
        "is_multi_account_mode": True,
        "multi_account_states": {
            "20260001": {"device_ua": "stale-snapshot-ua"},
            "20260002": {"device_ua": UA_B},
        },
    })

    assert api.accounts["20260001"] is existing
    assert existing.device_ua == UA_A
    assert empty.device_ua == UA_B
    assert session_runtime.refresh_started == [("20260001", UA_A), ("20260002", UA_B)]
