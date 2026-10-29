import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WaypointSearch } from './waypoint-search';
import { useState } from 'react';
import type { ActiveWaypoint } from '@/components/types';

const mockOnResultSelect = vi.fn();
const mockFlyTo = vi.fn();

function WaypointSearchHarness() {
  const [results, setResults] = useState<ActiveWaypoint[]>([]);
  return (
    <WaypointSearch
      userInput=""
      geocodeResults={results}
      onGeocodeResults={setResults}
      onResultSelect={mockOnResultSelect}
    />
  );
}

vi.mock('react-map-gl/maplibre', () => ({
  useMap: vi.fn(() => ({
    mainMap: {
      flyTo: mockFlyTo,
    },
  })),
}));

vi.mock('@/stores/common-store', () => ({
  useCommonStore: vi.fn((selector) =>
    selector({
      settings: {
        use_geocoding: false,
      },
    })
  ),
}));

vi.mock('@tanstack/react-query', () => ({
  useMutation: vi.fn(({ mutationFn, onSuccess }) => ({
    mutate: vi.fn(async () => {
      onSuccess(await mutationFn());
    }),
    isPending: false,
    isSuccess: true,
  })),
}));

const mockGeocodeResults = [
  {
    title: 'Berlin, Germany',
    description: 'https://osm.org/node/123',
    selected: false,
    addresslnglat: [13.4, 52.5] as [number, number],
    sourcelnglat: [13.4, 52.5] as [number, number],
    displaylnglat: [13.4, 52.5] as [number, number],
    key: 0,
    addressindex: 0,
  },
  {
    title: 'Berlin, New Hampshire',
    description: '',
    selected: false,
    addresslnglat: [-71.3, 44.5] as [number, number],
    sourcelnglat: [-71.3, 44.5] as [number, number],
    displaylnglat: [-71.3, 44.5] as [number, number],
    key: 1,
    addressindex: 1,
  },
];

describe('WaypointSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render without crashing', () => {
    expect(() =>
      render(
        <WaypointSearch
          userInput=""
          geocodeResults={[]}
          onResultSelect={mockOnResultSelect}
        />
      )
    ).not.toThrow();
  });

  it('should render with placeholder text', () => {
    render(
      <WaypointSearch
        userInput=""
        geocodeResults={[]}
        onResultSelect={mockOnResultSelect}
        placeholder="Search for a location..."
      />
    );

    expect(screen.getByText('Search for a location...')).toBeInTheDocument();
  });

  it('should display user input when provided', () => {
    render(
      <WaypointSearch
        userInput="Berlin"
        geocodeResults={[]}
        onResultSelect={mockOnResultSelect}
      />
    );

    expect(screen.getByText('Berlin')).toBeInTheDocument();
  });

  it('should render with custom testId', () => {
    render(
      <WaypointSearch
        userInput=""
        geocodeResults={[]}
        onResultSelect={mockOnResultSelect}
        testId="custom-waypoint-search"
      />
    );

    expect(screen.getByTestId('custom-waypoint-search')).toBeInTheDocument();
  });

  it('should render left content when provided', () => {
    render(
      <WaypointSearch
        userInput=""
        geocodeResults={[]}
        onResultSelect={mockOnResultSelect}
        leftContent={<span data-testid="left-content">Left</span>}
      />
    );

    expect(screen.getByTestId('left-content')).toBeInTheDocument();
  });

  it('should render right content when provided', () => {
    render(
      <WaypointSearch
        userInput=""
        geocodeResults={[]}
        onResultSelect={mockOnResultSelect}
        rightContent={<span data-testid="right-content">Right</span>}
      />
    );

    expect(screen.getByTestId('right-content')).toBeInTheDocument();
  });

  it('should open popover when button is clicked', async () => {
    const user = userEvent.setup();
    render(<WaypointSearchHarness />);

    await user.click(screen.getByRole('combobox'));

    expect(
      screen.getByPlaceholderText('输入经度, 纬度，按回车确认')
    ).toBeInTheDocument();
  });

  it('should display geocode results when available', async () => {
    const user = userEvent.setup();
    render(
      <WaypointSearch
        userInput=""
        geocodeResults={mockGeocodeResults}
        onResultSelect={mockOnResultSelect}
      />
    );

    await user.click(screen.getByRole('combobox'));

    expect(screen.getByText('Berlin, Germany')).toBeInTheDocument();
    expect(screen.getByText('Berlin, New Hampshire')).toBeInTheDocument();
  });

  it('should show OSM Link for results with description', async () => {
    const user = userEvent.setup();
    render(
      <WaypointSearch
        userInput=""
        geocodeResults={mockGeocodeResults}
        onResultSelect={mockOnResultSelect}
      />
    );

    await user.click(screen.getByRole('combobox'));

    expect(screen.getByText('OSM Link')).toBeInTheDocument();
  });

  it('should call onResultSelect when a result is clicked', async () => {
    const user = userEvent.setup();
    render(
      <WaypointSearch
        userInput=""
        geocodeResults={mockGeocodeResults}
        onResultSelect={mockOnResultSelect}
      />
    );

    await user.click(screen.getByRole('combobox'));
    await user.click(screen.getByText('Berlin, Germany'));

    expect(mockOnResultSelect).toHaveBeenCalledWith(mockGeocodeResults[0]);
  });

  it('should fly to location when result is selected', async () => {
    const user = userEvent.setup();
    render(
      <WaypointSearch
        userInput=""
        geocodeResults={mockGeocodeResults}
        onResultSelect={mockOnResultSelect}
      />
    );

    await user.click(screen.getByRole('combobox'));
    await user.click(screen.getByText('Berlin, Germany'));

    expect(mockFlyTo).toHaveBeenCalledWith({
      center: [13.4, 52.5],
    });
  });

  it('preserves manually entered GCJ-02 campus coordinates without conversion', async () => {
    const user = userEvent.setup();
    render(<WaypointSearchHarness />);

    await user.click(screen.getByRole('combobox'));
    expect(screen.queryByLabelText('输入坐标系')).not.toBeInTheDocument();
    await user.type(
      screen.getByPlaceholderText('输入经度, 纬度，按回车确认'),
      '113.391997,22.529253'
    );
    await user.keyboard('{Enter}');
    const result = await screen.findByTestId('search-result');
    expect(result).toHaveTextContent('GCJ-02 113.391997,22.529253');
    await user.click(result);

    expect(mockFlyTo).toHaveBeenCalledWith({
      center: [113.391997, 22.529253],
    });
    const selectedWaypoint = mockOnResultSelect.mock.calls[0]![0];
    expect(selectedWaypoint.addresslnglat).toEqual([113.391997, 22.529253]);
    expect(selectedWaypoint.sourcelnglat).toEqual([113.391997, 22.529253]);
    expect(selectedWaypoint.displaylnglat).toEqual([113.391997, 22.529253]);
  });

  it('explains that all manual coordinates are GCJ-02', async () => {
    const user = userEvent.setup();
    render(<WaypointSearchHarness />);

    await user.click(screen.getByRole('combobox'));
    expect(
      screen.getByText(/GCJ-02（火星坐标），经度在前/)
    ).toBeInTheDocument();
    await user.type(
      screen.getByPlaceholderText('输入经度, 纬度，按回车确认'),
      '113.391997,22.529253'
    );
    await user.keyboard('{Enter}');
    await user.click(await screen.findByTestId('search-result'));

    expect(mockFlyTo).toHaveBeenCalledWith({ center: [113.391997, 22.529253] });
  });

  it('should close popover after selecting a result', async () => {
    const user = userEvent.setup();
    render(
      <WaypointSearch
        userInput=""
        geocodeResults={mockGeocodeResults}
        onResultSelect={mockOnResultSelect}
      />
    );

    await user.click(screen.getByRole('combobox'));
    expect(
      screen.getByPlaceholderText('输入经度, 纬度，按回车确认')
    ).toBeInTheDocument();

    await user.click(screen.getByText('Berlin, Germany'));

    await waitFor(() => {
      expect(
        screen.queryByPlaceholderText('输入经度, 纬度，按回车确认')
      ).not.toBeInTheDocument();
    });
  });

  it('should have combobox role on trigger button', () => {
    render(
      <WaypointSearch
        userInput=""
        geocodeResults={[]}
        onResultSelect={mockOnResultSelect}
      />
    );

    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('should apply custom className', () => {
    render(
      <WaypointSearch
        userInput=""
        geocodeResults={[]}
        onResultSelect={mockOnResultSelect}
        className="custom-class"
      />
    );

    const container = screen.getByRole('combobox').parentElement;
    expect(container).toHaveClass('custom-class');
  });
});
