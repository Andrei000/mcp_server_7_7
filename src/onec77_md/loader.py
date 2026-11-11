"""Загрузка конфигурации и кэш по mtime/размеру файла."""
from __future__ import annotations

import os
from pathlib import Path

from .model.entities import Config
from .model.mapping import build_config
from .sources.detect import open_source
from .sources.ole import RawConfig

FALLBACK_PATH = r"D:\DSH\Projects\Rain\1Cv7.MD"


def default_path() -> Path:
    """Путь по умолчанию: ONE77_MD_PATH, иначе база Rain на этой машине."""
    return Path(os.environ.get("ONE77_MD_PATH") or FALLBACK_PATH)


class Registry:
    """Держит одну активную конфигурацию и перечитывает её при изменении файла."""

    def __init__(self) -> None:
        self._path: Path | None = None
        self._stamp: tuple[int, int] | None = None
        self._config: Config | None = None

    @property
    def path(self) -> Path:
        return self._path or default_path()

    def load(self, path: str | Path | None = None) -> Config:
        target = Path(path) if path else self.path
        if not target.exists():
            raise FileNotFoundError(
                f"путь не найден: {target}. Укажите 1Cv7.MD или каталог выгрузки "
                "в аргументе либо в переменной ONE77_MD_PATH."
            )
        stat = target.stat()
        stamp = (stat.st_mtime_ns, stat.st_size)
        if self._config is not None and self._path == target and self._stamp == stamp:
            return self._config

        raw: RawConfig = open_source(target).read()
        config = build_config(raw)
        self._path, self._stamp, self._config = target, stamp, config
        return config


registry = Registry()
