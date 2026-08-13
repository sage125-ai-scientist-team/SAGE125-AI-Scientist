# T08 Wave B Production E2E 与 T07 配对审查模板

状态：`TEMPLATE_ONLY / NOT_EXECUTED`

本文件不能作为 B016/B017 或 T07 配对审查已完成的证据。只有填入最终 commit、
production owner ports、真实命令输出和双方签字后，状态才可改变。

## 1. 运行身份

```text
T08 commit:
integration commit:
PR:
environment:
actor_id:
job_id:
correlation_id:
question_id:
run_id:
initial_version_id:
resulting_version_id:
execution_id:
```

任何字段未知都必须写 `N/A` 或 `unavailable`，不得猜测。

## 2. Owner port 清单

| Owner | 唯一 import/service path | production persistence | identity 已验证 | 代表性非 Mock 数据 |
|---|---|---|---|---|
| T01 Evidence | 待填写 | 待填写 | run+question | 待填写 |
| T02 Versions/Diff | 待填写 | 待填写 | run+question+version | 待填写 |
| T03 Feedback/Gate | 待填写 | 待填写 | actor+run+question+version | 待填写 |
| T05 Execution | 待填写 | 待填写 | run+question+version+execution | 待填写 |
| T06 Multimodal | 待填写 | 待填写 | run+question+version+artifact | 待填写 |

任一 mandatory owner 为 unavailable 时，production E2E 结论必须是 `WAIT`。

## 3. B016/B017 trace

按顺序保存请求、响应状态、correlation ID 和安全截图：

1. 选择真实问题并创建 job，请求快速返回 202。
2. 查询 queued/running/waiting/terminal 状态与 retry/timeout。
3. 查看带 quote、locator、关系、置信度和来源的 T01 evidence。
4. 查看 T02 V1/V2、Reviewer issue、lineage、score change 和 stop reason。
5. 向 T03 提交 feedback；重复 key 验证幂等，不同 payload 验证 conflict。
6. 查询 accepted/partial/rejected decision 与 resulting version。
7. 查看持久 ValidationReport；T08 不重新计算 Gate。
8. 查看 T05 execution；仅 owner 返回 true 时展示 `ACTUAL EXECUTION`。
9. 查看 T06 原始来源标识、page/bbox、axes/legend、单位、置信度和核验状态。
10. 导出 JSON/Markdown/PDF，并核对 canonical fingerprint、引用和 truth status。
11. 下载受控 artifact；跨 actor、checksum mismatch 和未知 artifact 必须失败关闭。
12. 刷新浏览器，通过 URL job ID 恢复，不读取旧缓存或本地 exports。

```text
TRACE_RESULT=WAIT
VIDEO_OR_TRACE_PATH=N/A
SCREENSHOT_PATHS=N/A
KNOWN_LIMITATIONS=
```

## 4. T07 配对审查

T07 reviewer 至少确认：

- questions 清单和 `question_id` 与 T07 manifest 一致；
- job/cache/artifact/download key 不会跨 question、job 或 actor 污染；
- 五个并发 question 的状态和产物保持隔离；
- T08 不解析 T07 私有文件名、内部表或临时日志；
- 失败题不会显示其他题的 evidence、version、execution 或 export；
- partial、failed、timed_out、unavailable 状态不会被标记 completed；
- 125 题列表为空、部分可用和 owner 失败均有明确外部语义。

```text
T07_REVIEWER=
T07_REVIEW_COMMIT=
T07_REVIEW_RESULT=WAIT
T07_FINDINGS=
T08_OWNER=
T08_RESPONSE=
CAPTAIN_ACKNOWLEDGEMENT=WAIT
```

## 5. 完成门禁

只有同时满足以下条件才可把模板改为证据：

- trace 对应最终 clean tip，分支 `behind=0`；
- production owner ports 已合入 integration；
- 没有 fixture、HTTP stub、Mock 或旧 export 替代生产结果；
- T07 配对审查完成；
- P0/P1 关闭；
- 队长明确 `READY_AUTHORIZED=YES`。

