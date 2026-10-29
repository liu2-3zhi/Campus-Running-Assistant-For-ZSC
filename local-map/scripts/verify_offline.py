"""Run real-release HTTP and browser checks in a fresh, restricted process."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

import httpx
import mercantile

PROJECT = Path(__file__).resolve().parents[1]


def verify():
    evidence = PROJECT / "evidence"
    evidence.mkdir(exist_ok=True)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    report = {"python_socket_guard": True, "browser_external_requests_blocked": True}
    pointer = json.loads((PROJECT / "data/current.json").read_text(encoding="utf-8"))
    release = PROJECT / "data/builds" / pointer["version"]
    config = json.loads((release / "routing/valhalla.json").read_text(encoding="utf-8"))
    assert not config.get("mjolnir", {}).get("tile_url"), "Remote routing tiles must be disabled"
    report["routing_remote_tiles_disabled"] = True
    with (evidence / "offline-server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen([sys.executable, str(PROJECT / "scripts/offline_server.py"), "--port", str(port)],
                                  cwd=PROJECT, stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=base, trust_env=False, timeout=30) as client:
                deadline = time.monotonic() + 30
                while True:
                    if server.poll() is not None:
                        raise RuntimeError("Offline test server exited; see evidence/offline-server.log")
                    try:
                        health = client.get("/healthz")
                        if health.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Offline server did not become healthy")
                    time.sleep(0.2)
                report["health"] = health.json()
                metadata = client.get("/api/v1/map").raise_for_status().json()
                for layer in metadata["layers"]:
                    assert client.get(f"/api/v1/features/{layer}").raise_for_status().json()["type"] == "FeatureCollection"
                report["layers"] = list(metadata["layers"])
                for zoom in range(metadata["minzoom"], metadata["maxzoom"] + 1):
                    tile = mercantile.tile(*metadata["center"], zoom)
                    image = client.get(f"/api/v1/tiles/{zoom}/{tile.x}/{tile.y}.png").raise_for_status()
                    assert image.content.startswith(b"\x89PNG\r\n\x1a\n")
                for path in ("/", "/docs", "/openapi.json"):
                    assert client.get(path).status_code == 200
                examples = []
                for example in metadata["examples"]:
                    body = {key: example[key] for key in ("start", "end", "waypoints") if key in example}
                    result = client.post("/api/v1/routes", json=body).raise_for_status().json()
                    assert len(result["legs"]) == len(body.get("waypoints", [])) + 1
                    assert all(point["offset_m"] <= 50.1 for point in result["snapped_points"])
                    west, south, east, north = metadata["bounds"]
                    assert all(west <= lon <= east and south <= lat <= north
                               for lon, lat in result["route"]["geometry"]["coordinates"])
                    examples.append({"name": example["name"], "distance_m": result["distance_m"], "legs": len(result["legs"])})
                assert len(examples) >= 3
                body = {key: metadata["examples"][0][key] for key in ("start", "end", "waypoints") if key in metadata["examples"][0]}
                with ThreadPoolExecutor(max_workers=8) as pool:
                    responses = list(pool.map(lambda _: client.post("/api/v1/routes", json=body).raise_for_status().json(), range(24)))
                assert all(response == responses[0] for response in responses)
                invalid = client.post("/api/v1/routes", json={"start": [0, 0], "end": body["end"]})
                assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "INVALID_INPUT"
                report.update(examples=examples, concurrent_requests=24, zoom_levels=list(range(metadata["minzoom"], metadata["maxzoom"] + 1)))
            node = shutil.which("node")
            if not node:
                raise RuntimeError("Node is needed to run browser acceptance tests")
            browser = subprocess.run([node, "--test", "tests/web-smoke.mjs"], cwd=PROJECT,
                                     env=dict(os.environ, CAMPUS_MAP_URL=base), capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=240)
            (evidence / "web-tests.log").write_text(browser.stdout + browser.stderr, encoding="utf-8")
            if browser.returncode:
                raise RuntimeError("Browser checks failed; see evidence/web-tests.log")
            report["status"] = "passed"
        finally:
            if os.name == "nt":
                # The Windows venv launcher may own the real Python child.
                subprocess.run(["taskkill", "/PID", str(server.pid), "/T", "/F"], capture_output=True, timeout=15)
            else:
                server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
            deadline = time.monotonic() + 3
            while True:
                with socket.socket() as probe:
                    probe.settimeout(0.25)
                    report["server_port_released"] = probe.connect_ex(("127.0.0.1", port)) != 0
                if report["server_port_released"] or time.monotonic() >= deadline:
                    break
                time.sleep(0.1)
            report.setdefault("status", "failed")
            if not report["server_port_released"]:
                report["status"] = "failed"
            (evidence / "offline-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if not report["server_port_released"]:
                raise RuntimeError("The test server still owns its listener port")
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    verify()
