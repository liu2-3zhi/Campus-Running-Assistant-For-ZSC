import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MapComponent } from './index';

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  toggle: vi.fn(),
  setReady: vi.fn(),
  setWaypoint: vi.fn().mockResolvedValue([]),
  refetch: vi.fn(),
  toast: vi.fn(),
  waypoints: [] as {
    geocodeResults: {
      selected: boolean;
      displaylnglat: number[];
      title: string;
    }[];
  }[],
  map: {
    getCenter: () => ({ lng: 113.39, lat: 22.528 }),
    getZoom: () => 17,
    fitBounds: vi.fn(),
    getMap: () => ({
      getCanvas: () => ({ style: {} }),
      getLayer: () => undefined,
    }),
  },
}));

vi.mock('react-map-gl/maplibre', async () => {
  const React = await import('react');
  return {
    Map: React.forwardRef(
      (
        {
          children,
          onClick,
          onDblClick,
          onContextMenu,
          onTouchStart,
          onLoad,
          onMove,
          minZoom,
          maxZoom,
          mapStyle,
          longitude,
          latitude,
          zoom,
        }: any,
        ref
      ) => {
        React.useImperativeHandle(ref, () => mocks.map);
        const event = {
          lngLat: { lng: 113.39, lat: 22.528 },
          point: { x: 200, y: 200 },
        };
        return (
          <div
            data-testid="map"
            data-minzoom={minZoom}
            data-maxzoom={maxZoom}
            data-style={mapStyle}
            data-position={JSON.stringify([longitude, latitude, zoom])}
            onClick={() => onClick(event)}
            onDoubleClick={() => onDblClick(event)}
            onContextMenu={(e) => {
              e.preventDefault();
              onContextMenu(event);
            }}
            onTouchStart={(e) => onTouchStart({ ...event, originalEvent: e })}
          >
            <button
              data-testid="map-load"
              onClick={(e) => {
                e.stopPropagation();
                onLoad();
              }}
            >
              load
            </button>
            <button
              data-testid="move-map"
              onClick={(e) => {
                e.stopPropagation();
                onMove({ viewState: { longitude: 0, latitude: 0, zoom: 17 } });
              }}
            >
              move
            </button>
            {children}
          </div>
        );
      }
    ),
    Marker: ({ children, onDragEnd, draggable }: any) => (
      <div data-testid="marker" data-draggable={String(draggable)}>
        {children}
        <button
          data-testid="drag-marker"
          onClick={() => onDragEnd({ lngLat: { lng: 113.385, lat: 22.53 } })}
        >
          drag
        </button>
      </div>
    ),
    Popup: ({ children }: any) => <div data-testid="popup">{children}</div>,
    NavigationControl: () => <div data-testid="navigation-control" />,
    GeolocateControl: React.forwardRef(({ onError }: any, ref) => {
      const control = React.useMemo(() => ({ _onSuccess: vi.fn() }), []);
      React.useImperativeHandle(ref, () => control, [control]);
      return (
        <div data-testid="geolocate-control">
          <button
            data-testid="gps-error"
            onClick={() => onError({ code: 3, PERMISSION_DENIED: 1 })}
          >
            error
          </button>
          <button
            data-testid="gps-denied"
            onClick={() => onError({ code: 1, PERMISSION_DENIED: 1 })}
          >
            denied
          </button>
        </div>
      );
    }),
    useMap: () => ({ mainMap: mocks.map }),
  };
});
vi.mock('@tanstack/react-router', () => ({
  useParams: () => ({ activeTab: 'directions' }),
  useNavigate: () => mocks.navigate,
  useSearch: () => ({ profile: 'pedestrian' }),
}));
vi.mock('@/stores/common-store', () => ({
  useCommonStore: (selector: any) =>
    selector({
      coordinates: [],
      directionsPanelOpen: false,
      toggleDirections: mocks.toggle,
      setMapReady: mocks.setReady,
    }),
}));
vi.mock('@/stores/directions-store', () => ({
  useDirectionsStore: (selector: any) =>
    selector({
      waypoints: mocks.waypoints,
      results: { data: null, show: {} },
      successful: false,
      setActiveRouteIndex: vi.fn(),
    }),
}));
vi.mock('@/stores/isochrones-store', () => ({
  useIsochronesStore: (selector: any) => selector({ geocodeResults: [] }),
}));
vi.mock('@/hooks/use-directions-queries', () => ({
  useDirectionsQuery: () => ({ refetch: mocks.refetch }),
  useSetWaypointFromCoords: () => ({
    setWaypointFromCoords: mocks.setWaypoint,
  }),
}));
vi.mock('@/hooks/use-isochrones-queries', () => ({
  useIsochronesQuery: () => ({ refetch: vi.fn() }),
  useReverseGeocodeIsochrones: () => ({ reverseGeocode: vi.fn() }),
}));
vi.mock('./parts/route-lines', () => ({
  RouteLines: () => <div data-testid="route-lines" />,
}));
vi.mock('./parts/highlight-segment', () => ({
  HighlightSegment: () => <div data-testid="highlight-segment" />,
}));
vi.mock('./parts/route-hover-popup', () => ({ RouteHoverPopup: () => null }));
vi.mock('./parts/heightgraph-hover-marker', () => ({
  HeightgraphHoverMarker: () => null,
}));
vi.mock('./parts/map-context-menu', () => ({
  MapContextMenu: ({ onAddWaypoint, popupLocation }: any) => (
    <div data-testid="map-context-menu">
      <span>
        {popupLocation.lng}, {popupLocation.lat}
      </span>
      <button onClick={() => onAddWaypoint(0)}>设为起点</button>
    </div>
  ),
}));
vi.mock('sonner', () => ({ toast: { error: mocks.toast } }));

describe('offline MapComponent', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mocks.waypoints = [];
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('uses only the local raster style at the supported zooms', () => {
    render(<MapComponent />);
    expect(screen.getByTestId('map')).toHaveAttribute(
      'data-style',
      '/api/v1/map-style'
    );
    expect(screen.getByTestId('map')).toHaveAttribute('data-minzoom', '14');
    expect(screen.getByTestId('map')).toHaveAttribute('data-maxzoom', '20');
  });

  it('keeps the map center inside the campus coverage without restricting the viewport', () => {
    render(<MapComponent />);
    fireEvent.click(screen.getByTestId('move-map'));
    expect(screen.getByTestId('map')).toHaveAttribute(
      'data-position',
      '[113.3852747260368,22.522802343443914,17]'
    );
  });

  it('starts on the configured GCJ-02 campus center', () => {
    render(<MapComponent />);
    expect(screen.getByTestId('map')).toHaveAttribute(
      'data-position',
      '[113.38995276699997,22.526967288038794,17]'
    );
  });

  it('retains navigation, GPS and route drawing controls', () => {
    render(<MapComponent />);
    for (const id of [
      'navigation-control',
      'geolocate-control',
      'route-lines',
      'highlight-segment',
    ])
      expect(screen.getByTestId(id)).toBeInTheDocument();
  });

  it('does not expose unsupported service shortcuts or external OSM navigation', () => {
    render(<MapComponent />);
    for (const id of [
      'tab-isochrones-button',
      'tab-tiles-button',
      'osm-button',
      'map-style-control',
      'heightgraph-toggle',
      'draw-control',
    ])
      expect(screen.queryByTestId(id)).not.toBeInTheDocument();
    expect(screen.getByTestId('tab-directions-button')).toBeInTheDocument();
  });

  it('opens the route sidebar from the map shortcut', () => {
    render(<MapComponent />);
    fireEvent.click(screen.getByTestId('tab-directions-button'));
    expect(mocks.toggle).toHaveBeenCalledOnce();
    expect(mocks.navigate).toHaveBeenCalledWith({
      params: { activeTab: 'directions' },
    });
  });

  it('marks the map ready after the actual load callback', () => {
    render(<MapComponent />);
    fireEvent.click(screen.getByTestId('map-load'));
    expect(mocks.setReady).toHaveBeenCalledWith(true);
  });

  it('opens coordinate selection on a single click without querying elevation or geocoding', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    render(<MapComponent />);
    fireEvent.click(screen.getByTestId('map'));
    expect(screen.queryByTestId('map-context-menu')).not.toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });
    expect(screen.getByTestId('map-context-menu')).toHaveTextContent(
      '113.39, 22.528'
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('selects a waypoint from the coordinate context menu and recalculates locally', async () => {
    render(<MapComponent />);
    fireEvent.contextMenu(screen.getByTestId('map'));
    fireEvent.click(screen.getByRole('button', { name: '设为起点' }));
    await waitFor(() => expect(mocks.refetch).toHaveBeenCalledOnce());
    expect(mocks.setWaypoint).toHaveBeenCalledWith(113.39, 22.528, 0);
  });

  it('closes the context menu with a subsequent map click', () => {
    render(<MapComponent />);
    fireEvent.contextMenu(screen.getByTestId('map'));
    expect(screen.getByTestId('map-context-menu')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('map'));
    expect(screen.queryByTestId('map-context-menu')).not.toBeInTheDocument();
  });

  it('keeps double-click available for zoom without placing a waypoint', async () => {
    vi.useFakeTimers();
    render(<MapComponent />);
    fireEvent.click(screen.getByTestId('map'));
    fireEvent.doubleClick(screen.getByTestId('map'));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });
    expect(screen.queryByTestId('map-context-menu')).not.toBeInTheDocument();
    expect(mocks.setWaypoint).not.toHaveBeenCalled();
  });

  it('cancels a pending click during a multi-finger map gesture', async () => {
    vi.useFakeTimers();
    render(<MapComponent />);
    fireEvent.click(screen.getByTestId('map'));
    fireEvent.touchStart(screen.getByTestId('map'), {
      touches: [
        { clientX: 1, clientY: 1 },
        { clientX: 2, clientY: 2 },
      ],
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });
    expect(screen.queryByTestId('map-context-menu')).not.toBeInTheDocument();
  });

  it('recalculates after an upstream draggable waypoint marker moves', async () => {
    mocks.waypoints = [
      {
        geocodeResults: [
          {
            selected: true,
            displaylnglat: [113.39, 22.528],
            title: 'start',
          },
        ],
      },
    ];
    render(<MapComponent />);
    expect(screen.getByTestId('marker')).toHaveAttribute(
      'data-draggable',
      'true'
    );
    fireEvent.click(screen.getByTestId('drag-marker'));
    await waitFor(() => expect(mocks.refetch).toHaveBeenCalledOnce());
    expect(mocks.setWaypoint).toHaveBeenCalledWith(113.385, 22.53, 0);
  });

  it('explains manual entry after a GPS error', () => {
    render(<MapComponent />);
    fireEvent.click(screen.getByTestId('gps-error'));
    expect(mocks.toast).toHaveBeenCalledWith(
      '定位暂不可用，请点击地图或手动输入坐标。'
    );
  });

  it('explains manual entry after denied GPS permission', () => {
    render(<MapComponent />);
    fireEvent.click(screen.getByTestId('gps-denied'));
    expect(mocks.toast).toHaveBeenCalledWith(
      '未获得定位权限，请点击地图或手动输入坐标。'
    );
  });
});
