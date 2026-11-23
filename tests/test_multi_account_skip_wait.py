"""Starting an account between tasks wakes its existing worker without duplicating it."""

import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import main
from api_runtime import Api


@pytest.fixture
def waiting_account():
    api = object.__new__(Api)
    api._init_state_variables()
    api._payment_required_for_overdue_gate = lambda: False
    api._resolve_waive_charge = lambda requested: False
    api.log_and_notify_frontend = lambda *args, **kwargs: None
    api._update_multi_global_buttons = lambda: None
    runs = []
    for index in range(3):
        run = main.RunData()
        run.errand_id = f"skip-wait-{index}"
        run.errand_schedule = "schedule"
        run.run_name = f"task-{index}"
        runs.append(run)
    account = SimpleNamespace(
        username="skip-wait-account", user_data=SimpleNamespace(
            username="skip-wait-account", student_id="skip-wait-account", id="student",
            name="test", gender="male",
        ),
        api_client=SimpleNamespace(), stop_event=threading.Event(),
        worker_thread=None, account_operation_lock=threading.Lock(),
        last_refresh_time=time.time(), all_run_data=runs,
        params={"ignore_task_time": True, "task_gap_min_s": 60, "task_gap_max_s": 60},
        status_text="", summary={}, tag="", log_and_notify_frontend=lambda *args, **kwargs: None,
    )
    api.accounts[account.username] = account
    executed = []
    first_wait = threading.Event()
    second_wait = threading.Event()

    def fetch(target):
        target.all_run_data = runs
        target.summary = {"total": 3, "executable": 3 - len(executed), "expired": 0, "not_started": 0}
        return True

    def execute(target, run, *args, **kwargs):
        executed.append(run.errand_id)
        run.status = 1
        return "success"

    def status(target, **fields):
        for key, value in fields.items():
            setattr(target, key, value)
        if "任务间等待" in fields.get("status_text", ""):
            (first_wait if len(executed) == 1 else second_wait).set()

    api._multi_fetch_and_summarize_tasks = fetch
    api._run_single_multi_account_task = execute
    api._update_account_status_js = status
    assert api._start_multi_account_worker(account, 0, True)
    worker = account.worker_thread
    try:
        assert first_wait.wait(timeout=3)
        yield api, account, worker, executed, second_wait
    finally:
        account.stop_event.set()
        api.multi_run_stop_flag.set()
        worker.join(timeout=3)
        assert not worker.is_alive()


def test_start_skips_only_current_task_gap_without_starting_another_worker(waiting_account):
    api, account, worker, executed, second_wait = waiting_account
    api.waive_charge_active = True
    api._payment_required_for_overdue_gate = Mock(side_effect=AssertionError("not a new execution"))

    result = api.multi_start_single_account(account.username)

    assert result["success"]
    assert result["wait_skipped"]
    assert account.worker_thread is worker
    assert second_wait.wait(timeout=3)
    assert executed == ["skip-wait-0", "skip-wait-1"]
    assert not account.stop_event.is_set()
    assert not api.multi_run_stop_flag.is_set()
    assert api.waive_charge_active is True


def test_start_does_not_wake_a_task_gap_after_stop_is_requested(waiting_account):
    api, account, worker, executed, second_wait = waiting_account
    with api._get_multi_execution_lock():
        api.multi_stop_all_accounts()
        result = api.multi_start_single_account(account.username)

    # Let the already-running worker finish reacting to Stop.
    worker.join(timeout=3)
    assert not result.get("wait_skipped")
    assert executed == ["skip-wait-0"]
    assert not second_wait.is_set()


def test_snapshot_and_status_push_expose_only_a_live_task_wait(waiting_account):
    api, account, worker, executed, second_wait = waiting_account
    api._web_session_id = "skip-wait-session"
    socket = Mock()
    assert api.multi_get_all_accounts_status()["accounts"][0]["can_skip_wait"] is True
    with patch.object(main, "socketio", socket, create=True):
        Api._update_account_status_js(api, account, status_text=account.status_text)
    assert socket.emit.call_args.args[1]["data"]["can_skip_wait"] is True

    api.multi_stop_all_accounts()
    assert api.multi_get_all_accounts_status()["accounts"][0]["can_skip_wait"] is False


def test_start_during_task_execution_still_rejects_duplicate_worker(waiting_account):
    api, account, worker, executed, second_wait = waiting_account
    task_started = threading.Event()
    release_task = threading.Event()
    original_execute = api._run_single_multi_account_task

    def execute(target, run, *args, **kwargs):
        task_started.set()
        release_task.wait(timeout=3)
        return original_execute(target, run, *args, **kwargs)

    api._run_single_multi_account_task = execute
    try:
        assert api.multi_start_single_account(account.username)["success"]
        assert task_started.wait(timeout=3)
        result = api.multi_start_single_account(account.username)
        assert result["success"] is False
        assert not result.get("wait_skipped")
        assert account.worker_thread is worker
    finally:
        release_task.set()
