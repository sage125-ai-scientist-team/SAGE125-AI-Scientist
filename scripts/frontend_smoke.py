#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/frontend_smoke.py — 前端可启动性 smoke（Streamlit 不白屏）。

运行：py -3 scripts/frontend_smoke.py

流程：设置 MOCK_LLM=true -> 启动 streamlit（headless）-> 轮询首页 -> 关闭进程。
安全：Windows 兼容；不访问外网；不打印 Key。默认超时 30 秒。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PORT = 8531
URL = f"http://127.0.0.1:{PORT}/"


def main() -> int:
    """前端 smoke 主入口。"""
    env = dict(os.environ)
    env["MOCK_LLM"] = "true"
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(PROJECT_ROOT / "app" / "ui" / "streamlit_app.py"),
         "--server.headless", "true", "--server.port", str(PORT)],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
    )
    ok = False
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(URL, timeout=3) as resp:
                    if resp.status == 200:
                        ok = True
                        break
            except Exception:
                time.sleep(1)
    finally:
        proc.terminate()
        try:
            out, _ = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            out = ""
        # 失败时打印日志尾部辅助排查（不含 Key）。
        if not ok and out:
            print("--- streamlit log tail ---")
            print("\n".join(out.splitlines()[-15:]))

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
