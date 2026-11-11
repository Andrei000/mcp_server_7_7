"""Подготовка sys.path для локальных зависимостей проекта (`.deps`)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bootstrap() -> Path:
    """Добавляет `.deps` и модули pywin32 в пути импорта. Возвращает корень проекта."""
    root = project_root()
    src = root / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

    deps = Path(os.environ.get("ONE77_DEPS_DIR", root / ".deps"))
    if deps.is_dir():
        for extra in (deps, deps / "win32", deps / "win32" / "lib", deps / "win32comext"):
            if extra.is_dir() and str(extra) not in sys.path:
                sys.path.insert(0, str(extra))
        system32 = deps / "pywin32_system32"
        if system32.is_dir() and hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(str(system32))
            except OSError:
                pass
    return root


bootstrap()
