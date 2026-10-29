"""Acceptance-test server: deny Python socket access outside loopback."""

import ipaddress
from pathlib import Path
import socket
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))


def restrict_network(event, arguments):
    if event == "socket.connect":
        address = arguments[1]
        host = address[0] if isinstance(address, tuple) else address
    elif event == "socket.getaddrinfo":
        host = arguments[0]
    else:
        return
    if host in (None, "localhost", b"localhost"):
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise PermissionError("Offline acceptance check blocked external network access")


sys.addaudithook(restrict_network)
try:
    socket.getaddrinfo("example.com", 443)
except PermissionError:
    pass
else:
    raise RuntimeError("Network restriction did not take effect")

from campus_map.cli import main

raise SystemExit(main(["serve", *sys.argv[1:]]))
