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

- status: ready | partial | blocked
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

## Suggested Host Agent Instructions

```text
ARMS 异常工作流：
- 使用 `arms-exceptions-triage` 分诊 CI 或人工触发的 ARMS 异常。
- 每次必须显式指定一个 target 或一个可唯一反查 target 的 service。
- 分诊和修复 worktree 统一放在 `.arms-exceptions/worktrees/`。
- 最近 setup 报告位于 `.arms-exceptions/setup/setup-report.md`。
```

## Missing Actions

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

- 找不到 `aliyun`：引导安装阿里云 CLI，再重跑 doctor。
- 未鉴权：引导 `aliyun configure get` 和 `aliyun configure --mode OAuth`。
- 缺 ARMS 权限：记录为 ARMS blocked，仍可继续检查 Yunxiao/Lark。

发现 app：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region <region> --search <keyword> --json
```

必须让用户确认：

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

SLS 是可选增强。若用户跳过 SLS，`show` 和 `logs` 不会提供关联日志，但 ARMS 主流程仍可用。

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

如果没有环境变量：

```bash
export YUNXIAO_ACCESS_TOKEN=<personal_access_token>
```

只在 token 已存在时运行：

```bash
python3 skills/yunxiao-mr/scripts/cli.py doctor --json
```

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

不要在 setup 阶段调用真实 `send`。需要验证 payload 时只允许 `send --dry-run`。

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

- 单个子系统失败时，不要抹掉已经完成的配置。
- ARMS 失败会阻塞 triage/fix 主流程，但不阻塞 Lark 本地配置。
- Yunxiao remote 不是 Codeup 时，记录为 Yunxiao blocked，不影响 ARMS/Lark。
- 缺 `YUNXIAO_ACCESS_TOKEN` 时，记录为 partial，并给出 export 引导。
- 缺 Lark Webhook 时，记录为 partial；不影响 ARMS/Yunxiao。
- 用户无法确认 app/SLS 时，停止对应配置并记录需要人工选择。

## Final Checklist

- `.arms-exceptions/config.json` 存在并只包含非凭证配置。
- `targets --json` 能列出确认过的 target、branch 和 services。
- `.arms-exceptions/setup/setup-report.md` 和 `source-manifest.md` 已写入。
- `.gitignore` 和 `.arms-exceptions/.gitignore` 忽略 setup、triage、worktrees、本地 webhook 和本地数据。
- `yunxiao-mr doctor --json --skip-api` 已记录。
- Lark `config --show --json` 已记录，且没有打印完整 Webhook。
