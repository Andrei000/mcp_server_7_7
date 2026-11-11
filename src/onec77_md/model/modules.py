"""Сопоставление OLE-стримов `MD Programm text` с объектами метаданных."""
from __future__ import annotations

import re

from ..sources.ole import RawConfig, RawModule
from .entities import Config, Module

NUMBERED = re.compile(r"^(?P<prefix>[A-Za-z]+)_Number(?P<id>\d+)$")

# (каталог стрима, тип модуля)
TITLES = {
    "SubList": "Модуль формы списка",
    "SubFolder": "Модуль формы элемента",
    "Subconto": "Модуль формы субконто",
    "Document": "Модуль формы документа",
    "Report": "Модуль отчёта",
    "CalcVar": "Модуль обработки",
    "Journal": "Модуль формы журнала",
}

# для SubList/SubFolder/Subconto идентификатор в имени стрима — это id формы
FORM_OWNED = {"SubList", "SubFolder", "Subconto"}


def _find_object(config: Config, kind: str, obj_id: str):
    obj = config.by_id.get(obj_id)
    if obj is not None and obj.kind == kind:
        return obj
    return None


def _resolve(config: Config, raw: RawModule) -> tuple[str, str, str, str, str, str] | None:
    """Возвращает (owner_kind, owner_id, owner_name, title, key, form_id) либо None."""
    parts = raw.path
    if len(parts) < 2:
        return None
    head, second = parts[0], parts[1]

    if head == "TypedText" and second == "ModuleText_Number1":
        return ("global", "0", "Глобальный модуль", "Глобальный модуль", "global", "")

    match = NUMBERED.match(second)
    if not match:
        return None
    prefix, obj_id = match.group("prefix"), match.group("id")

    if head == "TypedText" and prefix == "Transact":
        obj = _find_object(config, "document", obj_id)
        if obj:
            return ("document", obj.id, obj.name, "Модуль проведения", f"document:{obj.id}:transact", "")
        return None

    if head in FORM_OWNED:
        # SubList ссылается на id формы, SubFolder/Subconto — на id самого справочника
        obj = config.by_form_id.get(obj_id) or config.by_id.get(obj_id)
        if obj:
            title = TITLES.get(head, "Модуль формы")
            form_id = obj_id if head == "SubList" else ""
            return (obj.kind, obj.id, obj.name, title, f"{obj.kind}:{obj.id}:{head}:{obj_id}", form_id)
        return None

    kind_by_head = {
        "Document": "document",
        "Report": "report",
        "CalcVar": "processing",
        "Journal": "journal",
    }
    kind = kind_by_head.get(head)
    if not kind:
        return None
    obj = _find_object(config, kind, obj_id)
    if obj:
        title = TITLES.get(head, "Модуль")
        return (kind, obj.id, obj.name, title, f"{kind}:{obj.id}:{head}", "")
    return None


def build_modules(raw: RawConfig, config: Config) -> list[Module]:
    modules: list[Module] = []
    for raw_module in raw.modules:
        if not raw_module.text.strip():
            continue
        resolved = _resolve(config, raw_module)
        if resolved is None:
            continue
        owner_kind, owner_id, owner_name, title, key, form_id = resolved
        modules.append(
            Module(
                key=key,
                owner_kind=owner_kind,
                owner_id=owner_id,
                owner_name=owner_name,
                title=title,
                text=raw_module.text,
                form_id=form_id,
            )
        )
    return modules
