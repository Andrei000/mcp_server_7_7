"""Дамп разделов MD в UTF-8 файл для изучения реальной структуры."""
from __future__ import annotations

import io
import sys

import olefile

from probe_md import parse_sections


def main(src: str, out: str, sections: list[str], per_section: int = 2, width: int = 3000) -> None:
    ole = olefile.OleFileIO(src)
    text = ole.openstream('Metadata/Main MetaData Stream').read().decode('cp1251')
    root = parse_sections(text)[0]
    with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
        for item in root:
            if not isinstance(item, list) or not item:
                continue
            name = str(item[0])
            fh.write(f'\n===== SECTION {name} items={len(item) - 1} =====\n')
            if sections and name not in sections:
                continue
            for idx, child in enumerate(item[1:1 + per_section]):
                fh.write(f'--- {name}[{idx}] ---\n')
                fh.write(repr(child)[:width] + '\n')


if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    secs = sys.argv[3].split(',') if len(sys.argv) > 3 else []
    main(src, out, secs)
