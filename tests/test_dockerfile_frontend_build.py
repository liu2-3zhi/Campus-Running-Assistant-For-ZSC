"""Docker 前端构建步骤（npm ci）的健壮性契约测试。

背景:
    CI 在 `RUN cd frontend && npm ci --prefer-offline` 处以 exit 1 失败，
    但报错被截断，只剩 "npm error A complete log of this run can be found in: ..."。
    本地用同一份 package.json + package-lock.json 执行 npm ci / npm run build
    均成功（exit 0），且在“空缓存 + --prefer-offline”下同样成功，说明
    lockfile 本身没有问题，失败来自 CI 环境的网络/缓存。

    `--prefer-offline` 只在缓存命中时省流量，缓存未命中仍走网络；而 CI 的
    buildx 缓存经常缺失（日志中 "local cache import at /tmp/.buildx-cache
    skipped"），此时任何网络抖动都会中断整个镜像构建。

因此 Dockerfile 需要：放宽重试、关闭 audit/fund、显式重试整条命令，
并在失败时打印完整调试日志，避免再次出现无法定位的截断报错。
"""

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = PROJECT_ROOT / "Dockerfile"


def _dockerfile_run_commands(stage_text):
    """把 `RUN ...` 指令拼成逻辑行列表（处理反斜杠续行，忽略注释）。"""
    logical_lines = []
    buffer = ""
    for raw_line in stage_text.splitlines():
        stripped = raw_line.strip()
        if not buffer and (not stripped or stripped.startswith("#")):
            continue
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
            continue
        buffer += stripped
        logical_lines.append(buffer)
        buffer = ""
    if buffer:
        logical_lines.append(buffer)
    return [line for line in logical_lines if line.startswith("RUN ")]


class TestDockerfileFrontendBuildContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOCKERFILE.read_text(encoding="utf-8")
        # 只取前端构建阶段，避免命中后端阶段的 apt/pip 命令
        cls.frontend_stage = cls.text.split("AS frontend-builder", 1)[1].split(
            "FROM python:", 1
        )[0]
        cls.run_commands = _dockerfile_run_commands(cls.frontend_stage)
        cls.run_text = "\n".join(cls.run_commands)

    def test_install_step_no_longer_uses_prefer_offline(self):
        """注释里会提到这个参数，因此只检查实际的 RUN 指令。"""
        self.assertNotIn(
            "--prefer-offline",
            self.run_text,
            "CI 缓存缺失时 --prefer-offline 无法回退到网络，应改为在线安装 + 重试",
        )

    def test_npm_ci_disables_audit_and_fund(self):
        self.assertIn("npm ci", self.run_text)
        self.assertIn("--no-audit", self.run_text)
        self.assertIn("--no-fund", self.run_text)

    def test_fetch_retry_settings_are_configured(self):
        self.assertIn("npm_config_fetch_retries", self.frontend_stage)
        self.assertIn("npm_config_fetch_retry_mintimeout", self.frontend_stage)
        self.assertIn("npm_config_fetch_retry_maxtimeout", self.frontend_stage)
        self.assertIn("npm_config_audit=false", self.frontend_stage)
        self.assertIn("npm_config_fund=false", self.frontend_stage)

    def test_install_is_retried_with_backoff(self):
        self.assertIn("for attempt in 1 2 3", self.run_text)
        self.assertIn("sleep $((attempt * 10))", self.run_text)
        self.assertIn("rm -rf node_modules", self.run_text)

    def test_final_failure_dumps_full_npm_debug_log(self):
        """最终失败时必须打印完整调试日志，而不是只留一行被截断的提示。"""
        self.assertIn("_logs/*.log", self.run_text)
        self.assertIn("xargs -r cat", self.run_text)
        self.assertIn("exit 1", self.run_text)

    def test_dependency_completeness_is_checked_after_install(self):
        """缺少 linux 原生二进制时应立即失败并给出明确原因。"""
        self.assertIn("@tailwindcss/oxide", self.run_text)

    def test_retry_loop_control_flow_is_sound(self):
        """重试循环必须：先尝试→失败则计数→仅第 3 次失败才放弃。"""
        loop = self.run_text.split("for attempt in 1 2 3", 1)[1]

        # 成功即 break，不再重试
        self.assertRegex(loop, r"if npm ci[^;]*;\s*then")
        self.assertIn("break", loop)
        # 成功分支出现在"放弃"判定之前
        self.assertLess(loop.index("break"), loop.index('= "3"'))

    def test_retry_loop_is_posix_compatible(self):
        """node:22-slim 的 /bin/sh 是 dash，不能使用 bash 专有语法。"""
        shell_bits = self.run_text

        for bashism in ("[[", "]]", "function ", "local ", "+=(", "declare "):
            with self.subTest(bashism=bashism):
                self.assertNotIn(bashism, shell_bits)

    def test_stage_places_dependency_check_before_source_copy(self):
        """依赖校验必须在 npm ci 之后、拷贝源码之前，才能尽早失败。"""
        ci_index = self.frontend_stage.index("npm ci")
        check_index = self.frontend_stage.index("@tailwindcss/oxide")
        copy_index = self.frontend_stage.index("COPY frontend/ ./frontend/")

        self.assertLess(ci_index, check_index)
        self.assertLess(check_index, copy_index)


if __name__ == "__main__":
    unittest.main()
