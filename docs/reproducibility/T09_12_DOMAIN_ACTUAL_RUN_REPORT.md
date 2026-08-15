# T09 12 域正式实跑报告

本报告记录 `d211a0c` clean-room 上的正式 12 域 actual evaluation。产物保留在仓库外临时目录，不把原始 pipeline 工件或未脱敏 request_id 写入 Git。

## 执行身份

- HEAD：`d211a0c6dcadcecb28f3bbdbdea80c4681955f48`
- 分支：`t09/c-quality-hardening`
- 题库 SHA-256：`b6712a3b53f9776d7f695ea67f810c30b7d97ee59c183009432870d3224cdebb`
- Manifest SHA-256：`d75446be68491f7df11d3486d2c2726e53ebf4561aedd36956f591e93905bc95`
- Provider：`bailian` / `cn-beijing`
- 模型栈：fast=`qwen3.6-flash`，balanced=`qwen3.7-plus`，strong=`qwen3.7-max`，deep_research=`qwen-deep-research`，embedding=`text-embedding-v4`，rerank=`qwen3-rerank`
- MOCK_LLM：未设置
- 仓库内 `.env`：不存在
- 成本：`cost_usd=null`（只记账 token，不标价）

## 门禁

| 门禁 | 结果 |
| --- | --- |
| clean-room lint / type / unit / integration / coverage / security / build | PASS（`dd63738` 上 7 项全绿；后续审计修复提交跑 targeted + preflight） |
| `--preflight-only` | PASS，`provider_calls=0` |
| ledger validator | PASS |
| T09-METRIC-005 | PASS，`evaluated_domain_count=12` |

## 实跑结果

- 模式：`execute`
- `passed=true`
- `stopped=false`
- `global_attempt_count=12`
- `provider_calls=144`
- `request_id_count=144`
- `failed_attempt_count=0`
- 每域 secret scan：PASS

| 标准化领域 | QID | run_id | 调用/request_id | token 合计 | artifact sha256 前缀 |
| --- | --- | --- | --- | --- | --- |
| mathematics | Q001 | 20260815-030425-393aef57 | 12/12 | 74227 | 2d12338aeef38949 |
| physics | Q069 | 20260815-030834-1cdb860d | 12/12 | 72740 | 645c833de73c6728 |
| chemistry | Q003 | 20260815-031158-5a3724eb | 12/12 | 78025 | b06b35204cf63897 |
| biology | Q026 | 20260815-031534-b662473e | 12/12 | 83351 | 62f1e0af5ba07d26 |
| medicine | Q013 | 20260815-031931-56d655fc | 12/12 | 79538 | 2e2012304d08240f |
| earth_science | Q109 | 20260815-032307-38271681 | 12/12 | 78508 | 19303e09d46b13ee |
| computer_science | Q091 | 20260815-032636-8a6e0cb9 | 12/12 | 93658 | 04c4b8c111de6ed1 |
| materials | Q089 | 20260815-033054-e4704a1d | 12/12 | 90815 | 7f7bbdf34c1ab511 |
| astronomy | Q046 | 20260815-033511-933cfc9d | 12/12 | 84661 | b2fc120bbb46255c |
| neuroscience | Q095 | 20260815-033924-ab2e57a1 | 12/12 | 82543 | b0902e8c65887e42 |
| climate | Q107 | 20260815-034317-1608eda1 | 12/12 | 81637 | 7c260f5285dfa65c |
| engineering | Q088 | 20260815-034654-23b4675c | 12/12 | 80002 | 41d60a8c094a1367 |

Deep Research 调用均有真实 `request_id`。百炼对该模型经常省略 usage，对应 token 字段保持 `null` 且不计入合计，没有写成 0。

## 仍未关闭

- 20 页技术方案 PDF 与 125 个最终主交付文件仍缺失，METRIC-003 等包装项保持 BLOCKED。
- 本报告不把 PR 标为 Ready，不申请 Approve/Merge。
- Actual ablation 仍未授权。
