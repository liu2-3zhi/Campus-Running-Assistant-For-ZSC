import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DirectionsControl } from './directions';

const mocks = vi.hoisted(() => ({
  add: vi.fn(),
  clear: vi.fn(),
  clearRoutes: vi.fn(),
  refetch: vi.fn(),
  loading: false,
  waypoints: [
    { geocodeResults: [] as { selected: boolean }[] },
    { geocodeResults: [] as { selected: boolean }[] },
  ],
  results: { data: null as null | { trip: { legs: unknown[] } } },
}));

vi.mock('@/stores/directions-store', () => ({
  useDirectionsStore: (selector: (state: unknown) => unknown) =>
    selector({
      waypoints: mocks.waypoints,
      results: mocks.results,
      addEmptyWaypointToEnd: mocks.add,
      clearWaypoints: mocks.clear,
      clearRoutes: mocks.clearRoutes,
    }),
}));
vi.mock('@/stores/common-store', () => ({
  useCommonStore: (selector: (state: unknown) => unknown) =>
    selector({ loading: mocks.loading }),
}));
vi.mock('@/hooks/use-directions-queries', () => ({
  useDirectionsQuery: () => ({ refetch: mocks.refetch }),
}));
vi.mock('./waypoints/waypoint-list', () => ({
  Waypoints: () => <div data-testid="waypoints" />,
}));
vi.mock('./route-card', () => ({
  RouteCard: ({ index }: { index: number }) => (
    <div data-testid={`route-card-${index}`} />
  ),
}));

describe('offline DirectionsControl', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.loading = false;
    mocks.results.data = null;
    mocks.waypoints = [{ geocodeResults: [] }, { geocodeResults: [] }];
  });

  it('retains the upstream waypoint list and documents coordinate and drag entry', () => {
    render(<DirectionsControl />);
    expect(screen.getByTestId('waypoints')).toBeInTheDocument();
    expect(
      screen.getByText(/点击地图设置起点、终点或途经点/)
    ).toHaveTextContent(/拖动标记或列表序号/);
  });

  it('adds a waypoint using the visible Chinese action', async () => {
    render(<DirectionsControl />);
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: '添加途经点' }));
    expect(mocks.add).toHaveBeenCalledOnce();
  });

  it('clears selected waypoints and previously drawn routes together', async () => {
    render(<DirectionsControl />);
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: '清空路线' }));
    expect(mocks.clear).toHaveBeenCalledOnce();
    expect(mocks.clearRoutes).toHaveBeenCalledOnce();
  });

  it('disables planning until two locations have been selected', () => {
    mocks.waypoints[0]!.geocodeResults = [{ selected: true }];
    render(<DirectionsControl />);
    expect(screen.getByTestId('calculate-route-button')).toBeDisabled();
  });

  it('ignores unselected coordinate candidates when enabling route planning', () => {
    mocks.waypoints.forEach((waypoint) => {
      waypoint.geocodeResults = [{ selected: false }];
    });
    render(<DirectionsControl />);
    expect(screen.getByTestId('calculate-route-button')).toBeDisabled();
  });

  it('requests a route when two locations are selected', async () => {
    mocks.waypoints.forEach((waypoint) => {
      waypoint.geocodeResults = [{ selected: true }];
    });
    render(<DirectionsControl />);
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: '规划步行路线' }));
    expect(mocks.refetch).toHaveBeenCalledOnce();
  });

  it('blocks duplicate planning while the route is loading', () => {
    mocks.loading = true;
    mocks.waypoints.forEach((waypoint) => {
      waypoint.geocodeResults = [{ selected: true }];
    });
    render(<DirectionsControl />);
    expect(screen.getByRole('button', { name: '正在规划…' })).toBeDisabled();
  });

  it('does not show a stale result card without a route', () => {
    render(<DirectionsControl />);
    expect(screen.queryByTestId('route-results')).not.toBeInTheDocument();
  });

  it('shows the number of legs and the native route card', () => {
    mocks.results.data = { trip: { legs: [{}, {}] } };
    render(<DirectionsControl />);
    expect(screen.getByText('步行路线 · 2 段')).toBeInTheDocument();
    expect(screen.getByTestId('route-card-0')).toBeInTheDocument();
  });

  it('does not expose online optimization or general routing settings', () => {
    render(<DirectionsControl />);
    expect(
      screen.queryByText(/Optimize Route|Advanced settings|Quick Settings/)
    ).not.toBeInTheDocument();
  });
});
