"""Exercise the user entry point rather than its argparse implementation."""

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_no_arguments_starts_the_local_web(monkeypatch):
    from campus_map import cli, server

    calls = []
    def run(app, **options):
        calls.append((app, options))
        return 0

    monkeypatch.setattr(server, "serve", run)
    assert cli.main([]) == 0
    assert calls[0][1] == {"host": "127.0.0.1", "port": None}


def test_shutdown_is_bounded_when_a_windows_tcp_transport_never_closes(monkeypatch, tmp_path):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import uvicorn
    from campus_map import cli

    class StuckTransport:
        closed = False
        cancelled = False

        def close(self):
            self.closed = True

        async def wait_closed(self):
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled = True

    def run_with_stuck_transport(server, sockets):
        assert len(sockets) == 1 and sockets[0].getsockname()[1] > 0
        assert server.config.timeout_graceful_shutdown == 10
        # Keep this regression test fast while preserving the production setting check.
        server.config.timeout_graceful_shutdown = 0.01
        transport = StuckTransport()
        server.servers = [transport]
        server.lifespan = SimpleNamespace(shutdown=AsyncMock())

        async def shutdown():
            await asyncio.wait_for(server.shutdown(), timeout=5)
            assert transport.closed and transport.cancelled
            server.lifespan.shutdown.assert_awaited_once()

        asyncio.run(shutdown())
        server.started = True

    monkeypatch.setattr(uvicorn.Server, "run", run_with_stuck_transport)
    assert cli.main(["serve", "--port", "0", "--data-dir", str(tmp_path)]) == 0


def test_shutdown_is_bounded_when_a_http_connection_never_closes(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import uvicorn
    from campus_map import cli

    class StuckConnection:
        def shutdown(self):
            pass

    def run_with_stuck_connection(server, sockets):
        assert len(sockets) == 1 and sockets[0].getsockname()[1] > 0
        server.config.timeout_graceful_shutdown = 0.01
        server.servers = []
        server.server_state.connections.add(StuckConnection())
        server.lifespan = SimpleNamespace(shutdown=AsyncMock())

        async def shutdown():
            await asyncio.wait_for(server.shutdown(), timeout=5)
            server.lifespan.shutdown.assert_awaited_once()

        asyncio.run(shutdown())
        server.started = True

    monkeypatch.setattr(uvicorn.Server, "run", run_with_stuck_connection)
    assert cli.main(["serve", "--port", "0"]) == 0


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def test_help_lists_all_offline_workflow_commands():
    result = run_cli("--help")
    assert result.returncode == 0, result.stderr
    for command in ("prepare", "build", "validate", "serve"):
        assert command in result.stdout


def test_validate_missing_data_fails_without_creating_a_dataset(tmp_path):
    data_root = tmp_path / "absent"
    result = run_cli("validate", "--data-dir", str(data_root))
    assert result.returncode == 1
    error = json.loads(result.stderr)
    assert error["code"] == "DATA_UNAVAILABLE"
    assert not data_root.exists()


def test_validate_rejects_pointer_outside_release_directory(tmp_path):
    (tmp_path / "current.json").write_text('{"version":"../outside"}', encoding="utf-8")
    result = run_cli("validate", "--data-dir", str(tmp_path))
    assert result.returncode == 1
    assert json.loads(result.stderr)["code"] == "DATA_INVALID"


def test_validate_detects_changed_data(tmp_path):
    release = tmp_path / "builds" / "test-release"
    release.mkdir(parents=True)
    (tmp_path / "current.json").write_text('{"version":"test-release"}', encoding="utf-8")
    (release / "changed.txt").write_text("changed", encoding="utf-8")
    (release / "manifest.json").write_text(json.dumps({
        "version": "test-release", "checksums": {"changed.txt": "0" * 64},
    }), encoding="utf-8")
    result = run_cli("validate", "--data-dir", str(tmp_path))
    assert result.returncode == 1
    assert "changed.txt" in json.loads(result.stderr)["message"]


def test_validate_rejects_hashes_without_a_routing_graph(tmp_path):
    from campus_map.pipeline import COORDINATE_METADATA

    release = tmp_path / "builds" / "incomplete"
    release.mkdir(parents=True)
    (tmp_path / "current.json").write_text('{"version":"incomplete"}', encoding="utf-8")
    (release / "empty.txt").write_bytes(b"")
    (release / "manifest.json").write_text(json.dumps({
        "version": "incomplete", "bounds": [113.3798, 22.5255, 113.3901, 22.5355],
        **COORDINATE_METADATA,
        "minzoom": 14, "maxzoom": 20,
        "checksums": {"empty.txt": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
    }), encoding="utf-8")
    result = run_cli("validate", "--data-dir", str(tmp_path))
    assert result.returncode == 1
    assert "routing graph" in json.loads(result.stderr)["message"]
