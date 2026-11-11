"""Тесты разрешения вызовов: локальные, глобальные, единственные и неоднозначные."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import onec77_md.bootstrap  # noqa: F401,E402
from onec77_md.code.resolve import build_resolver  # noqa: E402
from onec77_md.model.entities import Module  # noqa: E402

TEXT_1 = """Процедура Локальная()
    Локальная();
    Общая();
    Глобальная();
    Дубликат();
КонецПроцедуры
"""

TEXT_2 = """Процедура Общая()
    Общая();
КонецПроцедуры
Процедура Дубликат()
КонецПроцедуры
"""

TEXT_3 = """Процедура Дубликат()
КонецПроцедуры
"""

TEXT_GLOBAL = """Процедура Глобальная()
КонецПроцедуры
"""


def module(key: str, title: str, text: str, owner_kind: str = "document", owner_name: str = "Док") -> Module:
    return Module(
        key=key,
        owner_kind=owner_kind,
        owner_id="1",
        owner_name=owner_name,
        title=title,
        text=text,
    )


class ResolveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = [
            module("m1", "Модуль формы", TEXT_1),
            module("m2", "Модуль проведения", TEXT_2),
            module("m3", "Модуль отчёта", TEXT_3),
            module("g", "Глобальный модуль", TEXT_GLOBAL, "global", "Глобальный модуль"),
        ]
        cls.resolver, _ = build_resolver(modules)

    def test_local(self) -> None:
        result = self.resolver.resolve("m1", "Локальная")
        self.assertEqual(result.rule, "local")
        self.assertEqual(result.definition.module_key, "m1")

    def test_global(self) -> None:
        result = self.resolver.resolve("m1", "Глобальная")
        self.assertEqual(result.rule, "global")
        self.assertEqual(result.definition.module_key, "g")

    def test_unique(self) -> None:
        result = self.resolver.resolve("m1", "Общая")
        self.assertEqual(result.rule, "unique")
        self.assertEqual(result.definition.module_key, "m2")

    def test_ambiguous(self) -> None:
        result = self.resolver.resolve("m1", "Дубликат")
        self.assertEqual(result.rule, "ambiguous")
        self.assertIsNone(result.definition)

    def test_unknown(self) -> None:
        result = self.resolver.resolve("m1", "Сообщить")
        self.assertEqual(result.rule, "none")


if __name__ == "__main__":
    unittest.main(verbosity=2)
