# UI 与主题系统重构设计

- 日期：2026-04-11
- 主题：以 `ui/` 为唯一主题来源重构真实前后台 UI，并重建 `theme/` 主题系统
- 状态：已完成方案确认，待用户审阅书面规格

## 1. 背景

当前仓库已经在 `ui/` 下提供了成套静态预览，包括：

- `default-login.html` / `default-admin.html`
- `neo-minimal-login.html` / `neo-minimal-admin.html`
- `cyber-grid-login.html` / `cyber-grid-admin.html`
- `eastern-calm-login.html` / `eastern-calm-admin.html`
- `editorial-magazine-login.html` / `editorial-magazine-admin.html`
- `luxe-noir-login.html` / `luxe-noir-admin.html`

这些文件已经定义了每个主题的视觉人格、桌面端与移动端结构、亮暗模式方向和组件气质。

而当前运行时主题系统 `theme/` 中的主题集合、元信息和视觉变量已经与 `ui/` 不一致：

1. `theme/` 里仍保留旧主题（如 `anime`、`retro`、`corporate` 等）；
2. `default` 主题仍是旧的“中性默认样式”，而不是当前 `ui/default-*` 对应的 Anime Core；
3. 现有主题变量主要服务登录页，没有完整覆盖前台主容器与后台主容器；
4. 默认主题随机背景图虽然已有绑定机制，但作用范围主要集中在登录页。

本轮设计的目标不是继续补丁式修正，而是做一次完整对齐：

- 以 `ui/` 为唯一主题来源；
- 用 `ui/` 覆盖 `theme/`；
- 让真实运行页对齐 `ui/` 的 6 套主题视觉；
- 扩展默认主题随机背景图到登录页、前台主容器和后台主容器；
- 保留现有业务逻辑、会话逻辑与背景绑定语义。

## 2. 已确认范围

本次设计范围已经明确如下：

1. 所有主题都以 `ui/` 中的预览文件为准。
2. 不只是默认主题，所有主题都要落地到真实运行页面。
3. 桌面端与移动端都要一起适配。
4. 允许调整真实页面的展示层 DOM 结构，但必须保留现有功能与接口语义。
5. 默认主题随机背景图继续沿用现有背景绑定规则。
6. 默认主题随机背景图的作用范围扩展到：
   - 登录页
   - 前台主容器
   - 后台主容器
7. `theme/` 必须被 `ui/` 覆盖：
   - `ui/` 中存在的主题要在 `theme/` 中存在；
   - `ui/` 中不存在的旧主题要从 `theme/` 删除。
8. `theme/` 中每个主题文件的以下元信息都必须重新编写，不继承旧值：
   - `id`
   - `label`
   - `description`
   - `svg`

## 3. 目标

本次改造的目标是建立一套真正可运行的、与静态预览一致的主题系统，使得：

1. 主题选择列表与 `ui/` 完全一致；
2. 登录页、前台主容器、后台主容器都能呈现对应主题人格；
3. 同一主题在桌面端和移动端都有成体系的表达，而不是简单换色；
4. 默认主题的背景图在登录页 / 前台 / 后台之间保持同 target 一致；
5. 整个改造尽量不破坏现有业务逻辑、会话流程和主题加载链路。

## 4. 非目标

本阶段不包含以下内容：

1. 不重写登录、注册、2FA、短信登录等业务接口。
2. 不重写地图、跑步任务、多账号等核心业务逻辑。
3. 不把 `ui/*.html` 直接作为运行时模板页面。
4. 不重新设计默认主题随机背景图的缓存来源、拉取策略或 TTL 语义。
5. 不为前台/后台新增独立背景绑定维度。
6. 不把项目中所有页面全部主题化，仅覆盖当前真实运行页中的登录区、前台主容器、后台主容器。

## 5. 主题来源与目录同步规则

### 5.1 唯一主题来源

`ui/` 是唯一主题来源目录。

一个主题只有在同时满足以下条件时才视为有效主题：

- 存在 `*-login.html`
- 存在 `*-admin.html`

主题 slug 由文件名前缀直接确定。

### 5.2 最终保留的主题集合

本轮最终主题集合固定为：

1. `default`
2. `neo-minimal`
3. `cyber-grid`
4. `eastern-calm`
5. `editorial-magazine`
6. `luxe-noir`

### 5.2.1 预览主题名与运行时主题名映射

为了消除 `ui/` 预览命名与运行时默认主题命名之间的歧义，本轮采用以下固定映射：

| `ui/` 预览主题 | 运行时主题文件 | 运行时 `id` | 展示 `label` |
| --- | --- | --- | --- |
| `anime-core`（由 `ui/default-*` 承载） | `theme/default.json` | `default` | `Anime Core` |
| `neo-minimal` | `theme/neo-minimal.json` | `theme-neo-minimal` | `Neo Minimal` |
| `cyber-grid` | `theme/cyber-grid.json` | `theme-cyber-grid` | `Cyber Grid` |
| `eastern-calm` | `theme/eastern-calm.json` | `theme-eastern-calm` | `Eastern Calm` |
| `editorial-magazine` | `theme/editorial-magazine.json` | `theme-editorial-magazine` | `Editorial Magazine` |
| `luxe-noir` | `theme/luxe-noir.json` | `theme-luxe-noir` | `Luxe Noir` |

说明：

- `ui/default-*` 的视觉身份是 `Anime Core`；
- 运行时仍使用 `default` 作为默认主题技术标识；
- 主题选择器、主题列表和说明文案统一展示 `label`，不展示旧的“默认主题”命名。

### 5.3 `theme/` 目录处理规则

`theme/` 目录必须与上述主题集合一一对应：

保留 / 新增：

- `theme/default.json`
- `theme/neo-minimal.json`
- `theme/cyber-grid.json`
- `theme/eastern-calm.json`
- `theme/editorial-magazine.json`
- `theme/luxe-noir.json`

删除：

- `theme/anime.json`
- `theme/minimalist.json`
- `theme/corporate.json`
- `theme/creative.json`
- `theme/futuristic.json`
- `theme/retro.json`

## 6. `theme` 元信息重建规则

### 6.1 总体原则

`theme/` 中每个保留或新增主题文件，都必须全量重写 `basic_information`，不沿用旧值。

需重写字段：

- `id`
- `label`
- `description`
- `svg`

### 6.2 `id` 规则

为了兼容现有运行时逻辑：

- `default.json` 的 `id` 保持为 `default`
- 其余主题使用 `theme-<slug>`

最终 `id` 为：

- `default`
- `theme-neo-minimal`
- `theme-cyber-grid`
- `theme-eastern-calm`
- `theme-editorial-magazine`
- `theme-luxe-noir`

### 6.3 `label` 规则

`label` 直接对齐 `ui/` 里的主题身份：

- `default` → `Anime Core`
- `neo-minimal` → `Neo Minimal`
- `cyber-grid` → `Cyber Grid`
- `eastern-calm` → `Eastern Calm`
- `editorial-magazine` → `Editorial Magazine`
- `luxe-noir` → `Luxe Noir`

说明：

- `default` 仍是技术层面的默认主题文件名；
- 但其展示名不再是“默认主题”，而是明确的 `Anime Core`。

### 6.4 `description` 规则

每个主题的 `description` 根据对应 `ui/*-login.html` 与 `ui/*-admin.html` 的视觉语言重新编写，不沿用旧主题文案。

描述方向如下：

- `Anime Core`：梦幻、柔雾、徽章、缎带、高光、二次元产品控制台
- `Neo Minimal`：留白、秩序、低噪声、成熟工具感
- `Cyber Grid`：荧光栅格、数字感、终端化控制界面
- `Eastern Calm`：东方留白、纸感、静谧秩序
- `Editorial Magazine`：栏目化、杂志排版、编辑感信息分栏
- `Luxe Noir`：暗奢、夜色、金属边界、高对比质感

### 6.5 `svg` 规则

每个主题的 `svg` 缩略图也必须重新绘制，不沿用旧文件中的 SVG。

新的 `svg` 需要满足：

1. 直接体现该主题的主视觉气质；
2. 能从缩略图中辨认出该主题主要布局语言；
3. 优先提炼对应登录页与后台页的共性风格；
4. `default` 的 `svg` 也要重写为 Anime Core，而不是旧的中性卡片缩略图。

## 7. 真实运行页的结构策略

### 7.1 总体原则

真实运行页仍然以 `index.html` 为主，不直接把 `ui/*.html` 变成运行模板。

采用“稳定功能节点 + 可重组主题壳层”的方式落地：

- 保留现有 JS 强依赖的关键 ID、字段和交互节点；
- 允许调整展示层 DOM 结构；
- 让真实页面在视觉上对齐 `ui/` 对应主题。

### 7.2 三类主题壳层

真实页面被重组为三类主题壳层：

1. **Auth Shell**
   - 登录 / 注册 / 2FA 相关展示层
2. **App Shell**
   - 前台主容器、多账号、地图、会话区等主内容展示层
3. **Admin Shell**
   - 后台配置与管理展示层

### 7.3 登录页映射

基于当前：

- PC 登录区：`index.html` 中 `auth-login-container` 一段
- Mobile 登录区：`index.html` 中 `mobile-auth-login-container` 一段

重组为统一主题语义结构，例如：

- `theme-auth-shell`
- `theme-auth-hero`
- `theme-auth-panel`
- `theme-auth-form`
- `theme-auth-meta`

这样可以让不同主题落地各自的预览布局，同时不破坏用户名、密码、验证码、短信登录、2FA 等既有逻辑。

### 7.4 前台主容器映射

基于当前桌面端与移动端真实前台区域，重组出：

- `theme-app-shell`
- `theme-app-header`
- `theme-app-toolbar` / `theme-app-sidebar`
- `theme-app-main`
- `theme-app-card-grid`

不改变前台主功能分区，只改变其主题化展示结构。

### 7.5 后台主容器映射

后台区域重组为：

- `theme-admin-shell`
- `theme-admin-topbar`
- `theme-admin-alert`
- `theme-admin-section`
- `theme-admin-field-card`

让后台配置界面可以对齐 `ui/*-admin.html` 中各自的版式与材质风格。

### 7.6 桌面端 / 移动端策略

桌面端与移动端都必须按对应预览稿落地，但不做两套独立业务逻辑。

策略是：

- 同语义，不同布局骨架；
- 共享现有交互与数据流；
- 通过主题壳层与主题变量体现双端差异。

## 8. 主题变量体系

### 8.1 保持现有读取机制

继续使用现有 `theme/*.json` 读取和合并方式：

- 读取主题定义
- default 作为基础配置
- 非 default 在 default 基础上叠加

因此 `theme` 文件的主结构仍保持：

- `basic_information`
- `global_environment_variables`

### 8.2 变量覆盖范围扩展

`global_environment_variables` 不再只服务登录页，而是扩展为覆盖三类主题壳层：

- `auth_*`
- `app_*`
- `admin_*`

并且同时覆盖 PC / Mobile。

示例变量：

- `auth_login_container_background`
- `mobile_auth_login_content_background`
- `auth_login_panel_background`
- `auth_login_panel_shadow`
- `auth_login_panel_border`
- `app_shell_background`
- `mobile_app_shell_background`
- `app_panel_background`
- `admin_shell_background`
- `mobile_admin_shell_background`
- `admin_panel_background`
- `admin_panel_border`
- `admin_panel_shadow`

### 8.3 `ui` 与 `theme` 的职责分工

本轮不采用“自动解析 preview HTML 生成 theme JSON”的脆弱方案。

而是采用人工映射原则：

- `ui/` 决定主题身份与视觉目标；
- `theme/` 提供运行时变量；
- 真实页面结构与 CSS 负责解释这些变量。

即：

- `ui/` 回答“应该长什么样”；
- `theme/` 回答“真实页面怎么被驱动成这样”。

## 9. 背景绑定方法

### 9.1 绑定维度保持不变

默认主题随机背景图继续沿用现有绑定维度，只按以下两项绑定：

- `session_uuid`
- `target ∈ {pc, mobile}`

不新增 `app` 或 `admin` 作为绑定维度。

原因：

- 用户要求登录页、前台主容器、后台主容器在同一 target 下共用同一张图；
- 如果把前台和后台单独作为绑定维度，会导致登录、前台、后台各抽一张不同的图。

### 9.2 绑定范围扩展

在默认主题下，同一 target 的绑定结果必须复用到以下位置：

- 登录页
- 前台主容器
- 后台主容器

即：

- `pc` 绑定图 → PC 登录页 / PC 前台 / PC 后台共用
- `mobile` 绑定图 → Mobile 登录页 / Mobile 前台 / Mobile 后台共用

### 9.3 登录前后延续规则不变

继续保留现有机制：

- 未登录阶段：页面拿到背景图并在稳定 target 上报一次 consume；
- 登录成功后：把登录前看到的图作为候选图带给后端；
- 后端优先将该候选图绑定到当前 session；
- 若会话已有未过期绑定则复用；
- 否则才使用当前图建立新绑定。

### 9.4 服务端绑定决策规则

保持当前决策语义：

1. 若 `session_uuid` 无效：不建立绑定；
2. 若 `login_context=true` 且 `candidate_image_url` 有效：覆盖当前 `(session_uuid, target)` 绑定；
3. 若已有未过期绑定：复用已有绑定；
4. 若无绑定但当前图存在：以当前图建立新绑定；
5. TTL 继续保持 1800 秒语义。

### 9.5 作用到真实页面的方法

本轮不改变背景绑定接口协议，而是扩展默认主题配置注入结果。

也就是说：

- 后端仍解析同一份 default target 背景图；
- 只是把同一张图同时写入 auth / app / admin 对应的背景变量；
- 前端主题应用函数从“只写登录区”扩展为“同时写登录区、前台主容器、后台主容器”。

### 9.6 不会变更的部分

本轮不改以下语义：

- 背景缓存来源
- 背景补齐策略
- 公共 consume 接口语义
- session 绑定模型
- target 模型
- 背景 TTL

## 10. 主要改动文件

### 10.1 主题定义层

- `theme/default.json`
- `theme/neo-minimal.json`
- `theme/cyber-grid.json`
- `theme/eastern-calm.json`
- `theme/editorial-magazine.json`
- `theme/luxe-noir.json`

以及删除旧主题文件。

### 10.2 后端主题装配层

重点修改：

- 默认主题背景注入逻辑
- 主题列表输出逻辑
- 主题 metadata 输出逻辑

### 10.3 前端主题应用层

重点修改：

- 主题环境变量应用函数
- 主题壳层背景/材质应用函数
- 主题选择器渲染与回退逻辑的兼容验证

### 10.4 真实页面结构层

重点修改：

- `index.html` 中登录展示层
- `index.html` 中前台主容器展示层
- `index.html` 中后台展示层
- 桌面端 / 移动端对应壳层结构

### 10.5 测试层

继续保留并补充：

- `tests/test_ui_theme_previews.py`
- `tests/test_theme_background_binding.py`

## 11. 验证与验收标准

### 11.1 主题集合验证

运行时主题列表必须只包含 `ui/` 中存在的这 6 套主题。

### 11.2 元信息验证

每个主题的：

- `id`
- `label`
- `description`
- `svg`

都必须是新值，而不是旧主题遗留值。

### 11.3 UI 对齐验证

每个主题都必须满足：

- 登录页视觉对齐对应 `ui/*-login.html`
- 后台页视觉对齐对应 `ui/*-admin.html`
- 前台主容器风格与该主题语言一致
- PC / Mobile 都可识别出清晰主题差异

### 11.4 背景绑定验证

默认主题必须满足：

1. PC 登录页 / PC 前台 / PC 后台共用同一张背景图；
2. Mobile 登录页 / Mobile 前台 / Mobile 后台共用同一张背景图；
3. 登录前看到的图，登录后优先继承；
4. 不新增 `app/admin` 独立绑定维度；
5. 非默认主题不走随机背景绑定。

### 11.5 回退行为验证

若用户本地缓存了旧 theme id 或运行时出现未知主题值：

- 继续通过现有归一化逻辑回退到 `default`；
- 不因旧值导致页面不可用。

## 12. 风险与缓解

### 12.1 DOM 调整导致脚本依赖失效

缓解：

- 保留现有脚本依赖的关键 ID；
- 仅重组展示层，不直接替换功能节点。

### 12.2 背景绑定扩展后出现重复换图

缓解：

- 不新增 `app/admin` 绑定维度；
- 所有展示位都复用同一 target 绑定结果。

### 12.3 删除旧主题后本地缓存值失配

缓解：

- 继续使用现有主题归一化与默认回退逻辑；
- 新主题列表加载后自动回落到 `default`。

### 12.4 `svg` 重写成本较高

缓解：

- 先保证 6 套 SVG 全部与新主题身份一致；
- 设计上以稳定、可读、可用于选择器预览为优先，而不是追求过度复杂。

## 13. 实施顺序建议

建议后续实现按以下顺序执行：

1. 重建 `theme/` 文件集合与 metadata；
2. 扩展后端默认主题背景注入变量；
3. 重构前端主题应用函数，使其覆盖 auth/app/admin；
4. 重组 `index.html` 的主题壳层结构；
5. 对齐桌面端与移动端展示；
6. 补充测试与回归验证。

## 14. 结论

本次改造将把当前项目的主题系统从“旧 theme 定义 + 新 UI 预览分离”的状态，重构为“`ui/` 主导主题身份、`theme/` 承载运行时变量、真实页面统一按主题壳层呈现”的一致体系。

最终结果应达到：

- 主题列表与 `ui/` 一致；
- `theme/` 内容与 `ui/` 对齐；
- 登录 / 前台 / 后台都能呈现每套主题风格；
- 默认主题随机背景图在前后台与登录页之间按 target 一致复用；
- 保持现有业务与绑定逻辑的稳定性。
