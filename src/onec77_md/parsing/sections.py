"""Разбор MD-дерева 1С 7.7: `{a,b,{c,d}}` -> вложенные списки.

Формат недокументирован, поэтому парсер терпимый: мусор до/после дерева
игнорируется, строки в кавычках экранируются удвоением (`""`).
"""
from __future__ import annotations

from typing import Union

Node = Union[str, list]


def parse_sections(text: str) -> list[Node]:
    """Возвращает список верхнеуровневых узлов дерева MD."""
    root: list[Node] = []
    stack: list[list[Node]] = [root]
    buf: list[str] = []
    in_str = False
    i, n = 0, len(text)

    def flush() -> None:
        token = "".join(buf).strip()
        buf.clear()
        if token:
            stack[-1].append(token)

    while i < n:
        ch = text[i]
        if in_str:
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    buf.append('"')
                    i += 2
                    continue
                in_str = False
                stack[-1].append("".join(buf))
                buf.clear()
            else:
                buf.append(ch)
            i += 1
            continue

        if ch == '"':
            in_str = True
            buf.clear()
        elif ch == '{':
            flush()
            node: list[Node] = []
            stack[-1].append(node)
            stack.append(node)
        elif ch == '}':
            flush()
            if len(stack) > 1:
                stack.pop()
        elif ch == ',':
            flush()
        else:
            buf.append(ch)
        i += 1
    flush()
    return root


def section(node: list[Node], name: str) -> list[Node] | None:
    """Находит вложенную секцию по первому элементу."""
    for child in node:
        if isinstance(child, list) and child and child[0] == name:
            return child
    return None


def sections(node: list[Node], name: str) -> list[Node]:
    """Все вложенные секции с указанным именем."""
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def text(node: list[Node], index: int, default: str = "") -> str:
    if index < len(node):
        value = node[index]
        if isinstance(value, str):
            return value
    return default
