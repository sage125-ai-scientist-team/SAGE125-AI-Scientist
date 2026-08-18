# Known Limitations

1. T01 EvidenceBundle 生产读口 **已接通**（`get_evidence_bundle`，PR #43）。Issue #52 文案过期，不再当作 T08 缺口。
2. T02 version/diff 生产读口缺失：Issue #53。`GET .../versions` 与 `.../versions/diff` 继续 503。
3. T05 execution/history 生产读口缺失：Issue #54。canonical report / 生产导出继续 503。
4. T03 feedback GET、decision、resulting-version、Gate 读口未冻结。`POST` 可提交；`GET` 仍 503。
5. 浏览器证据是 fixture rehearsal，不是生产 E2E。
6. 执行保持 `NOT ACTUAL`；文件存在不等于真实实验。
7. 多模态 fixture 置信度 0.72，保持人工核验。
8. 当前执行环境没有 Docker，干净部署与镜像扫描保持 WAIT。
9. 正式 120 分钟稳定性保持 WAIT；90 秒宿主机短测不能替代。
10. 资源泄漏状态 UNVERIFIED；短采样不足。
11. 备用录屏未制作：`ffmpeg` 可用，但无生产闭环可录，禁止用 fixture 冒充。
12. T07 配对审查未签字。
13. T09 部署验收未签字。
14. PR #41 仍 CONFLICTING / 越权路径；T08 无权限改队友 fork。
15. 不得把 `preview_seed` 题库当作 booklet gold 或 T09 评测输入。
