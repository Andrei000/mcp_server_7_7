"""Точка входа MCP-сервера. Запуск: python run_server.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import onec77_md.bootstrap  # noqa: F401,E402  (настраивает пути к .deps)
from onec77_md.server import main  # noqa: E402

if __name__ == "__main__":
    main()
