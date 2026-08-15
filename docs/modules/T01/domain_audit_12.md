# T01 12-Domain Audit Table（08/04）

Machine-readable source: `domain_audit_12.json`.

## Honesty / scope（严格对齐手册）

- 本表是 **12 个领域代表题抽查表**：记录题目相关性与跨域外推策略。
- **不是** live pipeline / agent-trace 跑题产物（`not_live_pipeline_traces=true`）。
- 每行通过 `linked_gold_claim_ids` 回链 `evidence_gold_set.json`，可用 metrics 复现。

| QID | Domain | Topic relevant | Cross-domain policy | Linked gold |
|---|---|---|---|---|
| Q001 | mathematics | Yes | allow_if_quote_overlaps | CLAIM-013 |
| Q012 | physics | Yes | allow_if_quote_overlaps | CLAIM-024, CLAIM-030 |
| Q018 | chemistry | Yes | allow_if_quote_overlaps | CLAIM-014 |
| Q024 | biology | Yes | allow_if_quote_overlaps | CLAIM-015 |
| Q028 | medicine | Yes | DEGRADE OVERGENERALIZATION | CLAIM-026/027/028 |
| Q035 | earth_science | Yes | allow_if_quote_overlaps | CLAIM-023, CLAIM-029 |
| Q042 | computer_science | Yes | allow_if_quote_overlaps | CLAIM-021, CLAIM-025 |
| Q051 | materials | Yes | allow_if_quote_overlaps | CLAIM-016 |
| Q063 | astronomy | Yes | allow_if_quote_overlaps | CLAIM-017 |
| Q077 | neuroscience | Yes | allow_if_quote_overlaps | CLAIM-018 |
| Q089 | climate | No (oncology evidence) | DEGRADE CROSS_DOMAIN | CLAIM-020 |
| Q102 | engineering | Yes | allow_if_quote_overlaps | CLAIM-019 |

## Reproduce

```powershell
# 测试/临时产物：写入目录（不碰 tracked 文件）
python -c "from pathlib import Path; from app.evidence.metrics import generate_wave_b_metrics_artifacts; print(generate_wave_b_metrics_artifacts(output_dir=Path('_tmp_t01_metrics'), generated_at='2026-08-02T06:41:57.966684+00:00'))"

# 维护者刷新 tracked JSON（显式 opt-in；Issue #44）
python -c "from app.evidence.metrics import generate_wave_b_metrics_artifacts; print(generate_wave_b_metrics_artifacts(allow_tracked_write=True, generated_at='2026-08-02T06:41:57.966684+00:00'))"
```
