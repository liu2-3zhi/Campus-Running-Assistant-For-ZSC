import { useCallback, useRef } from 'react';
import type maplibregl from 'maplibre-gl';
import {
  GeolocateControl,
  type GeolocateControlProps,
} from 'react-map-gl/maplibre';
import { convertGpsPosition } from '@/utils/gps';

export function GcjGeolocateControl(props: GeolocateControlProps) {
  const activeControl = useRef<maplibregl.GeolocateControl | null>(null);
  const originalCallback = useRef<
    ((position: GeolocationPosition) => void) | null
  >(null);
  const latestPosition = useRef(0);
  const connectControl = useCallback(
    (control: maplibregl.GeolocateControl | null) => {
      if (activeControl.current && originalCallback.current) {
        activeControl.current._onSuccess = originalCallback.current;
      }
      activeControl.current = control;
      originalCallback.current = control?._onSuccess ?? null;
      latestPosition.current += 1;
      if (!control) return;

      // MapLibre 5.15 has no geolocation option; convert before its marker/camera callback.
      const onSuccess = control._onSuccess;
      control._onSuccess = (position) => {
        const sequence = ++latestPosition.current;
        void convertGpsPosition(position).then((converted) => {
          if (
            activeControl.current === control &&
            sequence === latestPosition.current
          ) {
            onSuccess(converted);
          }
        });
      };
    },
    []
  );

  return <GeolocateControl {...props} ref={connectControl} />;
}
