import { z } from 'zod';
import { create } from 'zustand';

const coordinate = z.tuple([
  z.number().finite().min(-180).max(180),
  z.number().finite().min(-90).max(90),
]);
const taskDocument = z.object({
  task_name: z.string().optional(),
  target_point_names: z.string().optional(),
  target_points: z.array(coordinate).min(2),
  recommended_coords: z.array(coordinate).optional(),
});
const metric = z.number().finite().nonnegative();
const metrics = z.object({ distance_m: metric, duration_s: metric });
const line = z.object({
  type: z.literal('Feature'),
  geometry: z.object({
    type: z.literal('LineString'),
    coordinates: z.array(coordinate).min(2),
  }),
});
const lineCollection = z.object({
  type: z.literal('FeatureCollection'),
});
const taskResult = metrics.extend({
  coordinate_system: z.literal('GCJ-02'),
  task_name: z.string(),
  target_points: z.array(z.object({ name: z.string(), coordinate })).min(1),
  route: line.extend({ properties: metrics }),
  recommended_paths: lineCollection.extend({
    features: z.array(
      line.extend({ properties: z.record(z.unknown()).nullable() })
    ),
  }),
  connectors: lineCollection.extend({
    features: z.array(
      line.extend({
        properties: z.object({
          target_index: z.number().int().nonnegative(),
          distance_m: metric,
        }),
      })
    ),
  }),
});

export type TaskPlan = z.infer<typeof taskResult>;
export type TaskCoordinate = z.infer<typeof coordinate>;

interface TaskPlannerStore {
  fileName: string;
  plan: TaskPlan | null;
  showTask: boolean;
  loading: boolean;
  error: string;
  importTask: (file: File) => Promise<void>;
  clearTask: () => void;
  setShowTask: (visible: boolean) => void;
}

export const useTaskPlannerStore = create<TaskPlannerStore>((set) => {
  let pending: AbortController | undefined;
  return {
    fileName: '',
    plan: null,
    showTask: false,
    loading: false,
    error: '',
    async importTask(file) {
      pending?.abort();
      const request = new AbortController();
      pending = request;
      set({ loading: true, error: '' });

      try {
        let input: unknown;
        try {
          input = JSON.parse((await file.text()).replace(/^\uFEFF/, ''));
        } catch {
          throw new Error('无法读取任务文件，请选择有效的 JSON 文件。');
        }
        if (request.signal.aborted) return;
        const task = taskDocument.safeParse(input);
        if (!task.success) {
          throw new Error('任务坐标格式无效，请检查目标点和推荐路线。');
        }
        const response = await fetch('/api/v1/tasks/plan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(task.data),
          signal: request.signal,
        }).catch(() => {
          throw new Error('无法连接本地任务规划服务，请重新导入。');
        });
        if (!response.ok) {
          if (response.status === 422) {
            throw new Error('任务坐标超出地图范围或任务格式无效。');
          }
          if (response.status === 404) {
            throw new Error('校园路网无法连接任务中的所有目标点。');
          }
          throw new Error('本地任务规划服务暂不可用，请重新导入。');
        }
        const plan = taskResult.safeParse(
          await response.json().catch(() => null)
        );
        if (!plan.success) {
          throw new Error('本地服务返回的任务路线格式无效。');
        }
        if (!request.signal.aborted) {
          const target_points = plan.data.target_points.map(
            (target, index) => ({
              ...target,
              name: target.name.trim() || `打卡点 ${index + 1}`,
            })
          );
          set({
            fileName: file.name,
            plan: { ...plan.data, target_points },
            showTask: true,
          });
        }
      } catch (error) {
        if (!request.signal.aborted) {
          set({
            error: error instanceof Error ? error.message : String(error),
          });
        }
      } finally {
        if (pending === request) {
          pending = undefined;
          set({ loading: false });
        }
      }
    },
    clearTask() {
      pending?.abort();
      pending = undefined;
      set({
        fileName: '',
        plan: null,
        showTask: false,
        loading: false,
        error: '',
      });
    },
    setShowTask: (showTask) => set({ showTask }),
  };
});
