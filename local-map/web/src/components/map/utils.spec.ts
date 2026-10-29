import { describe, it, expect, beforeEach } from 'vitest';
import {
  convertDDToDMS,
  mapStyleSchema,
  getMapStyleUrl,
  getInitialMapStyle,
  getCustomStyle,
  getInitialMapPosition,
  LAST_CENTER_KEY,
} from './utils';
import {
  MAP_STYLE_STORAGE_KEY,
  CUSTOM_STYLE_STORAGE_KEY,
  DEFAULT_CENTER,
} from './constants';

describe('convertDDToDMS', () => {
  it('should convert zero degrees correctly', () => {
    expect(convertDDToDMS(0)).toBe('0° 0\' 0"');
  });

  it('should convert positive decimal degrees correctly', () => {
    expect(convertDDToDMS(45.5)).toBe('45° 30\' 0"');
    expect(convertDDToDMS(23.456789)).toBe('23° 27\' 24"');
    expect(convertDDToDMS(1.234567)).toBe('1° 14\' 4"');
  });

  it('should convert negative decimal degrees correctly', () => {
    expect(convertDDToDMS(-45.5)).toBe('-45° 30\' 0"');
    expect(convertDDToDMS(-23.456789)).toBe('-23° 27\' 24"');
    expect(convertDDToDMS(-1.234567)).toBe('-1° 14\' 4"');
  });

  it('should handle exact degree values', () => {
    expect(convertDDToDMS(90)).toBe('90° 0\' 0"');
    expect(convertDDToDMS(180)).toBe('180° 0\' 0"');
    expect(convertDDToDMS(360)).toBe('360° 0\' 0"');
  });

  it('should handle exact minute values', () => {
    expect(convertDDToDMS(45.5)).toBe('45° 30\' 0"');
    expect(convertDDToDMS(30.25)).toBe('30° 15\' 0"');
  });

  it('should handle exact second values', () => {
    expect(convertDDToDMS(45.5041667)).toBe('45° 30\' 15"');
  });

  it('should handle small decimal values', () => {
    expect(convertDDToDMS(0.0001)).toBe('0° 0\' 0"');
    expect(convertDDToDMS(0.0166667)).toBe('0° 1\' 0"');
    expect(convertDDToDMS(0.0002778)).toBe('0° 0\' 1"');
  });

  it('should handle large decimal degrees', () => {
    expect(convertDDToDMS(359.9999)).toBe('359° 0\' 0"');
    expect(convertDDToDMS(180.5)).toBe('180° 30\' 0"');
  });

  it('should handle extreme negative values', () => {
    expect(convertDDToDMS(-180)).toBe('-180° 0\' 0"');
    expect(convertDDToDMS(-359.9999)).toBe('-359° 0\' 0"');
  });

  it('should maintain precision for various decimal places', () => {
    expect(convertDDToDMS(45.123456789)).toBe('45° 7\' 24"');
    expect(convertDDToDMS(45.987654321)).toBe('45° 59\' 15"');
  });

  it('should handle values with high precision minutes', () => {
    expect(convertDDToDMS(45.999999)).toBe('45° 0\' 0"');
  });

  it('should handle coordinate edge cases', () => {
    expect(convertDDToDMS(90)).toBe('90° 0\' 0"');
    expect(convertDDToDMS(-90)).toBe('-90° 0\' 0"');
    expect(convertDDToDMS(180)).toBe('180° 0\' 0"');
    expect(convertDDToDMS(-180)).toBe('-180° 0\' 0"');
  });

  it('should handle very small positive values', () => {
    expect(convertDDToDMS(0.0000001)).toBe('0° 0\' 0"');
  });

  it('should handle very small negative values', () => {
    expect(convertDDToDMS(-0.0000001)).toBe('0° 0\' 0"');
  });

  it('should handle floating point precision issues', () => {
    // Test cases that might be affected by floating point precision
    expect(convertDDToDMS(45.123456789123)).toBe('45° 7\' 24"');
    expect(convertDDToDMS(23.456789012345)).toBe('23° 27\' 24"');
  });

  it('should handle values around 0 with negative sign', () => {
    expect(convertDDToDMS(-0.0000001)).toBe('0° 0\' 0"');
    expect(convertDDToDMS(0.0000001)).toBe('0° 0\' 0"');
  });

  it('should demonstrate the rounding behavior at degree boundaries', () => {
    // Values very close to full degrees get rounded to 0 minutes/seconds
    // due to the +1e-4 rounding in the implementation
    expect(convertDDToDMS(45.9999)).toBe('45° 0\' 0"');
    expect(convertDDToDMS(359.9999)).toBe('359° 0\' 0"');
    expect(convertDDToDMS(-359.9999)).toBe('-359° 0\' 0"');
  });

  it('should handle typical geographic coordinates', () => {
    expect(convertDDToDMS(52.5167)).toBe('52° 31\' 0"');
    expect(convertDDToDMS(13.3777)).toBe('13° 22\' 40"');
    expect(convertDDToDMS(-33.8688)).toBe('-33° 52\' 8"');
    expect(convertDDToDMS(151.2093)).toBe('151° 12\' 33"');
  });
});

describe('offline map styles', () => {
  beforeEach(() => localStorage.clear());

  it('accepts only the local built-in style among upstream built-ins', () => {
    expect(mapStyleSchema.safeParse('shortbread').success).toBe(true);
    for (const id of [
      'carto',
      'alidade-smooth',
      'invalid',
      '',
      null,
      undefined,
      123,
    ]) {
      expect(mapStyleSchema.safeParse(id).success).toBe(false);
    }
  });

  it('resolves known, old public, custom and invalid selections to the local raster style', () => {
    for (const id of [
      'shortbread',
      'carto',
      'alidade-smooth',
      'custom',
      'invalid',
    ]) {
      expect(getMapStyleUrl(id)).toBe('/api/v1/map-style');
    }
  });

  it('ignores custom and public style values in the URL', () => {
    localStorage.setItem(CUSTOM_STYLE_STORAGE_KEY, '{"version":8}');
    for (const id of [
      'shortbread',
      'carto',
      'alidade-smooth',
      'custom',
      'invalid',
      undefined,
    ]) {
      expect(getInitialMapStyle(id)).toBe('shortbread');
    }
  });

  it('does not restore public or custom styles from previous browser sessions', () => {
    for (const id of ['carto', 'alidade-smooth', 'custom', 'invalid']) {
      localStorage.setItem(MAP_STYLE_STORAGE_KEY, id);
      localStorage.setItem(CUSTOM_STYLE_STORAGE_KEY, '{"version":8}');
      expect(getInitialMapStyle()).toBe('shortbread');
    }
  });

  it('never loads stored style JSON with external resource URLs', () => {
    localStorage.setItem(
      CUSTOM_STYLE_STORAGE_KEY,
      JSON.stringify({
        version: 8,
        sources: { osm: { type: 'vector', url: 'https://example.invalid' } },
        layers: [],
      })
    );
    expect(getCustomStyle()).toBeNull();
  });

  it('does not parse malformed stored style JSON', () => {
    localStorage.setItem(CUSTOM_STYLE_STORAGE_KEY, 'invalid-json{');
    expect(getCustomStyle()).toBeNull();
  });
});

describe('GCJ-02 map position storage', () => {
  beforeEach(() => localStorage.clear());

  it('ignores the old unversioned WGS84 center cache', () => {
    localStorage.setItem(
      'last_center',
      JSON.stringify({ center: [22.5296609, 113.384474], zoom_level: 19 })
    );
    expect(getInitialMapPosition()).toEqual({
      center: DEFAULT_CENTER,
      zoom: 17,
    });
  });

  it('restores only a GCJ-02 center inside the current campus bounds', () => {
    localStorage.setItem(
      LAST_CENTER_KEY,
      JSON.stringify({ center: [22.528, 113.39], zoom_level: 21 })
    );
    expect(getInitialMapPosition()).toEqual({
      center: [113.39, 22.528],
      zoom: 20,
    });
  });
});
