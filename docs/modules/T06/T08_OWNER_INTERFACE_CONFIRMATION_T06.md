# T06 → T08 Owner Interface Confirmation (PR #39)

Status: `T06_OWNER_CONFIRMATION=ACCEPTED_WITH_PORT`

Date: 2026-08-11  
Owner: T06 / `ZBY-06`  
Reviewed Head (implementation): PR #36 `t06/b-multimodal-core`

## Scope answered

Group ask: **T06 — 多模态详情、bbox、单位、置信度及来源**

## Frozen public ports

```python
from app.multimodal.read_port import (
    list_multimodal_artifacts,
    list_multimodal_details,
    put_multimodal_artifact,
)

list_multimodal_artifacts(
    *,
    run_id: str,
    question_id: str,
    version_id: str,
) -> list[MultimodalArtifact]
```

- Import path: `app.multimodal.read_port.list_multimodal_artifacts`
- Schema: `app.contracts.multimodal.MultimodalArtifact` (+ detail DTO `MultimodalDetailView`)
- Policy / schema version: `t06.multimodal_store.v1` / `t06.multimodal_detail.v1`
- Durable root: `exports/multimodal_store` or `T06_MULTIMODAL_STORE_DIR`
- `MultimodalQueue.snapshot()` remains process-local only — **not** production truth

## T06-02 source / preview rules

- Absolute `provenance.source_path` is **redacted** on read to `t06-source:<id>/<basename>...`
- `public_source.source_id` = `sha256:<digest of raw locator>`
- `public_source.source_label` = `<basename>#page=N`
- `public_source.preview_artifact_id` = `artifact_id` (controlled; T08 must not open raw FS paths)
- Coordinate space: `pdf_user_space` | `image_pixel` | `csv_placeholder` | `unknown`
- Low-confidence: owned by T06 (`confidence` + `validation_status` + `needs_human_review`); threshold constant `T06_LOW_CONFIDENCE_THRESHOLD=0.70`. T08 must not invent another gate.

## Errors (for T08 HTTP mapping)

| category | retryable | when |
| --- | --- | --- |
| `invalid_contract` | no | bad identity tokens |
| `identity_mismatch` | no | stored envelope identity ≠ request |
| `unavailable` | no | corrupt store entry |
| empty list | n/a | no artifacts for identity (success, not 404) |

## Shared X-* answers (T06)

- **X-01**: Accept binding `run_id` + `question_id` + `version_id`. T08 may resolve `upstream_run_id` → `run_id` before calling; T06 verifies tokens and rejects mismatch. Empty result ≠ wrong identity.
- **X-02**: Stable import above; missing optional fields stay schema defaults/`None`; identity mismatch fails closed.
- **X-03**: Categories above; no secret paths in `details`.
- **X-04**: File-backed store survives process restart.
- **X-05**: Agree — T08 thin adapter only; T06 owns domain truth.

## Reply template (filled)

```text
Owner / 任务：T06 Multimodal
确认项 ID：T06-01, T06-02 (+ X-01..X-05 as applicable)
结论：接受
唯一公共 import path：app.multimodal.read_port.list_multimodal_artifacts
方法签名：list_multimodal_artifacts(*, run_id: str, question_id: str, version_id: str) -> list[MultimodalArtifact]
Schema / policy version：t06.multimodal_store.v1 ; detail t06.multimodal_detail.v1 ; MultimodalArtifact from app.contracts.multimodal
identity 校验规则：三者必填且匹配 [A-Za-z0-9._:-]{1,128}；读时校验 envelope identity；不允许静默修正
持久化与重启语义：exports/multimodal_store (or T06_MULTIMODAL_STORE_DIR) JSON envelopes；重启后按 identity 可读
错误类型与 retryable：invalid_contract/identity_mismatch/unavailable → not retryable；empty list = success
权限规则：read port 不暴露绝对路径；预览仅用 preview_artifact_id；无用户隔离字段时由 T08 actor 层控制下载
代表性非 Mock 输入/输出：tests/multimodal/test_read_port.py；put then list preserves bbox/units/confidence/validation_status
owner reviewer：T05 (pairing)
补充限制：完整 data 允许返回；若 payload 过大可改用 list_multimodal_details 同等字段；真实 VL chart digits 仍受 B016 凭证门禁，与本 read port 正交
```
