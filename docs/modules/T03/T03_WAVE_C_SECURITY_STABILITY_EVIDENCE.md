# T03 Wave C 安全与稳定性回归证据

## 结论

T03 在离线、确定性测试环境中完成 20 个明确攻击与稳定性案例，结果为
`20 passed / 0 failed`。覆盖范围包括恶意反馈与 prompt injection、超长输入、
不可见控制字符、五类必需验证产物逐项缺失、伪造引用、错误的
`actual_execution`、跨 run/question/version 污染、重复提交、并发重放、SQLite
重启恢复和持久化快照篡改。

所有拒绝路径均为失败关闭：输入要么在写库前被拒绝，要么生成阻断报告；不会
被误判为成功。阻断报告仍会写入哈希绑定的 `gate_evaluated ->
validation_completed` 审计链。重复写入不增加第二条完成事件，SQLite 重启后
事件 ID、父事件 ID 和 payload SHA-256 保持一致。

## 可复验证据

- 案例清单：`examples/wave_c_attack_case_manifest.json`
- 结果记录：`examples/wave_c_attack_case_results.json`
- 可执行测试：`tests/validation/test_wave_c_security_stability.py`
- 执行命令：

  ```powershell
  python -m pytest -q tests/validation/test_wave_c_security_stability.py
  ```

案例清单与结果文件均为 JSON，案例 ID 一一对应。测试本身还会校验 JSON
记录完整性、唯一性以及 `20/20` 汇总，防止文档与可执行证据脱节。因此 pytest
实际收集 21 项：20 个安全/稳定性案例，加 1 个机器可读证据一致性测试；执行结果
为 `21 passed`。

## 边界与限制

- 本轮没有连接生产 API，也没有把离线 fixture 描述成 live E2E。
- 本轮没有执行 T07/T08 批量或 API 流程。
- 本轮没有修改公共契约、`app/**`、`app/batch/**`、pipeline 或其他队员路径。
- 本证据证明 T03 owner 范围的安全边界和恢复语义，不替代跨 owner 的最终配对。
