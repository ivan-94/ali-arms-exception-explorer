---
name: lark-notify
description: 通过飞书/Lark 自定义机器人 Webhook 发送 Agent 通知。Use when 需要把分诊报告、修复结果、MR 链接、验收摘要或其他 Agent 产物发送到飞书群，或用户提到飞书机器人、Lark bot、Webhook 通知。
---

# 飞书通知

## Overview

这个 skill 用随仓库分发的 CLI 向飞书/Lark 自定义机器人发送通知。CLI 只使用 Webhook，不读取群成员、历史消息或回调事件。

入口始终在宿主项目根目录执行：

```bash
python3 skills/lark-notify/scripts/cli.py <command>
```

完整参数和 payload 说明见 `references/cli.md`。

## Quick Reference

| 任务 | 做法 |
| --- | --- |
| 保存 Webhook | `config --webhook-url <url>` |
| 查看配置状态 | `config --show` |
| 文本通知 | `send --title ... --body-file ... --format text` |
| 卡片通知 | `send --title ... --body-file ... --format card` |
| 原始 payload | `send --json-file ... --format raw` |
| 预览不发送 | `send ... --dry-run` |

## Config

Webhook 读取优先级：

1. `.arms-exceptions/lark-notify.local.json`
2. `ARMS_LARK_WEBHOOK_URL`

本地配置只保存 Webhook URL，必须忽略提交：

```bash
python3 skills/lark-notify/scripts/cli.py config --webhook-url <webhook>
```

如果手动配置，确认宿主项目 `.gitignore` 包含：

```text
.arms-exceptions/lark-notify.local.json
```

## Workflow

1. 检查配置：

   ```bash
   python3 skills/lark-notify/scripts/cli.py config --show
   ```

2. 先 dry-run，确认格式、大小和截断状态：

   ```bash
   python3 skills/lark-notify/scripts/cli.py send \
     --title "ARMS 异常分诊" \
     --body-file .arms-exceptions/triage/<run-id>/summary.md \
     --format card \
     --dry-run
   ```

3. 发送：

   ```bash
   python3 skills/lark-notify/scripts/cli.py send \
     --title "ARMS 异常分诊" \
     --body-file .arms-exceptions/triage/<run-id>/summary.md \
     --format card
   ```

## Rules

- 不要在回复、日志、MR 或报告中打印完整 Webhook。
- 不要发送凭证、Authorization header、AccessKey、Secret、Token、SecurityToken、签名 URL 或 OAuth code。
- 异常 message、关键 stack frame、根因、修复建议和少量 raw event/log 摘要可以发送。
- 超过飞书自定义机器人 20 KB 请求体限制时，CLI 会截断正文并保留本地报告路径。
- 发送真实 Webhook 前优先跑 `--dry-run`。
- `raw` 只用于已经构造好的飞书 payload；普通 Agent 报告优先用 `text` 或 `card`。

## References

```text
skills/lark-notify/
  SKILL.md
  references/
    cli.md
  scripts/
    cli.py
```

- `references/cli.md`：完整命令、配置、payload、截断和错误处理。
- `scripts/cli.py`：CLI 执行入口。
