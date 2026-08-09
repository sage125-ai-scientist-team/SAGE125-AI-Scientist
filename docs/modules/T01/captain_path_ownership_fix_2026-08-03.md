# T01 路径越权整改说明（队长 REQUEST_CHANGES）

## 不做的事（遵守队长/T09）

- 不 Close PR #25
- 不 Ready（未经队长授权）
- 不 Merge
- 不把 ACCEPT_CANDIDATE 写成正式 corpus 纳入
- 不改写已冻结 payload commit `14494e7…`（仅追加工程整改 tip）

## 已做最小修复

1. `scripts/t01/**` → 迁入允许路径 `docs/modules/T01/scripts/**`
2. 根目录 `.gitattributes` 中 T01 eval_gold 规则已撤销
3. 换行/XML `-text` 规则下沉到：
   - `docs/modules/T01/eval_gold/v1/.gitattributes`
   - `docs/modules/T01/eval_gold/v1/sources/.gitattributes`
4. 文档/manifest/REPRODUCE/测试命令路径已同步更新

## 状态

- PR #25 保持 **OPEN + Draft**
- ENGINEERING 路径 P1 按上表收敛到 T01 允许树
- Wave B Ready 仍待队长授权后再操作
