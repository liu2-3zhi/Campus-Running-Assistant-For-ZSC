import { create } from 'zustand';

interface RouteTrace {
  request: unknown;
  response: unknown;
  elapsedMs: number | null;
  status: string;
  error: string;
}

export const useRouteDebugStore = create<RouteTrace>(() => ({
  request: null,
  response: null,
  elapsedMs: null,
  status: '尚未请求',
  error: '',
}));
