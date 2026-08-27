"""Platform-neutral API process entrypoint for hosted preview environments."""

from __future__ import annotations

import os

import uvicorn


def service_port(default: int = 8000) -> int:
    """
    Return a validated platform port and reject malformed placeholders.

    参数：
        default: PORT 缺失时的默认端口。

    返回：
        合法端口整数（1–65535）。

    异常：
        RuntimeError: PORT 非数字或越界。
    """
    raw = os.getenv("PORT", str(default)).strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        raise RuntimeError("PORT must be an integer between 1 and 65535.")
    return int(raw)


def _preview_seed_allowed() -> bool:
    """
    判断 API 启动时是否允许 preview seed。

    仅 development + ``SAGE125_ALLOW_PREVIEW_SEED`` 为真。
    """
    from app.catalog.official import allow_preview_seed

    return allow_preview_seed()


def ensure_preview_questions() -> None:
    """
    在 API 进程启动前绑定官方 125 题 Catalog。

    正式 / preview / staging 只使用打包的官方映射。
    Preview Seed 不得在这些环境自动写入。
    """
    try:
        from app.api.preview_catalog import ensure_preview_catalog

        path = ensure_preview_catalog()
        if path is None:
            print("[start_api] official catalog unavailable; questions API will fail closed")
    except Exception as exc:  # noqa: BLE001 — 启动入口必须容错
        print(f"[start_api] catalog bind failed: {exc}")


def main() -> None:
    """
    启动 FastAPI（uvicorn）。

    步骤：
        1. 尝试引导题库；
        2. 绑定 0.0.0.0 与平台 PORT。
    """
    ensure_preview_questions()
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=service_port(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
