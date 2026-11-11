"""Предложения правок: переименование и замена в коде модулей.

Сервер ничего не меняет в базе. Он готовит unified diff и, по желанию, раскладывает
файлы «до/после» в рабочий каталог — применяет человек или git.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from ..model.entities import Config, Module
from .parser import strip_noise

IDENT_CHARS = "A-Za-zА-Яа-яЁё0-9_"


@dataclass
class ModuleChange:
    module: Module
    owner: str
    file_name: str
    before: str
    after: str
    count: int

    @property
    def diff(self) -> str:
        return "".join(
            difflib.unified_diff(
                self.before.splitlines(keepends=True),
                self.after.splitlines(keepends=True),
                fromfile=f"a/{self.file_name}",
                tofile=f"b/{self.file_name}",
                n=2,
            )
        )


def _safe(name: str) -> str:
    return re.sub(r"[^\w.-]+", "_", name, flags=re.UNICODE).strip("_") or "module"


def _pattern(old: str, whole_word: bool) -> re.Pattern[str]:
    if whole_word:
        return re.compile(rf"(?<![{IDENT_CHARS}]){re.escape(old)}(?![{IDENT_CHARS}])", re.IGNORECASE)
    return re.compile(re.escape(old), re.IGNORECASE)


def replace_in_code(text: str, old: str, new: str, whole_word: bool = True) -> tuple[str, int]:
    """Замена только в коде: позиции берутся по тексту с вырезанными комментариями и строками."""
    masked = strip_noise(text)
    if len(masked) != len(text):  # страховка: индексы должны совпадать
        return text, 0
    pieces: list[str] = []
    last = 0
    count = 0
    for match in _pattern(old, whole_word).finditer(masked):
        pieces.append(text[last:match.start()])
        pieces.append(new)
        last = match.end()
        count += 1
    if not count:
        return text, 0
    pieces.append(text[last:])
    return "".join(pieces), count


def propose_rename(config: Config, symbol: str, new_name: str) -> list[ModuleChange]:
    changes: list[ModuleChange] = []
    for module in config.modules:
        after, count = replace_in_code(module.text, symbol, new_name, whole_word=True)
        if not count:
            continue
        owner = "Глобальный модуль" if module.owner_kind == "global" else module.owner_name
        file_name = f"{_safe(owner)}__{_safe(module.title)}.txt"
        changes.append(
            ModuleChange(
                module=module,
                owner=owner,
                file_name=file_name,
                before=module.text,
                after=after,
                count=count,
            )
        )
    return changes


def propose_replace(config: Config, old: str, new: str, whole_word: bool = False) -> list[ModuleChange]:
    changes: list[ModuleChange] = []
    for module in config.modules:
        after, count = replace_in_code(module.text, old, new, whole_word=whole_word)
        if not count:
            continue
        owner = "Глобальный модуль" if module.owner_kind == "global" else module.owner_name
        file_name = f"{_safe(owner)}__{_safe(module.title)}.txt"
        changes.append(
            ModuleChange(
                module=module,
                owner=owner,
                file_name=file_name,
                before=module.text,
                after=after,
                count=count,
            )
        )
    return changes


def write_patch(changes: list[ModuleChange], out_dir: Path) -> Path:
    """Раскладывает changes.diff и файлы «после» в каталог, возвращает путь к diff."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "after").mkdir(exist_ok=True)
    diff_path = out_dir / "changes.diff"
    parts = [change.diff for change in changes]
    diff_path.write_text("".join(parts), encoding="utf-8")
    for change in changes:
        (out_dir / "after" / change.file_name).write_text(change.after, encoding="utf-8")
    return diff_path
