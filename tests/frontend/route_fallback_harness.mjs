/**
 * 在受控的地图服务桩上真实执行 provider 路径规划 JS，
 * 用于验证「规划失败时使用直线连接」(api_fallback_line) 是否真的生效。
 *
 * 用法:
 *   node route_fallback_harness.mjs <jsPath> <provider> <scenarioJsonPath>
 *
 * 场景 JSON:
 *   {
 *     "arg": [...],                 // 传给 JS 的 execute_js 实参数组
 *     "failSegments": [0, 2],       // 需要"规划失败"的段索引（0 基）
 *     "rateLimitedSegments": [1],   // 需要"被限流"的段索引
 *     "waypointKey": "lng"          // 用起点 lng 反查段索引的映射
 *   }
 *
 * 输出: stdout 单行 JSON
 *   {"ok":true,"result":{...},"searchCallCount":N,"failedDetail":[...]}
 */

import { readFileSync } from "node:fs";

const [, , jsPath, provider, scenarioPath] = process.argv;
if (!jsPath || !provider || !scenarioPath) {
  console.log(JSON.stringify({ ok: false, error: "参数不足" }));
  process.exit(2);
}

const scenario = JSON.parse(readFileSync(scenarioPath, "utf-8"));
const failSegments = new Set(scenario.failSegments || []);
const rateLimitedSegments = new Set(scenario.rateLimitedSegments || []);
const failSet = new Set(scenario.failByStartLng || []);
let searchCallCount = 0;
/** 每次 search 的记录：{index, failed, rateLimited}，便于校验重试预算 */
const searchLog = [];

// 段索引：用起点经度在 waypoints 里的位置反查
const waypoints = (scenario.arg && scenario.arg[0]) || [];
function segmentIndexFromStartLng(lng) {
  const value = Number(lng);
  for (let i = 0; i < waypoints.length - 1; i += 1) {
    if (Number(waypoints[i][0]) === value) return i;
  }
  return -1;
}

function isFailed(index) {
  return index >= 0 && failSegments.has(index);
}
function isRateLimited(index) {
  return index >= 0 && rateLimitedSegments.has(index);
}

/** 生成 start→end 的中间点，便于区分"真实路线"与"两点直线兜底" */
function makeRoutePoints(startLng, startLat, endLng, endLat, mid = 2) {
  const out = [];
  for (let i = 0; i <= mid + 1; i += 1) {
    const t = i / (mid + 1);
    out.push({
      lng: Number(startLng) + (Number(endLng) - Number(startLng)) * t,
      lat: Number(startLat) + (Number(endLat) - Number(startLat)) * t,
    });
  }
  return out;
}

// ── 浏览器环境桩 ────────────────────────────────────────────
globalThis.window = globalThis;
/**
 * 定时器桩：必须区分「退避重试」与「单次请求超时」。
 *
 * JS 里两种用法都存在：
 *   window.setTimeout(runOnce, backoff + jitter)  ← 重试退避，最多 5s，必须真的执行
 *   window.setTimeout(..., 15000)                 ← 单次请求超时，绝不能在 search 回调前触发
 *
 * 处理方式：
 *   延迟 >= REQUEST_TIMEOUT_MS 视为超时计时器 -> 永不触发（交给 search 回调 settle）；
 *   其余延迟 -> 用 setImmediate 立即调度（保留异步语义，同时不让测试变慢）。
 *
 * 若把两者都立即执行，超时回调会抢先 settle，真实的地图错误就永远看不到；
 * 若把两者都不执行，限流退避后的重试就永远不会发生，测试会挂住。
 */
const REQUEST_TIMEOUT_MS = 15000;
globalThis.setTimeout = (fn, delay = 0) => {
  const ms = Number(delay) || 0;
  if (ms >= REQUEST_TIMEOUT_MS) {
    // 请求超时计时器：故意不触发
    return 0;
  }
  setImmediate(fn);
  return 0;
};
globalThis.clearTimeout = () => {};
globalThis.document = {
  querySelector: () => null,
  getElementById: () => null,
  createElement: () => ({
    dataset: {},
    style: {},
    setAttribute() {},
    appendChild() {},
    remove() {},
  }),
  head: { appendChild() {} },
  body: { appendChild() {} },
};

let jsonpSeq = 0;
function fakeJsonp(url, onSuccess, onError) {
  searchCallCount += 1;
  const startLng = Number((String(url).match(/from=([\d.]+)/) || [])[1]);
  const index = segmentIndexFromStartLng(startLng);
  if (isFailed(index) || isRateLimited(index)) {
    const status = isRateLimited(index) ? 120 : 0;
    if (onSuccess) {
      onSuccess({ status, message: status === 120 ? "此key每秒请求量已达到上限" : "no route" });
    }
    return;
  }
  const points = makeRoutePoints(startLng, 0, startLng, 0, 0);
  if (onSuccess) onSuccess({ status: 0, result: { routes: [{ polyline: "" }] } });
}

// ── AMap 桩 ────────────────────────────────────────────────
class FakeLngLat {
  constructor(lng, lat) {
    this.lng = Number(lng);
    this.lat = Number(lat);
  }
  getLng() {
    return this.lng;
  }
  getLat() {
    return this.lat;
  }
}
function makeAmapService() {
  // 限流是"可恢复"的：真实服务重试若干次后会成功。
  // 若桩一直返回限流，JS 会无限退避重试（其设计就是限流不消耗重试预算），
  // 测试会挂住。这里在第 N 次之后转为成功，用于验证"限流不计入重试预算"。
  const rateLimitCounts = new Map();
  const rateLimitUntilAttempt = scenario.rateLimitUntilAttempt ?? 3;

  return function Service() {
    this.search = (start, end, cb) => {
      searchCallCount += 1;
      const index = segmentIndexFromStartLng(start.lng ?? start.getLng?.());
      const isRlSegment = isRateLimited(index);

      if (isRlSegment) {
        const seen = (rateLimitCounts.get(index) || 0) + 1;
        rateLimitCounts.set(index, seen);
        searchLog.push({
          provider: "amap",
          startLng: start.lng ?? start.getLng?.(),
          segmentIndex: index,
          failed: false,
          rateLimited: seen <= rateLimitUntilAttempt,
          recoverAfter: rateLimitUntilAttempt,
        });
        if (seen <= rateLimitUntilAttempt) {
          cb("error", { info: "CUQPS_HAS_EXCEEDED_THE_LIMIT" });
          return;
        }
        cb("complete", {
          routes: [
            {
              steps: [
                { path: makeRoutePoints(start.lng, start.lat, end.lng, end.lat) },
              ],
            },
          ],
        });
        return;
      }

      searchLog.push({
        provider: "amap",
        startLng: start.lng ?? start.getLng?.(),
        segmentIndex: index,
        failed: isFailed(index),
        rateLimited: false,
      });
      if (isFailed(index)) {
        cb("error", { info: "NO_ROADS_NEARBY" });
        return;
      }
      cb("complete", {
        routes: [
          {
            steps: [
              { path: makeRoutePoints(start.lng, start.lat, end.lng, end.lat) },
            ],
          },
        ],
      });
    };
  };
}
globalThis.AMap = {
  LngLat: FakeLngLat,
  Walking: makeAmapService(),
  Driving: makeAmapService(),
};
globalThis.AMapLoader = { load: async () => globalThis.AMap };

// ── 天地图桩 ──────────────────────────────────────────────
function makeTdtService() {
  return function Service() {
    this.search = (start, end, cb) => {
      searchCallCount += 1;
      const index = segmentIndexFromStartLng(start.getLng?.() ?? start.lng);
      if (isFailed(index)) {
        cb({ status: 1, message: "no route" });
        return;
      }
      cb({
        status: 0,
        result: {
          routes: [
            {
              steps: [
                {
                  path: makeRoutePoints(
                    start.getLng(),
                    start.getLat(),
                    end.getLng(),
                    end.getLat(),
                  ),
                },
              ],
            },
          ],
        },
        getRoute: () => 0,
      });
    };
    this.clearResults = () => {};
    this.setPolicy = () => {};
  };
}
globalThis.T = {
  LngLat: FakeLngLat,
  Map: function Map() {},
  NavigationControl: function NavigationControl() {},
  Walking: makeTdtService(),
  Driving: makeTdtService(),
};

// ── 百度桩 ────────────────────────────────────────────────
function makeBaiduService() {
  return function Service() {
    this.search = (start, end, cb) => {
      searchCallCount += 1;
      const index = segmentIndexFromStartLng(start.lng ?? start.getLng?.());
      if (isFailed(index)) {
        cb({ status: 1, message: "no route" });
        return;
      }
      cb({
        status: 0,
        getRoute: () => 0,
        getNumPlans: () => 1,
        getPlan: () => ({
          getNumRoutes: () => 1,
          getRoute: () => ({
            getNumSteps: () => 1,
            getStep: () => ({
              getNumPoints: () => 2,
              getPoint: (i) => new (globalThis.BMap.Point)(i === 0 ? start.lng : end.lng, i === 0 ? start.lat : end.lat),
            }),
            getPath: () => [
              new globalThis.BMap.Point(start.lng, start.lat),
              new globalThis.BMap.Point(end.lng, end.lat),
            ],
          }),
        }),
      });
    };
    this.clearResults = () => {};
    this.setPolylinesSetCallback = () => {};
    this.setMarkersSetCallback = () => {};
  };
}
globalThis.BMap = {
  Point: FakeLngLat,
  WalkingRoute: makeBaiduService(),
  DrivingRoute: makeBaiduService(),
  Geocoder: function Geocoder() {},
  Map: function Map() {},
};

// ── fetch 桩（腾讯走 JSONP，这里兼容可能的 fetch 用法）────────
globalThis.fetch = async () => ({
  ok: true,
  status: 200,
  text: async () => "callback&&callback({\"status\":0});",
  json: async () => ({ status: 0 }),
});

// ── 载入真实 JS 并执行 ─────────────────────────────────────
const source = readFileSync(jsPath, "utf-8");
let fn;
try {
  fn = new Function(`return (${source});`)();
} catch (err) {
  console.log(JSON.stringify({ ok: false, error: `JS 求值失败: ${err.message}` }));
  process.exit(0);
}
if (typeof fn !== "function") {
  console.log(JSON.stringify({ ok: false, error: "JS 未返回函数" }));
  process.exit(0);
}

try {
  const result = await fn(scenario.arg);
  console.log(
    JSON.stringify({
      ok: true,
      result,
      searchCallCount,
      searchLog,
      provider,
    }),
  );
} catch (err) {
  console.log(JSON.stringify({ ok: false, error: `执行异常: ${err.message}` }));
}
