"""Keep the public response documentation aligned with the unified API."""

from fastapi.testclient import TestClient

from campus_map.api import create_app


def test_route_response_and_error_shapes_are_documented(tmp_path):
    client = TestClient(create_app(tmp_path))
    schema = client.get("/openapi.json").json()
    responses = schema["paths"]["/api/v1/routes"]["post"]["responses"]
    assert "GCJ-02" in schema["paths"]["/api/v1/routes"]["post"]["description"]
    assert responses["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/RouteResult")
    for status in ("404", "422", "503"):
        assert responses[status]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
    required = schema["components"]["schemas"]["RouteResult"]["required"]
    assert set(required) == {"route", "legs", "distance_m", "duration_s", "snapped_points"}
    invalid = client.post("/api/v1/routes", json={"start": [0], "end": [1, 2]})
    assert invalid.status_code == 422
    assert set(invalid.json()) == {"error"}
    assert set(invalid.json()["error"]) == {"code", "message"}
