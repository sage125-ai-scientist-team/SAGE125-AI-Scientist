# T08 Wave B API 回归报告

状态：`IMPLEMENTATION_VERIFIED / NOT_READY`

日期：2026-08-11

审查基线：`d9ffb67ab5b0cf2e25c4a346bf0bef70a8b65485`

实现证据 SHA：`57e8fa2a851acdda87ed469dd3fb7b3ffb36f60c`

Windows CI：`quality-gates` run `31466958039`，6/6 success

分支：`codex/t08-b-delivery-core`

## 1. 本轮目标

本轮针对 PR #39 review 中的 Windows 导出 P1，验证：

- JSON/Markdown/PDF 导出在长临时根目录下不因 staging 路径超过 legacy Windows
  `MAX_PATH` 而失败；
- 底层 `FileNotFoundError` 不再成为裸 500，而是稳定、可重试、无本地路径泄露的
  `503 EXPORT_STORAGE_UNAVAILABLE`；
- 导出成功、幂等、hash、下载权限、篡改拒绝和三格式 canonical fingerprint 仍通过；
- OpenAPI 继续暴露现有路由和统一错误 schema。

本报告已绑定实现提交 `57e8fa2a851acdda87ed469dd3fb7b3ffb36f60c`。该提交已
推送到 PR #39，并在 `windows-latest` / Python 3.12 上通过 lint、type、unit、
integration、security、build 六项检查。owner E2E 与 captain Ready 授权仍未满足，
因此本状态不是 Ready。

## 2. 实际命令与精确结果

### 2.1 导出专项

```text
.venv/bin/python -m pytest -q tests/api/test_v1_artifacts_exports.py -vv

结果：8 passed in 1.47s
```

新增的两个跨平台失败测试：

- `test_export_keeps_temporary_path_within_windows_legacy_limit`；
- `test_export_filesystem_failure_is_fail_closed_and_logs_safe_stack`。

### 2.2 API 全量

```text
.venv/bin/python -m pytest -q tests/api

结果：67 passed in 5.81s
```

### 2.3 lint 与 type contract

```text
.venv/bin/python scripts/eval/wave_a_quality.py lint
结果：{"check":"wave_a_lint","files":3,"failures":[]}

.venv/bin/python scripts/eval/wave_a_quality.py type
结果：{"check":"wave_a_type_contract","failures":[]}
```

### 2.4 全仓回归

```text
.venv/bin/python -m pytest -q

结果：814 passed, 36 skipped, 5 warnings in 14.74s
```

36 个 skip 来自当前 checkout 缺少 `questions_125.json`、原始 booklet PDF，以及
macOS 不支持 Windows junction；5 个 warning 是既有 SWIG/PDF loader
`DeprecationWarning`。本轮未新增测试 skip 或 warning。

### 2.5 OpenAPI 快照检查

```text
OpenAPI: 3.1.0
paths: 27
required_missing: []
ErrorResponse schema: present
```

检查的交付入口包括 `/health`、questions、jobs/run/status、evidence、versions/diff、
feedback、artifacts 和 exports。OpenAPI 存在不代表 owner production adapter 已接通；
未确认的 owner 路由仍按契约返回 503。

## 3. PDF 实际 QA

使用 canonical fixture 生成代表性 PDF 后执行 `pdfinfo`、`pdftoppm -png -r 144`
并查看页面 PNG：

```text
Pages: 1
Page size: A4
File size: 39778 bytes
DOI links: 1
```

页面未发现裁切、重叠、异常字距或空白页；`planned`、
`ACTUAL EXECUTION: NO`、版本、证据 ID 和中文限制均可见。Poppler 输出运行时
fontconfig 缓存不可写 warning，但 PNG 渲染成功且视觉正常；该 warning 未由本轮
代码引入。

## 4. 可复制 curl

启动 API 并配置合法 key 后，可使用
`docs/deployment/T08_WAVE_B3_ARTIFACT_EXPORT.md` 中的 curl 示例列出 artifact 并提交
JSON/Markdown/PDF 统一导出。`JOB_ID` 必须属于当前 key 对应 actor，写请求必须携带
`Idempotency-Key`。

## 5. 跨平台结论边界

- 本轮直接执行环境：macOS 15 / Python 3.14.5；
- 新测试在任意平台模拟 248 字符 legacy Windows 临时路径上限，旧实现稳定红灯、
  新实现转绿；
- 新 head `57e8fa2` 的 GitHub CI 使用 `windows-latest` / Python 3.12，lint、type、
  unit、integration、security、build 六项均成功；
- 当前仓库 workflow 没有 Linux job，本机也未安装 Docker，因此本轮没有新增 Linux
  runner 证据。根据 reviewer 要求，Linux 回归仍需由 T09/队长指定的现有环境补齐，
  不能通过修改 `.github/workflows/**` 越权增加。

## 6. 仍然阻断 Ready 的事项

- T01/T02/T03/T05/T06 owner 确认未齐，生产 feedback 及 canonical read adapters 继续
  失败关闭；
- B016/B017 production owner 全闭环 E2E trace/浏览器证据/视频未生成；
- B014 已绑定同一实现 SHA 与 Windows CI run，但最终 Ready 包仍需对应最终交付 tip；
- PR #39 必须保持 Draft、Open，不得在 captain 授权前转 Ready 或 Merge。
