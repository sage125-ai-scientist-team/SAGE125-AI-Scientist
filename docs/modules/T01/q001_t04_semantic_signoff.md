# T01：T04 `retrieve_hits` / Q001 语义签字清单

**Status:** `WAITING_T04_DRAFT_PR` + `Q001_MATERIAL_STATUS=AWAITING_CONTROLLED_DELIVERY`  
**Date:** 2026-08-12  
**Captain source:** PR [#35](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/35) comment  
`[CAPTAIN AUTHORIZATION] T04 无损 RetrievalHit 接口与 Q001 真实文献包责任人`  
**Decision flags（摘录）：**

```text
T04_RETRIEVE_HITS_IMPLEMENTATION_AUTHORIZED=true
AUTHORIZED_BRANCH=t04/c-retrieval-hit-interface
DRAFT_PR_AUTHORIZED=true
READY_AUTHORIZED=false
MERGE_AUTHORIZED=false
FORMAL_RETRIEVAL_METRICS_AUTHORIZED=false
FIVE_REAL_RUNS_AUTHORIZED_BY_THIS_DECISION=false
CAPTAIN_DECISION=AUTHORIZED_WITH_GATES
Q001_MATERIAL_STATUS=AWAITING_CONTROLLED_DELIVERY
T07_REAL_RUN_STATUS=HOLD
```

## 1. T01 角色（仅此）

| 角色 | 账号 | 职责 |
|---|---|---|
| `Q001_SEMANTIC_SIGNOFF_OWNER` | `@Yqqxz`（T01） | 独立核验 quote / locator / authors / DOI\|URL / content_hash / supports·contradicts / `precheck.gate.passed` |
| 非职责 | — | **不**写 T04 检索实现；**不**改 `app/rag/**`；**不**提供/批准文献源；**不**替 T07 跑五题真实运行 |

职责分离（队长原文）：

- 材料提供/受控保管：`@liuyanbo12`
- loader/chunk/index/provenance：`@YHY0728`（T04）
- 下游消费：`@myr-111`（T07）— 仅消费 **T04 manifest + T01 signoff** 的包

## 2. 合并顺序中 T01 的两道门

```text
1. T04: t04/c-retrieval-hit-interface Draft PR
2. T01: 对 T04 PR 准确 HEAD 做 semantic signoff     ← 门 A（接口语义）
3. Captain: 审核并合并 T04 interface → integration
4. T07: 后续受控运行分支从最新 integration 创建/merge
5. Q001 真实文献包受控交付 → T04 loader/chunk/index/provenance
6. T01: 对实际 Q001 hits / EvidenceBundle 做语义签字   ← 门 B（材料语义）
7. 五题材料与全部门禁齐备后，T07 才可申请五题真实运行
```

当前：**门 A 未触发**（未见 `t04/c-retrieval-hit-interface` 开放 Draft PR）。  
当前：**门 B 未触发**（`Q001_MATERIAL_STATUS=AWAITING_CONTROLLED_DELIVERY`）。

## 3. 门 A — T04 `retrieve_hits` 接口语义签字检查表

在 T04 Draft PR 发布且六项 CI 绿、模块测/全仓回归通过后，T01 对**该 PR 准确 HEAD**核对：

| # | 检查项 | PASS 判据 |
|---|---|---|
| A1 | 分支/基线 | 自最新 `integration/2026-08-10` 新建；非复用 #23 分支 |
| A2 | 签名 | `LocalRAGRetriever.retrieve_hits(query, filters=None, source_scope="all") -> tuple[RetrievalHit, ...]` |
| A3 | 旧路径不变 | `retrieve()` 签名/返回 `EvidenceCard` 列表/排序/异常/fallback 行为回归通过 |
| A4 | 同核 | `retrieve_hits` 与 `retrieve` 共用同一检索核；单次调用无重复 embedding/rerank |
| A5 | 返回形态 | 确定序 `tuple`；无结果为空 `tuple`（非假成功 hit） |
| A6 | 无损字段 | `quoted_text`、原始 `retrieval_score`/`score_kind`、`source_type`/`source_role`、`SourceLocator`、完整 SHA-256 `content_hash`、title、DOI/URL、必要 metadata |
| A7 | provenance | type/role 来自已持久 provenance/SourcePolicy；不靠文件名推断“论文” |
| A8 | fail-closed | 缺 quote/locator/完整 hash/document·chunk identity/provenance → 不得补造字段 |
| A9 | 题册边界 | `sjtu-booklet.pdf` 仅可作题目身份；**不得**进入 T01 scientific `supports`；正式 context 须 `question_booklet_hits=0` |
| A10 | 路径所有权 | 仅 `app/rag/**`、`tests/rag/**`、`docs/modules/T04/**`（及必要时兼容补丁 `app/contracts/rag.py`）；**未改** `app/evidence/**` |
| A11 | 指标边界 | **未**宣称正式 retrieval 指标；`FORMAL_RETRIEVAL_METRICS_AUTHORIZED=false` |

**签字输出格式（门 A，待填）：**

```text
T01_T04_RETRIEVE_HITS_SEMANTIC_SIGNOFF=<PASS|FAIL|WAIT>
PR=#?
REVIEWED_HEAD_SHA=<40-hex>
BOOKLET_AS_SUPPORTS=FORBIDDEN_CONFIRMED
FORMAL_METRICS_CLAIMED=false
BLOCKING_FINDINGS=<NONE|...>
SIGNOFF_OWNER=Yqqxz
SIGNOFF_DATE=YYYY-MM-DD
```

未见到准确 HEAD 前：**不得**给 PASS。

## 4. 门 B — Q001 真实 hits / EvidenceBundle 语义签字检查表

仅在队长受控交付 Q001 包且 T04 完成 loader/chunk/index/provenance 验收后执行。

不合格输入（一律 FAIL，不得签字）：

- `data/raw/sjtu-booklet.pdf`（仅题目标题源）
- `tests/rag/fixtures/**`
- provisional retrieval gold / `FIX-*`
- 仅有 DOI/元数据、无可核验原文 quote
- 无 license/授权、版本、SHA-256 或 locator

合格包至少含：source URI/provider、title/authors/DOI|URL、license/access、acquisition date/version、原始 bytes SHA-256+size、稳定 document ID、受控存储位置/引用、可复现 loader 命令、chunk/index manifest + per-chunk content hash。

| # | 检查项 | PASS 判据 |
|---|---|---|
| B1 | 身份 | Q001 包与 T04 manifest 一致；非题册 |
| B2 | quote | 非空；可在受控源中核验；非 metadata-only |
| B3 | locator | 非空且非 identity 兜底 |
| B4 | authors + doi\|url | supports 所需 provenance 完整 |
| B5 | content_hash | 与原文/chunk 字节一致（SHA-256） |
| B6 | links | supports/contradicts 语义正确；无静默冲突 |
| B7 | precheck | `precheck_bundle_for_validation(...).gate.passed is True` |
| B8 | booklet | `question_booklet_hits=0`；题册未进 supports |
| B9 | 指标 | 未宣称正式 retrieval 指标；未授权五题真实运行 |

**签字输出格式（门 B，待填）：**

```text
T01_Q001_EVIDENCE_SEMANTIC_SIGNOFF=<PASS|FAIL|WAIT>
PACKAGE_REF=<manifest path or controlled URI>
T04_MANIFEST_SHA_OR_COMMIT=<...>
BUNDLE_OR_HIT_DIGEST=<...>
PRECHECK_GATE_PASSED=true
BOOKLET_HITS=0
SIGNOFF_OWNER=Yqqxz
SIGNOFF_DATE=YYYY-MM-DD
```

## 5. 停止条件（T01 必须报停）

出现任一项立即停止并报告队长：跨 owner 改路径、破坏性 Schema、真实密钥、许可/再分发不明、源 bytes/hash 不一致、题册/fixture/provisional gold 充当正式 evidence、**T01 gate 未通过**、材料未验收前跑 provider 或宣称正式指标。

## 6. 自我审查（2026-08-12）

| 项 | 结果 |
|---|---|
| 是否已实现/修改 `app/rag/**` | **否**（正确：属 T04） |
| 是否已对不存在的 T04 HEAD 给 PASS | **否**（正确：WAIT） |
| 是否已对未交付 Q001 包给 PASS | **否**（正确：WAIT） |
| 是否保持 `FORMAL_RETRIEVAL_METRICS_AUTHORIZED=false` | **是** |
| 是否保持五题真实运行 HOLD | **是** |
| 下一步 | 等 T04 Draft PR → 门 A；等队长交付 Q001 → 门 B |

## 7. 相关文档

- 既有 T07 precheck 语义：`docs/modules/T01/t07_evidence_context_acceptance.md`
- Wave C handoff：`docs/modules/T01/handoff.md`
- T08 证据读口（另 PR #43，与本授权正交）
