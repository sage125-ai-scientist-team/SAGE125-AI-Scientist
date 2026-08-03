# T01 → T09 最终 provenance 整改包（冻结 10 项）

> 本轮验收标准冻结，一次性提交。本地 SOURCE_OK ≠ T09 通过。  
> **申请 ACCEPT_CANDIDATE = YES**（provenance 候选）。  
> **不申请**正式 corpus 纳入、不申请 Merge；PR 保持 **OPEN + Draft**。

## 1. PR 编号与最新完整 HEAD

| 项 | 值 |
|---|---|
| PR | [#25](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/25) |
| 状态 | OPEN / **Draft**（未经授权不 Ready / 不 Merge） |
| 固定复验 HEAD | 见本文件提交后的 PR tip（与 `gh pr view 25 --json headRefOid` 一致） |
| payload commit（`provenance.git_commit`） | `14494e7f2e4ba30f5717332e030a65a9da448d6a` |
| tip ≠ payload | 是（metadata/handoff 可晚于内容冻结） |

## 2. 实际来源或提供人

| 角色 | 说明 |
|---|---|
| 任务负责人 / 提供人 | T01 owner `Yqqxz` |
| 原始科学来源 | 5 篇 Open Access CC-BY 论文（DOI / Europe PMC / 出版商 PDF） |
| 金标著录 | T01 人工从冻结 XML 摘录 quote，并标注 allow/degrade/block |
| 非来源 | `evidence_gold_set.json` harness fixture（明确排除） |

DOI 列表：

1. `10.1371/journal.pone.0001248`（PLOS ONE，PMC2082661）
2. `10.1371/journal.pcbi.1005425`（PLOS Comp Biol，PMC5444614）
3. `10.7554/elife.05033`（eLife，PMC4341466）
4. `10.3389/fncom.2016.00094`（Frontiers，PMC5021692）
5. `10.1371/journal.pmed.1002120`（PLOS Medicine，PMC5021260）

## 3. 文件名、字节数及完整 SHA-256

权威包清单：`checksums.sha256`。冻结 XML 另见 `sources/SOURCES_INDEX.json`。

### 包文件（UTF-8 LF）

见同目录 `checksums.sha256`（随本整改包提交更新）。

### 冻结 XML（raw bytes，Git `-text`）

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `sources/PMC2082661.xml` | 100763 | `6b21f1dcffbd72ae43da960ef620cf320df27b94bb839f35d15007e2a7ee0c3c` |
| `sources/PMC4341466.xml` | 194281 | `41b9cf07c4d95675866f8f91fd0edac88336eeaa618173268db1bf5d9da0f935` |
| `sources/PMC5021260.xml` | 119897 | `4815c878ad592488886e2dcc67fc8e6c0e8b7851cb1b6045fceff9d0cb3da74c` |
| `sources/PMC5021692.xml` | 613898 | `4874c91db71cb2c8f1f69c3f5e6fa7af9c882a4228c14f40e1268ef9c7216eec` |
| `sources/PMC5444614.xml` | 64603 | `ca506948ca5a5f4b2012fbc8960714f4e311e442548dcdc4f1ac5ab7e611d28c` |

Publisher PDF 默认不入仓；SHA 钉死在 `SOURCES_INDEX.json` / `*.meta.json`，按需 `--pdf --refetch-missing`。

## 4. 来源、版本及使用授权

| 项 | 说明 |
|---|---|
| 来源 | Europe PMC fullTextXML + 出版商 OA PDF URL（见 meta） |
| 版本 | `data_version` / `xml_frozen_at_utc` / DOI |
| 授权 | 各篇 **CC-BY** Open Access；短摘录署名引用；完整 PDF 遵循各刊 CC-BY |
| 包 schema/脚本 | 仓库根许可证 |

## 5. registry / manifest / handoff / REPRODUCE 一致

| 工件 | 路径 | 一致性要点 |
|---|---|---|
| registry/index | `sources/SOURCES_INDEX.json` | DOI、xml/pdf SHA、字节、URL |
| manifest | `manifest.json` | `git_commit`=payload；`domain_mapping_doc`；reproduce 命令 |
| handoff | `T09_HANDOFF.md` + `T09_HANDOFF_MESSAGE.md` + 本文件 | HEAD/payload/命令一致 |
| REPRODUCE | `REPRODUCE.md` | 与 manifest.reproduce_command 相同两命令 |
| domain mapping | `domain_mapping_eval_gold.json` | 仅 EVAL-CLAIM-* |

## 6. 无 PENDING_CONFIRMATION / 无法解释占位

- 无 `PENDING_CONFIRMATION` 字段  
- `provenance.git_commit` = 真实 payload SHA（非 tip 自指）  
- `pair.example.json` 中 `10.xxxx` **仅为形状示例**，不计入 `pairs.json` 金标  
- `corpus_inclusion_status=NOT_CLAIMED_IN_FORMAL_CORPUS`（明确语义，非待填占位）

## 7. 隔离环境验证

```powershell
git clone --depth 1 --branch t01/b-evidence-core https://github.com/Yqqxz/SAGE125-AI-Scientist-t01.git
cd SAGE125-AI-Scientist-t01
git rev-parse HEAD   # 须等于本轮固定 HEAD
python docs/modules/T01/scripts/fetch_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1
# expect exit 0 / SOURCE_OK
python docs/modules/T01/scripts/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --require-ready
# expect exit 0 / ACTUAL_GOLD_OK
```

## 8. CI 各项检查结果

以固定 HEAD 对应 PR Checks 为准（`lint` / `type` / `unit` / `integration` / `security` / `build`）。  
提交本包后以最新 workflow 结论更新于 PR 评论。

## 9. 是否申请 ACCEPT_CANDIDATE

**YES — 申请 ACCEPT_CANDIDATE**（T09 provenance-only 候选接受）。

**NO** — 不申请正式 corpus 纳入；不申请 Merge。

## 10. PR 状态约束

- 保持 **OPEN + Draft**  
- 未经 T09/队长授权：**不 Ready、不 Merge**  
- 本轮仅 provenance-only 最终复验
