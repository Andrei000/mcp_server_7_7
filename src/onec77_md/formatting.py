"""Текстовое представление модели: его читает агент, а не машина."""
from __future__ import annotations

import re

from .model.entities import KINDS, Config, Field, MdObject, Module, kind_label

ROLE_TITLES = {
    "dimension": "Измерения",
    "resource": "Ресурсы",
    "attribute": "Реквизиты",
    "tabfield": "Табличная часть",
    "common": "Общие реквизиты документов",
}


def human_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} МБ"
    if size >= 1024:
        return f"{size / 1024:.0f} КБ"
    return f"{size} Б"


def symbols_report(hits: list, name: str) -> str:
    if not hits:
        return f"Символ «{name}» не найден (точное совпадение, без учёта регистра)."
    kinds = {"procedure": "Процедура", "function": "Функция", "variable": "Переменная"}
    lines = [f"Объявлений «{name}»: {len(hits)}"]
    for hit in hits:
        kind = kinds.get(hit.kind, hit.kind)
        if hit.kind == "variable":
            signature = hit.name
        else:
            signature = f"{hit.name}({hit.params})"
        export = " Экспорт" if hit.is_export else ""
        span = f":{hit.line}" + (f"–{hit.end_line}" if hit.end_line and hit.end_line != hit.line else "")
        lines.append(f"  {kind} {signature}{export}")
        lines.append(f"      {hit.owner} [{hit.module_title}] {span}")
    return "\n".join(lines)


def calls_report(hits: list, name: str) -> str:
    if not hits:
        return f"Вызовов «{name}» не найдено (комментарии и строковые литералы не учитываются)."
    lines = [f"Вызовов «{name}»: {len(hits)}"]
    for hit in hits:
        caller = hit.caller or "вне процедуры"
        tail = ""
        if hit.rule == "ambiguous":
            tail = "  (вызов неоднозначен: объявлений несколько)"
        elif hit.target_owner and hit.target_owner != hit.owner:
            tail = f"  → {hit.target_owner}"
        elif hit.rule == "unique":
            tail = "  → единственное объявление"
        lines.append(f"  {hit.owner} [{hit.module_title}] :{hit.line} — {caller}{tail}")
    return "\n".join(lines)


def patch_report(title: str, changes: list, diff_path=None, max_lines: int = 200) -> str:
    if not changes:
        return f"{title}: совпадений в коде не найдено."
    total = sum(change.count for change in changes)
    lines = [f"{title}: модулей {len(changes)}, замен {total}"]
    if diff_path is not None:
        lines.append(f"Файл: {diff_path}")
    lines.append("")
    diff = "".join(change.diff for change in changes)
    diff_lines = diff.splitlines()
    lines.extend(diff_lines[:max_lines])
    if len(diff_lines) > max_lines:
        lines.append(f"… diff обрезан: всего {len(diff_lines)} строк, полный текст в файле")
    return "\n".join(lines)


def config_summary(config: Config) -> str:
    lines = [
        f"Конфигурация: {config.synonym or config.name}",
        f"Источник: {config.source_path} ({human_size(config.size)})",
        f"Тип источника: {'текстовая выгрузка' if config.source_kind == 'text' else 'OLE-контейнер 1Cv7.MD'}",
        f"Кодировка MD: {config.encoding}",
    ]
    counts = config.counts()
    total = sum(counts.values())
    lines.append(f"Объектов метаданных: {total}")
    lines.append("")
    for kind in KINDS:
        if counts.get(kind):
            lines.append(f"  {kind_label(kind):<15} {counts[kind]:>4}")
    if config.common_fields:
        lines.append("")
        lines.append(f"Общих реквизитов документов: {len(config.common_fields)}")
    if config.modules:
        total_lines = sum(m.lines for m in config.modules)
        lines.append(f"Модулей: {len(config.modules)} ({total_lines} строк)")
    return "\n".join(lines)


def _field_lines(fields: list[Field]) -> list[str]:
    return [f"    - {field.describe()}" for field in fields]


def object_card(obj: MdObject, modules: list[Module] | None = None) -> str:
    lines = [f"{obj.title}" + (f" — {obj.synonym}" if obj.synonym and obj.synonym != obj.name else "")]
    meta = [f"id: {obj.id}"]
    if obj.comment:
        meta.append(f"комментарий: {obj.comment}")
    lines.append("  " + ", ".join(meta))

    if obj.enum_values:
        lines.append(f"  Значения ({len(obj.enum_values)}):")
        for value in obj.enum_values:
            label = value.name + (f" — {value.synonym}" if value.synonym and value.synonym != value.name else "")
            lines.append(f"    - {label}")

    by_role: dict[str, list[Field]] = {}
    for field in obj.fields:
        by_role.setdefault(field.role, []).append(field)
    for role, fields in by_role.items():
        lines.append(f"  {ROLE_TITLES.get(role, role)} ({len(fields)}):")
        lines.extend(_field_lines(fields))

    if obj.tabular:
        lines.append(f"  {ROLE_TITLES['tabfield']} ({len(obj.tabular)}):")
        lines.extend(_field_lines(obj.tabular))

    if obj.forms:
        lines.append("  Формы: " + ", ".join(_form_labels(obj, modules or [])))

    if modules:
        lines.append(f"  Модули ({len(modules)}):")
        for module in modules:
            lines.append(f"    - {module.title}: {module.lines} строк")

    if not obj.fields and not obj.tabular and not obj.enum_values:
        lines.append("  (состав не описан в этой версии формата)")
    return "\n".join(lines)


def _form_labels(obj: MdObject, modules: list[Module]) -> list[str]:
    labels = []
    for form in obj.forms:
        label = f"{form.name} (id {form.id}"
        module = next((m for m in modules if m.form_id == form.id), None)
        if module:
            label += f", модуль {module.lines} строк"
        labels.append(label + ")")
    return labels


def forms_card(obj: MdObject, modules: list[Module], store=None, limit: int = 40) -> str:
    if not obj.forms:
        builtin = [m for m in modules if m.title in ("Модуль формы документа", "Модуль формы журнала")]
        if builtin:
            lines = [f"{obj.title} — встроенная форма (в метаданных не перечислена):"]
            lines.extend(f"  - {m.title}: {m.lines} строк" for m in builtin)
            return "\n".join(lines)
        return f"У {obj.title} нет форм в метаданных."
    lines = [f"{obj.title} — формы ({len(obj.forms)}):"]
    for form in obj.forms:
        module = next((m for m in modules if m.form_id == form.id), None)
        suffix = f", модуль: {module.lines} строк" if module else ", модуля нет"
        lines.append(f"  - {form.name}, id {form.id}{suffix}")

        layout = store.layout(form.id) if store is not None else None
        if layout is None:
            continue
        if layout.controls:
            lines.append(f"    элементов: {len(layout.controls)}")
            for control in layout.controls[:limit]:
                lines.append(f"      · {control.describe()}")
            if len(layout.controls) > limit:
                lines.append(f"      … ещё {len(layout.controls) - limit}")
        elif layout.error:
            lines.append(f"    разметка не прочитана: {layout.error}")

    lines.append("")
    if store is None:
        lines.append("Разметка формы доступна только для OLE-источника (1Cv7.MD).")
    return "\n".join(lines)


def module_text(module: Module) -> str:
    owner = "Глобальный модуль" if module.owner_kind == "global" else f"{kind_label(module.owner_kind)}.{module.owner_name}"
    header = f"# {owner} — {module.title} ({module.lines} строк)"
    return f"{header}\n\n{module.text}"


def module_search(config: Config, query: str, use_regex: bool, limit: int) -> str:
    needle = query.strip()
    if not needle:
        return "Пустой запрос."
    try:
        pattern = re.compile(needle, re.IGNORECASE if not use_regex else 0) if use_regex else None
    except re.error as exc:
        return f"Некорректное регулярное выражение: {exc}"

    hits: list[str] = []
    matched_modules: set[str] = set()
    total = 0
    for module in config.modules:
        owner = "Глобальный модуль" if module.owner_kind == "global" else f"{kind_label(module.owner_kind)}.{module.owner_name}"
        for number, line in enumerate(module.text.splitlines(), start=1):
            if (pattern.search(line) if pattern else needle.lower() in line.lower()):
                total += 1
                matched_modules.add(module.key)
                if len(hits) < limit:
                    hits.append(f"{owner} [{module.title}] :{number}: {line.strip()[:160]}")
    if not total:
        return f"По запросу «{query}» в модулях ничего не найдено."
    head = f"Совпадений: {total} в {len(matched_modules)} модулях" + (f", показано {len(hits)}" if total > len(hits) else "")
    return "\n".join([head, *hits])


def object_list(objects: list[MdObject], title: str = "") -> str:
    if not objects:
        return "Ничего не найдено."
    lines = [title] if title else []
    for obj in objects:
        lines.append(obj.describe_line())
    return "\n".join(lines)


def search_results(config: Config, query: str, limit: int) -> str:
    needle = query.strip().lower()
    if not needle:
        return "Пустой запрос."
    hits: list[MdObject] = []
    for obj in config.objects:
        haystack = " ".join((obj.name, obj.synonym, obj.comment)).lower()
        if needle in haystack:
            hits.append(obj)
    if not hits:
        # попробуем по реквизитам
        for obj in config.objects:
            if any(needle in f.name.lower() for f in (*obj.fields, *obj.tabular)):
                hits.append(obj)
    if not hits:
        return f"По запросу «{query}» ничего не найдено."
    shown = hits[:limit]
    lines = [f"Найдено: {len(hits)}" + (f", показано {len(shown)}" if len(hits) > len(shown) else "")]
    for obj in shown:
        lines.append(obj.describe_line())
    return "\n".join(lines)
