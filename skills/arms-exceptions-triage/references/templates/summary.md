# Triage Summary

`summary.md` 面向人类阅读，必须使用中文字段和值。飞书通知不直接发送 Markdown 报告，而是由 triage 生成业务专用 `lark-card.json` raw payload，再交给 `lark-notify --format raw` 发送。

建议包含：

- target/service、窗口、branch、worktree；
- 同步结果和异常数量；
- 二次聚合前后数量；
- 中文状态统计，例如 `噪音`、`需要人工介入`、`明确 Bug`、`已有 MR 覆盖`、`待人工 review`、`人工 review 已通过并修复中`、`已创建修复 MR`；
- 每个保留异常的短标题、状态、置信度、核心 message、top frame、根因摘要；
- 每个保留/代表异常的 `group`、`sample_trace_id`，以及 explorer 已生成的 `trace_console_url`（如有）；
- 相关 MR 链接；
- 人工 review 状态；获批后进入修复阶段时再记录修复 MR 链接；
- 本地证据路径；
- 剩余风险和下一步。

字段示例：

```markdown
## 待人工 review 项

### OSS HEAD 404 导致 ARMS 异常 Span

- group: dbfd817213210b31
- sample_trace_id: 0a1b2c3d
- trace_console_url: https://trace.console.aliyun.com/#/cn-beijing/tracing-explorer?source=XTRACE&filters=...
- 状态: 待人工 review
- 根因: OSS HEAD 404 被 SDK 上报为 error span
- MR 覆盖判断: not_related
- review 关注点: 确认该根因是否应由当前 target 分支修复，以及是否允许派发 `fix-arms-exception`
```
