"""Тесты источников: текстовая выгрузка и автоопределение."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import onec77_md.bootstrap  # noqa: F401,E402
from onec77_md.model.mapping import build_config  # noqa: E402
from onec77_md.sources.detect import open_source  # noqa: E402
from onec77_md.sources.text import TextMdSource  # noqa: E402

REAL_MD = Path(r"D:\DSH\Projects\Rain\1Cv7.MD")
WORK = ROOT / "tests" / ".work"

TASK_ITEM = '{"TaskItem",{"1","Тест","","Тестовая","","1","0","1","0","0"}}'
CATALOGS = (
    '{"SbCnts",{"723","_ЗоныСклада","","_Зоны на складе","0","5",'
    '{"Params",{"724","Зона","","","B","0","0","723","0","0"}},'
    '{"Form",{"722","ФормаСписка","",""}}}}'
)
DOCUMENTS = (
    '{"Documents",{"1638","АгентскийБонус","","Агентские проценты","5",'
    '{"Head Fields",{"1624","Сумма","","","N","15","2","0","0"}},'
    '{"Table Fields"}}}'
)


class TextDumpTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = WORK / self._testMethodName
        if self.dir.exists():
            shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, name: str, text: str, encoding: str = "utf-8") -> None:
        (self.dir / name).write_bytes(text.encode(encoding))

    def test_directory_of_md_files(self) -> None:
        self._write("TaskItem.md", TASK_ITEM)
        self._write("SbCnts.md", CATALOGS)
        self._write("Documents.md", DOCUMENTS, encoding="cp1251")

        raw = TextMdSource(self.dir).read()
        config = build_config(raw)

        self.assertEqual(config.source_kind, "text")
        self.assertEqual(config.name, "Тест")
        self.assertEqual(len(config.of_kind("catalog")), 1)
        self.assertEqual(len(config.of_kind("document")), 1)

        catalog = config.of_kind("catalog")[0]
        self.assertEqual(catalog.name, "_ЗоныСклада")
        self.assertEqual(catalog.synonym, "_Зоны на складе")
        self.assertEqual(catalog.fields[0].ref_name, "_ЗоныСклада")

    def test_single_text_file(self) -> None:
        path = self.dir / "config.md"
        path.write_text(TASK_ITEM + CATALOGS + DOCUMENTS, encoding="utf-8")

        config = build_config(TextMdSource(path).read())

        self.assertEqual(config.source_kind, "text")
        self.assertEqual(len(config.objects), 2)

    def test_detect_text_source(self) -> None:
        self._write("SbCnts.md", CATALOGS)
        source = open_source(self.dir)
        self.assertIsInstance(source, TextMdSource)

    @unittest.skipUnless(REAL_MD.is_file(), "нет реальной базы")
    def test_detect_ole_source(self) -> None:
        from onec77_md.sources.ole import OleMdSource

        self.assertIsInstance(open_source(REAL_MD), OleMdSource)
        self.assertIsInstance(open_source(REAL_MD.parent), OleMdSource)


if __name__ == "__main__":
    unittest.main(verbosity=2)
