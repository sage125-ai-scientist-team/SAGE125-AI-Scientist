# T01：T04 `retrieve_hits` / Q001 语义签字清单

**Status:** `GATE_A=PASS`（#47 MERGED）+ `GATE_B1=PASS`（#59）+ `GATE_B_FINAL=BLOCKED` + `Q001_MATERIAL_STATUS=AWAITING_CONTROLLED_DELIVERY`  
**Date:** 2026-08-12  
**Gate A reviewed PR:** [#47](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/47) @ `f77959b43f7f520119070181011e0d0713425cdd`  
**Captain sources:**
1. PR [#35](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/35) — `[CAPTAIN AUTHORIZATION] T04 无损 RetrievalHit…`
2. PR [#47](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/47) review — `Captain review — PR #47 (T04 Wave C · Gate A)`（2026-08-12）

**Decision flags（队长 #47 裁决 + T01 签字，摘录）：**

```text
T04_RETRIEVE_HITS_IMPLEMENTATION_AUTHORIZED=true
AUTHORIZED_BRANCH=t04/c-retrieval-hit-interface
GATE_A_TECHNICAL_REVIEW=PASS
T01_T04_RETRIEVE_HITS_SEMANTIC_SIGNOFF=PASS
BLOCKING_FINDINGS=NONE
READY_AUTHORIZED=YES                 # 仅 Gate A 接口增量；不代表 Wave C Done
MERGE_AUTHORIZED_NOW=NO              # 须 Ready 后由队长手工 squash
MERGE_AFTER_READY=YES                # tip 仍为 f77959b… 且 checks 绿时可合
WAVE_C_DONE=NO                       # 本合入不算 T04 Wave C Done
FORMAL_RETRIEVAL_METRICS=NOT_AUTHORIZED
T07_FIVE_REAL_RUNS=NOT_AUTHORIZED
Q001_MATERIAL_STATUS=AWAITING_CONTROLLED_DELIVERY
T07_REAL_RUN_STATUS=HOLD
KEEP_PR_OPEN=YES
```

**#47 观察（2026-08-13 队长 merge gate recheck）：**
- 已 Ready；固定 SHA `f77959b…` tip **未变** → 既有 Gate A PASS **仍有效**。
- 阻断：`behind=3 / diverged`（`require_up_to_date=true`）→ **现在不能 squash**。
- **T04** 须普通 merge `upstream/integration/2026-08-10`（勿 force-push）→ CI 绿 → **@Yqqxz 对新 tip 快速确认 Gate A** → @队长按**新 tip** squash。
- T01 **不**改 `app/rag/**`、**不**代 merge #47。

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
1. T04: t04/c-retrieval-hit-interface Draft PR          ← 已开 #47
2. T01: 对 T04 PR 准确 HEAD 做 semantic signoff         ← 门 A DONE PASS
3. Captain: Gate A 技术审 PASS + 授权 Ready；队员转 Ready ← 已 Ready，tip 未变
4. Captain: tip=f77959b… 时手工 squash → integration   ← 进行中（T01 不 merge）
5. T07: 后续受控运行分支从最新 integration 创建/merge
6. Q001 真实文献包受控交付 → T04 loader/chunk/index/provenance
7. T01: 对实际 Q001 hits / EvidenceBundle 做语义签字   ← 门 B WAIT
8. 五题材料与全部门禁齐备后，T07 才可申请五题真实运行
```

当前：**门 A = PASS**（PR #47 已 MERGED，2026-08-14）。  
当前：**门 B1 = PASS**（PR #59 @ `cf65aa8…`；接口语义）。  
当前：**门 B final 未触发**（`Q001_MATERIAL_STATUS=AWAITING_CONTROLLED_DELIVERY`）。  
当前：**Wave C Done = NO**。

## 3. 门 A — T04 `retrieve_hits` 接口语义签字检查表

在 T04 Draft PR 发布且六项 CI 绿、模块测/全仓回归通过后，T01 对**该 PR 准确 HEAD**核对：

| # | 检查项 | 结果 | 依据 |
|---|---|---|---|
| A1 | 分支/基线 | PASS | `t04/c-retrieval-hit-interface`；`behind_by=0` vs `integration/2026-08-10`；仅 1 commit |
| A2 | 签名 | PASS | `retrieve_hits(query, filters=None, source_scope="all") -> tuple[RetrievalHit, ...]` |
| A3 | 旧路径不变 | PASS | 同核 + 定向测覆盖 signature/list/fallback；legacy `EvidenceCard` 路径保留 |
| A4 | 同核 | PASS | 二者均调 `_retrieve_ranked()`；单次无重复 embed/rerank |
| A5 | 返回形态 | PASS | 确定序 `tuple`；空结果 `()` 且不调 rerank |
| A6 | 无损字段 | PASS | quote / score+kind / type+role / `SourceLocator` / 64-hex hash / title / doi\|url / metadata 袋 |
| A7 | provenance | PASS | type/role/locator/hash 来自持久 metadata；缺则 `RetrievalError`；题册不靠文件名升格为 paper |
| A8 | fail-closed | PASS | 缺 quote/locator/hash/identity/type·role/source_id → 整批失败，无部分成功 |
| A9 | 题册边界 | PASS | `BOOKLET` + `QUESTION_SOURCE` 可识别且非 `PAPER`；scientific `supports` 仍由 T01 消费侧 `BOOKLET_EXCLUDED` |
| A10 | 路径所有权 | PASS | 仅 `app/rag/evidence.py`、`app/rag/retriever.py`、`tests/rag/test_retrieve_hits.py`；未改 `app/evidence/**` |
| A11 | 指标边界 | PASS | PR 声明正式指标/五题运行未授权；`FORMAL_METRICS_CLAIMED=false` |

**签字输出（门 A，已填）：**

```text
T01_T04_RETRIEVE_HITS_SEMANTIC_SIGNOFF=PASS
PR=#47
REVIEWED_HEAD_SHA=f77959b43f7f520119070181011e0d0713425cdd
BOOKLET_AS_SUPPORTS=FORBIDDEN_CONFIRMED
FORMAL_METRICS_CLAIMED=false
BLOCKING_FINDINGS=NONE
SIGNOFF_OWNER=Yqqxz
SIGNOFF_DATE=2026-08-12
READY_AUTHORIZED=YES
MERGE_AUTHORIZED_NOW=NO
MERGE_AFTER_READY=YES
WAVE_C_DONE=NO
```

### 3.1 Gate A 转换契约（T04 `RetrievalHit` → T01 `EvidenceCardContract`）

门 A 确认：**接口足以无损承载** T01 所需身份与 provenance；下列为下游适配义务（非 T04 本 PR blocker）：

| T04 `RetrievalHit` | T01 `EvidenceCardContract` / Bundle | 备注 |
|---|---|---|
| `quoted_text` | `quoted_text` | 必须原样；禁改写 |
| `source_locator` | `locator` dict | 有 `page`/`section` 时可直接用；仅有 `document_id`/`chunk_id` 时适配器须映射为 T01 认可键（`document`/`chunk`），否则 `incomplete_support_provenance_fields` 会判 locator 缺失 |
| `content_hash`（64-hex） | `content_hash` | 已 fail-closed；勿截断 |
| `source_type=paper\|web\|dataset` | 同名 Literal | `booklet` → **`question_booklet`**；`unknown` 不得伪装为 scientific support |
| `source_role` | （保留于 metadata / 审计） | 题册须保持 `question_source` |
| `metadata["source_id"]` | `source_id` | `retrieve_hits` 已要求非空 |
| `chunk_id` / hash | `evidence_id` | 由适配器稳定派生；禁 `booklet_excerpt_Q*` |
| `doi` / `url` | `doi` / `url` | hit 上可选；**supports** 缺一则 T01 `INCOMPLETE_PROVENANCE` BLOCK |
| `metadata["authors"]` 等 | `authors` | **非** `RetrievalHit` 一等字段；须由 loader 写入 metadata；缺则 supports BLOCK（门 B / loader 责任） |
| （无） | `ClaimEvidenceLink` | T01/T07 组 Bundle 时绑定；非 T04 返回物 |
| （组 Bundle 后） | `precheck_bundle_for_validation(...).gate.passed` | 门 B 材料级验收；门 A 不替代 |

**无 T01 semantic blocker** 阻止本接口合并路径上的门 A 签字。  
`precheck.gate.passed=true` **不得**仅凭门 A 宣称——须门 B（Q001 真实包）后核验。

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

### 4.1 门 B 到货操作清单（预写；材料未到前不得执行签字）

**触发条件（全部满足才开始）：**

1. 队长 `@liuyanbo12` 已受控交付 Q001 包（含 manifest / license / bytes hash）  
2. T04 `@YHY0728` 已完成 loader/chunk/index/provenance，并给出可复现命令与 manifest commit  
3. 材料**不是**题册 / `tests/rag/fixtures/**` / provisional gold  

**到货后逐步核验（T01 只读消费，不改 `app/rag/**`）：**

| 步 | 动作 | 失败则 |
|---|---|---|
| 1 | 核对 manifest 路径、document ID、原始 bytes SHA-256+size、license/access | 停止，报队长 |
| 2 | 确认包内无 `sjtu-booklet.pdf` 充当 scientific source | FAIL B1/B8 |
| 3 | 用 T04 提供的命令取出 `retrieve_hits`（或等价 hits 导出） | 记录 HEAD/命令 |
| 4 | 抽检每条 hit：`quoted_text`、`source_locator`、`content_hash`、`source_type`/`source_role`、`metadata.authors`、`doi`\|`url` | 缺字段 → FAIL B2–B5 |
| 5 | 投影为 `EvidenceCardContract`（见 §3.1）；`booklet`→`question_booklet`；禁伪造 authors/doi | 适配错误自修，不改 T04 |
| 6 | 组 `EvidenceBundle` + `ClaimEvidenceLink`；`question_booklet_hits=0` | FAIL B6/B8 |
| 7 | `ValidationContext = build_validation_context_from_bundle(...)` | 防字段丢失 |
| 8 | `precheck = precheck_bundle_for_validation(...); assert precheck.gate.passed` | FAIL B7 |
| 9 | 确认未宣称正式 retrieval 指标 / 未跑五题真实运行 | B9 |
| 10 | 填写门 B 签字块并回帖相关 PR / 通知队长与 T07 | 仅 PASS 后 |

**门 B 判定速查（supports）：**

```text
PASS 仅当：quote 可核验 + locator 有效 + authors 非空 + (doi|url) + content_hash
     + links 无静默冲突 + precheck.gate.passed + booklet 未进 supports
WAIT 若材料/manifest/T04 loader 任一未齐
FAIL 若题册/fixture/metadata-only/缺 provenance/precheck 失败
```

## 4.2 门 B1 — frozen `chunks.jsonl` 适配器接口语义（非 Gate B final）

T04 Draft PR [#59](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/59)。  
请求审查 SHA：`3c7230b725360383cf9bcf56358b00bbaac0a97e`（父提交）。  
**实际签字 SHA（当前 tip + CI 绿）：** `cf65aa8eeff25900278f52a8017b55dc17099b20`（相对父提交仅加强 production 门禁，不削弱 B1 字段契约）。

| # | 检查项 | 结果 | 依据 |
|---|---|---|---|
| B1-1 | 路径所有权 | PASS | 仅 `app/rag/frozen_chunk_builder.py` + `tests/rag/test_frozen_chunk_builder.py`；未改 `app/evidence/**` |
| B1-2 | 身份 | PASS | `chunk_id` / `document_id`/`doc_id` 一致；重复 ID fail-closed |
| B1-3 | quote | PASS | `text` 与 `metadata.quoted_text` 必等且非空 |
| B1-4 | locator | PASS | 必为 `SourceLocator`；与 document/chunk 身份一致；冲突 fail-closed |
| B1-5 | content hash | PASS | 完整 64-hex；别名不一致 fail-closed；文件级 `expected_sha256` 不匹配 fail-closed |
| B1-6 | type/role | PASS | 仅 `SourceType`/`SourceRole` 枚举；非法值 fail-closed；不靠文件名升格 |
| B1-7 | provenance 袋 | PASS | `origin` / `custodian` / `license_or_authorization` 必填非空 |
| B1-8 | fake / production | PASS | fake embedder 不能 `production=true`；tip 另要求队长授权对象 |
| B1-9 | 题册 | PASS（下游） | booklet 不升格为 paper；**production** 路径强制 `paper`+`external_retrieval`；scientific `supports` 仍由 T01 `BOOKLET_EXCLUDED` |
| B1-10 | 指标 / Provider | PASS | `real_embedding_calls=0` / `provider_calls=0` / `Gate B2 executed=false` |
| B1-11 | Gate B final | **WAIT** | 167/5 为**测试合成**记录（`Q001_EVIDENCE_*.pdf`）；非队长受控 Q001 包 |

**非阻塞（Gate B / production 材料责任，不挡 B1）：**

- `load_frozen_chunks` **不**强制 `authors` 或真实 `doi`\|`url`；仅 `production=true`（tip）才拒 placeholder / 缺 authors。
- 测试夹具使用 `doi/url/provenance=UNKNOWN`。T01 `incomplete_support_provenance_fields` 会把非空 `"UNKNOWN"` 当成已填——**正式包不得带 placeholder**；T07 不得把 B1 测试夹具当 scientific supports。
- locator 键为 `document_id`/`chunk_id`；T07 投影须映射为 `document`/`chunk`（见 `t07_hit_to_bundle_adapter.md`）。

**签字输出（门 B1，已填）：**

```text
T01_T04_GATE_B1_SEMANTIC_SIGNOFF=PASS
PR=#59
REQUESTED_HEAD_SHA=3c7230b725360383cf9bcf56358b00bbaac0a97e
REVIEWED_HEAD_SHA=cf65aa8eeff25900278f52a8017b55dc17099b20
FROZEN_CHUNKS_SHA256=205b7e0c44805fe568cd9d20cd5760862f906b5be4453ecb011deca7d9d14d46
BOOKLET_AS_SUPPORTS=FORBIDDEN_CONFIRMED
FORMAL_METRICS_CLAIMED=false
GATE_B2_EXECUTED=false
GATE_B_FINAL=BLOCKED
BLOCKING_FINDINGS=NONE
NON_BLOCKING=authors/doi_or_url_not_required_until_production; test_UNKNOWN_placeholders
SIGNOFF_OWNER=Yqqxz
SIGNOFF_DATE=2026-08-14
READY_AUTHORIZED=false
MERGE_AUTHORIZED=false
```

## 5. 停止条件（T01 必须报停）

出现任一项立即停止并报告队长：跨 owner 改路径、破坏性 Schema、真实密钥、许可/再分发不明、源 bytes/hash 不一致、题册/fixture/provisional gold 充当正式 evidence、**T01 gate 未通过**、材料未验收前跑 provider 或宣称正式指标。

## 6. 自我审查（2026-08-12，Gate A）

| 项 | 结果 |
|---|---|
| 是否已实现/修改 `app/rag/**` | **否**（正确：属 T04） |
| 是否对准确 HEAD `f77959b…` 给门 A PASS | **是** |
| 是否已对未交付 Q001 包给门 B final PASS | **否**（正确：BLOCKED） |
| 是否对 #59 Gate B1 接口给 PASS | **是**（tip `cf65aa8…`；非 Ready/Merge） |
| 是否把 Wave C Done 当作门 A 通过 | **否**（`WAVE_C_DONE=NO`） |
| 是否由 T01 擅自 merge #47 | **否**（等队长 `MERGE_AFTER_READY` squash） |
| 是否保持正式指标 / 五题真跑未授权 | **是** |
| 下一步 | 等队长按固定 SHA squash 合入 #47；等 Q001 → 门 B |

## 7. 相关文档

- 既有 T07 precheck 语义：`docs/modules/T01/t07_evidence_context_acceptance.md`
- T07 hit→Bundle 适配：`docs/modules/T01/t07_hit_to_bundle_adapter.md`
- Wave C handoff：`docs/modules/T01/handoff.md`
- Owner 状态板：`docs/modules/T01/owner_status_board_2026-08-12.md`
- T08 证据读口（另 PR #43，与本授权正交）
