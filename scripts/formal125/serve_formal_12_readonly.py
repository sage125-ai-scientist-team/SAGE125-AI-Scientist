"""Start Formal 12 read-only API (8050) and UI (8550). Does not stop 8040/8540."""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-port", type=int, default=8050)
    parser.add_argument("--ui-port", type=int, default=8550)
    args = parser.parse_args(argv)

    def _api() -> None:
        import uvicorn

        uvicorn.run("app.api.main:app", host="127.0.0.1", port=args.api_port, reload=False)

    thread = threading.Thread(target=_api, daemon=True)
    thread.start()
    from app.formal125.readonly_ui import serve

    serve(port=args.ui_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
