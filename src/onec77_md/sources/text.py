"""Второй источник: текстовая выгрузка конфигурации (`*.md` файлы)."""
from __future__ import annotations

from pathlib import Path

from ..parsing.sections import Node, parse_sections
from .ole import MdFormatError, RawConfig

MD_SUFFIXES = {".md", ".txt"}
# в выгрузке файлы бывают и UTF-8, и CP1251 — UTF-8 пробуем первым, чтобы не словить мойибаке
TEXT_ENCODINGS = ("utf-8", "cp1251", "cp866")


def _decode(blob: bytes) -> tuple[str, str]:
    for encoding in TEXT_ENCODINGS:
        try:
            return blob.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return blob.decode("cp1251", errors="replace"), "cp1251/replace"


class TextMdSource:
    """Читает дерево метаданных из текстовой выгрузки: файл или каталог с `*.md`."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def _files(self) -> list[Path]:
        if self.path.is_file():
            return [self.path]
        files = [
            item
            for item in sorted(self.path.rglob("*"))
            if item.is_file() and item.suffix.lower() in MD_SUFFIXES
        ]
        return files

    def read(self) -> RawConfig:
        files = self._files()
        if not files:
            raise MdFormatError(f"в {self.path} нет файлов .md — это не текстовая выгрузка")

        root: list[Node] = []
        encoding = ""
        total_size = 0
        for file in files:
            blob = file.read_bytes()
            total_size += len(blob)
            text, current = _decode(blob)
            encoding = encoding or current
            nodes = parse_sections(text)
            for node in nodes:
                if isinstance(node, list) and node:
                    # файл целиком = одна секция верхнего уровня
                    if isinstance(node[0], str):
                        root.append(node)
                    else:
                        root.extend(child for child in node if isinstance(child, list))
        if not root:
            raise MdFormatError("в файлах выгрузки не нашлось дерева метаданных")
        return RawConfig(
            source=self.path,
            root=root,
            encoding=encoding or "cp1251",
            stream_count=len(files),
            size=total_size,
            modules=[],
            kind="text",
        )
