"""Разовая проверка: требует ли глобальный модуль флаг Экспорт в этой базе."""
import sys

sys.path.insert(0, "src")

import onec77_md.bootstrap  # noqa: F401
from onec77_md.index.store import ensure
from onec77_md.loader import registry

config = registry.load()
index = ensure(config)

sql_calls = (
    "SELECT s.is_export, COUNT(*) FROM calls c "
    "JOIN symbols s ON s.module_key = c.target_module_key AND s.line = c.target_line "
    "WHERE c.rule = 'global' GROUP BY s.is_export"
)
print("вызовы глобальных процедур по признаку Экспорт:", index.conn.execute(sql_calls).fetchall())

sql_defs = (
    "SELECT is_export, COUNT(*) FROM symbols "
    "WHERE module_title = 'Глобальный модуль' AND kind != 'variable' GROUP BY is_export"
)
print("объявления в глобальном модуле:", index.conn.execute(sql_defs).fetchall())
