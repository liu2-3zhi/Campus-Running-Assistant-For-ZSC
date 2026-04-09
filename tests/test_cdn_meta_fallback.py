import unittest
from unittest.mock import patch

from main import _load_cdn_meta, _meta_set_mapping, _save_cdn_meta, _load_or_refetch_cached_file


class TestCdnMeta(unittest.TestCase):
    def test_meta_roundtrip_and_mapping(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            meta_path = os.path.join(d, 'flowchart.meta.json')
            meta = _load_cdn_meta(meta_path)
            self.assertEqual(meta['url_to_local'], {})
            self.assertEqual(meta['local_to_url'], {})

            _meta_set_mapping(meta, 'https://cdn.jsdelivr.net/npm/flowchart.js/index.js', 'flowchart.js')
            _save_cdn_meta(meta_path, meta)

            saved = _load_cdn_meta(meta_path)
            self.assertEqual(saved['url_to_local']['https://cdn.jsdelivr.net/npm/flowchart.js/index.js'], 'flowchart.js')
            self.assertEqual(saved['local_to_url']['flowchart.js'], 'https://cdn.jsdelivr.net/npm/flowchart.js/index.js')


class TestLocalFallback(unittest.TestCase):
    @patch('main.save_cached_file', create=True)
    @patch('main.fetch_cdn_file', create=True)
    @patch('main.load_cached_file', create=True)
    def test_refetch_when_local_missing(self, mock_load, mock_fetch, mock_save):
        mock_load.return_value = None
        mock_fetch.return_value = 'module.exports = {}'
        meta = {
            'local_to_url': {
                'flowchart/flowchart_src_flowchart.shim.js': 'https://cdn.jsdelivr.net/npm/flowchart.js/src/flowchart.shim.js'
            }
        }
        content = _load_or_refetch_cached_file('flowchart/flowchart_src_flowchart.shim.js', meta)
        self.assertEqual(content, 'module.exports = {}')
        mock_fetch.assert_called_once_with(
            'https://cdn.jsdelivr.net/npm/flowchart.js/src/flowchart.shim.js',
            binary=False,
        )
        mock_save.assert_called_once()


if __name__ == '__main__':
    unittest.main()
