# ARMS 异常修复结果

如果由 `arms-exceptions-triage` 调度，最终总结必须写入父 Agent 提供的：

```text
.arms-exceptions/triage/<run-id>/subagents/fix-<stable-slug>.md
```

即使修复 blocked 或转为 needs_human，也必须写入该文件，方便父 Agent 汇总、通知和清理 worktree。

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
