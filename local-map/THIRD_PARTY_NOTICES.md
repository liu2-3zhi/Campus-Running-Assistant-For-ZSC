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

## AMap

The default background consists of cached AMap raster images. AMap is a data
service, not an open source component or ODbL map source. Its terms apply
separately: https://lbs.amap.com/pages/terms .

Original OSM nodes are converted once with the official GPS-to-GCJ-02 Web
service: https://lbs.amap.com/api/webservice/guide/api/convert . The local
routing graph and map features use the converted coordinates. A sampled official
conversion grid supports offline browser GPS conversion inside the campus.

Raster images are retrieved from the tested, undocumented endpoint
https://webrd01.is.autonavi.com/appmaptile . There is no upstream version or
availability guarantee for that endpoint. The manifest records its actual URL,
attribution, native maximum zoom and terms. All AMap preparation requests use
the configured origin https://zslf.zsc.edu.cn; this request origin is not a claim
that the images originate from that site. API keys remain in ignored local
configuration or environment variables and are not shipped with the Web bundle.
