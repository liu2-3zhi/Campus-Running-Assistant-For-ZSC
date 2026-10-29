# Upstream provenance

This directory vendors the official Valhalla Web App, licensed under MIT.

- Repository: https://github.com/valhalla/web-app
- Commit: `699e32f3addaaed415257f020439384de54281a1`
- Source archive: https://codeload.github.com/valhalla/web-app/zip/699e32f3addaaed415257f020439384de54281a1
- Retrieved: 2026-10-29
- Upstream license: [LICENSE](LICENSE)
- Upstream package metadata and npm lockfile are retained.

Campus distribution changes retain the upstream React/MapLibre route planner,
waypoint ordering/dragging, route display, GPS and JSON/GeoJSON export. They lock
the application to a same-origin pedestrian Valhalla adapter and local raster
tiles, remove unsupported online-service controls, add Chinese route workflow
copy, local map examples and a request/response debug panel. The upstream
developer documentation and test fixtures describe the original application.

The campus distribution now uses GCJ-02 for map data, route coordinates and exports.
Manual coordinates are retained verbatim. Browser GPS is converted once through the
same-origin calibrated GPS API, with a local forward approximation as fallback.
`GcjGeolocateControl` adapts MapLibre 5.15's success callback before its blue dot and
camera update. The active Python release supplies the map style at `/api/v1/map-style`.
Coordinate cache keys and permalink `crs=gcj02` isolate old WGS84 browser state.

OpenStreetMap attribution is displayed for the default locally rendered raster background; the sidebar
identifies the separate OSM routing source. The alternate locally rendered OSM
background retains OpenStreetMap attribution. Routing coverage is limited to
the real OSM features in the configured campus bounds.

Local browser acceptance tests pin `puppeteer@25.14.0` as a web development
dependency from [puppeteer/puppeteer](https://github.com/puppeteer/puppeteer),
licensed under Apache-2.0 as recorded in its installed npm package metadata.
`tests/web-smoke.mjs` resolves it from this package so tests do not
depend on the parent checkout. Browser binaries use Puppeteer's local cache;
this test dependency is not required by the Python service.

Local API documentation assets are copied from the npm package
`swagger-ui-dist@5.34.0` into `public/static/vendor/swagger/`. Its Apache-2.0
license is retained there. Reproduce after `npm ci` with PowerShell:

```powershell
Copy-Item node_modules/swagger-ui-dist/swagger-ui-bundle.js public/static/vendor/swagger/
Copy-Item node_modules/swagger-ui-dist/swagger-ui.css public/static/vendor/swagger/
Copy-Item node_modules/swagger-ui-dist/LICENSE public/static/vendor/swagger/
```
