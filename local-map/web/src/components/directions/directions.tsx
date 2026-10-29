import { Waypoints } from './waypoints/waypoint-list';
import { Button } from '@/components/ui/button';
import { MapPinPlus, MapPinXInside, Route } from 'lucide-react';
import { RouteCard } from './route-card';
import { useDirectionsStore } from '@/stores/directions-store';
import { useCommonStore } from '@/stores/common-store';
import { useDirectionsQuery } from '@/hooks/use-directions-queries';

export const DirectionsControl = () => {
  const waypoints = useDirectionsStore((state) => state.waypoints);
  const results = useDirectionsStore((state) => state.results);
  const addEmptyWaypointToEnd = useDirectionsStore(
    (state) => state.addEmptyWaypointToEnd
  );
  const clearWaypoints = useDirectionsStore((state) => state.clearWaypoints);
  const clearRoutes = useDirectionsStore((state) => state.clearRoutes);
  const loading = useCommonStore((state) => state.loading);
  const { refetch } = useDirectionsQuery();
  const activeCount = waypoints.filter((wp) =>
    wp.geocodeResults.some((r) => r.selected)
  ).length;

  return (
    <>
      <p className="text-xs text-muted-foreground">
        点击地图设置起点、终点或途经点；拖动标记或列表序号可调整路线。也可输入“经度,
        纬度”后按回车选择。
      </p>
      <Waypoints />
      <div className="flex gap-2">
        <Button
          variant="outline"
          onClick={addEmptyWaypointToEnd}
          data-testid="add-waypoint-button"
          className="flex-1 min-w-0"
        >
          <MapPinPlus className="size-4" />
          添加途经点
        </Button>
        <Button
          variant="destructive-outline"
          onClick={() => {
            clearWaypoints();
            clearRoutes();
          }}
          data-testid="reset-waypoints-button"
          className="flex-1 min-w-0"
        >
          <MapPinXInside className="size-4" />
          清空路线
        </Button>
      </div>
      <Button
        onClick={() => refetch()}
        disabled={activeCount < 2 || loading}
        data-testid="calculate-route-button"
      >
        <Route className="size-4" />
        {loading ? '正在规划…' : '规划步行路线'}
      </Button>
      {results.data && (
        <div data-testid="route-results">
          <h3 className="font-bold mb-2">
            步行路线 · {results.data.trip.legs.length} 段
          </h3>
          <RouteCard
            data={results.data}
            index={0}
            isActive={true}
            onSelect={() => {}}
          />
        </div>
      )}
    </>
  );
};
