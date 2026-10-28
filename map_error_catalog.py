"""Public map error contracts, isolated by provider and API namespace.

References: AMap JSAPI /guide/abc/errorcode, Tencent WebService /status,
Baidu JSAPI v4 ServiceStatus and FAQ 2273. Tianditu gateway entries are
observed Drive responses, not a claim of a complete public gateway contract.
"""

import re
from urllib.parse import urlsplit

from route_diagnostics import sanitize_diagnostic


def _entry(explanation, hint, retryable=False):
    return {'error_explanation': explanation, 'error_hint': hint, 'retryable': retryable}


_AMAP = {
    'SERVICE_NOT_AVAILABLE': ('服务不可用或接口路径错误', '检查当前 Key 的服务权限和请求路径'),
    'INVALID_USER_KEY': ('Key 无效或已过期', '检查地图控制台中的 Key 状态'),
    'INVALID_USER_SCODE': ('安全码未通过验证', '检查安全密钥与当前 JS API Key 是否配套'),
    'INVALID_USER_DOMAIN': ('绑定域名无效', '检查后端规划页面来源与 Key 的域名白名单'),
    'USERKEY_PLAT_NOMATCH': ('Key 与调用平台不匹配', '使用 Web 端 JS API 类型的 Key'),
    'NOT_SUPPORT_HTTPS': ('当前服务不支持 HTTPS', '核对服务支持范围并联系供应商'),
    'INSUFFICIENT_PRIVILEGES': ('服务权限不足', '检查当前 Key 对应服务是否已授权'),
    'USER_KEY_RECYCLED': ('Key 已被删除', '在地图控制台确认并使用有效 Key'),
    'INVALID_PARAMS': ('请求参数不合法', '检查坐标、经纬度顺序和参数取值'),
    'MISSING_REQUIRED_PARAMS': ('缺少必填参数', '检查起点、终点及接口必填参数'),
    'UNKNOWN_ERROR': ('未知服务错误', '依据原始原因和诊断编号排查'),
    'OUT_OF_SERVICE': ('规划点超出服务范围', '检查全部规划点的坐标与服务覆盖范围'),
    'NO_ROADS_NEARBY': ('规划点附近没有可用道路', '将规划点调整到附近可通行道路'),
    'ROUTE_FAIL': ('无法计算连通路线', '检查起终点之间的道路连通性'),
    'OVER_DIRECTION_RANGE': ('起终点距离过远', '缩短单段规划距离'),
    'ENGINE_RESPONSE_DATA_ERROR': ('路线引擎响应异常', '检查参数，持续失败时向供应商反馈'),
}

_TENCENT = {
    110: ('请求来源未被授权', '检查后端规划页面来源、Referer 和 Key 的白名单'),
    111: ('签名验证失败', '检查签名配置、路径、参数及编码'),
    112: ('IP 未被授权', '检查实际出口 IP 是否在白名单中'),
    113: ('当前功能未被授权', '检查当前 Key 的服务权限'),
    120: ('每秒调用量已达到上限', '降低 QPS 并有限退避重试'),
    121: ('每日调用量已达到上限', '检查当日配额；短时间重复请求无法恢复'),
    160: ('当前请求类型不支持 sig', '检查接口与签名形式'),
    161: ('sig 不支持当前 POST JSON 结构', '检查实际接口的 POST JSON 格式'),
    190: ('Key 无效', '检查地图控制台中的 Key 状态'),
    199: ('Key 未开启 WebService 功能', '在地图控制台开启 WebService'),
    300: ('缺少必要字段', '根据供应商原始说明检查必填字段'),
    301: ('缺少 Key 参数', '检查运行时密钥和请求构造'),
    306: ('缺少参数', '根据供应商原始说明补齐参数'),
    310: ('参数格式错误', '检查参数格式、分隔符和编码'),
    311: ('Key 格式错误', '检查配置值是否完整且没有多余空白'),
    320: ('参数数据类型错误', '检查数值、字符串和数组类型'),
    324: ('GET 与 POST 的同名参数冲突', '检查请求封装和代理是否重复传参'),
    326: ('起终点距离过近', '检查是否存在重复点或过短路段'),
    327: ('附近没有公交站', '检查实际响应是否属于公交接口'),
    328: ('没有可达公交路线', '检查实际响应是否属于公交接口'),
    329: ('没有可达火车路线', '检查实际响应是否属于铁路接口'),
    330: ('参数长度错误', '检查具体参数的长度限制'),
    331: ('查询条件过长', '减少对应查询字段的长度'),
    332: ('途经点个数超过限制', '检查实际请求的途经点参数；不要用业务点总数推断'),
    333: ('坐标无法吸附道路', '检查 GCJ-02 坐标、经纬度顺序及道路覆盖'),
    335: ('不支持该城市的公交查询', '检查实际响应是否属于公交接口'),
    341: ('缺少关键词', '检查实际响应是否属于搜索接口'),
    344: ('附近没有火车站', '检查实际响应是否属于公交或铁路接口'),
    347: ('查询没有结果', '检查当前接口的起终点或查询条件'),
    348: ('请求参数错误', '根据供应商原始说明检查参数'),
    351: ('存在互斥参数', '检查参数组合'),
    364: ('扩大搜索参数取值错误', '检查实际响应是否属于搜索接口'),
    365: ('纬度超过有效范围', '检查纬度是否在 -90 至 90 之间'),
    366: ('经度超过有效范围', '检查经度是否在 -180 至 180 之间'),
    373: ('起终点距离过长', '检查当前出行模式的距离限制'),
    374: ('起终点坐标错误', '使用 GCJ-02；腾讯路线参数为纬度在前'),
    375: ('局域网 IP 无法定位', '检查实际响应是否属于 IP 定位接口'),
    377: ('无法规划导航线路', '检查起终点和道路连通性'),
    378: ('无法规划步行线路', '检查步行路网、起终点和距离'),
    379: ('无法规划公交线路', '检查实际响应是否属于公交接口'),
    380: ('坐标类型参数缺少对应坐标', '检查坐标和坐标类型参数组合'),
    382: ('IP 无法定位', '检查实际响应是否属于 IP 定位接口'),
    384: ('无法规划骑行线路', '检查实际响应是否属于骑行接口'),
    387: ('没有对应的 POI', '检查实际请求的 POI 标识'),
    393: ('没有符合条件的数据', '检查当前接口的查询条件'),
    394: ('查询条件错误', '检查当前接口的条件表达式'),
    395: ('传入参数不合法', '根据供应商原始说明检查参数'),
    396: ('距离矩阵坐标或组合数量超限', '检查实际响应是否属于距离矩阵接口'),
    397: ('距离矩阵点数或模式限制超限', '检查实际响应是否属于距离矩阵接口'),
    399: ('查询关键词错误', '检查实际响应是否属于搜索接口'),
    400: ('参数无法解码', '使用 UTF-8 并正确进行 URL 编码'),
    402: ('提交数据格式错误', '检查 UTF-8、编码和提交结构'),
    403: ('不支持当前接口转发', '检查代理路径和转发方式'),
    404: ('请求路径错误', '检查 API 路径与版本'),
    405: ('接口要求 GET 请求', '检查请求方法'),
    406: ('接口要求 POST 请求', '检查请求方法'),
    407: ('请求方法不受支持', '检查接口要求的请求方法'),
    408: ('自定义 Referer 错误', '检查 Referer 构造与来源授权规则'),
    500: ('下游服务超时', '检查网络并有限退避重试'),
    510: ('下游服务无法连接', '检查网络并有限重试'),
    520: ('下游服务请求失败', '有限重试并保留原始原因'),
    530: ('下游响应无法解析', '保留脱敏响应；持续发生时反馈供应商'),
    531: ('下游服务内部报错', '有限重试并保留诊断编号'),
    600: ('其他服务错误', '依据原始原因和诊断编号排查'),
}

_BAIDU_ROUTE = {
    1: ('返回城市候选', '明确城市或起终点位置'),
    2: ('无法确定位置', '检查业务 GCJ-02 到 SDK BD09 的转换及输入点'),
    3: ('无法确定导航方案', '检查出行模式、道路连通性和起终点'),
    4: ('路线 SDK 密钥无效', '检查浏览器 AK、服务权限和鉴权响应'),
    5: ('请求无效', '检查参数类型、范围及格式'),
    6: ('服务权限不足', '检查 AK 类型和对应服务权限'),
    7: ('路线服务不可用', '有限退避重试'),
    8: ('路线检索超时', '检查网络并有限重试'),
}
_BAIDU_AUTH = {
    101: ('AK 参数缺失或不支持当前 JS 服务', '检查脚本 AK 参数、应用类型和原始鉴权消息'),
    102: ('MCODE 参数缺失', 'JS 场景检查是否误用了移动端 AK'),
    200: ('找不到对应应用', '检查 AK 和应用状态'),
    201: ('应用已删除或停用', '检查控制台应用状态和回收站'),
    202: ('应用被平台限制', '检查应用状态并联系供应商'),
    203: ('应用类型错误', 'JS API 使用浏览器类型 AK'),
    210: ('应用 IP 校验失败', 'JS 场景检查是否误用了服务端 AK'),
    211: ('应用 SN 校验失败', '检查 AK 类型及原始鉴权响应'),
    220: ('Referer 校验失败', '检查规划页面来源与 AK 的 Referer 白名单'),
    230: ('MCODE 校验失败', 'JS 场景检查是否误用了移动端 AK'),
    240: ('应用服务未启用', '检查浏览器 AK 的服务权限'),
    250: ('关联用户不存在', '检查 AK 所属账号'),
    251: ('用户已删除或未激活', '检查账号状态和回收站'),
    252: ('用户被平台限制', '检查账号状态并联系供应商'),
    260: ('服务不存在或未授权', '检查接口和 AK 的服务权限'),
    261: ('服务已被禁用', '检查服务状态'),
    301: ('长期配额已耗尽', '检查控制台额度，停止即时重试'),
    302: ('当日配额已耗尽', '检查当日额度，停止即时重试'),
    311: ('签名错误', '核对原始鉴权响应并联系供应商'),
    401: ('应用并发超限', '降低并发并有限退避'),
    402: ('应用与服务总并发均超限', '降低并发并有限退避'),
    502: ('商用授权状态限制服务', '检查控制台商用授权状态'),
    503: ('商用授权状态限制服务', '检查控制台商用授权状态'),
    8001: ('实际加载的 JS API 版本过旧', '检查入口、重复脚本和缓存'),
}
_TIANDITU = {
    301001: ('非法 Key', '检查 Token 是否完整、有效并已启用所需服务'),
    301012: ('权限类型错误', '检查应用类型、服务权限及规划页面来源'),
    308010: ('请求参数错误或缺失', '检查 Token 和 Drive 必填参数'),
    308011: ('参数长度或格式不合规', '检查 Token 长度和参数格式'),
}
_HTTP = {
    400: ('HTTP 请求格式错误', '检查请求参数和编码'),
    401: ('HTTP 身份验证失败', '检查请求对应服务的认证配置'),
    403: ('HTTP 请求被拒绝', '检查响应中的业务错误、来源和服务权限'),
    404: ('HTTP 资源不存在', '检查 SDK 或服务请求路径'),
    405: ('HTTP 请求方法不受支持', '检查请求方法'),
    408: ('HTTP 请求超时', '检查网络并有限重试'),
    413: ('HTTP 请求内容过大', '减少请求数据量'),
    414: ('HTTP 请求地址过长', '减少请求参数长度'),
    415: ('HTTP 内容类型不受支持', '检查 Content-Type'),
    422: ('HTTP 请求内容无法处理', '检查参数取值'),
    429: ('HTTP 请求过于频繁', '降低频率并有限退避'),
    500: ('HTTP 服务内部错误', '有限重试并保留诊断编号'),
    502: ('HTTP 上游网关错误', '检查网络并有限重试'),
    503: ('HTTP 服务暂不可用', '有限退避重试'),
    504: ('HTTP 网关超时', '检查网络并有限重试'),
}


def describe_map_error(provider, api_type, code, stage='route'):
    """Return a fresh explanation; unknown and success codes remain unmapped."""
    code = str(code).strip() if code is not None else ''
    if not code:
        return {}
    if api_type == 'http':
        table, transient = _HTTP, {408, 429, 500, 502, 503, 504}
    elif provider == 'amap' and api_type == 'amap_jsapi':
        item = _AMAP.get(code)
        retryable = None if code in {'UNKNOWN_ERROR', 'ENGINE_RESPONSE_DATA_ERROR'} else code == 'SERVICE_NOT_AVAILABLE'
        return _entry(*item, retryable=retryable) if item else {}
    elif provider == 'tencent' and api_type == 'tencent_webservice':
        table, transient = _TENCENT, {120, 500, 510, 520, 530, 531}
    elif provider == 'baidu' and api_type == 'baidu_jsapi_route':
        table, transient = _BAIDU_ROUTE, {7, 8}
    elif provider == 'baidu' and api_type == 'baidu_jsapi_auth':
        table, transient = _BAIDU_AUTH, {401, 402}
    elif provider == 'tianditu' and api_type == 'tianditu_drive':
        table, transient = _TIANDITU, set()
    else:
        return {}
    if not re.fullmatch(r'\d+', code):
        return {}
    number = int(code)
    item = table.get(number)
    return _entry(*item, retryable=number in transient) if item else {}


def normalize_map_error(provider, api_type, value, *, callback_status=None, http_status=None, stage='route'):
    """Extract vendor fields, preserving strings and never scanning arbitrary numbers."""
    result = {'provider': provider, 'api_type': api_type, 'stage': stage}
    code = None
    if isinstance(value, dict):
        message = next((value[k] for k in ('info', 'message', 'msg', 'error') if value.get(k) not in (None, '')), '')
        code = next((value[k] for k in ('error_code', 'infocode', 'code', 'status') if value.get(k) not in (None, '')), None)
        if provider == 'amap' and isinstance(value.get('info'), str) and value['info'].strip() in _AMAP:
            code = value['info'].strip()
    else:
        message = str(value or '')
    if provider == 'amap' and isinstance(message, str):
        # Only named vendor tokens are recognized in wrapped loader failures.
        for token in _AMAP:
            if re.search(r'(?<![A-Z0-9_])' + re.escape(token) + r'(?![A-Z0-9_])', message):
                code = token
                break
    result['message'] = message if isinstance(message, str) else str(message)
    if code is not None:
        result['error_code'] = code
        result.update(describe_map_error(provider, api_type, code, stage))
    if callback_status is not None:
        result['callback_status'] = callback_status
    if http_status is not None:
        result['http_status'] = http_status
        if 'error_explanation' not in result:
            result.update(describe_map_error(provider, 'http', http_status, stage))
    return result


def _is_baidu_console_auth_dialog(message):
    if not re.search(r'APP\s*不存在|AK\s*有误', message, re.I):
        return False
    for url in re.findall(r'https?://[^\s"\'<>]+', message, re.I):
        try:
            parsed = urlsplit(url)
            default_port = 80 if parsed.scheme.lower() == 'http' else 443
            if (parsed.hostname == 'lbsyun.baidu.com' and parsed.path == '/apiconsole/key'
                    and parsed.username is None and parsed.password is None
                    and parsed.port in (None, default_port)):
                return True
        except ValueError:
            continue
    return False


def extract_baidu_sdk_auth_error(event, *, provider, sensitive_values=()):
    """Recognize explicit SDK authentication dialogs, never incidental numbers."""
    if provider != 'baidu' or not isinstance(event, dict) or event.get('kind') != 'dialog':
        return None
    message = sanitize_diagnostic(event.get('detail', ''), 1024, sensitive_values)
    console_auth = _is_baidu_console_auth_dialog(message)
    if not console_auth and not re.search(r'百度(?:地图|LBS)|百度未授权使用地图\s*api|baidu\s*maps?\s*api', message, re.I):
        return None
    if not console_auth and not re.search(r'认证|鉴权|未授权|authentication|authorization|'
                                         r'(?:AK|key|referer|域名|密钥).{0,20}(?:校验|无效|失败|invalid|denied)', message, re.I):
        return None
    # HTTP status, coordinates and elapsed times are not vendor authentication codes.
    match = re.search(r'(?<![A-Za-z0-9_])(?:错误码|error[\s_-]*code)\s*[：:=]\s*["\']?(\d{1,9})(?![\w.])', message, re.I)
    value = {'message': sanitize_diagnostic(message, 256, sensitive_values)}
    if match:
        value['error_code'] = int(match.group(1))
    result = normalize_map_error('baidu', 'baidu_jsapi_auth', value, stage='sdk_auth')
    result['source'] = 'dialog'
    return result


def map_error_retry_policy(provider):
    api_type = {'amap': 'amap_jsapi', 'tencent': 'tencent_webservice',
                'baidu': 'baidu_jsapi_route', 'tianditu': 'tianditu_drive'}.get(provider)
    table = {'amap': _AMAP, 'tencent': _TENCENT, 'baidu': _BAIDU_ROUTE,
             'tianditu': _TIANDITU}.get(provider, {})
    return {str(code): describe_map_error(provider, api_type, code)['retryable'] for code in table}
