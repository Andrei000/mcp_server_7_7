"""Модель метаданных 1С 7.7, не зависящая от источника."""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any

# Код типа поля из MD -> русское имя
TYPE_NAMES: dict[str, str] = {
    "U": "Неопределено",
    "N": "Число",
    "S": "Строка",
    "D": "Дата",
    "B": "Справочник",
    "O": "Документ",
    "E": "Перечисление",
    "T": "Счёт",
    "P": "ПланСчетов",
    "K": "Субконто",
    "C": "Календарь",
    "A": "ВидРасчёта",
}

REF_KIND_BY_TYPE: dict[str, str] = {
    "B": "catalog",
    "O": "document",
    "E": "enum",
    "T": "account_chart",
    "P": "account_chart",
    "C": "calendar",
    "A": "calc_var",
}

# вид -> (русское имя, секция MD)
KINDS: dict[str, tuple[str, str]] = {
    "catalog": ("Справочник", "SbCnts"),
    "document": ("Документ", "Documents"),
    "register": ("Регистр", "Registers"),
    "enum": ("Перечисление", "EnumList"),
    "const": ("Константа", "Consts"),
    "journal": ("Журнал", "Journalisters"),
    "report": ("Отчёт", "ReportList"),
    "processing": ("Обработка", "CalcVars"),
    "calendar": ("Календарь", "Calendars"),
    "numerator": ("Нумератор", "DocNumDef"),
    "account_chart": ("План счетов", "AccountChart"),
}

KIND_ALIASES: dict[str, str] = {}
for _kind, (_ru, _section) in KINDS.items():
    KIND_ALIASES[_kind] = _kind
    KIND_ALIASES[_ru.lower()] = _kind
KIND_ALIASES.update(
    {
        "справочники": "catalog",
        "документы": "document",
        "регистры": "register",
        "перечисления": "enum",
        "константы": "const",
        "журналы": "journal",
        "отчёты": "report",
        "отчет": "report",
        "отчеты": "report",
        "обработки": "processing",
        "обработка": "processing",
        "календари": "calendar",
        "план счетов": "account_chart",
        "планы счетов": "account_chart",
        "sbcnts": "catalog",
        "documents": "document",
        "registers": "register",
        "enumlist": "enum",
        "consts": "const",
        "reportlist": "report",
    }
)


def kind_label(kind: str) -> str:
    return KINDS.get(kind, (kind, ""))[0]


def resolve_kind(value: str) -> str | None:
    return KIND_ALIASES.get(value.strip().lower())


@dataclass
class Field:
    """Реквизит шапки, колонка ТЧ, измерение или ресурс регистра."""

    id: str
    name: str
    synonym: str = ""
    comment: str = ""
    type_code: str = "U"
    length: int = 0
    precision: int = 0
    ref_id: str = ""
    ref_name: str = ""
    role: str = "attribute"

    @property
    def type_name(self) -> str:
        base = TYPE_NAMES.get(self.type_code, self.type_code)
        if self.type_code in REF_KIND_BY_TYPE:
            return f"{base}.{self.ref_name}" if self.ref_name else base
        if self.type_code == "S" and self.length:
            return f"Строка({self.length})"
        if self.type_code == "N":
            if self.precision:
                return f"Число({self.length},{self.precision})"
            return f"Число({self.length})" if self.length else "Число"
        return base

    def describe(self) -> str:
        title = self.name
        if self.synonym and self.synonym != self.name:
            title += f" ({self.synonym})"
        return f"{title} : {self.type_name}"


@dataclass
class EnumValue:
    id: str
    name: str
    synonym: str = ""
    comment: str = ""


@dataclass
class FormRef:
    id: str
    name: str


@dataclass
class Module:
    """Текст модуля: глобальный, объекта, формы, проведения."""

    key: str
    owner_kind: str
    owner_id: str
    owner_name: str
    title: str
    text: str
    form_id: str = ""

    @property
    def lines(self) -> int:
        return self.text.count("\n") + 1 if self.text else 0


@dataclass
class MdObject:
    kind: str
    id: str
    name: str
    synonym: str = ""
    comment: str = ""
    fields: list[Field] = dc_field(default_factory=list)
    tabular: list[Field] = dc_field(default_factory=list)
    enum_values: list[EnumValue] = dc_field(default_factory=list)
    forms: list[FormRef] = dc_field(default_factory=list)
    extras: dict[str, Any] = dc_field(default_factory=dict)

    @property
    def title(self) -> str:
        return f"{kind_label(self.kind)}.{self.name}"

    @property
    def display_name(self) -> str:
        return self.synonym or self.name

    def describe_line(self) -> str:
        parts = [self.title]
        if self.synonym and self.synonym != self.name:
            parts.append(f"— {self.synonym}")
        stats = []
        if self.fields:
            stats.append(f"реквизитов: {len(self.fields)}")
        if self.tabular:
            stats.append(f"ТЧ: {len(self.tabular)}")
        if self.enum_values:
            stats.append(f"значений: {len(self.enum_values)}")
        if stats:
            parts.append(f"({', '.join(stats)})")
        return " ".join(parts)


@dataclass
class Config:
    name: str
    synonym: str
    source_path: str
    size: int
    encoding: str
    source_kind: str = "ole"
    objects: list[MdObject] = dc_field(default_factory=list)
    common_fields: list[Field] = dc_field(default_factory=list)
    modules: list[Module] = dc_field(default_factory=list)

    def __post_init__(self) -> None:
        self.by_kind: dict[str, list[MdObject]] = {}
        self.by_id: dict[str, MdObject] = {}
        self.by_form_id: dict[str, MdObject] = {}
        self.modules_by_owner: dict[tuple[str, str], list[Module]] = {}
        for obj in self.objects:
            self.by_kind.setdefault(obj.kind, []).append(obj)
            if obj.id:
                self.by_id[obj.id] = obj
            for form in obj.forms:
                if form.id:
                    self.by_form_id[form.id] = obj
        self.reindex_modules()

    def reindex_modules(self) -> None:
        self.modules_by_owner = {}
        for module in self.modules:
            self.modules_by_owner.setdefault((module.owner_kind, module.owner_id), []).append(module)

    def modules_of(self, obj: MdObject) -> list[Module]:
        return self.modules_by_owner.get((obj.kind, obj.id), [])

    def of_kind(self, kind: str) -> list[MdObject]:
        return self.by_kind.get(kind, [])

    def counts(self) -> dict[str, int]:
        return {kind: len(items) for kind, items in self.by_kind.items()}
