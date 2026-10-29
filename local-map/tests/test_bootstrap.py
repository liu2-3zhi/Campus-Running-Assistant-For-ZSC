"""Exercise Windows environment repair with real uv-created launchers."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNTIMES = sorted((ROOT / ".runtime/python").glob("cpython-3.12.*-windows-x86_64-none/python.exe"))
pytestmark = pytest.mark.skipif(os.name != "nt" or not RUNTIMES or not shutil.which("uv"),
                                reason="Requires Windows, uv and the prepared Python 3.12 runtime")


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@pytest.fixture(params=[shell for shell in ("powershell", "pwsh") if shutil.which(shell)])
def shell(request):
    return request.param


def initialize(project, shell):
    command = (f"Set-StrictMode -Version Latest; . {ps_quote(ROOT / 'scripts/venv.ps1')}; "
               f"Initialize-ProjectVenv -ProjectDir {ps_quote(project)} -PythonExe {ps_quote(RUNTIMES[-1])}")
    result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", command],
                            capture_output=True, text=True, errors="replace", timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    executable = project / ".venv/Scripts/python.exe"
    probe = subprocess.run([str(executable), "-c", "import json,sys;print(json.dumps([sys.prefix,sys.version_info[:2]]))"],
                           capture_output=True, text=True, timeout=15)
    assert probe.returncode == 0, probe.stderr
    prefix, version = json.loads(probe.stdout)
    assert Path(prefix) == project / ".venv"
    assert version == [3, 12]


def test_repairs_broken_environment_preserving_all_files(tmp_path, shell):
    broken = tmp_path / ".venv"
    (broken / "Scripts").mkdir(parents=True)
    shutil.copy2(ROOT / ".venv/Scripts/python.exe", broken / "Scripts/python.exe")
    (broken / "pyvenv.cfg").write_text(f"home = {tmp_path / 'missing-runtime'}\n", encoding="utf-8")
    (broken / "keep.txt").write_text("preserve me", encoding="utf-8")
    initialize(tmp_path, shell)
    backups = list((tmp_path / ".runtime/venv-backups").iterdir())
    assert len(backups) == 1
    assert (backups[0] / "keep.txt").read_text() == "preserve me"
    initialize(tmp_path, shell)
    assert list((tmp_path / ".runtime/venv-backups").iterdir()) == backups


def test_repairs_copied_environment_even_when_old_runtime_still_exists(tmp_path, shell):
    original = tmp_path / "original"
    original.mkdir()
    initialize(original, shell)
    moved = tmp_path / "moved with spaces"
    shutil.copytree(original, moved)
    initialize(moved, shell)
    assert len(list((moved / ".runtime/venv-backups").iterdir())) == 1
    marker = json.loads((moved / ".venv/.campus-environment.json").read_text(encoding="utf-8-sig"))
    assert Path(marker["project_dir"]) == moved
