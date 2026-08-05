"""Platform-neutral API process entrypoint for hosted preview environments."""

from __future__ import annotations

import os

import uvicorn


def service_port(default: int = 8000) -> int:
    """Return a validated platform port and reject malformed placeholders."""
    raw = os.getenv("PORT", str(default)).strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        raise RuntimeError("PORT must be an integer between 1 and 65535.")
    return int(raw)


def main() -> None:
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=service_port(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
