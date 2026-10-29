"""User-facing entry point; heavy dependencies are loaded only when needed."""

import argparse
import json
from pathlib import Path
import sys

from .validation import DataError, validate_data


ROOT = Path(__file__).resolve().parents[1]


def _port(value: str) -> int:
    number = int(value)
    if not 0 <= number <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 0 and 65535.")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Campus offline map and walking routes")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "build", "validate", "serve"):
        command = commands.add_parser(name)
        command.add_argument("--data-dir", type=Path, default=ROOT / "data")
        if name == "prepare":
            command.add_argument("--source", type=Path, help="Import an existing local OSM file")
            command.add_argument("--footpaths", type=Path,
                                 help="Collect campus walking paths for GCJ-02 target_points from a task JSON or coordinate array")
            command.add_argument("--tile-provider", choices=("amap", "osm"), default="amap",
                                 help="Prepare AMap raster tiles (default), or render OSM locally")
            command.add_argument("--minzoom", type=int, default=14)
            command.add_argument("--maxzoom", type=int, default=18)
        elif name == "build":
            command.add_argument("--minzoom", type=int, default=14)
            command.add_argument("--maxzoom", type=int, default=18)
        elif name == "serve":
            command.add_argument("--host", default="127.0.0.1")
            command.add_argument("--port", type=_port, default=None,
                                 help="Use this exact port (0 selects a free port); default prefers 8765 with automatic fallback")
    arguments = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(arguments or ["serve"])
    try:
        data_root = args.data_dir.resolve()
        if args.command == "validate":
            result = validate_data(data_root)
        elif args.command == "serve":
            from .api import create_app
            from .server import serve

            return serve(create_app(data_root=data_root), host=args.host, port=args.port)
        elif args.command == "prepare":
            from .pipeline import prepare

            if not 0 <= args.minzoom <= args.maxzoom <= 20:
                raise DataError("Require 0 <= minzoom <= maxzoom <= 20", "INVALID_INPUT")
            if args.tile_provider == "amap" and args.maxzoom > 18:
                raise DataError("AMap native tiles support maxzoom 18; the web page overzooms to 20.", "INVALID_INPUT")
            footpath_points = None
            if args.footpaths is not None:
                reference = json.loads(args.footpaths.read_text(encoding="utf-8"))
                footpath_points = reference.get("target_points") if isinstance(reference, dict) else reference
                if not isinstance(footpath_points, list):
                    raise DataError("Footpaths JSON must be a coordinate array or contain target_points.", "INVALID_INPUT")
                footpath_points = [point for point in footpath_points
                                   if isinstance(point, (list, tuple)) and len(point) == 2
                                   and point != [0, 0] and tuple(point) != (0, 0)]
            result = prepare(data_root, source=args.source, tile_provider=args.tile_provider,
                             minzoom=args.minzoom, maxzoom=args.maxzoom, footpath_points=footpath_points)
        else:
            from .pipeline import build

            if not 0 <= args.minzoom <= args.maxzoom <= 20:
                raise DataError("Require 0 <= minzoom <= maxzoom <= 20", "INVALID_INPUT")
            result = build(data_root, minzoom=args.minzoom, maxzoom=args.maxzoom)
        print(json.dumps(result, ensure_ascii=True, default=str))
        return 0
    except KeyboardInterrupt:
        return 130
    except (DataError, OSError, ValueError, RuntimeError) as error:
        print(json.dumps({
            "code": getattr(error, "code", "COMMAND_FAILED"),
            "message": str(error),
        }, ensure_ascii=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
