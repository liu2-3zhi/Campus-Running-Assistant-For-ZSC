import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "main.new.js"


def _extract_js_section(source, start_marker, end_marker):
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


class TestDailyRestartSystemConfigUi(unittest.TestCase):
    def test_load_system_config_renders_daily_restart_controls(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        load_system_config_source = _extract_js_section(
            source,
            "async function loadSystemConfig() {",
            "\nasync function saveSystemConfig() {",
        )

        self.assertIn('"Daily_Restart"', load_system_config_source)
        self.assertIn('"enabled"', load_system_config_source)
        self.assertIn('"time"', load_system_config_source)
        self.assertIn("每日自动重启", load_system_config_source)
        self.assertIn('createInput(\n      "Daily_Restart",\n      "enabled",', load_system_config_source)
        self.assertIn('createInput(\n      "Daily_Restart",\n      "time",', load_system_config_source)

    def test_save_system_config_submits_daily_restart_payload(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        save_system_config_source = _extract_js_section(
            source,
            "async function saveSystemConfig() {",
            "\nfunction showTempMessage",
        )

        self.assertIn('Daily_Restart:', save_system_config_source)
        self.assertIn('enabled: $("config-Daily_Restart-enabled").value === "true"', save_system_config_source)
        self.assertIn('time: ($("config-Daily_Restart-time").value || "").trim()', save_system_config_source)


if __name__ == "__main__":
    unittest.main()
