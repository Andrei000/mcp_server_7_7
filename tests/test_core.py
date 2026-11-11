"""Тесты парсера MD-дерева и модели на реальной базе (если она доступна)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import onec77_md.bootstrap  # noqa: F401,E402
from onec77_md.model.entities import resolve_kind  # noqa: E402
from onec77_md.parsing.sections import parse_sections, section  # noqa: E402
from onec77_md.sources.ole import OleMdSource  # noqa: E402

REAL_MD = Path(r"D:\DSH\Projects\Rain\1Cv7.MD")


class SectionsTest(unittest.TestCase):
    def test_simple(self) -> None:
        root = parse_sections("{a,b,{c,d}}")
        self.assertEqual(root, [["a", "b", ["c", "d"]]])

    def test_quoted_with_comma(self) -> None:
        root = parse_sections('{1,"Имя, с запятой",3}')
        self.assertEqual(root, [["1", "Имя, с запятой", "3"]])

    def test_escaped_quotes(self) -> None:
        root = parse_sections('{"Он сказал ""да""",2}')
        self.assertEqual(root, [['Он сказал "да"', "2"]])

    def test_garbage_around(self) -> None:
        root = parse_sections('мусор{1,2}ещё мусор')
        node = next(n for n in root if isinstance(n, list))
        self.assertEqual(node, ["1", "2"])

    def test_nested_section(self) -> None:
        node = parse_sections("{SbCnts,{723,Имя}}")[0]
        self.assertEqual(node[0], "SbCnts")
        self.assertEqual(node[1], ["723", "Имя"])


class KindTest(unittest.TestCase):
    def test_aliases(self) -> None:
        self.assertEqual(resolve_kind("Справочник"), "catalog")
        self.assertEqual(resolve_kind("документ"), "document")
        self.assertEqual(resolve_kind("catalog"), "catalog")
        self.assertIsNone(resolve_kind("нет-такого"))


@unittest.skipUnless(REAL_MD.is_file(), "нет реальной базы для проверки")
class RealBaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from onec77_md.model.mapping import build_config

        cls.config = build_config(OleMdSource(REAL_MD).read())

    def test_counts(self) -> None:
        counts = self.config.counts()
        self.assertGreater(counts.get("catalog", 0), 50)
        self.assertGreater(counts.get("document", 0), 30)
        self.assertGreater(counts.get("enum", 0), 10)

    def test_catalog_fields(self) -> None:
        catalog = next(o for o in self.config.of_kind("catalog") if o.name == "Номенклатура")
        self.assertGreater(len(catalog.fields), 50)

    def test_document_tabular(self) -> None:
        doc = next(o for o in self.config.of_kind("document") if o.name == "АктНесоответствия")
        self.assertGreater(len(doc.tabular), 5)

    def test_refs_resolved(self) -> None:
        doc = next(o for o in self.config.of_kind("document") if o.name == "АктНесоответствия")
        refs = [f for f in doc.fields + doc.tabular if f.ref_name]
        self.assertTrue(refs, "ссылочные типы должны разрешаться в имена")

    def test_enum_values(self) -> None:
        enum = next(o for o in self.config.of_kind("enum") if o.name == "Булево")
        self.assertEqual([v.name for v in enum.enum_values], ["Да", "Нет"])

    def test_modules_loaded(self) -> None:
        self.assertGreater(len(self.config.modules), 400)
        self.assertGreater(sum(m.lines for m in self.config.modules), 100_000)

    def test_global_module(self) -> None:
        global_modules = [m for m in self.config.modules if m.owner_kind == "global"]
        self.assertEqual(len(global_modules), 1)
        self.assertGreater(global_modules[0].lines, 1000)

    def test_document_has_transaction_module(self) -> None:
        doc = next(o for o in self.config.of_kind("document") if o.name == "АктНесоответствия")
        titles = [m.title for m in self.config.modules_of(doc)]
        self.assertIn("Модуль проведения", titles)
        self.assertIn("Модуль формы документа", titles)

    def test_module_search(self) -> None:
        from onec77_md.formatting import module_search

        result = module_search(self.config, "Процедура", False, 5)
        self.assertTrue(result.startswith("Совпадений"))

    def test_forms_and_form_modules(self) -> None:
        from onec77_md.formatting import forms_card

        catalog = next(o for o in self.config.of_kind("catalog") if o.name == "Контрагенты")
        self.assertGreaterEqual(len(catalog.forms), 1)
        card = forms_card(catalog, self.config.modules_of(catalog))
        self.assertIn("ФормаСписка", card)
        self.assertIn("модуль", card)

    def test_audit_runs(self) -> None:
        from onec77_md.audit.rules import run_audit

        report = run_audit(self.config, "", 5)
        self.assertIn("Аудит конфигурации", report)
        self.assertIn("Битые ссылки", report)

    def test_exports(self) -> None:
        import json

        from onec77_md.export.markdown import to_markdown
        from onec77_md.export.mermaid import to_mermaid
        from onec77_md.export.sql_ddl import to_sql
        from onec77_md.export.writer import to_json

        payload = json.loads(to_json(self.config))
        self.assertEqual(len(payload["objects"]), len(self.config.objects))
        self.assertGreater(len(to_markdown(self.config)), 10_000)
        self.assertTrue(to_mermaid(self.config).startswith("%%"))
        self.assertIn("CREATE TABLE SC", to_sql(self.config))


if __name__ == "__main__":
    unittest.main(verbosity=2)
