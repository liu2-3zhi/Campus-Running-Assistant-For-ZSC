import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TaskPlanner } from './task-planner';
import { useTaskPlannerStore } from '@/stores/task-planner-store';

const first = [113.39, 22.528];
const join = [113.391, 22.529];
const target = [113.392, 22.529];
const coordinates = [first, join, target, join, first];
const input = {
  task_name: '校园任务',
  target_point_names: '起点|体育馆|起点',
  target_points: [first, target, first],
  recommended_coords: [first, join],
};
const responseBody = {
  coordinate_system: 'GCJ-02',
  task_name: input.task_name,
  target_points: input.target_points.map((coordinate, index) => ({
    coordinate,
    name: input.target_point_names.split('|')[index],
  })),
  distance_m: 350,
  duration_s: 250,
  route: {
    type: 'Feature',
    geometry: { type: 'LineString', coordinates },
    properties: { distance_m: 350, duration_s: 250 },
  },
  recommended_paths: {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: input.recommended_coords },
        properties: {},
      },
    ],
  },
  connectors: {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: [join, target] },
        properties: { target_index: 1, distance_m: 12 },
      },
    ],
  },
};

function fileWith(content: string) {
  return Object.assign(
    new File([content], 'task_export.json', { type: 'application/json' }),
    { text: async () => content }
  );
}

function resultResponse(body = responseBody) {
  return new Response(JSON.stringify(body), { status: 200 });
}

describe('task route import', () => {
  afterEach(() => {
    act(() => useTaskPlannerStore.getState().clearTask());
    vi.unstubAllGlobals();
  });

  it('imports route fields and preserves repeated checkpoints when switching route views', async () => {
    const fetchMock = vi.fn().mockImplementation(async () => resultResponse());
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();
    render(<TaskPlanner />);
    const fileInput = screen.getByLabelText('导入任务 JSON');
    await user.upload(
      fileInput,
      fileWith(JSON.stringify({ ...input, 'run_coords (gps)': [first, join] }))
    );
    await screen.findByRole('heading', { name: '校园任务' });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/tasks/plan',
      expect.objectContaining({ method: 'POST', body: JSON.stringify(input) })
    );
    const list = screen.getByRole('list', { name: '打卡顺序' });
    expect(
      within(list)
        .getAllByRole('listitem')
        .map((item) => item.textContent)
    ).toEqual(['起点', '体育馆直线 12.0 米', '起点']);
    expect(screen.getByText('350 米 · 预计 4分 10秒')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '返回步行路线' }));
    expect(screen.queryByTestId('task-plan-result')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '查看任务路线' }));
    expect(screen.getByTestId('task-plan-result')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledOnce();

    await user.click(screen.getByRole('button', { name: '清除任务' }));
    expect(screen.queryByTestId('task-plan-result')).not.toBeInTheDocument();
  });

  it('reports failed imports and permits selecting the same file again', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('{}', { status: 422 }))
      .mockImplementationOnce(async () =>
        resultResponse({
          ...responseBody,
          target_points: [
            { coordinate: first, name: '' },
            ...responseBody.target_points.slice(1),
          ],
        })
      );
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();
    const file = fileWith(JSON.stringify(input));
    render(<TaskPlanner />);
    const fileInput = screen.getByLabelText('导入任务 JSON');

    await user.upload(fileInput, fileWith('not JSON'));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '有效的 JSON 文件'
    );
    expect(fetchMock).not.toHaveBeenCalled();
    await user.upload(fileInput, file);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '坐标超出地图范围'
    );
    await user.upload(fileInput, file);
    expect(await screen.findByTestId('task-plan-result')).toBeInTheDocument();
    expect(screen.getByText('打卡点 1')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('ignores a request resolved after its task was cleared', async () => {
    let respond!: (response: Response) => void;
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          respond = resolve;
        })
    );
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();
    render(<TaskPlanner />);
    await user.upload(
      screen.getByLabelText('导入任务 JSON'),
      fileWith(JSON.stringify(input))
    );
    expect(await screen.findByRole('status')).toHaveTextContent(
      '正在规划任务路线'
    );

    await user.click(screen.getByRole('button', { name: '清除任务' }));
    await act(async () => respond(resultResponse()));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByTestId('task-plan-result')).not.toBeInTheDocument();
  });
});
