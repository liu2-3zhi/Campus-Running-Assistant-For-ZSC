import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_DIR = ROOT / "run"


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker CLI is unavailable")
def test_compose_uses_internal_redis_without_publishing_its_port():
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "-f",
            "docker-compose.mysql.yml",
            "config",
            "--format",
            "json",
        ],
        cwd=COMPOSE_DIR,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    config = json.loads(result.stdout)
    services = config["services"]
    app = services["python-running-helper"]
    redis = services["python-running-redis"]

    assert app["environment"]["APP_CACHE_BACKEND"] == "redis"
    assert app["environment"]["REDIS_HOST"] == "python-running-redis"
    assert "cache-internal" in app["networks"]
    assert redis.get("ports") is None
    assert set(redis["networks"]) == {"cache-internal"}
    assert config["networks"]["cache-internal"]["internal"] is True
    assert "MYSQL_HOST" in app["environment"]
    assert "mysql" not in services


def test_redis_client_dependency_is_in_image_requirements():
    requirements = (ROOT / "ssl" / "requirements.txt").read_text(encoding="utf-8")
    assert "redis>=5,<7" in requirements
