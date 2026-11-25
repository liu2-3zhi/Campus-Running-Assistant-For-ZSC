import { useEffect, useMemo } from 'react';
import { Layer, Marker, Source, useMap } from 'react-map-gl/maplibre';
import type { Feature, MultiLineString } from 'geojson';
import { useCommonStore } from '@/stores/common-store';
import type { TaskCoordinate, TaskPlan } from '@/stores/task-planner-store';

const pathLayout = {
  'line-cap': 'round',
  'line-join': 'round',
} as const;

function segmentKey(first: TaskCoordinate, second: TaskCoordinate) {
  const a = first.join(',');
  const b = second.join(',');
  return a < b ? `${a}:${b}` : `${b}:${a}`;
}

function roadGeometry(plan: TaskPlan): Feature<MultiLineString> {
  const connectors = new Set(
    plan.connectors.features.map(({ geometry }) =>
      segmentKey(geometry.coordinates[0]!, geometry.coordinates[1]!)
    )
  );
  const coordinates = plan.route.geometry.coordinates;
  const sections: TaskCoordinate[][] = [];
  let path: TaskCoordinate[] = [];
  for (let index = 1; index < coordinates.length; index++) {
    const previous = coordinates[index - 1]!;
    const next = coordinates[index]!;
    if (connectors.has(segmentKey(previous, next))) {
      if (path.length) sections.push(path);
      path = [];
    } else {
      if (!path.length) path.push(previous);
      path.push(next);
    }
  }
  if (path.length) sections.push(path);
  return {
    type: 'Feature',
    geometry: { type: 'MultiLineString', coordinates: sections },
    properties: {},
  };
}

export function TaskRouteLayers({ plan }: { plan: TaskPlan }) {
  const { current: map } = useMap();
  const ready = useCommonStore((state) => state.mapReady);
  const panelOpen = useCommonStore((state) => state.directionsPanelOpen);
  const road = useMemo(() => roadGeometry(plan), [plan]);
  const groupedTargets = useMemo(() => {
    const groups = new Map<
      string,
      { coordinate: TaskCoordinate; labels: string[]; order: number[] }
    >();
    plan.target_points.forEach(({ name, coordinate }, index) => {
      const key = coordinate.join(',');
      const group = groups.get(key);
      if (group) {
        group.labels.push(name);
        group.order.push(index + 1);
      } else {
        groups.set(key, { coordinate, labels: [name], order: [index + 1] });
      }
    });
    return groups;
  }, [plan]);

  useEffect(() => {
    if (!map || !ready) return;
    const coordinates = plan.route.geometry.coordinates;
    const [lng, lat] = coordinates[0]!;
    const bounds = coordinates.reduce<[TaskCoordinate, TaskCoordinate]>(
      ([[west, south], [east, north]], [longitude, latitude]) => [
        [Math.min(west, longitude), Math.min(south, latitude)],
        [Math.max(east, longitude), Math.max(north, latitude)],
      ],
      [
        [lng, lat],
        [lng, lat],
      ]
    );
    map.fitBounds(bounds, {
      padding: {
        left: panelOpen && window.innerWidth >= 550 ? 432 : 42,
        right: 42,
        top: 48,
        bottom: 48,
      },
      maxZoom: 18,
    });
  }, [map, panelOpen, plan, ready]);

  return (
    <>
      <Source
        id="task-recommended"
        type="geojson"
        data={plan.recommended_paths}
      >
        <Layer
          id="task-recommended-line"
          type="line"
          layout={pathLayout}
          paint={{
            'line-color': '#008566',
            'line-width': 3,
            'line-opacity': 0.8,
          }}
        />
      </Source>
      <Source id="task-route" type="geojson" data={road}>
        <Layer
          id="task-route-outline"
          type="line"
          layout={pathLayout}
          paint={{ 'line-color': '#fff', 'line-width': 8 }}
        />
        <Layer
          id="task-route-line"
          type="line"
          layout={pathLayout}
          paint={{ 'line-color': '#006FAD', 'line-width': 5 }}
        />
      </Source>
      <Source id="task-connectors" type="geojson" data={plan.connectors}>
        <Layer
          id="task-connectors-outline"
          type="line"
          paint={{ 'line-color': '#fff', 'line-width': 6 }}
        />
        <Layer
          id="task-connectors-line"
          type="line"
          paint={{
            'line-color': '#BA4C19',
            'line-width': 4,
            'line-dasharray': [2, 1],
          }}
        />
      </Source>
      {Array.from(groupedTargets, ([key, { coordinate, labels, order }]) => (
        <Marker key={key} longitude={coordinate[0]} latitude={coordinate[1]}>
          <span
            className="inline-flex h-6 min-w-6 items-center justify-center rounded-full border-2 border-white bg-[#006FAD] px-1 text-xs font-semibold text-white shadow-sm"
            title={labels.join('、')}
            role="img"
            aria-label={labels
              .map((label, index) => `${order[index]} ${label}`)
              .join('、')}
            data-testid="task-target-marker"
          >
            {order.join('/')}
          </span>
        </Marker>
      ))}
    </>
  );
}
