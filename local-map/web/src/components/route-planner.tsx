import { DirectionsControl } from './directions/directions';
import { CampusPanel, RouteDebugPanel } from './campus-panel';
import { useCommonStore } from '@/stores/common-store';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { X, Footprints } from 'lucide-react';
import { useDirectionsPermalink } from '@/hooks/use-directions-permalink';

export const RoutePlanner = () => {
  const open = useCommonStore((state) => state.directionsPanelOpen);
  const toggleDirections = useCommonStore((state) => state.toggleDirections);
  useDirectionsPermalink(true);

  return (
    <Sheet open={open} modal={false}>
      <SheetContent
        side="left"
        className="campus-sidebar w-[400px] max-w-[calc(100vw-52px)] sm:max-w-[400px] max-h-screen overflow-y-auto gap-3 pb-4"
      >
        <SheetHeader className="justify-between">
          <SheetTitle className="flex items-center gap-2">
            <Footprints className="size-5" />
            校园步行路线
          </SheetTitle>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleDirections}
            aria-label="收起路线面板"
            data-testid="close-directions-button"
          >
            <X className="size-4" />
          </Button>
          <SheetDescription className="sr-only">
            校园离线底图与多途经点步行路线，所有坐标为 GCJ-02
            火星坐标，经度在前。
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-3 px-2 min-w-0">
          <CampusPanel />
          <DirectionsControl />
          <RouteDebugPanel />
          <p className="text-xs text-muted-foreground">
            Valhalla Web App · MIT · © OpenStreetMap contributors / ODbL 1.0
          </p>
        </div>
      </SheetContent>
    </Sheet>
  );
};
