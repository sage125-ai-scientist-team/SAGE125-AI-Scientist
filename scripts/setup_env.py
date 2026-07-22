#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/setup_env.py — 本地交互式环境变量配置脚本。

设计目标：
    在**本地终端**（而非 Cursor / 任何对话框）中安全地采集真实 API Key，
    并将其写入项目根目录下的 .env 文件。脚本全程不会将完整 Key 回显到终端，
    也不会将其写入日志、README、前端或测试文件。

安全约束（对应项目硬性安全要求）：
    1. 真实 Key 只应粘贴到本地终端或本地 .env 文件；
    2. 禁止把真实 Key 粘贴到 Cursor 对话框；
    3. 禁止提交 .env（已由 .gitignore 屏蔽）；
    4. 日志/回显只显示“已配置 / 未配置”或掩码形式（前 4 位 + 后 4 位）。

用法：
    python scripts/setup_env.py
"""

from __future__ import annotations

import os
import sys
from getpass import getpass
from pathlib import Path
from typing import Dict, List, Tuple

# 项目根目录：本文件位于 <root>/scripts/setup_env.py，故上溯两级即为根。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 目标 .env 文件的绝对路径。
ENV_PATH = PROJECT_ROOT / ".env"
# 模板文件，用于在 .env 不存在时提供默认结构。
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"


def mask_secret(value: str) -> str:
    """
    将敏感字符串掩码为“前 4 位 + **** + 后 4 位”的安全展示形式。

    参数：
        value: 原始敏感字符串（如 API Key）。

    返回：
        掩码后的字符串；若为空返回“未配置”；若过短则整体用 * 遮蔽，
        以避免泄露短 Key 的全部内容。
    """
    # 空值直接返回“未配置”提示，避免误导。
    if not value:
        return "未配置"
    # 过短的密钥不做“前后各 4 位”展示，改为全遮蔽，防止信息泄露。
    if len(value) <= 8:
        return "*" * len(value)
    # 常规情况：仅暴露首尾各 4 位，中间以 **** 代替。
    return f"{value[:4]}****{value[-4:]}"


def parse_env_file(path: Path) -> Tuple[Dict[str, str], List[str]]:
    """
    解析 .env 文件为“键值字典”与“原始行列表”。

    保留原始行列表是为了在写回时尽量维持注释与顺序（非键值行原样保留）。

    参数：
        path: .env 或 .env.example 的路径。

    返回：
        (values, lines):
            values —— 键到值的映射（仅解析 KEY=VALUE 形式的有效行）；
            lines  —— 文件原始行（含注释、空行），用于顺序化写回。
    """
    # 若文件不存在，返回空字典与空行列表，交由上层决定回退策略。
    if not path.exists():
        return {}, []
    # 以 UTF-8 读取所有行，保留换行结构。
    lines = path.read_text(encoding="utf-8").splitlines()
    # 累积解析出的键值对。
    values: Dict[str, str] = {}
    for line in lines:
        # 去除首尾空白后判断是否为可解析的键值行。
        stripped = line.strip()
        # 跳过空行与注释行（以 # 开头）。
        if not stripped or stripped.startswith("#"):
            continue
        # 仅处理包含 '=' 的行，按第一个 '=' 拆分键值。
        if "=" in stripped:
            key, _, val = stripped.partition("=")
            values[key.strip()] = val.strip()
    return values, lines


def prompt_value(field: str, current: str, secret: bool, optional: bool) -> str:
    """
    交互式地向用户询问单个字段的值。

    参数：
        field:    字段名（如 DASHSCOPE_API_KEY）。
        current:  当前 .env 中的旧值（用于回车保留）。
        secret:   是否为敏感字段（True 时使用 getpass 隐藏输入，不回显）。
        optional: 是否可选（True 时允许直接回车跳过并保留旧值/留空）。

    返回：
        用户最终确定的字段值（可能与旧值相同）。
    """
    # 组装提示语：敏感字段展示掩码旧值，普通字段展示明文旧值。
    shown = mask_secret(current) if secret else (current or "（空）")
    hint = "（可回车跳过）" if optional else ""
    print(f"\n[{field}] 当前值：{shown} {hint}")

    # 敏感字段使用 getpass，输入内容不会显示在终端，避免肩窥与日志泄露。
    if secret:
        entered = getpass(f"请输入 {field}（直接回车保留当前值）：").strip()
    else:
        entered = input(f"请输入 {field}（直接回车保留当前值）：").strip()

    # 用户直接回车 -> 保留旧值，实现“可跳过 / 不覆盖”。
    if entered == "":
        return current
    return entered


def build_env_lines(values: Dict[str, str], template_lines: List[str]) -> List[str]:
    """
    依据模板行结构，将最新的 values 写回为完整的 .env 文本行。

    策略：
        以模板（现有 .env 或 .env.example）的行顺序为骨架，逐行处理：
        - 注释/空行原样保留；
        - KEY=VALUE 行使用 values 中的最新值覆盖；
        - values 中存在但模板未覆盖的键，追加到文件末尾。

    参数：
        values:         最新的键值映射。
        template_lines: 用于保序的模板原始行。

    返回：
        可直接写入 .env 的字符串行列表。
    """
    # 记录哪些键已在模板行中被写出，避免末尾重复追加。
    written_keys = set()
    output: List[str] = []

    for line in template_lines:
        stripped = line.strip()
        # 注释与空行原样保留，维持文件可读性。
        if not stripped or stripped.startswith("#"):
            output.append(line)
            continue
        # 键值行：用最新值覆盖，保留键名原始写法。
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in values:
                output.append(f"{key}={values[key]}")
                written_keys.add(key)
                continue
        # 其它无法识别的行，原样保留。
        output.append(line)

    # 追加模板中未出现、但 values 中新增的键（保证不丢配置）。
    for key, val in values.items():
        if key not in written_keys:
            output.append(f"{key}={val}")

    return output


def main() -> int:
    """
    脚本主入口：读取现有配置 -> 交互采集 -> 派生 URL -> 写回 .env -> 安全总结。

    返回：
        进程退出码（0 表示成功）。
    """
    # 打印安全须知，作为脚本运行的第一道提醒。
    print("=" * 60)
    print("SAGE125-AI-Scientist 环境配置向导")
    print("=" * 60)
    print("安全提示：")
    print("  - 真实 Key 只粘贴到【本地终端】或【本地 .env 文件】。")
    print("  - 不要把真实 API Key 粘贴到 Cursor 对话框。")
    print("  - 不要提交 .env；不要把 Key 写入 README / 前端 / 日志 / 测试文件。")
    print("=" * 60)

    # 读取现有 .env；若不存在则回退到 .env.example 作为模板骨架。
    values, lines = parse_env_file(ENV_PATH)
    if not lines:
        # 没有 .env 时，用 .env.example 的结构作为写回模板。
        _, lines = parse_env_file(ENV_EXAMPLE_PATH)
        # 同步读取示例文件的默认值（如模型名等非敏感字段）。
        example_values, _ = parse_env_file(ENV_EXAMPLE_PATH)
        # 已有 values（来自 .env）优先，缺失的用示例默认值补齐。
        for k, v in example_values.items():
            values.setdefault(k, v)

    # 交互采集：DASHSCOPE_API_KEY 为敏感必填（允许留空但会提示后续调用失败）。
    values["DASHSCOPE_API_KEY"] = prompt_value(
        "DASHSCOPE_API_KEY", values.get("DASHSCOPE_API_KEY", ""),
        secret=True, optional=True,
    )
    # WORKSPACE_ID 用于派生两个 base_url，非敏感。
    values["WORKSPACE_ID"] = prompt_value(
        "WORKSPACE_ID", values.get("WORKSPACE_ID", ""),
        secret=False, optional=True,
    )
    # OPENALEX_API_KEY 可直接回车跳过。
    values["OPENALEX_API_KEY"] = prompt_value(
        "OPENALEX_API_KEY", values.get("OPENALEX_API_KEY", ""),
        secret=True, optional=True,
    )
    # CONTACT_EMAIL 用于 arXiv / Crossref 礼貌联系，非敏感。
    values["CONTACT_EMAIL"] = prompt_value(
        "CONTACT_EMAIL", values.get("CONTACT_EMAIL", ""),
        secret=False, optional=True,
    )

    # 根据 WORKSPACE_ID 自动派生两个 base_url（仅在填写了 WORKSPACE_ID 时覆盖）。
    workspace_id = values.get("WORKSPACE_ID", "").strip()
    if workspace_id:
        # OpenAI-compatible endpoint（供 qwen chat / embedding / rerank 使用）。
        values["DASHSCOPE_BASE_URL"] = (
            f"https://{workspace_id}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
        )
        # 原生 DashScope endpoint（供 qwen-deep-research 使用）。
        values["DASHSCOPE_DEEP_RESEARCH_BASE_URL"] = (
            f"https://{workspace_id}.cn-beijing.maas.aliyuncs.com/api/v1"
        )

    # 依据模板行结构写回 .env，保留注释与顺序。
    output_lines = build_env_lines(values, lines)
    ENV_PATH.write_text("\n".join(output_lines) + "\n", encoding="utf-8")

    # 安全总结：仅展示掩码或“已配置 / 未配置”，绝不打印完整 Key。
    print("\n" + "=" * 60)
    print(".env 已创建/更新：", ENV_PATH)
    dashscope_key = values.get("DASHSCOPE_API_KEY", "")
    if dashscope_key:
        print(f"DASHSCOPE_API_KEY：已配置，显示为 {mask_secret(dashscope_key)}")
    else:
        # 未填写时允许保存，但明确提示后续真实 API 调用会失败。
        print("DASHSCOPE_API_KEY：未配置（后续真实 API 调用会失败）")
    openalex_key = values.get("OPENALEX_API_KEY", "")
    print(f"OPENALEX_API_KEY：{'已配置' if openalex_key else '未配置（可选）'}")
    print(f"WORKSPACE_ID：{'已配置' if workspace_id else '未配置'}")
    print(f"CONTACT_EMAIL：{values.get('CONTACT_EMAIL') or '未配置'}")
    print("-" * 60)
    print("请不要提交 .env（已在 .gitignore 中屏蔽）。")
    print("真实 Key 只粘贴到本地终端或本地 .env 文件，不要粘贴到 Cursor 对话框。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    # 允许通过退出码反映执行结果，便于脚本化调用。
    sys.exit(main())
