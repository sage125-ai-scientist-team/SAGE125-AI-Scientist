# SAGE125 科学 UI 重构回滚说明

MODE=LOCAL_ONLY。本轮不 Push、不创建 PR、不修改远端分支、不修改部署。

## 修改前入口

- 正式前端：`streamlit run app/ui/streamlit_app.py`
- 后端：`python -m scripts.start_api`（常见 `http://127.0.0.1:8000`）
- 分支（开始时）：`integration/2026-08-10`
- HEAD：`bfac1de2c64801ecc6964147dadcb26e6a4d0730`

## 修改后入口

- 默认：`streamlit run app/ui/streamlit_app.py`（首页 + 工作区导航）
- 回退单页：`streamlit run app/ui/streamlit_app_legacy.py`
- 工作区导航内「完整控制台（回退）」页调用同一套旧功能
- 本地分支：`captain/local-scientific-ui-redesign-20260824-141019`（未设置 upstream）

## 备份路径

- UI 快照：`D:\SAGE125_Local_Backups\ui_redesign_before_20260824-141019`
  - 含当时的 `app/ui/**` 与 `.streamlit`
- 开始前工作区为 dirty，备份保留用户未提交的前端修改，重构未覆盖该备份目录

## 回滚命令（仅本地，不 push）

在仓库根目录：

```powershell
# 1) 用备份覆盖当前前端（不碰科学结果与后端契约）
Copy-Item -Recurse -Force "D:\SAGE125_Local_Backups\ui_redesign_before_20260824-141019\ui\*" ".\app\ui\"

# 2) 或仅改用旧入口，不覆盖新文件
# streamlit run app/ui/streamlit_app_legacy.py --server.port 8501
```

若只需丢弃本轮未提交的重构文件、保留开始前的 dirty 状态：从上述备份恢复 `app/ui`，不要对 `integration/2026-08-10` 做 reset。

禁止：`git push --force`、`git reset --hard` 到共享分支、修改 `main`。

## 恢复旧入口方式

1. 停止新预览进程（见任务结束时的 `STOP_COMMANDS`）。
2. 使用备份或 `streamlit_app_legacy.py`。
3. 用户已有的 `8000` / `8501` 服务不要误杀；回滚后可继续用原端口。

## 未改动的内容

- 125 题科学结果、Q028 旗舰产物、Prompt、质量门、模型路由
- `main` 与 `integration/2026-08-10` 远端
- Render / Railway 或其他部署
