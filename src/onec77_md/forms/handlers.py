"""Имена процедур, на которые ссылаются обработчики элементов формы."""
from __future__ import annotations

import re

# вызов в строке обработчика: `ПоискКонтрагента()` или `ОткрытьФорму("...")`
CALL = re.compile(r"([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9]*)\s*\(")

# системные действия 7.7, которые не являются процедурами конфигурации
BUILTIN = {
    "закрыть", "выполнить", "открытьформу", "открытьформурасширенно", "восстановитьзначение",
    "сохранитьзначение", "предупреждение", "вопрос", "сообщить",
}


def handler_names(action: str) -> list[str]:
    """Уникальные имена процедур в строке обработчика, без системных действий."""
    names: list[str] = []
    seen: set[str] = set()
    for match in CALL.finditer(action or ""):
        name = match.group(1)
        key = name.lower()
        if key in BUILTIN or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names
