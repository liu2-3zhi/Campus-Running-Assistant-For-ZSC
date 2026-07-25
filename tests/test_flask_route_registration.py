import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_ROOT / "main.py"


def _parse_flask_routes(source: str):
    lines = source.splitlines()
    routes = []
    pending = []
    route_re = re.compile(r'^\s*@app\.route\("([^"]+)"(?:,\s*methods=\[([^\]]+)\])?')
    def_re = re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")

    for line_number, line in enumerate(lines, start=1):
        route_match = route_re.match(line)
        if route_match:
            methods_text = route_match.group(2)
            if methods_text:
                methods = tuple(
                    sorted(
                        item.strip().strip('"').strip("'")
                        for item in methods_text.split(",")
                        if item.strip()
                    )
                )
            else:
                methods = ("GET",)
            pending.append(
                {
                    "line": line_number,
                    "rule": route_match.group(1),
                    "methods": methods,
                }
            )
            continue

        def_match = def_re.match(line)
        if def_match and pending:
            endpoint = def_match.group(1)
            for route in pending:
                routes.append({**route, "endpoint": endpoint, "def_line": line_number})
            pending = []
        elif line.strip() and not line.lstrip().startswith("@") and pending:
            pending = []

    return routes


class TestFlaskRouteRegistration(unittest.TestCase):
    def test_startup_routes_do_not_register_duplicate_endpoints_or_rules(self):
        routes = _parse_flask_routes(MAIN_PATH.read_text(encoding="utf-8"))

        endpoint_groups = {}
        rule_groups = {}
        for route in routes:
            endpoint_groups.setdefault(route["endpoint"], set()).add(route["def_line"])
            for method in route["methods"]:
                rule_groups.setdefault((route["rule"], method), []).append(route)

        duplicate_endpoints = {
            endpoint: sorted(lines)
            for endpoint, lines in endpoint_groups.items()
            if endpoint and len(lines) > 1
        }
        duplicate_rules = {
            f"{method} {rule}": [item["line"] for item in items]
            for (rule, method), items in rule_groups.items()
            if len(items) > 1
        }

        self.assertEqual({}, duplicate_endpoints)
        self.assertEqual({}, duplicate_rules)


if __name__ == "__main__":
    unittest.main()
