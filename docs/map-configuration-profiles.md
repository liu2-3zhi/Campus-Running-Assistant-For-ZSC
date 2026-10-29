# 地图多配置

系统配置中的“地图配置”支持为同一供应商添加多份配置。每张卡片包含名称、供应商对应的密钥和可选页面来源；高德另有可选安全密钥。卡片可通过拖动手柄排序，也可使用上移、下移按钮，桌面与手机均可操作。

“前端地图配置”和“后端路径规划配置”分别选择卡片，例如前端使用“高德1”，后端使用“高德2”；也可选择不同供应商。排序只改变显示顺序。删除被选中的卡片时，界面会将相应用途改选剩余第一张卡片；至少保留一份配置，保存前可以检查两个选择。

## 管理接口

继续使用需要现有管理权限的 `GET /api/admin/config/load` 和 `POST /api/admin/config/save`，不新增另一套管理接口。地图字段示例：

```json
{
  "Map": {
    "configs": [
      {
        "id": "amap-front",
        "name": "高德1",
        "provider": "amap",
        "js_key": "frontend-placeholder",
        "security_js_code": "",
        "backend_page_origin": "https://front.example.com"
      },
      {
        "id": "amap-back",
        "name": "高德2",
        "provider": "amap",
        "js_key": "backend-placeholder",
        "security_js_code": "",
        "backend_page_origin": "https://back.example.com"
      }
    ],
    "frontend_config_id": "amap-front",
    "backend_config_id": "amap-back"
  }
}
```

`configs` 数组顺序即卡片顺序。ID 唯一、固定，以字母或数字开头，只包含字母、数字、下划线和短横线，最多 128 位。名称为 1 至 100 个字符，不包含控制字符。两个用途 ID 必须引用列表中的有效配置；空列表、重复 ID、未知供应商或失效引用会被拒绝，配置不会写盘。

供应商及密钥字段为 `amap/js_key`、`tencent/map_key`、`tianditu/token`、`baidu/ak`。保存列表时，已有同 ID、同供应商配置中未提交的密钥保持原值，显式空字符串清除密钥。全局页面来源、前端代理开关和瓦片缓存设置仍可独立更新。

旧的单供应商配置结构无需手工转换：读取时生成稳定的 `legacy-*` ID，管理界面保存时写入列表及两个选择 ID。管理接口的旧 `provider`、`providers` 字段仍以所选前端配置为准，旧客户端往返保存不会将后端密钥复制到前端。普通前端响应保留 `map_provider`、脱敏的 `map_providers` 和当前需要的加密密钥包，并增加 `map_config_id`；不会下发完整配置列表或后端专用密钥。

## 生效与隔离

后端规划读取后端选择的密钥和来源；前端显示及资源代理使用前端选择。来源依次采用所选卡片、全局来源和应用请求来源，且只保留 HTTP/HTTPS 的协议、主机和端口。关闭前端代理时，地图使用浏览器当前页面来源。

前端只展示地图、已有路线和标记，或收集用户手绘的坐标；路线规划、失败重试和距离补足由后端负责。新版和旧版自动生成均调用后端 `auto_generate_path_with_provider`，不传前端供应商或展示密钥决定规划配置。旧版未使用的浏览器步行规划函数、队列和 `AMap.Walking` 插件已移除，后端失败不会回退到浏览器规划。

旧版保存后在下次地图加载时应用前端配置，执行中的地图保持原配置。已加载 SDK 更换密钥或高德安全码时自动刷新页面；前端代理模式变化也沿用原有刷新规则。新旧页面显式选择空密钥时会清除旧凭据，不回退到上一份配置。

代理上下文固定页面初始化时的来源，避免管理员保存新配置后旧页面的密钥与新来源混用；新页面初始化使用新选择。后端折返腿缓存按后端配置运行字段隔离，并与实际规划共用同一配置快照。

现有 `POST /api/map-proxy/context` 可接收 `map_config_id`，返回不透明的 `context_token`；新版脚本还提交 `pin_context: true`，使旧配置在首次迁移前就固定页面来源。前端为代理资源附加 `__map_context` 控制参数，续期提交原 token。服务器保存有界、限时且绑定认证身份的来源快照，控制参数不会转发给供应商，返回值不包含来源或密钥。Worker、模块依赖和 CSS 相对子资源保持原上下文；同一用户不同业务会话的页签分别验证各自会话权限。上下文过期或服务重启后不能为已加载的 SDK 静默更换来源，页面会提示并尝试刷新恢复；无多配置、未请求固定来源的旧接口调用保留原契约。

代理模式支持普通 Worker 和远程 URL 的模块 Worker。Blob 模块 Worker 的静态导入会绕过来源固定，因此暂不支持，会在创建时明确报错；关闭代理时不受此限制。

## 验证入口

- Python：`test_map_config_profiles.py`、`test_map_config_runtime.py`、管理接口、密钥包、来源、代理及路线业务回归。
- Node：配置列表、旧版卡片、SDK 切换、Vue 空凭据清除及现有运行时回归。
- 浏览器：`node tests/browser_map_config_profiles_smoke.mjs` 和 `node tests/browser_map_cache_config_smoke.mjs`，使用隔离本地接口与真实组件，覆盖新版/旧版、桌面鼠标/手机触摸、排序后 ID 绑定、保存重载、删除和缓存设置保留。
- 代理浏览器：`python tests/browser_map_proxy_profiles_smoke.py`，使用真实 Chromium 与本地代理响应，覆盖模块依赖先于入口执行的请求、CSS 相对资源、配置切换、多会话页签、旧结构迁移和 Blob 模块 Worker 拦截。

浏览器截图位于忽略目录 `output/map-config-profiles-smoke/`。上述配置界面验收使用占位凭据，不代表实际地图供应商鉴权或真实路线规划的在线验收。
