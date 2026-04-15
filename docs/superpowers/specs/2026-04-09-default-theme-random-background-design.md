# 默认主题随机背景图修正设计

- 日期：2026-04-09
- 主题：默认主题随机背景图消耗与绑定逻辑修正
- 状态：已评审（用户确认方案 A）

## 1. 背景与问题

当前默认主题随机背景图在以下场景存在问题：

1. 加载过程会触发多次“已使用背景”上报，导致重复消耗。
2. 登录后（有 `sessionUUID`）仍会继续消耗新背景图，而不是复用登录前看到的图。

目标行为：

- 未登录：每次刷新可拿新图，但**单次页面加载仅消耗一次**（稳定后的端类型）。
- 已登录：按 `(sessionUUID, target)` 绑定背景图，`target ∈ {pc,mobile}`，绑定有效期 30 分钟。
- PC/Mobile 绑定独立、计时独立。

## 2. 设计目标

1. 消除加载期间重复消耗。
2. 登录后在 30 分钟内稳定复用同一背景图。
3. 支持同一会话下 PC/Mobile 独立绑定。
4. 保持现有默认主题随机背景缓存机制可用。

## 3. 总体方案（A）

采用“**服务端绑定 + 前端状态门闩**”双层控制：

- 服务端负责最终一致性：
  - 对已登录请求按 `(sessionUUID, target)` 返回绑定图（未过期）。
  - 无绑定或已过期才分配新图并更新绑定（触发一次消耗）。
- 前端负责减少噪音请求：
  - 未登录仅在页面稳定后上报一次消耗（按稳定 target）。
  - 登录后仅在当前 target 未绑定时触发一次 ensure-bind。

## 4. 数据模型与持久化

### 4.1 存储位置

扩展 `random_background_image/index.json`，新增顶层字段：

- `session_bindings`

### 4.2 结构

```json
{
  "session_bindings": {
    "<session_uuid>": {
      "pc": {
        "image_url": "/theme-assets/random_background_image/pc_xxx.jpg",
        "bound_at": "2026-04-09T10:00:00+08:00",
        "expires_at": "2026-04-09T10:30:00+08:00"
      },
      "mobile": {
        "image_url": "/theme-assets/random_background_image/mb_xxx.jpg",
        "bound_at": "2026-04-09T10:05:00+08:00",
        "expires_at": "2026-04-09T10:35:00+08:00"
      }
    }
  }
}
```

### 4.3 规则

- 绑定键：`(session_uuid, target)`。
- 命中且 `expires_at > now`：直接复用绑定图，不消耗。
- 未命中或过期：分配新图、写入绑定、过期时间 = 30 分钟。
- 懒清理：每次访问对应 session 时清理过期 target 绑定。
- 可选周期清理：在现有索引清理流程中附带清理过期 `session_bindings`。

## 5. 接口语义调整

> 说明：保留现有接口路径，升级语义，减少前后端改动面。

### 5.1 未登录路径

- `GET /api/public/theme_styles`
  - 仍返回默认主题背景候选（按 target）。
  - 不建立 session 绑定。

- `POST /api/public/theme_background/consume`
  - 仅用于未登录“首稳态 target”消耗上报。
  - 后端保留现有防抖/限流逻辑。

### 5.2 已登录路径

- `mark_theme_background_consumed(target, image_url)`（Python API）
  - 升级为“ensure-bind”：
    1) 若 `(sessionUUID,target)` 有未过期绑定，返回该绑定对应 `theme_config`（忽略 image_url，不消耗）。
    2) 否则建立新绑定并返回新 `theme_config`（发生一次消耗）。

## 6. 前端状态机与触发时机

文件：`scripts/main.new.js`

### 6.1 新增前端门闩状态

- `initialConsumeDone = { pc: false, mobile: false }`
  - 未登录阶段“稳定后仅一次消耗”。
- `sessionBindEnsured = { pc: false, mobile: false }`
  - 已登录阶段“按 target 确保绑定”。

### 6.2 触发规则

1. 页面加载并稳定后：
   - 计算稳定 target（pc/mobile）。
   - 若未登录，仅触发一次 consume（`initialConsumeDone[target] = true`）。

2. 登录成功后：
   - 读取当前 target。
   - 若 `sessionBindEnsured[target] == false`，调用 ensure-bind。
   - 成功后置 `sessionBindEnsured[target] = true`。

3. 后续 resize / target 切换：
   - 不触发未登录重复消耗。
   - 若已登录且新 target 尚未 ensure，可触发一次 ensure-bind。

### 6.3 关键边界场景

- 初始稳定为 PC，之后判定变 mobile：
  - 未登录阶段只消耗 PC。
  - 若此时登录，mobile 可建立独立绑定并消耗一次。

## 7. 与现有代码映射

- 背景选择与注入：`main.py` 主题配置注入逻辑（默认主题背景注入）。
- 已登录上报入口：`mark_theme_background_consumed`。
- 公开消耗入口：`/api/public/theme_background/consume`。
- 前端上报与主题应用：`scripts/main.new.js` 中 `scheduleThemeBackgroundConsumed` / `notifyThemeBackgroundConsumed` / `applyThemeGlobalEnvironmentVariables`。

## 8. 验收标准

1. 未登录单次页面加载仅消耗一次（稳定 target）。
2. 登录后同 target 30 分钟内刷新复用同图。
3. 30 分钟到期后刷新分配下一张。
4. PC 与 mobile 绑定互不影响、独立计时。
5. 登录前后切换场景满足：
   - 初始稳定 target 消耗一次；
   - 登录后新 target 可独立建立绑定。

## 9. 风险与缓解

1. **多标签页并发 ensure-bind**
   - 缓解：后端按 `(sessionUUID,target)` 幂等读取优先，避免重复消耗。

2. **索引文件膨胀**
   - 缓解：懒清理 + 周期清理过期绑定。

3. **前端重复触发遗留路径**
   - 缓解：统一通过门闩状态判断，保留 in-flight 与 debounce。

## 10. 非目标

- 不修改默认主题之外的主题行为。
- 不改变随机背景来源与缓存补齐策略。
- 不引入新 API 路径（优先复用既有接口）。

## 11. 特殊场景补充（已确认）

### 11.1 无 UUID 页面重进后再登录：覆盖旧绑定并重置 30 分钟

场景：

1. 用户已登录并有 `uuid=A`，且 `(A,target)` 绑定尚未过期。
2. 用户访问 `/`（无 UUID，按未登录逻辑拿到一张新背景）。
3. 用户再次登录。

要求：

- 再次登录时，若存在“本次未登录阶段已消费背景图”，则**覆盖当前会话该 target 的旧绑定**，并将 TTL 重置为 30 分钟（从本次登录时刻起算）。

设计落地：

- 前端在未登录首稳态 consume 成功后，记录 `anonConsumedBackgroundByTarget[target]`。
- 登录成功后触发 ensure-bind 时，附带：
  - `login_context=true`
  - `target`
  - `candidate_image_url=anonConsumedBackgroundByTarget[target]`
- 后端 ensure-bind 规则新增：
  - 若 `login_context=true` 且 `candidate_image_url` 有效，则无论旧绑定是否过期，直接覆盖 `(sessionUUID,target)` 绑定并重置 `expires_at=now+30m`。
  - 覆盖成功后返回新的 `theme_config`（即该 candidate 对应样式）。

### 11.2 重复登录“多端登录提示”修正（同浏览器重登不提示）

现象：

- 用户在同浏览器重复登录时，可能收到“其他设备登录”提示，影响体验。

要求：

- 重复登录应分配新 cookie；同浏览器重登不应提示“多端登录”。

设计落地：

1. `/auth/login` 每次成功登录都**强制签发新 `auth_token` cookie**（cookie 轮换）。
2. 在登录响应中，区分“跨设备挤下线”与“同端重登会话替换”：
   - 仅当确认为跨设备会话被踢时，返回 `multi_device_warning`。
   - 同浏览器重登导致的旧会话清理，不返回 `multi_device_warning`（可保留普通 `cleanup_message` 或静默）。
3. 前端展示规则保持：只在 `result.multi_device_warning` 存在时弹多端提示。

### 11.3 登录用户名归一化（防止手机号登录路径误判）

为避免手机号登录/用户名登录分支使用不同变量造成会话清理与告警误判，登录后续会话管理统一使用：

- `normalized_auth_username = auth_result["auth_username"]`

并用该值执行：

- 单会话清理、会话关联、token 创建、告警判定。

## 12. 验收补充

在原验收基础上新增：

1. 已绑定 30 分钟内，访问 `/` 后再登录：
   - 采用本次未登录拿到的新图覆盖旧绑定；
   - 覆盖后 30 分钟内刷新保持该新图。
2. 同浏览器重复登录不会出现“多端登录”提示。
3. 每次登录响应都下发新的 `auth_token` cookie。
4. 手机号登录、用户名登录两条路径下，会话清理与告警行为一致。
