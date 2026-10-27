"""Optional live deployment check: set ZX_NGINX_BINARY to a local nginx executable."""

import contextlib
import datetime
import functools
import ipaddress
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

import requests
from flask import Flask, g, request
from werkzeug.serving import make_server

from map_request_proxy import register_map_proxy_routes


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SESSION_ID = "11111111-1111-4111-8111-111111111111"
FAKE_KEY = "DEPLOYMENT_TEST_ONLY_MAP_KEY"


def _heredoc(source, name):
    match = re.search(r"<<'?" + name + r"'?\r?\n(.*?)\r?\n" + name + r"(?:\r?\n|$)", source, re.S)
    if not match:
        raise AssertionError(f"Missing entrypoint template {name}")
    return match.group(1) + "\n"


def _free_port(preferred=0):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", preferred))
        return listener.getsockname()[1]


@unittest.skipUnless(os.environ.get("ZX_NGINX_BINARY"), "Set ZX_NGINX_BINARY for isolated live Nginx verification")
class NginxLiveDeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = Path(os.environ["ZX_NGINX_BINARY"]).resolve(strict=True)
        cls.source = (PROJECT_ROOT / "docker/docker-entrypoint.sh").read_text(encoding="utf-8")
        cls.flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cls.version = subprocess.run(
            [str(cls.binary), "-v"], capture_output=True, text=True, timeout=10,
            creationflags=cls.flags, check=True,
        ).stderr.strip()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zx-nginx-live-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.received = []
        app = Flask(__name__)
        app.secret_key = "isolated-deployment-test-only-secret"

        def login_required(view):
            @functools.wraps(view)
            def wrapped(*args, **kwargs):
                g.user = "deployment-test"
                g.session_id = SESSION_ID
                return view(*args, **kwargs)
            return wrapped

        def transport(method, url, *, headers, body, timeout):
            self.received.append({"method": method, "url": url, "headers": headers, "body": body})
            return SimpleNamespace(
                status_code=200, headers={"Content-Type": "application/javascript"},
                content=b"window.deploymentProxyLoaded=true;",
            )

        config_values = {"frontend_proxy_enabled": True, "backend_page_origin": "https://authorized.example"}
        config = SimpleNamespace(get=lambda section, key, fallback=None:
                                 config_values.get(key, fallback) if section == "Map" else fallback)
        register_map_proxy_routes(
            app, login_required,
            lambda: config,
            lambda user, token, sid, require_view_all: user == "deployment-test"
                and token == "deployment-test-only-token" and sid == SESSION_ID,
            transport=transport,
            dns_resolver=lambda *_args, **_kwargs: [(None, None, None, None, ("8.8.8.8", 443))],
        )

        @app.get("/api/deployment-health")
        def health():
            return {"host": request.host, "proto": request.headers.get("X-Forwarded-Proto"),
                    "forwarded_for": request.headers.get("X-Forwarded-For")}

        self.backend = make_server("127.0.0.1", 0, app, threaded=True)
        self.backend_thread = threading.Thread(target=self.backend.serve_forever, daemon=True)
        self.backend_thread.start()
        self.addCleanup(self.backend.server_close)
        self.addCleanup(self.backend.shutdown)
        self.http_port = _free_port(int(os.environ.get("ZX_NGINX_HTTP_PORT", "0")))
        self.https_port = _free_port(int(os.environ.get("ZX_NGINX_HTTPS_PORT", "0")))
        self._certificate()

    def _certificate(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "isolated-deployment-test")])
        now = datetime.datetime.now(datetime.timezone.utc)
        certificate = (
            x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .sign(key, hashes.SHA256())
        )
        ssl_dir = self.root / "app/ssl"
        ssl_dir.mkdir(parents=True)
        (ssl_dir / "fullchain.pem").write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        (ssl_dir / "privkey.key").write_bytes(key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))

    def _prepare(self, mode):
        for name in ("nginx", "logs", "app", "temp"):
            (self.root / name).mkdir(exist_ok=True)
        mime_source = self.binary.parent / "conf/mime.types"
        if not mime_source.is_file():
            mime_source = Path(os.environ.get("ZX_NGINX_MIME_TYPES", "/etc/nginx/mime.types"))
        self.assertTrue(mime_source.is_file(), f"Expected Nginx mime.types: {mime_source}")
        (self.root / "nginx/mime.types").write_bytes(mime_source.read_bytes())
        replacements = {
            "/etc/nginx": (self.root / "nginx").as_posix(),
            "/var/log/nginx": (self.root / "logs").as_posix(),
            "/var/run/nginx.pid": (self.root / "nginx.pid").as_posix(),
            "/app": (self.root / "app").as_posix(),
            "127.0.0.1:5000": f"127.0.0.1:{self.backend.server_port}",
            "listen 80;": f"listen 127.0.0.1:{self.http_port};",
            "listen 443 ssl http2;": f"listen 127.0.0.1:{self.https_port} ssl http2;",
        }

        def adapt(text):
            pattern = "|".join(
                re.escape(value) + (r"(?=/|[;\s])" if value == "/app" else "")
                for value in replacements
            )
            text = re.sub(pattern, lambda match: replacements[match.group(0)], text)
            if os.name == "nt":
                text = text.replace("error_log /dev/null crit;", "error_log NUL crit;")
                text = text.replace("worker_processes  auto;", "worker_processes  1;")
            return text

        (self.root / "nginx/nginx_map.conf").write_text(
            adapt(_heredoc(self.source, "NGINX_MAP_EOF").replace("\\$", "$")), encoding="utf-8"
        )
        (self.root / "nginx/app_locations.conf").write_text(
            adapt(_heredoc(self.source, "LOCATIONS_EOF")), encoding="utf-8"
        )
        if mode == "http":
            config = _heredoc(self.source, "HTTP_ONLY_EOF")
        else:
            config = _heredoc(self.source, "HEAD_EOF")
            config += _heredoc(self.source, "EOF_80_REDIRECT" if mode == "redirect" else "EOF_80_NORMAL")
            config += _heredoc(self.source, "EOF_443")
        config_path = self.root / "nginx.conf"
        config_path.write_text(adapt(config), encoding="utf-8")
        return [str(self.binary), "-p", self.root.as_posix() + "/", "-c", str(config_path)]

    @contextlib.contextmanager
    def _running(self, mode):
        command = self._prepare(mode)
        checked = subprocess.run(command + ["-t"], capture_output=True, text=True, timeout=10, creationflags=self.flags)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        print(f"{self.version}; {mode}: nginx -t passed", flush=True)
        process = subprocess.Popen(
            command + ["-g", "daemon off;"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=self.flags,
        )
        try:
            deadline = time.monotonic() + 10
            while True:
                try:
                    with socket.create_connection(("127.0.0.1", self.http_port), timeout=0.2):
                        break
                except OSError:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        self.fail("Isolated Nginx failed to listen: " + (self.root / "logs/error.log").read_text(errors="replace"))
                    time.sleep(0.05)
            yield
        finally:
            subprocess.run(command + ["-s", "quit"], capture_output=True, timeout=10, creationflags=self.flags)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                subprocess.run(command + ["-s", "stop"], capture_output=True, timeout=10, creationflags=self.flags)
                process.wait(timeout=5)
            for port in (self.http_port, self.https_port):
                with socket.socket() as probe:
                    self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0, f"Leaked test listener {port}")

    def _verify_origin_and_proxy(self, origin):
        session = requests.Session()
        self.addCleanup(session.close)
        session.trust_env = False
        session.cookies.set("auth_token", "deployment-test-only-token")
        request_options = {"verify": str(self.root / "app/ssl/fullchain.pem"), "timeout": 5}
        health = session.get(origin + "/api/deployment-health?control=keep-log", **request_options)
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["host"], origin.split("://", 1)[1])
        self.assertEqual(health.json()["proto"], origin.split("://", 1)[0])
        self.assertTrue(health.json()["forwarded_for"])
        headers = {"Origin": origin, "X-Session-ID": SESSION_ID}
        bootstrap = session.post(origin + "/api/map-proxy/context", headers=headers, json={}, **request_options)
        self.assertEqual(bootstrap.status_code, 200, bootstrap.text)
        wrong_port = origin.rsplit(":", 1)[0] + ":1"
        mismatch = session.post(origin + "/api/map-proxy/context", headers={**headers, "Origin": wrong_port}, json={}, **request_options)
        self.assertEqual(mismatch.status_code, 403)
        proxy = session.get(origin + f"/map-proxy/amap/https/webapi.amap.com/maps?key={FAKE_KEY}&callback=testCallback", **request_options)
        self.assertEqual(proxy.status_code, 200, proxy.text)
        self.assertEqual(proxy.text, "window.deploymentProxyLoaded=true;")
        self.assertTrue(self.received[-1]["url"].endswith(f"?key={FAKE_KEY}&callback=testCallback"))
        self.assertEqual(self.received[-1]["headers"]["Origin"], "https://authorized.example")
        print(f"{origin}: Host/proto preserved, matching Origin=200, wrong port=403, proxy=200", flush=True)

    def _assert_logs(self):
        self.assertTrue((self.root / "logs/access.log").exists())
        self.assertTrue((self.root / "logs/access_json.log").exists())
        for path in (self.root / "logs").glob("*.log"):
            content = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn(FAKE_KEY, content, f"Map query leaked to {path.name}")
            self.assertNotIn(" /map-proxy/", content, f"Map request logged to {path.name}")
            if path.name in {"access.log", "access_json.log"}:
                self.assertIn("control=keep-log", content, f"Ordinary API logging disabled in {path.name}")

    def test_http_templates_proxy_origin_and_exclude_map_logs(self):
        with self._running("http"):
            self._verify_origin_and_proxy(f"http://127.0.0.1:{self.http_port}")
            self.backend.shutdown()
            self.backend.server_close()
            failure = requests.get(
                f"http://127.0.0.1:{self.http_port}/map-proxy/amap/https/webapi.amap.com/maps?key={FAKE_KEY}&failure=upstream-offline",
                timeout=5,
            )
            self.assertEqual(failure.status_code, 502)
        self._assert_logs()

    def test_https_and_http_templates_preserve_nondefault_ports(self):
        with self._running("https"):
            self._verify_origin_and_proxy(f"http://127.0.0.1:{self.http_port}")
            self._verify_origin_and_proxy(f"https://127.0.0.1:{self.https_port}")
        self._assert_logs()

    def test_https_only_redirect_also_excludes_map_queries(self):
        with self._running("redirect"):
            self._verify_origin_and_proxy(f"https://127.0.0.1:{self.https_port}")
            response = requests.get(
                f"http://127.0.0.1:{self.http_port}/map-proxy/amap/https/webapi.amap.com/maps?key={FAKE_KEY}",
                allow_redirects=False, timeout=5,
            )
            self.assertEqual(response.status_code, 301)
        self._assert_logs()


if __name__ == "__main__":
    unittest.main()
