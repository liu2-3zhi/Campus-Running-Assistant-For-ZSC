"""Reserve a local listener before handing it to Uvicorn."""

import errno
import logging
import os
import socket

from .validation import DataError


DEFAULT_PORT = 8765
GRACEFUL_SHUTDOWN_TIMEOUT = 10
PORT_ERRORS = {errno.EADDRINUSE, errno.EACCES, 10048, 10013}


def bind_listener(host: str, port: int | None) -> socket.socket:
    addresses = socket.getaddrinfo(host, 0, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP,
                                   flags=socket.AI_PASSIVE)
    preferred = DEFAULT_PORT if port is None else port
    candidates = (preferred, 0) if port is None else (preferred,)
    for candidate in candidates:
        errors = []
        retry_addresses = []
        for endpoint in addresses:
            family, kind, protocol, _, address = endpoint
            listener = None
            try:
                listener = socket.socket(family, kind, protocol)
                if os.name == "nt":
                    listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                else:
                    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if family == socket.AF_INET6:
                    listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                listener.bind((address[0], candidate, *address[2:]))
                listener.listen(128)
                listener.setblocking(False)
                return listener
            except OSError as error:
                if listener is not None:
                    listener.close()
                if error.errno in PORT_ERRORS:
                    retry_addresses.append(endpoint)
                else:
                    errors.append(error)
        if not retry_addresses:
            raise errors[0]
        addresses = retry_addresses
    raise DataError(
        f"Port {preferred} is unavailable on {host}. Choose another --port, or omit --port for automatic selection.",
        "PORT_IN_USE",
    )


def serve(app, *, host: str, port: int | None) -> int:
    import uvicorn

    with bind_listener(host, port) as listener:
        address, actual_port = listener.getsockname()[:2]
        config = uvicorn.Config(app, host=address, port=actual_port,
                                timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT)
        logger = logging.getLogger("uvicorn.error")
        if port is None and actual_port != DEFAULT_PORT:
            logger.warning("Port %s is unavailable; selected port %s.", DEFAULT_PORT, actual_port)
        display_address = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(address, address)
        url_host = f"[{display_address}]" if listener.family == socket.AF_INET6 else display_address
        base = f"http://{url_host}:{actual_port}"
        logger.info("Map: %s/ | API docs: %s/docs (Press CTRL+C to quit)", base, base)
        server = uvicorn.Server(config)
        server.run(sockets=[listener])
        return 0 if server.started else 1
