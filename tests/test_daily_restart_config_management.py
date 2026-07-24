import unittest

import main as main_module


class TestDailyRestartConfigManagement(unittest.TestCase):
    def test_default_config_exposes_daily_restart_defaults(self):
        config = main_module._get_default_config()

        self.assertTrue(config.has_section("Daily_Restart"))
        self.assertEqual(config.get("Daily_Restart", "enabled"), "false")
        self.assertEqual(config.get("Daily_Restart", "time"), "00:00")

    def test_parse_daily_restart_config_reads_enabled_and_time(self):
        config = main_module._get_default_config()
        config.set("Daily_Restart", "enabled", "true")
        config.set("Daily_Restart", "time", "23:45")

        parsed = main_module._get_daily_restart_schedule_config(config)

        self.assertEqual(
            parsed,
            {
                "enabled": True,
                "time": "23:45",
                "hour": 23,
                "minute": 45,
                "valid": True,
            },
        )

    def test_parse_daily_restart_config_rejects_invalid_time(self):
        config = main_module._get_default_config()
        config.set("Daily_Restart", "enabled", "true")
        config.set("Daily_Restart", "time", "24:00")

        parsed = main_module._get_daily_restart_schedule_config(config)

        self.assertTrue(parsed["enabled"])
        self.assertEqual(parsed["time"], "24:00")
        self.assertFalse(parsed["valid"])
        self.assertIsNone(parsed["hour"])
        self.assertIsNone(parsed["minute"])

    def test_daily_restart_view_data_returns_defaults_when_section_missing(self):
        config = main_module._get_default_config()
        config.remove_section("Daily_Restart")

        view_data = main_module._get_daily_restart_config_view_data(config)

        self.assertEqual(
            view_data,
            {
                "enabled": False,
                "time": "00:00",
            },
        )

    def test_apply_daily_restart_config_updates_writes_enabled_and_time(self):
        config = main_module._get_default_config()

        main_module._apply_daily_restart_config_updates(
            config,
            {
                "enabled": True,
                "time": "23:45",
            },
        )

        self.assertEqual(config.get("Daily_Restart", "enabled"), "true")
        self.assertEqual(config.get("Daily_Restart", "time"), "23:45")

    def test_apply_daily_restart_config_updates_rejects_invalid_time(self):
        config = main_module._get_default_config()

        with self.assertRaises(ValueError):
            main_module._apply_daily_restart_config_updates(
                config,
                {
                    "enabled": True,
                    "time": "24:00",
                },
            )

    def test_admin_config_load_route_exposes_daily_restart_config(self):
        with open(main_module.__file__, "r", encoding="utf-8") as fp:
            source = fp.read()

        start = source.index('@app.route("/api/admin/config/load", methods=["GET"])')
        end = source.index('@app.route("/api/admin/config/save", methods=["POST"])', start)
        route_source = source[start:end]

        self.assertIn('"Daily_Restart": _get_daily_restart_config_view_data(config)', route_source)

    def test_admin_config_save_route_applies_daily_restart_updates(self):
        with open(main_module.__file__, "r", encoding="utf-8") as fp:
            source = fp.read()

        start = source.index('@app.route("/api/admin/config/save", methods=["POST"])')
        end = source.index('@app.route("/api/log_frontend", methods=["POST"])', start)
        route_source = source[start:end]

        self.assertIn('_apply_daily_restart_config_updates(config, data["Daily_Restart"])', route_source)


if __name__ == "__main__":
    unittest.main()
