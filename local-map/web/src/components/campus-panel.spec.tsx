import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CampusPanel, RouteDebugPanel } from './campus-panel';
import { useRouteDebugStore } from '@/stores/route-debug-store';

const mocks = vi.hoisted(() => ({
  clear: vi.fn(),
  clearRoutes: vi.fn(),
  setWaypoint: vi.fn().mockResolvedValue([]),
  refetch: vi.fn().mockResolvedValue({}),
}));
vi.mock('@/stores/directions-store', () => ({
  useDirectionsStore: {
    getState: () => ({
      clearWaypoints: mocks.clear,
      clearRoutes: mocks.clearRoutes,
    }),
  },
}));
vi.mock('@/hooks/use-directions-queries', () => ({
  useDirectionsQuery: () => ({ refetch: mocks.refetch }),
  useSetWaypointFromCoords: () => ({
    setWaypointFromCoords: mocks.setWaypoint,
  }),
}));

const metadata = {
  name: '测试校园',
  coverage: {
    notes: ['主校区：已收录道路 6 条、建筑 2 栋。'],
    warnings: ['北校区入口数据不足。'],
  },
  examples: [
    {
      id: 'via',
      name: '经由道路中点',
      start: [113.384, 22.529],
      waypoints: [[113.385, 22.53]],
      end: [113.386, 22.531],
    },
  ],
};

describe('campus offline panels', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => metadata })
    );
    useRouteDebugStore.setState({
      request: null,
      response: null,
      elapsedMs: null,
      status: '尚未请求',
      error: '',
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it('loads metadata only from the same-origin local API', async () => {
    render(<CampusPanel />);
    await screen.findByText('测试校园');
    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledWith('/api/v1/map', {
      signal: expect.any(AbortSignal),
    });
  });

  it('shows real data coverage notes and the difference between a road snap and a building entrance', async () => {
    render(<CampusPanel />);
    expect(screen.getByText(/内部步道与建筑入口未完整收录/)).toHaveTextContent(
      /不能视为建筑入口/
    );
    expect(screen.getByText(/定位不可用时/)).toBeInTheDocument();
    expect(
      await screen.findByText(metadata.coverage.notes[0]!)
    ).toBeInTheDocument();
    expect(
      screen.getByText(metadata.coverage.warnings[0]!)
    ).toBeInTheDocument();
  });

  it('clears the old route and preserves the start, via and end coordinate order when loading an example', async () => {
    render(<CampusPanel />);
    await userEvent
      .setup()
      .click(await screen.findByRole('button', { name: '经由道路中点' }));
    await waitFor(() => expect(mocks.refetch).toHaveBeenCalledOnce());
    expect(mocks.clear).toHaveBeenCalledOnce();
    expect(mocks.clearRoutes).toHaveBeenCalledOnce();
    expect(mocks.setWaypoint.mock.calls).toEqual([
      [113.384, 22.529, 0, { isPermalink: true }],
      [113.385, 22.53, 1, { isPermalink: true }],
      [113.386, 22.531, 2, { isPermalink: true }],
    ]);
  });

  it('supports an API response that wraps the active manifest', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ manifest: metadata }),
    } as Response);
    render(<CampusPanel />);
    expect(
      await screen.findByRole('button', { name: '经由道路中点' })
    ).toBeInTheDocument();
  });

  it('does not show removed supplemental controls before data is available', async () => {
    render(<CampusPanel />);
    await screen.findByText('测试校园');
    expect(screen.queryByTestId('reference-route')).not.toBeInTheDocument();
    expect(screen.queryByTestId('supplementary-paths')).not.toBeInTheDocument();
  });

  it('shows local metadata errors without hiding manual entry instructions', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: false, status: 503 } as Response);
    render(<CampusPanel />);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '地图信息请求失败：HTTP 503'
    );
    expect(screen.getByText(/定位不可用时/)).toBeInTheDocument();
  });

  it('aborts its metadata request when the sidebar unmounts', () => {
    vi.mocked(fetch).mockImplementation(() => new Promise(() => {}));
    const view = render(<CampusPanel />);
    const signal = vi.mocked(fetch).mock.calls[0]![1]!.signal!;
    view.unmount();
    expect(signal.aborted).toBe(true);
  });

  it('links to the local interactive OpenAPI page', async () => {
    render(<CampusPanel />);
    expect(screen.getByRole('link', { name: '本地 API 文档' })).toHaveAttribute(
      'href',
      '/docs'
    );
    await screen.findByText('测试校园');
  });

  it('renders the actual request, response and measured elapsed time from the route trace', () => {
    const request = {
      costing: 'pedestrian',
      locations: [{ lon: 113.384, lat: 22.529 }],
    };
    const response = { trip: { status: 0 } };
    useRouteDebugStore.setState({
      request,
      response,
      elapsedMs: 24,
      status: 'HTTP 200',
      error: '',
    });
    render(<RouteDebugPanel />);
    expect(screen.getByText(/HTTP 200.*24 ms/)).toBeInTheDocument();
    expect(
      JSON.parse(screen.getByTestId('route-request').textContent!)
    ).toEqual(request);
    expect(
      JSON.parse(screen.getByTestId('route-response').textContent!)
    ).toEqual(response);
  });

  it('updates the visible trace error when the local route fails', () => {
    render(<RouteDebugPanel />);
    act(() => {
      useRouteDebugStore.setState({
        status: '失败',
        error: '超出地图覆盖范围',
      });
    });
    expect(screen.getByRole('alert')).toHaveTextContent('超出地图覆盖范围');
  });
});
