"""Тесты разбора разметки форм (Container.Contents и Dialog Stream)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import onec77_md.bootstrap  # noqa: F401,E402
from onec77_md.forms.layout import parse_container, parse_dialog  # noqa: E402
from onec77_md.forms.store import FormLayoutStore  # noqa: E402

REAL_MD = Path(r"D:\DSH\Projects\Rain\1Cv7.MD")

MANIFEST = (
    b'{"Container.Contents",{"DialogEditor","Dialog Stream","Dialog Form",""},'
    b'{"TextDocument","MD Programm text","Module text",""}}\n'
)


def _control(name: str, cls: str, x: int, action: str, attr: str) -> str:
    fields = [name, cls, "0", str(x), "10", "50", "14", "0", "0", "4153", "", action or attr, "", "-1", "U"]
    fields += [""] * (43 - len(fields))
    return "{" + ",".join(f'"{value}"' for value in fields) + "}"


DIALOG = (
    '{"Dialogs",{"Frame","0","400"},{"Controls",'
    + _control("Выполнить", "BUTTON", 10, "Выполнить()", "")
    + ","
    + _control("", "1CEDIT", 20, "", "Количество")
    + ","
    + _control("Итого", "STATIC", 30, "", "")
    + '},{"Cnt_Ver","10001"}}'
)


class ContainerTest(unittest.TestCase):
    def test_manifest_entries(self) -> None:
        entries = parse_container(MANIFEST)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0], ("DialogEditor", "Dialog Stream", "Dialog Form"))
        self.assertEqual(entries[1][1], "MD Programm text")

    def test_manifest_with_binary_prefix(self) -> None:
        entries = parse_container(b"\xff\x74\x0f" + MANIFEST)
        self.assertEqual(len(entries), 2)


class DialogTest(unittest.TestCase):
    def test_controls(self) -> None:
        layout = parse_dialog(DIALOG.encode("cp1251"))
        self.assertEqual(len(layout.controls), 3)
        button, edit, static = layout.controls
        self.assertEqual(button.cls, "BUTTON")
        self.assertEqual(button.action, "Выполнить()")
        self.assertEqual(edit.attribute, "Количество")
        self.assertEqual(edit.x, 20)
        self.assertEqual(static.name, "Итого")

    def test_empty_stream(self) -> None:
        layout = parse_dialog(b"")
        self.assertEqual(layout.controls, [])
        self.assertTrue(layout.error)


@unittest.skipUnless(REAL_MD.is_file(), "нет реальной базы")
class RealFormTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.store = FormLayoutStore(REAL_MD)
        from onec77_md.loader import registry

        cls.config = registry.load(REAL_MD)

    def test_catalog_form_layout(self) -> None:
        catalog = next(o for o in self.config.of_kind("catalog") if o.name == "Контрагенты")
        form = catalog.forms[0]
        layout = self.store.layout(form.id)
        self.assertIsNotNone(layout)
        self.assertGreaterEqual(len(layout.controls), 5)
        classes = {c.cls for c in layout.controls}
        self.assertIn("BUTTON", classes)

    def test_container_entries(self) -> None:
        catalog = next(o for o in self.config.of_kind("catalog") if o.name == "Контрагенты")
        entries = self.store.entries(catalog.forms[0].id)
        self.assertTrue(entries)
        self.assertTrue(any(e[1] == "Dialog Stream" for e in entries))


if __name__ == "__main__":
    unittest.main(verbosity=2)
