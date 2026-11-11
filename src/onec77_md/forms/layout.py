"""Разбор бинарной части формы: контейнер и `Dialog Stream`.

`Container.Contents` — это текстовый манифест со списком потоков формы,
а `Dialog Stream` — такое же дерево `{...}`, как MD, с описанием элементов.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..parsing.sections import Node, parse_sections


@dataclass
class Control:
    """Элемент формы: кнопка, поле ввода, таблица, группа."""

    position: int
    name: str
    cls: str
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    control_id: str = ""
    action: str = ""
    attribute: str = ""
    type_code: str = ""

    def describe(self) -> str:
        parts = [f"{self.cls}"]
        title = self.name or self.attribute
        if title:
            parts.append(f"«{title}»")
        parts.append(f"{self.x},{self.y} {self.width}×{self.height}")
        if self.attribute and self.attribute != title:
            parts.append(f"→ {self.attribute}")
        if self.action:
            parts.append(f"обработчик: {self.action}")
        return " ".join(parts)


@dataclass
class FormLayout:
    controls: list[Control] = field(default_factory=list)
    entries: list[tuple[str, str, str]] = field(default_factory=list)
    error: str = ""


def _to_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def decode_text(blob: bytes) -> str:
    """Поток формы начинается с короткого бинарного префикса, дальше — текст."""
    start = blob.find(b"{")
    if start < 0:
        return ""
    body = blob[start:]
    for encoding in ("cp1251", "cp866", "utf-8"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("cp1251", errors="replace")


def parse_container(blob: bytes) -> list[tuple[str, str, str]]:
    """Возвращает (тип, поток, имя) из манифеста контейнера."""
    text = decode_text(blob)
    if not text:
        return []
    root = parse_sections(text)
    node = next((n for n in root if isinstance(n, list)), None)
    if not node:
        return []
    result = []
    for child in node[1:]:
        if isinstance(child, list) and len(child) >= 2:
            result.append((str(child[0]), str(child[1]), str(child[2]) if len(child) > 2 else ""))
    return result


def _is_control(node: Node) -> bool:
    # обычный элемент формы — 43 поля; служебная запись IDD короче и классом IDD
    return (
        isinstance(node, list)
        and len(node) >= 40
        and isinstance(node[1], str)
        and node[1].isupper()
        and node[1] != "IDD"
    )


def walk_controls(node: Node, out: list[list[Node]]) -> None:
    if isinstance(node, list):
        if _is_control(node):
            out.append(node)
        for child in node:
            walk_controls(child, out)


def parse_dialog(blob: bytes) -> FormLayout:
    text = decode_text(blob)
    if not text:
        return FormLayout(error="поток не содержит текста формы")
    root = parse_sections(text)
    node = next((n for n in root if isinstance(n, list)), None)
    if not node:
        return FormLayout(error="не удалось разобрать дерево формы")

    raw: list[list[Node]] = []
    walk_controls(node, raw)

    controls: list[Control] = []
    for position, item in enumerate(raw):
        values = [str(v) for v in item]
        cls = values[1]
        # одиннадцатая колонка: у кнопок и флажков — обработчик, у полей и таблиц — реквизит
        eleventh = (values[11] if len(values) > 11 else "").strip()
        is_action = "(" in eleventh or eleventh.startswith("#")
        controls.append(
            Control(
                position=position,
                name=values[0],
                cls=cls,
                x=_to_int(values[3]),
                y=_to_int(values[4]),
                width=_to_int(values[5]),
                height=_to_int(values[6]),
                control_id=values[9] if len(values) > 9 else "",
                action=eleventh if is_action else "",
                attribute="" if is_action else eleventh,
                type_code=values[14] if len(values) > 14 else "",
            )
        )
    return FormLayout(controls=controls)
