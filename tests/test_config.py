"""
tests/test_config.py — 配置模块单元测试。

覆盖：
    - mask_secret 掩码逻辑（空值 / 短值 / 常规值）；
    - Settings 可从 .env 加载且默认聊天模型均为千问；
    - 生成模型校验器拒绝非千问模型。
"""

from __future__ import annotations

import pytest

from app.core.config import Settings, mask_secret, get_settings


def test_mask_secret_empty_returns_placeholder():
    """空值应返回“未配置”，避免误导为已配置。"""
    # 空字符串与 None 都应被视为未配置。
    assert mask_secret("") == "未配置"
    assert mask_secret(None) == "未配置"


def test_mask_secret_short_is_fully_masked():
    """短值应被全遮蔽，防止泄露短 Key 全部内容。"""
    # 长度 <= 8 的值应全部替换为 *。
    assert mask_secret("abcd") == "****"


def test_mask_secret_regular_shows_prefix_suffix():
    """常规值应仅暴露首尾各 4 位。"""
    # 首尾各 4 位 + 中间 ****。
    assert mask_secret("sk-1234567890abcd") == "sk-1****abcd"


def test_default_chat_models_are_qwen():
    """默认聊天模型均应为千问，满足安全约束。"""
    # 使用默认值构造（不依赖 .env 中的具体填写）。
    settings = get_settings()
    assert settings.qwen_fast_model.lower().startswith("qwen")
    assert settings.qwen_balanced_model.lower().startswith("qwen")
    assert settings.qwen_strong_model.lower().startswith("qwen")


def test_non_qwen_model_rejected():
    """将聊天模型设为非千问时，应触发校验错误。"""
    # 直接实例化并覆盖字段，期望 pydantic 校验抛错。
    with pytest.raises(Exception):
        Settings(QWEN_FAST_MODEL="gpt-4o")
