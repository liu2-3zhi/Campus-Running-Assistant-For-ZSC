"""Read-only integrity checks for a published offline data release."""

import hashlib
import json
from pathlib import Path
import re


class DataError(RuntimeError):
    def __init__(self, message: str, code: str = "DATA_INVALID"):
        super().__init__(message)
        self.code = code


def validate_data(data_root: Path) -> dict:
    pointer = data_root / "current.json"
    if not pointer.is_file():
        raise DataError("No prepared data. Run prepare and build first.", "DATA_UNAVAILABLE")
    try:
        version = json.loads(pointer.read_text(encoding="utf-8"))["version"]
        if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", version):
            raise ValueError("Invalid release version")
        release = (data_root / "builds" / version).resolve()
        if not release.is_relative_to((data_root / "builds").resolve()):
            raise ValueError("Release path escapes data directory")
        manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("version") != version:
            raise ValueError("Release manifest version mismatch")
        checksums = manifest.get("checksums")
        if not isinstance(checksums, dict) or not checksums:
            raise ValueError("Release has no file checksums")
        for name, expected in checksums.items():
            file = (release / name).resolve()
            if not file.is_relative_to(release) or not file.is_file():
                raise ValueError(f"Missing or invalid release file: {name}")
            with file.open("rb") as source:
                actual = hashlib.file_digest(source, "sha256").hexdigest()
            if actual != expected:
                raise ValueError(f"Checksum mismatch: {name}")
        from campus_map.pipeline import validate_release

        validate_release(release)
        return {"status": "ok", "version": version, "checked_files": len(checksums)}
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise DataError(str(error)) from error
