"""Проверки конфигурации: битые ссылки, неиспользуемые объекты, дубли и пустоты."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..model.entities import REF_KIND_BY_TYPE, Config, MdObject, kind_label

IDENT = re.compile(r"[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*")


@dataclass
class Finding:
    rule: str
    title: str
    total: int
    samples: list[str] = field(default_factory=list)


def _module_tokens(config: Config) -> set[str]:
    tokens: set[str] = set()
    for module in config.modules:
        tokens.update(IDENT.findall(module.text))
    return tokens


def broken_refs(config: Config) -> Finding:
    samples: list[str] = []
    total = 0
    for obj in config.objects:
        for field in (*obj.fields, *obj.tabular):
            if field.type_code not in REF_KIND_BY_TYPE or not field.ref_id or field.ref_id == "0":
                continue
            target = config.by_id.get(field.ref_id)
            if target is not None and target.kind == REF_KIND_BY_TYPE[field.type_code]:
                continue
            total += 1
            samples.append(f"{obj.title}.{field.name} → id {field.ref_id} (объект не найден)")
    return Finding("broken_refs", "Битые ссылки", total, sorted(samples))


def unused_objects(config: Config, tokens: set[str]) -> Finding:
    referenced: set[str] = set()
    for obj in config.objects:
        for field in (*obj.fields, *obj.tabular):
            if field.ref_id and field.ref_id != "0":
                referenced.add(field.ref_id)
    samples: list[str] = []
    for obj in config.objects:
        if obj.id in referenced or obj.name in tokens:
            continue
        samples.append(obj.title)
    return Finding("unused", "Неиспользуемые объекты (нет ссылок и упоминаний в модулях)", len(samples), sorted(samples))

def duplicate_synonyms(config: Config) -> Finding:
    groups: dict[str, list[MdObject]] = {}
    for obj in config.objects:
        synonym = (obj.synonym or "").strip().lower()
        if synonym and synonym != obj.name.lower():
            groups.setdefault(synonym, []).append(obj)
    samples: list[str] = []
    for synonym, objects in sorted(groups.items()):
        if len(objects) > 1:
            names = ", ".join(f"{kind_label(o.kind)}.{o.name}" for o in objects)
            samples.append(f"«{objects[0].synonym}»: {names}")
    return Finding("duplicate_synonyms", "Одинаковые синонимы", len(samples), samples)


def objects_without_forms(config: Config) -> Finding:
    samples = []
    for obj in config.objects:
        if obj.kind not in ("catalog", "report", "processing"):
            continue
        if obj.forms or config.modules_of(obj):
            continue
        samples.append(obj.title)
    return Finding("no_forms", "Объекты без форм и модулей", len(samples), sorted(samples))


def documents_without_transaction(config: Config) -> Finding:
    samples = []
    for obj in config.of_kind("document"):
        if not any(m.title == "Модуль проведения" for m in config.modules_of(obj)):
            samples.append(obj.title)
    return Finding("no_transaction", "Документы без модуля проведения", len(samples), sorted(samples))


def empty_objects(config: Config) -> Finding:
    # отчёты и обработки описываются формой и модулем, а не реквизитами — их не проверяем
    expected = {"catalog", "document", "register", "enum", "account_chart"}
    samples = []
    for obj in config.objects:
        if obj.kind not in expected:
            continue
        if not obj.fields and not obj.tabular and not obj.enum_values:
            samples.append(obj.title)
    return Finding("empty", "Объекты без состава", len(samples), sorted(samples))


ALL_RULES = {
    "broken_refs": broken_refs,
    "unused": None,  # требует предварительно собранных токенов
    "duplicate_synonyms": duplicate_synonyms,
    "no_forms": objects_without_forms,
    "no_transaction": documents_without_transaction,
    "empty": empty_objects,
}


def run_audit(config: Config, rule: str = "", limit: int = 20) -> str:
    wanted = [rule.strip()] if rule.strip() else list(ALL_RULES)
    unknown = [r for r in wanted if r not in ALL_RULES]
    if unknown:
        return f"Неизвестная проверка: {', '.join(unknown)}. Доступны: {', '.join(ALL_RULES)}"

    tokens: set[str] | None = None
    findings: list[Finding] = []
    for name in wanted:
        if name == "unused":
            tokens = tokens if tokens is not None else _module_tokens(config)
            findings.append(unused_objects(config, tokens))
        else:
            findings.append(ALL_RULES[name](config))

    lines = [f"Аудит конфигурации «{config.synonym or config.name}»", ""]
    problems = [f for f in findings if f.total]
    if not problems:
        lines.append("Проблем не найдено.")
        return "\n".join(lines)

    for finding in findings:
        lines.append(f"## {finding.title} — {finding.total}")
        if not finding.total:
            lines.append("  (нет)")
        else:
            shown = finding.samples[:limit]
            lines.extend(f"  - {item}" for item in shown)
            if finding.total > len(shown):
                lines.append(f"  ... ещё {finding.total - len(shown)}")
        lines.append("")
    if any(f.rule == "unused" for f in findings):
        lines.append("Примечание: «неиспользуемые» — эвристика по ссылочным типам и именам в модулях;")
        lines.append("журналы и отчёты могут попадать в список ложно.")
    return "\n".join(lines).rstrip() + "\n"
