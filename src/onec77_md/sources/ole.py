"""Источник метаданных: файл `1Cv7.MD` (OLE2-контейнер)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import olefile
import zlib

from ..parsing.sections import Node, parse_sections

MAIN_STREAM = "Metadata/Main MetaData Stream"
MODULE_STREAM = "MD Programm text"
ENCODINGS = ("cp1251", "cp866", "utf-8")


class MdFormatError(RuntimeError):
    """Файл не похож на 1Cv7.MD."""


@dataclass
class RawModule:
    path: tuple[str, ...]
    text: str

    @property
    def key(self) -> str:
        return "/".join(self.path)


@dataclass
class RawConfig:
    source: Path
    root: list[Node]
    encoding: str
    stream_count: int
    size: int = 0
    modules: list[RawModule] = field(default_factory=list)
    kind: str = "ole"


def decompress_module(blob: bytes) -> bytes:
    """Модули 7.7 — zlib; у части версий заголовок срезан, тогда это raw deflate."""
    try:
        return zlib.decompress(blob)
    except zlib.error:
        pass
    try:
        return zlib.decompressobj(-15).decompress(blob)
    except zlib.error:
        return blob


class OleMdSource:
    """Читает дерево метаданных из OLE-контейнера 1Cv7.MD."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.is_file()

    def read(self) -> RawConfig:
        try:
            ole = olefile.OleFileIO(str(self.path))
        except Exception as exc:  # noqa: BLE001 - olefile кидает разные типы
            raise MdFormatError(f"не удалось открыть {self.path} как OLE-контейнер: {exc}") from exc

        with ole:
            if not ole.exists(MAIN_STREAM):
                raise MdFormatError(f"в {self.path.name} нет потока {MAIN_STREAM}")
            blob = ole.openstream(MAIN_STREAM).read()
            paths = ole.listdir()
            modules = self._read_modules(ole, paths)

        text, encoding = self._decode(blob)
        nodes = parse_sections(text)
        # до и после дерева в файле встречается мусор; берём первый список
        root = next((node for node in nodes if isinstance(node, list)), [])
        if not root:
            raise MdFormatError("дерево метаданных пустое")
        return RawConfig(
            source=self.path,
            root=root,
            encoding=encoding,
            stream_count=len(paths),
            size=self.path.stat().st_size,
            modules=modules,
            kind="ole",
        )

    def _read_modules(self, ole: "olefile.OleFileIO", paths: list[list[str]]) -> list[RawModule]:
        result: list[RawModule] = []
        for path in paths:
            if not path or path[-1] != MODULE_STREAM:
                continue
            try:
                raw = ole.openstream(path).read()
            except Exception:  # noqa: BLE001 - битый стрим не должен ронять загрузку
                continue
            text, _ = self._decode(decompress_module(raw))
            result.append(RawModule(path=tuple(path), text=text))
        return result

    @staticmethod
    def _decode(blob: bytes) -> tuple[str, str]:
        for encoding in ENCODINGS:
            try:
                return blob.decode(encoding), encoding
            except UnicodeDecodeError:
                continue
        return blob.decode("cp1251", errors="replace"), "cp1251/replace"
