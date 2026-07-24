import unittest
from unittest import mock

import product_name_generator as png


class TestProductNameGeneratorModes(unittest.TestCase):
    def test_supported_modes_include_lomei_and_travel_service(self):
        self.assertEqual(
            png.get_supported_product_name_generator_modes(),
            ("lomei", "travel_service"),
        )

    def test_invalid_mode_raises_clear_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            png.validate_product_name_generator_mode("bad_mode")

        message = str(ctx.exception)
        self.assertIn("PRODUCT_NAME_GENERATOR_MODE", message)
        self.assertIn("bad_mode", message)
        self.assertIn("lomei", message)
        self.assertIn("travel_service", message)

    def test_lomei_mode_keeps_existing_single_item_style(self):
        with mock.patch.object(png, "PRODUCT_NAME_GENERATOR_MODE", "lomei"):
            generator = png.LoMeiGenerator()
            with mock.patch.object(
                png.random,
                "choice",
                side_effect=["鸭脖", "串", "快乐的", "麻辣", "一串快乐的麻辣鸭脖"],
            ):
                result = generator.generate(1)

        self.assertEqual(result, "一串快乐的麻辣鸭脖")

    def test_travel_service_mode_uses_fixed_item_quantifier(self):
        with mock.patch.object(png, "PRODUCT_NAME_GENERATOR_MODE", "travel_service"):
            generator = png.LoMeiGenerator()
            with mock.patch.object(
                png.random,
                "choice",
                return_value={"name": "短信费", "quantifier": "次"},
            ):
                result = generator.generate(2)

        self.assertEqual(result, "二次短信费")

    def test_invalid_quantity_returns_none(self):
        with mock.patch.object(png, "PRODUCT_NAME_GENERATOR_MODE", "travel_service"):
            generator = png.LoMeiGenerator()
        self.assertIsNone(generator.generate(0))


if __name__ == "__main__":
    unittest.main()
