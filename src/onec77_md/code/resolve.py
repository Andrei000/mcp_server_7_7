"""Разрешение вызовов: какое именно объявление имеется в виду.

Правила для 1С 7.7, по убыванию приоритета:

1. `local` — процедура с таким именем объявлена в том же модуле;
2. `global` — процедура объявлена в глобальном модуле;
3. `unique` — во всей конфигурации есть ровно одно объявление с таким именем;
4. `ambiguous` — объявлений несколько и они в чужих модулях: не угадываем.

Правило 1 покрывает основную массу вызовов: одноимённые `ОбработкаПроведения`
в 53 документах вызываются платформой и друг друга не видят.
"""
from __future__ import annotations

from dataclasses import dataclass

from .parser import ParsedModule, parse_module


@dataclass
class Definition:
    name: str
    kind: str
    owner: str
    module_title: str
    module_key: str
    line: int
    is_export: bool


@dataclass
class Resolution:
    definition: Definition | None
    rule: str  # local | global | unique | ambiguous | none


def owner_of(module) -> str:
    return "Глобальный модуль" if module.owner_kind == "global" else module.owner_name


class Resolver:
    """Индекс объявлений и правило разрешения вызовов."""

    def __init__(self, definitions: dict[str, list[Definition]], by_module: dict[str, dict[str, Definition]]):
        self._all = definitions
        self._by_module = by_module
        self._global: dict[str, Definition] = {}
        for items in definitions.values():
            for item in items:
                if item.module_title == "Глобальный модуль":
                    self._global.setdefault(item.name.lower(), item)

    def resolve(self, module_key: str, callee: str) -> Resolution:
        key = callee.lower()
        local = self._by_module.get(module_key, {}).get(key)
        if local is not None:
            return Resolution(local, "local")
        glob = self._global.get(key)
        if glob is not None:
            return Resolution(glob, "global")
        candidates = self._all.get(key, [])
        if len(candidates) == 1:
            return Resolution(candidates[0], "unique")
        if candidates:
            return Resolution(None, "ambiguous")
        return Resolution(None, "none")

    def definitions(self, name: str) -> list[Definition]:
        return self._all.get(name.lower(), [])


def build_resolver(modules) -> tuple[Resolver, dict[str, ParsedModule]]:
    """Разбирает модули один раз и строит индекс объявлений."""
    parsed: dict[str, ParsedModule] = {}
    all_defs: dict[str, list[Definition]] = {}
    by_module: dict[str, dict[str, Definition]] = {}

    for module in modules:
        result = parse_module(module.text)
        parsed[module.key] = result
        local: dict[str, Definition] = {}
        for symbol in result.procedures:
            definition = Definition(
                name=symbol.name,
                kind=symbol.kind,
                owner=owner_of(module),
                module_title=module.title,
                module_key=module.key,
                line=symbol.line,
                is_export=symbol.is_export,
            )
            all_defs.setdefault(symbol.name.lower(), []).append(definition)
            local.setdefault(symbol.name.lower(), definition)
        by_module[module.key] = local

    return Resolver(all_defs, by_module), parsed
