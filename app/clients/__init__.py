"""
app.clients —— 外部模型与文献服务客户端子包。

包含：
    - qwen_chat_client          : 通过 OpenAI-compatible endpoint 调用 Qwen 聊天模型。
    - qwen_deep_research_client : 通过原生 dashscope SDK 调用 qwen-deep-research。
    - embedding_client          : 百炼向量嵌入客户端（可选本地模式）。
    - rerank_client             : 百炼重排序客户端。
    - literature_clients        : arXiv / OpenAlex / Crossref 文献检索客户端。

约束：所有生成模型必须为 Qwen/千问；base_url 必须来自配置。
"""
