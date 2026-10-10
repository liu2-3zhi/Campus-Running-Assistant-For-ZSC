/**
 * 临时复现脚本：用真实任务数据端到端复现“路线直线连接”与
 * “多段同时变蓝”两个缺陷。
 *
 * 1) 抓取腾讯地图逐段步行路线（真实 API）
 * 2) 在 Node 中执行 main.py 内嵌的腾讯运行时 JS，得到后端规划结果
 * 3) 复刻 _complete_route_path_with_waypoint_endpoints + auto_generate_path_with_api
 * 4) 在 Node 中加载真实的前端 legacy-map-render.js，调用
 *    buildProviderRouteProgressSegments 检查分段着色
 *
 * 用法: node tools/repro_pipeline.mjs
 * 仅用于本地诊断，不属于运行时依赖。
 */
import http from "node:http";
import vm from "node:vm";
import { readFileSync } from "node:fs";

const KEY = "XQBBZ-WMQEL-VYQPF-E3SA2-XDD52-4CBS7";
const ROOT = new URL("../", import.meta.url);
const TASK = JSON.parse(
  readFileSync(new URL("tests/fixtures/map_route_task_9points.json", ROOT), "utf8"),
);
const WAYPOINTS = TASK.target_points.map((point) => [Number(point[0]), Number(point[1])]);

const mainPy = readFileSync(new URL("main.py", ROOT), "utf8");
const s = mainPy.indexOf("def _plan_route_path_with_tencent_runtime(");
const e = mainPy.indexOf("def _plan_route_path_with_tianditu_runtime(", s);
const block = mainPy.slice(s, e);
const routeScript = block.slice(block.indexOf('"""') + 3, block.lastIndexOf('"""')).trim();

/** 本地代理：把 JSONP 请求转发到真实腾讯地图服务 */
function startProxy() {
  return http.createServer(async (req, res) => {
    const u = new URL(req.url, "http://127.0.0.1");
    const cb = u.searchParams.get("callback");
    const params = [...u.searchParams.entries()].filter(([k]) => k !== "callback");
    const target = `https://apis.map.qq.com${u.pathname}?${params
      .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
      .join("&")}`;
    try {
      const upstream = await fetch(target);
      const text = await upstream.text();
      res.writeHead(200, { "Content-Type": "application/javascript; charset=utf-8" });
      res.end(`${cb}(${text});`);
    } catch (err) {
      res.writeHead(502);
      res.end(String(err));
    }
  });
}

/** 从腾讯 JSONP 响应中提取 JSON（响应可能带有 QQmap&& 前缀） */
function extractJsonpPayload(text, callbackName) {
  const marker = `${callbackName}(`;
  let body;
  const at = text.indexOf(marker);
  if (at >= 0) {
    body = text.slice(at + marker.length);
  } else {
    const open = text.indexOf("(");
    if (open < 0) return null;
    body = text.slice(open + 1);
  }

  // 真实响应形如 callback(QQmap&&QQmap({...}););
  // 不能用首尾括号截取，需要花括号配对 + 字符串感知扫描。
  const start = body.indexOf("{");
  if (start < 0) return null;
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let i = start; i < body.length; i += 1) {
    const ch = body[i];
    if (inString) {
      if (escaped) escaped = false;
      else if (ch === "\\") escaped = true;
      else if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') inString = true;
    else if (ch === "{") depth += 1;
    else if (ch === "}") {
      depth -= 1;
      if (depth === 0) {
        try {
          return JSON.parse(body.slice(start, i + 1));
        } catch (err) {
          return null;
        }
      }
    }
  }
  return null;
}

function createSandbox(port) {
  const sandbox = { console, setTimeout, clearTimeout, URL, fetch, JSON, Math, Number, String, Array, Object, Date, Promise, encodeURIComponent, decodeURIComponent };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.document = {
    head: {
      appendChild(script) {
        const u = new URL(script.src);
        const cb = u.searchParams.get("callback");
        const url = `http://127.0.0.1:${port}${u.pathname}${u.search}`;
        console.log("[dbg] src=", String(script.src).slice(0,110));
        fetch(url)
          .then((r) => r.text())
          .then((text) => {
            const payload = extractJsonpPayload(text, cb);
            if (payload === null) {
              if (typeof script.onerror === "function") script.onerror();
              return;
            }
            sandbox.window[cb](payload);
          })
          .catch(() => {
            if (typeof script.onerror === "function") script.onerror();
          });
      },
    },
    createElement() {
      return {
        parentNode: null,
        set src(value) {
          this._src = value;
        },
        get src() {
          return this._src;
        },
      };
    },
  };
  vm.createContext(sandbox);
  return sandbox;
}

/**
 * 注意：后端补点逻辑（_complete_route_path_with_waypoint_endpoints）在 Python 侧，
 * 请改用 tools/repro_task_route.py 验证；本脚本只负责
 * ① 用真实腾讯 API 跑 main.py 内嵌的腾讯运行时 JS，导出规划路径；
 * ② 在 Node 中加载真实前端 legacy-map-render.js，校验分段着色。
 */

function distanceM(a, b) {
  return Math.hypot(
    (a.lng - b.lng) * Math.cos((a.lat * Math.PI) / 180) * 111320,
    (a.lat - b.lat) * 110540,
  );
}

/** 加载真实前端 legacy-map-render.js，导出进度分段相关函数 */
function loadFrontendProgressModule() {
  const source = readFileSync(new URL("scripts/legacy-map-render.js", ROOT), "utf8");
  const needed = [
    "normalizeRouteCoord",
    "isRouteSegmentSeparator",
    "normalizeRouteCoords",
    "estimateProviderCoordDistanceMeters",
    "findNearestProviderRouteIndex",
    "resolveRouteProgressIndex",
    "resolveTaskProgressSequence",
    "hasActiveRouteProgress",
    "resolveVisualTaskProgressSequence",
    "getProviderRouteProgressStatus",
    "appendProviderRouteProgressSegment",
    "buildProviderRouteProgressSegments",
    "buildProviderRouteProgressSegmentsByProgress",
    "splitRouteCoordsIntoDrawableSegments",
  ];
  const chunks = [];
  for (const name of needed) {
    const re = new RegExp(`^function ${name}\\(`, "m");
    const match = re.exec(source);
    if (!match) throw new Error(`未找到函数 ${name}`);
    let depth = 0;
    let i = source.indexOf("{", match.index);
    const begin = match.index;
    for (; i < source.length; i += 1) {
      if (source[i] === "{") depth += 1;
      else if (source[i] === "}") {
        depth -= 1;
        if (depth === 0) break;
      }
    }
    chunks.push(source.slice(begin, i + 1));
  }
  chunks.push(
    "({normalizeRouteCoords, resolveRouteProgressIndex, resolveTaskProgressSequence," +
      " buildProviderRouteProgressSegments, buildProviderRouteProgressSegmentsByProgress," +
      " splitRouteCoordsIntoDrawableSegments," +
      " resolveVisualTaskProgressSequence, estimateProviderCoordDistanceMeters," +
      " findNearestProviderRouteIndex, hasActiveRouteProgress});",
  );
  const sandbox = {};
  vm.createContext(sandbox);
  return vm.runInContext(chunks.join("\n"), sandbox);
}

async function main() {
  const server = startProxy();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  const sandbox = createSandbox(port);
  const planFn = vm.runInContext(routeScript, sandbox);

  console.log("=== 1) 真实腾讯地图分段规划（串行限流） ===");
  const t0 = Date.now();
  const planned = await planFn([
    WAYPOINTS,
    KEY,
    { api_queue_interval_s: 0.2, api_retries: 2, api_retry_delay_s: 1.0 },
    "walking",
  ]);
  console.log(`耗时=${Date.now() - t0}ms`);
  if (!planned || planned.error) {
    console.log("规划失败:", planned && planned.error);
    await new Promise((r) => server.close(r));
    return;
  }
  console.log(`JS 规划点数=${planned.path.length}`);
  const { writeFileSync } = await import("node:fs");
  writeFileSync(
    new URL("../output/repro_planned_path.json", import.meta.url),
    JSON.stringify({ waypoints: WAYPOINTS, path: planned.path }, null, 0),
  );

  console.log("\n=== 2) 前端分段着色（在当前位置切开） ===");
  const fe = loadFrontendProgressModule();
  const targetPoints = TASK.target_points;
  const runCoords = planned.path.map((p) => ({ lng: p.lng, lat: p.lat }));

  let violations = 0;
  for (let runnerIndex = 1; runnerIndex < runCoords.length - 1; runnerIndex += 7) {
    // 找到一个不超过 runnerIndex 的打卡点作为「已过打卡点」
    let sequence = 1;
    for (let i = 0; i < targetPoints.length; i += 1) {
      const target = targetPoints[i];
      const matched = fe.findNearestProviderRouteIndex(
        runCoords,
        { lng: Number(target[0]), lat: Number(target[1]) },
        0,
      );
      if (matched >= 0 && matched <= runnerIndex) sequence = i + 1;
    }
    const data = {
      run_coords: runCoords,
      target_points: targetPoints,
      target_sequence: sequence,
      status: 0,
      current_point_index: runnerIndex + 1,
    };
    const segments = fe.buildProviderRouteProgressSegmentsByProgress(runCoords, data);
    if (!segments) {
      console.log(`  runner=${runnerIndex} -> 无分段`);
      continue;
    }
    const summary = segments.map((seg) => `${seg.styleId}(${seg.coords.length})`);
    const currentCount = segments.filter((s) => s.styleId === "current").length;
    if (currentCount > 1) violations += 1;
    console.log(
      `  runner=${String(runnerIndex).padStart(3)} seq=${sequence} -> ${summary.join(" | ")}` +
        (currentCount > 1 ? `   <== ${currentCount} 段同时为 current(蓝)` : ""),
    );
  }
  console.log(
    violations === 0
      ? "\n结论: 任一位置最多只有一个 current 段 ✔"
      : `\n结论: 发现 ${violations} 处多段同时为蓝 ✘`,
  );

  await new Promise((r) => server.close(r));
}

await main();
