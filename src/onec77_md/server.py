"""MCP-сервер метаданных 1С 7.7."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from mcp.server import MCPServer

from . import __version__

from .formatting import (
    config_summary,
    forms_card,
    module_search,
    module_text,
    object_card,
    object_list,
    search_results,
)
from .audit.rules import run_audit
from .export.markdown import to_markdown
from .export.mermaid import to_mermaid
from .export.sql_ddl import to_sql
from .export.writer import to_json, write_export
from .forms.store import get_store
from .index.store import ensure as ensure_index
from .loader import registry
from .model.entities import KINDS, MdObject, kind_label, resolve_kind

EXPORT_FORMATS = ("json", "md", "markdown", "mermaid", "sql")

log = logging.getLogger("onec77_md")

mcp = MCPServer(
    name="onec77-md",
    version=__version__,
    instructions=(
        "Метаданные конфигурации 1С 7.7: справочники, документы, регистры, перечисления, "
        "константы, журналы, отчёты и обработки — с реквизитами, типами и ссылками. "
        "Начните с md_config_info, затем md_list_objects / md_get_object."
    ),
)


def _kind_name(value: str) -> str | None:
    return resolve_kind(value) if value else None


def _find_object(config, kind: str, name: str) -> tuple[MdObject | None, str]:
    """Ищет объект по виду и имени; понимает форму «Документ.Реализация»."""
    kind_key = _kind_name(kind)
    target = name.strip()
    if "." in target and not kind_key:
        prefix, _, rest = target.partition(".")
        kind_key = _kind_name(prefix)
        target = rest
    if not kind_key:
        return None, "Не указан вид объекта (например, document или «Документ.Реализация»)."
    for obj in config.of_kind(kind_key):
        if obj.name.lower() == target.lower():
            return obj, ""
    return None, f"{kind_label(kind_key)} «{target}» не найден."


@mcp.tool()
def md_config_info(path: str | None = None) -> str:
    """Сводка по конфигурации 7.7: имя, источник, количество объектов по видам.

    path — путь к 1Cv7.MD; если не задан, берётся ONE77_MD_PATH или последняя открытая база.
    """
    try:
        return config_summary(registry.load(path))
    except Exception as exc:  # noqa: BLE001 - текст ошибки важен агенту
        return f"Ошибка чтения конфигурации: {exc}"


@mcp.tool()
def md_list_objects(kind: str = "", mask: str = "", limit: int = 50) -> str:
    """Список объектов метаданных, компактно: «Документ.Имя — синоним (реквизитов: N)».

    kind — вид: catalog/справочник, document/документ, register/регистр, enum/перечисление,
    const/константа, journal/журнал, report/отчёт, processing/обработка.
    Пусто — все виды. mask — подстрока имени или синонима.
    """
    try:
        config = registry.load()
        kind_key = _kind_name(kind)
        if kind and not kind_key:
            return f"Неизвестный вид «{kind}». Доступны: {', '.join(KINDS)} и русские названия."
        objects = config.of_kind(kind_key) if kind_key else config.objects
        if mask:
            needle = mask.strip().lower()
            objects = [
                o for o in objects if needle in o.name.lower() or needle in o.synonym.lower()
            ]
        objects = sorted(objects, key=lambda o: (o.kind, o.name.lower()))
        if not objects:
            return "Ничего не найдено."
        total = len(objects)
        shown = objects[: max(1, limit)]
        title = f"Объектов: {total}" + (f", показано {len(shown)}" if total > len(shown) else "")
        return object_list(shown, title)
    except Exception as exc:  # noqa: BLE001
        return f"Ошибка чтения конфигурации: {exc}"


@mcp.tool()
def md_get_object(kind: str = "", name: str = "") -> str:
    """Карточка объекта: реквизиты шапки, табличная часть, значения перечисления, формы.

    Можно передать kind и name отдельно либо name вида «Документ.Реализация».
    """
    try:
        config = registry.load()
        kind_key = _kind_name(kind)
        target = name.strip()
        if "." in target and not kind_key:
            prefix, _, rest = target.partition(".")
            kind_key = _kind_name(prefix)
            target = rest
        if not kind_key:
            return "Не указан вид объекта (например, document или «Документ.Реализация»)."
        for obj in config.of_kind(kind_key):
            if obj.name.lower() == target.lower():
                return object_card(obj, config.modules_of(obj))
        # нечёткий подскок по подстроке
        candidates = [o for o in config.of_kind(kind_key) if target.lower() in o.name.lower()]
        if len(candidates) == 1:
            return object_card(candidates[0], config.modules_of(candidates[0]))
        if candidates:
            names = ", ".join(o.name for o in candidates[:15])
            return f"Объект «{target}» не найден точно. Похожие: {names}"
        return f"{kind_label(kind_key)} «{target}» не найден."
    except Exception as exc:  # noqa: BLE001
        return f"Ошибка чтения конфигурации: {exc}"


@mcp.tool()
def md_find(query: str, limit: int = 20) -> str:
    """Поиск по имени, синониму и комментарию объектов и по именам реквизитов."""
    try:
        return search_results(registry.load(), query, max(1, limit))
    except Exception as exc:  # noqa: BLE001
        return f"Ошибка чтения конфигурации: {exc}"


@mcp.tool()
def md_get_attribute(kind: str = "", name: str = "", attribute: str = "") -> str:
    """Один реквизит объекта по имени: тип, длина, точность, ссылка, роль.

    attribute можно указывать как «Цена» — ищется и в шапке, и в табличной части.
    """
    try:
        config = registry.load()
        kind_key = _kind_name(kind)
        target = name.strip()
        if "." in target and not kind_key:
            prefix, _, rest = target.partition(".")
            kind_key = _kind_name(prefix)
            target = rest
        if not kind_key:
            return "Не указан вид объекта."
        obj = next((o for o in config.of_kind(kind_key) if o.name.lower() == target.lower()), None)
        if obj is None:
            return f"{kind_label(kind_key)} «{target}» не найден."
        needle = attribute.strip().lower()
        for field in (*obj.fields, *obj.tabular):
            if field.name.lower() == needle:
                return f"{obj.title}.{field.name}: {field.type_name}"
        return f"У {obj.title} нет реквизита «{attribute}»."
    except Exception as exc:  # noqa: BLE001
        return f"Ошибка чтения конфигурации: {exc}"


def _mark_startup() -> None:
    """След запуска: stdio-сервер иначе невидим, если клиент его не запустил."""
    default = Path(__file__).resolve().parents[2] / ".cache" / "server.log"
    path = Path(os.environ.get("ONE77_LOG", default))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            stamp = datetime.now().isoformat(timespec="seconds")
            handle.write(f"{stamp} pid={os.getpid()} cwd={Path.cwd()}\n")
    except OSError:
        pass


@mcp.tool()
def md_get_form(target: str, kind: str = "", limit: int = 40) -> str:
    """Формы объекта: имена, id, модуль и элементы формы (кнопки, поля, таблицы, группы).

    target — «Справочник.Контрагенты». Элементы читаются из Dialog Stream OLE-источника.
    """
    try:
        config = registry.load()
        obj, error = _find_object(config, kind, target)
        if obj is None:
            return error
        store = get_store(config.source_path) if config.source_kind == "ole" else None
        return forms_card(obj, config.modules_of(obj), store, max(1, limit))
    except Exception as exc:  # noqa: BLE001
        return f"Ошибка чтения конфигурации: {exc}"


@mcp.tool()
def md_export(
    fmt: str = "json",
    kind: str = "",
    detail: bool = False,
    out_path: str = "",
    inline: bool = False,
    max_edges: int = 200,
) -> str:
    """Экспорт конфигурации в файл: json, md (справочник), mermaid (схема связей), sql (DDL).

    kind — ограничить одним видом (document, catalog, …). detail — подробные карточки в md.
    out_path — куда писать (по умолчанию папка export рядом с проектом).
    inline=true добавляет первые 40 строк прямо в ответ.
    """
    try:
        config = registry.load()
        fmt_key = fmt.strip().lower()
        if fmt_key not in EXPORT_FORMATS:
            return f"Неизвестный формат «{fmt}». Доступны: {', '.join(EXPORT_FORMATS)}"
        kind_key = _kind_name(kind)
        if kind and not kind_key:
            return f"Неизвестный вид «{kind}»."

        if fmt_key == "json":
            content, extension = to_json(config), "json"
        elif fmt_key in ("md", "markdown"):
            content, extension = to_markdown(config, kind_key or "", detail), "md"
        elif fmt_key == "mermaid":
            content, extension = to_mermaid(config, max(1, max_edges), kind_key or ""), "mmd"
        else:
            content, extension = to_sql(config), "sql"

        path = write_export(config, extension, content, out_path)
        size_kb = path.stat().st_size / 1024
        head = [
            f"Готово: {path}",
            f"{size_kb:.0f} КБ, {content.count(chr(10)) + 1} строк",
        ]
        if inline:
            preview = "\n".join(content.splitlines()[:40])
            head += ["", preview]
        return "\n".join(head)
    except Exception as exc:  # noqa: BLE001
        return f"Ошибка экспорта: {exc}"


@mcp.tool()
def md_audit(rule: str = "", limit: int = 20) -> str:
    """Аудит конфигурации: битые ссылки, неиспользуемые объекты, дубли синонимов,
    объекты без форм, документы без модуля проведения, объекты без состава.

    rule — одна проверка (broken_refs, unused, duplicate_synonyms, no_forms,
    no_transaction, empty); пусто — все.
    """
    try:
        return run_audit(registry.load(), rule, max(1, limit))
    except Exception as exc:  # noqa: BLE001
        return f"Ошибка аудита: {exc}"


def _numbered(text: str, start_line: int, max_lines: int) -> tuple[list[str], int]:
    lines = text.splitlines()
    total = len(lines)
    first = max(0, start_line - 1)
    chunk = lines[first:first + max_lines]
    return [f"{first + i + 1:>5}  {line}" for i, line in enumerate(chunk)], total


@mcp.tool()
def md_get_module(
    target: str,
    kind: str = "",
    module: str = "",
    start_line: int = 1,
    max_lines: int = 300,
) -> str:
    """Текст модуля с нумерацией строк: глобального, объекта, формы или проведения.

    target — «Документ.Реализация» либо «ГлобальныйМодуль». module — фильтр по типу
    («проведения», «формы списка»), если у объекта несколько модулей.
    start_line / max_lines ограничивают выдачу: большие модули читайте частями.
    """
    try:
        config = registry.load()
        alias = target.strip().lower()
        if alias in ("глобальныймодуль", "глобальный модуль", "global", "globals"):
            modules = [m for m in config.modules if m.owner_kind == "global"]
        else:
            obj, error = _find_object(config, kind, target)
            if obj is None:
                return error
            modules = config.modules_of(obj)
        if module:
            needle = module.strip().lower()
            modules = [m for m in modules if needle in m.title.lower()]
        if not modules:
            return f"У «{target}» нет текста модулей (или такой модуль не найден)."

        chunks = []
        for item in modules:
            body, total = _numbered(item.text, max(1, start_line), max(1, max_lines))
            header = f"### {item.title} — {total} строк"
            chunks.append(header + "\n" + "\n".join(body))
            shown_last = max(1, start_line) + len(body) - 1
            if shown_last < total:
                chunks.append(f"... показано до строки {shown_last}; продолжайте start_line={shown_last + 1}")
        return "\n\n".join(chunks)
    except Exception as exc:  # noqa: BLE001
        return f"Ошибка чтения конфигурации: {exc}"


@mcp.tool()
def md_search_modules(query: str, regex: bool = False, limit: int = 20) -> str:
    """Поиск по текстам всех модулей: возвращает объект, строку и фрагмент кода.

    Обычный поиск идёт по SQLite-индексу (строится при первом обращении), regex — перебором.
    """
    try:
        config = registry.load()
        needle = query.strip()
        if not needle:
            return "Пустой запрос."
        if not regex:
            index = ensure_index(config)
            if index is not None:
                total = index.count_hits(needle)
                if not total:
                    return f"По запросу «{query}» в модулях ничего не найдено."
                rows = index.search_lines(needle, max(1, limit))
                modules = len({row[0] for row in rows})
                head = f"Совпадений: {total}" + (f", показано {len(rows)}" if total > len(rows) else "")
                head += f" (индекс, модулей в выдаче: {modules})"
                body = [
                    f"{owner} [{title}] :{number}: {text.strip()[:160]}"
                    for owner, title, number, text in rows
                ]
                return "\n".join([head, *body])
        return module_search(config, needle, regex, max(1, limit))
    except Exception as exc:  # noqa: BLE001
        return f"Ошибка чтения конфигурации: {exc}"


def main() -> None:
    _mark_startup()
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    mcp.run()


if __name__ == "__main__":
    main()
