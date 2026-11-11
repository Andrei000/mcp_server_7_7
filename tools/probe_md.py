"""Одноразовый разведчик формата 1Cv7.MD: печатает дерево стримов и верхние секции."""
from __future__ import annotations

import sys
from collections import Counter

import olefile


def parse_sections(text: str):
    """Разбирает {a,b,{c,d}} в вложенные списки. Строки в кавычках сохраняются как есть."""
    stack = [[]]
    i, n = 0, len(text)
    buf = []
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    buf.append('"')
                    i += 2
                    continue
                in_str = False
                stack[-1].append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        else:
            if ch == '"':
                in_str = True
                buf = []
            elif ch == '{':
                stack.append([])
            elif ch == '}':
                node = stack.pop()
                stack[-1].append(node)
            elif ch == ',':
                pass
            else:
                buf.append(ch)
        i += 1
    return stack[0]


def main(path: str, dump_section: str | None = None) -> None:
    ole = olefile.OleFileIO(path)
    streams = ole.listdir()
    print(f'streams: {len(streams)}')
    for e in streams[:40]:
        print('  ', '/'.join(e), ole.get_size(e))
    blob = ole.openstream('Metadata/Main MetaData Stream').read() if ole.exists('Metadata/Main MetaData Stream') else None
    if blob is None:
        print('NO Main MetaData Stream')
        return
    print(f'md stream size: {len(blob)}')
    for enc in ('cp1251', 'cp866', 'utf-8'):
        try:
            text = blob.decode(enc)
            print(f'decoded as {enc}: ok, {len(text)} chars')
            break
        except UnicodeDecodeError as exc:
            print(f'decoded as {enc}: FAIL {exc}')
    root = parse_sections(text)[0]
    print('root type:', type(root).__name__, 'len', len(root))
    counters = Counter()
    for item in root:
        if isinstance(item, list) and item:
            counters[str(item[0])] += 1
    print('top sections:', dict(counters))
    if dump_section:
        for item in root:
            if isinstance(item, list) and item and str(item[0]) == dump_section:
                stats = Counter(str(x[0]) for x in item[1:] if isinstance(x, list))
                print(f'{dump_section}: {len(item) - 1} children, kinds={dict(stats)}')
                for child in item[1:4]:
                    print(repr(child)[:1200])
                break


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
