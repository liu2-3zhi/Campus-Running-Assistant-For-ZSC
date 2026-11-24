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
        command = [docker, 'compose']
        for filename in files:
            command += ['-f', filename]
        result = subprocess.run(command + ['config', '--format', 'json'], cwd=root / 'run',
            env=environment, capture_output=True, encoding='utf-8', timeout=30)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    base = render(['docker-compose.yml'])
    merged = render(['docker-compose.yml', 'docker-compose.mysql.yml'])
    assert set(merged['services']) == {'python-running-helper', 'python-running-redis'}
    assert not merged['services']['python-running-redis'].get('ports')
    assert not merged.get('volumes')
    service = merged['services']['python-running-helper']
    assert service['environment']['MYSQL_HOST'] == 'database.example.com'
    assert service['environment']['MYSQL_PORT'] == '3306'
    assert service['environment']['MYSQL_PASSWORD'] == 'replace-with-your-own-password'
    assert base['services']['python-running-helper']['environment']['APP_STORAGE_BACKEND'] == 'sqlite'
    assert base['services']['python-running-helper']['environment']['SQLITE_DATABASE_PATH'] == '/app/data/application.sqlite3'
    assert not (root / 'run/mysql.env.example').exists()
    for filename in ('docker-compose.yml', 'docker-compose.mysql.yml'):
        source = (root / 'run' / filename).read_text(encoding='utf-8')
        assert 'env_file' not in source
        assert '--env-file' not in source
        assert '${' not in source
    assert 'MYSQL_ROOT_PASSWORD' not in service['environment']
    assert not service.get('depends_on')
    assert service['volumes'] == base['services']['python-running-helper']['volumes']
    assert {volume['target'] for volume in service['volumes']} == {
        '/app/ssl', '/app/cache', '/app/logs', '/app/data', '/app/uploads',
        '/app/system_accounts/images', '/app/random_background_image',
    }
    assert service['logging'] == base['services']['python-running-helper']['logging']
    assert service['networks'] == base['services']['python-running-helper']['networks']


def test_docker_build_does_not_create_frozen_business_file_placeholders():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'Dockerfile').read_text(encoding='utf-8')
    for filename in ('config.ini', 'messages.json', 'permissions.json',
                     'reminders.json', 'payment_methods.json'):
        assert f'touch /app/{filename}' not in source
    ignored = (root / '.dockerignore').read_text(encoding='utf-8').splitlines()
    assert '/trusted_ips.txt' in ignored
    assert '/remove' in ignored


def test_entrypoint_has_valid_bash_syntax():
    bash = shutil.which('bash')
    if not bash:
        pytest.skip('Bash is needed to verify the entrypoint syntax')
    root = Path(__file__).resolve().parents[1]
    # Windows checkouts may use CRLF; the Dockerfile normalizes shell files.
    source = (root / 'docker/docker-entrypoint.sh').read_bytes().replace(b'\r\n', b'\n')
    result = subprocess.run([bash, '-n'], input=source, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
