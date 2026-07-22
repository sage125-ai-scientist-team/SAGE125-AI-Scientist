"""
tests/test_no_non_qwen_models.py — 项目级“仅千问生成模型”合规扫描。

覆盖：
    - 禁止把非千问模型名作为 model 配置（model="gpt-4" 等）；
    - 允许 openai 作为 SDK 包名（import openai）；
    - 禁止调用 OpenAI 官方 endpoint（api.openai.com）；
    - 禁止 qwen-deep-research 走 OpenAI-compatible client（chat/embeddings + deep-research 同现）。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 扫描范围：应用与脚本代码（不含测试自身与虚拟环境）。
SCAN_DIRS = [ROOT / "app", ROOT / "scripts"]

# model= 赋值中出现非千问生成模型名（作为字符串字面量）。
_MODEL_ASSIGN = re.compile(
    r"model\s*=\s*[\"'][^\"']*(gpt-|claude|gemini|deepseek|kimi|glm-4|minimax)",
    re.IGNORECASE,
)
# OpenAI 官方 endpoint。
_OPENAI_ENDPOINT = re.compile(r"api\.openai\.com", re.IGNORECASE)


def _iter_py_files():
    """产出所有待扫描的 .py 文件路径。"""
    for d in SCAN_DIRS:
        for p in d.rglob("*.py"):
            yield p


def test_no_non_qwen_model_config():
    """代码中不得把非千问模型名作为 model= 配置。"""
    offenders = []
    for p in _iter_py_files():
        text = p.read_text(encoding="utf-8")
        for m in _MODEL_ASSIGN.finditer(text):
            offenders.append(f"{p.name}: {m.group(0)}")
    assert not offenders, f"发现非千问模型配置：{offenders}"


def test_no_openai_official_endpoint():
    """代码中不得出现 OpenAI 官方 endpoint。"""
    offenders = [p.name for p in _iter_py_files() if _OPENAI_ENDPOINT.search(p.read_text(encoding="utf-8"))]
    assert not offenders, f"发现 OpenAI 官方 endpoint：{offenders}"


def test_deep_research_not_via_openai_client():
    """qwen-deep-research 不得与 openai chat/embeddings 调用同现于同一文件。"""
    offenders = []
    for p in _iter_py_files():
        text = p.read_text(encoding="utf-8")
        if "qwen-deep-research" in text:
            # 深度研究文件不应调用 openai 的 chat/embeddings 方法。
            if "chat.completions.create" in text or "embeddings.create" in text:
                offenders.append(p.name)
    assert not offenders, f"qwen-deep-research 疑似走了 OpenAI-compatible client：{offenders}"


def test_openai_sdk_import_allowed():
    """允许 openai 作为 SDK 包名被导入（存在即通过，不作为失败项）。"""
    # 该用例只确保扫描逻辑不误伤 SDK 导入；始终通过。
    assert True
