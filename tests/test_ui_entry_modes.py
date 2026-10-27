import re
import unittest
from pathlib import Path
from tests.backend_source_utils import read_backend_source


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestUiEntryModes(unittest.TestCase):
    def test_backend_registers_fixed_new_and_old_entries(self):
        source = read_backend_source()
        for route in (
            '@app.route("/frontend")',
            '@app.route("/frontend/")',
            '@app.route("/frontend/<path:path>")',
            '@app.route("/old")',
            '@app.route("/old/")',
            '@app.route("/old/<path:path>")',
        ):
            self.assertIn(route, source)
        self.assertIn('runtime_config.get("Config", "default_ui"', source)
        self.assertIn('config.set("Config", "default_ui", default_ui)', source)
        self.assertIn('return redirect("/frontend/")', source)

    def test_vue_build_and_router_use_frontend_base(self):
        vite_config = (PROJECT_ROOT / "frontend/vite.config.js").read_text(
            encoding="utf-8"
        )
        router = (PROJECT_ROOT / "frontend/src/router/index.js").read_text(
            encoding="utf-8"
        )
        main_js = (PROJECT_ROOT / "frontend/src/main.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("base: '/frontend/'", vite_config)
        self.assertIn("createWebHistory(import.meta.env.BASE_URL)", router)
        self.assertIn("window.__RUNNING_UI_BASE__ = import.meta.env.BASE_URL", main_js)

    def test_legacy_entry_keeps_old_prefix_for_session_navigation(self):
        source = (PROJECT_ROOT / "scripts/main.js").read_text(encoding="utf-8")
        self.assertIn("function buildLegacyUiPath(path = \"/\")", source)
        self.assertIn(
            "window.location.href = buildLegacyUiPath(`/uuid=${originSession}`)",
            source,
        )
        self.assertIn(
            "window.location.replace(buildLegacyUiPath(`/uuid=${sessionUUID}`))",
            source,
        )
        self.assertNotIn('window.location.href = "/";', source)
        self.assertNotIn('window.location.replace("/")', source)

    def test_nginx_proxies_prefixed_ui_entries(self):
        source = (PROJECT_ROOT / "docker/docker-entrypoint.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("location ^~ /frontend/", source)
        self.assertIn("location ^~ /old/", source)

    def test_nginx_preserves_host_port_for_flask_origin_checks(self):
        source = (PROJECT_ROOT / "docker/docker-entrypoint.sh").read_text(
            encoding="utf-8"
        )
        flask_proxies = re.findall(
            r"location [^{]+\{(?P<body>[^{}]*"
            r"proxy_pass http://127\.0\.0\.1:5000;[^{}]*)\}",
            source,
        )
        self.assertEqual(len(flask_proxies), 8)
        for body in flask_proxies:
            self.assertRegex(body, r"(?m)^\s*proxy_set_header Host \$http_host;")
            self.assertNotRegex(body, r"proxy_set_header Host \$host;")
            self.assertRegex(body, r"proxy_set_header X-Forwarded-Proto \$scheme;")

    def test_nginx_map_proxy_omits_access_logs_and_keeps_api_forwarding(self):
        source = (PROJECT_ROOT / "docker/docker-entrypoint.sh").read_text(
            encoding="utf-8"
        )
        shared_locations = source.split("<<'LOCATIONS_EOF'", 1)[1].split(
            "\nLOCATIONS_EOF", 1
        )[0]
        proxy_match = re.search(
            r"location \^~ /map-proxy/ \{(?P<body>[^{}]*)\}", shared_locations
        )
        self.assertIsNotNone(proxy_match, "Map requests must bypass inherited access logs")
        proxy_body = proxy_match.group("body")
        self.assertRegex(proxy_body, r"(?m)^\s*access_log\s+off;")
        self.assertRegex(proxy_body, r"(?m)^\s*error_log\s+/dev/null\s+crit;")

        api_match = re.search(
            r"location ~ \^/\(api\|auth\|logs\|cdn-cache\|avatar\|system-announcement\)/ "
            r"\{(?P<body>[^{}]*)\}",
            shared_locations,
        )
        self.assertIsNotNone(api_match)
        forwarding_directives = lambda body: [
            line.strip()
            for line in body.splitlines()
            if line.strip().startswith("proxy_")
        ]
        self.assertEqual(
            forwarding_directives(proxy_body),
            forwarding_directives(api_match.group("body")),
        )
        self.assertIn("proxy_pass http://127.0.0.1:5000;", proxy_body)
        self.assertNotIn("try_files", proxy_body)
        self.assertEqual(source.count("include /etc/nginx/app_locations.conf;"), 3)

    def test_nginx_redirect_and_http_logs_also_exclude_map_proxy_queries(self):
        source = (PROJECT_ROOT / "docker/docker-entrypoint.sh").read_text(
            encoding="utf-8"
        )
        map_config = source.split("<<NGINX_MAP_EOF", 1)[1].split(
            "\nNGINX_MAP_EOF", 1
        )[0]
        self.assertRegex(
            map_config,
            r"map \\\$uri \\\$map_proxy_access_log \{\s*"
            r"default 1;\s*~\^/map-proxy/ 0;\s*\}",
        )
        access_logs = re.findall(
            r"(?m)^\s*access_log\s+/var/log/nginx/[^;]+;", source
        )
        self.assertEqual(len(access_logs), 4)
        for directive in access_logs:
            self.assertRegex(directive, r"if=\$map_proxy_access_log;$")
        self.assertEqual(source.count("include       /etc/nginx/nginx_map.conf;"), 2)


if __name__ == "__main__":
    unittest.main()
