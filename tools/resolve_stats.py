"""Статистика разрешения вызовов: сколько правил каждого типа."""
import sys

sys.path.insert(0, "src")

import onec77_md.bootstrap  # noqa: F401
from onec77_md.index.store import ensure
from onec77_md.loader import registry

config = registry.load()
index = ensure(config, rebuild=True)

rows = index.conn.execute("SELECT rule, COUNT(*) FROM calls GROUP BY rule ORDER BY 2 DESC").fetchall()
for rule, count in rows:
    print(f"{rule:10} {count}")

total = sum(count for _, count in rows)
resolved = sum(count for rule, count in rows if rule in ("local", "global", "unique"))
print(f"итого {total}, разрешено {resolved} ({resolved * 100 // total}%)")
