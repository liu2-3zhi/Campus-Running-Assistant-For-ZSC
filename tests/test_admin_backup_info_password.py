"""管理员欠费详情必须使用当前学校账号配置中的密码。"""

from pathlib import Path
import unittest


class TestAdminBackupInfoPassword(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            Path(__file__).resolve().parents[1] / "web_server.py"
        ).read_text(encoding="utf-8")
        cls.block = cls.source.split(
            "def api_admin_view_backup_info(", 1
        )[1].split("@app.route", 1)[0]

    def test_backup_info_merges_current_account_password(self):
        self.assertIn(
            "_load_user_school_accounts",
            self.block,
            "备份详情必须读取当前 school_accounts 配置",
        )
        self.assertIn(
            'text_password',
            self.block,
            "备份详情必须回填前端使用的 text_password 字段",
        )


if __name__ == "__main__":
    unittest.main()
