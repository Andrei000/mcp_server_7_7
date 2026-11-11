"""Поиск по символам: объявления и настоящие вызовы (без комментариев и литералов)."""
from __future__ import annotations

from dataclasses import dataclass

from ..index.store import ensure
from ..model.entities import Config
from .parser import parse_module


@dataclass
class SymbolHit:
    name: str
    kind: str
    owner: str
    module_title: str
    line: int
    end_line: int
    params: str
    is_export: bool


@dataclass
class CallHit:
    caller: str
    owner: str
    module_title: str
    line: int
    target_owner: str = ""
    rule: str = ""


def find_symbols(config: Config, name: str, limit: int = 20) -> list[SymbolHit]:
    index = ensure(config)
    if index is not None:
        rows = index.find_symbols(name, limit)
        return [
            SymbolHit(
                name=name,
                kind=row[0],
                owner=row[1],
                module_title=row[2],
                line=row[3],
                end_line=row[4],
                params=row[5],
                is_export=bool(row[6]),
            )
            for row in rows
        ]

    needle = name.lower()
    hits: list[SymbolHit] = []
    for module in config.modules:
        parsed = parse_module(module.text)
        owner = "Глобальный модуль" if module.owner_kind == "global" else module.owner_name
        for symbol in (*parsed.procedures, *parsed.variables):
            if symbol.name.lower() == needle:
                hits.append(
                    SymbolHit(
                        name=symbol.name,
                        kind=symbol.kind,
                        owner=owner,
                        module_title=module.title,
                        line=symbol.line,
                        end_line=symbol.end_line,
                        params=", ".join(symbol.params),
                        is_export=symbol.is_export,
                    )
                )
                if len(hits) >= limit:
                    return hits
    return hits


def find_calls(config: Config, name: str, limit: int = 30) -> list[CallHit]:
    index = ensure(config)
    if index is not None:
        rows = index.find_calls(name, limit)
        return [
            CallHit(
                caller=row[0],
                owner=row[1],
                module_title=row[2],
                line=row[3],
                target_owner=row[4] or "",
                rule=row[5] or "",
            )
            for row in rows
        ]

    needle = name.lower()
    hits: list[CallHit] = []
    for module in config.modules:
        parsed = parse_module(module.text)
        owner = "Глобальный модуль" if module.owner_kind == "global" else module.owner_name
        for call in parsed.calls:
            if call.callee.lower() == needle:
                hits.append(
                    CallHit(
                        caller=call.caller,
                        owner=owner,
                        module_title=module.title,
                        line=call.line,
                    )
                )
                if len(hits) >= limit:
                    return hits
    return hits
