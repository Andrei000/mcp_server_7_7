"""Тесты графа вызовов: обход, глубина, циклы, лимит узлов."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import onec77_md.bootstrap  # noqa: F401,E402
from onec77_md.code.graph import Edge, build_tree, render  # noqa: E402

REAL_MD = Path(r"D:\DSH\Projects\Rain\1Cv7.MD")

GRAPH = {
    "A": [Edge("B", "Документ.X", "Модуль формы", 10), Edge("C", "Документ.X", "Модуль формы", 20)],
    "B": [Edge("D", "Документ.X", "Модуль формы", 30), Edge("A", "Документ.X", "Модуль формы", 40)],
    "C": [Edge("D", "Документ.X", "Модуль формы", 50)],
    "D": [],
}


def lookup(name: str) -> list[Edge]:
    return GRAPH.get(name, [])


def is_defined(name: str) -> bool:
    return name in GRAPH


class GraphTest(unittest.TestCase):
    def test_depth_one(self) -> None:
        result = build_tree("A", "down", 1, lookup, is_defined)
        self.assertEqual(result.root.name, "A")
        self.assertEqual([child.name for child in result.root.children], ["B", "C"])
        self.assertTrue(all(not child.children for child in result.root.children))

    def test_depth_two(self) -> None:
        result = build_tree("A", "down", 2, lookup, is_defined)
        b = result.root.children[0]
        self.assertEqual([child.name for child in b.children], ["D", "A"])
        cycle = [child for child in b.children if child.name == "A"][0]
        self.assertTrue(cycle.cycle)

    def test_unknown_symbol_marked(self) -> None:
        result = build_tree("Z", "down", 2, lookup, is_defined)
        self.assertFalse(result.root.defined)

    def test_node_limit(self) -> None:
        wide = lambda name: [Edge(f"{name}_{i}") for i in range(20)]  # noqa: E731
        result = build_tree("N", "down", 3, wide, lambda n: True, max_nodes=10)
        self.assertTrue(result.truncated)
        self.assertLessEqual(result.nodes, 10)

    def test_render_contains_arrow(self) -> None:
        text = render(build_tree("A", "down", 1, lookup, is_defined))
        self.assertIn("→", text)
        self.assertIn("Документ.X", text)

    def test_builtin_filtered_by_default(self) -> None:
        graph = {"A": [Edge("B"), Edge("Сообщить")], "B": []}
        filtered = build_tree("A", "down", 1, lambda n: graph.get(n, []), lambda n: n in graph)
        self.assertEqual([c.name for c in filtered.root.children], ["B"])

        full = build_tree(
            "A", "down", 1, lambda n: graph.get(n, []), lambda n: n in graph, include_builtin=True
        )
        self.assertEqual([c.name for c in full.root.children], ["B", "Сообщить"])

    def test_up_direction_label(self) -> None:
        text = render(build_tree("A", "up", 1, lambda n: [], is_defined))
        self.assertIn("кто вызывает", text)


@unittest.skipUnless(REAL_MD.is_file(), "нет реальной базы")
class RealGraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import os
        import shutil

        from onec77_md.loader import registry

        work = ROOT / "tests" / ".work" / "graph-cache"
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        os.environ["ONE77_CACHE_DIR"] = str(work)
        cls.config = registry.load(REAL_MD)

    def test_down_graph(self) -> None:
        from onec77_md.code.graph import lookup_from_index
        from onec77_md.index.store import ensure

        index = ensure(self.config)
        self.assertIsNotNone(index)
        lookup, defined = lookup_from_index(index, "down")
        result = build_tree("ПолучитьЗначение", "down", 2, lookup, defined, 200)
        self.assertGreater(result.nodes, 1)
        self.assertTrue(render(result).startswith("Граф"))

    def test_up_graph(self) -> None:
        from onec77_md.code.graph import lookup_from_index
        from onec77_md.index.store import ensure

        index = ensure(self.config)
        lookup, defined = lookup_from_index(index, "up")
        result = build_tree("ПолучитьЗначение", "up", 1, lookup, defined, 200)
        self.assertGreater(len(result.root.children), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
