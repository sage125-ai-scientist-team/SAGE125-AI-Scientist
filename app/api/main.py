"""
app.api.main —— FastAPI 应用入口。

通过 create_app() 组装应用并挂载路由；模块级 app 变量供 uvicorn 启动：
    uvicorn app.api.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import setup_logging

# 项目版本，用于 OpenAPI 文档展示。
from app import __version__


def create_app() -> FastAPI:
    """
    应用工厂：初始化日志、创建 FastAPI 实例并挂载路由与 CORS。

    返回：
        组装完成的 FastAPI 应用实例。
    """
    # 依据配置初始化统一日志（含 API Key 脱敏过滤器）。
    settings = get_settings()
    setup_logging(settings.log_level)

    # 创建应用并声明基础元信息。
    application = FastAPI(
        title="SAGE125-AI-Scientist",
        description="面向赛道 A『科学假设生成与研究计划设计』的 AI Scientist 原型 API。",
        version=__version__,
    )
    # 仅允许显式配置的本地 Streamlit origin，避免把本地 API 暴露给任意网页。
    allowed_origins = [x.strip() for x in settings.cors_allow_origins.split(",") if x.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def reject_oversized_upload_request(request: Request, call_next):
        """在 multipart 解析前按 Content-Length 拒绝明显超限的上传请求。"""
        if request.url.path == "/ingest" and request.method.upper() == "POST":
            raw_length = request.headers.get("content-length", "")
            if raw_length.isdigit():
                # 为 multipart 边界和每个文件头预留 1 MiB；文献内容本身仍由 LibraryManager
                # 精确执行单文件/批次上限。
                hard_limit = settings.library_max_batch_mb * 1024 * 1024 + 1024 * 1024
                if int(raw_length) > hard_limit:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "status": "failed",
                            "message": f"上传请求超过 {settings.library_max_batch_mb} MB 批次上限。",
                        },
                    )
        return await call_next(request)

    # 挂载业务路由。
    application.include_router(router)
    return application


# 模块级应用实例：uvicorn 的启动目标。
app = create_app()
