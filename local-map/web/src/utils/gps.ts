import { wgs84ToGcj02 } from './coordinates';

export async function convertGpsPosition(
  position: GeolocationPosition
): Promise<GeolocationPosition> {
  const { longitude, latitude } = position.coords;
  let point = wgs84ToGcj02(longitude, latitude);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1500);
  try {
    const response = await fetch('/api/v1/coordinates/gps', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ points: [[longitude, latitude]] }),
      signal: controller.signal,
    });
    if (response.ok) {
      const conversion = await response.json();
      const converted = conversion.points?.[0];
      if (
        conversion.coordinate_system === 'GCJ-02' &&
        Array.isArray(converted) &&
        converted.length === 2 &&
        converted.every(
          (value: unknown) =>
            typeof value === 'number' && Number.isFinite(value)
        ) &&
        Math.abs(converted[0]) <= 180 &&
        Math.abs(converted[1]) <= 90
      ) {
        point = [converted[0], converted[1]];
      }
    }
  } catch {
    // The local forward formula keeps GPS usable without the calibration API.
  } finally {
    clearTimeout(timeout);
  }

  // Native coordinate fields may be prototype getters rather than own properties.
  const coordinates = {
    longitude: point[0],
    latitude: point[1],
    accuracy: position.coords.accuracy,
    altitude: position.coords.altitude,
    altitudeAccuracy: position.coords.altitudeAccuracy,
    heading: position.coords.heading,
    speed: position.coords.speed,
  };
  return {
    coords: { ...coordinates, toJSON: () => coordinates },
    timestamp: position.timestamp,
    toJSON: () => ({ coords: coordinates, timestamp: position.timestamp }),
  };
}
