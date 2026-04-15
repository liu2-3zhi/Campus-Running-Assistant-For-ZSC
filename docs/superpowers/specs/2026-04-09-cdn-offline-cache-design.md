# CDN 离线缓存升级设计（支持 require 递归拉取）

- 日期：2026-04-09
- 状态：已评审（待实现）
- 目标：升级现有 CDN 缓存系统，支持 CommonJS `require(...)` 依赖自动识别、递归拉取、重命名改写与本地优先加载；本地失败自动回源。

## 1. 背景与问题

当前系统缓存入口文件后，未同步缓存其 `require(...)` 依赖，导致运行时仍请求外部资源或直接报错。

示例入口：
`https://cdn.jsdelivr.net/npm/flowchart.js/index.js`

该入口依赖：
- `require('./src/flowchart.shim')`
- `require('./src/flowchart.parse')`
- `require('./src/jquery-plugin')`

如果只缓存入口，不缓存上述依赖，离线不可用。

## 2. 目标与范围

### 2.1 功能目标

1. 支持识别并处理：
   - 相对依赖：`./`、`../`
   - 包依赖：`pkg`、`pkg/subpath`
2. 递归拉取依赖，尽量实现离线可运行。
3. 保持 CommonJS：改写后继续使用 `require(local_path)`。
4. 主文件与依赖独立目录存储（在**现有缓存目录**内）。
5. 本地缓存失败自动回源原始 URL 拉取，并写回缓存。

### 2.2 非目标

- 不改造成单文件打包（IIFE/UMD bundling）。
- 不做 ESM import 语法转换。

## 3. 目录与命名规范

以 `https://cdn.jsdelivr.net/npm/flowchart.js/index.js` 为例：

- 入口缓存文件：`<cache>/flowchart.js`
- 依赖目录：`<cache>/flowchart/`
- 所有递归依赖统一放在 `flowchart/` 内。

### 3.1 重命名规则（包名_路径）

- 相对依赖按入口包名归属：
  - `./src/flowchart.shim` → `flowchart_src_flowchart.shim.js`
- 包依赖：
  - `jquery` → `jquery_index.js`（若入口为 index）
  - `lodash/fp` → `lodash_fp.js`

### 3.2 冲突与安全处理

- 文件名非法字符统一转 `_`（如 `@`, `/`, `\\`, `:` 等）。
- 同名冲突追加短哈希（例如 `_a1b2c3`）。
- 无扩展名时按规则补全：`.js`、`.json`、`/index.js`。

## 4. 解析与改写流程

1. 下载入口文件到 `<cache>/<entry>.js`。
2. 扫描源码中的 `require(...)`（排除注释与字符串误判）。
3. 对每个依赖分流：
   - 相对依赖：基于当前文件 URL 解析绝对 URL。
   - 包依赖：读取包元信息并解析入口。
4. 下载依赖文件到 `<cache>/<entry_dir>/`，生成本地文件名。
5. 改写当前源码 `require(...)` 为本地路径（CommonJS 保持不变）。
6. 对新下载 JS 递归执行步骤 2-5。
7. 全程做去重与循环保护。

## 5. 包依赖解析策略

对于 `require('pkg')` / `require('pkg/subpath')`：

1. 获取 `pkg@version` 的 `package.json`（来源遵循现有 CDN 解析方式）。
2. 入口解析优先级：
   - `exports`
   - `module`
   - `main`
   - `index.js`（兜底）
3. `pkg/subpath` 优先走 `exports` 子路径映射，否则拼接子路径并补全扩展。
4. 将解析得到的远程 URL 纳入递归抓取。

## 6. 缓存读取与回源兜底

统一加载顺序：

1. 先读本地缓存文件。
2. 本地不存在 / 读取失败 / 校验失败 → 自动回源原始 URL 拉取。
3. 拉取成功后写回本地缓存并继续执行。
4. 拉取失败则记录失败项并按策略继续（不中断全局）。

### 6.1 运行时兜底

若改写后的本地 `require(local_path)` 目标文件缺失：

- 从映射表查到对应远程 URL；
- 自动回源下载并落盘；
- 重试加载当前依赖。

## 7. 元数据与索引

每个入口维护元数据文件（示例：`<cache>/flowchart.meta.json`）：

```json
{
  "entry_url": "https://cdn.jsdelivr.net/npm/flowchart.js/index.js",
  "entry_file": "flowchart.js",
  "deps_dir": "flowchart",
  "url_to_local": {},
  "local_to_url": {},
  "status": "complete",
  "failed": []
}
```

字段说明：
- `url_to_local`：远程 URL → 本地文件。
- `local_to_url`：本地文件 → 远程 URL（运行时回源使用）。
- `status`：`complete | partial`。
- `failed`：失败依赖与错误信息。

## 8. 错误处理策略

1. 网络失败：短次数重试 + 指数退避。
2. 单依赖失败：登记 `failed`，继续其余依赖。
3. 解析失败：记录警告，保留原片段，避免整体中断。
4. 循环依赖：使用 `visiting/visited` 集合防止死循环。
5. 文件冲突：短哈希消歧，保证可重复构建。

## 9. 测试与验收

最小测试集：

1. 相对依赖递归（`./a -> ./b -> ../c`）
2. 包依赖递归（`pkg` + `pkg/subpath`）
3. 文件名冲突（多个 `index.js`）
4. 纯离线命中（全本地读取成功）
5. 回源兜底（删除一个本地依赖后自动补齐）
6. 部分失败容忍（某依赖 404，不影响其余缓存）
7. 改写正确性（仍为 CommonJS `require(local)`）

验收标准：
- 示例 `flowchart.js` 入口及其递归依赖在断网场景可加载（在失败列表为空时）。
- 本地缺失时可自动回源并恢复缓存。
- 改写路径全部落在 `<cache>/<entry_dir>/` 且命名符合“包名_路径”。

## 10. 实施边界

- 仅对当前 CDN 缓存系统做增量升级，不改动业务无关模块。
- 保持现有缓存根目录不变，仅新增入口同级依赖目录与元数据文件。
