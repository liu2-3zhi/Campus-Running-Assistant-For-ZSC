import { useCallback } from 'react';
import {
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  arrayMove,
} from '@dnd-kit/sortable';

import { Waypoint } from './waypoint-item';
import { useDirectionsStore } from '@/stores/directions-store';
import { useDirectionsQuery } from '@/hooks/use-directions-queries';

export const Waypoints = () => {
  const { refetch: refetchDirections } = useDirectionsQuery();
  const waypoints = useDirectionsStore((state) => state.waypoints);
  const setWaypoint = useDirectionsStore((state) => state.setWaypoint);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const onDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;

      // dropped outside the list
      if (!over || active.id === over.id) {
        return;
      }

      const oldIndex = waypoints.findIndex((wp) => wp.id === active.id);
      const newIndex = waypoints.findIndex((wp) => wp.id === over.id);

      if (oldIndex !== -1 && newIndex !== -1) {
        const items = arrayMove(waypoints, oldIndex, newIndex);
        setWaypoint(items);
        refetchDirections();
      }
    },
    [setWaypoint, refetchDirections, waypoints]
  );

  return (
    <DndContext
      sensors={sensors}
      onDragEnd={onDragEnd}
      accessibility={{
        announcements: {
          onDragStart({ active }) {
            const waypointIndex =
              waypoints.findIndex((wp) => wp.id === active.id) + 1;
            return `已拾取路线点 ${waypointIndex}。方向键移动，空格放置，Escape 取消。`;
          },
          onDragOver({ active, over }) {
            if (!over) return '';
            const activeIndex =
              waypoints.findIndex((wp) => wp.id === active.id) + 1;
            const overIndex =
              waypoints.findIndex((wp) => wp.id === over.id) + 1;
            if (activeIndex !== overIndex) {
              return `将路线点 ${activeIndex} 移至位置 ${overIndex}。`;
            }
            return '';
          },
          onDragEnd({ active, over }) {
            if (!over || active.id === over.id) {
              return '已取消拖动，路线点已回到原位。';
            }
            const activeIndex =
              waypoints.findIndex((wp) => wp.id === active.id) + 1;
            const newIndex = waypoints.findIndex((wp) => wp.id === over.id) + 1;
            return `路线点 ${activeIndex} 已移至位置 ${newIndex}。`;
          },
          onDragCancel({ active }) {
            const waypointIndex =
              waypoints.findIndex((wp) => wp.id === active.id) + 1;
            return `已取消拖动，路线点 ${waypointIndex} 已回到原位。`;
          },
        },
      }}
    >
      <SortableContext
        items={waypoints.map((wp) => wp.id)}
        strategy={verticalListSortingStrategy}
      >
        <div
          role="list"
          aria-label="路线点列表"
          className="flex flex-col gap-2"
        >
          {waypoints.map((wp, index) => (
            <Waypoint key={wp.id} id={wp.id} index={index} />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
};
