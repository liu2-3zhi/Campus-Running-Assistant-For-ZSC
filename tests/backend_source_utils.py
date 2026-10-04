from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_normalized_web_server_source(encoding: str = "utf-8") -> str:
    source = (PROJECT_ROOT / "web_server.py").read_text(encoding=encoding)
    return source.replace("_main().", "")


def read_backend_source() -> str:
    """Return entry-point and extracted backend source in original order."""
    return "\n\n".join(
        (
            (PROJECT_ROOT / "main.py").read_text(encoding="utf-8"),
            _read_normalized_web_server_source(),
        )
    )


class _BackendSource:
    def read_text(self, encoding="utf-8") -> str:
        return "\n\n".join(
            (
                (PROJECT_ROOT / "main.py").read_text(encoding=encoding),
                _read_normalized_web_server_source(encoding),
            )
        )


BACKEND_SOURCE = _BackendSource()
