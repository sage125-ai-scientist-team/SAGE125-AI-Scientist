"""Frozen Formal 125 UI entrypoint. Binds 0.0.0.0:$PORT. Never uses 127.0.0.1 API."""

from __future__ import annotations

import os

import uvicorn

from app.formal125.frozen_demo_ui import create_demo_ui


def service_port() -> int:
    raw = os.getenv("PORT", "").strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        raise RuntimeError("PORT must be an integer between 1 and 65535.")
    return int(raw)


def main() -> None:
    api = os.getenv("SAGE_INTERNAL_API_URL") or os.getenv("API_BASE_URL") or ""
    if "127.0.0.1" in api or "localhost" in api.lower():
        if os.getenv("APP_ENV", "").strip() == "competition_demo" and os.getenv("ALLOW_LOCALHOST_API", "").strip() != "1":
            raise RuntimeError("competition demo UI must not call 127.0.0.1 API")
    os.environ.setdefault("APP_ENV", "competition_demo")
    app = create_demo_ui()
    uvicorn.run(app, host="0.0.0.0", port=service_port(), proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
