import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
  type Mock,
} from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MapStyleControl } from './map-style-control';
import { MAP_STYLES, MAP_STYLE_STORAGE_KEY } from './constants';
import * as utils from './utils';

vi.mock('react-map-gl/maplibre', () => ({
  default: vi.fn(({ id }) => <div data-testid={`map-${id}`}>Mock Map</div>),
  useMap: vi.fn(() => ({
    current: {
      getCenter: () => ({ lng: 13.4, lat: 52.5 }),
      getZoom: () => 10,
    },
  })),
}));

vi.mock('./custom-control', async () => {
  const { forwardRef: fwdRef } = await import('react');
  return {
    CustomControl: vi.fn(({ children }: { children: React.ReactNode }) => (
      <div data-testid="custom-control">{children}</div>
    )),
    ControlButton: fwdRef<
      HTMLButtonElement,
      React.ComponentPropsWithoutRef<'button'> & {
        title: string;
        icon: React.ReactNode;
      }
    >(({ title, icon, ...props }, ref) => (
      <button ref={ref} aria-label={title} title={title} {...props}>
        {icon}
      </button>
    )),
  };
});

vi.mock('./custom-styles-dialog', () => ({
  CustomStylesDialog: vi.fn(({ onStyleLoaded }) => (
    <button
      data-testid="custom-styles-dialog"
      onClick={() =>
        onStyleLoaded?.({
          version: 8,
          name: 'Custom Style',
          sources: {},
          layers: [],
        })
      }
    >
      Load custom styles
    </button>
  )),
}));

vi.mock('./edit-styles-dialog', () => ({
  EditStylesDialog: vi.fn(({ styleData, onStyleSaved }) => (
    <button
      data-testid="edit-styles-dialog"
      onClick={() =>
        onStyleSaved?.({
          ...styleData,
          name: 'Edited Style',
        })
      }
    >
      Edit custom style
    </button>
  )),
}));

vi.mock('./utils', async (importOriginal) => {
  const original = await importOriginal<typeof utils>();
  return {
    ...original,
    getInitialMapStyle: vi.fn(() => 'shortbread'),
  };
});

describe('MapStyleControl', () => {
  let localStorageMock: Record<string, string>;

  beforeEach(() => {
    localStorageMock = {};
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(
      (key: string, value: string) => {
        localStorageMock[key] = value;
      }
    );
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(
      (key: string) => localStorageMock[key] ?? null
    );

    vi.clearAllMocks();
    (utils.getInitialMapStyle as Mock).mockReturnValue('shortbread');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should render without crashing', () => {
    expect(() =>
      render(
        <MapStyleControl
          customStyleData={null}
          onStyleChange={vi.fn()}
          onCustomStyleLoaded={vi.fn()}
        />
      )
    ).not.toThrow();
  });

  it('should render the map styles button', () => {
    render(
      <MapStyleControl
        customStyleData={null}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={vi.fn()}
      />
    );

    expect(
      screen.getByRole('button', { name: 'Map Styles' })
    ).toBeInTheDocument();
  });

  it('should open popover when button is clicked', async () => {
    const user = userEvent.setup();

    render(
      <MapStyleControl
        customStyleData={null}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={vi.fn()}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Map Styles' }));

    await waitFor(() => {
      MAP_STYLES.forEach((mapStyle) => {
        expect(screen.getByText(mapStyle.label)).toBeInTheDocument();
      });
    });
  });

  it('should render the Load custom styles button', async () => {
    const user = userEvent.setup();

    render(
      <MapStyleControl
        customStyleData={null}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={vi.fn()}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Map Styles' }));

    await waitFor(() => {
      expect(screen.getByTestId('custom-styles-dialog')).toBeInTheDocument();
    });
  });

  it('should display custom style option when customStyleData is provided', async () => {
    const user = userEvent.setup();
    const customStyleData = {
      version: 8 as const,
      name: 'My Custom Style',
      sources: {},
      layers: [],
    };

    render(
      <MapStyleControl
        customStyleData={customStyleData}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={vi.fn()}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Map Styles' }));

    await waitFor(() => {
      expect(screen.getByText('My Custom Style')).toBeInTheDocument();
    });
  });

  it('should show "Custom" as label when customStyleData has no name', async () => {
    const user = userEvent.setup();
    const customStyleData = {
      version: 8 as const,
      sources: {},
      layers: [],
    };

    render(
      <MapStyleControl
        customStyleData={customStyleData}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={vi.fn()}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Map Styles' }));

    await waitFor(() => {
      expect(screen.getByText('Custom')).toBeInTheDocument();
    });
  });

  it('should show EditStylesDialog when custom style is selected', async () => {
    const user = userEvent.setup();
    (utils.getInitialMapStyle as Mock).mockReturnValue('custom');

    const customStyleData = {
      version: 8 as const,
      name: 'My Custom Style',
      sources: {},
      layers: [],
    };

    render(
      <MapStyleControl
        customStyleData={customStyleData}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={vi.fn()}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Map Styles' }));

    await waitFor(() => {
      expect(screen.getByTestId('edit-styles-dialog')).toBeInTheDocument();
    });
  });

  it('should not show EditStylesDialog when custom style is not selected', async () => {
    const user = userEvent.setup();
    const customStyleData = {
      version: 8 as const,
      name: 'My Custom Style',
      sources: {},
      layers: [],
    };

    render(
      <MapStyleControl
        customStyleData={customStyleData}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={vi.fn()}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Map Styles' }));

    await waitFor(() => {
      expect(
        screen.queryByTestId('edit-styles-dialog')
      ).not.toBeInTheDocument();
    });
  });

  it('should call onCustomStyleLoaded when custom style is loaded', async () => {
    const user = userEvent.setup();
    const onCustomStyleLoaded = vi.fn();

    render(
      <MapStyleControl
        customStyleData={null}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={onCustomStyleLoaded}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Map Styles' }));

    await waitFor(() => {
      expect(screen.getByTestId('custom-styles-dialog')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('custom-styles-dialog'));

    await waitFor(() => {
      expect(onCustomStyleLoaded).toHaveBeenCalledWith(
        expect.objectContaining({
          version: 8,
          name: 'Custom Style',
        })
      );
    });
  });

  it('should set selectedStyle to custom when custom style is loaded', async () => {
    const user = userEvent.setup();
    const onStyleChange = vi.fn();

    render(
      <MapStyleControl
        customStyleData={null}
        onStyleChange={onStyleChange}
        onCustomStyleLoaded={vi.fn()}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Map Styles' }));

    await waitFor(() => {
      expect(screen.getByTestId('custom-styles-dialog')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('custom-styles-dialog'));

    await waitFor(() => {
      expect(onStyleChange).toHaveBeenCalledWith('custom');
    });
  });

  it('should call onStyleChange on initial render with initial style', async () => {
    const onStyleChange = vi.fn();

    render(
      <MapStyleControl
        customStyleData={null}
        onStyleChange={onStyleChange}
        onCustomStyleLoaded={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(onStyleChange).toHaveBeenCalledWith('shortbread');
    });
  });

  it('should save initial style to localStorage on mount', async () => {
    render(
      <MapStyleControl
        customStyleData={null}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(localStorageMock[MAP_STYLE_STORAGE_KEY]).toBe('shortbread');
    });
  });

  it('should call onCustomStyleLoaded when edit styles dialog saves', async () => {
    const user = userEvent.setup();
    (utils.getInitialMapStyle as Mock).mockReturnValue('custom');
    const onCustomStyleLoaded = vi.fn();
    const customStyleData = {
      version: 8 as const,
      name: 'My Custom Style',
      sources: {},
      layers: [],
    };

    render(
      <MapStyleControl
        customStyleData={customStyleData}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={onCustomStyleLoaded}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Map Styles' }));

    await waitFor(() => {
      expect(screen.getByTestId('edit-styles-dialog')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('edit-styles-dialog'));

    await waitFor(() => {
      expect(onCustomStyleLoaded).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Edited Style',
        })
      );
    });
  });

  it('should render custom style mini map when customStyleData is provided', async () => {
    const user = userEvent.setup();
    const customStyleData = {
      version: 8 as const,
      name: 'My Custom Style',
      sources: {},
      layers: [],
    };

    render(
      <MapStyleControl
        customStyleData={customStyleData}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={vi.fn()}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Map Styles' }));

    await waitFor(() => {
      expect(screen.getByTestId('map-custom-map')).toBeInTheDocument();
    });
  });

  it('should handle switching between built-in and custom styles', async () => {
    const user = userEvent.setup();
    const onStyleChange = vi.fn();
    const customStyleData = {
      version: 8 as const,
      name: 'My Custom Style',
      sources: {},
      layers: [],
    };

    render(
      <MapStyleControl
        customStyleData={customStyleData}
        onStyleChange={onStyleChange}
        onCustomStyleLoaded={vi.fn()}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Map Styles' }));

    await waitFor(() => {
      expect(screen.getByText('My Custom Style')).toBeInTheDocument();
    });

    const customMap = screen.getByTestId('map-custom-map');
    const customOption = customMap.closest('.cursor-pointer');
    await user.click(customOption!);

    await waitFor(() => {
      expect(onStyleChange).toHaveBeenCalledWith('custom');
      expect(localStorageMock[MAP_STYLE_STORAGE_KEY]).toBe('custom');
    });

    const shortbreadMap = screen.getByTestId('map-shortbread-map');
    const shortbreadOption = shortbreadMap.closest('.cursor-pointer');
    await user.click(shortbreadOption!);

    await waitFor(() => {
      expect(onStyleChange).toHaveBeenCalledWith('shortbread');
      expect(localStorageMock[MAP_STYLE_STORAGE_KEY]).toBe('shortbread');
    });
  });

  it('offers only the campus raster among built-in map styles', async () => {
    render(
      <MapStyleControl
        customStyleData={null}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={vi.fn()}
      />
    );
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: 'Map Styles' }));
    expect(screen.getByText('校园离线底图')).toBeInTheDocument();
    expect(screen.queryByText('Carto')).not.toBeInTheDocument();
    expect(screen.queryByText('Alidade Smooth')).not.toBeInTheDocument();
    expect(MAP_STYLES).toHaveLength(1);
    expect(MAP_STYLES[0].style).toBe('/api/v1/map-style');
  });

  it('previews the single local built-in raster style', async () => {
    render(
      <MapStyleControl
        customStyleData={null}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={vi.fn()}
      />
    );
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: 'Map Styles' }));
    expect(screen.getByTestId('map-shortbread-map')).toBeInTheDocument();
    expect(screen.queryByTestId('map-carto-map')).not.toBeInTheDocument();
    expect(
      screen.queryByTestId('map-alidade-smooth-map')
    ).not.toBeInTheDocument();
  });

  it('highlights the local built-in style selected by the offline initializer', async () => {
    render(
      <MapStyleControl
        customStyleData={null}
        onStyleChange={vi.fn()}
        onCustomStyleLoaded={vi.fn()}
      />
    );
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: 'Map Styles' }));
    expect(screen.getByText('校园离线底图')).toHaveClass(
      'font-bold',
      'text-primary'
    );
    expect(
      screen.getByTestId('map-shortbread-map').closest('.cursor-pointer')
    ).toHaveClass('border-primary');
  });
});
