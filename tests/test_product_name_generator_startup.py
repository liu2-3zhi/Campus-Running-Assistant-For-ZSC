import unittest
from unittest import mock

import main as main_module


class TestProductNameGeneratorStartupValidation(unittest.TestCase):
    def test_startup_validation_accepts_registered_mode(self):
        with mock.patch.object(main_module, "PRODUCT_NAME_GENERATOR_MODE", "travel_service", create=True), \
             mock.patch.object(main_module, "validate_product_name_generator_mode") as validate_mode, \
             mock.patch.object(main_module, "logging") as fake_logging:
            main_module._validate_product_name_generator_startup_config()

        validate_mode.assert_called_once_with("travel_service")
        fake_logging.info.assert_called()

    def test_startup_validation_exits_on_invalid_mode(self):
        with mock.patch.object(main_module, "PRODUCT_NAME_GENERATOR_MODE", "broken_mode", create=True), \
             mock.patch.object(
                 main_module,
                 "validate_product_name_generator_mode",
                 side_effect=ValueError("PRODUCT_NAME_GENERATOR_MODE 配置无效: 'broken_mode'"),
             ), \
             mock.patch.object(main_module, "logging") as fake_logging, \
             mock.patch("builtins.print") as fake_print:
            with self.assertRaises(SystemExit) as ctx:
                main_module._validate_product_name_generator_startup_config()

        self.assertEqual(ctx.exception.code, 1)
        fake_print.assert_called_once()
        fake_logging.error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
