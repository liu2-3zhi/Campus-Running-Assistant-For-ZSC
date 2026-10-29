import { z } from 'zod';
import type maplibregl from 'maplibre-gl';
import {
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  MAP_STYLES,
  MAP_STYLE_IDS,
  DEFAULT_MAP_STYLE,
  DEFAULT_MAP_STYLE_ID,
  maxBounds,
} from './constants';
import type { MapStyleType } from './types';

export const LAST_CENTER_KEY = 'campus.gcj02.last_center';

export const mapStyleSchema = z.enum([
  ...MAP_STYLE_IDS,
  'custom',
] as unknown as [string, ...string[]]);

export const getMapStyleUrl = (styleId: string): string => {
  const found = MAP_STYLES.find((s) => s.id === styleId);
  return found?.style ?? DEFAULT_MAP_STYLE;
};

export const getInitialMapStyle = (_urlValue?: string): MapStyleType => {
  // This offline distribution never restores imported or online styles.
  return DEFAULT_MAP_STYLE_ID;
};

export const getCustomStyle = (): maplibregl.StyleSpecification | null => {
  return null;
};

export const convertDDToDMS = (decimalDegrees: number): string => {
  const absDegrees =
    (decimalDegrees < 0 ? -decimalDegrees : decimalDegrees) + 1e-4;

  const minutes = Math.floor((absDegrees % 1) * 60);
  const seconds = Math.floor(((absDegrees * 60) % 1) * 60);

  return `${0 | decimalDegrees}° ${minutes}' ${seconds}"`;
};

const isValidCoordinates = (lng: unknown, lat: unknown): boolean =>
  typeof lng === 'number' &&
  typeof lat === 'number' &&
  lng >= -180 &&
  lng <= 180 &&
  lat >= -90 &&
  lat <= 90;

const parseLastCenter = (
  data: unknown
): { center: [number, number]; zoom: number } | null => {
  if (!data || typeof data !== 'object') return null;

  const obj = data as Record<string, unknown>;
  const { center, zoom_level } = obj;

  if (!Array.isArray(center) || center.length !== 2) return null;
  if (typeof zoom_level !== 'number') return null;
  if (!isValidCoordinates(center[1], center[0])) return null;

  return {
    center: [center[1] as number, center[0] as number],
    zoom: zoom_level,
  };
};

export const getInitialMapPosition = (): {
  center: [number, number];
  zoom: number;
} => {
  const defaults = { center: DEFAULT_CENTER, zoom: DEFAULT_ZOOM };

  try {
    const stored = localStorage.getItem(LAST_CENTER_KEY);
    if (!stored) return defaults;

    const parsed = parseLastCenter(JSON.parse(stored));
    if (
      parsed &&
      parsed.center[0] >= maxBounds[0][0] &&
      parsed.center[0] <= maxBounds[1][0] &&
      parsed.center[1] >= maxBounds[0][1] &&
      parsed.center[1] <= maxBounds[1][1]
    ) {
      return {
        center: parsed.center,
        zoom: Math.max(14, Math.min(20, parsed.zoom)),
      };
    }

    console.warn('Invalid coordinates in localStorage, using defaults');
    localStorage.removeItem(LAST_CENTER_KEY);
  } catch {
    console.warn('Invalid localStorage data, using defaults');
    localStorage.removeItem(LAST_CENTER_KEY);
  }

  return defaults;
};
