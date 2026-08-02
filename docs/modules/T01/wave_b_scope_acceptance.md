# T01 Wave B — Scope Acceptance（bridge-only / UI）

**PR:** #25  
**Requirement IDs:** T01-B-009 / T01-B-013 / T01-B-015  
**Status:** **ACCEPTED for Wave B as contract-bridge + citation UI scope**  
**Not claimed:** live `pipeline.py` / EvidenceExtractor / HypothesisGenerator / ExperimentDesigner wiring（T02-owned）

## Written acceptance

T01 Wave B 正式验收以下范围，并明确不把后续项算作本 PR 已完成：

| Capability | Wave B acceptance evidence | Out of Wave B scope |
|---|---|---|
| 一键回证据（UI/Markdown） | `citation_renderer.render_citation_markdown`：claim → `#evidence-<id>` 锚点；含 locator / quote / source URL / support status | 前端产品页真实点击 trace（T08 消费 payload） |
| T08 payload | `build_t08_citation_payload` + `docs/contracts/T01.md` §6 | T08 渲染实现本身 |
| 版本记录挂载 | `attach_bundle_to_plan_version` 写入 `PlanVersion.prompt_fingerprints` / `hypothesis_generation.evidence_bundle` | T02 修订环业务逻辑 |
| Validator 交接 | `build_validation_context_from_bundle` + `precheck_bundle_for_validation`；E2E：`tests/evidence/test_integration_e2e.py` | T03 `ValidationService` 完整规则执行 |
| 真·pipeline 贯穿 | **不验收**（禁止改 `app/workflow/pipeline.py`） | T02 按冻结接口接入 |

## Reproduce（一键回证据 UI 样例）

```powershell
python -c "from app.contracts.evidence import EvidenceCardContract; from app.evidence.citation_renderer import build_citation_item, render_citation_markdown; c=EvidenceCardContract(evidence_id='EV-DEMO',source_id='s',source_type='paper',title='Demo',quoted_text='EGFR inhibition improves response in lung adenocarcinoma samples.',locator={'page':3,'section':'Results'},authors=['A'],year=2024,doi='10.1234/demo',content_hash='sha256:demo',domain='medicine'); print(render_citation_markdown([build_citation_item(claim_id='C1',card=c)]))"
```

Expected: Markdown contains `[EV-DEMO](#evidence-EV-DEMO)` and evidence detail anchor.

## Deferred to Wave C / T02

- Live agent-trace E2E through pipeline revision loop  
- Independent scientific annotator precision on non-provisional gold  
- Full T08 product UI click-path screenshots bound to final commit  

Signed acceptance for Wave B content gate: **bridge-only + citation UI evidence is sufficient for T01-B-009/B-013/B-015 under path-ownership constraints.**
