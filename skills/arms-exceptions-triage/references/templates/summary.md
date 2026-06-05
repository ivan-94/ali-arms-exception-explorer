# Triage Summary

`summary.md` 面向人类阅读，必须使用中文字段和值。飞书通知不直接发送 Markdown 报告，而是由 triage 生成业务专用 `lark-card.json` raw payload，再交给 `lark-notify --format raw` 发送。

建议包含：

- target/service、窗口、branch、worktree；
- 同步结果和异常数量；
- 二次聚合前后数量；
- 中文状态统计，例如 `噪音`、`需要人工介入`、`明确 Bug`、`已有 MR 覆盖`、`修复中`、`已创建修复 MR`；
- 每个保留异常的短标题、状态、置信度、核心 message、top frame、根因摘要；
- 每个保留/代表异常的 `group`、`sample_trace_id`，以及 explorer 已生成的 `trace_console_url`（如有）；
- 相关 MR 链接；
- 修复 MR 链接；
- 本地证据路径；
- 剩余风险和下一步。

字段示例：

```markdown
## 修复项

### OSS HEAD 404 导致 ARMS 异常 Span

- group: dbfd817213210b31
- sample_trace_id: 0a1b2c3d
- trace_console_url: https://trace.console.aliyun.com/#/cn-beijing/tracing-explorer?source=XTRACE&filters=...
- 状态: 已创建修复 MR
- 根因: OSS HEAD 404 被 SDK 上报为 error span
- 修复 MR: [MR #212](https://...)
```
