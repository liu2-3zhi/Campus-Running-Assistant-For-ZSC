const centerCoords = import.meta.env.VITE_CENTER_COORDS?.split(',') || [];

export const DEFAULT_CENTER: [number, number] = [
  parseFloat(centerCoords[1] || '113.38995276699997'),
  parseFloat(centerCoords[0] || '22.526967288038794'),
];

export const DEFAULT_ZOOM = 17;

export const maxBounds: [[number, number], [number, number]] = [
  [113.3852747260368, 22.522802343443914],
  [113.39558244764372, 22.53281022147416],
];

export const routeObjects = {
  color: '#3b82f6',
  alternativeColor: '#66a3ff',
  inactiveColor: '#66a3ff',
};

export const MAP_STYLE_STORAGE_KEY = 'campus.gcj02.selectedMapStyle';
export const CUSTOM_STYLE_STORAGE_KEY = 'campus.gcj02.customMapStyle';

export const MAP_STYLES = [
  {
    id: 'shortbread',
    label: '校园离线底图',
    style: '/api/v1/map-style',
  },
] as const;

export const DEFAULT_MAP_STYLE = MAP_STYLES[0].style;
export const DEFAULT_MAP_STYLE_ID = MAP_STYLES[0].id;
export const MAP_STYLE_IDS = MAP_STYLES.map((s) => s.id);
export const CLICK_DELAY_MS = 200;
export const DOUBLE_TAP_THRESHOLD_MS = 300;
