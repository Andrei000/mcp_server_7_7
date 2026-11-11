"""Преобразование разобранного MD-дерева в модель `Config`."""
from __future__ import annotations

from ..parsing.sections import Node, section, text
from ..sources.ole import RawConfig
from .entities import (
    REF_KIND_BY_TYPE,
    Config,
    EnumValue,
    Field,
    FormRef,
    MdObject,
)

# Секции, которые содержат объекты, и как их разбирать
OBJECT_SECTIONS = {
    "SbCnts": "catalog",
    "Documents": "document",
    "Registers": "register",
    "EnumList": "enum",
    "Consts": "const",
    "Journalisters": "journal",
    "ReportList": "report",
    "CalcVars": "processing",
    "Calendars": "calendar",
    "DocNumDef": "numerator",
    "AccountChart": "account_chart",
}

# Где у объекта лежат реквизиты
FIELD_SECTIONS = {
    "catalog": [("Params", "attribute")],
    "document": [("Head Fields", "attribute"), ("Table Fields", "tabfield")],
    "register": [("Props", "dimension"), ("Figures", "resource"), ("Flds", "attribute")],
    "journal": [("JournalFld", "attribute")],
    "account_chart": [("Params", "attribute")],
}


def _to_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _is_number(value: Node) -> bool:
    return isinstance(value, str) and value.isdigit()


def parse_field(node: list[Node], role: str = "attribute") -> Field | None:
    """Поле: [id, имя, синоним, комментарий, тип, длина, точность, ссылка, ...]."""
    if not isinstance(node, list) or len(node) < 2:
        return None
    return Field(
        id=text(node, 0),
        name=text(node, 1),
        synonym=text(node, 2),
        comment=text(node, 3),
        type_code=text(node, 4) or "U",
        length=_to_int(text(node, 5)),
        precision=_to_int(text(node, 6)),
        ref_id=text(node, 7),
        role=role,
    )


def _collect_fields(node: list[Node], role: str, into: list[Field]) -> None:
    for child in node[1:]:
        if isinstance(child, list):
            parsed = parse_field(child, role)
            if parsed and parsed.name:
                into.append(parsed)


def parse_object(kind: str, node: list[Node]) -> MdObject | None:
    if not isinstance(node, list) or len(node) < 2 or not _is_number(str(node[0])):
        return None

    obj = MdObject(
        kind=kind,
        id=text(node, 0),
        name=text(node, 1),
        comment=text(node, 2),
        synonym=text(node, 3),
    )

    for section_name, role in FIELD_SECTIONS.get(kind, []):
        found = section(node, section_name)
        if found:
            target = obj.tabular if role == "tabfield" else obj.fields
            _collect_fields(found, role, target)

    if kind == "const":
        parsed = parse_field(node, "attribute")
        if parsed:
            obj.fields.append(parsed)

    if kind == "enum":
        values = section(node, "EnumVal")
        if values:
            for child in values[1:]:
                if isinstance(child, list) and len(child) >= 2:
                    obj.enum_values.append(
                        EnumValue(
                            id=text(child, 0),
                            name=text(child, 1),
                            synonym=text(child, 2),
                            comment=text(child, 3),
                        )
                    )

    forms = section(node, "Form")
    if forms:
        for child in forms[1:]:
            if isinstance(child, list) and len(child) >= 2:
                obj.forms.append(FormRef(id=text(child, 0), name=text(child, 1)))

    return obj


def build_config(raw: RawConfig) -> Config:
    name, synonym = "", ""
    objects: list[MdObject] = []
    common_fields: list[Field] = []

    for item in raw.root:
        if not isinstance(item, list) or not item:
            continue
        head = item[0]
        if not isinstance(head, str):
            continue
        if head == "TaskItem" and len(item) > 1 and isinstance(item[1], list):
            name = text(item[1], 1)
            synonym = text(item[1], 3).strip('"')
        elif head == "GenJrnlFldDef":
            for child in item[1:]:
                parsed = parse_field(child, "common")
                if parsed:
                    common_fields.append(parsed)
        elif head in OBJECT_SECTIONS:
            kind = OBJECT_SECTIONS[head]
            for child in item[1:]:
                obj = parse_object(kind, child)
                if obj:
                    objects.append(obj)

    config = Config(
        name=name or raw.source.stem,
        synonym=synonym,
        source_path=str(raw.source),
        size=raw.size,
        encoding=raw.encoding,
        source_kind=raw.kind,
        objects=objects,
        common_fields=common_fields,
    )
    _resolve_refs(config)
    from .modules import build_modules

    config.modules = build_modules(raw, config)
    config.reindex_modules()
    return config


def _resolve_refs(config: Config) -> None:
    for obj in config.objects:
        for field in (*obj.fields, *obj.tabular):
            if field.type_code in REF_KIND_BY_TYPE and field.ref_id:
                target = config.by_id.get(field.ref_id)
                if target and target.kind == REF_KIND_BY_TYPE[field.type_code]:
                    field.ref_name = target.name
