"""Real socket checks for automatic and explicitly requested listener ports."""

import json
import errno
import socket

import pytest

from campus_map import cli


def test_automatic_port_avoids_a_busy_preferred_port(monkeypatch):
    from campus_map import server

    with server.bind_listener("127.0.0.1", 0) as occupied:
        preferred = occupied.getsockname()[1]
        monkeypatch.setattr(server, "DEFAULT_PORT", preferred)
        with server.bind_listener("127.0.0.1", None) as selected:
            assert selected.getsockname()[1] > 0
            assert selected.getsockname()[1] != preferred
            # The returned socket already owns its listener until Uvicorn takes it.
            with socket.socket() as competitor, pytest.raises(OSError):
                competitor.bind(selected.getsockname())


def test_automatic_port_keeps_the_preferred_port_when_available(monkeypatch):
    from campus_map import server

    with server.bind_listener("127.0.0.1", 0) as reservation:
        preferred = reservation.getsockname()[1]
    monkeypatch.setattr(server, "DEFAULT_PORT", preferred)
    with server.bind_listener("127.0.0.1", None) as selected:
        assert selected.getsockname()[1] == preferred


def test_explicit_busy_port_fails_clearly_without_switching(capsys):
    from campus_map import server

    with server.bind_listener("127.0.0.1", 0) as occupied:
        port = occupied.getsockname()[1]
        assert cli.main(["serve", f"--port={port}"]) == 1
        error = json.loads(capsys.readouterr().err)
        assert error["code"] == "PORT_IN_USE"
        assert str(port) in error["message"]


@pytest.mark.parametrize("port", ["-1", "65536"])
def test_invalid_ports_are_rejected_before_startup(port):
    with pytest.raises(SystemExit) as error:
        cli.main(["serve", "--port", port])
    assert error.value.code == 2


def test_invalid_host_does_not_trigger_port_fallback():
    from campus_map import server

    with pytest.raises(OSError) as error:
        server.bind_listener("192.0.2.1", None)
    assert error.value.errno in (errno.EADDRNOTAVAIL, 10049)


def test_startup_failure_closes_the_reserved_socket(monkeypatch):
    import uvicorn
    from campus_map import server

    listeners = []

    def fail_startup(self, sockets):
        listeners.extend(sockets)
        raise RuntimeError("startup failed")

    monkeypatch.setattr(uvicorn.Server, "run", fail_startup)
    with pytest.raises(RuntimeError, match="startup failed"):
        server.serve(object(), host="127.0.0.1", port=0)
    assert len(listeners) == 1 and listeners[0].fileno() == -1


def test_server_uses_a_bounded_graceful_shutdown_timeout(monkeypatch):
    import uvicorn
    from campus_map import server

    def started(self, sockets):
        assert self.config.timeout_graceful_shutdown == server.GRACEFUL_SHUTDOWN_TIMEOUT == 10
        self.started = True

    monkeypatch.setattr(uvicorn.Server, "run", started)
    assert server.serve(object(), host="127.0.0.1", port=0) == 0


@pytest.mark.parametrize("host, url_host", [("0.0.0.0", "127.0.0.1"), ("::", "[::1]")])
def test_wildcard_listener_reports_a_loopback_url(monkeypatch, capsys, host, url_host):
    import uvicorn
    from campus_map import server

    if host == "::":
        try:
            with server.bind_listener("::1", 0):
                pass
        except OSError:
            pytest.skip("IPv6 loopback is unavailable")

    def started(self, sockets):
        assert sockets[0].getsockname()[0] == host
        self.started = True

    monkeypatch.setattr(uvicorn.Server, "run", started)
    assert server.serve(object(), host=host, port=0) == 0
    assert f"Map: http://{url_host}:" in capsys.readouterr().err
