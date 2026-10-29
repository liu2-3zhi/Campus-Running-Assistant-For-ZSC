import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MapContextMenu } from './map-context-menu';

const mockAddWaypointAtIndex = vi.fn();
const mockUseDirectionsStore = vi.fn();

vi.mock('@/stores/directions-store', () => ({
  useDirectionsStore: (selector: (state: unknown) => unknown) =>
    mockUseDirectionsStore(selector),
}));

const defaultProps = {
  activeTab: 'directions',
  onAddWaypoint: vi.fn(),
  onAddIsoWaypoint: vi.fn(),
  popupLocation: { lng: 10.5, lat: 50.5 },
};

describe('MapContextMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseDirectionsStore.mockImplementation((selector) => {
      const state = {
        waypoints: [{}, {}, {}],
        addWaypointAtIndex: mockAddWaypointAtIndex,
      };
      return selector(state);
    });
  });

  describe('directions tab', () => {
    it('should render without crashing', () => {
      expect(() => render(<MapContextMenu {...defaultProps} />)).not.toThrow();
    });

    it('should render "设为起点" button', () => {
      render(<MapContextMenu {...defaultProps} />);

      expect(
        screen.getByRole('button', { name: '设为起点' })
      ).toBeInTheDocument();
    });

    it('should render "添加为途经点" button', () => {
      render(<MapContextMenu {...defaultProps} />);

      expect(
        screen.getByRole('button', { name: '添加为途经点' })
      ).toBeInTheDocument();
    });

    it('should render "设为终点" button', () => {
      render(<MapContextMenu {...defaultProps} />);

      expect(
        screen.getByRole('button', { name: '设为终点' })
      ).toBeInTheDocument();
    });

    it('should call onAddWaypoint(0) when "设为起点" is clicked', async () => {
      const user = userEvent.setup();
      const onAddWaypoint = vi.fn();

      render(
        <MapContextMenu {...defaultProps} onAddWaypoint={onAddWaypoint} />
      );

      await user.click(screen.getByRole('button', { name: '设为起点' }));

      expect(onAddWaypoint).toHaveBeenCalledWith(0);
    });

    it('should call onAddWaypoint with last index when "设为终点" is clicked', async () => {
      const user = userEvent.setup();
      const onAddWaypoint = vi.fn();

      render(
        <MapContextMenu {...defaultProps} onAddWaypoint={onAddWaypoint} />
      );

      await user.click(screen.getByRole('button', { name: '设为终点' }));

      expect(onAddWaypoint).toHaveBeenCalledWith(2);
    });

    it('should add waypoint and call onAddWaypoint when "添加为途经点" is clicked', async () => {
      const user = userEvent.setup();
      const onAddWaypoint = vi.fn();
      const popupLocation = { lng: 10.5, lat: 50.5 };

      render(
        <MapContextMenu
          {...defaultProps}
          onAddWaypoint={onAddWaypoint}
          popupLocation={popupLocation}
        />
      );

      await user.click(screen.getByRole('button', { name: '添加为途经点' }));

      expect(mockAddWaypointAtIndex).toHaveBeenCalledWith({
        index: 2,
        placeholder: popupLocation,
      });
      expect(onAddWaypoint).toHaveBeenCalledWith(2);
    });
  });

  describe('isochrones tab', () => {
    it('should render "Set center here" button', () => {
      render(<MapContextMenu {...defaultProps} activeTab="isochrones" />);

      expect(
        screen.getByRole('button', { name: 'Set center here' })
      ).toBeInTheDocument();
    });

    it('should not render directions buttons', () => {
      render(<MapContextMenu {...defaultProps} activeTab="isochrones" />);

      expect(
        screen.queryByRole('button', { name: '设为起点' })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole('button', { name: '添加为途经点' })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole('button', { name: '设为终点' })
      ).not.toBeInTheDocument();
    });

    it('should call onAddIsoWaypoint when "Set center here" is clicked', async () => {
      const user = userEvent.setup();
      const onAddIsoWaypoint = vi.fn();

      render(
        <MapContextMenu
          {...defaultProps}
          activeTab="isochrones"
          onAddIsoWaypoint={onAddIsoWaypoint}
        />
      );

      await user.click(screen.getByRole('button', { name: 'Set center here' }));

      expect(onAddIsoWaypoint).toHaveBeenCalled();
    });
  });
});
