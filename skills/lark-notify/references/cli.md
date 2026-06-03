# lark-notify CLI

入口：

```bash
python3 skills/lark-notify/scripts/cli.py <command>
```

## 配置

Webhook 读取优先级：

1. `.arms-exceptions/lark-notify.local.json`
2. `ARMS_LARK_WEBHOOK_URL`

保存本地 Webhook：

```bash
python3 skills/lark-notify/scripts/cli.py config --webhook-url <webhook>
```

这个命令会写入：

```text
.arms-exceptions/lark-notify.local.json
```

并确保宿主项目 `.gitignore` 包含：

```text
.arms-exceptions/lark-notify.local.json
```

查看配置：

```bash
python3 skills/lark-notify/scripts/cli.py config --show
python3 skills/lark-notify/scripts/cli.py config --show --json
```

`config --show` 只显示配置来源和脱敏 Webhook，不打印完整 URL。

## 发送文本

```bash
python3 skills/lark-notify/scripts/cli.py send \
  --title "Agent 通知" \
  --body-file <report.md> \
  --format text
```

payload:

```json
{
  "msg_type": "text",
  "content": {
    "text": "<title>\n\n<body>"
  }
}
```

## 发送卡片

```bash
python3 skills/lark-notify/scripts/cli.py send \
  --title "Agent 通知" \
  --body-file <report.md> \
  --format card
```

payload 类型为 `interactive`，包含标题和一个 `lark_md` 文本块。

`card` 是通用简单卡片：CLI 不理解业务字段，不做领域翻译，也不把某类报告格式改写成另一类格式。业务专用卡片应由业务 skill 生成 raw 飞书 payload，再用 `--format raw` 发送。

飞书卡片只支持 Markdown 子集。自定义机器人卡片只用于展示和 URL 跳转，不处理回调交互。

## 发送 raw payload

```bash
python3 skills/lark-notify/scripts/cli.py send \
  --json-file /tmp/lark-payload.json \
  --format raw
```

raw payload 必须是 JSON object，且包含 `msg_type`。CLI 不会重写 raw payload 的内容；如果超过 20 KB，会直接失败。

## Dry Run

```bash
python3 skills/lark-notify/scripts/cli.py send \
  --title "测试通知" \
  --body "hello" \
  --format card \
  --dry-run
```

dry-run 会渲染 payload、检查大小、显示是否截断，但不会发 HTTP 请求。

结构化 dry-run：

```bash
python3 skills/lark-notify/scripts/cli.py send \
  --title "测试通知" \
  --body "hello" \
  --format card \
  --dry-run \
  --json
```

## 大小和截断

飞书自定义机器人请求体限制为 20 KB。`text` 和 `card` 会在发送前测量 UTF-8 JSON 大小。

如果超限，CLI 会：

- 截断正文；
- 添加“内容已截断”说明；
- 如果正文来自 `--body-file`，保留该本地路径；
- 再次确认 payload 不超过限制。

如果最小 payload 仍超限，命令失败并提示缩短标题或正文。

## 安全规则

- 不打印完整 Webhook。
- 不保存 Authorization header、AccessKey、Secret、Token、SecurityToken、OAuth code 或签名 URL。
- `--dry-run --json` 会输出 payload，payload 中的常见凭证形态会先脱敏。
- 异常 message、关键 stack frame、根因、修复建议和少量 raw event/log 摘要可以发送。

## Exit Codes

- `0`: 成功。
- `1`: 用户可修复错误，例如未配置 Webhook、payload 超限、Webhook 返回失败。
- `2`: 参数解析错误。
- `130`: 用户中断。

## 常见问题

### 未配置 Webhook

```bash
python3 skills/lark-notify/scripts/cli.py config --webhook-url <webhook>
```

或：

```bash
export ARMS_LARK_WEBHOOK_URL=<webhook>
```

### Webhook 被拒绝

先确认飞书机器人安全设置。如果机器人配置了关键词，通知标题或正文必须包含关键词。

### 消息太大

优先使用 `--body-file` 指向本地报告，CLI 会截断正文并保留路径。仍然失败时，先缩短报告摘要，再发送。
