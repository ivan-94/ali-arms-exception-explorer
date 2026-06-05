ARMS 异常工作流：
- 使用 `arms-exceptions-triage` 分诊 CI 或人工触发的 ARMS 异常。
- 每次必须显式指定一个 target 或一个可唯一反查 target 的 service。
- 分诊和修复 worktree 统一放在 `.arms-exceptions/worktrees/`。
- 最近 setup 报告位于 `.arms-exceptions/setup/setup-report.md`。
