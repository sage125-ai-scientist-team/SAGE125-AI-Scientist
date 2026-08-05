"""
app.core.config —— 类型化应用配置与模型安全校验。

基于 pydantic-settings，从项目根目录的 .env 加载配置并提供强类型访问。

关键能力：
    - 当 WORKSPACE_ID 已配置但 base_url 仍含占位符“你的WorkspaceId”时自动替换；
    - 提供 qwen_configured / deep_research_configured / openalex_configured 三个 property；
    - 提供 mask_secret() 掩码函数（仅显示前 4 位与后 4 位）；
    - 提供 assert_qwen_model()，仅允许 qwen* 或 text-embedding-v4 / qwen3-rerank，
      检测到 deepseek/kimi/glm/claude/gpt/gemini/minimax 等直接 raise ValueError。

安全约束：严禁在任何地方打印完整 API Key。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：本文件位于 <root>/app/core/config.py，上溯三级为根。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# .env 的绝对路径，供 pydantic-settings 加载。
ENV_FILE = PROJECT_ROOT / ".env"

# base_url 模板中使用的占位符，配置真实 WORKSPACE_ID 后应被替换。
_WORKSPACE_PLACEHOLDER = "你的WorkspaceId"

_INVALID_CONFIGURATION_VALUES = {
    "todo",
    "placeholder",
    "your_key",
    "your-key",
    "your_workspace_id",
    "your-workspace-id",
    _WORKSPACE_PLACEHOLDER.casefold(),
}


def _is_configured_value(value: str | None) -> bool:
    """Reject empty, padded, and well-known placeholder configuration values."""
    if not isinstance(value, str) or not value:
        return False
    if value != value.strip():
        return False
    return value.casefold() not in _INVALID_CONFIGURATION_VALUES

# 明确禁用的非千问生成模型关键字（小写匹配），命中即拒绝。
FORBIDDEN_MODEL_KEYWORDS: tuple[str, ...] = (
    "gpt",       # OpenAI GPT
    "o1", "o3",  # OpenAI o 系列
    "claude",    # Anthropic
    "gemini",    # Google
    "deepseek",  # DeepSeek
    "kimi",      # Moonshot
    "glm",       # 智谱
    "minimax",   # MiniMax
)

# 例外允许的非 qwen 前缀模型（向量与重排序），属于千问生态且安全。
_EXPLICITLY_ALLOWED_MODELS: tuple[str, ...] = (
    "text-embedding-v4",
    "text-embedding-v3",
    "qwen3-rerank",
)


def mask_secret(value: str | None) -> str:
    """
    将敏感字符串掩码为“前 4 位 + **** + 后 4 位”的安全展示形式。

    参数：
        value: 原始敏感字符串（可能为 None 或空）。

    返回：
        "未配置"（空值）/ 全遮蔽（过短）/ "前4位****后4位"（常规）三种之一。
    """
    # 空值统一提示未配置，避免误导。
    if not value:
        return "未配置"
    # 过短的密钥全遮蔽，防止泄露其全部内容。
    if len(value) <= 8:
        return "*" * len(value)
    # 常规值仅暴露首尾各 4 位，中间以 **** 代替。
    return f"{value[:4]}****{value[-4:]}"


def assert_qwen_model(model_name: str) -> str:
    """
    断言给定模型名满足“仅千问”安全约束，否则抛出 ValueError。

    允许：
        - 以 "qwen" 开头（不区分大小写）的生成/嵌入/重排序模型；
        - 显式白名单：text-embedding-v4 / text-embedding-v3 / qwen3-rerank。
    拒绝：
        - 名称包含 deepseek/kimi/glm/claude/gpt/gemini/minimax 等关键字。

    参数：
        model_name: 待校验的模型名称。

    返回：
        合规的模型名称原值（便于链式使用）。

    异常：
        ValueError: 当模型名称为空或不满足“仅千问”约束时抛出。
    """
    # 空名称直接判为非法。
    if not model_name:
        raise ValueError("模型名称为空，禁止调用。")
    # 统一小写后匹配，避免大小写绕过。
    name = model_name.lower()
    # 命中任一禁用关键字即拒绝（明确列出常见非千问厂商）。
    for keyword in FORBIDDEN_MODEL_KEYWORDS:
        if keyword in name:
            raise ValueError(
                f"检测到非千问模型 '{model_name}'（含关键字 '{keyword}'），"
                "违反安全约束：仅允许 Qwen/千问模型。"
            )
    # 显式白名单（向量与重排序）直接放行。
    if name in _EXPLICITLY_ALLOWED_MODELS:
        return model_name
    # 其余必须以 qwen 前缀开头。
    if not name.startswith("qwen"):
        raise ValueError(
            f"非法模型 '{model_name}'：仅允许以 'qwen' 开头或 "
            f"{list(_EXPLICITLY_ALLOWED_MODELS)} 之一。"
        )
    return model_name


class BailianRuntimeConfig(BaseModel):
    """Server-only normalized Alibaba Cloud Model Studio configuration."""

    provider: str
    region: str
    workspace_id: str
    api_key: str
    base_url: str
    chat_model: str
    embedding_model: str
    request_timeout: float
    max_retries: int
    configured: bool
    configuration_error: str | None


class Settings(BaseSettings):
    """
    应用配置模型：字段与 .env 键一一对应（通过 alias 映射大写环境变量名）。

    使用方式：
        from app.core.config import get_settings
        settings = get_settings()
        settings.dashscope_api_key  # 类型化访问
    """

    # pydantic-settings 行为：从 .env 读取、忽略多余键、大小写不敏感、允许 alias 填充。
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # ---- 阿里云百炼 / DashScope ----
    llm_provider: str = Field(default="bailian", alias="LLM_PROVIDER")
    dashscope_region: str = Field(default="cn-beijing", alias="DASHSCOPE_REGION")
    dashscope_api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    workspace_id: str = Field(default="", alias="WORKSPACE_ID")
    dashscope_base_url: str = Field(default="", alias="DASHSCOPE_BASE_URL")

    # ---- Qwen 聊天模型（必须为千问）----
    qwen_fast_model: str = Field(default="qwen3.6-flash", alias="QWEN_FAST_MODEL")
    qwen_balanced_model: str = Field(default="qwen3.7-plus", alias="QWEN_BALANCED_MODEL")
    qwen_strong_model: str = Field(default="qwen3.7-max", alias="QWEN_STRONG_MODEL")

    # ---- Qwen Deep Research（走原生 dashscope SDK）----
    qwen_deep_research_model: str = Field(
        default="qwen-deep-research", alias="QWEN_DEEP_RESEARCH_MODEL"
    )
    dashscope_deep_research_base_url: str = Field(
        default="", alias="DASHSCOPE_DEEP_RESEARCH_BASE_URL"
    )

    # ---- RAG：百炼向量与重排序 ----
    embedding_backend: str = Field(default="bailian", alias="EMBEDDING_BACKEND")
    bailian_embedding_model: str = Field(
        default="text-embedding-v4", alias="BAILIAN_EMBEDDING_MODEL"
    )
    bailian_rerank_model: str = Field(default="qwen3-rerank", alias="BAILIAN_RERANK_MODEL")

    # ---- 可选：本地 Qwen3 Embedding / Reranker（默认不启用）----
    local_qwen_embedding_model: str = Field(
        default="Qwen/Qwen3-Embedding-0.6B", alias="LOCAL_QWEN_EMBEDDING_MODEL"
    )
    local_qwen_rerank_model: str = Field(
        default="Qwen/Qwen3-Reranker-0.6B", alias="LOCAL_QWEN_RERANK_MODEL"
    )

    # ---- 文献 API ----
    arxiv_base_url: str = Field(
        default="https://export.arxiv.org/api/query", alias="ARXIV_BASE_URL"
    )
    arxiv_request_interval_seconds: float = Field(
        default=3.0, alias="ARXIV_REQUEST_INTERVAL_SECONDS"
    )
    openalex_api_key: str = Field(default="", alias="OPENALEX_API_KEY")
    crossref_base_url: str = Field(
        default="https://api.crossref.org", alias="CROSSREF_BASE_URL"
    )
    contact_email: str = Field(default="", alias="CONTACT_EMAIL")

    # ---- LLM 调用鲁棒性（超时 / 重试）----
    # 流式 Qwen 请求的读取超时；收到任一 chunk 后会重新计时。
    llm_timeout_seconds: float = Field(default=180.0, alias="LLM_TIMEOUT_SECONDS")
    # TCP/TLS 建连应快速失败，避免错误网络出口等待十分钟。
    llm_connect_timeout_seconds: float = Field(default=20.0, alias="LLM_CONNECT_TIMEOUT_SECONDS")
    # SDK 自动重试关闭；客户端只对可恢复错误执行此处配置的有限重试。
    llm_max_retries: int = Field(default=1, ge=0, le=2, alias="LLM_MAX_RETRIES")
    # 限制单个 Agent 输出，避免默认思考模式产生数万 token 与 300 秒超时。
    llm_max_output_tokens: int = Field(default=8192, ge=256, le=65536, alias="LLM_MAX_OUTPUT_TOKENS")
    # 点击真实模式时的轻量连通性探测超时。
    qwen_probe_timeout_seconds: float = Field(default=20.0, ge=3.0, le=60.0, alias="QWEN_PROBE_TIMEOUT_SECONDS")
    # 可选企业/VPN HTTPS 代理；为空时沿用系统 HTTP(S)_PROXY。
    outbound_https_proxy: str = Field(default="", alias="OUTBOUND_HTTPS_PROXY")
    # DeepResearch 流式长任务超时（秒）。
    deep_research_timeout_seconds: float = Field(default=900.0, alias="DEEP_RESEARCH_TIMEOUT_SECONDS")

    # ---- 应用配置 ----
    app_env: str = Field(default="development", alias="APP_ENV")
    preview_ephemeral_storage: bool = Field(
        default=False, alias="PREVIEW_EPHEMERAL_STORAGE"
    )
    export_dir: str = Field(default="exports", alias="EXPORT_DIR")
    data_dir: str = Field(default="data", alias="DATA_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_allow_origins: str = Field(
        default="http://127.0.0.1:8501,http://localhost:8501",
        alias="CORS_ALLOW_ORIGINS",
    )
    max_upload_mb: int = Field(default=25, ge=1, le=200, alias="MAX_UPLOAD_MB")
    # 永久本地文献库的资源上限。所有入口（HTTP 与进程内 fallback）共用这些限制，
    # 防止大量文献、向量或临时上传耗尽内存与磁盘。
    library_max_batch_files: int = Field(
        default=10, ge=1, le=100, alias="LIBRARY_MAX_BATCH_FILES"
    )
    library_max_batch_mb: int = Field(
        default=100, ge=1, le=2048, alias="LIBRARY_MAX_BATCH_MB"
    )
    library_max_files: int = Field(
        default=500, ge=1, le=100000, alias="LIBRARY_MAX_FILES"
    )
    library_max_raw_mb: int = Field(
        default=2048, ge=25, le=102400, alias="LIBRARY_MAX_RAW_MB"
    )
    library_max_index_mb: int = Field(
        default=4096, ge=25, le=204800, alias="LIBRARY_MAX_INDEX_MB"
    )
    library_max_chunks: int = Field(
        default=100000, ge=100, le=5000000, alias="LIBRARY_MAX_CHUNKS"
    )
    library_max_chunks_per_file: int = Field(
        default=5000, ge=10, le=100000, alias="LIBRARY_MAX_CHUNKS_PER_FILE"
    )
    library_min_free_mb: int = Field(
        default=5120, ge=0, le=1024000, alias="LIBRARY_MIN_FREE_MB"
    )
    library_min_free_percent: float = Field(
        default=5.0, ge=0.0, le=50.0, alias="LIBRARY_MIN_FREE_PERCENT"
    )
    library_max_pdf_pages: int = Field(
        default=2000, ge=1, le=100000, alias="LIBRARY_MAX_PDF_PAGES"
    )
    library_max_text_chars: int = Field(
        default=10000000, ge=1000, le=1000000000, alias="LIBRARY_MAX_TEXT_CHARS"
    )
    library_max_csv_rows: int = Field(
        default=250000, ge=1, le=100000000, alias="LIBRARY_MAX_CSV_ROWS"
    )
    library_max_csv_columns: int = Field(
        default=200, ge=1, le=100000, alias="LIBRARY_MAX_CSV_COLUMNS"
    )

    @field_validator(
        "qwen_fast_model",
        "qwen_balanced_model",
        "qwen_strong_model",
        "qwen_deep_research_model",
    )
    @classmethod
    def _validate_chat_models_are_qwen(cls, value: str) -> str:
        """
        校验生成模型字段必须为 Qwen/千问，拦截任何非千问模型配置。

        参数：
            value: 待校验的模型名称。

        返回：
            合规的模型名称原值。

        异常：
            ValueError: 当模型名称不满足“仅千问”约束时抛出。
        """
        # 复用 assert_qwen_model 的统一判定逻辑，保证全局一致。
        return assert_qwen_model(value)

    @field_validator("llm_provider")
    @classmethod
    def _validate_provider_is_bailian(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "bailian":
            raise ValueError("LLM_PROVIDER 仅允许 bailian。")
        return normalized

    @field_validator("dashscope_region")
    @classmethod
    def _validate_dashscope_region(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in normalized):
            raise ValueError("DASHSCOPE_REGION 格式无效。")
        return normalized

    @model_validator(mode="after")
    def _fill_base_urls_from_workspace(self) -> "Settings":
        """
        在配置加载后，用 WORKSPACE_ID 自动替换 base_url 中的占位符。

        规则：
            当 WORKSPACE_ID 已配置，但 base_url 为空或仍含“你的WorkspaceId”时，
            依据地域模板自动生成 compatible-mode / api base_url。

        返回：
            处理后的 Settings 实例（self）。
        """
        # Base URL 只能由服务端根据已验证的 region + Workspace ID 构建。
        wid = self.workspace_id
        if _is_configured_value(wid):
            host = f"{wid}.{self.dashscope_region}.maas.aliyuncs.com"
            self.dashscope_base_url = f"https://{host}/compatible-mode/v1"
            self.dashscope_deep_research_base_url = f"https://{host}/api/v1"
        else:
            self.dashscope_base_url = ""
            self.dashscope_deep_research_base_url = ""
        return self

    @property
    def qwen_configured(self) -> bool:
        """
        判断 Qwen 聊天调用是否具备最小配置（Key + 有效 base_url）。

        返回：
            True 表示 DASHSCOPE_API_KEY 与 DASHSCOPE_BASE_URL 均已配置且无占位符。
        """
        base_ok = self.dashscope_base_url.startswith("https://")
        return (
            self.llm_provider == "bailian"
            and _is_configured_value(self.dashscope_api_key)
            and _is_configured_value(self.workspace_id)
            and base_ok
        )

    @property
    def deep_research_configured(self) -> bool:
        """
        判断 Qwen Deep Research 是否具备最小配置（Key + 有效深度研究 base_url）。

        返回：
            True 表示 Key 与 DASHSCOPE_DEEP_RESEARCH_BASE_URL 均已配置且无占位符。
        """
        return self.qwen_configured and self.dashscope_deep_research_base_url.startswith("https://")

    @property
    def bailian(self) -> BailianRuntimeConfig:
        """Return the single normalized server-side Bailian configuration object."""
        configuration_error = None
        if not _is_configured_value(self.workspace_id):
            configuration_error = "workspace_id_missing_or_invalid"
        elif not _is_configured_value(self.dashscope_api_key):
            configuration_error = "api_key_missing_or_invalid"
        elif not self.qwen_configured:
            configuration_error = "bailian_configuration_invalid"
        return BailianRuntimeConfig(
            provider=self.llm_provider,
            region=self.dashscope_region,
            workspace_id=self.workspace_id,
            api_key=self.dashscope_api_key,
            base_url=self.dashscope_base_url,
            chat_model=self.qwen_balanced_model,
            embedding_model=self.bailian_embedding_model,
            request_timeout=self.llm_timeout_seconds,
            max_retries=self.llm_max_retries,
            configured=self.qwen_configured,
            configuration_error=configuration_error,
        )

    @property
    def openalex_configured(self) -> bool:
        """
        判断是否配置了 OpenAlex API Key（可选能力）。

        返回：
            True 表示 OPENALEX_API_KEY 非空。
        """
        # OpenAlex 为可选增强，未配置时相关调用应优雅跳过。
        return bool(self.openalex_api_key)

    def rerank_base_url(self) -> str:
        """
        推导百炼重排序（qwen3-rerank）的 OpenAI-compatible endpoint。

        说明：
            重排序使用 `.../compatible-api/v1/reranks`，与 chat 的
            `.../compatible-mode/v1` 路径不同，故由 base_url 推导。

        返回：
            重排序请求的完整 URL；无法推导时返回空串。
        """
        # 优先由 WORKSPACE_ID 与地域直接拼接，最稳妥。
        wid = self.workspace_id
        if _is_configured_value(wid):
            return (
                f"https://{wid}.{self.dashscope_region}.maas.aliyuncs.com/"
                "compatible-api/v1/reranks"
            )
        # 退化路径：从 chat base_url 变换路径段。
        if self.dashscope_base_url and _WORKSPACE_PLACEHOLDER not in self.dashscope_base_url:
            return self.dashscope_base_url.replace("compatible-mode/v1", "compatible-api/v1") + "/reranks"
        return ""

    def safe_summary(self) -> dict[str, str]:
        """
        生成可安全打印的配置摘要（敏感字段仅显示掩码或状态）。

        返回：
            字段名到安全展示值的映射，绝不含明文 Key。
        """
        # 仅暴露掩码 / 状态，避免任何明文密钥进入日志或界面。
        return {
            "DASHSCOPE_API_KEY": "已配置" if _is_configured_value(self.dashscope_api_key) else "未配置",
            "OPENALEX_API_KEY": "已配置" if self.openalex_api_key else "未配置",
            "WORKSPACE_ID": "已配置" if _is_configured_value(self.workspace_id) else "未配置",
            "DASHSCOPE_BASE_URL": "已配置" if self.qwen_configured else "未配置",
            "LLM_PROVIDER": self.llm_provider,
            "DASHSCOPE_REGION": self.dashscope_region,
            "qwen_configured": str(self.qwen_configured),
            "deep_research_configured": str(self.deep_research_configured),
            "APP_ENV": self.app_env,
            "EMBEDDING_BACKEND": self.embedding_backend,
            "OUTBOUND_HTTPS_PROXY": "已配置" if self.outbound_https_proxy else "未配置",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    获取全局单例配置对象（带缓存，避免重复解析 .env）。

    返回：
        进程内唯一的 Settings 实例。
    """
    # lru_cache 确保 .env 只被解析一次；测试可用 get_settings.cache_clear() 重置。
    return Settings()
