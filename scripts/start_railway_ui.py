"""Railway Streamlit entrypoint isolated from backend model credentials."""

from __future__ import annotations

import os
import sys


def railway_port(default: int = 8501) -> int:
    raw = os.getenv("PORT", str(default)).strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        raise RuntimeError("PORT must be an integer between 1 and 65535.")
    return int(raw)


def main() -> None:
    os.environ.setdefault("FRONTEND_RUN_VIA_API", "1")
    argv = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app/ui/streamlit_app.py",
        "--server.address",
        "0.0.0.0",
        "--server.port",
        str(railway_port()),
        "--server.headless",
        "true",
    ]
    os.execv(sys.executable, argv)


if __name__ == "__main__":
    main()
