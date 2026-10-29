import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { decode } from "../web/src/utils/polyline.ts";

const root = fileURLToPath(new URL("../", import.meta.url));
const base = process.env.CAMPUS_MAP_URL;
const require = createRequire(new URL("../web/package.json", import.meta.url));
const puppeteer = require("puppeteer");

test("offline build retains provenance, local style, and local API docs", async () => {
  const upstream = await readFile(path.join(root, "web/UPSTREAM.md"), "utf8");
  assert.match(upstream, /699e32f3addaaed415257f020439384de54281a1/);
  const style = JSON.parse(
    await readFile(
      path.join(root, "web/dist/styles/campus-raster.json"),
      "utf8",
    ),
  );
  assert.deepEqual(style.sources.campus.tiles, [
    "/api/v1/tiles/{z}/{x}/{y}.png",
  ]);
  assert.deepEqual(
    style.sources.campus.bounds,
    [113.3852747260368, 22.522802343443914, 113.39558244764372, 22.53281022147416],
  );
  assert.equal(style.sources.campus.minzoom, 14);
  assert.equal(style.sources.campus.maxzoom, 18);
  for (const asset of ["swagger-ui-bundle.js", "swagger-ui.css", "LICENSE"]) {
    assert.ok(
      (await readFile(path.join(root, "web/dist/static/vendor/swagger", asset)))
        .length > 100,
    );
  }
  const html = await readFile(path.join(root, "web/dist/index.html"), "utf8");
  assert.match(html, /lang="zh-CN"/);
  assert.match(html, /connect-src 'self' blob:/);
});

test(
  "real offline API browser workflow",
  { skip: !base, timeout: 180000 },
  async (t) => {
    const origin = new URL(base).origin;
    const browser = await puppeteer.launch({
      headless: true,
      args: [
        "--no-sandbox",
        "--use-angle=swiftshader",
        "--enable-unsafe-swiftshader",
      ],
    });
    const page = await browser.newPage();
    const external = [];
    const pageErrors = [];
    const consoleMessages = [];
    const disallowed = [];
    const requests = [];
    let tileResponses = 0;
    const screenshots = path.join(root, ".runtime", "screenshots");
    await mkdir(screenshots, { recursive: true });
    try {
      await page.setViewport({ width: 1440, height: 1000 });
      page.setDefaultTimeout(10000);
      await page.evaluateOnNewDocument(() => {
        Object.defineProperty(navigator, "geolocation", {
          configurable: true,
          value: {
            getCurrentPosition(success, failure) {
              if (window.__campusGPSMode === "success")
                success({
                  coords: {
                    longitude: window.__campusGPSPoint[0],
                    latitude: window.__campusGPSPoint[1],
                    accuracy: 5,
                  },
                  timestamp: Date.now(),
                });
              else if (window.__campusGPSMode === "timeout")
                failure({ code: 3, PERMISSION_DENIED: 1, TIMEOUT: 3 });
              else failure({ code: 1, PERMISSION_DENIED: 1 });
            },
            watchPosition(success, failure) {
              this.getCurrentPosition(success, failure);
              return 1;
            },
            clearWatch() {},
          },
        });
        const original = URL.createObjectURL;
        URL.createObjectURL = function (blob) {
          if (["text/json", "application/json"].includes(blob.type))
            blob.text().then((text) => {
              window.__campusDownload = text;
            });
          return original.call(this, blob);
        };
        localStorage.setItem("valhalla_base_url", "https://example.invalid");
        localStorage.setItem("selectedMapStyle", "custom");
        localStorage.setItem(
          "customMapStyle",
          JSON.stringify({
            version: 8,
            sources: {
              online: {
                type: "raster",
                tiles: ["https://example.invalid/{z}/{x}/{y}.png"],
              },
            },
            layers: [],
          }),
        );
      });
      page.on("pageerror", (error) => pageErrors.push(String(error)));
      page.on("console", (message) => {
        if (["warn", "error"].includes(message.type()))
          consoleMessages.push(message.text());
      });
      await page.setRequestInterception(true);
      page.on("request", (request) => {
        const url = new URL(request.url());
        if (
          ["http:", "https:"].includes(url.protocol) &&
          url.origin !== origin
        ) {
          external.push(request.url());
          return request.abort();
        }
        if (
          /\/(height|isochrone|optimized_route|disabled-geocoding|search|reverse)(?:\?|$)/.test(
            url.pathname,
          )
        )
          disallowed.push(request.url());
        if (url.pathname === "/valhalla/route")
          requests.push(JSON.parse(url.searchParams.get("json")));
        return request.continue();
      });
      page.on("response", (response) => {
        if (
          /\/api\/v1\/tiles\/.*\.png$/.test(new URL(response.url()).pathname) &&
          response.status() === 200
        )
          tileResponses++;
      });
      const waitRoute = () => {
        const promise = page.waitForResponse(
          (response) => new URL(response.url()).pathname === "/valhalla/route",
          { timeout: 30000 },
        );
        promise.catch(() => {});
        return promise;
      };
      const clickText = async (text) => {
        for (const control of await page.$$('button,[role="menuitem"]')) {
          if (
            (await control.isVisible()) &&
            (await control.evaluate(
              (item, label) => item.textContent.trim() === label,
              text,
            ))
          ) {
            await control.click();
            return;
          }
        }
        assert.fail(`control exists: ${text}`);
      };
      const captureMap = async (name) => {
        await page.waitForSelector('.maplibregl-canvas[data-rendered="true"]');
        const bytes = await page.screenshot({
          path: path.join(screenshots, name),
          fullPage: false,
          captureBeyondViewport: false,
        });
        const paintedRatio = await page.evaluate(async (base64) => {
          const picture = new Image();
          picture.src = `data:image/png;base64,${base64}`;
          await picture.decode();
          const canvas = document.createElement("canvas");
          canvas.width = picture.width;
          canvas.height = picture.height;
          const context = canvas.getContext("2d");
          context.drawImage(picture, 0, 0);
          const pixels = context.getImageData(
            0,
            0,
            canvas.width,
            canvas.height,
          ).data;
          let colored = 0,
            total = 0;
          for (let y = 100; y < canvas.height - 70; y += 16)
            for (
              let x = canvas.width > 700 ? 430 : 60;
              x < canvas.width - 50;
              x += 16
            ) {
              const at = (y * canvas.width + x) * 4;
              total++;
              if (Math.min(pixels[at], pixels[at + 1], pixels[at + 2]) < 240)
                colored++;
            }
          return colored / total;
        }, Buffer.from(bytes).toString("base64"));
        assert.ok(
          paintedRatio > 0.1,
          `map canvas visibly rendered in ${name}: ${paintedRatio}`,
        );
      };
      const selectCoords = async (index, point) => {
        await page.click(`[data-testid="waypoint-input-${index}"]`);
        await page.waitForSelector(
          'input[placeholder="输入经度, 纬度，按回车确认"]',
        );
        await page.type(
          'input[placeholder="输入经度, 纬度，按回车确认"]',
          point.join(","),
        );
        await page.keyboard.press("Enter");
        await page.waitForSelector('[data-testid="search-result"]');
        await page.click('[data-testid="search-result"]');
        await page.waitForFunction(
          () =>
            !document.querySelector(
              'input[placeholder="输入经度, 纬度，按回车确认"]',
            ),
        );
      };
      await page.goto(base, { waitUntil: "networkidle0", timeout: 30000 });
      const metadata = await (await fetch(`${origin}/api/v1/map`)).json();
      assert.equal(metadata.coordinate_system, "GCJ-02");
      assert.equal(metadata.graph_coordinate_system, "GCJ-02");
      assert.equal(metadata.tile_provider, "osm");
      const liveStyle = await (await fetch(`${origin}/api/v1/map-style`)).json();
      assert.deepEqual(liveStyle.sources.campus.bounds, metadata.bounds);
      assert.equal(liveStyle.sources.campus.maxzoom, metadata.maxzoom);
      assert.match(liveStyle.sources.campus.tiles[0], new RegExp(`v=${metadata.version}$`));
      assert.equal(liveStyle.sources.footpaths, undefined);
      const bounds = (metadata.manifest ?? metadata).bounds;
      await page.waitForSelector('[data-testid="example-route-0"]');
      assert.ok(await page.$(".maplibregl-canvas"), "MapLibre canvas loaded");
      assert.equal(
        await page.$$eval(
          '[data-testid^="example-route-"]',
          (items) => items.length,
        ),
        3,
      );

      await t.test(
        "three real examples, native request and response, multi-leg shape",
        async () => {
          for (let i = 0; i < 3; i++) {
            const responsePromise = waitRoute();
            await page.click(`[data-testid="example-route-${i}"]`);
            const response = await responsePromise;
            assert.equal(response.status(), 200);
            const data = await response.json();
            await page.waitForSelector('[data-testid="route-results"]');
            await page.waitForFunction(() =>
              document
                .querySelector('[data-testid="route-debug-panel"] summary')
                .textContent.includes("HTTP 200"),
            );
            const request = requests.at(-1);
            assert.equal(request.costing, "pedestrian");
            assert.equal(request.costing_options.pedestrian.shortest, true);
            assert.equal(
              request.costing_options.pedestrian.walking_speed,
              5.04,
            );
            assert.ok(
              request.locations.every((location) => location.type === "break"),
            );
            assert.equal(data.trip.legs.length, request.locations.length - 1);
            assert.ok(data.trip.legs.every((leg) => leg.shape.length > 0));
            for (const leg of data.trip.legs) {
              for (const [lat, lng] of decode(leg.shape, 6)) {
                assert.ok(
                  lng >= bounds[0] &&
                    lng <= bounds[2] &&
                    lat >= bounds[1] &&
                    lat <= bounds[3],
                  "route coordinate remains in local tile coverage",
                );
              }
            }
            assert.ok(data.trip.summary.length > 0);
            assert.deepEqual(
              JSON.parse(
                await page.$eval(
                  '[data-testid="route-request"]',
                  (el) => el.textContent,
                ),
              ),
              request,
            );
            assert.deepEqual(
              JSON.parse(
                await page.$eval(
                  '[data-testid="route-response"]',
                  (el) => el.textContent,
                ),
              ),
              data,
            );
          }
          assert.ok(
            requests.some((request) => request.locations.length >= 3),
            "examples include a via point",
          );
          assert.ok(tileResponses > 0, "local raster PNGs were rendered");
          await page.waitForFunction(
            () =>
              !document.querySelector('[data-testid="calculate-route-button"]')
                .disabled,
          );
          await captureMap("desktop.png");
        },
      );

      await t.test(
        "JSON and GeoJSON export preserve route geometry",
        async () => {
          for (const format of ["JSON", "GeoJSON"]) {
            await clickText("导出");
            await page.waitForSelector('[role="menuitem"]');
            await clickText(format);
            await page.waitForFunction(
              () => !document.querySelector('[role="menuitem"]'),
            );
            await page.waitForFunction(() => Boolean(window.__campusDownload));
            const data = JSON.parse(
              await page.evaluate(() => window.__campusDownload),
            );
            if (format === "JSON") assert.ok(data.trip.legs.length > 0);
            else assert.equal(data.geometry.type, "LineString");
            await page.evaluate(() => {
              window.__campusDownload = "";
            });
          }
        },
      );

      await t.test(
        "GPS success, rejection and timeout all preserve manual route planning",
        async () => {
          await page.click('[data-testid="use-current-location-button"]');
          await page.waitForFunction(() =>
            document.body.textContent.includes("未获得定位权限"),
          );
          const map = await (await fetch(`${origin}/api/v1/map`)).json();
          const example = (map.manifest ?? map).examples[0];
          // The browser emits WGS84. Invert the independently served calibration
          // only in this test to locate a GPS point that lands on a known road.
          let gpsPoint = [...example.start];
          for (let iteration = 0; iteration < 8; iteration++) {
            const conversion = await (await fetch(`${origin}/api/v1/coordinates/gps`, {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ points: [gpsPoint] }),
            })).json();
            gpsPoint = gpsPoint.map((value, axis) => value - (conversion.points[0][axis] - example.start[axis]));
          }
          assert.ok(Math.abs(gpsPoint[0] - example.start[0]) > 0.005, "GPS fixture is WGS84, distinct from GCJ-02 route coordinates");
          await page.evaluate((point) => {
            window.__campusGPSMode = "success";
            window.__campusGPSPoint = point;
          }, gpsPoint);
          const gpsResponse = waitRoute();
          await page.click('[data-testid="use-current-location-button"]');
          assert.equal((await gpsResponse).status(), 200);
          t.diagnostic("GPS success produced a real local route");
          assert.ok(Math.abs(requests.at(-1).locations[0].lon - example.start[0]) < 1e-8);
          assert.ok(Math.abs(requests.at(-1).locations[0].lat - example.start[1]) < 1e-8);
          await page.evaluate(() => {
            window.__campusGPSMode = "timeout";
          });
          await page.click('[data-testid="use-current-location-button"]');
          await page.waitForFunction(() =>
            document.body.textContent.includes("定位暂不可用"),
          );
          await page.click('[data-testid="reset-waypoints-button"]');
          await selectCoords(0, example.start);
          t.diagnostic("Manual start coordinate selected");
          await page.screenshot({
            path: path.join(screenshots, "manual-start.png"),
            fullPage: false,
          });
          const responsePromise = waitRoute();
          await selectCoords(1, example.end);
          t.diagnostic(
            `Manual coordinate labels: ${JSON.stringify(await page.$$eval('[role="combobox"]', (els) => els.map((el) => el.textContent)))}`,
          );
          await page.screenshot({
            path: path.join(screenshots, "manual-coordinates.png"),
            fullPage: false,
          });
          assert.equal((await responsePromise).status(), 200);
          t.diagnostic(
            "Manual start/end coordinates produced a real local route",
          );
          await page.waitForSelector('[data-testid="route-results"]');
        },
      );

      await t.test(
        "original task GCJ-02 inputs reach the routing graph unchanged",
        async () => {
          const start = [113.391996, 22.529253];
          const end = [113.392747, 22.530308];
          await page.click('[data-testid="reset-waypoints-button"]');
          await selectCoords(0, start);
          const responsePromise = waitRoute();
          await selectCoords(1, end);
          assert.equal((await responsePromise).status(), 200);
          const locations = requests.at(-1).locations;
          assert.deepEqual([locations[0].lon, locations[0].lat], start);
          assert.deepEqual([locations[1].lon, locations[1].lat], end);
          await captureMap("original-task-gcj02.png");
        },
      );

      await t.test(
        "click selection, draggable marker and waypoint ordering",
        async () => {
          const exampleResponse = waitRoute();
          await page.click('[data-testid="example-route-2"]');
          assert.equal((await exampleResponse).status(), 200);
          const old = structuredClone(requests.at(-1).locations);
          await page.click('[data-testid="close-directions-button"]');
          await page.waitForFunction(
            () => !document.querySelector('[data-slot="sheet-content"]'),
          );
          await page.waitForFunction(() => {
            const marker = document.querySelector(".maplibregl-marker");
            if (!marker) return false;
            const box = marker.getBoundingClientRect();
            const inView = box.left > 0 && box.right < innerWidth && box.top > 0 && box.bottom < innerHeight;
            const previous = window.__campusMarkerBounds;
            window.__campusMarkerBounds = [box.x, box.y];
            if (!inView || !previous || Math.abs(previous[0] - box.x) > .1 || Math.abs(previous[1] - box.y) > .1) {
              window.__campusMarkerStableFrames = 0;
              return false;
            }
            window.__campusMarkerStableFrames = (window.__campusMarkerStableFrames || 0) + 1;
            return window.__campusMarkerStableFrames >= 5;
          });
          const marker = await page.$(".maplibregl-marker");
          const box = await marker.boundingBox();
          t.diagnostic(`Dragging map marker at ${JSON.stringify(box)}`);
          const dragged = waitRoute();
          await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
          await page.mouse.down();
          await page.mouse.move(
            box.x + box.width / 2 + 12,
            box.y + box.height / 2 + 8,
            { steps: 10 },
          );
          await page.mouse.up();
          assert.equal((await dragged).status(), 200);
          assert.notDeepEqual(requests.at(-1).locations[0], old[0]);
          t.diagnostic("Map marker drag produced a real local route");
          await page.mouse.click(1100, 700);
          await page
            .waitForSelector('[data-testid="button-group-right-context"]', {
              timeout: 1000,
            })
            .catch(() => page.mouse.click(1100, 700));
          await page.waitForSelector(
            '[data-testid="button-group-right-context"]',
          );
          assert.ok(
            await page.evaluate(() =>
              document
                .querySelector('[data-testid="button-group-right-context"]')
                .textContent.includes("设为起点"),
            ),
          );
          await page.mouse.click(1000, 700);
          await page.click('[data-testid="tab-directions-button"]');
          await page.waitForSelector('[data-testid="waypoint-input-0"]');
          await page.waitForFunction(
            () =>
              Math.abs(
                document
                  .querySelector(".campus-sidebar")
                  .getBoundingClientRect().left,
              ) < 1,
          );
          t.diagnostic("Map click selector and reopened panel verified");
          const handle = await page.$('button[aria-label^="拖动路线点 1"]');
          await handle.scrollIntoView();
          const dragBox = await handle.boundingBox();
          const nextBox = await (
            await page.$('[role="listitem"][aria-label="路线点 2"]')
          ).boundingBox();
          t.diagnostic(
            `Waypoint drag bounds ${JSON.stringify({ dragBox, nextBox })}`,
          );
          const orderBefore = structuredClone(requests.at(-1).locations);
          const reordered = waitRoute();
          try {
            await page.mouse.move(
              dragBox.x + dragBox.width / 2,
              dragBox.y + dragBox.height / 2,
            );
            await page.mouse.down();
            await page.mouse.move(
              dragBox.x + dragBox.width / 2,
              dragBox.y + dragBox.height / 2 + 10,
              { steps: 3 },
            );
            await page.waitForFunction(
              () =>
                getComputedStyle(
                  document.querySelector(
                    '[role="listitem"][aria-label="路线点 1"]',
                  ),
                ).opacity === "0.5",
            );
            const fromY = dragBox.y + dragBox.height / 2 + 10;
            const toY = nextBox.y + nextBox.height + 18;
            for (let step = 1; step <= 12; step++) {
              await page.mouse.move(
                dragBox.x + dragBox.width / 2,
                fromY + ((toY - fromY) * step) / 12,
              );
              await page.evaluate(() => new Promise(requestAnimationFrame));
            }
            t.diagnostic(
              `Waypoint drag live state: ${await page.evaluate(() => [...document.querySelectorAll('[role="status"]')].map((el) => el.textContent).join(" | "))}`,
            );
            t.diagnostic(
              `Waypoint DOM drag state: ${JSON.stringify(await page.evaluate(() => ({ rows: [...document.querySelectorAll('[role="listitem"]')].map((el) => ({ style: el.getAttribute("style"), rect: el.getBoundingClientRect().toJSON() })), scroll: document.querySelector(".campus-sidebar").scrollTop, canvasLost: document.querySelector(".maplibregl-canvas").getContext("webgl2")?.isContextLost() })))}`,
            );
            t.diagnostic(
              `Browser warnings: ${JSON.stringify(consoleMessages)}`,
            );
          } finally {
            await page.mouse.up();
          }
          await page.evaluate(() => new Promise(requestAnimationFrame));
          t.diagnostic(
            `Waypoint drop state: ${JSON.stringify(await page.evaluate(() => ({ labels: [...document.querySelectorAll('[role="combobox"]')].map((el) => el.textContent), live: [...document.querySelectorAll('[role="status"]')].map((el) => el.textContent).join(" | ") })))}`,
          );
          // Full-page capture can cancel an active pointer sensor; capture after release.
          await page.screenshot({
            path: path.join(screenshots, "waypoint-drag.png"),
            fullPage: false,
          });
          assert.equal((await reordered).status(), 200);
          assert.notDeepEqual(requests.at(-1).locations, orderBefore);
          assert.deepEqual(
            [...requests.at(-1).locations].sort((a, b) => a.lon - b.lon),
            [...orderBefore].sort((a, b) => a.lon - b.lon),
          );
        },
      );

      await t.test(
        "API errors are visible and a valid route recovers",
        async () => {
          const rejected = waitRoute();
          await selectCoords(0, [0, 0]);
          assert.ok((await rejected).status() >= 400);
          await page.waitForFunction(() =>
            document
              .querySelector('[data-testid="route-debug-panel"] summary')
              .textContent.includes("失败"),
          );
          assert.ok(
            (
              await page.$eval(
                '[data-testid="route-error"]',
                (el) => el.textContent,
              )
            ).length > 0,
          );
          const recovered = waitRoute();
          await page.click('[data-testid="example-route-0"]');
          assert.equal((await recovered).status(), 200);
        },
      );

      await t.test(
        "responsive sidebar, mobile map and local Swagger docs",
        async () => {
          for (const close of await page.$$("[data-sonner-toast] button[data-close-button]")) {
            await close.click();
          }
          await page.mouse.move(1300, 20);
          await page.waitForFunction(() => [...document.querySelectorAll("[data-sonner-toast]")]
            .every((el) => el.dataset.removed === "true" || getComputedStyle(el).opacity === "0"),
            { timeout: 12000 });
          for (const width of [320, 768, 1024]) {
            await page.setViewport({ width, height: 900 });
            if (width === 320) {
              await page.$eval('[data-testid="route-debug-panel"]', (el) => {
                el.open = true;
                el.scrollIntoView({ block: "start" });
              });
              await page.waitForFunction(() => {
                const panel = document
                  .querySelector('[data-testid="route-debug-panel"]')
                  .getBoundingClientRect();
                return (
                  panel.top >= 0 &&
                  panel.top < innerHeight &&
                  panel.right <= innerWidth
                );
              });
            }
            const metrics = await page.$eval(".campus-sidebar", (el) => ({
              left: el.getBoundingClientRect().left,
              right: el.getBoundingClientRect().right,
              overflow: el.scrollWidth > el.clientWidth,
            }));
            assert.ok(metrics.left >= 0 && metrics.right <= width);
            assert.equal(metrics.overflow, false);
            await page.screenshot({
              path: path.join(screenshots, `width-${width}.png`),
              fullPage: false,
            });
          }
          await page.setViewport({ width: 390, height: 844 });
          await page.click('button[aria-label="缩放到路线"]');
          await page.waitForSelector(
            '.maplibregl-canvas[data-rendered="true"]',
          );
          await page.click('[data-testid="close-directions-button"]');
          await page.waitForFunction(
            () => !document.querySelector('[data-slot="sheet-content"]'),
          );
          await captureMap("mobile-map.png");
          await page.goto(`${origin}/docs`, { waitUntil: "networkidle0" });
          await page.waitForSelector(".swagger-ui");
          assert.ok(
            await page.$(".swagger-ui .opblock"),
            "interactive local OpenAPI documentation loaded",
          );
        },
      );

      assert.deepEqual(
        external,
        [],
        "no external request attempted while external network blocked",
      );
      assert.deepEqual(
        disallowed,
        [],
        "unsupported upstream endpoints never called",
      );
      assert.deepEqual(pageErrors, [], "no uncaught browser exception");
    } finally {
      await browser.close();
    }
  },
);
