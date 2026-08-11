# T08 Wave B3：产物、安全与导出

## 运行配置

API v1 默认拒绝匿名访问。使用环境变量配置调用方与 API key：

```bash
export SAGE_API_KEYS_JSON='{"judge":"replace-with-at-least-12-characters"}'
```

请求通过 `X-API-Key` 传递凭证。服务内存中只保存 key 的 SHA-256 摘要；导出幂等键在 SQLite 中也只保存摘要。当前最小限流器为单进程、按 actor 的固定 60 秒窗口，默认每个 actor 60 次请求。API v1 的 POST/PUT/PATCH 请求体上限为 64 KiB。

## Artifact API

```text
GET  /api/v1/jobs/{job_id}/artifacts
GET  /api/v1/jobs/{job_id}/artifacts/{artifact_id}/download
POST /api/v1/jobs/{job_id}/exports
```

导出请求必须包含 `Idempotency-Key`：

```json
{
  "formats": ["json", "markdown", "pdf"]
}
```

可复制的最小调用示例（`JOB_ID` 必须来自当前调用方创建的任务）：

```bash
export SAGE_API_BASE='http://127.0.0.1:8000'
export SAGE_API_KEY='replace-with-configured-key'
export JOB_ID='replace-with-owned-job-id'

curl --fail-with-body \
  -H "X-API-Key: ${SAGE_API_KEY}" \
  "${SAGE_API_BASE}/api/v1/jobs/${JOB_ID}/artifacts"

curl --fail-with-body \
  -X POST \
  -H "X-API-Key: ${SAGE_API_KEY}" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: judge-export-001' \
  --data '{"formats":["json","markdown","pdf"]}' \
  "${SAGE_API_BASE}/api/v1/jobs/${JOB_ID}/exports"
```

若 production composition 尚未注入 owner canonical report，第二个请求应稳定返回
`503 CANONICAL_REPORT_UNAVAILABLE`，不能回退旧导出或 fixture。

产物注册表持久化 `job_id`、`question_id`、actor、受控文件名、MIME、大小、SHA-256、真实性状态和相对路径。列表与下载都校验 job 归属；下载前重新校验根目录边界、文件存在性、大小和 SHA-256，不返回服务器绝对路径。

## Canonical report

JSON、Markdown 和 PDF 只接受 `CanonicalReport`，三种格式共享同一个 `content_sha256`。投影保留问题、版本、假设、方法、证据、Reviewer issue、人工反馈、Validation Gate、执行、多模态、真实性状态和已知限制。

生产应用默认使用 `UnavailableCanonicalReportSource`，因此在上游 canonical projection 未注入时导出明确返回 `503 CANONICAL_REPORT_UNAVAILABLE`，不会用旧文件或 Mock 替代正式结果。集成方应通过 `create_app(canonical_report_source=...)` 注入冻结的 owner adapter。

PDF 优先嵌入 `SAGE_PDF_FONT_PATH` 指定的中文字体，然后查找常见 Noto/Arial Unicode 字体；只有不存在可嵌入字体时才回退到 `STSong-Light`。部署镜像应提供 Noto CJK 字体或显式配置字体路径。

导出写入先在 artifact 根目录下的短路径 `.tmp` staging 文件中完成，再通过同一文件系统内的原子替换发布。canonical report 的 `content_sha256` 已绑定 job/question/run，因此最终目录不重复加入 `job_id`，避免长 Windows checkout 或 pytest 临时目录触发 legacy `MAX_PATH`。底层 `OSError` 统一映射为可重试的 `503 EXPORT_STORAGE_UNAVAILABLE`；响应不包含本地路径，日志保留脱敏后的完整帧链、异常类型、`errno` 与 `winerror`。

## 本轮验收

```text
python -m pytest -q tests/api
python -m pytest -q
pdftoppm -png -r 144 canonical-report-final.pdf final-page
pdfinfo canonical-report-final.pdf
```

代表性 PDF QA 结果：A4、1 页、1 个可点击 DOI 链接、嵌入 `ArialUnicodeMS` 子集，中文、页脚 SHA、`planned` 和 `ACTUAL EXECUTION: NO` 均可见；未发现裸 Markdown、内容越界、异常字距或空白页。
