import tempfile
import unittest
from pathlib import Path

from main import (
    _get_session_theme_background_binding,
    _load_random_background_index,
    _resolve_theme_background_binding_decision,
    _save_random_background_index,
    _set_session_theme_background_binding,
)


class TestThemeBackgroundBinding(unittest.TestCase):
    def test_index_backward_compatible_with_session_bindings(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            index = _load_random_background_index(str(cache_dir))
            self.assertIn("files", index)
            self.assertIn("feedback", index)
            self.assertIn("session_bindings", index)

            index["session_bindings"]["sid-1"] = {
                "pc": {
                    "image_url": "/theme-assets/random_background_image/pc_a.jpg",
                    "bound_at": "2026-04-09T10:00:00+08:00",
                    "expires_at": "2099-01-01T00:00:00+00:00",
                }
            }
            _save_random_background_index(str(cache_dir), index)
            reloaded = _load_random_background_index(str(cache_dir))
            self.assertIn("sid-1", reloaded["session_bindings"])

    def test_set_and_get_binding_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            _set_session_theme_background_binding(
                str(cache_dir),
                session_uuid="sid-2",
                target="pc",
                image_url="/theme-assets/random_background_image/pc_b.jpg",
                ttl_seconds=1800,
            )
            binding = _get_session_theme_background_binding(str(cache_dir), "sid-2", "pc")
            self.assertIsNotNone(binding)
            self.assertEqual(
                binding["image_url"],
                "/theme-assets/random_background_image/pc_b.jpg",
            )

    def test_reuse_unexpired_binding(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            first = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-reuse",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_1.jpg",
                login_context=False,
                candidate_image_url="",
                ttl_seconds=1800,
            )
            self.assertEqual(first["action"], "bind_new")

            second = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-reuse",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_2.jpg",
                login_context=False,
                candidate_image_url="",
                ttl_seconds=1800,
            )
            self.assertEqual(second["action"], "reuse_existing")
            self.assertEqual(
                second["selected_image_url"],
                "/theme-assets/random_background_image/pc_1.jpg",
            )

    def test_login_context_overrides_unexpired_binding(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-override",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_old.jpg",
                login_context=False,
                candidate_image_url="",
                ttl_seconds=1800,
            )
            result = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-override",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_old.jpg",
                login_context=True,
                candidate_image_url="/theme-assets/random_background_image/pc_new.jpg",
                ttl_seconds=1800,
            )
            self.assertEqual(result["action"], "override_binding")
            self.assertEqual(
                result["selected_image_url"],
                "/theme-assets/random_background_image/pc_new.jpg",
            )

    def test_login_context_without_candidate_falls_back_to_current_image(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            result = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="sid-fallback",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_current.jpg",
                login_context=True,
                candidate_image_url="",
                ttl_seconds=1800,
            )
            self.assertEqual(result["action"], "bind_new")
            self.assertEqual(
                result["selected_image_url"],
                "/theme-assets/random_background_image/pc_current.jpg",
            )

    def test_null_literal_session_uuid_is_treated_as_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            cache_dir = Path(d)
            result = _resolve_theme_background_binding_decision(
                cache_dir=str(cache_dir),
                session_uuid="null",
                target="pc",
                current_image_url="/theme-assets/random_background_image/pc_current.jpg",
                login_context=True,
                candidate_image_url="/theme-assets/random_background_image/pc_candidate.jpg",
                ttl_seconds=1800,
            )
            self.assertEqual(result["action"], "noop")
            self.assertEqual(
                result["selected_image_url"],
                "/theme-assets/random_background_image/pc_current.jpg",
            )
            index_data = _load_random_background_index(str(cache_dir))
            self.assertEqual(index_data.get("session_bindings", {}), {})


if __name__ == "__main__":
    unittest.main()
