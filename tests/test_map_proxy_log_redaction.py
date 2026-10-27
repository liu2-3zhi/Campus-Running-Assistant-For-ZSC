import json
import logging

import pytest

import main


MAP_SECRET_FIELDS = (
    "key", "ak", "tk", "jscode", "jsCode", "js_code", "js-code",
    "securityJsCode", "security_js_code", "security-js-code",
)


@pytest.mark.parametrize("field", MAP_SECRET_FIELDS)
def test_upstream_urllib3_debug_record_redacts_map_credentials(field):
    record = logging.LogRecord(
        "urllib3.connectionpool", logging.DEBUG, __file__, 1,
        '%s://%s:%s "%s %s HTTP/1.1" %s %s',
        ("https", "api.tianditu.gov.cn", 443, "GET",
         f"/route?{field}=private-map-credential&status=OK", 200, 42), None,
    )
    rendered = main.SensitiveLogFormatter("%(message)s").format(record)
    assert "private-map-credential" not in rendered
    assert f"{field}=<redacted>" in rendered
    assert "api.tianditu.gov.cn" in rendered
    assert "status=OK" in rendered
    assert "200 42" in rendered


@pytest.mark.parametrize("field", MAP_SECRET_FIELDS)
@pytest.mark.parametrize("representation", (json.dumps, repr))
def test_map_credentials_redacted_in_non_url_dictionary_logs(field, representation):
    payload = {field: "private-map-credential", "status": "OK"}
    record = logging.LogRecord(
        "map_runtime", logging.INFO, __file__, 1, "%s",
        (representation(payload),), None,
    )
    rendered = main.SensitiveLogFormatter("%(message)s").format(record)
    assert "private-map-credential" not in rendered
    assert "<redacted>" in rendered
    assert "status" in rendered and "OK" in rendered


@pytest.mark.parametrize("field", MAP_SECRET_FIELDS)
def test_structured_log_boundary_redacts_exact_map_secret_field_names(field):
    payload = {"nested": {field: "private-map-credential"}, "task": "visible-task"}
    redacted = main._redact_sensitive_log_value(payload)
    assert redacted["nested"][field] == "<redacted>"
    assert redacted["task"] == "visible-task"
    assert payload["nested"][field] == "private-map-credential"


def test_short_map_secret_names_do_not_hide_unrelated_fields():
    payload = {"task": "visible-task", "remark": "visible-remark", "track": "visible-track"}
    assert main._redact_sensitive_log_value(payload) == payload
    assert main._redact_sensitive_log_text("task=visible-task remark=visible-remark track=visible-track") == (
        "task=visible-task remark=visible-remark track=visible-track"
    )
