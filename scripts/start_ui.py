"""Platform-neutral Streamlit entrypoint isolated from backend credentials."""

from __future__ import annotations

import os
import sys


def service_port(default: int = 8501) -> int:
    """Return a validated platform port and reject malformed placeholders."""
    raw = os.getenv("PORT", str(default)).strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        raise RuntimeError("PORT must be an integer between 1 and 65535.")
    return int(raw)


def main() -> None:
    # Hosted UI services must call the API and must never execute backend model
    # work in-process when the API is unavailable.
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
        str(service_port()),
        "--server.headless",
        "true",
        "--client.showErrorDetails",
        "false",
    ]
    os.execv(sys.executable, argv)


if __name__ == "__main__":
    main()
