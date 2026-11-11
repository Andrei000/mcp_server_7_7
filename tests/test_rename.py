"""Тесты «предложи патч»: замена только в коде, diff и файлы."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import onec77_md.bootstrap  # noqa: F401,E402
from onec77_md.code.rename import (  # noqa: E402
    propose_rename,
    propose_replace,
    replace_in_code,
    write_patch,
)
from onec77_md.model.entities import Config, Module  # noqa: E402

REAL_MD = Path(r"D:\DSH\Projects\Rain\1Cv7.MD")
WORK = ROOT / "tests" / ".work"

TEXT = """Перем Сумма;
// Сумма в комментарии не трогаем
Процедура Посчитать()
    Сообщить("Сумма в строке");
    Сумма = Сумма + 1;
    СуммаДокумента = 5;
КонецПроцедуры
"""


class ReplaceInCodeTest(unittest.TestCase):
    def test_comment_and_string_untouched(self) -> None:
        after, count = replace_in_code(TEXT, "Сумма", "Итог")
        self.assertEqual(count, 3)  # Перем, присваивание, правая часть
        self.assertIn("// Сумма в комментарии не трогаем", after)
        self.assertIn('Сообщить("Сумма в строке")', after)
        self.assertIn("Итог = Итог + 1;", after)

    def test_whole_word(self) -> None:
        after, count = replace_in_code(TEXT, "Сумма", "Итог", whole_word=True)
        self.assertEqual(count, 3)
        self.assertIn("СуммаДокумента = 5;", after)

    def test_case_insensitive(self) -> None:
        after, count = replace_in_code("сумма = 1;", "Сумма", "Итог")
        self.assertEqual(count, 1)
        self.assertEqual(after, "Итог = 1;")

    def test_no_match(self) -> None:
        after, count = replace_in_code(TEXT, "НетТакого", "Икс")
        self.assertEqual(count, 0)
        self.assertEqual(after, TEXT)


class ProposeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config(name="Тест", synonym="", source_path="memory", size=0, encoding="utf-8")
        self.config.modules = [
            Module(
                key="document:1",
                owner_kind="document",
                owner_id="1",
                owner_name="Документ1",
                title="Модуль проведения",
                text=TEXT,
            )
        ]
        self.dir = WORK / "patch-test"
        shutil.rmtree(self.dir, ignore_errors=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_rename_changes(self) -> None:
        changes = propose_rename(self.config, "Сумма", "Итог")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].count, 3)
        diff = changes[0].diff
        self.assertIn("-Перем Сумма;", diff)
        self.assertIn("+Перем Итог;", diff)
        self.assertIn("--- a/", diff)
        self.assertIn("+++ b/", diff)

    def test_replace_literal(self) -> None:
        changes = propose_replace(self.config, "СуммаДокумента", "СуммаДок")
        self.assertEqual(len(changes), 1)
        self.assertIn("СуммаДок = 5;", changes[0].after)

    def test_write_patch(self) -> None:
        changes = propose_rename(self.config, "Сумма", "Итог")
        path = write_patch(changes, self.dir)
        self.assertTrue(path.exists())
        self.assertIn("+Перем Итог;", path.read_text(encoding="utf-8"))
        self.assertTrue((self.dir / "after").is_dir())


@unittest.skipUnless(REAL_MD.is_file(), "нет реальной базы")
class RealRenameTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import os

        from onec77_md.loader import registry

        work = WORK / "rename-cache"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        os.environ["ONE77_CACHE_DIR"] = str(work)
        cls.config = registry.load(REAL_MD)

    def test_rename_existing_symbol(self) -> None:
        changes = propose_rename(self.config, "ПоискКонтрагента", "НайтиКонтрагента")
        self.assertTrue(changes)
        self.assertGreaterEqual(changes[0].count, 1)
        self.assertIn("НайтиКонтрагента", changes[0].after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
