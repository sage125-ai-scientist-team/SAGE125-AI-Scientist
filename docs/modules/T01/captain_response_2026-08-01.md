# T01 对队长 REQUEST_CHANGES / 跨 PR 联审的响应

**原 PR:** #13（已关闭）  
**现行 PR:** #25（Draft reopen）  
**Reviewed HEAD（旧）:** `a40d9a5`  
**现行 HEAD:** 见 PR #25 最新 commit  

依据：`T01.yaml` Wave B + 队长审核截图（REQUEST_CHANGES + Cross-PR note）。

---

## 你（T01）必须做的 vs 他人做的

| 来源 | 项 | 责任 | T01 状态 |
|---|---|---|---|
| P0 T01-B-004 | DOI-only / 纯元数据 quote → BLOCK + 红灯 | **T01** | **DONE** |
| P1 指标诚实 | `precision=1.0` 不得当独立科学 ≥90% | **T01** | **DONE**（`not_independent_scientific_precision`） |
| P1 联调诚实 | 契约桥 ≠ 真·T02 pipeline | **T01 文档**；接线 **T02** | **DONE 文档** |
| P1 behind / Draft | sync；P0 未关前不 Ready | **T01** | **DONE sync**；**保持 Draft** |
| Cross T04→T01 FAIL | loader 缺 locator/authors/DOI/hash | **T04 修 loader**；**T01 消费侧拒残缺** | **T01 侧 DONE**（`INCOMPLETE_PROVENANCE`） |
| Cross booklet 改名 | 题册不得支撑事实 | **T04 #23/#17** + **T01 线索识别** | **T01 侧 DONE** |
| Cross T01→T02 WAIT | #11/#21 接 EvidenceBundle | **T02 / 队长澄清** | **T01 不改 pipeline** |
| Combined NOT READY | 勿手工 squash merge | 队长 | 已知悉 |

---

## P0 — T01-B-004（已关闭）

| 项 | 处理 |
|---|---|
| 规范 | 标题 / DOI / 问题册不得单独支撑事实 |
| 代码 | `is_doi_only_text` + 扩展 `is_metadata_only` |
| 测试 | `test_block_doi_only_quoted_text_supports`（probe `10.1234/x.y.z`） |
| 验证 | `python -m pytest -q tests/evidence` |

## P1 — 指标 / 联调 / Ready 门禁

| 项 | 处理 |
|---|---|
| metrics | `precision_interpretation=fixture_accuracy_vs_hand_assigned_expected_decision` |
| 联调 | `integration_bridge` = 契约层；`pipeline.py` 未改 |
| Ready | **仍 Draft**（手册 08/05；等队长重审 Approve） |

## Cross-PR — T04 loader 缺口（T01 消费侧）

新增 `SupportErrorCode.INCOMPLETE_PROVENANCE`：当 `relation=supports` 且缺少

- 真实 `locator`（非 builder 推断兜底）
- `authors`
- `doi` 或 `url`
- `content_hash`

→ **BLOCK**，禁止残缺元数据支撑事实。

T04 仍须在 #23 修复 loader 完整产出；T01 不再静默吞掉缺口。

Booklet 改名：`is_booklet_evidence` 扫描 evidence_id/title/locator 中 booklet 线索。

## 复现

```powershell
python -m pytest -q tests/evidence
python -c "from app.contracts.evidence import EvidenceCardContract; from app.evidence.support_checker import is_metadata_only, check_claim_evidence_support, ClaimText; c=EvidenceCardContract(evidence_id='EV',source_id='s',source_type='paper',title='T',quoted_text='10.1234/x.y.z',locator={'page':1},authors=['A'],doi='10.1234/x.y.z',content_hash='sha256:x'); print(is_metadata_only(c)); r=check_claim_evidence_support([ClaimText(claim_id='C',text='x',evidence_ids=['EV'],domain='oncology',relation='supports')],[c]); print(r.blocked, r.error_codes)"
```
