import type { ReactNode } from 'react';
import { render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import type { TaskCoordinate, TaskPlan } from '@/stores/task-planner-store';
import { TaskRouteLayers } from './task-route-layers';

const { fitBounds } = vi.hoisted(() => ({ fitBounds: vi.fn() }));

vi.mock('react-map-gl/maplibre', () => ({
  useMap: () => ({ current: { fitBounds } }),
  Marker: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Source: () => null,
  Layer: () => null,
}));

vi.mock('@/stores/common-store', () => ({
  useCommonStore: (
    select: (state: {
      mapReady: boolean;
      directionsPanelOpen: boolean;
    }) => unknown
  ) => select({ mapReady: true, directionsPanelOpen: false }),
}));

const start: TaskCoordinate = [113.39, 22.528];
const end: TaskCoordinate = [113.391, 22.528];
const offRoute: TaskCoordinate = [113.3915, 22.529];
const metrics = { distance_m: 200, duration_s: 140 };
const plan: TaskPlan = {
  coordinate_system: 'GCJ-02',
  task_name: '校园任务',
  target_points: [
    { name: '北门2', coordinate: start },
    { name: '体育馆', coordinate: offRoute },
    { name: '北门2', coordinate: start },
    { name: '东门', coordinate: end },
  ],
  ...metrics,
  route: {
    type: 'Feature',
    geometry: { type: 'LineString', coordinates: [start, end] },
    properties: metrics,
  },
  connectors: { type: 'FeatureCollection', features: [] },
  recommended_paths: { type: 'FeatureCollection', features: [] },
};

it('shows visible checkpoint names and every visit number for shared locations', () => {
  render(<TaskRouteLayers plan={plan} />);

  const markers = screen.getAllByTestId('task-target-marker');
  expect(markers).toHaveLength(3);
  const repeated = within(markers[0]!);
  expect(repeated.getByText('1/3')).toBeVisible();
  expect(repeated.getByText('北门2')).toBeVisible();
  expect(markers[0]).toHaveAccessibleName('1 北门2、3 北门2');
  expect(screen.getByText('体育馆')).toBeVisible();
});

it('fits the viewport around all checkpoints, even beyond the route geometry', () => {
  render(<TaskRouteLayers plan={plan} />);

  expect(fitBounds).toHaveBeenCalledWith(
    [start, offRoute],
    expect.objectContaining({ maxZoom: 18 })
  );
});
