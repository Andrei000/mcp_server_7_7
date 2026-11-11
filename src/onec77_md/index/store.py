"""SQLite-индекс: строки модулей и объекты, чтобы поиск не зависел от размера базы."""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from hashlib import sha1
from pathlib import Path

from ..model.entities import Config

log = logging.getLogger("onec77_md.index")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS lines (
    module_key TEXT NOT NULL,
    owner      TEXT NOT NULL,
    title      TEXT NOT NULL,
    line_no    INTEGER NOT NULL,
    text       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lines_module ON lines(module_key);
CREATE TABLE IF NOT EXISTS objects (
    kind TEXT, obj_id TEXT, name TEXT, synonym TEXT, fields INTEGER, tabular INTEGER
);
"""


def cache_dir() -> Path:
    override = os.environ.get("ONE77_CACHE_DIR")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "onec77-md" / "cache"


def fingerprint(config: Config) -> str:
    raw = f"{config.source_path}|{config.size}|{len(config.objects)}|{len(config.modules)}"
    return sha1(raw.encode("utf-8")).hexdigest()[:16]


def index_path(config: Config) -> Path:
    return cache_dir() / f"index-{fingerprint(config)}.sqlite"


class Index:
    def __init__(self, path: Path):
        self.path = path
        # MCP обрабатывает вызовы в разных потоках, поэтому соединение общее и под замком
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.Lock()
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    def build(self, config: Config) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM lines")
            self.conn.execute("DELETE FROM objects")
            rows = []
            for module in config.modules:
                owner = (
                    "Глобальный модуль"
                    if module.owner_kind == "global"
                    else f"{module.owner_name}"
                )
                for number, line in enumerate(module.text.splitlines(), start=1):
                    rows.append((module.key, owner, module.title, number, line))
            self.conn.executemany(
                "INSERT INTO lines (module_key, owner, title, line_no, text) VALUES (?,?,?,?,?)",
                rows,
            )
            self.conn.executemany(
                "INSERT INTO objects (kind, obj_id, name, synonym, fields, tabular) VALUES (?,?,?,?,?,?)",
                [
                    (o.kind, o.id, o.name, o.synonym, len(o.fields), len(o.tabular))
                    for o in config.objects
                ],
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('fingerprint', ?)",
                (fingerprint(config),),
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('built_rows', ?)",
                (str(len(rows)),),
            )

    def search_lines(self, query: str, limit: int) -> list[tuple[str, str, int, str]]:
        pattern = f"%{query}%"
        with self.lock:
            cursor = self.conn.execute(
                "SELECT owner, title, line_no, text FROM lines WHERE text LIKE ? LIMIT ?",
                (pattern, limit),
            )
            return cursor.fetchall()

    def count_lines(self) -> int:
        with self.lock:
            return int(self.conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0])

    def count_hits(self, query: str) -> int:
        with self.lock:
            return int(
                self.conn.execute(
                    "SELECT COUNT(*) FROM lines WHERE text LIKE ?", (f"%{query}%",)
                ).fetchone()[0]
            )


_instances: dict[str, Index] = {}
_ensure_lock = threading.Lock()


def ensure(config: Config, rebuild: bool = False) -> Index | None:
    """Открывает готовый индекс или строит его; None — если индекс недоступен."""
    try:
        path = index_path(config)
        key = str(path)
        with _ensure_lock:
            if not rebuild and key in _instances:
                return _instances[key]
            path.parent.mkdir(parents=True, exist_ok=True)
            index = Index(path)
            stored = index.conn.execute(
                "SELECT value FROM meta WHERE key='fingerprint'"
            ).fetchone()
            if rebuild or stored is None or stored[0] != fingerprint(config):
                index.build(config)
            _instances[key] = index
            return index
    except Exception as exc:  # noqa: BLE001 - индекс не должен ломать основные инструменты
        log.warning("SQLite-индекс недоступен (%s), поиск пойдёт перебором", exc)
        return None
