/** 前端分段着色回归测试。
 *
 * 期望（用户明确要求）：
 * - 灰色 completed：起点 -> 最近已过打卡点，以及该点 -> 当前位置；
 * - 蓝色 current  ：当前位置 -> 下一个打卡点；
 * - 红色 active   ：其余待执行路段。
 *
 * 历史缺陷：整段「上一打卡点 -> 下一打卡点」都是蓝色，已跑过的一半不变灰。
 *
 * 用法: node tests/frontend/test_map_route_progress_segments.mjs
 */

import assert from "node:assert/strict";
import vm from "node:vm";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");

function loadFrontendProgressModule() {
  const source = readFileSync(
    path.join(ROOT, "scripts", "legacy-map-render.js"),
    "utf8",
  );
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
  ];
  const chunks = [];
  for (const name of needed) {
    const match = new RegExp(`^function ${name}\\(`, "m").exec(source);
    assert.ok(match, `未找到函数 ${name}`);
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
    "({buildProviderRouteProgressSegmentsByProgress, resolveRouteProgressIndex," +
      " resolveTaskProgressSequence, findNearestProviderRouteIndex});",
  );
  const sandbox = {};
  vm.createContext(sandbox);
  return vm.runInContext(chunks.join("\n"), sandbox);
}

/** 构造一条 0.0001 度步进的直线路线（约 10 m/点） */
function makeRoute(points) {
  return points;
}

const fe = loadFrontendProgressModule();

const ROUTE = makeRoute(
  Array.from({ length: 100 }, (_, i) => ({
    lng: 113.39 + i * 0.0001,
    lat: 22.53,
  })),
);
const TARGET_POINTS = [
  [ROUTE[0].lng, ROUTE[0].lat],
  [ROUTE[20].lng, ROUTE[20].lat],
  [ROUTE[60].lng, ROUTE[60].lat],
  [ROUTE[99].lng, ROUTE[99].lat],
];

let failures = 0;
function check(name, fn) {
  try {
    fn();
    console.log(`  ok   ${name}`);
  } catch (err) {
    failures += 1;
    console.log(`  FAIL ${name}\n       ${err.message}`);
  }
}

console.log("分段着色（在当前位置切开）");

check("runner 位于 2 号与 3 号打卡点之间时正确分为灰/蓝/红", () => {
  const data = {
    run_coords: ROUTE,
    target_points: TARGET_POINTS,
    target_sequence: 2,
    status: 0,
    current_point_index: 41,
  };
  const segments = fe.buildProviderRouteProgressSegmentsByProgress(ROUTE, data);
  assert.ok(Array.isArray(segments) && segments.length > 0, "应返回分段");

  const byStyle = (styleId) => segments.filter((s) => s.styleId === styleId);
  const current = byStyle("current");
  const completed = byStyle("completed");
  const active = byStyle("active");

  assert.equal(current.length, 1, `current 段应恰好 1 个，实际 ${current.length}`);
  assert.ok(completed.length >= 1, "应有 completed 段");
  assert.ok(active.length >= 1, "应有 active 段");

  // 灰色必须覆盖到当前位置，蓝色从当前位置开始
  const runnerIndex = fe.resolveRouteProgressIndex({
    ...data,
  }, ROUTE);
  const currentStart = current[0].coords[0];
  assert.ok(
    Math.abs(currentStart.lng - ROUTE[runnerIndex].lng) < 1e-9,
    `蓝色段起点应等于当前位置 idx=${runnerIndex}`,
  );
  const completedTail = completed[completed.length - 1].coords;
  assert.ok(
    Math.abs(completedTail[completedTail.length - 1].lng - ROUTE[runnerIndex].lng) < 1e-9,
    "灰色段应一直覆盖到当前位置",
  );

  // 蓝色段终点应等于下一个打卡点（3 号 → 索引 60）
  const currentTail = current[0].coords[current[0].coords.length - 1];
  assert.ok(
    Math.abs(currentTail.lng - ROUTE[60].lng) < 1e-9,
    `蓝色段终点应为下一个打卡点，实际 ${currentTail.lng}`,
  );
  // 红色段从下一个打卡点开始
  const activeHead = active[0].coords[0];
  assert.ok(
    Math.abs(activeHead.lng - ROUTE[60].lng) < 1e-9,
    "红色段应从一个打卡点之后开始",
  );
});

check("任一推进位置最多只有一个 current 段", () => {
  for (let index = 1; index < ROUTE.length - 1; index += 1) {
    const data = {
      run_coords: ROUTE,
      target_points: TARGET_POINTS,
      target_sequence: index < 20 ? 1 : index < 60 ? 2 : 3,
      status: 0,
      current_point_index: index + 1,
    };
    const segments = fe.buildProviderRouteProgressSegmentsByProgress(ROUTE, data);
    assert.ok(Array.isArray(segments), `idx=${index} 应返回分段`);
    const currentCount = segments.filter((s) => s.styleId === "current").length;
    // 恰好停在打卡点上时蓝色段消失（该腿已走完），因此允许 0
    assert.ok(
      currentCount === 1 || currentCount === 0,
      `idx=${index} 的 current 段数量应为 0 或 1，实际 ${currentCount}`,
    );
    // 灰色必须覆盖到当前位置
    const completed = segments.filter((s) => s.styleId === "completed");
    const completedLast = completed[completed.length - 1];
    assert.ok(completedLast, `idx=${index} 应有 completed 段`);
    const tail = completedLast.coords[completedLast.coords.length - 1];
    assert.ok(
      Math.abs(tail.lng - ROUTE[index].lng) < 1e-9,
      `idx=${index} 灰色段应覆盖到当前位置`,
    );
  }
});

check("同一路线点不同时出现在蓝段与红段内部", () => {
  const data = {
    run_coords: ROUTE,
    target_points: TARGET_POINTS,
    target_sequence: 2,
    status: 0,
    current_point_index: 41,
  };
  const segments = fe.buildProviderRouteProgressSegmentsByProgress(ROUTE, data);
  const current = segments.find((s) => s.styleId === "current");
  const active = segments.find((s) => s.styleId === "active");
  assert.ok(current && active, "应同时存在蓝段与红段");
  const activeKeys = new Set(
    active.coords.map((c) => `${c.lng.toFixed(7)},${c.lat.toFixed(7)}`),
  );
  // 相邻段共享边界点是允许的，但蓝段内部点不得出现在红段里
  current.coords.slice(0, -1).forEach((coord) => {
    const key = `${coord.lng.toFixed(7)},${coord.lat.toFixed(7)}`;
    assert.ok(!activeKeys.has(key), `蓝段内部点 ${key} 不应出现在红段`);
  });
});

check("缺少定位信息时回退到原有行为", () => {
  const data = {
    run_coords: ROUTE,
    target_points: TARGET_POINTS,
    target_sequence: 2,
    status: 0,
  };
  const segments = fe.buildProviderRouteProgressSegmentsByProgress(ROUTE, data);
  assert.ok(Array.isArray(segments) && segments.length > 0, "应返回分段");
  const currentCount = segments.filter((s) => s.styleId === "current").length;
  assert.equal(currentCount, 1, "回退路径仍应只有一个 current 段");
});

check("任务完成时整条路线都是灰色", () => {
  const data = {
    run_coords: ROUTE,
    target_points: TARGET_POINTS,
    target_sequence: TARGET_POINTS.length,
    status: 1,
    current_point_index: ROUTE.length,
  };
  const segments = fe.buildProviderRouteProgressSegmentsByProgress(ROUTE, data);
  assert.ok(Array.isArray(segments) && segments.length > 0, "应返回分段");
  assert.equal(
    segments[0].styleId,
    "completed",
    "完成后首段应为 completed",
  );
  assert.equal(
    segments.filter((s) => s.styleId !== "completed").length,
    0,
    "完成后不应还有非 completed 段",
  );
});

if (failures > 0) {
  console.error(`\n${failures} 项失败`);
  process.exit(1);
}
console.log("\n全部分段着色用例通过");
