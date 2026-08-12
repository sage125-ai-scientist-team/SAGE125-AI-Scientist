# Backup Recording

状态：`WAIT`

No backup recording was created because:

- `ffmpeg` is unavailable in the current execution environment;
- the current browser run is synthetic, not production E2E;
- the worktree is not at a clean final SHA;
- a recording must not preserve local paths, API keys, or stale fixture claims.

Recording acceptance:

1. Use the same clean SHA as the release package.
2. Show an environment banner identifying production or synthetic mode.
3. Stay below 10 minutes.
4. Show evidence, versions/diff, feedback/resulting version, Gate, execution,
   multimodal, and three-format export for the same job.
5. Keep `NOT ACTUAL` visible unless T05 attests actual execution.
6. Scan audio, video frames, browser URL, and logs for secrets.
7. Record file SHA256 and duration in this file.

```text
RECORDING_PATH=
RECORDING_SHA256=
DURATION_SECONDS=
SOURCE_GIT_SHA=
SECRET_SCAN=WAIT
RECORDING_RESULT=WAIT
```
