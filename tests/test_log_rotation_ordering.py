"""日志轮转策略的行为测试。

需求:
    - 不再"每次移动所有历史文件"；
    - `zx-slm-tool-01.log` 是最旧的；
    - 后续按编号往后延（`-02`、`-03`、…），编号越大越新；
    - WARNING / ERROR 处理器各自用自己的前缀，不能与主日志撞名。
"""

import logging
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import main


def _make_handler(path, max_bytes=100):
    handler = main.CustomLogHandler(path, mode="a", encoding="utf-8", max_bytes=max_bytes)
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


def _log(handler, message):
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname=__file__, lineno=1,
        msg=message, args=(), exc_info=None,
    )
    handler.emit(record)


class TestLogRotationOrdering(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="logrotate_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _path(self, name):
        return os.path.join(self.tmp, name)

    def _names(self, prefix="zx-slm-tool"):
        return sorted(
            n
            for n in os.listdir(self.tmp)
            if n.startswith(prefix) and n.endswith(".log")
        )

    def test_first_rollover_creates_backup_01(self):
        path = self._path("zx-slm-tool.log")
        handler = _make_handler(path)
        self.addCleanup(handler.close)

        for i in range(5):
            _log(handler, f"line-{i}-" + "x" * 30)

        names = self._names()
        self.assertIn("zx-slm-tool-01.log", names)
        self.assertIn("zx-slm-tool.log", names)

    def test_backup_numbers_increase_with_time(self):
        """编号必须与时间同向：编号越小越旧。

        注意编号是**单调递增**的，裁剪掉最旧的之后会留下编号空洞
        （例如只剩 -05..-14），这是预期行为：不能回收编号，
        否则"编号越大越新"这个不变量就破了。
        """
        path = self._path("zx-slm-tool.log")
        handler = _make_handler(path, max_bytes=60)
        self.addCleanup(handler.close)

        for i in range(30):
            _log(handler, f"gen{i:03d}-" + "y" * 40)

        names = self._names()
        numbered = sorted(
            (int(n[len("zx-slm-tool-") : -len(".log")]), n)
            for n in names
            if n != "zx-slm-tool.log"
        )
        self.assertGreaterEqual(
            len(numbered), 2, f"应产生多个历史文件，实际: {names}"
        )

        # 按修改时间排序后，编号必须同步递增（编号小 = 更旧）
        by_mtime = sorted(numbered, key=lambda item: os.path.getmtime(self._path(item[1])))
        indexes = [index for index, _ in by_mtime]
        self.assertEqual(
            indexes,
            sorted(indexes),
            f"编号与时间不同向: {by_mtime}",
        )

        # 编号不回收：最小值不会回到 1
        self.assertGreater(
            min(indexes),
            1,
            "裁剪最旧文件后编号不应被回收（否则新旧判断会失效）",
        )

    def test_oldest_surviving_backup_is_never_rewritten(self):
        """轮转只新增文件，绝不改名/改写仍然存在的最旧历史文件。"""
        path = self._path("zx-slm-tool.log")
        handler = _make_handler(path, max_bytes=60)
        self.addCleanup(handler.close)

        for i in range(10):
            _log(handler, f"first-batch-{i}-" + "z" * 40)

        snapshots = {}
        for name in self._names():
            if name != "zx-slm-tool.log":
                snapshots[name] = Path(self._path(name)).read_text(encoding="utf-8")

        for i in range(40):
            _log(handler, f"later-batch-{i}-" + "w" * 40)

        # 仍然存在的历史文件，内容与快照必须完全一致
        for name, content in snapshots.items():
            if os.path.exists(self._path(name)):
                self.assertEqual(
                    content,
                    Path(self._path(name)).read_text(encoding="utf-8"),
                    f"{name} 被改写或移动了；新方案只应新增文件",
                )

        # 并且必须存在比快照更新的编号（说明是往后延而不是原地滚动）
        existing_numbers = [
            int(n[len("zx-slm-tool-") : -len(".log")])
            for n in self._names()
            if n != "zx-slm-tool.log"
        ]
        self.assertGreater(
            max(existing_numbers),
            max(
                int(n[len("zx-slm-tool-") : -len(".log")])
                for n in snapshots
            ),
            "应产生比原有历史更大的编号",
        )

    def test_history_is_capped_at_max_backup_count(self):
        path = self._path("zx-slm-tool.log")
        handler = _make_handler(path, max_bytes=40)
        self.addCleanup(handler.close)

        for i in range(200):
            _log(handler, f"flood-{i:04d}-" + "q" * 60)

        numbered = [
            n for n in self._names() if n != "zx-slm-tool.log"
        ]
        self.assertLessEqual(
            len(numbered),
            main.CustomLogHandler.MAX_BACKUP_COUNT,
            f"历史文件数超过上限: {len(numbered)}",
        )

    def test_backup_count_is_configurable_per_handler(self):
        """构造参数可覆盖保留数量（供 Logging.log_backup_count 使用）。"""
        path = self._path("zx-slm-tool.log")
        handler = main.CustomLogHandler(
            path, mode="a", encoding="utf-8", max_bytes=40, backup_count=3
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.addCleanup(handler.close)

        for i in range(80):
            _log(handler, f"cap-{i:03d}-" + "c" * 60)

        survived = [
            n for n in os.listdir(self.tmp)
            if n.startswith("zx-slm-tool-") and n.endswith(".log")
        ]
        self.assertEqual(
            len(survived),
            3,
            f"应只保留 3 个历史文件，实际: {sorted(survived)}",
        )

    def test_backup_count_is_at_least_one(self):
        handler = main.CustomLogHandler(
            self._path("zx-slm-tool.log"),
            mode="a",
            encoding="utf-8",
            backup_count=0,
        )
        self.addCleanup(handler.close)
        self.assertEqual(handler.backup_count, 1)

    def test_warning_handler_uses_its_own_prefix(self):
        """WARNING 处理器的历史文件不能与主日志撞名/互相覆盖。"""
        main_path = self._path("zx-slm-tool.log")
        warn_path = self._path("zx-slm-tool-WARNING.log")

        main_handler = _make_handler(main_path, max_bytes=60)
        warn_handler = _make_handler(warn_path, max_bytes=60)
        self.addCleanup(main_handler.close)
        self.addCleanup(warn_handler.close)

        for i in range(20):
            _log(main_handler, f"main-{i}-" + "m" * 40)
            _log(warn_handler, f"warn-{i}-" + "n" * 40)

        names = self._names()
        main_backups = [n for n in names if n.startswith("zx-slm-tool-") and "WARNING" not in n]
        warn_backups = [n for n in names if "WARNING-" in n]

        self.assertTrue(main_backups, f"主日志应有历史文件: {names}")
        self.assertTrue(
            warn_backups,
            f"WARNING 日志应有自己的历史文件（zx-slm-tool-WARNING-NN.log）: {names}",
        )

        # 主日志的历史文件内容里不应出现 WARNING 专属前缀
        for name in main_backups:
            content = Path(self._path(name)).read_text(encoding="utf-8")
            self.assertNotIn(
                "warn-",
                content,
                f"{name} 混入了 WARNING 处理器的内容",
            )

    def test_backup_prefix_derivation(self):
        handler = _make_handler(self._path("zx-slm-tool.log"))
        self.addCleanup(handler.close)
        self.assertEqual(handler._resolve_backup_prefix(), "zx-slm-tool")

        warn = _make_handler(self._path("zx-slm-tool-WARNING.log"))
        self.addCleanup(warn.close)
        self.assertEqual(warn._resolve_backup_prefix(), "zx-slm-tool-WARNING")

    def test_next_backup_path_starts_at_one(self):
        handler = _make_handler(self._path("zx-slm-tool.log"))
        self.addCleanup(handler.close)

        self.assertTrue(handler._next_backup_path().endswith("zx-slm-tool-01.log"))

        Path(self._path("zx-slm-tool-01.log")).write_text("x", encoding="utf-8")
        self.assertTrue(handler._next_backup_path().endswith("zx-slm-tool-02.log"))

        Path(self._path("zx-slm-tool-07.log")).write_text("x", encoding="utf-8")
        self.assertTrue(
            handler._next_backup_path().endswith("zx-slm-tool-08.log"),
            "应取最大编号 +1，而不是文件个数 +1",
        )

    def test_rollover_failure_keeps_writing(self):
        """轮转失败时必须能继续写日志，不能把处理器弄坏。"""
        path = self._path("zx-slm-tool.log")
        handler = _make_handler(path, max_bytes=40)
        self.addCleanup(handler.close)

        # 让目标路径无法写入：把目录换成只读不现实，这里直接 monkeypatch
        original = handler._next_backup_path

        def boom():
            raise OSError("simulated failure")

        handler._next_backup_path = boom
        _log(handler, "before-" + "a" * 60)
        _log(handler, "after-" + "b" * 60)
        handler._next_backup_path = original

        self.assertTrue(
            os.path.exists(path), "轮转失败后主日志文件应仍然存在"
        )
        self.assertGreater(
            os.path.getsize(path), 0, "轮转失败后仍应能继续写入"
        )


if __name__ == "__main__":
    unittest.main()
