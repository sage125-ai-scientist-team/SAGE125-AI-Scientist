# T09_HANDOFF_MESSAGE（NEEDS_CLARIFICATION 整改后）

## 摘要

T01 已针对 PR #25 固定验收 Commit `bf196567a6bfe5dcc196ba58a5ec94bcb589ea92` 的 `NEEDS_CLARIFICATION` 完成整改（新增 commit，未改写旧 commit）。

**未宣布纳入正式 corpus。** 请 T09 复验；通过后再提交组长确认。

## 固定信息

- 新固定 **payload Commit**：`14494e7f2e4ba30f5717332e030a65a9da448d6a`
- 新 **PR head**：`a2e41738ac432565262be401f53ed5f08b600072`
- 路径：`docs/modules/T01/eval_gold/v1/`

`provenance.git_commit` = payload commit（内容冻结提交），**不等于** tip/metadata commit。

## 两个验证命令及 exit code（隔离 clone 已复验）

```powershell
python scripts/t01/fetch_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1
# exit 0 / RESULT=SOURCE_OK

python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --require-ready
# exit 0 / RESULT=ACTUAL_GOLD_OK
```

隔离 clone：`git clone --depth 1 --branch t01/b-evidence-core https://github.com/Yqqxz/SAGE125-AI-Scientist-t01.git`  
在 tip `a2e41738ac432565262be401f53ed5f08b600072` 上两命令均为 exit 0。

## Fixture 隔离说明

- 正式标签权威：`pairs.json` + `domain_mapping_eval_gold.json`（仅 `EVAL-CLAIM-*`）
- 明确排除：`docs/modules/T01/evidence_gold_set.json`（`CLAIM-*` 不参与正式标签/expected_decision）
- `domain_audit_12.json` 不再作为本包 `domain_mapping_doc`

## XML 规范字节语义

Europe PMC `fullTextXML` HTTP 响应体原样冻结；`Path.write_bytes`；Git `sources/*.xml -text`；SHA-256 = raw bytes。  
验收时 `fetch_eval_gold_sources.py` **只读校验**冻结快照，默认不重下。

## 逐文件 SHA-256（checksums.sha256）

```
19911679ca11aa9f4b0491936f0468e5a3a607e67ad934ef4646d6455d273563  CURATION_CHECKLIST.md
1747f93441f85fe354d6e4fc4eeb608936a6f13cb1ef23913188e71bab4d51e3  REPRODUCE.md
fee6625dbb4f23e291e3e33f470adcd9e99328af2dfd3756a2afd889a331acda  T09_HANDOFF.md
5d39440ef538d703972139935ea4c9d1ba1b275ebc35281903f6c8b8a7140f71  T09_HANDOFF_MESSAGE.md
7f36a19b3887db21406d27b59a36bf1babec12d6674062d74c6618f912f873d8  domain_mapping_eval_gold.json
9b0befd1889a3013d97b05b31358d2db8baf751d46255243109a93b16d03afb5  manifest.json
fe8c2b8b157ccace3be368d1380e94cb92fd643b27bec61bd0e62d3686ac4c62  pair.example.json
b422d04a266fcdc8998e90c7fa0a2e8a489d907f0452b370723282038243b308  pairs.json
9dc40b278b62ebe8d8c679d50945251b33d1962f9c54574c592dabc272d3a14c  sources/SOURCES_INDEX.json

```

## 冻结 XML SHA-256

```
PMC2082661 6b21f1dcffbd72ae43da960ef620cf320df27b94bb839f35d15007e2a7ee0c3c
PMC4341466 41b9cf07c4d95675866f8f91fd0edac88336eeaa618173268db1bf5d9da0f935
PMC5021260 4815c878ad592488886e2dcc67fc8e6c0e8b7851cb1b6045fceff9d0cb3da74c
PMC5021692 4874c91db71cb2c8f1f69c3f5e6fa7af9c882a4228c14f40e1268ef9c7216eec
PMC5444614 ca506948ca5a5f4b2012fbc8960714f4e311e442548dcdc4f1ac5ab7e611d28c
```

## CC-BY

每条 pair 保留 DOI、作者与 CC-BY `license_or_authorization`。