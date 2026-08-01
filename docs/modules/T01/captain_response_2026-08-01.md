# T01 对队长 REQUEST_CHANGES 的响应（2026-08-01）

**PR:** #13  
**Reviewed HEAD:** `a40d9a5`  
**Response HEAD:** 见本 PR 最新 push  

## P0 — T01-B-004 DOI-only / 纯元数据

| 项 | 处理 |
|---|---|
| 规范 | 标题 / DOI / 问题册不得单独支撑事实 |
| 代码 | `is_doi_only_text` + 扩展 `is_metadata_only`（DOI / DOI-URL / 裸 URL / quote==doi\|url） |
| 测试 | `test_block_doi_only_quoted_text_supports`（含 captain probe `10.1234/x.y.z`） |
| 额外 | `test_block_url_only_quoted_text_supports`；booklet 改名线索仍排除 |

复现：

```powershell
python -c "from app.contracts.evidence import EvidenceCardContract; from app.evidence.support_checker import is_metadata_only, check_claim_evidence_support, ClaimText; c=EvidenceCardContract(evidence_id='EV',source_id='s',source_type='paper',title='T',quoted_text='10.1234/x.y.z',locator={'page':1},doi='10.1234/x.y.z',content_hash='sha256:x'); print(is_metadata_only(c)); r=check_claim_evidence_support([ClaimText(claim_id='C',text='x',evidence_ids=['EV'],domain='oncology',relation='supports')],[c]); print(r.blocked, r.error_codes, r.allowed_links)"
python -m pytest -q tests/evidence
```

## P1 — 诚实表述 / sync

| 项 | 处理 |
|---|---|
| metrics | `not_independent_scientific_precision=true`；`precision_interpretation=fixture_accuracy_vs_hand_assigned_expected_decision` |
| 联调 | 仍为契约层 bridge（不改 `pipeline.py`）；真·T02 接线属 T02 |
| sync | 已 merge `upstream/integration/2026-08-10`（含 CURRENT tip） |
| Ready | **仍保持 Draft**（P0 关闭后等队长重审；Ready 按手册 08/05） |

## Cross-PR

- T04 booklet 改名：T01 侧加强 booklet 线索识别；完整 loader 字段仍需 T04 修复 #17。  
- T02 双 PR：非本 PR 可单独 Approve 条件；T01 不改 `pipeline.py`。
