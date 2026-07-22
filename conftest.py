"""
conftest.py（项目根）—— pytest 全局夹具与路径配置。

将项目根目录加入 sys.path，确保测试可通过 `import app` 访问应用包。
放置于根目录可让 pytest 在收集时把根目录插入 sys.path（prepend 模式）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 项目根目录（本文件所在目录）。
PROJECT_ROOT = Path(__file__).resolve().parent

# 确保根目录位于 sys.path 首位，使 `import app` 可用。
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Pipeline tests previously created hundreds of production-like directories in
# exports/. Keep generated test runs under pytest's ignored cache instead.
os.environ.setdefault(
    "SAGE_TEST_EXPORT_DIR",
    str(PROJECT_ROOT / "data" / "cache" / "pytest-artifacts"),
)
