import json

from map_error_catalog import describe_map_error, normalize_map_error
from route_diagnostics import build_route_failure_summary, detailed_route_failure_message


def test_amap_string_and_object_preserve_security_code_meaning():
    for value in ('INVALID_USER_SCODE', {'info': 'INVALID_USER_SCODE', 'infocode': '10008'}):
        result = normalize_map_error('amap', 'amap_jsapi', value)
        assert result['error_code'] == 'INVALID_USER_SCODE'
        assert result['error_explanation'] == '安全码未通过验证'
        assert result['retryable'] is False
        assert 'MD5' not in result['error_hint']


def test_code_namespaces_do_not_confuse_http_and_vendor_status():
    assert 'Referer' in describe_map_error('tencent', 'tencent_webservice', 408)['error_explanation']
    assert '超时' in describe_map_error('tencent', 'http', 408)['error_explanation']
    assert '密钥' in describe_map_error('baidu', 'baidu_jsapi_route', 4)['error_explanation']
    assert describe_map_error('baidu', 'baidu_webservice', 4) == {}
    assert describe_map_error('tencent', 'tencent_webservice', 3000) == {}
    assert describe_map_error('tianditu', 'tianditu_drive', 2001) == {}


def test_tencent_qps_and_daily_quota_have_different_retry_policy():
    assert describe_map_error('tencent', 'tencent_webservice', 120)['retryable'] is True
    assert describe_map_error('tencent', 'tencent_webservice', 121)['retryable'] is False
    assert '每日' in describe_map_error('tencent', 'tencent_webservice', 121)['error_explanation']


def test_tianditu_gateway_and_http_failures_are_both_retained():
    result = normalize_map_error('tianditu', 'tianditu_drive',
                                 {'code': 301012, 'msg': '权限类型错误'}, http_status=403)
    assert result['error_code'] == 301012
    assert result['http_status'] == 403
    assert result['message'] == '权限类型错误'
    assert result['error_explanation'] == '权限类型错误'


def test_unknown_code_is_not_inferred_from_incidental_message_numbers():
    result = normalize_map_error('tencent', 'tencent_webservice', {'status': 99999, 'message': 'segment 408 failed'})
    assert result['error_code'] == 99999
    assert result['message'] == 'segment 408 failed'
    assert 'error_explanation' not in result
    assert 'error_code' not in normalize_map_error('baidu', 'baidu_jsapi_route', 'segment 220 failed')


def test_summary_is_idempotent_bounded_and_keeps_explanation():
    result = {'provider': 'amap', 'api_type': 'amap_jsapi', 'diagnostic_id': 'example-id',
              'error': 'INVALID_USER_SCODE ' + '详情' * 6000,
              'error_code': 'INVALID_USER_SCODE', 'error_explanation': '安全码未通过验证',
              'error_hint': '检查安全密钥与 Key 是否配套'}
    summary = build_route_failure_summary(result)
    assert build_route_failure_summary(summary) == summary
    for ascii_only in (False, True):
        assert len(json.dumps(summary, ensure_ascii=ascii_only).encode()) <= 2048
    assert '安全码未通过验证' in detailed_route_failure_message(summary)
    assert summary['api_type'] == 'amap_jsapi'


def test_success_and_unknown_namespaces_are_not_errors():
    assert describe_map_error('amap', 'amap_jsapi', 'OK') == {}
    assert describe_map_error('baidu', 'baidu_jsapi_route', 0) == {}
    assert describe_map_error('tencent', 'tencent_jsapi_gl', -1) == {}


def test_common_provider_codes_all_have_independent_explanations_and_hints():
    catalogs = {
        ('amap', 'amap_jsapi'): (
            'SERVICE_NOT_AVAILABLE', 'INVALID_USER_KEY', 'INVALID_USER_SCODE', 'INVALID_USER_DOMAIN',
            'USERKEY_PLAT_NOMATCH', 'NOT_SUPPORT_HTTPS', 'INSUFFICIENT_PRIVILEGES', 'USER_KEY_RECYCLED',
            'INVALID_PARAMS', 'MISSING_REQUIRED_PARAMS', 'UNKNOWN_ERROR', 'OUT_OF_SERVICE',
            'NO_ROADS_NEARBY', 'ROUTE_FAIL', 'OVER_DIRECTION_RANGE', 'ENGINE_RESPONSE_DATA_ERROR',
        ),
        ('baidu', 'baidu_jsapi_route'): tuple(range(1, 9)),
        ('baidu', 'baidu_jsapi_auth'): (
            101, 102, 200, 201, 202, 203, 210, 211, 220, 230, 240, 250, 251, 252, 260, 261,
            301, 302, 311, 401, 402, 502, 503, 8001,
        ),
        ('tencent', 'tencent_webservice'): (
            110, 111, 112, 113, 120, 121, 160, 161, 190, 199, 300, 301, 306, 310, 311, 320,
            324, 326, 327, 328, 329, 330, 331, 332, 333, 335, 341, 344, 347, 348, 351, 365,
            366, 373, 374, 375, 377, 378, 379, 380, 382, 384, 387, 393, 394, 395, 396, 397,
            399, 400, 402, 403, 404, 405, 406, 407, 408, 500, 510, 520, 530, 531, 600,
        ),
        ('tianditu', 'tianditu_drive'): (301001, 301012, 308010, 308011),
    }
    for (provider, api_type), codes in catalogs.items():
        for code in codes:
            result = describe_map_error(provider, api_type, code)
            assert result.get('error_explanation'), (provider, api_type, code)
            assert result.get('error_hint'), (provider, api_type, code)
            assert result.get('retryable') in (True, False, None), (provider, api_type, code)
            result['error_explanation'] = 'changed by caller'
            assert describe_map_error(provider, api_type, code)['error_explanation'] != 'changed by caller'


def test_baidu_auth_and_route_namespaces_keep_different_codes_and_retry_rules():
    assert describe_map_error('baidu', 'baidu_jsapi_auth', 4) == {}
    assert describe_map_error('baidu', 'baidu_jsapi_route', 220) == {}
    assert describe_map_error('baidu', 'baidu_jsapi_route', 4)['retryable'] is False
    assert describe_map_error('baidu', 'baidu_jsapi_route', 7)['retryable'] is True
    assert describe_map_error('baidu', 'baidu_jsapi_route', 8)['retryable'] is True
    assert describe_map_error('baidu', 'baidu_jsapi_auth', 302)['retryable'] is False
    assert describe_map_error('baidu', 'baidu_jsapi_auth', 401)['retryable'] is True
