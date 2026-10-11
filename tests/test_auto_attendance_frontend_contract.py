from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _input_tag(html: str, element_id: str) -> str:
    match = re.search(
        r'<input\b[^>]*?id="' + re.escape(element_id) + r'"[^>]*?>', html, re.S
    )
    assert match is not None, f"未找到 id={element_id} 的 input"
    return match.group(0)


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


def test_all_three_auto_close_controls_default_to_checked():
    """桌面端 / 移动端 / 移动端多账号三个控件都必须默认勾选。

    这三处曾不一致过（「自动生成路径」就是桌面端漏了 checked），
    而漏掉的那一端会静默退回未勾选，用户很难发现，所以显式断言。
    """
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    for element_id in (
        "param-auto_attendance_stop_after_success",
        "mobile-param-auto_attendance_stop_after_success",
        "mobile-multi-auto_attendance_stop_after_success",
    ):
        tag = _input_tag(html, element_id)
        assert "checked" in tag, f"{element_id} 缺少 checked 默认属性"


def test_inverse_semantics_controls_stay_unchecked():
    """「运行已完成任务」是相反语义，必须保持未勾选。"""
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    for element_id in ("run-completed-check", "mobile-run-completed-check"):
        tag = _input_tag(html, element_id)
        assert "checked" not in tag, f"{element_id} 不应默认勾选"



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
    legacy = "\n\n".join(
        (
            (ROOT / "scripts/legacy-app-runtime.js").read_text(encoding="utf-8"),
            (ROOT / "scripts/main.js").read_text(encoding="utf-8"),
        )
    )
    vue_socket = (ROOT / "frontend/src/services/socket.js").read_text(encoding="utf-8")

    assert 'auto_attendance_updated' in legacy
    assert 'auto_attendance_updated' in vue_socket
    assert 'auto_attendance_enabled = false' in legacy
    assert 'auto_attendance_enabled: false' in vue_socket
