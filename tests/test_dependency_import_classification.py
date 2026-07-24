import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_ROOT / "main.py"


class TestDependencyImportClassification(unittest.TestCase):
    def test_eventlet_is_not_checked_as_standard_library(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        standard_block = source.split("def import_standard_libraries():", 1)[1].split(
            "def import_core_third_party():", 1
        )[0]

        std_lib_block = standard_block.split("std_libs = [", 1)[1].split("]", 1)[0]
        self.assertNotIn('(\"eventlet\", \"import eventlet\")', std_lib_block)

    def test_eventlet_remains_a_core_third_party_dependency(self):
        source = MAIN_PATH.read_text(encoding="utf-8")
        core_block = source.split("def import_core_third_party():", 1)[1].split(
            "def check_and_import_dependencies():", 1
        )[0]

        self.assertIn('(\"eventlet\", \"import eventlet\", \"eventlet\")', core_block)


if __name__ == "__main__":
    unittest.main()
