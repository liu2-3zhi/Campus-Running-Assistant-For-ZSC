"""Compare offline GPS calibration with AMap and check original task coordinates."""

import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from campus_map.amap import REQUEST_ORIGIN, convert_points
from campus_map.gps import Calibration
from campus_map.routing import RoutingService, RouteNotFoundError, _distance_m
from campus_map.validation import validate_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-file", type=Path)
    parser.add_argument("--compare-amap", action="store_true", help="Use 25 official conversion samples while online")
    options = parser.parse_args()
    data_root = PROJECT / "data"
    report = {"data": validate_data(data_root), "request_origin": REQUEST_ORIGIN}
    release = data_root / "builds" / report["data"]["version"]
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    calibration = Calibration(json.loads((release / "coordinate-calibration.json").read_text(encoding="utf-8")))
    report.update(coordinate_system=manifest["coordinate_system"], graph_coordinate_system=manifest["graph_coordinate_system"],
                  tile_provider=manifest["tile_provider"], tiles=manifest["coverage"]["tiles"])
    if options.compare_amap:
        west, south, east, north = calibration.bounds
        # Off-grid samples check interpolation, rather than merely replaying grid vertices.
        samples = [[round(west + (east - west) * (column + .37) / 5, 6),
                    round(south + (north - south) * (row + .61) / 5, 6)]
                   for row in range(5) for column in range(5)]
        official = convert_points(samples)
        errors = [_distance_m(calibration.convert(point)[0], expected) for point, expected in zip(samples, official)]
        report["gps_calibration"] = {"official_samples": len(samples), "maximum_error_m": max(errors),
                                     "mean_error_m": sum(errors) / len(errors)}
        assert max(errors) < .2, "Campus GPS calibration differs from AMap by over 0.2m"
    if options.task_file:
        task = json.loads(options.task_file.read_text(encoding="utf-8"))
        points = task["target_points"]
        west, south, east, north = manifest["bounds"]
        service = RoutingService(release)
        checks = []
        for index, point in enumerate(points):
            assert west <= point[0] <= east and south <= point[1] <= north, "Original GCJ-02 point is outside the map"
            try:
                response = service.route(point, point)
                assert response["snapped_points"][0]["input"] == point, "Task coordinate was converted at runtime"
                checks.append({"index": index, "input": point, "within_map": True,
                               "snap_offset_m": response["snapped_points"][0]["offset_m"]})
            except RouteNotFoundError:
                checks.append({"index": index, "input": point, "within_map": True,
                               "routing": "OSM has no walkable path within 50m"})
        report["original_task_points"] = checks
    report["status"] = "passed"
    output = PROJECT / "evidence/gcj02-report.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
