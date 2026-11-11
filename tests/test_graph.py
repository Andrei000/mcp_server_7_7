"""Тесты графа вызовов: обход, глубина, одноимённые объявления, циклы, лимит."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import onec77_md.bootstrap  # noqa: F401,E402
from onec77_md.code.graph import NodeRef, build_tree, render  # noqa: E402

REAL_MD = Path(r"D:\DSH\Projects\Rain\1Cv7.MD")


class FakeProvider:
    def __init__(self, defs, edges):
        self._defs = defs
        self._edges = edges

    def definitions(self, name):
        return self._defs.get(name, [])

    def expand(self, ref, direction):
        return self._edges.get((ref.module_key, ref.line, direction), [])


A = NodeRef("A", "Документ.X", "Модуль формы", "m1", 10)
B = NodeRef("B", "Документ.X", "Модуль формы", "m1", 20)
C = NodeRef("C", "Документ.X", "Модуль формы", "m1", 30)
D = NodeRef("D", "Отчёт.Y", "Модуль отчёта", "m2", 5)
X1 = NodeRef("X", "Документ.X", "Модуль формы", "m1", 10)
X2 = NodeRef("X", "Документ.Y", "Модуль формы", "m2", 7)

SIMPLE = FakeProvider(
    defs={"A": [A], "B": [B], "C": [C], "D": [D]},
    edges={
        ("m1", 10, "down"): [(B, 1), (C, 2)],
        ("m1", 20, "down"): [(D, 1), (A, 1)],
        ("m2", 5, "down"): [],
        ("m1", 30, "down"): [],
        ("m1", 20, "up"): [(A, 1)],
    },
)

TWINS = FakeProvider(
    defs={"X": [X1, X2]},
    edges={
        ("m1", 10, "down"): [(B, 1)],
        ("m2", 7, "down"): [(D, 1)],
    },
)


class GraphTest(unittest.TestCase):
    def test_depth_one(self) -> None:
        result = build_tree("A", "down", 1, SIMPLE)
        self.assertEqual([c.name for c in result.root.children], ["B", "C"])
        self.assertTrue(all(not c.children for c in result.root.children))

    def test_depth_two_and_counts(self) -> None:
        result = build_tree("A", "down", 2, SIMPLE)
        b = result.root.children[0]
        self.assertEqual([c.name for c in b.children], ["D", "A"])
        cycle = [c for c in b.children if c.name == "A"][0]
        self.assertTrue(cycle.cycle)
        self.assertEqual(result.root.children[1].count, 2)

    def test_up_direction(self) -> None:
        result = build_tree("B", "up", 1, SIMPLE)
        self.assertEqual([c.name for c in result.root.children], ["A"])

    def test_twins_are_separate_nodes(self) -> None:
        result = build_tree("X", "down", 1, TWINS)
        self.assertEqual(result.definitions, 2)
        self.assertEqual(len(result.roots), 2, "одноимённые объявления — отдельные корни")
        self.assertEqual([c.name for c in result.roots[0].children], ["B"])
        self.assertEqual([c.name for c in result.roots[1].children], ["D"])

    def test_node_limit(self) -> None:
        wide = FakeProvider(
            defs={"N": [NodeRef("N", module_key="m", line=1)]},
            edges={("m", 1, "down"): [(NodeRef(f"N{i}", module_key="m", line=i + 10), 1) for i in range(20)]},
        )
        result = build_tree("N", "down", 3, wide, max_nodes=10)
        self.assertTrue(result.truncated)
        self.assertLessEqual(result.nodes, 10)

    def test_render(self) -> None:
        text = render(build_tree("A", "down", 1, SIMPLE))
        self.assertIn("→", text)
        self.assertIn("Документ.X", text)


@unittest.skipUnless(REAL_MD.is_file(), "нет реальной базы")
class RealGraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import os
        import shutil

        from onec77_md.loader import registry

        work = ROOT / "tests" / ".work" / "graph-cache2"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        os.environ["ONE77_CACHE_DIR"] = str(work)
        cls.config = registry.load(REAL_MD)

    def test_down(self) -> None:
        from onec77_md.code.graph import provider_for
        from onec77_md.index.store import ensure

        provider = provider_for(self.config, ensure(self.config))
        result = build_tree("ПолучитьЗначение", "down", 2, provider, 200)
        self.assertGreater(result.nodes, 1)
        self.assertIn("ПолучитьЗначение", render(result))

    def test_up(self) -> None:
        from onec77_md.code.graph import provider_for
        from onec77_md.index.store import ensure

        provider = provider_for(self.config, ensure(self.config))
        result = build_tree("ПолучитьЗначение", "up", 1, provider, 200)
        self.assertGreater(len(result.root.children), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
