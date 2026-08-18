# Test Output Summary

当前分支：`t08/c-delivery-hardening`

记录时间：2026-08-16

工作区：`/Users/amanotooko/Projects/DC2026-2-t08-c`

解释器：`/Users/amanotooko/Projects/DC2026-2/.venv/bin/python`

## 本轮实际命令

```text
python -m pytest -q tests/api
```

精确结果：

```text
102 passed, 5 warnings in 9.30s
```

5 条 warning 来自既有 Swig/pytest 引导，不是本轮新增失败。

沙箱内同命令曾出现 `sqlite3.OperationalError: unable to open database file`
（47 failed）。那是沙箱写限制，不是产品回归。正式记录以无沙箱复跑为准。

```text
python -m compileall -q app/api frontend tests/api
result: exit 0
```

## 未跑 / 不能当作通过

```text
docker version                  WAIT  command not found
docker compose config           WAIT  command not found
120-minute formal stability     WAIT_NO_DOCKER
production browser E2E          WAIT_OWNER
T07 paired review               WAIT
T09 deployment acceptance       WAIT
```

全仓 `pytest -q` 本轮未重跑。历史失败在 T09/T05/T06 owner 路径，T08 不改那些测试来“变绿”。

本文件在 closeout commit 之后才会对应最终 SHA。
