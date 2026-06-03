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

如果缺少 `aliyun`，macOS 上优先安装：

```bash
brew install aliyun-cli
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
```

其他系统参考阿里云 CLI 安装文档：`https://help.aliyun.com/zh/cli/install-update-alibaba-cloud-cli`。

## 应用列表

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing --search ai-service
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing --json
```

主路径使用 `SearchTraceAppByPage`。失败时 fallback 到 `ListTraceApps`，并在本地过滤 `Type == "TRACE"`。

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

`message` 在表格里是缩略展示；完整信息在 `show` 中查看。

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

默认输出摘要、occurrences、error events、样本堆栈、精简 tags 和可选 SLS 关联日志。`show` 会按本地数据库中的 `group_id` 精确查找；如果无法唯一定位，再按 CLI 错误提示补 `--target` 或 `--service`。`--raw-event` 输出样本事件 tags；`--raw-span` 输出 ARMS 原始 span JSON。

SLS 关联日志规则：

- service 配置了 `sls` 时，`show` 默认按 occurrence 的 `trace_id` 做全文查询。
- 默认只查 1 个 occurrence，窗口为前后 120 秒，每个 trace 最多 50 条。
- `--no-logs` 关闭日志查询。
- `--log-occurrences`、`--log-before`、`--log-after`、`--log-limit` 覆盖默认查询范围。
- `--raw-logs --json` 才保留原始 SLS log item。
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
