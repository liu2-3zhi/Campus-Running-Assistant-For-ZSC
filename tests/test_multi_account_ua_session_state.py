"""Account device identities survive session snapshots without using the parent UA."""

import hashlib
import json
import threading
from types import SimpleNamespace

import pytest

import session_state


SESSION_ID = "55555555-5555-4555-8555-555555555555"
UA_A = "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 Chrome/121.0.0.0 Mobile Safari/537.36"
UA_B = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/122.0.0.0 Mobile Safari/537.36"
PARENT_UA = UA_A.replace("Pixel 6", "Parent device")
LEGACY_IOS_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) legacy"
LEGACY_DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"
LEGACY_CUSTOM_UA = "legacy-client/1.0"


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
    persisted = []
    lookups = []

    def generate_ua():
        ua = UA_B.replace("Pixel 8", f"Generated device {len(generated) + 1}")
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
        def load_credentials(owner, username, *, own_only=False):
            lookups.append((owner, username, own_only))
            entry = (stored_accounts or {}).get(username)
            if isinstance(entry, str):
                return {"password": entry, "ua": None}
            return entry

        return SimpleNamespace(
            auth_username="test-owner",
            accounts={},
            global_params={},
            params={},
            device_ua=PARENT_UA,
            is_multi_account_mode=True,
            user_data=None,
            all_run_data=[],
            current_run_idx=-1,
            _load_school_account_credentials=load_credentials,
            _persist_missing_school_account_ua=lambda owner, username, ua: persisted.append((owner, username, ua)),
            _load_account_tag=lambda _username: "",
            _multi_refresh_worker=lambda *_args: None,
        )

    return SimpleNamespace(
        make_api=make_api, refresh_started=refresh_started, generated=generated,
        persisted=persisted, lookups=lookups,
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
        "20260001": {"password": "test-a", "ua": UA_B},
        "20260002": {"password": "test-b", "ua": UA_A},
    })
    session_state.restore_session_to_api_instance(restored, state)

    assert restored.accounts["20260001"].device_ua == UA_A
    assert restored.accounts["20260002"].device_ua == UA_B
    assert restored.accounts["20260001"].is_first_login_verified is True
    assert restored.accounts["20260002"].password == "test-b"
    assert session_runtime.refresh_started == [("20260001", UA_A), ("20260002", UA_B)]
    assert session_runtime.generated == []
    assert restored.device_ua == PARENT_UA


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


@pytest.mark.parametrize("invalid_ua", [
    None, "", " null ", "None", "undefined", 123,
    LEGACY_IOS_UA, LEGACY_DESKTOP_UA, LEGACY_CUSTOM_UA,
])
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


def test_rebuilt_accounts_repair_legacy_ua_for_restored_accounts_only(session_runtime):
    api = session_runtime.make_api({
        "20260001": {"password": "test-a", "ua": LEGACY_IOS_UA},
        "20260002": {"password": "test-b", "ua": LEGACY_DESKTOP_UA},
        "20260003": {"password": "test-c", "ua": LEGACY_CUSTOM_UA},
    })
    session_state.restore_session_to_api_instance(api, {
        "is_multi_account_mode": True,
        "multi_account_states": {
            "20260001": {"device_ua": UA_A},
            "20260002": {"device_ua": LEGACY_CUSTOM_UA},
        },
    })

    assert len(session_runtime.generated) == 1
    ua_b = session_runtime.generated[0]
    assert api.accounts["20260001"].device_ua == UA_A
    assert api.accounts["20260002"].device_ua == ua_b
    assert session_runtime.persisted == [
        ("test-owner", "20260001", UA_A), ("test-owner", "20260002", ua_b),
    ]
    assert session_runtime.lookups == [
        ("test-owner", "20260001", False), ("test-owner", "20260002", False),
    ]
    assert session_runtime.refresh_started == [("20260001", UA_A), ("20260002", ua_b)]
    assert api.device_ua == PARENT_UA


@pytest.mark.parametrize("live_ua", [LEGACY_IOS_UA, LEGACY_DESKTOP_UA, LEGACY_CUSTOM_UA])
def test_existing_non_android_account_prefers_its_current_android_binding(session_runtime, live_ua):
    api = session_runtime.make_api({"20260001": {"password": "test-a", "ua": UA_A}})
    existing = SnapshotAccount("20260001", "test-a", api)
    existing.device_ua = live_ua
    api.accounts = {existing.username: existing}

    session_state.restore_session_to_api_instance(api, {
        "is_multi_account_mode": True,
        "multi_account_states": {"20260001": {"device_ua": UA_B}},
    })

    assert existing.device_ua == UA_A
    assert session_runtime.persisted == []
    assert session_runtime.refresh_started == [("20260001", UA_A)]


def test_repairing_live_legacy_ua_saves_only_once(session_runtime):
    api = session_runtime.make_api({"20260001": {"password": "test-a", "ua": LEGACY_CUSTOM_UA}})
    existing = SnapshotAccount("20260001", "test-a", api)
    existing.device_ua = LEGACY_DESKTOP_UA
    existing._repair_unsupported_device_ua = lambda _previous, replacement: api._persist_missing_school_account_ua(
        api.auth_username, existing.username, replacement
    )
    client = object.__new__(session_state.ApiClient)
    client.app = existing
    client._device_ua = ""
    client._device_ua_lock = threading.Lock()
    existing.api_client = client
    api.accounts = {existing.username: existing}

    session_state.restore_session_to_api_instance(api, {
        "is_multi_account_mode": True,
        "multi_account_states": {"20260001": {"device_ua": UA_A}},
    })

    assert existing.device_ua == UA_A
    assert session_runtime.persisted == [("test-owner", "20260001", UA_A)]


@pytest.mark.parametrize("stored_ua", [UA_A, LEGACY_IOS_UA, LEGACY_DESKTOP_UA])
@pytest.mark.parametrize("snapshot_ua", [LEGACY_IOS_UA.swapcase(), LEGACY_DESKTOP_UA, LEGACY_CUSTOM_UA])
def test_single_account_replaces_legacy_snapshot_from_own_binding(session_runtime, stored_ua, snapshot_ua):
    api = session_runtime.make_api({
        "20260001": {"password": "test-a", "ua": stored_ua},
        "20260002": {"password": "test-b", "ua": UA_B},
    })
    api.user_data = SimpleNamespace()
    session_state.restore_session_to_api_instance(api, {
        "is_multi_account_mode": False,
        "user_data": {"username": "20260001"},
        "device_ua": snapshot_ua,
    })

    assert session_runtime.lookups == [("test-owner", "20260001", True)]
    if stored_ua == UA_A:
        assert api.device_ua == UA_A
        assert session_runtime.generated == []
        assert session_runtime.persisted == []
    else:
        assert len(session_runtime.generated) == 1
        assert api.device_ua == session_runtime.generated[0]
        assert session_runtime.persisted == [("test-owner", "20260001", api.device_ua)]


def test_single_legacy_snapshot_waits_for_account_selection_when_username_is_unknown(session_runtime):
    api = session_runtime.make_api()
    session_state.restore_session_to_api_instance(api, {
        "is_multi_account_mode": False,
        "device_ua": LEGACY_IOS_UA,
    })

    assert api.device_ua == LEGACY_IOS_UA
    assert session_runtime.lookups == []
    assert session_runtime.persisted == []
