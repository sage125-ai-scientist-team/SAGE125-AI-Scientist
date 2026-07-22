"""
app.core —— 核心基础设施子包。

聚合项目级别的横切能力：
    - config    : 基于 pydantic-settings 的类型化配置（从 .env 加载）。
    - logging   : 统一日志初始化，内置 API Key 脱敏过滤器。
    - schemas   : 全局 Pydantic 数据模型（Evidence / Hypothesis / ResearchPlan 等）。
    - constants : 常量与禁用清单（禁用的非千问模型、提示词片段等）。
"""
