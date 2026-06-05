# ARMS 异常诊断

写入：

```text
.arms-exceptions/triage/<run-id>/subagents/diagnose-<stable-slug>.md
```

模板：

```markdown
# ARMS 异常诊断

## 结论
status: noise | needs_human | bug
confidence: high | medium | low

## 异常指纹
- exception_type:
- normalized_message:
- top_business_frame:
- service:
- operation:

## 证据
- ARMS:
- trace_console_url:
- logs:
- code:

## 根因分析

## 修复建议
- 是否可由 Agent 修复:
- 建议修复范围:
- 建议测试:

## Source Manifest

### Sources

### Produced artifacts

### Key decisions

### Verification evidence

### Open questions / risks
```

`status=bug` 必须有稳定代码路径证据和明确修复方向；否则使用 `noise` 或 `needs_human`。

`trace_console_url` 来自 `arms-exceptions-explorer groups/show --json` 的 `trace_console_url` 字段。字段缺失时写明原因，并提供 `sample_trace_id` 与本地查看命令；不要自行猜测 ARMS 控制台详情 URL。
