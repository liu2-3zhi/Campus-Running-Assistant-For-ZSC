import datetime
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import auth_system
import runtime_models
import theme_background_cache
import theme_background_legacy
import theme_background_state
from theme_background_state import BackgroundStateStore


class TestBackgroundCacheSafety(unittest.TestCase):
    def _main_stub(self):
        return SimpleNamespace(
            RANDOM_BACKGROUND_IMAGE_DIR="random_background_image",
            _load_random_background_index=theme_background_legacy._load_random_background_index,
            _save_random_background_index=theme_background_legacy._save_random_background_index,
            _cleanup_random_background_index=runtime_models._cleanup_random_background_index,
            _get_random_background_index_entry=theme_background_legacy._get_random_background_index_entry,
            _mark_random_background_file_state=theme_background_legacy._mark_random_background_file_state,
            _mark_random_background_file_expired=theme_background_legacy._mark_random_background_file_expired,
            _build_theme_background_image_url=theme_background_cache._build_theme_background_image_url,
            _cleanup_random_background_cache=Mock(),
            _BACKGROUND_SELECTION_LOCK=threading.Lock(),
            _BACKGROUND_SELECTION_STATE={},
        )

    def _write(self, directory, name, content=b"0123456789", mtime=1):
        path = Path(directory) / name
        path.write_bytes(content)
        os.utime(path, (mtime, mtime))
        return path

    def _cleanup(self, directory, limit=1):
        with patch.object(runtime_models, "_main", return_value=self._main_stub()):
            runtime_models._cleanup_random_background_cache(directory, limit)

    def test_cleanup_preserves_state_temp_and_new_and_legacy_bound_images(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            bundle = store.create_bundle(
                "/theme-assets/random_background_image/pc_bound.jpg",
                "/theme-assets/random_background_image/mb_bound.png",
                "test",
            )
            store.bind_identity("user:test", bundle["bundle_id"], "test")
            theme_background_legacy._set_session_theme_background_binding(
                directory,
                "legacy-session",
                "pc",
                "/theme-assets/random_background_image/pc_legacy.jpg",
            )
            keep = [
                "pc_bound.jpg", "mb_bound.png", "pc_legacy.jpg", "pc_partial.jpg.tmp",
                "background_state.json.tmp", "unrelated.txt",
            ]
            for name in keep:
                self._write(directory, name)
            stale = self._write(directory, "pc_stale.jpg", mtime=2)
            state_before = Path(store.path).read_bytes()
            with self.assertLogs(level="WARNING") as warning:
                self._cleanup(directory)
            self.assertFalse(stale.exists())
            self.assertEqual(Path(store.path).read_bytes(), state_before)
            self.assertTrue((Path(directory) / "index.json").exists())
            self.assertTrue(all((Path(directory) / name).exists() for name in keep))
            self.assertTrue(warning.output, "Over-quota protected files must be reported")

    def test_cleanup_preserves_all_bundles_including_unbound_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            store.create_bundle(
                "/theme-assets/random_background_image/pc_preview.jpg", "", "preview", consume=False
            )
            image = self._write(directory, "pc_preview.jpg")
            self._cleanup(directory)
            self.assertTrue(image.exists())

    def test_cleanup_protects_local_url_path_with_query_and_percent_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            BackgroundStateStore(directory).create_bundle(
                "/theme-assets/random_background_image/pc_%62ound.jpg?revision=2",
                "", "test",
            )
            image = self._write(directory, "pc_bound.jpg")
            self._cleanup(directory)
            self.assertTrue(image.exists())

    def test_cleanup_skips_deletion_for_invalid_state_or_index(self):
        cases = [
            ("background_state.json", b"{broken"),
            ("background_state.json", b'{"assignments": [], "bundles": {}}'),
            ("index.json", b"{broken"),
            ("index.json", b'{"session_bindings": []}'),
            ("index.json", b'{"session_bindings": {"sid": {"pc": {"image_url": "x", "expires_at": "bad"}}}}'),
        ]
        for file_name, content in cases:
            with self.subTest(file_name=file_name, content=content):
                with tempfile.TemporaryDirectory() as directory:
                    image = self._write(directory, "pc_keep.jpg")
                    metadata = self._write(directory, file_name, content)
                    self._cleanup(directory)
                    self.assertTrue(image.exists())
                    self.assertEqual(metadata.read_bytes(), content)

    def test_cleanup_skips_deletion_for_unreadable_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            image = self._write(directory, "pc_keep.jpg")
            Path(directory, "background_state.json").mkdir()
            self._cleanup(directory)
            self.assertTrue(image.exists())

    def test_cleanup_removes_expired_legacy_binding_image_with_missing_state(self):
        with tempfile.TemporaryDirectory() as directory:
            theme_background_legacy._save_random_background_index(directory, {
                "files": {}, "feedback": {}, "session_bindings": {"expired": {"pc": {
                    "image_url": "/theme-assets/random_background_image/pc_expired.jpg",
                    "expires_at": "2000-01-01T00:00:00+00:00",
                }}},
            })
            image = self._write(directory, "pc_expired.jpg")
            self._cleanup(directory)
            self.assertFalse(image.exists())

    def test_cleanup_never_unlinks_image_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._write(directory, "outside.txt")
            link = Path(directory) / "pc_link.jpg"
            try:
                link.symlink_to(source)
            except OSError as error:
                self.skipTest(f"Symbolic links unavailable: {error}")
            self._cleanup(directory)
            self.assertTrue(link.is_symlink())
            self.assertTrue(source.exists())

    def test_selection_ignores_partial_files_and_non_image_extensions(self):
        with tempfile.TemporaryDirectory() as directory:
            self._write(directory, "pc_partial.jpg.tmp")
            self._write(directory, "pc_notes.txt")
            self._write(directory, "pc_ready.jpg")
            main_stub = self._main_stub()
            with patch.object(auth_system, "_main", return_value=main_stub), patch.object(
                runtime_models, "_main", return_value=main_stub
            ):
                urls = auth_system.AuthSystem.__new__(auth_system.AuthSystem)._get_cached_random_background_image_urls(
                    directory, "pc", limit=0
                )
            self.assertEqual(urls, ["/theme-assets/random_background_image/pc_ready.jpg"])

    def test_state_store_lock_serializes_legacy_binding_transactions(self):
        with tempfile.TemporaryDirectory() as directory:
            first = BackgroundStateStore(directory)
            second = BackgroundStateStore(directory)
            self.assertIs(first.lock, second.lock)
            started = threading.Event()
            completed = threading.Event()

            def bind():
                started.set()
                theme_background_legacy._set_session_theme_background_binding(
                    directory, "sid", "pc", "/theme-assets/random_background_image/pc_locked.jpg"
                )
                completed.set()

            with first.lock:
                worker = threading.Thread(target=bind)
                worker.start()
                self.assertTrue(started.wait(1))
                self.assertFalse(completed.wait(0.05))
            worker.join(1)
            self.assertTrue(completed.is_set())

    def test_cleanup_waits_for_binding_transaction_and_retains_new_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            image = self._write(directory, "pc_selected.jpg")
            started = threading.Event()
            completed = threading.Event()

            def cleanup():
                started.set()
                self._cleanup(directory)
                completed.set()

            with store.lock:
                worker = threading.Thread(target=cleanup)
                worker.start()
                self.assertTrue(started.wait(1))
                self.assertFalse(completed.wait(0.05))
                bundle = store.create_bundle(
                    "/theme-assets/random_background_image/pc_selected.jpg", "", "test"
                )
                store.bind_identity("user:selected", bundle["bundle_id"], "test")
            worker.join(1)
            self.assertTrue(completed.is_set())
            self.assertTrue(image.exists())

    def test_concurrent_legacy_bindings_do_not_lose_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            start = threading.Barrier(8)
            errors = []

            def bind(index):
                try:
                    start.wait(timeout=2)
                    theme_background_legacy._set_session_theme_background_binding(
                        directory, f"sid-{index}", "pc",
                        f"/theme-assets/random_background_image/pc_{index}.jpg",
                    )
                except Exception as error:
                    errors.append(error)

            workers = [threading.Thread(target=bind, args=(index,)) for index in range(8)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(2)
            self.assertEqual(errors, [])
            self.assertTrue(all(not worker.is_alive() for worker in workers))
            index_data = theme_background_legacy._load_random_background_index(directory, strict=True)
            self.assertEqual(len(index_data["session_bindings"]), 8)

    def test_invalid_index_is_not_replaced_by_binding_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            index_path = self._write(directory, "index.json", b"{broken")
            with self.assertRaises(ValueError):
                theme_background_legacy._set_session_theme_background_binding(
                    directory, "sid", "pc", "/theme-assets/random_background_image/pc_a.jpg"
                )
            self.assertEqual(index_path.read_bytes(), b"{broken")

    def test_cleanup_logs_after_outermost_background_lock_is_released(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            store.create_bundle("/theme-assets/random_background_image/pc_keep.jpg", "", "test")
            self._write(directory, "pc_keep.jpg")
            emitted = []

            def log(level, message, *args, **kwargs):
                self.assertFalse(store.lock._is_owned())
                emitted.append(level)

            @theme_background_state.background_files_locked
            def outer_transaction():
                self._cleanup(directory)
                self.assertEqual(emitted, [])

            with patch.object(theme_background_state.logging, "log", side_effect=log):
                outer_transaction()
            self.assertIn(theme_background_state.logging.WARNING, emitted)

    def test_deferred_background_logs_preserve_exception_traceback(self):
        @theme_background_state.background_files_locked
        def failing_transaction():
            try:
                raise ValueError("test-background-error")
            except ValueError:
                theme_background_state.background_files_log(
                    theme_background_state.logging.DEBUG, "test failure", exc_info=True
                )

        with patch.object(theme_background_state.logging, "log") as log:
            failing_transaction()
        exception_info = log.call_args.kwargs["exc_info"]
        self.assertIsInstance(exception_info, tuple)
        self.assertIs(exception_info[0], ValueError)
        self.assertEqual(str(exception_info[1]), "test-background-error")
        self.assertIsNotNone(exception_info[2])

    def test_fetch_keeps_network_outside_lock_and_atomically_publishes_unique_images(self):
        with tempfile.TemporaryDirectory() as directory:
            store = BackgroundStateStore(directory)
            main_stub = self._main_stub()
            response = SimpleNamespace(status_code=200, headers={"Content-Type": "image/jpeg"}, content=b"complete-image")

            def get(*args, **kwargs):
                acquired = threading.Event()

                def probe():
                    with store.lock:
                        acquired.set()

                probe_thread = threading.Thread(target=probe)
                probe_thread.start()
                try:
                    self.assertTrue(acquired.wait(1), "Network request holds the background lock")
                finally:
                    probe_thread.join(1)
                return response

            main_stub.requests = SimpleNamespace(get=get, exceptions=SimpleNamespace(RequestException=RuntimeError))
            published = []
            real_replace = os.replace

            def publish(source, destination):
                if str(destination).endswith(".json"):
                    return real_replace(source, destination)
                self.assertTrue(str(source).endswith(".tmp"))
                self.assertEqual(Path(source).read_bytes(), response.content)
                self.assertTrue(store.lock._is_owned(), "Image publication must share the binding lock")
                published.append(str(destination))
                return real_replace(source, destination)

            fixed_time = datetime.datetime(2026, 10, 24, 12, 0, 0)
            with patch.object(theme_background_cache, "_main", return_value=main_stub), patch.object(
                theme_background_cache.os, "replace", side_effect=publish
            ), patch.object(theme_background_cache.datetime, "datetime", wraps=datetime.datetime) as clock:
                clock.now.return_value = fixed_time
                first = theme_background_cache._fetch_random_background_image(directory, "fake-key", "pc")
                second = theme_background_cache._fetch_random_background_image(directory, "fake-key", "pc")
            self.assertNotEqual(first, second)
            self.assertEqual(len(published), 2)
            self.assertEqual(len(list(Path(directory).glob("pc_*.jpg"))), 2)
            self.assertFalse(list(Path(directory).glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
