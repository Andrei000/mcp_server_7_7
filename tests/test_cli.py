"""Проверки CLI и упаковки: работают без установки пакета."""
from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import onec77_md  # noqa: E402
import onec77_md.bootstrap  # noqa: F401,E402
from onec77_md import cli  # noqa: E402

REAL_MD = Path(r"D:\DSH\Projects\Rain\1Cv7.MD")


class VersionTest(unittest.TestCase):
    def test_version_matches_pyproject(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = { attr = "onec77_md.__version__" }', text)
        self.assertRegex(onec77_md.__version__, r"^\d+\.\d+\.\d+$")


class CliTest(unittest.TestCase):
    def test_help_exits_cleanly(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            cli.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_unknown_command_fails(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            cli.main(["нет-такой-команды"])
        self.assertEqual(ctx.exception.code, 2)

    @unittest.skipUnless(REAL_MD.is_file(), "нет реальной базы")
    def test_info_output(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(["info", "--path", str(REAL_MD)])
        self.assertEqual(code, 0)
        self.assertIn("Конфигурация", buf.getvalue())

    @unittest.skipUnless(REAL_MD.is_file(), "нет реальной базы")
    def test_audit_rule_filter(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(["audit", "--path", str(REAL_MD), "--rule", "duplicate_synonyms"])
        self.assertEqual(code, 0)
        self.assertIn("Одинаковые синонимы", buf.getvalue())
        self.assertNotIn("Битые ссылки", buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
