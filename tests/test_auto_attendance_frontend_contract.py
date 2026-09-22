from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_attendance_controls_expose_auto_disable_defaults():
    source = (ROOT / "index.html").read_text(encoding="utf-8")

    assert source.count('data-key="auto_attendance_stop_after_success"') == 3
    assert source.count('data-key="auto_attendance_success_limit"') == 3
    assert source.count('id="param-auto_attendance_stop_after_success"') == 1
    assert source.count('id="mobile-param-auto_attendance_stop_after_success"') == 1
    assert source.count('id="mobile-multi-auto_attendance_stop_after_success"') == 1
    assert source.count('id="param-auto_attendance_success_limit"') == 1
    assert source.count('id="mobile-param-auto_attendance_success_limit"') == 1
    assert source.count('id="mobile-multi-auto_attendance_success_limit"') == 1
    assert source.count('value="1"') >= 3


def test_frontend_parameter_metadata_matches_backend_keys():
    legacy = (ROOT / "frontend/src/utils/legacyParams.js").read_text(encoding="utf-8")
    vue = (ROOT / "frontend/src/config/params.js").read_text(encoding="utf-8")
    control_tabs = (ROOT / "frontend/src/components/main/ControlTabs.vue").read_text(
        encoding="utf-8"
    )

    for source in (legacy, vue, control_tabs):
        assert "auto_attendance_stop_after_success" in source
        assert "auto_attendance_success_limit" in source

    assert "default: true" in vue
    assert "default: 1" in vue
    assert "min=\"1\"" in control_tabs


def test_frontends_sync_backend_auto_close_event():
    legacy = (ROOT / "scripts/main.js").read_text(encoding="utf-8")
    vue_socket = (ROOT / "frontend/src/services/socket.js").read_text(encoding="utf-8")

    assert 'auto_attendance_updated' in legacy
    assert 'auto_attendance_updated' in vue_socket
    assert 'auto_attendance_enabled = false' in legacy
    assert 'auto_attendance_enabled: false' in vue_socket
