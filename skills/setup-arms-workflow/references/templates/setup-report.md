# ARMS Workflow Setup Report

写入：

```text
.arms-exceptions/setup/setup-report.md
```

模板：

````markdown
# ARMS Workflow Setup Report

## Summary

- status: ready | blocked
- generated_at:
- host_repo:

## ARMS

- doctor:
- target:
- branch:
- services:
- SLS:

## Yunxiao

- repository:
- skip_api_doctor:
- api_doctor:
- token:

## Lark

- config:
- source:

## Local Artifacts

- setup:
- config:
- ignore:

## Configuration Closure

- arms-exceptions-explorer:
- arms-exceptions-triage:
- fix-arms-exception:
- yunxiao-mr:
- lark-notify:

## Suggested Host Agent Instructions

```text
ARMS 异常工作流：
- 使用 `arms-exceptions-triage` 分诊 CI 或人工触发的 ARMS 异常。
- 每次必须显式指定一个 target 或一个可唯一反查 target 的 service。
- 分诊和修复 worktree 统一放在 `.arms-exceptions/worktrees/`。
- 最近 setup 报告位于 `.arms-exceptions/setup/setup-report.md`。
```

## Blockers

只有外部权限、账号、CI secret 注入或用户拒绝导致当前会话无法完成配置时才填写。Agent 最终回复也必须直接说明这些 blocker，不能只写在报告里。

## Risks

## Source Manifest

- .arms-exceptions/setup/source-manifest.md
````
