#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/api_smoke.py — API 可启动性 smoke（不发起真实 LLM 调用）。

运行：py -3 scripts/api_smoke.py

流程：启动 uvicorn -> 轮询 /health -> /questions -> /diagnostics -> 关闭进程。
安全：不打印 Key；Windows 兼容；不访问外网。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

# 确保项目根在 sys.path。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PORT = 8021
BASE = f"http://127.0.0.1:{PORT}"


def _get(path: str, timeout: float = 3.0):
    """简单 GET，返回 (status_code, json_or_none)。"""
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None, None


def main() -> int:
    """API smoke 主入口。"""
    # 启动 uvicorn（headless）。
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api.main:app", "--port", str(PORT), "--log-level", "warning"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    summary = {"health": False, "questions": False, "diagnostics": False, "key_leak": False}
    try:
        # 轮询 /health（最多 30 秒）。
        deadline = time.time() + 30
        code = None
        while time.time() < deadline:
            code, data = _get("/health")
            if code == 200:
                summary["health"] = True
                # 检查响应不含明文 Key。
                if "sk-" in json.dumps(data or {}):
                    summary["key_leak"] = True
                break
            time.sleep(1)
        # /questions。
        code, _ = _get("/questions")
        summary["questions"] = code == 200
        # /diagnostics。
        code, _ = _get("/diagnostics")
        summary["diagnostics"] = code == 200
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    ok = summary["health"] and summary["questions"] and summary["diagnostics"] and not summary["key_leak"]
    print("API smoke summary:", json.dumps(summary, ensure_ascii=False))
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
