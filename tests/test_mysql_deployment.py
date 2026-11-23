import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_mysql_overlay_only_connects_application_to_external_database():
    docker = shutil.which('docker')
    if not docker:
        pytest.skip('Docker Compose CLI is needed to render the deployment configuration')
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, MYSQL_HOST='database.example.invalid', MYSQL_PORT='3307',
        MYSQL_USER='test-app', MYSQL_PASSWORD='test-only-placeholder', MYSQL_DATABASE='test-db',
        MYSQL_ROOT_PASSWORD='test-only-unused-placeholder')
    def render(files):
        command = [docker, 'compose', '--env-file', 'mysql.env.example']
        for filename in files:
            command += ['-f', filename]
        result = subprocess.run(command + ['config', '--format', 'json'], cwd=root / 'run',
            env=environment, capture_output=True, encoding='utf-8', timeout=30)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    base = render(['docker-compose.yml'])
    merged = render(['docker-compose.yml', 'docker-compose.mysql.yml'])
    assert set(merged['services']) == {'python-running-helper'}
    assert not merged.get('volumes')
    service = merged['services']['python-running-helper']
    assert service['environment']['MYSQL_HOST'] == 'database.example.invalid'
    assert service['environment']['MYSQL_PORT'] == '3307'
    assert 'MYSQL_ROOT_PASSWORD' not in service['environment']
    assert not service.get('depends_on')
    assert service['volumes'] == base['services']['python-running-helper']['volumes']
    assert service['logging'] == base['services']['python-running-helper']['logging']
    assert service['networks'] == base['services']['python-running-helper']['networks']
