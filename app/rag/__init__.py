"""
app.rag —— 检索增强生成（RAG）子包。

组件：
    - document_loader : 加载 PDF / 文本等原始资料。
    - chunker         : 将文档切分为适合嵌入的片段。
    - zvec_store      : 基于 zvec 的向量存储与检索封装。
    - retriever       : 组合嵌入、检索与重排序的高层检索器。
    - evidence        : 将检索命中转换为可溯源的 Evidence 卡片。
"""
