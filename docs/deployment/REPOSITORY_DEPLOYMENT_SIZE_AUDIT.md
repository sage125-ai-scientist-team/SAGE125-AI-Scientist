# 仓库部署体积审计

WORKTREE=D:\SAGE125_Local_Worktrees\ui_catalog_performance_release_20260828-140220  
INTEGRATION_SHA=6741effd8625543c0a42870d9b8bfc2a999d73eb  

REPO_TRACKED_SIZE_BEFORE=10513290  
REPO_TRACKED_COUNT_BEFORE=993  
OVER_1MB=0  
OVER_5MB=0  
OVER_20MB=0  

git count-objects：loose 33.19 MiB，pack 5.09 MiB。最大 tracked 文件为落地组件 `index-r96ktMW1.js`（819582 B），属于正式前端静态资源，不得删除。

## 候选删除结论

本次 **不删除任何 tracked 文件**。

原因：大于 100KB 的 tracked 路径均为正式依赖或比赛材料：

- `frontend_components/sage125_landing/**`：首页组件运行时  
- `docs/modules/T01/eval_gold/**`、`docs/modules/T06/gold/**`、`docs/modules/T05/**`：正式评测/金标  
- `docs/deployment/T08_handoff/**`：部署验收  
- `app/workflow/wave_c_release.py`：正式代码  
- `data/ui/ui_question_index.json`：轻量 UI 索引  
- `app/catalog/official_question_catalog.json`：官方 125 题  

上述路径 `official_output_dependency=true` 或 `runtime_reference_count>0`，`deletion_decision=keep`。

未跟踪的本地截图、`_*.py`、`.egg-info` 只存在于队长主工作区，不在本 worktree，不会进入本 PR。

## 部署排除

`.dockerignore` 已默认 deny-all，只放行 `app/`、`scripts/`、`frontend/`、`requirements.txt`、`Dockerfile`。  
当前 Render 服务是 `runtime: python`，**不是 Docker**，因此 `.dockerignore` 不减小 git clone 上下文。

EXCLUDED_FROM_DEPLOY_COUNT=0（python runtime 克隆全部 tracked 文件）  
REMOVED_FILE_COUNT=0  
REMOVED_BYTES=0  

优先保持排除策略，不误删正式 125 题结果、EvidenceCard、Catalog、测试或锁文件。

## Render Free

RENDER_FREE_INSTANCE=True  
IDLE_COLD_START_EXPECTED=True  

删除仓库文件不能消除平台冷启动。代码只优化热状态交互。
