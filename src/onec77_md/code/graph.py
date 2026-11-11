"""Граф вызовов с разрешением объявлений.

Узел графа — конкретное объявление (модуль + строка), а не просто имя. Это убирает
склейку одноимённых процедур из разных модулей: `ОбработкаПроведения` в 53 документах
остаётся 53 разными узлами.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from .parser import parse_module
from ..model.entities import Config


@dataclass(frozen=True)
class NodeRef:
    name: str
    owner: str = ""
    module_title: str = ""
    module_key: str = ""
    line: int = 0

    @property
    def identity(self) -> tuple:
        return (self.module_key, self.line) if self.line else ("", self.name.lower())


@dataclass
class GraphNode:
    name: str
    owner: str = ""
    module_title: str = ""
    module_key: str = ""
    line: int = 0
    defined: bool = True
    cycle: bool = False
    count: int = 1
    children: list["GraphNode"] = field(default_factory=list)


@dataclass
class GraphResult:
    roots: list["GraphNode"]
    direction: str
    depth: int
    nodes: int
    truncated: bool
    include_builtin: bool = False
    definitions: int = 1

    @property
    def root(self) -> GraphNode:
        return self.roots[0]


class Provider(Protocol):
    def definitions(self, name: str) -> list[NodeRef]: ...
    def expand(self, ref: NodeRef, direction: str) -> list[tuple[NodeRef, int]]: ...


class IndexProvider:
    """Провайдер поверх SQLite: вызовы уже разрешены при построении индекса."""

    def __init__(self, index):
        self.index = index

    def definitions(self, name: str) -> list[NodeRef]:
        rows = self.index.definitions(name, 50)
        return [
            NodeRef(
                name=name,
                owner=row[0],
                module_title=row[1],
                module_key=row[2],
                line=row[3],
            )
            for row in rows
        ]

    def expand(self, ref: NodeRef, direction: str) -> list[tuple[NodeRef, int]]:
        if not ref.name:  # код вне процедуры — не раскрываем, иначе шум
            return []
        if direction == "down":
            rows = self.index.calls_from(ref.module_key, ref.name, 200)
            edges = []
            for callee, owner, title, target_key, target_line, target_owner in rows:
                if target_key:
                    edges.append(
                        NodeRef(
                            name=callee,
                            owner=target_owner or owner,
                            module_title=title,
                            module_key=target_key,
                            line=target_line or 0,
                        )
                    )
                else:
                    edges.append(NodeRef(name=callee))
            return _group(edges)

        rows = self.index.calls_to(ref.module_key, ref.line, 200)
        edges = [
            NodeRef(name=caller, owner=owner, module_title=title, module_key=caller_key, line=caller_line or 0)
            for caller, owner, title, caller_key, caller_line in rows
        ]
        return _group(edges)


class ModuleProvider:
    """Резервный провайдер без индекса: без разрешения, только по именам."""

    def __init__(self, config: Config):
        self._defs: dict[str, list[NodeRef]] = {}
        self._down: dict[tuple[str, str], list[NodeRef]] = {}
        self._up: dict[tuple[str, str], list[NodeRef]] = {}
        for module in config.modules:
            parsed = parse_module(module.text)
            owner = "Глобальный модуль" if module.owner_kind == "global" else module.owner_name
            for symbol in parsed.procedures:
                self._defs.setdefault(symbol.name.lower(), []).append(
                    NodeRef(symbol.name, owner, module.title, module.key, symbol.line)
                )
            for call in parsed.calls:
                self._down.setdefault((module.key, call.caller.lower()), []).append(
                    NodeRef(call.callee)
                )
                self._up.setdefault((module.key, call.caller.lower()), [])
                if call.caller:
                    self._up.setdefault((module.key, call.caller.lower()), []).append(
                        NodeRef(call.caller, owner, module.title, module.key, call.line)
                    )

    def definitions(self, name: str) -> list[NodeRef]:
        return self._defs.get(name.lower(), [])

    def expand(self, ref: NodeRef, direction: str) -> list[tuple[NodeRef, int]]:
        if direction == "down":
            return _group(self._down.get((ref.module_key, ref.name.lower()), []))
        # вверх без разрешения: ищем всех, кто вызывает имя в том же модуле
        return _group(self._up.get((ref.module_key, ref.name.lower()), []))


def _group(edges: list[NodeRef]) -> list[tuple[NodeRef, int]]:
    counts: dict[tuple, int] = {}
    order: dict[tuple, NodeRef] = {}
    for edge in edges:
        key = edge.identity
        counts[key] = counts.get(key, 0) + 1
        order.setdefault(key, edge)
    return [(order[key], counts[key]) for key in order]


def build_tree(
    name: str,
    direction: str,
    depth: int,
    provider: Provider,
    max_nodes: int = 300,
    include_builtin: bool = False,
) -> GraphResult:
    counter = 0
    truncated = False

    def walk(ref: NodeRef, level: int, seen: frozenset[tuple]) -> GraphNode:
        nonlocal counter, truncated
        counter += 1
        node = GraphNode(
            name=ref.name,
            owner=ref.owner,
            module_title=ref.module_title,
            module_key=ref.module_key,
            line=ref.line,
            defined=ref.line > 0 or ref.name == name,
        )
        if level >= depth or counter >= max_nodes:
            truncated = truncated or counter >= max_nodes
            return node
        for child_ref, count in provider.expand(ref, direction):
            if counter >= max_nodes:
                truncated = True
                break
            if not include_builtin and not child_ref.module_key and child_ref.name.lower() != name.lower():
                continue
            identity = child_ref.identity
            if identity in seen:
                node.children.append(
                    GraphNode(
                        name=child_ref.name,
                        owner=child_ref.owner,
                        module_title=child_ref.module_title,
                        cycle=True,
                        count=count,
                    )
                )
                continue
            child = walk(child_ref, level + 1, seen | {identity})
            child.count = count
            node.children.append(child)
        return node

    root_refs = provider.definitions(name) or [NodeRef(name=name)]
    built: list[GraphNode] = []
    for ref in root_refs:
        built.append(walk(ref, 0, frozenset({ref.identity})))
    return GraphResult(
        roots=built,
        direction=direction,
        depth=depth,
        nodes=counter,
        truncated=truncated,
        include_builtin=include_builtin,
        definitions=len(root_refs),
    )


def render(result: GraphResult) -> str:
    arrow = "→" if result.direction == "down" else "←"
    title = "кого вызывает" if result.direction == "down" else "кто вызывает"
    scope = "" if result.include_builtin else ", только символы конфигурации"
    head = f"Граф «{result.root.name}»: {title}, глубина {result.depth}, узлов {result.nodes}{scope}"
    if result.definitions > 1:
        head += f", объявлений с этим именем: {result.definitions}"
    lines = [head]

    def walk(node: GraphNode, level: int) -> None:
        indent = "  " * level
        label = node.name or "вне процедуры"
        where = f"{node.owner} [{node.module_title}] :{node.line}" if node.owner and node.line else ""
        if level == 0:
            marker = "" if node.defined else "  (объявление не найдено)"
            lines.append(f"{indent}{label}{marker}" + (f"  {where}" if where else ""))
        else:
            suffix = ""
            if node.count > 1:
                suffix += f"  (×{node.count})"
            if node.cycle:
                suffix += "  (цикл)"
            elif not node.module_key:
                suffix += "  (объявление не найдено — встроенная или внешняя)"
            lines.append(f"{indent}{arrow} {label}  {where}{suffix}")
        for child in node.children:
            walk(child, level + 1)

    for index, root in enumerate(result.roots, start=1):
        if result.definitions > 1:
            lines.append(f"— объявление {index} из {result.definitions} —")
        walk(root, 0)
    if result.truncated:
        lines.append("… обход остановлен по лимиту узлов")
    return "\n".join(lines)


def provider_for(config: Config, index) -> Provider:
    return IndexProvider(index) if index is not None else ModuleProvider(config)


Lookup = Callable[[str], list]
