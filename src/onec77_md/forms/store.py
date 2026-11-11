"""Ленивое чтение разметки форм из OLE-контейнера."""
from __future__ import annotations

import threading
from pathlib import Path

import olefile

from .layout import FormLayout, parse_container, parse_dialog


class FormLayoutStore:
    """Открывает 1Cv7.MD один раз и разбирает `Dialog Stream` по требованию."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._ole: olefile.OleFileIO | None = None
        self._paths: dict[str, tuple[str, ...]] = {}
        self._cache: dict[str, FormLayout] = {}
        self._lock = threading.Lock()

    def _ensure_open(self) -> None:
        if self._ole is not None:
            return
        self._ole = olefile.OleFileIO(str(self.path))
        for stream in self._ole.listdir():
            if len(stream) >= 2 and stream[-1] == "Dialog Stream" and "_Number" in stream[1]:
                number = stream[1].rsplit("_Number", 1)[1]
                self._paths[number] = tuple(stream)

    def available(self) -> bool:
        try:
            with self._lock:
                self._ensure_open()
            return True
        except Exception:  # noqa: BLE001
            return False

    def layout(self, form_id: str) -> FormLayout | None:
        key = str(form_id)
        with self._lock:
            self._ensure_open()
            if key in self._cache:
                return self._cache[key]
            path = self._paths.get(key)
            if path is None:
                return None
            blob = self._ole.openstream(list(path)).read()
            result = parse_dialog(blob)
            self._cache[key] = result
            return result

    def find_handlers(self, name: str, limit: int = 10) -> list[tuple[str, str, str]]:
        """Ищет элементы форм, чей обработчик ссылается на имя: (form_id, класс, обработчик)."""
        needle = name.lower()
        found: list[tuple[str, str, str]] = []
        with self._lock:
            self._ensure_open()
            form_ids = list(self._paths)
        for form_id in form_ids:
            layout = self.layout(form_id)
            if layout is None:
                continue
            for control in layout.controls:
                if needle in control.action.lower():
                    found.append((form_id, control.cls, control.action))
                    if len(found) >= limit:
                        return found
        return found

    def entries(self, form_id: str) -> list[tuple[str, str, str]]:
        key = str(form_id)
        with self._lock:
            self._ensure_open()
            path = self._paths.get(key)
            if path is None:
                return []
            container = tuple(path[:-1]) + ("Container.Contents",)
            if not self._ole.exists(container):
                return []
            return parse_container(self._ole.openstream(list(container)).read())

    def close(self) -> None:
        with self._lock:
            if self._ole is not None:
                self._ole.close()
                self._ole = None
            self._paths.clear()
            self._cache.clear()


_stores: dict[str, FormLayoutStore] = {}


def get_store(path: str | Path) -> FormLayoutStore:
    key = str(Path(path))
    if key not in _stores:
        _stores[key] = FormLayoutStore(path)
    return _stores[key]
