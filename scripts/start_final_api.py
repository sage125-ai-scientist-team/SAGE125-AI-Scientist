"""Frozen Formal 125 API entrypoint. Binds 0.0.0.0:$PORT. No provider calls."""

from __future__ import annotations

import os

import uvicorn

from app.formal125.frozen_demo import create_demo_api


def service_port() -> int:
    raw = os.getenv("PORT", "").strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        raise RuntimeError("PORT must be an integer between 1 and 65535.")
    return int(raw)


def main() -> None:
    os.environ.setdefault("APP_ENV", "competition_demo")
    os.environ.setdefault("DEMO_MODE", "FROZEN_RELEASE_CANDIDATE")
    os.environ.setdefault("FORMAL_125_READ_ONLY", "true")
    os.environ.setdefault("ALLOW_PUBLIC_ACTUAL_RUN", "false")
    os.environ.setdefault("ALLOW_PUBLIC_PROVIDER_CALL", "false")
    app = create_demo_api()
    uvicorn.run(app, host="0.0.0.0", port=service_port(), proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
