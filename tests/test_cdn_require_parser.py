import unittest

from main import (
    _build_dep_storage_name,
    _extract_commonjs_requires,
    _rewrite_requires_to_local,
)


class TestCdnRequireParser(unittest.TestCase):
    def test_extract_commonjs_requires(self):
        source = """
        require('./src/flowchart.shim');
        var parse = require('./src/flowchart.parse');
        require('jquery');
        require('lodash/fp');
        """
        requires = _extract_commonjs_requires(source)
        self.assertEqual(
            requires,
            ['./src/flowchart.shim', './src/flowchart.parse', 'jquery', 'lodash/fp'],
        )

    def test_build_dep_storage_name(self):
        self.assertEqual(
            _build_dep_storage_name('flowchart', './src/flowchart.shim', '.js'),
            'flowchart_src_flowchart.shim.js',
        )
        self.assertEqual(
            _build_dep_storage_name('flowchart', 'lodash/fp', '.js'),
            'lodash_fp.js',
        )

    def test_rewrite_to_local(self):
        source = """
        require('./src/flowchart.shim');
        var parse = require('./src/flowchart.parse');
        require('jquery');
        """
        mapping = {
            './src/flowchart.shim': './flowchart/flowchart_src_flowchart.shim.js',
            './src/flowchart.parse': './flowchart/flowchart_src_flowchart.parse.js',
            'jquery': './flowchart/jquery_index.js',
        }
        out = _rewrite_requires_to_local(source, mapping)
        self.assertIn("require('./flowchart/flowchart_src_flowchart.shim.js')", out)
        self.assertIn("require('./flowchart/flowchart_src_flowchart.parse.js')", out)
        self.assertIn("require('./flowchart/jquery_index.js')", out)


if __name__ == '__main__':
    unittest.main()
