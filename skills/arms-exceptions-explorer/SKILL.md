---
name: arms-exceptions-explorer
description: 从宿主项目拉取、聚合并查看阿里云 ARMS 异常 Span。用于 Codex 需要排查生产、预发、测试环境中记录在 ARMS/APM 的异常，列出 ARMS target/service，同步异常 Span 到本地 SQLite，查看异常聚合组、堆栈、原始 span/event 数据，或把 ARMS trace/span 证据关联回代码时。
---

# ARMS 异常调查

## Overview

这个 skill 用随仓库分发的 CLI 读取阿里云 ARMS 调用链异常数据。CLI 输出是事实来源；只要 CLI 能检查，就不要根据截图、日志片段、记忆或二手摘要推断 ARMS 状态。

入口始终在宿主项目根目录执行：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py <command>
```

## Quick Reference

| 任务 | 做法 |
| --- | --- |
| 检查前置条件 | `doctor` |
| 找不到 `aliyun` CLI | 引导用户按官方文档安装，然后重跑 `doctor` |
| 未鉴权或无 ARMS 权限 | `aliyun configure get`，再引导用户完成 OAuth 或组织要求的默认凭证配置 |
| 找 ARMS 应用名 | `apps --region <region> --search <keyword>` |
| 初始化项目配置 | `init` |
| 查看配置范围 | `targets` |
| 同步异常 | `sync --target <target>` 或 `sync --service <service>` |
| 查看异常组 | `groups --target <target>` 或 `groups --service <service>` |
| 查看详情 | `show <group_id> --target <target>` 或 `show <group_id> --service <service>` |
| 需要原始异常 tags | `show <group_id> --raw-event ...` |
| 需要原始 span JSON | `show <group_id> --raw-span --json ...` |

完整参数、JSON 输出和配置结构见 `references/cli.md`。

## Prerequisites

每次调查前先执行：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
```

### `aliyun` CLI 不存在

先根据当前环境判断系统和可用包管理器；如果无法完成安装，或安装需要用户参与，引导用户按阿里云官方文档安装：

https://help.aliyun.com/zh/cli/install-update-alibaba-cloud-cli

安装完成后必须重跑：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
```

### 未鉴权或 ARMS API 不可访问

先检查当前阿里云 CLI 配置：

```bash
aliyun configure get
```

如果没有可用默认凭证，引导用户完成 OAuth 或他们组织要求的默认凭证配置：

```bash
aliyun configure --mode OAuth
```

完成后重跑：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
```

不要索要、打印或保存 AccessKey、AccessKeySecret、SecurityToken、OAuth code、签名 URL、Authorization header 或任何凭证内容。

### 多账号或多 profile

如果用户有多个阿里云账号，让用户确认当前默认身份是否正确。需要切换时，引导用户在 `aliyun` CLI 里切换默认 profile：

```bash
aliyun configure switch --profile <profile>
```

本 CLI 不显式传 `--profile`，也不把 profile 写入 `.arms-exceptions/config.json`。实际身份由 `aliyun` CLI 默认凭证链决定。

## Workflow

1. 检查前置条件：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
   ```

2. 如果项目尚未配置 target/service，先找 ARMS TRACE 应用再初始化：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py apps # 列出所有 ARMS Services 
   python3 skills/arms-exceptions-explorer/scripts/cli.py init --help # 查看如何初始化
   ```

   列出服务和本地分支之后，可以引导和帮助用户初始化。

3. 查看宿主项目配置(target 包含的 Services, 以及绑定的本地分支)：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py targets
   ```

4. 同步明确范围内的异常：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target <target>
   ```

5. 查看同一范围内的异常组：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py groups --target <target>
   ```

6. 打开相关异常组：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --target <target>
   ```

7. 用 `top_stack_frame`、`stacktrace`、`trace_id`、`span_id`、`service_name`、`operation_name` 和 occurrence 信息回到代码排查。

## Rules

- 先跑 `doctor`，再做任何 ARMS 调查。
- 遇到失败时，先执行 CLI 输出里的“下一步”命令，再提出假设。
- `sync`、`groups`、`show` 必须传 `--target` 或 `--service`；不要静默跨越所有项目。
- `sync --target <target>` 中某个 service 失败时，使用 CLI 输出的单 service 重试命令排查。
- `show --raw-event` 用于查看原始异常 tags 和 stack 字段。
- 只有摘要事件不够时才用 `show --raw-span`；原始 span 可能很大。
- 下游工具或后续分析需要结构化数据时使用 `--json`。
- 不要打印凭证、签名 URL、`AccessKey`、`SecurityToken`、`Signature`、`Authorization`、OAuth code，或可能包含这些内容的原始命令输出。
- `.arms-exceptions/config.json` 是项目配置，只应包含 target、branch、region、service、pid、app_id 等非凭证信息。

## References

当前 skill 的关键文件：

```text
skills/arms-exceptions-explorer/
  SKILL.md
  references/
    cli.md
  scripts/
    cli.py
```

- `references/cli.md`：CLI 参数、JSON 输出、配置格式或排障细节不足时读取。
- `scripts/cli.py`：CLI 执行入口；运行命令时始终调用这个脚本。
