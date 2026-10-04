import unittest
from pathlib import Path
from unittest.mock import patch

import main
from main_runtime import _main


class TestStartupSymbolBindings(unittest.TestCase):
    def test_theme_background_warmup_symbols_are_exported(self):
        self.assertTrue(
            callable(main._start_default_theme_background_cache_warmup)
        )
        self.assertTrue(callable(main._ensure_random_background_cache_count))
        self.assertTrue(callable(main._fetch_random_background_image))
        self.assertTrue(callable(main._build_theme_background_image_url))
        self.assertTrue(callable(main.ChromeBrowserPool))
        self.assertTrue(callable(main.MicroPixelCaptcha))
        self.assertTrue(callable(main.PlaywrightPageProxy))
        self.assertTrue(callable(main.PlaywrightContextProxy))

    def test_runtime_resolution_survives_main_abspath_patch(self):
        with patch(
            "main.os.path.abspath",
            return_value=str(Path(__file__).resolve().parents[1] / "main.py"),
        ):
            self.assertIs(_main(), main)


if __name__ == "__main__":
    unittest.main()
