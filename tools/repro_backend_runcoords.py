"""复现第二阶段：用真实规划路径生成 run_coords（走真实后端代码）。

用法: python tools/repro_backend_runcoords.py
输出: output/repro_run_coords.json
仅用于本地诊断，不属于运行时依赖。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PLANNED = ROOT / "output" / "repro_planned_path.json"
TASK = ROOT / "tests" / "fixtures" / "map_route_task_9points.json"
OUT = ROOT / "output" / "repro_run_coords.json"


class _RunStub:
    def __init__(self):
        self.run_coords = []
        self.total_run_time_s = 0.0
        self.total_run_distance_m = 0.0


class _Harness:
    """借用真实的 Api 方法，但不启动浏览器/网络。"""

    def __init__(self):
        from api_runtime import Api

        self._impl = Api.__new__(Api)
        self._impl.params = dict(getattr(Api, "_default_params", {}) or {})
        self._impl.all_run_data = [_RunStub()]
        self._impl.current_run_idx = 0
        self._impl.log = lambda *args, **kwargs: None

    def __getattr__(self, name):
        return getattr(self._impl, name)


def main():
    planned = json.loads(PLANNED.read_text(encoding="utf-8"))
    path = planned["path"]
    task = json.loads(TASK.read_text(encoding="utf-8"))

    from api_runtime import Api

    # 使用配置中的真实参数
    session = json.loads(
        (ROOT / "sessions" / "cc665bf6ec5f78ccc658024626e14357814bd3f62d4d15fad6f245cb02b867ed.json").read_text(
            encoding="utf-8"
        )
    )
    params = session["params"]

    # 直接从真实实现拷贝出所需方法
    runtime = Api.__new__(Api)
    runtime.params = params
    runtime.all_run_data = [_RunStub()]
    runtime.current_run_idx = 0
    runtime.log = lambda *args, **kwargs: None

    # _calculate_distance_m / _gps_random_offset / _get_path_for_distance 都是纯函数
    import random

    random.seed(20261010)

    dedup = []
    last = None
    for point in path:
        coord = (point["lng"], point["lat"])
        if coord != last:
            dedup.append(coord)
            last = coord

    cumulative = [0.0]
    for i in range(len(dedup) - 1):
        cumulative.append(
            cumulative[-1]
            + runtime._calculate_distance_m(
                dedup[i][0], dedup[i][1], dedup[i + 1][0], dedup[i + 1][1]
            )
        )
    print(f"规划路径去重后点数={len(dedup)} 总长={cumulative[-1]:.1f}m")

    min_dist_m = params.get("min_dist_m", 2000)
    target_dist_m = min_dist_m * 1.05
    final_geo = runtime._get_path_for_distance(dedup, cumulative, target_dist_m)
    print(f"补距后点数={len(final_geo)} 目标距离={target_dist_m:.1f}m")

    final_cumulative = [0.0]
    for i in range(len(final_geo) - 1):
        final_cumulative.append(
            final_cumulative[-1]
            + runtime._calculate_distance_m(
                final_geo[i][0], final_geo[i][1], final_geo[i + 1][0], final_geo[i + 1][1]
            )
        )
    total_dist = final_cumulative[-1]
    print(f"补距后总长={total_dist:.1f}m")

    target_time_s = params.get("min_time_m", 20) * 60 * 1.1
    avg_speed = total_dist / target_time_s
    run_coords = []
    start = final_geo[0]
    run_coords.append(runtime._gps_random_offset(start[0], start[1], params) + (0,))
    t_elapsed, d_covered = 0.0, 0.0
    while t_elapsed < target_time_s:
        interval = min(
            random.uniform(params["interval_ms"] * 0.9, params["interval_ms"] * 1.1) / 1000.0,
            target_time_s - t_elapsed,
        )
        if interval <= 0.1:
            break
        d_covered = min(
            d_covered + random.uniform(avg_speed * 0.9, avg_speed * 1.1) * interval,
            total_dist,
        )
        lon, lat = runtime._get_point_at_distance(final_geo, final_cumulative, d_covered)
        lon_o, lat_o = runtime._gps_random_offset(lon, lat, params)
        run_coords.append((lon_o, lat_o, int(interval * 1000)))
        t_elapsed += interval
        if d_covered >= total_dist:
            break

    print(f"run_coords 点数={len(run_coords)} 实际距离={d_covered:.1f}m 时长={t_elapsed:.1f}s")

    OUT.write_text(
        json.dumps(
            {
                "waypoints": planned["waypoints"],
                "target_points": task["target_points"],
                "target_point_names": task["target_point_names"],
                "planned_path": path,
                "run_coords": run_coords,
                "total_dist": d_covered,
                "total_time": t_elapsed,
                "params": params,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"已写入 {OUT}")


if __name__ == "__main__":
    main()
