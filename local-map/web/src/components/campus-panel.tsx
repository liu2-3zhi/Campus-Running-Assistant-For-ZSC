import { useEffect, useState } from 'react';
import { Button } from './ui/button';
import { useDirectionsStore } from '@/stores/directions-store';
import { useRouteDebugStore } from '@/stores/route-debug-store';
import {
  useDirectionsQuery,
  useSetWaypointFromCoords,
} from '@/hooks/use-directions-queries';

type Coordinate = [number, number];
interface Example {
  id?: string;
  name: string;
  description?: string;
  start: Coordinate;
  end: Coordinate;
  waypoints?: Coordinate[];
}
interface CampusInfo {
  name?: string;
  version?: string;
  examples?: Example[];
  reference_route?: Example;
  layers?: { footpaths?: { count?: number } };
  coverage?: { notes?: string[]; warnings?: string[] };
}

export function CampusPanel() {
  const [info, setInfo] = useState<CampusInfo | null>(null);
  const [error, setError] = useState('');
  const { setWaypointFromCoords } = useSetWaypointFromCoords();
  const { refetch } = useDirectionsQuery();
  const referenceRoute = info?.reference_route;
  const referencePointCount = referenceRoute
    ? (referenceRoute.waypoints?.length ?? 0) + 2
    : 0;
  const supplementaryPaths = info?.layers?.footpaths?.count ?? 0;

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/v1/map', { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok)
          throw new Error(`地图信息请求失败：HTTP ${response.status}`);
        const data = await response.json();
        setInfo(data.manifest ?? data);
      })
      .catch((reason) => {
        if (!controller.signal.aborted)
          setError(String(reason.message ?? reason));
      });
    return () => controller.abort();
  }, []);

  const loadExample = async (example: Example) => {
    const store = useDirectionsStore.getState();
    store.clearWaypoints();
    store.clearRoutes();
    const points = [example.start, ...(example.waypoints ?? []), example.end];
    for (const [index, point] of points.entries()) {
      await setWaypointFromCoords(point[0], point[1], index, {
        isPermalink: true,
      });
    }
    await refetch();
  };

  return (
    <section
      className="rounded-md border p-2 text-sm flex flex-col gap-2"
      aria-label="校园地图信息"
    >
      <p className="font-semibold">
        {info?.name ?? '校园离线地图'}{' '}
        <span className="text-xs font-normal text-muted-foreground">
          GCJ-02
        </span>
      </p>
      <p className="text-xs text-muted-foreground">
        底图与路线统一使用 GCJ-02（火星坐标）。步行路网采用已收录的 OSM 道路
        {supplementaryPaths > 0 ? '及高德步行补充路段' : ''}
        ，路线仅供步行参考，请遵守现场通行条件。
      </p>
      {supplementaryPaths > 0 && (
        <p
          className="text-xs text-muted-foreground"
          data-testid="supplementary-paths"
        >
          高德步行补充路段 {supplementaryPaths}{' '}
          条，以橙色细线显示；这些是参考点周边已收集的路段，并非全校园完整小路网。
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        内部步道与建筑入口未完整收录；吸附点只是已收录道路上的点，不能视为建筑入口。
      </p>
      {[...(info?.coverage?.notes ?? []), ...(info?.coverage?.warnings ?? [])]
        .filter((note) => typeof note === 'string')
        .map((note, index) => (
          <p key={index} className="text-xs text-muted-foreground">
            {note}
          </p>
        ))}
      <p className="text-xs text-muted-foreground">
        定位不可用时，可继续点击地图或手动输入 GCJ-02
        坐标。地图选点与输入坐标直接使用，GPS 定位自动转换为火星坐标。
      </p>
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
      {info?.examples?.map((example, index) => (
        <Button
          key={example.id ?? index}
          variant="outline"
          className="h-auto min-h-9 whitespace-normal justify-start text-left"
          onClick={() => loadExample(example)}
          data-testid={`example-route-${index}`}
          title={example.description}
        >
          {example.name}
        </Button>
      ))}
      {referenceRoute && (
        <Button
          variant="outline"
          className="h-auto min-h-9 whitespace-normal justify-start text-left"
          onClick={() => loadExample(referenceRoute)}
          data-testid="reference-route"
          title={referenceRoute.description ?? referenceRoute.name}
        >
          加载{referencePointCount}个参考点
        </Button>
      )}
      <a
        href="/docs"
        target="_blank"
        rel="noreferrer"
        className="text-xs underline underline-offset-2"
      >
        本地 API 文档
      </a>
    </section>
  );
}

export function RouteDebugPanel() {
  const trace = useRouteDebugStore();
  return (
    <details
      className="rounded-md border p-2 min-w-0"
      data-testid="route-debug-panel"
    >
      <summary className="cursor-pointer text-sm font-semibold">
        路由调试 · {trace.status}
        {trace.elapsedMs !== null ? ` · ${trace.elapsedMs} ms` : ''}
      </summary>
      <div className="mt-2 flex flex-col gap-2 text-xs">
        <p>GET /valhalla/route · pedestrian · GCJ-02 经度在前</p>
        {trace.error && (
          <p
            className="text-destructive break-words"
            role="alert"
            data-testid="route-error"
          >
            {trace.error}
          </p>
        )}
        <p className="font-semibold">实际请求 JSON</p>
        <pre
          className="max-h-60 overflow-auto whitespace-pre-wrap break-all bg-muted p-2"
          data-testid="route-request"
        >
          {JSON.stringify(trace.request, null, 2)}
        </pre>
        <p className="font-semibold">实际响应 JSON</p>
        <pre
          className="max-h-80 overflow-auto whitespace-pre-wrap break-all bg-muted p-2"
          data-testid="route-response"
        >
          {JSON.stringify(trace.response, null, 2)}
        </pre>
      </div>
    </details>
  );
}
