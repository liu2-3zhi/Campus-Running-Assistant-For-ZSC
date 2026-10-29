# Third-party projects and map data

This directory integrates existing projects. It does not implement a routing
algorithm, OSM parser, raster map renderer, or SDF font algorithm.

| Project | Version / source | Role | License |
| --- | --- | --- | --- |
| Valhalla / pyvalhalla | 3.9.1, https://github.com/valhalla/valhalla | Native pedestrian routing and graph building | MIT; bundled dependency notices apply |
| Valhalla web-app | Upstream revision recorded in web/UPSTREAM.md | Adapted local browser UI | MIT; web/LICENSE retained |
| TileServer GL | 5.7.0, https://github.com/maptiler/tileserver-gl | Build-time PNG rendering | BSD-2-Clause |
| MapLibre GL JS / Native | Locked by web/tools package-lock files | Map display and rasterization | BSD-3-Clause |
| MapLibre Font Maker | Source digests recorded by preparation | CJK glyph generation | BSD-3-Clause |
| Noto CJK | Source and license retained with preparation assets | Chinese map labels | SIL Open Font License 1.1 |
| PyOsmium | 4.3.2, https://github.com/osmcode/pyosmium | OSM data handling | BSD-2-Clause |
| osm2geojson | 0.3.2, https://github.com/rapkin/osm2geojson | GeoJSON conversion | MIT |
| Mercantile | 1.2.1, https://github.com/mapbox/mercantile | XYZ tile enumeration | BSD-3-Clause |
| FastAPI / Uvicorn | requirements.lock.txt | Local HTTP service | MIT / BSD-3-Clause |
| Swagger UI | Version recorded with web assets | Local interactive API documentation | Apache-2.0 |

Upstream release references and commits are recorded in UPSTREAM_LOCK.json.
Published binaries are identified separately from source references; this
distribution does not claim a reproducible source build of upstream binaries.

Python dependencies are pinned by requirements.lock.txt. Node dependencies are
pinned by the separate web and tools package-lock files. License files shipped
with those dependencies remain authoritative for their bundled components.

## OpenStreetMap

Map data: Copyright OpenStreetMap contributors.

https://www.openstreetmap.org/copyright

Database license: Open Data Commons Open Database License 1.0 (ODbL).

https://opendatacommons.org/licenses/odbl/1-0/

Preserve attribution and source/license metadata when sharing map data or images.
See data/source and each release manifest for the retrieved source, time, and
SHA-256 checksums. These local derived data do not imply endorsement by the
school, OpenStreetMap, or upstream software projects.

## Overture Maps evaluation

Overture Buildings was evaluated as an optional ODbL source:
https://docs.overturemaps.org/guides/buildings/ . Its building coverage was
larger in the candidate extract, but its transportation extract did not improve
the campus footpath coverage. It is therefore not part of the active release;
future imports must be reviewed, converted to the active coordinate system and
recorded as a separate source.
