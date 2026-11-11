"""CLI: serve по умолчанию, плюс быстрые команды для терминала."""
from __future__ import annotations

import argparse
import os
import sys

from . import bootstrap  # noqa: F401  (настраивает пути к .deps при запуске из исходников)
from .audit.rules import run_audit
from .export.markdown import to_markdown
from .export.mermaid import to_mermaid
from .export.sql_ddl import to_sql
from .export.writer import to_json, write_export
from .formatting import config_summary, module_text, object_card, object_list
from .loader import registry
from .model.entities import resolve_kind


def _config(args) -> "Config":
    path = getattr(args, "path", None)
    if path:
        os.environ["ONE77_MD_PATH"] = path
    return registry.load(path)


def _cmd_info(args) -> int:
    print(config_summary(_config(args)))
    return 0


def _cmd_objects(args) -> int:
    config = _config(args)
    kind = resolve_kind(args.kind) if args.kind else None
    if args.kind and not kind:
        print(f"Неизвестный вид: {args.kind}", file=sys.stderr)
        return 2
    objects = config.of_kind(kind) if kind else config.objects
    if args.mask:
        needle = args.mask.lower()
        objects = [o for o in objects if needle in o.name.lower() or needle in o.synonym.lower()]
    print(object_list(sorted(objects, key=lambda o: (o.kind, o.name.lower()))[: args.limit]))
    return 0


def _cmd_object(args) -> int:
    config = _config(args)
    kind = resolve_kind(args.kind)
    if not kind:
        print(f"Неизвестный вид: {args.kind}", file=sys.stderr)
        return 2
    obj = next((o for o in config.of_kind(kind) if o.name.lower() == args.name.lower()), None)
    if obj is None:
        print(f"{args.name} не найден", file=sys.stderr)
        return 1
    print(object_card(obj, config.modules_of(obj)))
    return 0


def _cmd_module(args) -> int:
    config = _config(args)
    modules = config.modules
    if args.target.lower() in ("global", "глобальныймодуль", "глобальный модуль"):
        modules = [m for m in modules if m.owner_kind == "global"]
    else:
        kind = resolve_kind(args.kind) if args.kind else None
        modules = [m for m in modules if m.owner_kind == kind and m.owner_name.lower() == args.target.lower()]
    if not modules:
        print("Модули не найдены", file=sys.stderr)
        return 1
    for module in modules:
        print(module_text(module))
        print()
    return 0


def _cmd_export(args) -> int:
    config = _config(args)
    fmt = args.fmt.lower()
    if fmt == "json":
        content, ext = to_json(config), "json"
    elif fmt in ("md", "markdown"):
        content, ext = to_markdown(config), "md"
    elif fmt == "mermaid":
        content, ext = to_mermaid(config), "mmd"
    elif fmt == "sql":
        content, ext = to_sql(config), "sql"
    else:
        print(f"Неизвестный формат: {args.fmt}", file=sys.stderr)
        return 2
    path = write_export(config, ext, content, args.out)
    print(path)
    return 0


def _cmd_audit(args) -> int:
    print(run_audit(_config(args), args.rule, args.limit))
    return 0


def _cmd_index(args) -> int:
    import time

    from .index.store import ensure

    config = _config(args)
    started = time.time()
    index = ensure(config, rebuild=True)
    elapsed = time.time() - started
    if index is None:
        print("Индекс недоступен", file=sys.stderr)
        return 1
    print(f"Индекс: {index.path}")
    print(f"Строк модулей: {index.count_lines()}, построен за {elapsed:.1f} с")
    return 0


def build_parser() -> argparse.ArgumentParser:
    default_path = os.environ.get("ONE77_MD_PATH", "")
    parser = argparse.ArgumentParser(
        prog="onec77-md",
        description="Метаданные конфигурации 1С 7.7: MCP-сервер и CLI.",
    )
    parser.add_argument("--path", default=None, help=f"путь к 1Cv7.MD (по умолчанию {default_path or 'ONE77_MD_PATH'})")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="запустить MCP-сервер (stdio)")
    serve.add_argument("--path", default=argparse.SUPPRESS)

    info = sub.add_parser("info", help="сводка по конфигурации")
    info.add_argument("--path", default=argparse.SUPPRESS)

    objects = sub.add_parser("objects", help="список объектов")
    objects.add_argument("--path", default=argparse.SUPPRESS)
    objects.add_argument("--kind", default="")
    objects.add_argument("--mask", default="")
    objects.add_argument("--limit", type=int, default=100)

    obj = sub.add_parser("object", help="карточка объекта")
    obj.add_argument("name")
    obj.add_argument("--path", default=argparse.SUPPRESS)
    obj.add_argument("--kind", required=True)

    module = sub.add_parser("module", help="текст модуля")
    module.add_argument("target")
    module.add_argument("--path", default=argparse.SUPPRESS)
    module.add_argument("--kind", default="")

    export = sub.add_parser("export", help="экспорт конфигурации")
    export.add_argument("--path", default=argparse.SUPPRESS)
    export.add_argument("--fmt", default="json", choices=["json", "md", "mermaid", "sql"])
    export.add_argument("--out", default="")

    audit = sub.add_parser("audit", help="проверки конфигурации")
    audit.add_argument("--path", default=argparse.SUPPRESS)
    audit.add_argument("--rule", default="")
    audit.add_argument("--limit", type=int, default=20)

    index = sub.add_parser("index", help="построить SQLite-индекс для поиска по модулям")
    index.add_argument("--path", default=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "serve"):
        from .server import main as serve_main

        path = getattr(args, "path", None)
        if path:
            os.environ["ONE77_MD_PATH"] = path
        serve_main()
        return 0

    handlers = {
        "info": _cmd_info,
        "objects": _cmd_objects,
        "object": _cmd_object,
        "module": _cmd_module,
        "export": _cmd_export,
        "audit": _cmd_audit,
        "index": _cmd_index,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
