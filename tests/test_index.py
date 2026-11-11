"""Тесты SQLite-индекса поиска по модулям."""
from __future__ import annotations

import os
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import onec77_md.bootstrap  # noqa: F401,E402
from onec77_md.index.store import ensure  # noqa: E402

REAL_MD = Path(r"D:\DSH\Projects\Rain\1Cv7.MD")
WORK = ROOT / "tests" / ".work"


@unittest.skipUnless(REAL_MD.is_file(), "нет реальной базы")
class IndexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from onec77_md.loader import registry

        cls.tmp = WORK / "index-cache"
        if cls.tmp.exists():
            shutil.rmtree(cls.tmp, ignore_errors=True)
        cls.tmp.mkdir(parents=True)
        os.environ["ONE77_CACHE_DIR"] = str(cls.tmp)
        cls.config = registry.load(REAL_MD)

    @classmethod
    def tearDownClass(cls) -> None:
        os.environ.pop("ONE77_CACHE_DIR", None)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_build_and_search(self) -> None:
        index = ensure(self.config, rebuild=True)
        self.assertIsNotNone(index)
        self.assertGreater(index.count_lines(), 100_000)

        total = index.count_hits("ОбработкаПроведения")
        self.assertGreater(total, 10)

        rows = index.search_lines("ОбработкаПроведения", 3)
        self.assertEqual(len(rows), 3)
        owner, title, number, text = rows[0]
        self.assertTrue(owner)
        self.assertGreaterEqual(number, 1)
        self.assertIn("ОбработкаПроведения", text)

    def test_missing_query(self) -> None:
        index = ensure(self.config)
        self.assertEqual(index.count_hits("Такого_текста_точно_нет_42"), 0)

    def test_search_from_another_thread(self) -> None:
        """MCP обрабатывает вызовы в разных потоках — индекс не должен падать."""
        from concurrent.futures import ThreadPoolExecutor

        ensure(self.config)

        def worker(query: str) -> int:
            return ensure(self.config).count_hits(query)

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(worker, ["ОбработкаПроведения", "Процедура", "КонецПроцедуры"]))
        self.assertTrue(all(value > 0 for value in results), results)


if __name__ == "__main__":
    unittest.main(verbosity=2)
