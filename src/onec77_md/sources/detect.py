"""Определение источника по пути: OLE-файл, текстовая выгрузка или каталог базы."""
from __future__ import annotations

from pathlib import Path

from .ole import OleMdSource
from .text import TextMdSource

OLE_MAGIC = b"\xd0\xcf\x11\xe0"


def open_source(path: str | Path):
    """Возвращает OLE или текстовый источник по содержимому пути."""
    target = Path(path)
    if target.is_dir():
        md_file = target / "1Cv7.MD"
        if md_file.is_file():
            return OleMdSource(md_file)
        return TextMdSource(target)

    with target.open("rb") as handle:
        magic = handle.read(4)
    if magic == OLE_MAGIC:
        return OleMdSource(target)
    return TextMdSource(target)
