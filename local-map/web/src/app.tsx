import { MapProvider } from 'react-map-gl/maplibre';
import { MapComponent } from './components/map';
import { RoutePlanner } from './components/route-planner';
import { Toaster } from '@/components/ui/sonner';

export const App = () => {
  return (
    <MapProvider>
      <MapComponent />
      <RoutePlanner />
      <Toaster position="bottom-center" duration={5000} richColors />
    </MapProvider>
  );
};
