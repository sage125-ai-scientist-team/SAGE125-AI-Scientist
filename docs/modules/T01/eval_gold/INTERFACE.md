# T01 Eval Gold — 接口文档

> Context7 MCP 当前环境不可用；本接口以仓库内 `scripts/t01/validate_eval_gold.py` /
> `scripts/t01/fetch_eval_gold_sources.py` 源码为准。

## 包路径约定

| 符号 | 路径 | 说明 |
|---|---|---|
| `EVAL_GOLD_ROOT` | `docs/modules/T01/eval_gold/` | 包族根目录 |
| `PACKAGE_V1` | `docs/modules/T01/eval_gold/v1/` | v1 正式评测金标包（当前为脚手架） |
| `VALIDATOR` | `scripts/t01/validate_eval_gold.py` | 结构 / 就绪门禁校验 CLI |

## CLI：`validate_eval_gold.py`

### 函数：`main(argv: list[str] | None = None) -> int`

```text
职责：解析命令行并调度写校验和 / 包校验。
入参：
  argv — 可选 argv；None 时使用 sys.argv[1:]。
出参：
  int — 进程退出码：0 成功；1 业务校验失败；2 路径/文件缺失。
副作用：
  --write-checksums 时改写 manifest.json 与 checksums.sha256。
```

### 函数：`write_checksums(package_dir: Path) -> Path`

```text
职责：回填 provenance.git_commit / pair_count，再生成 checksums.sha256。
入参：
  package_dir — 指向 eval_gold/v1 的目录。
出参：
  Path — checksums.sha256 绝对或相对路径。
约束：
  不把 checksums.sha256 自身列入自洽哈希目标（避免自指漂移）。
  权威摘要文件为 checksums.sha256；manifest.provenance.file_sha256 仅作指针说明。
被哈希文件：
  manifest.json, pairs.json, REPRODUCE.md, CURATION_CHECKLIST.md, pair.example.json
```

### 函数：`validate_package(package_dir: Path, *, require_ready: bool = False) -> int`

```text
职责：校验 manifest / pairs / checksums；脚手架或正式就绪两档。
入参：
  package_dir — 包目录。
  require_ready — True 时要求 ready_for_t09_formal_eval=true。
出参：
  0 → STRUCTURE_OK（脚手架）或 ACTUAL_GOLD_OK（就绪）；
  1 → FAIL（字段/哈希/门禁）；
  2 → 关键文件缺失（由调用方在缺失目录时也可能返回）。
脚手架规则：
  ready_for_t09_formal_eval=false 且 provenance 九项齐全 → STRUCTURE_OK。
正式规则（ready=true）：
  pairs 非空；每条 provisional/synthetic/fixture 均为 false；
  evaluation_tier=actual_gold；quote 非空且禁止 DOI-only。
```

### 函数：`_sha256_file(path: Path) -> str`

```text
职责：流式计算文件 SHA-256。
入参：path — 可读文件。
出参：小写 hex 摘要字符串。
```

### 函数：`_load_json(path: Path) -> dict`

```text
职责：以 UTF-8 读取 JSON 对象。
入参：path — .json 文件。
出参：dict；非对象 JSON 时由 json.loads 抛错。
```

### 函数：`_git_head(repo_root: Path) -> str`

```text
职责：在 repo_root 执行 git rev-parse HEAD。
入参：repo_root — 含 .git 的仓库根。
出参：commit sha；失败时 "unknown"。
```

## CLI 参数

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `--package` | path | `docs/modules/T01/eval_gold/v1` | 包目录 |
| `--write-checksums` | flag | off | 重算 checksums 并刷新 manifest |
| `--require-ready` | flag | off | 强制正式评测就绪 |

## PowerShell 示例（Windows 11）

```powershell
# 脚手架结构校验
python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1

# 重算摘要
python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --write-checksums

# 正式就绪门禁（当前脚手架应失败）
python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --require-ready
```

## 数据契约摘要

### `manifest.json`

| 字段 | 类型 | 脚手架期望 |
|---|---|---|
| `ready_for_t09_formal_eval` | bool | `true`（可供 T09 校验；≠已入正式 corpus） |
| `not_synthetic_provisional_fixture` | bool | `true` |
| `corpus_inclusion_status` | str | 须含 `NOT_CLAIMED` |
| `evaluation_tier` | str | `actual_gold_submitted_for_t09_review` |
| `provenance.*` | object | T09 九项字段均有占位 |
| `explicit_exclusion.harness_gold_path` | str | `docs/modules/T01/evidence_gold_set.json` |

### `pairs.json`

| 字段 | 类型 | 脚手架期望 |
|---|---|---|
| `pairs` | list | `[]`（刻意为空） |
| `pair_count` | int | `0` |
| `evaluation_tier` | str | `scaffold_pending_actual_gold` |

### 单条 pair（见 `pair.example.json`）

必填键由 `REQUIRED_PAIR_FIELDS` 定义；正式就绪时 `quote` 必须为真实摘录，字段名是 `quote`（不是 `quoted_text`）。

## 与 harness 的边界

| 工件 | 可否作 T09 actual gold |
|---|---|
| `docs/modules/T01/evidence_gold_set.json` | **否**（provisional fixture） |
| `docs/modules/T01/eval_gold/v1/` | 仅当 `ready_for_t09_formal_eval=true` |
