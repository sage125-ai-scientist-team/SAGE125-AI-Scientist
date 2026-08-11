# T01 → T08 Owner Interface Confirmation（Evidence 持久读口）

**Status:** `T01_OWNER_CONFIRMATION=ACCEPTED_WITH_PORT`（Draft PR 落地；合入待队长批准）  
**Date:** 2026-08-11  
**Owner / 实施人:** T01 / `Yqqxz`  
**配对:** T04  
**对应协调 PR:** [#39](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/39)

## 1. 确认结论

| 项 | 答复 |
|---|---|
| T01 小 PR 是否批准 | **请求队长批准合入**；本分支已实现并开 Draft（非自行 Ready/Merge） |
| 权威存储位置 | SQLite 文件：`exports/evidence_bundle_store/evidence_bundles.sqlite3`；可用环境变量 `T01_EVIDENCE_STORE_PATH` 覆盖 |
| 唯一公共 import path | `app.evidence.read_port.get_evidence_bundle` |
| 状态/错误语义 | **全部接受**（见 §3） |
| owner 实施人 | `Yqqxz` |
| 预计合入 PR | 本小 PR（`t01/evidence-bundle-store`）；合入前 T08 继续 unavailable |

## 2. 冻结公共端口

```python
from app.evidence.read_port import (
    get_evidence_bundle,
    save_evidence_bundle,
    mark_evidence_pending,
    mark_evidence_failed,
    EvidencePortError,
    SqliteEvidenceBundleStore,
)

get_evidence_bundle(*, run_id: str, question_id: str) -> EvidenceBundle
```

- Schema：`app.contracts.evidence.EvidenceBundle`
- Policy / store schema：`t01.evidence_bundle_store.v1`
- Identity：`run_id + question_id`（唯一）
- 写侧：T01 在生成并校验 Bundle 后调用 `save_evidence_bundle`（或等价 store 方法）
- T08：**只**薄适配 `app/api/**`；**禁止**扫描 `evidence_cards.json` / workflow 临时目录 / 旧 exports

### Protocol（实现类 `SqliteEvidenceBundleStore`）

```python
class EvidenceBundleStore(Protocol):
    def mark_pending(self, *, run_id: str, question_id: str) -> None: ...
    def save_bundle(self, *, run_id: str, question_id: str, bundle: EvidenceBundle) -> EvidenceBundle: ...
    def get_evidence_bundle(self, *, run_id: str, question_id: str) -> EvidenceBundle: ...
```

另提供 `mark_failed(...)` 以区分稳定失败与 pending。

## 3. 错误语义（供 T08 HTTP 映射）

| category | retryable | 何时 |
|---|---|---|
| `not_found` | no | 无记录 |
| `not_ready` | no | `pending` |
| `non_retryable_upstream_failure` | no | `failed`（含 owner failure_code） |
| `invalid_contract` | no | identity 非法 / Schema 坏 / hash 篡改 / 空 bundle |
| `identity_mismatch` | no | 存贮 identity 与请求不一致 |
| `conflict` | no | 同 identity 不同 payload |
| `retryable_upstream_failure` | yes | SQLite/IO 瞬时故障 |
| `unavailable` | no | 未知 status |

## 4. 最小验收（tests）

`tests/evidence/test_evidence_bundle_store.py` 覆盖：

1. 重启恢复（新 store 实例同文件）  
2. 跨 question fail-closed  
3. 幂等与冲突  
4. hash 篡改拒绝  
5. pending / failed / not_found 区分  
6. 五并发同/异 payload  
7. quote/locator/relation/confidence/hash/truncation 不丢  
8. 错误消息不含绝对路径  

## 5. 边界

- 不改 `app/workflow/pipeline.py`、`app/api/**`、其他 owner 路径  
- 不把 fixture/Mock 当生产成功响应  
- #35 Wave C 与本 read port 正交；本 PR 仅持久化读/写口  
- Ready/Merge 须队长明确授权  

## 6. 回复模板（已填）

```text
Owner / 任务：T01 Evidence
确认项 ID：T01-01, T01-02 (+ X-01..X-05)
结论：接受（ACCEPTED_WITH_PORT；Draft 待队长合入授权）
唯一公开 import path：app.evidence.read_port.get_evidence_bundle
函数签名：get_evidence_bundle(*, run_id: str, question_id: str) -> EvidenceBundle
Schema / policy version：EvidenceBundle + t01.evidence_bundle_store.v1
identity 校验：run_id+question_id；非法 → invalid_contract
权威存储位置：exports/evidence_bundle_store/evidence_bundles.sqlite3 或 T01_EVIDENCE_STORE_PATH
是否接受状态/错误语义：是
owner 实施人：Yqqxz
预计合入 PR：t01/evidence-bundle-store（Draft）
```
