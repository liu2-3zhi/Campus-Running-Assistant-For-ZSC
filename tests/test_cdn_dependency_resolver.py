import unittest

from main import _resolve_relative_require_url, _split_package_require


class TestCdnDependencyResolver(unittest.TestCase):
    def test_resolve_relative(self):
        base = 'https://cdn.jsdelivr.net/npm/flowchart.js/index.js'
        self.assertEqual(
            _resolve_relative_require_url(base, './src/flowchart.shim'),
            'https://cdn.jsdelivr.net/npm/flowchart.js/src/flowchart.shim.js',
        )

    def test_split_package_require(self):
        self.assertEqual(_split_package_require('jquery'), ('jquery', ''))
        self.assertEqual(_split_package_require('lodash/fp'), ('lodash', 'fp'))
        self.assertEqual(_split_package_require('@scope/pkg/subpath'), ('@scope/pkg', 'subpath'))


if __name__ == '__main__':
    unittest.main()
