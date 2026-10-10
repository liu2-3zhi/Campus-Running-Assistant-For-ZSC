"""诊断脚本：定位 _get_path_for_distance 实际从路线何处开始折返。

用法: python tools/diag_retrace_point.py
仅用于本地诊断，不属于运行时依赖。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PLANNED = ROOT / "output" / "repro_planned_path.json"
TASK = ROOT / "tests" / "fixtures" / "map_route_task_9points.json"


def cumulative_of(runtime, path):
    cum = [0.0]
    for i in range(len(path) - 1):
        cum.append(
            cum[-1]
            + runtime._calculate_distance_m(
                path[i][0], path[i][1], path[i + 1][0], path[i + 1][1]
            )
        )
    return cum


def nearest_index(runtime, path, point):
    best_i, best_d = -1, float("inf")
    for i, p in enumerate(path):
        d = runtime._calculate_distance_m(point[0], point[1], p[0], p[1])
        if d < best_d:
            best_i, best_d = i, d
    return best_i, best_d


def main():
    from api_runtime import Api

    rt = Api.__new__(Api)
    planned = json.loads(PLANNED.read_text(encoding="utf-8"))
    task = json.loads(TASK.read_text(encoding="utf-8"))
    base = [(p["lng"], p["lat"]) for p in planned["path"]]
    waypoints = [(float(p[0]), float(p[1])) for p in task["target_points"]]

    cum = cumulative_of(rt, base)
    total = cum[-1]
    dest = waypoints[-1]
    print(f"主路线: {len(base)} 点, 总长 {total:.1f} m")
    print(f"最后一个打卡点 {dest} 在路线上的位置: "
          f"索引 {nearest_index(rt, base, dest)[0]} / {len(base) - 1}, "
          f"距终点 {nearest_index(rt, base, dest)[1]:.2f} m")

    for target in (total + 50, total + 300, total + 900):
        out = rt._get_path_for_distance(base, cum, target)
        out_cum = cumulative_of(rt, out)
        # 找到折返起点：输出路径中第一个「与前一点的道路距离方向反转」的点
        # 用更朴素的办法：定位输出中首次离开 base 尾段的位置
        near_d = max(0.0, total - 50.0) if total >= 100 else total * 2 / 3
        far_d = max(0.0, total - 100.0) if total >= 100 else total / 3
        cut_distance = near_d
        # 输出路径中，第一次沿 base 前进到 cut_distance 的索引
        print(f"\n--- target={target:.0f} (+{target - total:.0f}m) ---")
        print(f"  截断点 near_d = {near_d:.1f} m（距终点 {total - near_d:.1f} m）")
        print(f"  折返区间 far_d = {far_d:.1f} m（长 {near_d - far_d:.1f} m）")
        print(f"  输出点数={len(out)} 输出长度={out_cum[-1]:.1f} m")
        # 判断输出前缀是否等于完整主路线（即是否先走完整条主路线）
        prefix_ok = len(out) >= len(base) and all(
            abs(out[i][0] - base[i][0]) < 1e-12 and abs(out[i][1] - base[i][1]) < 1e-12
            for i in range(len(base))
        )
        print(f"  输出前缀 == 完整主路线 ? {prefix_ok}")

        # 统计沿主路线的里程投影方向反转次数（折返次数）
        projected = []
        for pt in out:
            idx, dist = nearest_index(rt, base, pt)
            if dist <= 30:
                projected.append(cum[idx])
        turnarounds = 0
        last_dir = 0
        for i in range(1, len(projected)):
            diff = projected[i] - projected[i - 1]
            if abs(diff) < 1e-9:
                continue
            direction = 1 if diff > 0 else -1
            if last_dir != 0 and direction != last_dir:
                turnarounds += 1
            last_dir = direction
        print(f"  沿主路线的行进方向反转次数 = {turnarounds}")
        print(f"  输出最后一点 = {out[-1]}")
        print(f"  与最后一个打卡点距离 = {nearest_index(rt, [out[-1]], dest)[1]:.2f} m")


if __name__ == "__main__":
    main()
