# setup-arms-workflow Commands

这些命令是 setup 过程中的可复制入口；执行顺序和 ready/blocked 判定以 `SKILL.md` 为准。

## ARMS

依赖检查：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor --json
```

常见失败处理：

- 找不到 `aliyun`：引导用户安装阿里云 CLI，再重跑 doctor；不要只写入报告。
- 未鉴权：引导用户执行 `aliyun configure get` 和 `aliyun configure --mode OAuth`，完成后重跑 doctor。
- 缺 ARMS 权限：当场说明缺哪个权限/API，并让用户切换账号或补权限；无法补齐时标记 blocked，仍可继续检查 Yunxiao/Lark，但最终不能输出 ready。

发现 app：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region <region> --search <keyword> --json
```

必须让用户确认并完成：

- target 名；
- target branch；
- service 列表；
- 多个 app 是否属于同一个 target。

初始化：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py init \
  --target <target> \
  --branch <branch> \
  --service <service> \
  --window <window>
```

多个 service 传多次 `--service`。同名 target 已存在时，默认合并；需要替换时必须由用户明确确认 `--replace`。

初始化后必须重跑：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py targets --json
```

如果 target 没有 branch、service 为空或 service 无法唯一归属 target，必须继续引导用户补齐，不能只在报告中列为缺失项。

## SLS

发现 Project：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py sls projects --json
```

发现 Logstore：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py sls logstores \
  --project <project> \
  --endpoint <endpoint> \
  --json
```

SLS 是可选增强，但选择必须闭环：用户要么明确确认某个 project/logstore/endpoint，要么明确确认该 service 跳过 SLS。不能因为无法判断就只把缺失写入报告。

如果用户确认 SLS，用非交互 init 写入：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py init \
  --target <target> \
  --branch <branch> \
  --service <service> \
  --sls-project <project> \
  --sls-logstore <logstore> \
  --sls-endpoint <endpoint>
```

## Yunxiao

先运行不访问 API 的检查：

```bash
python3 skills/yunxiao-mr/scripts/cli.py doctor --json --skip-api
```

如果没有环境变量，必须在当前对话引导用户配置并等待或让用户重启会话后继续：

```bash
export YUNXIAO_ACCESS_TOKEN=<personal_access_token>
```

token 已存在或用户配置完成后运行：

```bash
python3 skills/yunxiao-mr/scripts/cli.py doctor --json
```

配置后必须重跑 `doctor --json`。如果用户无法提供 token，setup 结果是 `blocked`，不是 `ready` 或只写报告。

不要在 setup 阶段创建 MR、类标、评论或执行 merge。

## Lark

Webhook 读取优先级：

1. `.arms-exceptions/lark-notify.local.json`
2. `ARMS_LARK_WEBHOOK_URL`

如果用户提供 Webhook：

```bash
python3 skills/lark-notify/scripts/cli.py config --webhook-url <webhook>
```

随后检查：

```bash
python3 skills/lark-notify/scripts/cli.py config --show --json
```

如果没有本地 Webhook 也没有 `ARMS_LARK_WEBHOOK_URL`，必须当场引导用户提供 Webhook 或配置环境变量。配置后必须重跑 `config --show --json`。如果用户无法提供 Webhook，setup 结果是 `blocked`。

不要在 setup 阶段调用真实 `send`。需要验证 payload 时只允许 `send --dry-run`。
