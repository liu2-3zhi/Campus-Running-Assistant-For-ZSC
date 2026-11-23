"""A stop request must cancel both running and not-yet-started account workers."""

import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import api_runtime
import main
from api_runtime import Api


def make_api(*usernames):
    api = object.__new__(Api)
    api.accounts = {}
    api.multi_execution_lock = threading.RLock()
    api.multi_active_executions = set()
    api.multi_run_stop_flag = threading.Event()
    api.multi_run_stop_flag.set()
    api._payment_required_for_overdue_gate = lambda: False
    api._resolve_waive_charge = lambda _requested: False
    api._overdue_bypass_allowed = lambda _requested: False
    api.log_and_notify_frontend = lambda *_args, **_kwargs: None
    api._update_multi_global_buttons = lambda: None
    api._update_account_status_js = lambda acc, **fields: [
        setattr(acc, key, value) for key, value in fields.items()
    ]
    for username in usernames:
        api.accounts[username] = SimpleNamespace(
            username=username,
            user_data=SimpleNamespace(username=username, student_id=username),
            account_operation_lock=threading.Lock(),
            stop_event=threading.Event(),
            worker_thread=None,
            status_text="待命",
            log_and_notify_frontend=lambda *_args, **_kwargs: None,
        )
    api._multi_account_worker = lambda acc, *_args: acc.stop_event.wait(timeout=5)
    return api


def test_stop_all_signals_accounts_even_when_global_flag_is_already_set():
    api = make_api("student-a")
    acc = api.accounts["student-a"]
    api.multi_active_executions.add(acc.username)

    result = api.multi_stop_all_accounts()

    assert result["success"]
    assert acc.stop_event.is_set()
    assert acc.status_text == "正在停止..."


def test_batch_stop_does_not_start_remaining_accounts_or_clear_cancellation():
    api = make_api("student-a", "student-b")
    original_start = api._start_multi_account_worker
    workers = []

    def start_then_stop(acc, delay, incomplete, **kwargs):
        started = original_start(acc, delay, incomplete, **kwargs)
        if started:
            workers.append(acc.worker_thread)
        if acc.username == "student-a":
            api.multi_stop_all_accounts()
        return started

    api._start_multi_account_worker = start_then_stop
    try:
        with patch.object(api_runtime.time, "sleep", return_value=None):
            started = api._start_multi_account_threads(
                list(api.accounts.values()), [0, 0], False, True
            )
        assert started == 1
        assert api.multi_run_stop_flag.is_set()
        assert api.accounts["student-b"].stop_event.is_set()
        assert api.accounts["student-b"].worker_thread is None
    finally:
        for acc in api.accounts.values():
            acc.stop_event.set()
        for worker in workers:
            if worker is not None:
                worker.join(timeout=5)


def test_stop_during_single_start_preparation_prevents_worker_start():
    api = make_api("student-a")
    workers = []

    def check_payment():
        api.multi_stop_all_accounts()
        return False

    api._payment_required_for_overdue_gate = check_payment
    try:
        result = api.multi_start_single_account("student-a")
        worker = api.accounts["student-a"].worker_thread
        if worker is not None:
            workers.append(worker)
        assert not result["success"]
        assert api.accounts["student-a"].stop_event.is_set()
        assert worker is None
    finally:
        api.accounts["student-a"].stop_event.set()
        for worker in workers:
            worker.join(timeout=5)


def test_stop_during_batch_start_preparation_prevents_all_workers():
    api = make_api("student-a", "student-b")

    def check_payment():
        api.multi_stop_all_accounts()
        return False

    api._payment_required_for_overdue_gate = check_payment
    try:
        result = api.multi_start_all_accounts(0, 0, False, True)
        assert not result["success"]
        assert all(acc.stop_event.is_set() for acc in api.accounts.values())
        assert all(acc.worker_thread is None for acc in api.accounts.values())
    finally:
        workers = [acc.worker_thread for acc in api.accounts.values()]
        for acc in api.accounts.values():
            acc.stop_event.set()
        for worker in workers:
            if worker is not None:
                worker.join(timeout=5)


def test_explicit_start_after_stop_can_start_a_new_worker():
    api = make_api("student-a")
    acc = api.accounts["student-a"]
    api.multi_stop_all_accounts()
    try:
        result = api.multi_start_single_account(acc.username)
        worker = acc.worker_thread
        assert result["success"]
        assert worker is not None
        assert not acc.stop_event.is_set()
        assert not api.multi_run_stop_flag.is_set()
    finally:
        acc.stop_event.set()
        worker = acc.worker_thread
        if worker is not None:
            worker.join(timeout=5)


def test_worker_finish_wins_over_an_inflight_stopping_status_update():
    api = make_api("student-a")
    acc = api.accounts["student-a"]
    api.multi_run_stop_flag.clear()
    api.multi_active_executions.add(acc.username)
    worker = SimpleNamespace(is_alive=lambda: True)
    acc.worker_thread = worker
    update_entered = threading.Event()
    release_update = threading.Event()
    finish_done = threading.Event()

    def update_status(account, *, status_text):
        if status_text == "正在停止...":
            update_entered.set()
            release_update.wait(timeout=2)
        account.status_text = status_text

    api._update_account_status_js = update_status
    stop_thread = threading.Thread(target=api.multi_stop_all_accounts, daemon=True)

    def finish_worker():
        api._finish_multi_account_worker(acc, worker)
        finish_done.set()

    finish_thread = threading.Thread(target=finish_worker, daemon=True)
    try:
        stop_thread.start()
        assert update_entered.wait(timeout=2)
        finish_thread.start()
        finish_done.wait(timeout=0.1)
    finally:
        release_update.set()
        stop_thread.join(timeout=2)
        if finish_thread.ident is not None:
            finish_thread.join(timeout=2)

    assert not stop_thread.is_alive()
    assert not finish_thread.is_alive()
    assert acc.status_text == "已停止"


def test_real_worker_cleanup_cannot_leave_a_late_stopping_status():
    api = make_api("student-a")
    acc = api.accounts["student-a"]
    acc.api_client = SimpleNamespace()
    acc.current_position = None
    api.multi_run_stop_flag.clear()
    api.multi_active_executions.add(acc.username)
    stopping_update_entered = threading.Event()
    inner_cleanup_done = threading.Event()

    def update_status(account, *, status_text):
        if status_text == "正在停止...":
            stopping_update_entered.set()
            assert inner_cleanup_done.wait(timeout=2)
        account.status_text = status_text

    api._update_account_status_js = update_status

    def run_real_worker():
        assert stopping_update_entered.wait(timeout=2)
        try:
            Api._multi_account_worker(api, acc, 0, True)
        finally:
            inner_cleanup_done.set()
            api._finish_multi_account_worker(acc, threading.current_thread())

    worker = threading.Thread(target=run_real_worker, daemon=True)
    acc.worker_thread = worker
    worker.start()
    try:
        result = api.multi_stop_all_accounts()
    finally:
        worker.join(timeout=3)

    assert result["success"]
    assert not worker.is_alive()
    assert acc.worker_thread is None
    assert not api.multi_active_executions
    assert acc.status_text == "已停止"


@pytest.mark.parametrize(
    "accounts, expected",
    [
        ([({}, True)], (True, False, True)),
        ([({"total": 1, "executable": 0}, True)], (True, False, True)),
        ([({"total": 1, "executable": 1}, False), ({}, True)], (False, False, True)),
        ([({"total": 1, "executable": 1}, False)], (False, True, False)),
    ],
    ids=("logging-in", "worker-finalizing", "mixed-idle-and-running", "only-idle"),
)
def test_global_buttons_track_workers_even_without_executable_summary(accounts, expected):
    api = make_api(*(f"student-{index}" for index in range(len(accounts))))
    api._web_session_id = "test-session"
    api.multi_run_only_incomplete = True
    for acc, (summary, running) in zip(api.accounts.values(), accounts):
        acc.summary = summary
        if running:
            api.multi_active_executions.add(acc.username)
    socket = Mock()

    with patch.object(api_runtime, "_main", return_value=SimpleNamespace(socketio=socket)):
        Api._update_multi_global_buttons(api)

    buttons = socket.emit.call_args.args[1]
    assert tuple(buttons[key] for key in ("start_disabled", "stop_disabled", "exit_disabled")) == expected
