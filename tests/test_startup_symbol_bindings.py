import unittest

import main


class TestStartupSymbolBindings(unittest.TestCase):
    def test_theme_background_warmup_symbols_are_exported(self):
        self.assertTrue(
            callable(main._start_default_theme_background_cache_warmup)
        )
        self.assertTrue(callable(main._ensure_random_background_cache_count))
        self.assertTrue(callable(main._fetch_random_background_image))
        self.assertTrue(callable(main._build_theme_background_image_url))


if __name__ == "__main__":
    unittest.main()
