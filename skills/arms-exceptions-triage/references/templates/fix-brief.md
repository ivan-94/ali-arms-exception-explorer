# ARMS 修复任务

父 Agent 派发修复 Sub Agent 时，brief 必须从诊断报告开始，并明确 `result_path`。

```markdown
# ARMS 修复任务

## 输入
- HOST_ROOT:
- diagnostic_report: .arms-exceptions/triage/<run-id>/subagents/diagnose-<stable-slug>.md
- result_path: .arms-exceptions/triage/<run-id>/subagents/fix-<stable-slug>.md
- target:
- branch:
- representative_group_id:
- covered_duplicate_group_ids:

## 必须执行
- 使用 `fix-arms-exception`，从 diagnostic_report 开始
- 在独立 `.arms-exceptions/worktrees/fix-<stable-slug>/` worktree 中修复
- TDD：先复现或写失败回归测试，再修复
- 创建 Yunxiao MR 后，把最终修复结果写入 result_path

## 禁止
- 不自动合并 MR
- 不 push 非 `fix/arms-` 分支
- 不删除自己的 worktree；父 Agent 汇总后清理
```

修复 Sub Agent 未写入 `result_path` 时，父 Agent 不得假设修复成功；必须把该项记为 blocked，并在 summary/source-manifest 中记录缺失结果路径。
