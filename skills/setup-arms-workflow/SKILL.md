---
name: setup-arms-workflow
description: 在宿主项目配置 ARMS 异常分诊和修复工作流，检查 arms-exceptions-explorer、yunxiao-mr 和 lark-notify 依赖，发现 ARMS/SLS 配置并生成本地 setup 报告。Use when 用户要求初始化、配置、接入或检查 ARMS 异常自动分诊修复工作流。
---

# Setup ARMS Workflow

## Overview

这个 skill 在宿主项目里配置本仓库的 ARMS 工作流：

- `arms-exceptions-explorer`
- `arms-exceptions-triage`
- `fix-arms-exception`
- `yunxiao-mr`
- `lark-notify`

它是编排型 skill，不新增 setup CLI，不自动创建 MR、不发送真实飞书通知、不运行 ARMS sync。ARMS app 和 SLS 选择必须由用户确认。

入口始终在宿主项目根目录执行。

## Artifacts

每次 setup 写入本地产物：

```text
.arms-exceptions/setup/
  setup-report.md
  source-manifest.md
  arms-doctor.json
  arms-apps.json
  sls-projects.json
  sls-logstores-<project>.json
  targets.json
  yunxiao-doctor-skip-api.json
  yunxiao-doctor.json
  lark-config.json
```

确认宿主项目忽略本地 setup 和凭证文件：

```text
.arms-exceptions/setup/
.arms-exceptions/lark-notify.local.json
```

`source-manifest.md` 必须记录每条命令、用户确认的选择、产物路径、失败步骤和未决风险。

## Workflow

1. 创建 `.arms-exceptions/setup/`，开始 `setup-report.md` 和 `source-manifest.md`。
2. 检查 ARMS explorer：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py doctor --json
   ```

3. 发现 ARMS app，保存 `arms-apps.json`，让用户确认 target、branch 和 service 列表：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region <region> --search <keyword> --json
   ```

4. 发现 SLS，保存项目和 logstore 输出；SLS 可跳过，但不能替用户猜：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py sls projects --json
   python3 skills/arms-exceptions-explorer/scripts/cli.py sls logstores --project <project> --endpoint <endpoint> --json
   ```

5. 用确认值初始化 ARMS 配置：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py init \
     --target <target> \
     --branch <branch> \
     --service <service> \
     --window <window>
   ```

   如果用户确认 SLS，同时传 `--sls-project`、`--sls-logstore`、`--sls-endpoint`。

6. 保存最终 target 配置：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py targets --json
   ```

7. 检查 Yunxiao。先只读本地/remote；如果没有 `YUNXIAO_ACCESS_TOKEN`，在报告里给出配置引导。token 已存在时再运行 API doctor：

   ```bash
   python3 skills/yunxiao-mr/scripts/cli.py doctor --json --skip-api
   python3 skills/yunxiao-mr/scripts/cli.py doctor --json
   ```

8. 检查 Lark。若用户提供 Webhook，只保存本地配置；随后只做 `config --show --json`，不发送真实通知：

   ```bash
   python3 skills/lark-notify/scripts/cli.py config --webhook-url <webhook>
   python3 skills/lark-notify/scripts/cli.py config --show --json
   ```

9. 完成 `setup-report.md`，包含 readiness、缺失动作和建议的宿主 `AGENTS.md` 片段。

详细报告模板和失败处理见 `references/workflow.md`。

## Rules

- 没有用户确认，不选择 ARMS app、target、branch、SLS project/logstore。
- 不要求用户提供 AccessKey、Token、Authorization header、OAuth code 或签名 URL。
- `YUNXIAO_ACCESS_TOKEN` 只从环境变量读取；缺失时只引导用户配置，不保存 token。
- Lark Webhook 可以保存到 `.arms-exceptions/lark-notify.local.json`，但不能打印完整 URL 或写入报告。
- 不自动修改宿主 `AGENTS.md`、`CLAUDE.md` 或 CI 配置；只在报告里给建议片段。
- 任一子系统失败时，记录为 partial/blocked，安全时继续检查其他子系统。

## References

更多报告模板、Source Manifest 和错误处理细节见 `references/workflow.md`。
