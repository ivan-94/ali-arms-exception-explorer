# Review Sub Agent Brief

测试通过后、提交和 push 前，派发独立 review Sub Agent。它只读当前修复 worktree，不修改文件。

Review brief 至少包含：

- 诊断报告路径；
- 目标分支和修复分支；
- diff 摘要；
- 已执行测试命令和结果；
- MR 正文草稿路径；
- 要求按 P0/P1/P2 输出发现。

处理规则：

- P0/P1 或验收标准未满足：回到实现步骤修正，再重新测试和 review。
- P2：父 Agent 判断是否立即修复；不修时必须写入 MR 风险或后续项。
- 无发现：继续 commit、push、创建 MR。
