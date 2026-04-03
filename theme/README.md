# 主题文件标准规范

## 目录结构

```
theme/
├── README.md          ← 本规范文件
├── _schema.json       ← JSON Schema 校验文件
├── default.json       ← 默认主题（蓝白渐变）
├── minimalist.json    ← 极简风
├── corporate.json     ← 商务专业风
├── creative.json      ← 创意艺术风
├── tech.json          ← 科技未来风
├── anime.json         ← 二次元/动漫风
└── retro.json         ← 复古风
```

---

## 主题文件 JSON 规范

每个主题文件为独立的 `.json` 文件，遵循以下结构：

```jsonc
{
  // === 元信息 ===
  "id": "minimalist",                  // 唯一标识符（lowercase, 无空格）
  "name": "极简风 (Minimalist)",        // 显示名称
  "description": "简洁排版、大量留白，突出内容本身", // 简短描述
  "icon": "✨",                         // 代表性 emoji 图标
  "version": "1.0.0",                  // 主题版本
  "tags": ["clean", "modern"],         // 分类标签

  // === 预览色板（用于主题选择器 UI 展示）===
  "preview": {
    "primary":    "#3b82f6",           // 主色调
    "accent":     "#0066ff",           // 强调色
    "background": "#f8f9fa",           // 背景色
    "surface":    "#ffffff",           // 卡片/面板色
    "text":       "#1a1a1a"            // 主文字色
  },

  // === CSS 变量覆盖 ===
  // 所有变量会通过 JS 动态注入到 :root 中
  "variables": {
    // 主题色系
    "--base-color":       "#7dd3fc",   // 主题基色（用于高亮、焦点等）
    "--base-color-600":   "#0284c7",   // 主题深色（hover、active）
    "--base-color-500":   "#0ea5e9",   // 主题中色
    "--base-color-300":   "#7dd3fc",   // 主题浅色

    // 背景与表面
    "--bg-page":          "#f0f6ff",   // 页面背景（渐变起点）
    "--bg-page-mid":      "#e8f0ff",   // 页面背景（渐变中点）
    "--bg-page-end":      "#f0e8ff",   // 页面背景（渐变终点）
    "--card-bg":          "rgba(255,255,255,0.85)", // 卡片背景（可带透明度）
    "--glass":            "rgba(255,255,255,0.65)", // 玻璃态背景
    "--surface-1":        "#f8fafc",   // 次级表面（输入框背景）
    "--surface-2":        "#ffffff",   // 主表面（卡片内部）

    // 边框
    "--border-color":     "#e2e8f0",   // 主边框色
    "--border-light":     "#f1f5f9",   // 轻边框色

    // 文字
    "--ink":              "#0f172a",   // 主要文字色
    "--text-primary":     "#1e293b",   // 标题文字
    "--text-secondary":   "#64748b",   // 次级文字
    "--text-muted":       "#94a3b8",   // 弱化文字

    // 圆角
    "--radius-xs":        "4px",
    "--radius-sm":        "8px",
    "--radius-md":        "12px",
    "--radius-lg":        "16px",
    "--radius-xl":        "20px",
    "--radius-2xl":       "24px",

    // 阴影
    "--shadow-xs":        "0 1px 2px rgba(0,0,0,0.05)",
    "--shadow-sm":        "0 2px 8px rgba(0,0,0,0.08)",
    "--shadow-md":        "0 4px 12px rgba(0,0,0,0.10)",
    "--shadow-lg":        "0 10px 24px rgba(16,24,40,0.12)",

    // 模糊
    "--blur-panel":       "16px",      // 面板背景模糊

    // 渐变装饰条（modal 顶部彩条）
    "--accent-gradient":  "linear-gradient(90deg,#38bdf8,#818cf8)"
  },

  // === Body 类名 ===
  "bodyClasses": ["theme-minimalist"],  // 应用到 <body> 的类（用于覆盖特有样式）

  // === 是否启用深色模式 ===
  "darkMode": false,

  // === 背景图（可选；anime 主题使用）===
  "backgroundImage": null,             // URL 字符串或 null

  // === 字体（可选；使用 Google Fonts 或系统字体）===
  "fontFamily": null                   // CSS font-family 字符串或 null
}
```

---

## CSS 变量使用规范

在 `styles/style.css` 中，所有组件应优先使用以下语义化变量，而非硬编码颜色：

| 变量名 | 用途 |
|--------|------|
| `--base-color` | 主题主色（聚焦环、active 状态等）|
| `--card-bg` | 面板/卡片背景 |
| `--glass` | 毛玻璃背景 |
| `--surface-1` | 输入框、次级区域背景 |
| `--surface-2` | 卡片内部白色区域 |
| `--border-color` | 通用边框 |
| `--border-light` | 轻量边框（卡片内分割线）|
| `--ink` | 主要文字颜色 |
| `--text-secondary` | 次级说明文字 |
| `--radius-md` | 标准圆角 |
| `--shadow-md` | 标准阴影 |
| `--blur-panel` | 面板毛玻璃模糊量 |
| `--accent-gradient` | 渐变装饰条 |

---

## 主题加载流程

```
页面加载
  └─ loadTheme(themeId)         // JS: 获取 theme/{id}.json
       ├─ fetch("theme/{id}.json")
       ├─ applyCssVariables(vars) // 注入到 :root
       ├─ applyBodyClasses(classes)
       ├─ applyBackground(image)
       └─ applyFont(family)
```

JS 函数位于 `scripts/main.new.js` 中的 `loadTheme()` / `applyTheme()`。

---

## 新增主题步骤

1. 复制 `theme/default.json` → `theme/your-theme-id.json`
2. 修改 `id`、`name`、`description`、`icon`
3. 调整 `variables` 中的颜色、圆角、阴影值
4. 在 `styles/style.css` 中添加 `body.your-theme-id { ... }` 类（仅当需要特殊覆盖时）
5. 主题会自动出现在管理面板的"主题选择器"中

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-04-03 | 初始规范，支持 6 种主题 |
