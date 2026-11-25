import { useRef } from 'react';
import { ArrowLeft, FileUp, MapIcon, Route, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useCommonStore } from '@/stores/common-store';
import { useTaskPlannerStore } from '@/stores/task-planner-store';
import { formatDuration } from '@/utils/date-time';

export function TaskPlanner() {
  const {
    fileName,
    plan,
    showTask,
    loading,
    error,
    importTask,
    clearTask,
    setShowTask,
  } = useTaskPlannerStore();
  const toggleDirections = useCommonStore((state) => state.toggleDirections);
  const fileInput = useRef<HTMLInputElement>(null);
  const connectorByTarget = new Map(
    plan?.connectors.features.map(({ properties }) => [
      properties.target_index,
      properties.distance_m,
    ])
  );

  return (
    <section
      aria-labelledby="task-planner-title"
      className="rounded-md border p-2 text-sm flex flex-col gap-2"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="task-planner-title" className="font-semibold">
          任务规划
        </h2>
        <input
          ref={fileInput}
          type="file"
          accept=".json,application/json"
          aria-label="导入任务 JSON"
          hidden
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = '';
            if (file) void importTask(file);
          }}
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => fileInput.current?.click()}
        >
          <FileUp />
          导入任务 JSON
        </Button>
      </div>
      {loading && <p role="status">正在规划任务路线…</p>}
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      {(plan || loading || error) && (
        <div className="flex flex-wrap items-center gap-2">
          {plan && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setShowTask(!showTask)}
            >
              {showTask ? <ArrowLeft /> : <Route />}
              {showTask ? '返回步行路线' : '查看任务路线'}
            </Button>
          )}
          <Button type="button" size="sm" variant="ghost" onClick={clearTask}>
            <X />
            清除任务
          </Button>
        </div>
      )}
      {plan && showTask && (
        <div className="flex flex-col gap-2" data-testid="task-plan-result">
          <Button
            type="button"
            size="sm"
            className="self-start sm:hidden"
            onClick={toggleDirections}
          >
            <MapIcon />
            查看地图
          </Button>
          <h3 className="font-semibold break-all">
            {plan.task_name || fileName}
          </h3>
          <p role="status" className="text-muted-foreground tabular-nums">
            {Math.round(plan.distance_m)} 米 · 预计{' '}
            {formatDuration(Math.round(plan.duration_s)) || '0秒'}
          </p>
          <ul
            aria-label="地图图例"
            className="flex flex-wrap gap-x-3 gap-y-1 text-xs"
          >
            <li className="inline-flex items-center gap-1.5">
              <span className="w-4 border-t-3 border-[#006FAD]" />
              任务路线
            </li>
            {plan.recommended_paths.features.length > 0 && (
              <li className="inline-flex items-center gap-1.5">
                <span className="w-4 border-t-3 border-[#008566]" />
                推荐小路
              </li>
            )}
            {connectorByTarget.size > 0 && (
              <li className="inline-flex items-center gap-1.5">
                <span className="w-4 border-t-3 border-dashed border-[#BA4C19]" />
                直线补接
              </li>
            )}
          </ul>
          <ol
            aria-label="打卡顺序"
            className="list-decimal space-y-1 border-t pt-2 pl-6"
          >
            {plan.target_points.map(({ name }, index) => {
              const connector = connectorByTarget.get(index);
              return (
                <li key={index} className="break-all marker:font-medium">
                  {name}
                  {connector !== undefined && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      直线 {connector.toFixed(1)} 米
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </section>
  );
}
