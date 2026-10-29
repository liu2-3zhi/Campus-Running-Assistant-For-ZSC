import { afterEach, describe, expect, it, vi } from 'vitest';
import { convertGpsPosition } from './gps';

function nativePosition(): GeolocationPosition {
  const coordinatePrototype = {
    get longitude() {
      return 113.3865167;
    },
    get latitude() {
      return 22.5319451;
    },
    get accuracy() {
      return 4;
    },
    get altitude() {
      return 25;
    },
    get altitudeAccuracy() {
      return 3;
    },
    get heading() {
      return 180;
    },
    get speed() {
      return 1.2;
    },
  };
  return {
    coords: Object.create(coordinatePrototype),
    timestamp: 1234,
  } as GeolocationPosition;
}

describe('calibrated GPS positions', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('uses the same-origin calibrated point and preserves native prototype fields', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        coordinate_system: 'GCJ-02',
        points: [[113.391999, 22.529255]],
        method: 'amap-calibration',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const converted = await convertGpsPosition(nativePosition());
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/coordinates/gps',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ points: [[113.3865167, 22.5319451]] }),
      })
    );
    expect(converted.coords).toMatchObject({
      longitude: 113.391999,
      latitude: 22.529255,
      accuracy: 4,
      altitude: 25,
      altitudeAccuracy: 3,
      heading: 180,
      speed: 1.2,
    });
    expect(converted.timestamp).toBe(1234);
    expect(converted.toJSON()).toMatchObject({
      timestamp: 1234,
      coords: { longitude: 113.391999, accuracy: 4 },
    });
  });

  it('keeps offline GPS usable when the local calibration service is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    const converted = await convertGpsPosition(nativePosition());
    expect(converted.coords.longitude).toBeCloseTo(113.391997, 5);
    expect(converted.coords.latitude).toBeCloseTo(22.529253, 5);
  });

  it('rejects a malformed or wrong-datum conversion response', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue({
          ok: true,
          json: async () => ({ coordinate_system: 'WGS84', points: [[0, 0]] }),
        })
    );
    const converted = await convertGpsPosition(nativePosition());
    expect(converted.coords.longitude).toBeCloseTo(113.391997, 5);
    expect(converted.coords.latitude).toBeCloseTo(22.529253, 5);
  });
});
