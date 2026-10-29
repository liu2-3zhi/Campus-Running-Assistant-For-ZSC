import { act, render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GcjGeolocateControl } from './gcj-geolocate-control';

const mocks = vi.hoisted(() => ({
  onSuccess: vi.fn(),
  convert: vi.fn(),
  control: null as {
    _onSuccess: (position: GeolocationPosition) => void;
  } | null,
}));

vi.mock('@/utils/gps', () => ({ convertGpsPosition: mocks.convert }));
vi.mock('react-map-gl/maplibre', async () => {
  const React = await import('react');
  return {
    GeolocateControl: React.forwardRef((_props, ref) => {
      const control = React.useMemo(
        () => ({ _onSuccess: mocks.onSuccess }),
        []
      );
      mocks.control = control;
      React.useImperativeHandle(ref, () => control, [control]);
      return null;
    }),
  };
});

describe('MapLibre 5.15 GCJ-02 GPS adapter', () => {
  beforeEach(() => vi.clearAllMocks());

  it('converts before the upstream marker/camera callback and restores it on removal', async () => {
    const native = {
      coords: { longitude: 113.3865167, latitude: 22.5319451 },
    } as GeolocationPosition;
    const calibrated = {
      coords: { longitude: 113.391999, latitude: 22.529255 },
    } as GeolocationPosition;
    mocks.convert.mockResolvedValue(calibrated);
    const view = render(<GcjGeolocateControl />);
    const control = mocks.control!;
    await act(async () => control._onSuccess(native));
    expect(mocks.convert).toHaveBeenCalledExactlyOnceWith(native);
    expect(mocks.onSuccess).toHaveBeenCalledExactlyOnceWith(calibrated);
    view.unmount();
    expect(control._onSuccess).toBe(mocks.onSuccess);
  });

  it('does not update a removed control after asynchronous conversion finishes', async () => {
    let complete!: (position: GeolocationPosition) => void;
    mocks.convert.mockImplementation(
      () =>
        new Promise<GeolocationPosition>((resolve) => {
          complete = resolve;
        })
    );
    const view = render(<GcjGeolocateControl />);
    mocks.control!._onSuccess({} as GeolocationPosition);
    view.unmount();
    await act(async () => complete({} as GeolocationPosition));
    expect(mocks.onSuccess).not.toHaveBeenCalled();
  });
});
