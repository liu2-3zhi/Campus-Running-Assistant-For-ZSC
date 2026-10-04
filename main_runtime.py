from __future__ import annotations

import importlib
from pathlib import Path
import sys


def _resolve_entry_module():
    active_module = sys.modules.get("__main__")
    active_file = getattr(active_module, "__file__", "") if active_module else ""
    if active_file and Path(active_file).name == "main.py":
        return active_module
    return None


_ENTRY_MODULE = _resolve_entry_module()


def _main():
    if _ENTRY_MODULE is not None:
        return _ENTRY_MODULE

    module = sys.modules.get("main")
    if module is None:
        module = importlib.import_module("main")
    return module
