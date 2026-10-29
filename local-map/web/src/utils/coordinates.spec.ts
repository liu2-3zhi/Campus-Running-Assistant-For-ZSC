import { describe, expect, it } from 'vitest';
import { wgs84ToGcj02 } from './coordinates';

describe('GPS coordinate conversion', () => {
  it('converts WGS84 GPS once into the GCJ-02 campus coordinate range', () => {
    const converted = wgs84ToGcj02(113.3865167, 22.5319451);
    expect(converted[0]).toBeCloseTo(113.391997, 5);
    expect(converted[1]).toBeCloseTo(22.529253, 5);
  });

  it('leaves coordinates outside China unchanged', () => {
    expect(wgs84ToGcj02(13.4, 52.5)).toEqual([13.4, 52.5]);
  });
});
