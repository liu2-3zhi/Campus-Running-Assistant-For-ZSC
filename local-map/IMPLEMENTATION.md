# Campus offline map implementation

User-approved plan: independent Python entry point under local-map; Valhalla
3.9.1 for pedestrian routes and TileServer GL 5.7.0 for local OSM rendering,
and the upstream Valhalla web-app for the local browser interface.

## Boundaries

- GCJ-02 coordinates, longitude before latitude. Original WGS84 OSM is archived
  separately and converted forward once with the local formula before graph building.
  Runtime bounds come from the immutable release manifest. No inverse coordinate
  conversion occurs during routing or manual input.
- Runtime must read local assets only. No integration with the main application.
- Preserve OSM and upstream licenses, pinned versions, and source provenance.
- Preparation/build failures must preserve the last usable data release.
- No push, merge, or rebase.

## Shared interfaces

- Data root: local-map/data. Immutable releases: data/builds/<version>.
- Active pointer: data/current.json with {"version": "<version>"}.
- Each release: manifest.json, coordinate-calibration.json,
  features/<layer>.geojson, tiles/<z>/<x>/<y>.png,
  routing/valhalla.json and routing/tiles (or routing/tiles.tar).
- manifest.json: version, coordinate_system, graph_coordinate_system,
  source_coordinate_system, coordinate_conversion, tile_provider,
  name, bounds, center, minzoom, maxzoom, layers,
  coverage, sources, examples, and checksums (relative file names -> SHA256).
- API factory: campus_map.api.create_app(data_root: Path | None = None).
- Routing adapter: campus_map.routing.RoutingService(release_dir: Path), with
  route(start, end, waypoints) and native_route(payload) methods.
- Build module: campus_map.pipeline.prepare(data_root, source=None) and
  campus_map.pipeline.build(data_root, minzoom=14, maxzoom=18).
- CLI root main.py owns prepare/build/validate/serve; web/dist is served at /.

## Progress

- Current GCJ-02 release: the archived OSM snapshot is converted locally, rendered
  by TileServer GL, and served only from the release directory. A local 17x17 GPS
  calibration grid keeps browser GPS conversion offline. Legacy provider releases,
  browser caches and permalinks are isolated to avoid coordinate mixing.
- Runtime exposes GCJ-02 through routes, native polyline6, map metadata and
  features; /api/v1/coordinates/gps is the explicit WGS84 GPS input boundary.
- OSM remains the default source because the official OSM API and archived
  Overpass snapshot are redistributable and can be rebuilt locally. Overture
  Buildings was evaluated as an optional candidate but is not mixed into this
  release; its transportation extract did not improve campus footpath coverage.
  See VALIDATION.md for the latest checks and residual OSM coverage limits.

- Baseline: main clean, ahead 69. Dedicated branch codex/campus-offline-map.
- Ruling: use the explicitly requested checkout and isolated local-map directory;
  independent tasks share this checkout with disjoint file ownership.
- Dependency feasibility: official Windows Valhalla wheel, native TileServer GL,
  and official Font Maker WASM all executed successfully.
- Data pipeline: real OSM snapshot retained; 1416 PNGs, 61 CJK glyph ranges and
  5 graph files published with an atomic pointer and file checksums.
- Routing/API: implemented, including public response/error schemas and local
  Swagger assets; actual synthetic graph and campus routes verified.
- Web: final upstream adaptation built, 815 unit tests and 8 browser acceptance
  checks passed. See VALIDATION.md for evidence and residual limits.
- Independent code review: identified name/coverage/validation defects, fixed.
- Integration: real-release HTTP, 24 concurrent requests, restricted cold-start
  and independent visual verification passed; task servers are shut down.
