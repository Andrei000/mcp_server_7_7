"""Граф вызовов: рекурсивный обход «кто вызывает» и «кого вызывает»."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .parser import parse_module
from ..model.entities import Config


@dataclass
class Edge:
    name: str
    owner: str = ""
    module_title: str = ""
    line: int = 0


@dataclass
class GraphNode:
    name: str
    owner: str = ""
    module_title: str = ""
    line: int = 0
    defined: bool = True
    cycle: bool = False
    count: int = 1
    children: list["GraphNode"] = field(default_factory=list)


@dataclass
class GraphResult:
    root: GraphNode
    direction: str
    depth: int
    nodes: int
    truncated: bool
    include_builtin: bool = False


Lookup = Callable[[str], list[Edge]]


def build_tree(
    name: str,
    direction: str,
    depth: int,
    lookup: Lookup,
    is_defined: Callable[[str], bool],
    max_nodes: int = 300,
    include_builtin: bool = False,
) -> GraphResult:
    """Строит дерево вызовов. direction: "down" — кого вызывает, "up" — кто вызывает.

    include_builtin=False отбрасывает имена, которых нет в конфигурации: платформенные
    методы вроде `Сообщить` не рефакторят, а в дереве они дают много шума.
    """
    counter = 0
    truncated = False

    def walk(current: str, level: int, seen: frozenset[str]) -> GraphNode:
        nonlocal counter, truncated
        counter += 1
        node = GraphNode(name=current, defined=is_defined(current))
        if level >= depth:
            return node
        if counter >= max_nodes:
            truncated = True
            return node
        edges = lookup(current)
        # одинаковые вызовы схлопываем: имя + число вызовов, поддерево одно
        counts: dict[str, int] = {}
        unique: list[Edge] = []
        for edge in edges:
            if edge.name in counts:
                counts[edge.name] += 1
                continue
            counts[edge.name] = 1
            unique.append(edge)
        for edge in unique:
            if not include_builtin and not is_defined(edge.name):
                continue
            if counter >= max_nodes:
                truncated = True
                break
            if edge.name in seen:
                child = GraphNode(name=edge.name, defined=is_defined(edge.name), cycle=True)
            else:
                child = walk(edge.name, level + 1, seen | {edge.name})
            child.owner, child.module_title, child.line = edge.owner, edge.module_title, edge.line
            child.count = counts.get(edge.name, 1)
            node.children.append(child)
        return node

    root_node = walk(name, 0, frozenset({name}))
    return GraphResult(
        root=root_node,
        direction=direction,
        depth=depth,
        nodes=counter,
        truncated=truncated,
        include_builtin=include_builtin,
    )


def render(result: GraphResult) -> str:
    arrow = "→" if result.direction == "down" else "←"
    title = "кого вызывает" if result.direction == "down" else "кто вызывает"
    scope = "" if result.include_builtin else ", только символы конфигурации"
    lines = [f"Граф «{result.root.name}»: {title}, глубина {result.depth}, узлов {result.nodes}{scope}"]

    def walk(node: GraphNode, level: int) -> None:
        indent = "  " * level
        if level == 0:
            marker = "" if node.defined else "  (объявление не найдено)"
            lines.append(f"{indent}{node.name}{marker}")
        else:
            where = f"{node.owner} [{node.module_title}] :{node.line}" if node.owner else ""
            suffix = ""
            if node.count > 1:
                suffix += f"  (×{node.count})"
            if node.cycle:
                suffix += "  (цикл)"
            elif not node.defined:
                suffix += "  (объявление не найдено — встроенная или внешняя)"
            lines.append(f"{indent}{arrow} {node.name}  {where}{suffix}")
        for child in node.children:
            walk(child, level + 1)

    walk(result.root, 0)
    if result.truncated:
        lines.append("… обход остановлен по лимиту узлов")
    return "\n".join(lines)


def lookup_from_index(index, direction: str) -> tuple[Lookup, Callable[[str], bool]]:
    def lookup(name: str) -> list[Edge]:
        if index is None:
            return []
        rows = index.callees_of(name, 50) if direction == "down" else index.callers_of(name, 50)
        return [Edge(name=row[0], owner=row[1], module_title=row[2], line=row[3]) for row in rows]

    return lookup, index.has_symbol if index is not None else (lambda _n: False)


def lookup_from_modules(config: Config, direction: str) -> tuple[Lookup, Callable[[str], bool]]:
    """Резервный путь без индекса: разбираем модули на месте."""
    edges: dict[str, list[Edge]] = {}
    defined: set[str] = set()
    for module in config.modules:
        parsed = parse_module(module.text)
        owner = "Глобальный модуль" if module.owner_kind == "global" else module.owner_name
        for symbol in parsed.procedures:
            defined.add(symbol.name.lower())
        for call in parsed.calls:
            key = call.caller.lower() if direction == "down" else call.callee.lower()
            other = call.callee if direction == "down" else (call.caller or "")
            if not other:
                continue
            edges.setdefault(key, []).append(
                Edge(name=other, owner=owner, module_title=module.title, line=call.line)
            )

    def lookup(name: str) -> list[Edge]:
        return edges.get(name.lower(), [])[:50]

    def is_defined(name: str) -> bool:
        return name.lower() in defined

    return lookup, is_defined
