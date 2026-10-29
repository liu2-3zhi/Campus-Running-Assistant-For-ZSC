import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RoutePlanner } from './route-planner';

const mocks = vi.hoisted(() => ({
  toggle: vi.fn(),
  permalink: vi.fn(),
  open: true,
}));

vi.mock('@/stores/common-store', () => ({
  useCommonStore: (selector: (state: unknown) => unknown) =>
    selector({
      directionsPanelOpen: mocks.open,
      toggleDirections: mocks.toggle,
    }),
}));
vi.mock('@/hooks/use-directions-permalink', () => ({
  useDirectionsPermalink: mocks.permalink,
}));
vi.mock('./directions/directions', () => ({
  DirectionsControl: () => <div data-testid="directions-control" />,
}));
vi.mock('./campus-panel', () => ({
  CampusPanel: () => <div data-testid="campus-panel" />,
  RouteDebugPanel: () => <div data-testid="route-debug-panel" />,
}));

describe('offline RoutePlanner', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.open = true;
  });

  it('renders a Chinese walking route title and GCJ-02 coordinate order', () => {
    render(<RoutePlanner />);
    expect(
      screen.getByRole('heading', { name: '校园步行路线' })
    ).toBeInTheDocument();
    expect(screen.getByText(/GCJ-02 火星坐标，经度在前/)).toBeInTheDocument();
  });

  it('keeps campus metadata, direction controls and actual route debug in the sidebar', () => {
    render(<RoutePlanner />);
    for (const id of [
      'campus-panel',
      'directions-control',
      'route-debug-panel',
    ])
      expect(screen.getByTestId(id)).toBeInTheDocument();
  });

  it('does not expose unsupported routing tabs or profile selection', () => {
    render(<RoutePlanner />);
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Isochrones|Tiles|Change to Car|Advanced settings/)
    ).not.toBeInTheDocument();
  });

  it('retains upstream and OSM license attribution', () => {
    render(<RoutePlanner />);
    expect(
      screen.getByText(
        /Valhalla Web App.*MIT.*OpenStreetMap contributors.*ODbL 1.0/
      )
    ).toBeInTheDocument();
  });

  it('keeps coordinate permalinks active independently of sidebar visibility', () => {
    mocks.open = false;
    render(<RoutePlanner />);
    expect(mocks.permalink).toHaveBeenCalledWith(true);
    expect(screen.queryByTestId('directions-control')).not.toBeInTheDocument();
  });

  it('closes using the labeled button', async () => {
    render(<RoutePlanner />);
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: '收起路线面板' }));
    expect(mocks.toggle).toHaveBeenCalledOnce();
  });

  it('reserves room for map controls on narrow viewports', () => {
    render(<RoutePlanner />);
    expect(screen.getByRole('dialog')).toHaveClass('max-w-[calc(100vw-52px)]');
  });
});
