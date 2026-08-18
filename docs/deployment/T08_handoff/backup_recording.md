# Backup Recording

状态：`WAIT_NO_PRODUCTION_LOOP`

本机现在有 `ffmpeg`（`/opt/homebrew/bin/ffmpeg`），但 **没有** 可录的生产闭环：
T02 versions/diff、T03 feedback GET/Gate、T05 canonical report 仍 503。
因此本轮不生成备用录屏。用 fixture 页面录一段视频会冒充生产 E2E，禁止。

Windows 11 上若已具备生产读口和干净 SHA，按下面做：

```powershell
$sha = (git rev-parse HEAD).Trim()
$dirty = git status --porcelain
if ($dirty) { throw "Recording requires a clean worktree." }
ffmpeg -f gdigrab -framerate 15 -i desktop `
  -t 600 -an "docs/deployment/T08_handoff/acceptance_evidence/backup-$sha.mp4"
Get-FileHash "docs/deployment/T08_handoff/acceptance_evidence/backup-$sha.mp4" -Algorithm SHA256
```

录制验收：

1. 与发布包同一干净 SHA。
2. 画面标明 production 或 synthetic。
3. 不超过 10 分钟。
4. 同一 job 展示证据、versions/diff、反馈/新版本、Gate、执行、多模态、三格式导出。
5. 除非 T05 证明 actual，否则保持 `NOT ACTUAL`。
6. 扫描音频、画面、URL 和日志中的密钥。
7. 把路径、SHA256、时长写回本文件。

```text
RECORDING_PATH=
RECORDING_SHA256=
DURATION_SECONDS=
SOURCE_GIT_SHA=
SECRET_SCAN=WAIT
RECORDING_RESULT=WAIT_NO_PRODUCTION_LOOP
FFMPEG_AVAILABLE=YES
```
