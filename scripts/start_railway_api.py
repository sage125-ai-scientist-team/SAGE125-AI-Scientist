"""Railway API process entrypoint with an explicit host and platform port."""

from __future__ import annotations

import os

import uvicorn


def railway_port(default: int = 8000) -> int:
    """Return a validated Railway PORT without accepting invalid placeholders."""
    raw = os.getenv("PORT", str(default)).strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        raise RuntimeError("PORT must be an integer between 1 and 65535.")
    return int(raw)


def main() -> None:
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=railway_port(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
