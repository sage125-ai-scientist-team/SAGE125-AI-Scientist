# Issue #44 — pytest 不得改写 T01 审计产物

**Issue:** [#44](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/issues/44)  
**Owner:** T01 (`Yqqxz`)  
**Date:** 2026-08-12

## 问题

全仓 `pytest` 会改写已跟踪文件：

- `docs/modules/T01/metrics.json`（`generated_at` 变化）
- `docs/modules/T01/domain_audit_12.json`（字节/EOL 重写）

## 修复（五项要求对照）

| # | 要求 | 落实 |
|---|---|---|
| 1 | 写入 `tmp_path` / 注入目录 | `generate_wave_b_metrics_artifacts(output_dir=...)` |
| 2 | 冻结 `generated_at` | `compute_metrics(generated_at=...)` / 生成 API 同参 |
| 3 | pytest 不改写 tracked | 默认拒绝落到 `DEFAULT_*`；须 `allow_tracked_write=True` |
| 4 | worktree 不变回归 | `test_pytest_metrics_path_does_not_dirty_tracked_audit_files` |
| 5 | 确定性 JSON/EOL | `_write_json_deterministic`（UTF-8 + LF） |

## 自我审查

- 未改 T05 / 共享契约 / 依赖  
- 未把 Mock 标成 actual  
- tracked 刷新仅维护者显式 opt-in  
- 测试：`tests/evidence/test_metrics.py`
