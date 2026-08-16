# T08 × T01 生产证据读端口接口

状态：`WIRED_ON_INTEGRATION_TIP`

日期：2026-08-16

分支：`codex/t08-b-t01-production-read-port`

T01 真源：`upstream/integration/2026-08-10` 已合并 PR
[#43](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/43)
`app/evidence/read_port.py`。

T08 只消费该公开 callable，不打开 T01 SQLite schema，不扫描
`evidence_cards.json`、workflow 临时目录或旧 exports。

---

## 1. `get_evidence_bundle`

T01 生产只读入口。T08 默认 composition 通过
`ProductionOwnerContractAdapter` 调用本函数。

```text
get_evidence_bundle(*, run_id: str, question_id: str, store=None) -> EvidenceBundle
```

参数：

- `run_id`：上游 pipeline 运行 ID。必须与 Job 的 `upstream_run_id` 一致。
- `question_id`：题目 ID。必须与 Job 的 `question_id` 一致。
- `store`：仅 T01 / 测试注入。T08 生产路径不传，使用 T01 默认 store。

返回：

- 通过 hash 与 Schema 重验的 `EvidenceBundle`。
- 不得把空 bundle、fixture 或旧缓存包装成成功。

异常：`EvidencePortError`，稳定 `category` 与 `retryable` 如下。

| category | retryable | T08 HTTP | T08 code |
| --- | --- | --- | --- |
| `not_found` | false | 404 | `UPSTREAM_RESOURCE_NOT_FOUND` |
| `not_ready` | false | 409 | `UPSTREAM_RESOURCE_NOT_READY` |
| `invalid_contract` | false | 503 | `UPSTREAM_CONTRACT_INVALID` |
| `identity_mismatch` | false | 409 | `UPSTREAM_IDENTITY_MISMATCH` |
| `conflict` | false | 409 | `UPSTREAM_RESOURCE_CONFLICT` |
| `retryable_upstream_failure` | true | 503 | `UPSTREAM_READ_FAILED` |
| `non_retryable_upstream_failure` | false | 503 | `UPSTREAM_READ_FAILED` |
| `unavailable` | false | 503 | `UPSTREAM_READ_FAILED` |
| 未知 category | false | 503 | `UPSTREAM_CONTRACT_INVALID` |

未知 category 按非法契约失败关闭，避免 T08 猜测 T01 新语义。

---

## 2. `ProductionOwnerContractAdapter`

默认生产适配器。继承 T07 问题清单读取；覆盖证据读取；T02 versions/diff
继续 fail-closed。

### `__init__(questions_path, *, evidence_reader=None)`

组装 T07 问题源与 T01 读函数。

参数：

- `questions_path`：T07 `QuestionItem` JSON 路径。
- `evidence_reader`：可选注入，签名必须是
  `(*, run_id, question_id) -> EvidenceBundle`。缺省绑定
  `app.evidence.read_port.get_evidence_bundle`。

返回：适配器实例。不在构造时打开 T01 数据库。

### `get_evidence_bundle(*, run_id, question_id)`

调用 T01 公开端口，并把 owner 异常映射为 T08 `OwnerReadError`。

参数：

- `run_id`：已绑定的上游运行 ID。
- `question_id`：当前 Job 的题目 ID。

返回：

- 再次 `EvidenceBundle.model_validate` 后的副本。
- 校验失败视为 `invalid_contract`，不透传原始对象。

异常：

- `OwnerResourceNotFound`：T01 `not_found`。
- `OwnerIdentityMismatch`：T01 `identity_mismatch`。
- `OwnerContractInvalid`：非法契约或未知 category。
- `OwnerReadFailure`：`not_ready` / `conflict` / 上下游故障 / `unavailable`。

禁止：

- 读取 T01 私有表、绝对路径或异常原文。
- 用文件是否存在推断证据已就绪。
- 跨 `run_id` / `question_id` 回退到另一题的 bundle。

### `list_questions()`

沿用文件系统 T07 源。缺文件 → `OwnerContractUnavailable`；坏 JSON →
`OwnerContractInvalid`。

### `list_plan_versions()` / `get_version_diff()`

T02 生产读端口尚未冻结。继续抛 `OwnerContractUnavailable`，HTTP 503
`UPSTREAM_CONTRACT_UNAVAILABLE`。不得用 T01 store 或 fixture 冒充版本历史。

---

## 3. `OwnerReadFailure`

带稳定 category 与 retry 策略的脱敏失败。HTTP 层只映射这两个字段，
不序列化 T01 异常消息。

### `__init__(component, category, *, retryable)`

参数：

- `component`：例如 `T01 EvidenceBundle`。
- `category`：T01 原 category，原样进入 `details.category`。
- `retryable`：是否可重试；必须与 T01 `EvidencePortError.retryable` 一致。

返回：异常实例。`str(exc)` 只含 component 与 category。

---

## 4. `GET /api/v1/jobs/{job_id}/evidence`

读取当前调用方任务的 T01 证据投影。

前置：

1. `X-API-Key` 通过服务端鉴权。
2. Job 属于当前 actor，否则 403 `FORBIDDEN`。
3. Job 已绑定 `upstream_run_id`，否则 409 `UPSTREAM_RESULT_NOT_READY`。

成功 200：

```json
{
  "job_id": "c4ef4580-e351-4b44-b9a2-19edac5ec977",
  "bundle_id": "bundle-run-owner-1",
  "items": [
    {
      "evidence_id": "ev-001",
      "source_id": "src-001",
      "source_type": "paper",
      "title": "Catalyst stability",
      "quoted_text": "Catalyst A remained stable after 100 h.",
      "locator": {"page": 7, "section": "Results"},
      "authors": ["Example"],
      "year": 2024,
      "doi": "10.1000/example",
      "url": "https://example.invalid/paper",
      "content_hash": "sha256:owner-evidence-001",
      "domain": "materials science",
      "verification_status": "verified",
      "relations": [
        {
          "claim_id": "claim-001",
          "relation": "supports",
          "confidence": 0.91,
          "validation_status": "valid"
        }
      ]
    }
  ],
  "truncated": false,
  "truncation_reason": null,
  "availability": "available"
}
```

字段规则：

- `quoted_text`、`locator`、`authors`、`year`、`doi`/`url`、`content_hash`、
  支持关系必须来自 T01 bundle，T08 不补全。
- `availability=available` 只表示本次读到合法 bundle，不表示质量门通过，
  也不表示 `actual_execution`。
- 低置信或截断必须保留 `truncated` / `truncation_reason`，不得静默丢掉。

PowerShell 示例：

```powershell
$headers = @{ "X-API-Key" = $env:SAGE_API_KEY }
Invoke-RestMethod -Headers $headers `
  "$env:SAGE_API_BASE/api/v1/jobs/$env:JOB_ID/evidence"
```

空 store 或尚未写入的 identity 返回 404，不是 200 空列表。空列表只允许
T01 返回合法但 `evidences=[]` 的 bundle。

---

## 5. `_owner_call`

v1 路由共用的 owner 异常映射。

### `_owner_call(component, operation)`

执行 `operation()`，把 T08 adapter 异常变成统一 `ErrorResponse`。

参数：

- `component`：用于 `UPSTREAM_CONTRACT_UNAVAILABLE` 文案。
- `operation`：无参 callable，内部再调 adapter。

返回：owner 成功对象。

异常映射见第 1 节。响应不得包含绝对路径、SQLite 文件名、密钥或 T01
内部表名。

---

## 6. 默认 composition

`create_app()` 在未注入 `upstream_read_port` 时使用
`ProductionOwnerContractAdapter(_questions_path())`。

含义：

- 问题列表走 T07 文件源。
- 证据走 T01 默认 SQLite（`T01_EVIDENCE_STORE_PATH` 或
  `exports/evidence_bundle_store/evidence_bundles.sqlite3`）。
- T02 / T03 / T05 / T06 仍 fail-closed。
- 测试必须注入 fixture adapter，或把 `T01_EVIDENCE_STORE_PATH` 指到临时
  空库并调用 `reset_default_store_for_tests()`。

---

## 7. 仍未接通

| 接口 | 当前生产结果 |
| --- | --- |
| `GET /api/v1/jobs/{job_id}/versions` | 503 `UPSTREAM_CONTRACT_UNAVAILABLE` |
| `GET /api/v1/jobs/{job_id}/versions/diff` | 503 `UPSTREAM_CONTRACT_UNAVAILABLE` |
| `POST /api/v1/jobs/{job_id}/feedback` | 503 `UPSTREAM_CONTRACT_UNAVAILABLE` |
| `GET /api/v1/jobs/{job_id}/feedback/{id}` | 503 `UPSTREAM_CONTRACT_UNAVAILABLE` |
| `GET /api/v1/jobs/{job_id}/report` | 503 `CANONICAL_REPORT_UNAVAILABLE` |

T08-C `owner_composition.py` 尚未包含本 T01 适配器。合并 Wave C 前应先
同步本端口，避免两套默认 adapter。

---

## 8. 验收命令

```powershell
python -m pytest -q tests/api/test_v1_read_models.py
python -m pytest -q tests/api
```

必须覆盖：只调用公开端口、重启后读 SQLite、全部 T01 category 稳定映射、
错误正文不含路径或密钥。
