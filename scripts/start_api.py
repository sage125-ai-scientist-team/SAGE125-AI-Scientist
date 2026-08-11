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

    返回：
        满足任一条件即为 True：
        - `SAGE125_PREVIEW_SEED` 为真；
        - `APP_ENV=preview`（Render Blueprint 已有）；
        - `PREVIEW_EPHEMERAL_STORAGE` 为真。
    """
    seed = os.getenv("SAGE125_PREVIEW_SEED", "").strip().lower() in {"1", "true", "yes", "on"}
    app_env = os.getenv("APP_ENV", "").strip().lower() == "preview"
    ephemeral = os.getenv("PREVIEW_EPHEMERAL_STORAGE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return seed or app_env or ephemeral


def ensure_preview_questions() -> None:
    """
    在 API 进程启动前确保 questions_125.json 可用。

    行为：
        - 正式环境：若已有题库则复用；有 booklet 则抽取；
        - Preview：`APP_ENV=preview` / 临时存储 / `SAGE125_PREVIEW_SEED=1`
          时允许写入显式标记的 preview seed，避免 UI Questions=0；
        - 若无法准备题库：记录错误但不阻断进程启动（/health 仍可响应），
          以便冷启动诊断；业务 `/questions` 会如实返回 missing。
    """
    try:
        from scripts.bootstrap_preview_data import bootstrap
    except Exception as exc:  # noqa: BLE001 — 启动入口必须容错
        print(f"[start_api] bootstrap import failed: {exc}")
        return
    code = bootstrap(allow_seed=_preview_seed_allowed(), force_seed=False)
    if code != 0:
        print(f"[start_api] questions bootstrap exited with code {code}")


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
