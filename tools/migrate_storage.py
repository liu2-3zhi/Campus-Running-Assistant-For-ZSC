"""Run the offline storage migration CLI without starting the application."""
from pathlib import Path
import sys


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from storage_migration import main

    raise SystemExit(main())
