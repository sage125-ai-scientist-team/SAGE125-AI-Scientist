"""
T01 辅助脚本包（路径归属：docs/modules/T01/**）。

说明：
    校验/冻结工具放在 T01 允许路径下，避免根目录 ``scripts/t01/**`` 越权。
    不进入 ``app.evidence`` 运行时导入路径。
    模块：
        - ``validate_eval_gold``：eval_gold 结构与就绪门禁
        - ``fetch_eval_gold_sources``：冻结源只读校验
        - ``freeze_eval_gold_sources``：维护者重冻结 XML
"""
