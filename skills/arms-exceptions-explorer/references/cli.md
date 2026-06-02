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
  --window 24h
```

同名 target 默认合并 service；使用 `--replace` 替换 service 列表。

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
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target ai-service-dev --start "2026-06-01 00:00:00" --end "2026-06-02 00:00:00"
```

`--target` 会同步 target 下所有 service；某个 service 失败时会继续同步其他 service，但最终退出码为 `1`。

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
```

默认输出摘要、occurrences、error events、样本堆栈和精简 tags。`show` 会按本地数据库中的 `group_id` 精确查找；如果无法唯一定位，再按 CLI 错误提示补 `--target` 或 `--service`。`--raw-event` 输出样本事件 tags；`--raw-span` 输出 ARMS 原始 span JSON。
