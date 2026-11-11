"""Разбор языка 1С 7.7: процедуры, функции, переменные и вызовы.

Никакого исполнения и никакой эвристики «по подстроке»: сначала комментарии и строковые
литералы заменяются пробелами, и только потом ищутся объявления и вызовы. Поэтому
`// ПоискКонтрагента` и `"ПоискКонтрагента"` в выдачу не попадают.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

IDENT = re.compile(r"[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9]*")
PROC = re.compile(
    r"^\s*(?P<kind>Процедура|Функция)\s+(?P<name>[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9]*)"
    r"\s*\((?P<params>[^)]*)\)(?P<tail>.*)$",
    re.IGNORECASE,
)
END_PROC = re.compile(r"^\s*(КонецПроцедуры|КонецФункции)\b", re.IGNORECASE)
VAR = re.compile(r"^\s*Перем\s+(?P<names>[^;]+)", re.IGNORECASE)

# вызов — идентификатор, сразу за которым идёт скобка
CALL = re.compile(r"(?P<name>[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9]*)\s*\(")

# служебные слова, которые не являются вызовами
KEYWORDS = {
    "если", "тогда", "иначе", "иначеесли", "конецесли",
    "пока", "цикл", "конеццикла", "для", "из", "по", "каждого",
    "возврат", "продолжить", "прервать", "попытка", "исключение", "конецпопытки",
    "новый", "перем", "процедура", "функция", "конецпроцедуры", "конецфункции",
    "и", "или", "не", "экспорт",
}


@dataclass
class Symbol:
    name: str
    kind: str  # procedure | function | variable
    line: int
    end_line: int = 0
    params: list[str] = field(default_factory=list)
    is_export: bool = False


@dataclass
class Call:
    caller: str
    callee: str
    line: int


@dataclass
class ParsedModule:
    procedures: list[Symbol] = field(default_factory=list)
    variables: list[Symbol] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)


def strip_noise(text: str) -> str:
    """Заменяет комментарии и строковые литералы пробелами, сохраняя переводы строк."""
    out: list[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    out.append("  ")
                    i += 2
                    continue
                in_string = False
                out.append(" ")
            else:
                out.append("\n" if ch == "\n" else " ")
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(" ")
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _split_params(raw: str) -> list[str]:
    result = []
    for chunk in raw.split(","):
        name = chunk.strip()
        if not name:
            continue
        # «Парам = Значение» в объявлении не встречается, но «Экспорт» бывает в конце
        result.append(name.split("=")[0].strip())
    return result


def parse_module(text: str) -> ParsedModule:
    """Разбирает текст модуля в объявления и вызовы."""
    parsed = ParsedModule()
    current: Symbol | None = None

    for number, line in enumerate(strip_noise(text).splitlines(), start=1):
        match = PROC.match(line)
        if match:
            if current is not None:  # незакрытая процедура — закрываем на всякий случай
                current.end_line = number - 1
            kind = "procedure" if match.group("kind").lower().startswith("процедура") else "function"
            current = Symbol(
                name=match.group("name"),
                kind=kind,
                line=number,
                params=_split_params(match.group("params")),
                is_export="экспорт" in match.group("tail").lower(),
            )
            parsed.procedures.append(current)
        elif END_PROC.match(line):
            if current is not None:
                current.end_line = number
                current = None
        else:
            var = VAR.match(line)
            if var:
                for raw in var.group("names").split(","):
                    name = raw.replace("Экспорт", "").replace("экспорт", "").strip()
                    if name and IDENT.fullmatch(name):
                        parsed.variables.append(
                            Symbol(name=name, kind="variable", line=number, end_line=number)
                        )

        caller = current.name if current else ""
        for call in CALL.finditer(line):
            callee = call.group("name")
            if callee.lower() in KEYWORDS:
                continue
            if current is not None and callee == current.name and call.start() < 40:
                continue  # заголовок самой процедуры
            parsed.calls.append(Call(caller=caller, callee=callee, line=number))

    if current is not None:
        current.end_line = len(text.splitlines())
    return parsed
