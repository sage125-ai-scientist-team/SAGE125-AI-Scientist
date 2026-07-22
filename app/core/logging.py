"""
app.core.logging —— 统一日志初始化与 API Key 脱敏。

关键安全能力：
    SecretMaskingFilter 会在日志写出前扫描消息文本与参数，
    将疑似 API Key（如 sk- 开头的长串）整体替换为 `sk-****MASKED`，
    确保任何日志都不会打印完整 API Key，也不会打印 .env 全量内容。

所有 client 统一通过 get_logger(name) 获取日志器，从而共享脱敏能力。
"""

from __future__ import annotations

import logging
import re
import sys

# 匹配疑似密钥：sk- 开头后接至少 8 位字母数字/下划线/连字符。
# 命中后整体替换为固定掩码，避免任何真实片段泄露。
_SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
# 统一掩码文本。
_MASK_TEXT = "sk-****MASKED"


def mask_text(text: str) -> str:
    """
    将文本中所有疑似 API Key 替换为固定掩码 `sk-****MASKED`。

    参数：
        text: 原始文本。

    返回：
        脱敏后的文本；非字符串或无命中时原样返回。
    """
    # 仅处理字符串，避免破坏其它类型。
    if not isinstance(text, str):
        return text
    # 将所有命中片段替换为固定掩码。
    return _SECRET_PATTERN.sub(_MASK_TEXT, text)


class SecretMaskingFilter(logging.Filter):
    """
    日志过滤器：对日志消息与其格式化参数执行 API Key 脱敏。

    通过重写 filter()，在每条日志格式化前替换 record.msg 与 record.args
    中疑似 Key 的片段，作为密钥泄露的最后一道纵深防御。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        对单条日志记录执行脱敏，并始终允许其通过（返回 True）。

        参数：
            record: 待处理的日志记录。

        返回：
            True —— 表示该记录不被丢弃，仅内容被脱敏。
        """
        # 脱敏主消息文本。
        if isinstance(record.msg, str):
            record.msg = mask_text(record.msg)
        # 脱敏格式化参数（%-style），逐个处理字符串参数。
        if record.args:
            if isinstance(record.args, dict):
                # 字典参数：仅对字符串值脱敏。
                record.args = {k: mask_text(v) if isinstance(v, str) else v for k, v in record.args.items()}
            else:
                # 元组参数：逐项脱敏字符串。
                record.args = tuple(mask_text(a) if isinstance(a, str) else a for a in record.args)
        return True


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    初始化项目根日志器，挂载脱敏过滤器与标准格式。

    参数：
        level: 日志级别字符串（如 "INFO" / "DEBUG"）。

    返回：
        配置完成的项目根日志器（名为 "sage125"）。
    """
    # 使用固定命名空间，便于子模块通过 get_logger 继承配置。
    logger = logging.getLogger("sage125")
    # 将字符串级别解析为 logging 常量，非法值回退到 INFO。
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 幂等：避免重复添加 handler。
    if not logger.handlers:
        # 输出到标准输出，便于容器 / 终端采集。
        handler = logging.StreamHandler(sys.stdout)
        # 统一日志格式：时间 - 级别 - 名称 - 消息。
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )
        handler.setFormatter(formatter)
        # 挂载脱敏过滤器。
        handler.addFilter(SecretMaskingFilter())
        logger.addHandler(handler)

    # 不向 root logger 传播，避免重复输出。
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取带命名空间的子日志器（继承根日志器的处理器与过滤器）。

    参数：
        name: 子模块名称，如 "clients.qwen_chat"。

    返回：
        名为 "sage125.<name>" 的子日志器。
    """
    # 确保根日志器已初始化（含脱敏 handler），再返回子日志器。
    root = logging.getLogger("sage125")
    if not root.handlers:
        setup_logging()
    # 子日志器复用根日志器的 handler，从而共享脱敏能力。
    return logging.getLogger(f"sage125.{name}")
