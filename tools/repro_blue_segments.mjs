/**
 * 临时复现脚本：用真实 run_coords 逐点推进，模拟前端分段着色，
 * 复现“多段同时变蓝（下一段线路）”缺陷。
 *
 * 用法: node tools/repro_blue_segments.mjs
 * 依赖: output/repro_run_coords.json (由 tools/repro_backend_runcoords.py 生成)
 * 仅用于本地诊断，不属于运行时依赖。
 */
import vm from "node:vm";
import { readFileSync } from "node:fs";

const ROOT = new URL("../", import.meta.url);
const DATA = JSON.parse(readFileSync(new URL("output/repro_run_coords.json", ROOT), "utf8"));
const RUN_COORDS = DATA.run_coords.map(([lng, lat, ms]) => ({ lng, lat, ms }));
const TARGET_POINTS = DATA.target_points;

/** 加载真实前端 legacy-map-render.js 中的进度分段函数 */
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
  ];
  const chunks = [];
  for (const name of needed) {
    const match = new RegExp(`^function ${name}\\(`, "m").exec(source);
    if (!match) throw new Error(`未找到函数 ${name}`);
    let depth = 0;
    let i = source.indexOf("{", match.index);
    for (; i < source.length; i += 1) {
      if (source[i] === "{") depth += 1;
      else if (source[i] === "}") {
        depth -= 1;
        if (depth === 0) break;
      }
    }
    chunks.push(source.slice(match.index, i + 1));
  }
  chunks.push(
    "({resolveRouteProgressIndex, resolveTaskProgressSequence," +
      " buildProviderRouteProgressSegments, getProviderRouteProgressStatus," +
      " resolveVisualTaskProgressSequence, findNearestProviderRouteIndex});",
  );
  const sandbox = {};
  vm.createContext(sandbox);
  return vm.runInContext(chunks.join("\n"), sandbox);
}

/** 复刻 main.js 的 resolveRunnerTargetSequence */
function resolveRunnerTargetSequence(targetSequence, data, fe) {
  const incoming = Number.isFinite(+targetSequence) ? Math.floor(+targetSequence) + 1 : 1;
  const existing = Number.isFinite(+data?.target_sequence) ? Math.floor(+data.target_sequence) : 0;
  const merged = Math.max(incoming, existing || incoming);
  const sequenceData = { ...data, target_sequence: merged };
  return fe.resolveTaskProgressSequence(sequenceData, sequenceData.run_coords || []);
}

function distanceM(a, b) {
  return Math.hypot(
    (a.lng - b.lng) * Math.cos((a.lat * Math.PI) / 180) * 111320,
    (a.lat - b.lat) * 110540,
  );
}

const fe = loadFrontendProgressModule();

// ---- 场景 A: 后端 updateRunnerPosition 只下发 targetSequence（无 current_point_index） ----
console.log("=== 场景 A: 仅下发 target_sequence（模拟 SocketIO 推送） ===");
let data = {
  run_coords: RUN_COORDS,
  target_points: TARGET_POINTS,
  target_sequence: 0,
  status: 0,
};
let prevSequence = 0;
let nextTargetIndex = 1;
const anomalies = [];

for (let i = 0; i < RUN_COORDS.length; i += 1) {
  const point = RUN_COORDS[i];
  const prevProgressIndex = fe.resolveRouteProgressIndex(data, data.run_coords);
  data.current_position = { lng: point.lng, lat: point.lat };
  // 真实后端按“到达打卡点”推进 target_sequence
  const sequence = resolveRunnerTargetSequence(prevSequence, data, fe);
  const nextProgressIndex = fe.resolveRouteProgressIndex(data, data.run_coords);
  data.target_sequence = sequence;

  // 每 5 个点采样一次检查
  if (i % 5 !== 0 && sequence === prevSequence && nextProgressIndex === prevProgressIndex) continue;
  prevSequence = sequence;

  const segments = fe.buildProviderRouteProgressSegments(RUN_COORDS, data);
  const currentSegs = (segments || []).filter((s) => s.styleId === "current");
  const currentPointCount = currentSegs.reduce((acc, s) => acc + s.coords.length, 0);
  let currentLength = 0;
  for (const seg of currentSegs) {
    for (let k = 0; k < seg.coords.length - 1; k += 1) {
      currentLength += distanceM(seg.coords[k], seg.coords[k + 1]);
    }
  }
  // 蓝色段起点/终点在路线上的索引
  const idxOf = (coord) =>
    RUN_COORDS.findIndex(
      (p) => Math.abs(p.lng - coord.lng) < 1e-9 && Math.abs(p.lat - coord.lat) < 1e-9,
    );
  const spans = currentSegs.map((s) => `${idxOf(s.coords[0])}..${idxOf(s.coords[s.coords.length - 1])}`);

  if (currentLength > 400 || currentSegs.length > 1) {
    anomalies.push({
      i,
      sequence,
      progressIndex: nextProgressIndex,
      segs: currentSegs.length,
      points: currentPointCount,
      length: currentLength,
      spans,
    });
  }
}

console.log(`检测到 ${anomalies.length} 次异常着色（蓝色段过长或数量 > 1）`);
anomalies.slice(0, 15).forEach((a) => {
  console.log(
    `  i=${String(a.i).padStart(3)} seq=${a.sequence} progressIdx=${a.progressIndex} ` +
      `current段数=${a.segs} 点数=${a.points} 长度=${a.length.toFixed(0)}m 路线索引区间=${a.spans.join(",")}`,
  );
});

// ---- 场景 B: 后端同时下发 current_point_index（真实运行路径） ----
console.log("\n=== 场景 B: 同时下发 current_point_index（真实运行路径） ===");
data = { run_coords: RUN_COORDS, target_points: TARGET_POINTS, target_sequence: 0, status: 0 };
prevSequence = 0;
const anomaliesB = [];
for (let i = 0; i < RUN_COORDS.length; i += 1) {
  const point = RUN_COORDS[i];
  data.current_position = { lng: point.lng, lat: point.lat };
  data.current_point_index = i + 1;
  const sequence = resolveRunnerTargetSequence(prevSequence, data, fe);
  data.target_sequence = sequence;
  if (i % 10 !== 0 && sequence === prevSequence) continue;
  prevSequence = sequence;

  const segments = fe.buildProviderRouteProgressSegments(RUN_COORDS, data);
  const currentSegs = (segments || []).filter((s) => s.styleId === "current");
  let currentLength = 0;
  for (const seg of currentSegs) {
    for (let k = 0; k < seg.coords.length - 1; k += 1) {
      currentLength += distanceM(seg.coords[k], seg.coords[k + 1]);
    }
  }
  const idxOf = (coord) =>
    RUN_COORDS.findIndex(
      (p) => Math.abs(p.lng - coord.lng) < 1e-9 && Math.abs(p.lat - coord.lat) < 1e-9,
    );
  if (currentLength > 400) {
    anomaliesB.push({
      i,
      sequence,
      segs: currentSegs.length,
      length: currentLength,
      span: currentSegs
        .map((s) => `${idxOf(s.coords[0])}..${idxOf(s.coords[s.coords.length - 1])}`)
        .join(","),
    });
  }
}
console.log(`检测到 ${anomaliesB.length} 次蓝色段超过 400m`);
anomaliesB.slice(0, 15).forEach((a) => {
  console.log(
    `  i=${String(a.i).padStart(3)} seq=${a.sequence} current段数=${a.segs} ` +
      `长度=${a.length.toFixed(0)}m 区间=${a.span}`,
  );
});

// ---- 场景 C: 直接检查 target_points 在路线上的匹配索引 ----
console.log("\n=== 场景 C: 打卡点在 run_coords 上的匹配索引 ===");
let minIdx = 0;
const matched = [];
TARGET_POINTS.forEach((point, index) => {
  const coord = { lng: Number(point[0]), lat: Number(point[1]) };
  const routeIndex = fe.findNearestProviderRouteIndex(RUN_COORDS, coord, minIdx);
  matched.push(routeIndex);
  if (routeIndex >= 0) minIdx = routeIndex;
  console.log(
    `  打卡点${index + 1} ${coord.lng},${coord.lat} -> 路线索引 ${routeIndex}` +
      (routeIndex < 0 ? "  <== 未匹配" : ""),
  );
});
console.log("  匹配索引序列:", matched.join(" -> "));
