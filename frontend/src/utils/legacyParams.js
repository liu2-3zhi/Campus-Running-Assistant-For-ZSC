export const paramDefs = {
  interval_ms: {
    label: "采样间隔",
    unit: "ms",
    help: "相邻 GPS 点之间的时间间隔，用于模拟上报节奏。",
  },
  interval_random_ms: {
    label: "间隔随机范围",
    unit: "ms",
    help: "在采样间隔的基础上上下浮动的随机抖动幅度。",
  },
  speed_mps: {
    label: "平均速度",
    unit: "m/s",
    help: "生成/处理路径时的目标平均速度。",
  },
  speed_random_mps: {
    label: "速度随机范围",
    unit: "m/s",
    help: "速度的上下浮动范围，用于模拟自然波动。",
  },
  location_random_m: {
    label: "定位随机偏移半径",

    unit: "m",
    help: "对每个 GPS 点施加的随机偏移的半径，模拟定位噪声。",
  },

  task_gap_min_s: {
    label: "任务间隙下限",
    unit: "s",
    help: "连续执行任务之间的最短等待时间。",
  },
  task_gap_max_s: {
    label: "任务间隙上限",
    unit: "s",
    help: "连续执行任务之间的最长等待时间。",
  },

  api_fallback_line: {
    label: "规划失败时使用直线连接",
    unit: "",
    help: "启用后，当某段步行路径规划失败时，使用起终点直线代替。",
  },
  api_retries: {
    label: "API重试次数",
    unit: "次",
    help: "步行路径每一段失败后的重试次数。",
  },

  api_retry_delay_s: {
    label: "API重试间隔",
    unit: "s",
    help: "步行路径失败后发起下一次重试前的等待时间。",
  },
  api_queue_interval_s: {
    label: "API排队间隔",
    unit: "s",
    help: "批量规划多段路径时，相邻请求发起之间的排队间隔。",
  },
  ignore_task_time: {
    label: "忽略任务时间仅对比日期",
    unit: "",
    help: "勾选后，判断任务是否“未开始”或“已过期”时，只对比年月日，忽略具体时分秒。",
  },

  min_time_m: {
    label: "目标时长下限",
    unit: "分钟",
    help: "自动生成路径的总时长最小值。",
  },
  max_time_m: {
    label: "目标时长上限",
    unit: "分钟",
    help: "自动生成路径的总时长最大值。",
  },
  min_dist_m: {
    label: "目标距离下限",
    unit: "m",
    help: "自动生成路径的总距离下限。上限按 1.0–1.15 倍随机浮动。",
  },

  theme_style: {
    label: "界面主题风格",
    unit: "",
    help: "切换应用界面的外观。主题切换后将自动保存。",
    type: "theme_selector",
  },
  theme_base_color: {
    label: "主题基础颜色",
    unit: "",
    help: "界面主色调（点击颜色块进行选择）。",
    type: "color_picker",
  },
  auto_attendance_enabled: {
    label: "开启自动签到",
    unit: "",
    help: "开启后，将在后台自动刷新通知并尝试签到",
    type: "checkbox",
  },
  auto_attendance_stop_after_success: {
    label: "完成指定次数后自动关闭",
    unit: "",
    help: "勾选后，后台成功提交指定次数的新签到任务就会自动关闭自动签到。",
    type: "checkbox",
  },
  auto_attendance_success_limit: {
    label: "自动关闭次数",
    unit: "次",
    help: "达到该成功签到次数后自动关闭，最小值为1。",
    type: "number",
    min: 1,
  },
  auto_attendance_refresh_s: {
    label: "刷新间隔",
    unit: "秒",
    help: "自动刷新通知的间隔时间（秒），最小10秒",
  },
  attendance_user_radius_m: {
    label: "随机半径",
    unit: "米",
    help: "自动签到时，在服务器允许范围内的最大随机偏移半径。设为0为精确签到。",
  },
};

export const paramGroups = [
  {
    title: "采样与速度",
    keys: [
      "interval_ms",
      "interval_random_ms",
      "speed_mps",
      "speed_random_mps",
      "location_random_m",
    ],
  },
  {
    title: "任务间隔",
    keys: ["task_gap_min_s", "task_gap_max_s", "ignore_task_time"],
  },
  {
    title: "路径规划重试策略",
    keys: [
      "api_fallback_line",
      "api_retries",
      "api_retry_delay_s",
      "api_queue_interval_s",
    ],
  },
  {
    title: "自动生成目标",
    keys: ["min_time_m", "max_time_m", "min_dist_m"],
  },
  {
    title: "自动签到",
    keys: [
      "auto_attendance_enabled",
      "auto_attendance_stop_after_success",
      "auto_attendance_success_limit",
      "auto_attendance_refresh_s",
      "attendance_user_radius_m",
    ],
  },
];


