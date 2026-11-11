"""Проверка MCP-сервера по stdio: initialize -> tools/list -> tools/call."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def send(proc: subprocess.Popen, payload: dict) -> None:
    proc.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
    proc.stdin.flush()


def read_message(proc: subprocess.Popen, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("сервер закрыл stdout")
        text = line.decode("utf-8").strip()
        if text:
            return json.loads(text)
    raise TimeoutError("нет ответа")


def main() -> int:
    proc = subprocess.Popen(
        [PY, str(ROOT / "run_server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(ROOT),
    )
    try:
        send(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "probe", "version": "0.0.1"},
            },
        })
        init = read_message(proc)
        print("INIT:", json.dumps(init, ensure_ascii=False)[:400])

        send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = read_message(proc)
        names = [t["name"] for t in tools.get("result", {}).get("tools", [])]
        print("TOOLS:", names)

        send(proc, {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "md_config_info", "arguments": {}},
        })
        info = read_message(proc)
        print("CALL:", json.dumps(info, ensure_ascii=False)[:600])

        send(proc, {
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "md_get_object", "arguments": {"kind": "document", "name": "АктНесоответствия"}},
        })
        card = read_message(proc)
        text = card.get("result", {}).get("content", [{}])[0].get("text", "")
        print("OBJECT:", text[:500])
        return 0
    finally:
        proc.kill()
        err = proc.stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print("STDERR:", err[-1500:])


if __name__ == "__main__":
    raise SystemExit(main())
