import unittest

import main as main_module


class TestLocationCacheBounds(unittest.TestCase):
    def test_prune_timestamped_cache_removes_expired_entries(self):
        cache = {
            "expired": {"location": "old", "timestamp": 100},
            "fresh": {"location": "new", "timestamp": 950},
        }

        main_module._prune_timestamped_cache(
            cache,
            ttl_seconds=100,
            max_entries=10,
            now_ts=1000,
        )

        self.assertEqual(list(cache), ["fresh"])

    def test_prune_timestamped_cache_enforces_max_entries(self):
        cache = {
            f"key-{index}": {
                "location": str(index),
                "timestamp": 1000 + index,
            }
            for index in range(10)
        }

        main_module._prune_timestamped_cache(
            cache,
            ttl_seconds=1000,
            max_entries=3,
            now_ts=1100,
        )

        self.assertEqual(list(cache), ["key-7", "key-8", "key-9"])

    def test_phone_cache_timestamp_is_required_for_fresh_hit(self):
        cache = {
            "legacy": {"province": "old"},
            "fresh": {"province": "new", "timestamp": 990},
        }

        main_module._prune_timestamped_cache(
            cache,
            ttl_seconds=100,
            max_entries=10,
            now_ts=1000,
        )

        self.assertEqual(list(cache), ["fresh"])


if __name__ == "__main__":
    unittest.main()
