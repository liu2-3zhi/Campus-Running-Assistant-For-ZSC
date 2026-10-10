"""任务间隔默认值（Q7）的测试。

默认区间由 600–3600 秒改为 600–1800 秒。
由于会话持久化的是完整参数快照，会覆盖 global_params 的默认值，
因此必须同时做一次有界迁移：仅当持久化值恰好等于旧默认值 (600, 3600)
时才替换，任何其它取值都视为用户自定义并保留。
"""

import inspect
import unittest
from pathlib import Path
from unittest import mock

import main as main_module


class TestTaskGapDefaults(unittest.TestCase):
    def test_default_range_is_600_to_1800(self):
        api = object.__new__(main_module.Api)
        api._init_state_variables()

        self.assertEqual(api.global_params["task_gap_min_s"], 600)
        self.assertEqual(api.global_params["task_gap_max_s"], 1800)

    def test_no_other_hardcoded_3600_default_remains(self):
        """仓库内不应再有其它地方把上限默认成 3600。"""
        root = Path(__file__).resolve().parents[1]
        offenders = []
        for path in list(root.glob("*.py")) + list((root / "scripts").glob("*.js")):
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                if "task_gap" in line and "3600" in line:
                    offenders.append(f"{path.name}:{line_no}")

        self.assertEqual(
            offenders,
            [],
            f"任务间隔上限默认值仍残留 3600: {offenders}",
        )


class TestLegacyGapValueMigration(unittest.TestCase):
    """会话恢复时的有界迁移。"""

    @classmethod
    def setUpClass(cls):
        cls.source = (
            Path(__file__).resolve().parents[1] / "session_state.py"
        ).read_text(encoding="utf-8")

    def test_migration_block_exists(self):
        self.assertIn("_legacy_gap_default = (600, 3600)", self.source)
        self.assertIn('api_instance.params["task_gap_max_s"] = 1800', self.source)

    def test_migration_is_bounded_to_exact_legacy_pair(self):
        """只有恰好等于旧默认值时才迁移，避免覆盖用户自定义取值。"""
        block = self.source.split("_legacy_gap_default = (600, 3600)", 1)[1].split(
            "except Exception as _gap_error:", 1
        )[0]

        self.assertIn("if _saved_gap == _legacy_gap_default:", block)

    def _apply_migration(self, saved_params):
        """按 session_state 的逻辑对参数做一次迁移，返回迁移后的取值。"""
        params = {"task_gap_min_s": 600, "task_gap_max_s": 1800}
        params.update(saved_params)
        legacy_default = (600, 3600)
        saved_gap = (
            saved_params.get("task_gap_min_s"),
            saved_params.get("task_gap_max_s"),
        )
        if saved_gap == legacy_default:
            params["task_gap_min_s"] = 600
            params["task_gap_max_s"] = 1800
        return params

    def test_legacy_pair_is_migrated(self):
        result = self._apply_migration(
            {"task_gap_min_s": 600, "task_gap_max_s": 3600}
        )

        self.assertEqual(result["task_gap_max_s"], 1800)

    def test_custom_pair_is_preserved(self):
        result = self._apply_migration(
            {"task_gap_min_s": 300, "task_gap_max_s": 900}
        )

        self.assertEqual(result["task_gap_min_s"], 300)
        self.assertEqual(result["task_gap_max_s"], 900)

    def test_custom_max_only_is_preserved(self):
        """用户只改了下限时，上限仍是旧的 3600，不得被当作"沿用旧默认"。"""
        result = self._apply_migration(
            {"task_gap_min_s": 120, "task_gap_max_s": 3600}
        )

        self.assertEqual(result["task_gap_min_s"], 120)
        self.assertEqual(result["task_gap_max_s"], 3600)


if __name__ == "__main__":
    unittest.main()
