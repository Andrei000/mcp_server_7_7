# onec77-md-mcp

MCP-сервер метаданных конфигурации **1С:Предприятие 7.7**. Читает `1Cv7.MD` напрямую
(OLE-контейнер, без Конфигуратора и COM) и отдаёт агенту структуру конфигурации:
справочники, документы, регистры, перечисления, константы, журналы, отчёты, обработки —
с реквизитами, табличными частями, типами и ссылками.

Только чтение: файлы базы не изменяются.

## Быстрый старт

```bash
pip install .
export ONE77_MD_PATH=/path/to/base          # Windows: set ONE77_MD_PATH=D:\base
onec77-md info                               # сводка по конфигурации
onec77-md objects --kind document            # список документов
onec77-md serve                              # MCP-сервер по stdio
```

Подключение к Claude Desktop / Cursor:

```json
{
  "mcpServers": {
    "onec77md": {
      "command": "onec77-md",
      "args": ["serve"],
      "env": { "ONE77_MD_PATH": "/path/to/base/1Cv7.MD" }
    }
  }
}
```

Путь может быть файлом `1Cv7.MD`, каталогом базы или каталогом текстовой выгрузки —
тип источника определяется автоматически.

## Что умеет

| Инструмент | Назначение |
|---|---|
| `md_config_info` | имя конфигурации, источник, количество объектов и модулей |
| `md_list_objects` | список объектов с фильтром по виду и подстроке имени |
| `md_get_object` | карточка: реквизиты шапки, ТЧ, значения перечисления, формы, модули |
| `md_find` | поиск по имени/синониму/комментарию объектов и по реквизитам |
| `md_get_attribute` | один реквизит: тип, длина, точность, ссылка |
| `md_get_module` | текст модуля с нумерацией строк (глобальный, объекта, формы, проведения) |
| `md_search_modules` | поиск по текстам всех модулей с объектом и номером строки |
| `md_get_form` | формы объекта: имена, id, модуль и элементы формы (кнопки, поля, таблицы) |
| `md_export` | экспорт в файл: `json`, `md` (справочник), `mermaid` (схема связей), `sql` (DDL) |
| `md_audit` | проверки: битые ссылки, неиспользуемые, дубли синонимов, пустые объекты |

Виды объектов понимаются и по-английски, и по-русски: `catalog`/`справочник`,
`document`/`документ`, `register`/`регистр`, `enum`/`перечисление`, `const`/`константа`,
`journal`/`журнал`, `report`/`отчёт`, `processing`/`обработка`, `calendar`/`календарь`.

## Источники

Источник определяется по пути автоматически:

| Что подано | Как читается |
|---|---|
| файл `1Cv7.MD` или каталог базы, где он лежит | OLE2-контейнер |
| каталог с `*.md`-файлами (выгрузка «Конфигурация → Выгрузить в файлы») | текстовое дерево, файлы склеиваются |
| одиночный текстовый `*.md` | текстовое дерево |

В текстовой выгрузке модулей нет — там только описание метаданных; `md_config_info` честно
показывает тип источника. Кодировка файлов определяется сама (UTF-8, затем CP1251/CP866).

## Модули и формы

Модули лежат в OLE-стримах `MD Programm text` (raw deflate; в части версий — zlib с заголовком,
поэтому пробуются оба варианта). На базе Rain это 941 стрим, из них непустых — 457 модулей
на 201 667 строк:

| Что | Стрим | Сколько |
|---|---|---|
| Глобальный модуль | `TypedText/ModuleText_Number1` | 1 (17 240 строк) |
| Модуль проведения | `TypedText/Transact_Number<id документа>` | 50 |
| Модуль формы документа | `Document/Document_Number<id>` | 53 |
| Модуль отчёта | `Report/Report_Number<id>` | 104 |
| Модуль обработки | `CalcVar/CalcVar_Number<id>` | 149 |
| Модуль формы списка | `SubList/SubList_Number<id формы>` | 48 |
| Модуль формы элемента | `SubFolder/SubFolder_Number<id справочника>` | 6 |
| Модуль формы субконто | `Subconto/Subconto_Number<id справочника>` | 46 |

`UserHelp_*` (360 стримов) — тексты справки, к модулям не относятся и пропускаются.

### Разметка формы

Формы 7.7 оказались не бинарным монолитом: `Container.Contents` — текстовый манифест потоков
формы, а `Dialog Stream` — такое же дерево `{...}`, как MD. Поэтому из формы читаются элементы:

```
Справочник.Контрагенты — формы (2):
  - ФормаСписка, id 1158, модуль: 486 строк
    элементов: 14
      · STATIC «Телефон:» 18,190 33×9
      · BUTTON «Выход» 397,203 44×15 обработчик: #Закрыть
      · BUTTON «Счета» 18,203 44×15 обработчик: ОткрытьФорму("Справочник.РасчетныеСчета.ФормаСписка",)
      · CHECKBOX «- активность клиента» 194,222 93×10 обработчик: ПриИзмененииАктивности()
```

У элемента берутся класс (`BUTTON`, `STATIC`, `1CEDIT`, `COMBOBOX`, `TABLE`, `1CGROUPBOX`,
`CHECKBOX`), подпись, координаты и размеры, обработчик или привязанный реквизит, тип.
Не разбираются страницы `Page.1`/`Page.2` — это Moxcel-таблицы на форме, отдельный формат.

## Индекс

Поиск по модулям идёт через SQLite-индекс: строки модулей складываются в таблицу `lines`,
поиск — `LIKE` по ней. На Rain это 201 367 строк, 38 МБ, построение 0,6 с, поиск 0,09 с
(перебор по Python — около 1,5 с).

```
onec77-md index            # построить/перестроить
```

Индекс лежит в `%LOCALAPPDATA%\onec77-md\cache` (переопределяется `ONE77_CACHE_DIR`) и
привязан к отпечатку базы: путь, размер, число объектов и модулей. Если индекс построить
нельзя, поиск молча откатывается на перебор — инструмент не падает.

## Экспорт и аудит

`md_export(fmt, kind, detail, out_path, inline)` пишет файл в `export/` (или в `out_path`) и
возвращает путь и размер. Форматы:

| Формат | Что внутри | Размер на Rain |
|---|---|---|
| `json` | полная модель: объекты, реквизиты, ТЧ, перечисления, формы, метаданные модулей | 1,0 МБ |
| `md` | справочник по видам: таблицы объектов; `detail=true` — ещё и реквизиты | 49 КБ |
| `mermaid` | `flowchart` связей: объекты по видам, стрелки по ссылочным реквизитам | 15 КБ |
| `sql` | DDL: `SC<id>`, `DH<id>`+`DT<id>`, `RG<id>` с реквизитами | 104 КБ |

`md_audit(rule, limit)` гоняет шесть проверок: `broken_refs`, `unused`, `duplicate_synonyms`,
`no_forms`, `no_transaction`, `empty`. Результат на базе Rain:

```
Битые ссылки — 0
Неиспользуемые объекты — 211
Одинаковые синонимы — 2
Объекты без форм и модулей — 0
Документы без модуля проведения — 3
Объекты без состава — 18
```

«Неиспользуемые» — эвристика: нет входящих ссылок и имя не встречается в текстах модулей;
журналы и отчёты могут попадать туда ложно, о чём отчёт честно предупреждает.

## Установка

```bash
# из исходников
pip install .

# или собрать wheel и поставить его
pip wheel . -w dist
pip install dist/onec77_md_mcp-0.3.0-py3-none-any.whl
```

Ставится консольная команда `onec77-md` и тот же код доступен как `python -m onec77_md`.
Зависимости (`mcp`, `olefile`, на Windows ещё `pywin32`) подтягиваются автоматически.

```bash
onec77-md --path /path/to/base info        # сводка
onec77-md objects --kind document --mask Акт   # список
onec77-md object --kind document АктНесоответствия  # карточка
onec77-md module ГлобальныйМодуль          # текст модуля
onec77-md export --fmt md --out ./out      # экспорт
onec77-md audit --rule unused              # проверки
onec77-md index --path /path/to/base       # SQLite-индекс для поиска
onec77-md serve                            # MCP-сервер (stdio)
```

Путь к базе берётся из `--path`, иначе из `ONE77_MD_PATH`.

## Запуск из исходников

Без установки, если зависимости лежат в `.deps`:

```powershell
$env:ONE77_MD_PATH = 'D:\base\1Cv7.MD'
python D:\DSH\onec77-md-mcp\run_server.py
```

`ONE77_MD_PATH` задаёт базу по умолчанию; путь можно передавать в `md_config_info(path=...)`.

## Зависимости

Лежат локально в `.deps` (ставились `pip install --target`): `mcp`, `olefile`, `pywin32`.
`run_server.py` сам добавляет `.deps` и модули pywin32 в пути импорта (`src/onec77_md/bootstrap.py`),
поэтому глобальных установок не требуется. Другой каталог зависимостей задаётся `ONE77_DEPS_DIR`.

## Подключение в DSH

В профиль (`~/.dsh/profiles/desktop/cordis.patch.yml`) добавляется блок `- insert:` —
top-level запись `- id: ...` в патче работает только как override существующего плагина,
новый сервер она не добавляет:

```yaml
- insert:
    - id: mcp-onec77-md
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: onec77md
        transport: stdio
        command: 'C:\Users\Andrey\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
        args:
          - 'D:\DSH\onec77-md-mcp\run_server.py'
        cwd: 'D:\DSH\onec77-md-mcp'
        env:
          ONE77_MD_PATH: 'D:\DSH\Projects\Rain\1Cv7.MD'
        toolCallTimeoutMs: 120000
```

Инструменты появляются как `mcp__onec77md__md_*`. Проверить, что сервер поднялся, можно по
файлу `.cache/server.log` — он пишется при каждом старте процесса.

## Claude Desktop / Cursor

После `pip install` достаточно консольной команды. На Windows укажите полный путь к `.exe`
(его печатает `where onec77-md`), потому что GUI-приложения не видят `PATH` из терминала —
путь в примере ниже замените на свой:

```json
{
  "mcpServers": {
    "onec77md": {
      "command": "C:\\Users\\Andrey\\AppData\\Local\\Programs\\Python\\Python312\\Scripts\\onec77-md.exe",
      "args": ["serve"],
      "env": { "ONE77_MD_PATH": "D:\\DSH\\Projects\\Rain\\1Cv7.MD" }
    }
  }
}
```

Без установки тот же сервер запускается из исходников:

```json
{
  "mcpServers": {
    "onec77md": {
      "command": "C:\\Users\\Andrey\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe",
      "args": ["D:\\DSH\\onec77-md-mcp\\run_server.py"],
      "env": { "ONE77_MD_PATH": "D:\\DSH\\Projects\\Rain\\1Cv7.MD" }
    }
  }
}
```

## Как это работает

1. `1Cv7.MD` — OLE2-контейнер. Поток `Metadata/Main MetaData Stream` — текст CP1251
   с деревом секций `{a,b,{c,d}}`.
2. `parsing/sections.py` разбирает дерево в вложенные списки (без `eval`).
3. `model/mapping.py` раскладывает секции (`SbCnts`, `Documents`, `Registers`, `EnumList`, …)
   в `MdObject`/`Field`, разрешая ссылки по id таблиц (`B`→справочник, `O`→документ, `E`→перечисление).
4. `server.py` отдаёт модель через MCP (stdio).

Загрузка базы Rain (671 объект, 16 МБ) занимает ~0.1 с; кэш держится по mtime и размеру файла.

## Тесты

```bash
python -m unittest discover -s tests -v
```

Тесты парсера синтетические; тесты модели, форм и индекса проверяются на реальной базе
и пропускаются, если `1Cv7.MD` недоступен (путь задан в `tests/*.py`).

## Ограничения текущей версии

- Страницы формы `Page.1`/`Page.2` (Moxcel-таблицы) не разбираются — только `Dialog Stream`
  с элементами. Вложенность групп в разметке не восстанавливается: элементы идут плоским списком.
- В текстовой выгрузке нет модулей — только описание метаданных.
- Экспорт `sql` — приблизительный: имена таблиц и колонок по конвенции платформы, сверяйте с базой.

## Структура

```
pyproject.toml           пакет onec77-md-mcp, команда onec77-md
run_server.py            точка входа без установки
src/onec77_md/
  bootstrap.py           пути к .deps и pywin32
  cli.py                 serve / info / objects / object / module / export / audit / index
  loader.py              загрузка и кэш конфигурации
  parsing/sections.py    разбор дерева MD
  sources/ole.py         чтение OLE-контейнера
  sources/text.py        текстовая выгрузка
  sources/detect.py      автоопределение источника
  model/entities.py      модель (Config, MdObject, Field, Module)
  model/mapping.py       секции MD -> модель
  model/modules.py       стримы модулей -> владельцы
  forms/layout.py        разбор Container.Contents и Dialog Stream
  forms/store.py         ленивое чтение разметки форм
  index/store.py         SQLite-индекс строк модулей
  formatting.py          текстовые ответы для агента
  export/writer.py       json + запись файлов
  export/markdown.py     справочник в Markdown
  export/mermaid.py      схема связей
  export/sql_ddl.py      DDL по метаданным
  audit/rules.py         проверки конфигурации
  server.py              MCP-инструменты
tests/                   тесты (core, cli, sources, forms, index)
tools/                   разведочные скрипты (probe_md, dump_sections, mcp_probe)
```
