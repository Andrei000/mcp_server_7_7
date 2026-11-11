"""Тесты разбора языка 1С 7.7: символы, параметры и вызовы."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import onec77_md.bootstrap  # noqa: F401,E402
from onec77_md.code.parser import parse_module, strip_noise  # noqa: E402

REAL_MD = Path(r"D:\DSH\Projects\Rain\1Cv7.MD")

MODULE = """
Перем Счетчик, Флаг Экспорт;
// Процедура Скрытая() — это комментарий, её быть не должно
Процедура МояПроц(Первый, Второй) Экспорт
    Сообщить("Скрытая() и ТожеСкрытая()");
    Итог = Функция1(Первый);
    МояПроц2(Второй);
КонецПроцедуры

Функция Функция1(Значение)
    Возврат Значение;
КонецФункции
"""


class StripNoiseTest(unittest.TestCase):
    def test_comment_removed(self) -> None:
        cleaned = strip_noise("А = 1; // Скрытая()\nБ = 2;")
        self.assertNotIn("Скрытая", cleaned)
        self.assertIn("А = 1;", cleaned)
        self.assertEqual(cleaned.count("\n"), 1)

    def test_string_removed(self) -> None:
        cleaned = strip_noise('Сообщить("Текст с Вызов()");')
        self.assertNotIn("Вызов", cleaned)
        self.assertIn("Сообщить(", cleaned)

    def test_escaped_quotes(self) -> None:
        cleaned = strip_noise('А = "он сказал ""Вызов()""";')
        self.assertNotIn("Вызов", cleaned)


class ParseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parsed = parse_module(MODULE)

    def test_procedures(self) -> None:
        names = [p.name for p in self.parsed.procedures]
        self.assertEqual(names, ["МояПроц", "Функция1"])
        proc, func = self.parsed.procedures
        self.assertEqual(proc.kind, "procedure")
        self.assertTrue(proc.is_export)
        self.assertEqual(proc.params, ["Первый", "Второй"])
        self.assertEqual(func.kind, "function")
        self.assertFalse(func.is_export)
        self.assertGreater(proc.end_line, proc.line)

    def test_variables(self) -> None:
        names = [v.name for v in self.parsed.variables]
        self.assertEqual(names, ["Счетчик", "Флаг"])

    def test_calls_ignore_comments_and_strings(self) -> None:
        callees = {call.callee for call in self.parsed.calls}
        self.assertIn("Функция1", callees)
        self.assertIn("МояПроц2", callees)
        self.assertNotIn("Скрытая", callees)
        self.assertNotIn("ТожеСкрытая", callees)

    def test_call_caller(self) -> None:
        calls = [c for c in self.parsed.calls if c.callee == "Функция1"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].caller, "МояПроц")


class ForwardDeclTest(unittest.TestCase):
    FORWARD = """Функция Расчёт(Первый, Второй) Далее
Процедура Подготовка() Далее

Процедура Подготовка()
    Расчёт(1, 2);
КонецПроцедуры

Функция Расчёт(Первый, Второй)
    Возврат Первый + Второй;
КонецФункции
"""

    def test_forwards_parsed(self) -> None:
        parsed = parse_module(self.FORWARD)
        self.assertEqual([s.name for s in parsed.forwards], ["Расчёт", "Подготовка"])
        self.assertEqual([s.name for s in parsed.procedures], ["Подготовка", "Расчёт"])

    def test_forwards_are_not_calls(self) -> None:
        parsed = parse_module(self.FORWARD)
        call_lines = {call.callee for call in parsed.calls}
        self.assertIn("Расчёт", call_lines)
        calls_from_forward = [c for c in parsed.calls if c.line == 1]
        self.assertEqual(calls_from_forward, [])

    def test_multiline_header(self) -> None:
        text = (
            "Функция Длинная(Первый,\n"
            "                 Второй,\n"
            "                 Третий = 0) Экспорт\n"
            "    Возврат Первый;\n"
            "КонецФункции\n"
        )
        parsed = parse_module(text)
        self.assertEqual(len(parsed.procedures), 1)
        symbol = parsed.procedures[0]
        self.assertEqual(symbol.name, "Длинная")
        self.assertEqual(symbol.params, ["Первый", "Второй", "Третий"])
        self.assertTrue(symbol.is_export)
        self.assertEqual(symbol.line, 1)


@unittest.skipUnless(REAL_MD.is_file(), "нет реальной базы")
class RealSymbolsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import os
        import shutil

        from onec77_md.loader import registry

        work = ROOT / "tests" / ".work" / "symbols-cache"
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        os.environ["ONE77_CACHE_DIR"] = str(work)
        cls.config = registry.load(REAL_MD)

    def test_known_procedure(self) -> None:
        from onec77_md.code.search import find_symbols

        hits = find_symbols(self.config, "ОбработкаПроведения", 5)
        self.assertGreaterEqual(len(hits), 3)
        self.assertTrue(all(hit.kind == "procedure" for hit in hits))

    def test_calls_found(self) -> None:
        from onec77_md.code.search import find_calls

        hits = find_calls(self.config, "ПолучитьЗначение", 5)
        self.assertTrue(hits)
        self.assertTrue(all(hit.line > 0 for hit in hits))

    def test_comment_only_name_is_not_a_symbol(self) -> None:
        from onec77_md.code.search import find_symbols

        self.assertEqual(find_symbols(self.config, "КонецПроцедуры", 5), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
