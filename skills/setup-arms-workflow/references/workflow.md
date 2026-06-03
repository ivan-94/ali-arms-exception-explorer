# setup-arms-workflow Reference

## Source Manifest 模板

写入：

```text
.arms-exceptions/setup/source-manifest.md
```

模板：

```markdown
# ARMS Workflow Setup Source Manifest

## Sources

- user request:
- host repository:
- command outputs:

## Produced artifacts

- .arms-exceptions/setup/setup-report.md
- .arms-exceptions/setup/arms-doctor.json
- .arms-exceptions/setup/arms-apps.json
- .arms-exceptions/setup/sls-projects.json
- .arms-exceptions/setup/targets.json
- .arms-exceptions/setup/yunxiao-doctor-skip-api.json
- .arms-exceptions/setup/yunxiao-doctor.json
- .arms-exceptions/setup/lark-config.json

## User decisions

- region:
- target:
- branch:
- services:
- SLS:
- Lark:

## Commands

| command | output | exit | note |
| --- | --- | --- | --- |

## Verification evidence

## Closed configuration

## Open questions / risks
```

## Setup Report 模板

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

## ARMS 配置

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

## SLS 配置

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

## Yunxiao 配置

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

## Lark 配置

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

## Triage/Fix 配置闭环

`arms-exceptions-triage` 和 `fix-arms-exception` 没有独立 CLI 配置，但 setup 必须验证它们需要的宿主配置已经完成：

- `targets --json` 中每个要分诊的 target 都有 `branch`；
- 宿主 `.gitignore` 和 `.arms-exceptions/.gitignore` 已忽略 `.arms-exceptions/worktrees/`；
- Yunxiao doctor 已通过，因为 fix 需要创建 MR；
- Lark config 已通过，因为 triage 结束必须通知；
- `skills/arms-exceptions-triage/SKILL.md` 和 `skills/fix-arms-exception/SKILL.md` 在宿主项目存在。

缺任一项时继续引导用户补齐；无法补齐时 blocked。

## 忽略规则

宿主项目根 `.gitignore` 至少忽略：

```text
.arms-exceptions/data/
.arms-exceptions/setup/
.arms-exceptions/triage/
.arms-exceptions/worktrees/
.arms-exceptions/lark-notify.local.json
```

`.arms-exceptions/.gitignore` 由 `arms-exceptions-explorer init` 维护，必须包含：

```text
data/
setup/
triage/
worktrees/
lark-notify.local.json
```

## Error Handling

- 单个子系统失败时，不要抹掉已经完成的配置，但必须当场引导用户修复并重跑验证。
- ARMS 失败会阻塞 triage/fix 主流程；可以继续检查 Lark/Yunxiao，但最终不能输出 ready。
- Yunxiao remote 不是 Codeup 时，直接告诉用户当前 remote 不可用于 MR 创建，引导切换/配置 Codeup remote；无法补齐时 blocked。
- 缺 `YUNXIAO_ACCESS_TOKEN` 时，直接引导 export/CI secret 注入并重跑 doctor；不要只写入报告。
- 缺 Lark Webhook 时，直接引导提供 Webhook 或配置 `ARMS_LARK_WEBHOOK_URL` 并重跑 config；不要只写入报告。
- 用户无法确认 app/SLS 时，继续询问；用户拒绝或无法确认时 blocked。
- `setup-report.md` 可以记录 blocker，但最终回复必须把 blocker 和下一步命令直接告诉用户。

## Final Checklist

- `.arms-exceptions/config.json` 存在并只包含非凭证配置。
- `targets --json` 能列出确认过的 target、branch 和 services。
- Yunxiao `doctor --json` 已通过，或明确 blocked。
- Lark `config --show --json` 已通过，或明确 blocked。
- `.arms-exceptions/setup/setup-report.md` 和 `source-manifest.md` 已写入。
- `.gitignore` 和 `.arms-exceptions/.gitignore` 忽略 setup、triage、worktrees、本地 webhook 和本地数据。
- `yunxiao-mr doctor --json --skip-api` 已记录。
- Lark `config --show --json` 已记录，且没有打印完整 Webhook。
