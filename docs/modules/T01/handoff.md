# T01 最终 Handoff（Code Freeze）

**Status:** FINAL handoff 包（模块交付说明）。  
**PR #35 状态:** 仍为 OPEN / Draft；**未经队长明确授权，不 Ready、不 Merge**。  
**本文件用途:** 供队长在干净环境按命令复现验证；不宣称已合入 integration。

> `handoff_draft.md` 已被本文件取代，仅作历史草稿保留。

---

## 1. 模块目的

将检索得到的文献片段升级为可追溯证据系统：保留原文 quote、locator、DOI/URL、作者、内容哈希与 claim–evidence 支持关系；阻断题册/元数据冒充科学支撑；Wave C 增加冲突双侧保留、撤稿门禁、确定性 content-hash 缓存与 125 JSON 序列化信封。

## 2. 路径与边界

| 项 | 值 |
|---|---|
| Owner paths | `app/evidence/**`, `app/contracts/evidence.py`, `tests/evidence/**`, `docs/modules/T01/**`, `docs/contracts/T01.md` |
| Forbidden | `app/workflow/pipeline.py`（T02 接入） |
| Upstream | T04 retrieval |
| Downstream | T02 / T03 / T07 / T08 |
| Pairing 边界 | `PAIRING_STRUCTURE=STRUCTURE_OK`；`ACTUAL_RELEVANCE_GOLD=NOT_READY`；`FORMAL_RETRIEVAL_METRICS_AUTHORIZED=false` |

## 3. 入口与关键函数（接口索引）

契约说明：`docs/contracts/T01.md`  
Wave C 函数级接口：`docs/modules/T01/INTERFACE_WAVE_C.md`  
T07 precheck 语义：`docs/modules/T01/t07_evidence_context_acceptance.md`

### 3.1 Wave A/B 核心

| 函数 | 作用 |
|---|---|
| `build_evidence_bundle(...)` | 构建受控 EvidenceBundle（quote/locator/hash/token 预算） |
| `check_claim_evidence_support(...)` / `check_bundle_support(...)` | 事实—证据支持检查（题册/假 ID/元数据/跨域等） |
| `build_t08_citation_payload(...)` / `render_citation_markdown(...)` | 可点击引用与 T08 payload |
| `run_q028_regression()` | Q028 契约层回归（非 live pipeline） |
| `compute_metrics(...)` / `generate_wave_b_metrics_artifacts(...)` | 黄金集指标产物生成 |
| `precheck_bundle_for_validation(...)` | T07 用预检；**判定字段为 `precheck.gate.passed`** |
| `evidence_card_to_validation_wire(...)` / `build_validation_context_from_bundle(...)` | 校验侧序列化上下文 |

### 3.2 Wave C 增量

| 函数 | 作用 |
|---|---|
| `run_quality_gate(...)` | 冲突双侧保留 + 撤稿/撤回阻断（与 disposition 无关） |
| `detect_conflicts_preserving_both_sides(...)` | 冲突检测；`prior_links`/`expected_conflict_claim_ids` 可标静默覆盖 |
| `ContentHashCache.get_or_compute(...)` | 命中缓存时不调用 `hash_fn` |
| `deterministic_bundle_digest(...)` / `assert_same_input_stable_evidence_set(...)` | 同输入集合稳定性 |
| `build_output_envelope_v125(...)` / `dumps_output_envelope(...)` | 125 可序列化输出信封 |
| `build_separated_signoff_package(...)` / `write_separated_signoff_artifacts(...)` | 契约回归与人工原文签字分离产物 |

导入面：`from app.evidence import ...`（见 `app/evidence/__init__.py` 的 `__all__`）。

## 4. 配置与数据

| 资源 | 路径 |
|---|---|
| Wave B 黄金夹具 | `docs/modules/T01/evidence_gold_set.json`（30 条；fixture 精度见 metrics） |
| Wave C 真实签字源 | `docs/modules/T01/eval_gold/v1/`（冻结 XML + pairs） |
| 指标产物 | `docs/modules/T01/metrics.json`, `domain_audit_12.json` |
| Wave C 性能说明 | `docs/modules/T01/performance_report_wave_c.md` |
| API 样例 | `docs/modules/T01/api_examples_wave_c.json` |
| 分离签字包 | `wave_c_contract_regression.md`, `wave_c_human_locator_signoff.md`, `wave_c_signoff_package.json` |

环境：标准 Python 项目依赖即可；**不读取真实 `.env` / 不需要外部 API key** 即可跑 `tests/evidence` 与 Q028/signoff 构建。

## 5. PR 与提交锚点

| Wave | PR | 状态 | 说明 |
|---|---|---|---|
| A | [#7](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/7) | MERGED | 契约 / 红灯 |
| B | [#25](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/25) | MERGED | 核心实现；merge `73ce7c0…`（以 GitHub 为准） |
| C | [#35](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/35) | OPEN Draft | 质量门 / 缓存 / 序列化 / 签字 |

**冻结审查锚点（不得为追 tip 再 rebind）：**

| 锚点 | SHA |
|---|---|
| `reviewed_subject_sha`（T09 审主体） | `344482e481398fd304782b69d62c93f6441c7b6c` |
| 人工签字 artifact commit | `42f5685f49a3cc0427d7f4a9edce87be3b65161e` |
| T09 最终复验时 HEAD | `42f5685f49a3cc0427d7f4a9edce87be3b65161e` |
| T09 结论 | `T01_PR35_FINAL_REVERIFY=PASS`；`CAPTAIN_REVIEW_CANDIDATE=YES`（T09 **不**授权 Ready/Merge） |

**tip 相对签字包的后续提交（仅文档/同步，未改 5 条 eval_gold 源）：**

- `f61f70b…` — T07 EvidenceBundle precheck 验收语义说明  
- merge `upstream/integration` — 同步已合并的 T06 金标包（#29），**未修改 T06 内容**

最终 **integration commit** 在 #35 squash 合并后由队长/GitHub 确定；合并前本栏填写：`PENDING_MERGE_OF_PR_35`。

## 6. 复现命令（PowerShell / 仓库根目录）

```powershell
# 模块单测（本机 2026-08-10：70 passed）
python -m pytest -q tests/evidence

# Q028 契约回归
python -c "from app.evidence.q028_regression import run_q028_regression; print(run_q028_regression().to_dict())"

# 分离签字包（reviewed_subject_sha 应仍为 344482e…）
python -c "from app.evidence.wave_c_signoff import build_separated_signoff_package; p=build_separated_signoff_package(); print(p.reviewed_subject_sha); print(p.human_signoff_complete)"

# 可选：全量与 CI 对齐（耗时更长）
python -m pytest -q
```

### 6.1 本机验证记录（handoff 撰写时）

| 命令 | 结果 | 对应 tip 说明 |
|---|---|---|
| `python -m pytest -q tests/evidence` | **70 passed** | 同步 integration 后、本 handoff 提交前本地跑通 |
| `run_q028_regression()` | `all_passed=True`（S1–S4） | 同上 |
| `build_separated_signoff_package()` | `reviewed_subject_sha=344482e…`；人工签字字段保持已填写状态 | 未 rebind 主体 SHA |

CI（PR #35）：lint / type / unit / integration / security / build 在 tip `f61f70b…` 时均为 SUCCESS（见 GitHub Checks）。同步 merge 后再等一轮 CI。

## 7. 失败处理

| 现象 | 处理 |
|---|---|
| `precheck.gate.passed=False` | 查 quote/locator/provenance/link；题册不得作 scientific `supports` |
| 撤稿来源仍 `supports` | `run_quality_gate` 必失败；修复生命周期或去掉 supports |
| 冲突一侧丢失 | 提供 `prior_links` / `expected_conflict_claim_ids`；不得静默覆盖 |
| 缓存命中仍算 hash | 视为回归；见 `tests/evidence/test_content_hash_cache.py` |
| 人工签字行 provisional/fixture | 不得计入真人原文签字；仅 eval_gold 真实行 |

## 8. 已知限制

1. Live `pipeline.py` 接线由 **T02** 完成；T01 只提供冻结接口与桥接函数。  
2. T07 端到端仍依赖 **T04** `retrieve_hits()` + 非题册真实材料；队长已授权 T04 实施接口，但 **T01 不写 `app/rag/**`**，只做语义 signoff（见 `q001_t04_semantic_signoff.md`）。  
3. Pairing 正式 retrieval 指标 **未授权**（`FORMAL_RETRIEVAL_METRICS_AUTHORIZED=false`）。  
4. `metrics.json` 的 precision 标注为 fixture accuracy，**不是**独立科学标注员分数。  
5. Q028 回归是契约层场景，**不是**人工原文签字样本。  
6. PR #35 在队长授权前保持 Draft。  
7. Q001 真实文献包状态：`AWAITING_CONTROLLED_DELIVERY`；五题真实运行：`HOLD`。

## 9. 回滚

- Wave C 回归：在 integration 上 revert #35 的 squash commit；Wave A/B（#7/#25）保留。  
- 勿 force-push 队友分支；勿 `--admin` 合并。

## 10. 后续 Issue（建议，非本 PR 范围）

1. **门 A**：T04 开出 `t04/c-retrieval-hit-interface` Draft PR 后，T01 对准确 HEAD 做 `retrieve_hits` 语义 signoff。  
2. **门 B**：队长受控交付 Q001 包且 T04 完成 loader/provenance 后，T01 对实际 hits / EvidenceBundle 语义签字。  
3. 独立科学标注精度评估（若队长授权正式指标）。  
4. T02 完成 pipeline 接入后的集成冒烟。  
5. T08 证据持久读口见独立 Draft PR #43（与本 Wave C / Q001 授权正交）。

## 11. Code Freeze 无范围膨胀确认

本 handoff 周期（冻结后）：

- **未**新增公共接口改名/功能面  
- **未**升级依赖  
- **未**修改 `app/workflow/pipeline.py` 及其他任务 owner 实现  
- **仅**同步已合并的 upstream integration（T06 #29）并完成本 handoff 文档  
- Ready/Merge **等待队长授权**
