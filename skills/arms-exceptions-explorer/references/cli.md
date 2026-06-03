# CLI 使用说明

入口：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py <command>
```

## 环境检查

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor --skip-api
```

`doctor` 会检查 `aliyun` 是否存在、版本是否可读取、ARMS 应用列表 API 是否可用。失败时按输出中的 `下一步` 处理。

如果缺少 `aliyun`，不要假设用户的操作系统或包管理器。引导用户按阿里云官方文档安装：

https://help.aliyun.com/zh/cli/install-update-alibaba-cloud-cli

安装完成后必须重跑：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
```

## JSON 输出契约

所有命令默认输出人类可读文本；需要结构化消费时加 `--json`。JSON 字段名应保持稳定，且不包含凭证。完整参数以对应子命令 `--help` 为准，下面只列 Agent 常用结构化字段。

- `doctor --json`：顶层包含 `status`、`aliyun_installed`、`version`、`app_list_api`、`configured_service_api`、`config`、`config_exists`、`sls_api_available`、`sls_configured_services`、`sls_optional`、`next_steps`。
- `apps --json`：顶层 `apps` 数组；每项包含 `name`、`region`、`pid`、`app_id`、`type`。
- `sls projects --json`：顶层 `projects` 数组；每项包含 `project`。
- `sls logstores --json`：顶层包含 `project`、`endpoint`、`logstores`。
- `init --json`：顶层包含 `config`、`gitignore`、`target`、`services`。
- `targets --json`：输出 `.arms-exceptions/config.json` 的配置结构，顶层包含 `version`、`default_window`、`targets`。
- `sync --json`：顶层包含 `range`、`fresh`、`summaries`、`failures`；单个 service 失败时仍会输出成功 service 的摘要，并以退出码 `1` 标记部分失败。
- `groups --json`：顶层 `groups` 数组；每项包含表格字段的完整值，并尽量补 `trace_console_url`。
- `show --json`：顶层包含 `group`、`occurrences`、`events`、`sample_event`、`sample_span`、`related_logs`。
- `logs --json`：顶层包含 `group_id`、`related_logs`。

## 应用列表

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing --search ai-service
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing --json
```

主路径使用 `SearchTraceAppByPage`。失败时 fallback 到 `ListTraceApps`，并在本地过滤 `Type == "TRACE"`。

## SLS 发现

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py sls projects
python3 skills/arms-exceptions-explorer/scripts/cli.py sls projects --json
python3 skills/arms-exceptions-explorer/scripts/cli.py sls logstores --project ai-service-logs --endpoint cn-beijing.log.aliyuncs.com
python3 skills/arms-exceptions-explorer/scripts/cli.py sls logstores --project ai-service-logs --endpoint cn-beijing.log.aliyuncs.com --json
```

`sls projects` 使用当前 `aliyun` 默认凭证列出可见 Project。`sls logstores` 必须显式提供 `--project` 和 `--endpoint`，避免跨地域误查。两个命令都是只读发现，不会写入 `.arms-exceptions/config.json`。

JSON 输出：

```json
{
  "projects": [
    {
      "project": "ai-service-logs"
    }
  ]
}
```

```json
{
  "project": "ai-service-logs",
  "endpoint": "cn-beijing.log.aliyuncs.com",
  "logstores": ["app-log"]
}
```

## 初始化

交互式：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py init
```

非交互式：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py init \
  --target ai-service-dev \
  --branch dev \
  --service ai-service-dev \
  --service ai-service-dev-celery-worker \
  --window 24h \
  --sls-project ai-service-logs \
  --sls-logstore app-log \
  --sls-endpoint cn-beijing.log.aliyuncs.com
```

同名 target 默认合并 service；使用 `--replace` 替换 service 列表。`--sls-*` 是可选参数，传入时应用到本次 init 的所有 service；未传时保留已有 service 的 SLS 配置。交互式 init 会逐个 service 询问是否配置 SLS，并优先尝试只读导入 ARMS 控制台已有 SLS 关联配置。

## 查看配置

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py targets
python3 skills/arms-exceptions-explorer/scripts/cli.py targets --json
```

## 同步异常

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target ai-service-dev
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --service ai-service-dev-celery-worker
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target ai-service-dev --window 7d
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target ai-service-dev --keep-old-data
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target ai-service-dev --start "2026-06-01 00:00:00" --end "2026-06-02 00:00:00"
```

`--target` 会同步 target 下所有 service；某个 service 失败时会继续同步其他 service，但最终退出码为 `1`。`sync` 默认会先删除本次 target/service scope 的本地旧异常数据，让本地库代表当前排查窗口；需要保留旧数据时加 `--keep-old-data`。

## 查看聚合

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py groups --target ai-service-dev
python3 skills/arms-exceptions-explorer/scripts/cli.py groups --service ai-service-dev-celery-worker
python3 skills/arms-exceptions-explorer/scripts/cli.py groups --target ai-service-dev --json
```

`message` 在表格里是缩略展示；完整信息在 `show` 中查看。JSON 输出会尽量为每个 group 补 `trace_console_url`，前提是配置中能定位该 service 的 region 且 group 有 `sample_trace_id`。

## 查看详情

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id>
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --raw-event
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --raw-span
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --json
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --target ai-service-dev
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --no-logs
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --log-limit 20
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --raw-logs --json
```

默认输出摘要、occurrences、error events、样本堆栈、精简 tags 和可选 SLS 关联日志。`show` 会按本地数据库中的 `group_id` 精确查找；如果查不到或需要限定范围，再按 CLI 错误提示补 `--target` 或 `--service`。`--raw-event` 输出样本事件 tags；`--raw-span` 输出 ARMS 原始 span JSON。

当配置中能定位 service region 且 group 有 sample trace 时，`show` 文本和 JSON 的 `group.trace_console_url` 会输出一个阿里云调用链分析页链接。该链接使用阿里云官方 SLS 关联调用链文档中的 `trace.console.aliyun.com/#/<region>/tracing-explorer?source=XTRACE&filters=...` 过滤格式；它是跳转辅助，不代表接收者账号一定有权限看到该 trace。缺失时继续使用 `sample_trace_id`、`sample_span_id` 和本地 `show --json` 证据排查。

SLS 关联日志规则：

- service 配置了 `sls` 时，`show` 默认按 occurrence 的 `trace_id` 做全文查询。
- 生产敏感场景、不需要日志或担心外部查询时，先加 `--no-logs`。
- 默认只查 1 个 occurrence，窗口为前后 120 秒，每个 trace 最多 50 条。
- `--no-logs` 关闭日志查询。
- `--log-occurrences`、`--log-before`、`--log-after`、`--log-limit` 覆盖默认查询范围。
- 默认只展示归一化日志摘要；`--raw-logs --json` 才保留原始 SLS log item。
- SLS 未配置、查空或查询失败不会让 `show` 失败。

## 查看关联日志

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py logs <group_id>
python3 skills/arms-exceptions-explorer/scripts/cli.py logs <group_id> --target ai-service-dev
python3 skills/arms-exceptions-explorer/scripts/cli.py logs <group_id> --occurrences 3
python3 skills/arms-exceptions-explorer/scripts/cli.py logs <group_id> --before 5m --after 1m --limit 100
python3 skills/arms-exceptions-explorer/scripts/cli.py logs <group_id> --raw --json
```

`logs` 只输出关联日志视图，scope 解析和 `show` 一致。SLS 查询失败时 `logs` 返回 `1`，而 `show` 仍返回 `0` 并展示 ARMS 主证据。

## SLS 配置结构

```json
{
  "name": "ai-service-dev",
  "region": "cn-beijing",
  "pid": "xxx",
  "app_id": "xxx",
  "sls": {
    "project": "ai-service-logs",
    "logstore": "app-log",
    "endpoint": "cn-beijing.log.aliyuncs.com",
    "default_before_seconds": 120,
    "default_after_seconds": 120,
    "default_limit": 50
  }
}
```

SLS 配置只保存非凭证信息。CLI 使用现有 `aliyun sls GetLogs` 路径查询，不依赖 `aliyunlog`，也不写回 ARMS 控制台配置。
