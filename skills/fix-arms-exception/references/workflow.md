# fix-arms-exception Workflow Reference

## MR 正文模板

MR 正文必须包含：

```markdown
## 问题

## 归因分析

## 解决方案

## 验证

## 风险和回滚

## ARMS 证据

## Source Manifest

### Sources

### Produced artifacts

### Key decisions

### Verification evidence

### Open questions / risks
```

不要粘贴大段 raw span 或 raw logs。保留必要摘要、诊断报告路径、ARMS show 命令、测试命令和关键代码路径。

## 修复前检查

- 当前输入报告是否 `status: bug`。
- 报告是否包含 Source Manifest。
- target branch 是否明确。
- 本地是否能在 `.arms-exceptions/worktrees/` 下创建独立 worktree。
- 推荐测试是否能运行，不能运行时记录原因。
- 修复是否局限于当前仓库；跨仓库、发布、外部权限或产品判断要转为人工介入。

## 分支和 Push 规则

允许自动 push 的唯一范围：

```text
fix/arms-YYYYMMDD-{short-title}
```

push 前记录：

- remote；
- branch；
- worktree；
- commit；
- 已执行测试。

不要 push 用户当前分支、目标分支或任何非 `fix/arms-` 分支。

## Worktree 路径

修复 worktree 统一放在：

```text
.arms-exceptions/worktrees/fix-<stable-slug>/
```

最终总结必须把该路径返回给父 Agent。父 Agent 在 triage 汇总后负责清理；fix 子 Agent 不自行删除自己的 worktree，避免丢失父 Agent 尚未读取的证据。

## Review Sub Agent

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

## 失败处理

无法复现：

- 如果诊断证据仍足以证明根因，可以写回归测试覆盖根因。
- 如果证据不足，停止，更新总结为 `needs_human`。

测试失败：

- 不创建 MR。
- 记录失败命令、失败摘要和相关日志路径。

push 失败：

- 不创建 MR。
- 记录 `git push -u origin <branch>` 命令和失败原因。

Yunxiao MR 创建失败：

- 保留本地 commit 和 pushed branch 信息。
- 按 `yunxiao-mr` CLI 输出的下一步处理，不猜 token 或仓库 ID。

## 最终总结模板

```markdown
# ARMS 异常修复结果

## 状态
- status: fixed | blocked | needs_human

## 分支和 MR
- worktree:
- branch:
- commit:
- mr:

## 变更摘要

## 验证

## 风险

## Source Manifest
```
