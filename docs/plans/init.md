# ARMS Exceptions Explorer 生产化执行计划

## Source Manifest

### Sources

- 当前对齐讨论：用户要求在 `/Users/ivan/workspace/ai/arms-exceptions` 新建独立 skill 项目，提供面向 Agent 的 ARMS 异常 Span 拉取、聚合、查看 CLI。
- 当前对齐讨论：CLI 入口放在 `skills/arms-exceptions-explorer/scripts/cli.py`，实现可拆分到同目录包内；纯 Python 3，不能依赖标准库之外的第三方包。
- 当前对齐讨论：项目配置存放在宿主项目根目录 `.arms-exceptions/config.json`，本地 SQLite 数据存放在 `.arms-exceptions/data/arms_exceptions.sqlite`。
- 当前对齐讨论：一个 target 支持绑定多个 ARMS service；target/service 在 `sync/groups/show` 中必须显式传入，不能默认扫描全部。
- 当前对齐讨论：CLI 不再暴露 `--profile`，调用 `aliyun` CLI 时不显式传 `--profile`，凭证选择交给阿里云 CLI 默认模式、当前配置、`ALIBABA_CLOUD_PROFILE` 或 CI 环境。
- 当前对齐讨论：所有 CLI 错误都必须说明如何修复，以及下一步可以执行什么命令。
- 当前对齐讨论：`SearchTraceAppByPage` 已由子 Agent 用真实阿里云 CLI 验证可列出 `ai-service-dev`、`ai-service-dev-celery-worker` 等 TRACE 应用；fallback 为 `ListTraceApps` 后本地过滤 `Type == "TRACE"`。
- POC 代码：`/Users/ivan/workspace/sharge/ai_glass/side_projects/arms_traces/arms_traces/cli.py`。
- POC 代码：`/Users/ivan/workspace/sharge/ai_glass/side_projects/arms_traces/arms_traces/aliyun_cli.py`。
- POC 代码：`/Users/ivan/workspace/sharge/ai_glass/side_projects/arms_traces/arms_traces/ingestion.py`。
- POC 代码：`/Users/ivan/workspace/sharge/ai_glass/side_projects/arms_traces/arms_traces/aggregation.py`。
- POC 代码：`/Users/ivan/workspace/sharge/ai_glass/side_projects/arms_traces/arms_traces/repository.py`。
- POC 测试：`/Users/ivan/workspace/sharge/ai_glass/side_projects/arms_traces/tests/test_arms_traces.py`。
- 阿里云 CLI 文档：`https://help.aliyun.com/zh/cli/what-is-alibaba-cloud-cli`。
- 阿里云 CLI 配置文档：`https://help.aliyun.com/zh/cli/configure-alibaba-cloud-cli/`。
- 阿里云 CLI 多凭证管理文档：`https://help.aliyun.com/zh/cli/other-configure-command-operations`。
- 阿里云 CLI 安装文档：`https://help.aliyun.com/zh/cli/install-update-alibaba-cloud-cli`。
- Agent 持久化产物要求：`/Users/ivan/.agents/docs/agents/workflows.md`、`/Users/ivan/.agents/docs/agents/handoff-policy.md`。

### Produced artifacts

- 本计划：`/Users/ivan/workspace/ai/arms-exceptions/docs/plans/init.md`。

### Key decisions

- 先生产化 CLI + skill，不先做 Web UI。
- `skills/arms-exceptions-explorer/scripts/cli.py` 是唯一 CLI 执行入口，README 和 references 只引用入口；具体实现可以拆分到 `scripts/arms_exceptions/`。
- CLI 使用阿里云 CLI 作为外部执行器，不直接集成阿里云 Python SDK。
- 凭证不进入项目配置，不在 CLI 中显式传 profile。
- 请求端先过滤异常 Span：使用 `SearchTracesByPage --IsError true`，再用 `GetTrace` 拉原始 trace 并只落库异常 span。
- 聚合保留原始数据：`raw_spans` 保存原始异常 span JSON，`error_events` 保存抽取后的异常事件，`error_groups` 保存 fingerprint 聚合结果。
- fingerprint 第一版使用 `service_name + exception_type + normalized_message + top_stack_frame`，不使用 `trace_id/span_id/time`，也不使用 `operation_name/code_lineno` 作为主聚合键。
- `sync --target` 同步 target 下所有 service；`sync --service` 只同步单个 service。
- `groups/show` 也必须显式传 `--target` 或 `--service`，避免跨项目误混。
- `sync --target` 中部分 service 失败时继续同步剩余 service，但最终退出码为 `1`。

### Verification evidence

- POC 单测已在当前机器通过：`uv run --project side_projects/arms_traces python3 -m unittest side_projects/arms_traces/tests/test_arms_traces.py`。
- 子 Agent 已只读验证 `aliyun arms SearchTraceAppByPage --RegionId cn-beijing --PageNumber 1 --PageSize 100` 可返回 TRACE 应用列表，并包含 `ai-service-dev`、`ai-service-dev-celery-worker`。
- POC 曾用真实阿里云 CLI/OAuth 拉取 `ai-service-dev` 与 `ai-service-dev-celery-worker` 异常 Span，并证明可从原始数据里拿到 `exception.stacktrace`、`celery.einfo` 等错误详情。

### Open questions / risks

- ARMS 返回结构可能随 API 或不同应用类型变化；生产版需要解析函数兼容 `PageBean.TraceInfos`、`Spans`、`Span`、`TagEntryList`、`LogEventList` 的多种形态。
- `ListTraceApps --AppType TRACE` 过滤语义不可靠，fallback 必须客户端过滤 `Type == "TRACE"`。
- 阿里云 CLI 错误输出可能包含签名 URL 或临时凭证，所有错误消息必须脱敏。
- 真实验收依赖当前环境已经登录并拥有 ARMS 权限；测试中不能打印 AccessKey、SecurityToken、Signature、Authorization 等敏感信息。

## 目标

把现有 POC 生产化为一个可被 `npx skills` 安装到宿主项目的 Agent skill。第一版交付一个稳定、可诊断、可测试的 CLI，让 Agent 能在宿主项目中完成以下任务：

1. 检查本机是否有可用的阿里云 CLI 和 ARMS 访问权限。
2. 初始化宿主项目的 ARMS 异常抓取配置。
3. 按 target 或 service 显式拉取异常 Span。
4. 将异常 Span 原始数据落到本地 SQLite。
5. 对异常事件做通用聚合。
6. 用 CLI 展示异常组、样本堆栈、原始 span/event 数据。
7. 让 Agent 根据异常堆栈回到宿主项目代码排查。

## 非目标

- 不做 Web UI。Web 应用后续可以基于同一 SQLite 数据模型扩展。
- 不写入或修改宿主项目业务代码。
- 不直接调用阿里云 SDK，不引入第三方 Python 依赖。
- 不实现 ARMS 异常分析页面的聚合逻辑；我们只使用调用链 Span 数据，聚合在本地完成。
- 不把 profile、AccessKey、Token 或任何凭证写入 `.arms-exceptions/config.json`。
- 不在 `sync/groups/show` 没有 target/service 时自动扫描全部项目。

## 目标目录结构

```text
/Users/ivan/workspace/ai/arms-exceptions
  README.md
  docs/
    plans/
      init.md
  skills/
    arms-exceptions-explorer/
      SKILL.md
      references/
        cli.md
      scripts/
        cli.py
        arms_exceptions/
          __init__.py
          app.py
        test_cli.py
        test_config.py
        test_aggregation.py
        test_ingestion.py
```

## 宿主项目配置

配置文件路径固定为宿主项目根目录：

```text
.arms-exceptions/config.json
```

数据文件默认路径：

```text
.arms-exceptions/data/arms_exceptions.sqlite
```

配置示例：

```json
{
  "version": 1,
  "default_window": "24h",
  "targets": [
    {
      "name": "ai-service-dev",
      "branch": "dev",
      "default_window": "24h",
      "services": [
        {
          "name": "ai-service-dev",
          "region": "cn-beijing",
          "pid": "xxx",
          "app_id": "xxx"
        },
        {
          "name": "ai-service-dev-celery-worker",
          "region": "cn-beijing",
          "pid": "xxx",
          "app_id": "xxx"
        }
      ]
    }
  ]
}
```

规则：

- `targets[].name` 是 CLI 的 `--target` 参数值。
- `targets[].branch` 只用于帮助 Agent 建立“异常属于哪个代码分支”的上下文，不参与 ARMS 查询。
- `targets[].services[].name` 是 ARMS `ServiceName` 查询参数。
- `region` 优先使用 service 自己的 region；没有时 fallback 到 target 或全局默认 `cn-beijing`。
- `pid/app_id` 来自 `SearchTraceAppByPage`，第一版主要用于展示、防误选和后续扩展。
- config 可以提交到宿主项目；`.arms-exceptions/data/` 应加入宿主项目 `.gitignore`。

## CLI 总体约定

入口：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py <command>
```

全局参数：

- `--config <path>`：覆盖配置文件路径，默认 `.arms-exceptions/config.json`。
- `--db <path>`：覆盖 SQLite 路径，默认 `.arms-exceptions/data/arms_exceptions.sqlite`。
- `--json`：输出机器可读 JSON。各子命令按需支持。
- `--verbose`：输出更多诊断信息，但不得输出敏感凭证。

不提供：

- 不提供 `--profile`。
- 不在命令中主动追加 `--profile`。

凭证行为：

- CLI 调用 `aliyun arms ...` 时只传 ARMS API 业务参数。
- 默认凭证选择由阿里云 CLI 决定。
- 切换本地账号由用户执行 `aliyun configure switch --profile <name>`。
- CI 可用阿里云 CLI 支持的环境变量或默认配置文件提供凭证。

错误输出标准：

每个用户可修复错误都必须包含：

1. `错误:` 说明失败原因。
2. 当前可用 target/service 或缺失配置状态。
3. `下一步:` 给出可复制命令。

示例：

```text
错误: sync 需要指定 --target 或 --service。

可用 target:
- ai-service-dev

可用 service:
- ai-service-dev
- ai-service-dev-celery-worker

下一步:
  python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target ai-service-dev
  python3 skills/arms-exceptions-explorer/scripts/cli.py targets
```

敏感信息脱敏规则：

- `AccessKeyId`
- `AccessKeySecret`
- `SecurityToken`
- `Signature`
- `SignatureNonce`
- `Authorization`
- `Credential`
- `code`
- signed URL query string 中的凭证字段

## 子命令设计

### doctor

用途：检查运行环境和 ARMS API 连通性。

命令：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor --skip-api
```

检查项：

1. `aliyun` 是否存在。
2. `aliyun version` 是否可执行。
3. 当前默认凭证是否能调用 `SearchTraceAppByPage`。
4. 若已有 config，抽样检查首个 service 是否能调用 `SearchTracesByPage --IsError true`。

失败引导：

- 没有 CLI：提示安装文档和 macOS/Linux 常见安装命令。
- 未授权或无权限：提示执行 `aliyun configure --mode OAuth`、`aliyun configure switch --profile <name>` 或配置 CI 凭证。
- ARMS 权限不足：提示确认当前账号是否能访问对应 ARMS 应用。

### apps

用途：列出当前账号可见的 ARMS TRACE 应用，供初始化或诊断使用。

命令：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing --search ai-service
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing --json
```

主 API：

```bash
aliyun arms SearchTraceAppByPage --RegionId <region> --PageNumber <n> --PageSize <size>
```

搜索：

```bash
aliyun arms SearchTraceAppByPage --RegionId <region> --TraceAppName <keyword> --PageNumber <n> --PageSize <size>
```

fallback：

```bash
aliyun arms ListTraceApps --RegionId <region>
```

fallback 后必须本地过滤：

```text
Type == "TRACE"
```

输出字段：

- `name`
- `region`
- `pid`
- `app_id`
- `type`

### init

用途：初始化或更新宿主项目 `.arms-exceptions/config.json`。

交互式：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py init
```

交互步骤：

1. 检查 `aliyun` 和 ARMS app list API。
2. 选择 region，默认 `cn-beijing`。
3. 调用 `SearchTraceAppByPage` 拉取应用列表。
4. 选择或搜索多个 service。
5. 输入 target 名。
6. 输入 branch。
7. 输入默认窗口，默认 `24h`。
8. 若 target 已存在，询问合并、覆盖或取消。
9. 写入 `.arms-exceptions/config.json`。
10. 提示下一步 `targets`、`sync --target <name>`。

非交互式：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py init \
  --target ai-service-dev \
  --branch dev \
  --service ai-service-dev \
  --service ai-service-dev-celery-worker \
  --window 24h
```

非交互式规则：

- 一次添加或更新一个 target。
- 同名 target 默认合并 services，并更新 branch/window。
- `--replace` 表示清空原 target 后重设。
- `--service` 可出现多次。
- 如果 service 不在应用列表中，默认失败并给出 `apps --search` 命令；后续如果需要可加 `--allow-unknown-service`，第一版不加。

### targets

用途：列出当前配置里的 target 和 service，供 Agent 选择后续命令。

命令：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py targets
python3 skills/arms-exceptions-explorer/scripts/cli.py targets --json
```

输出：

- target 名。
- branch。
- default window。
- services 列表。
- 下一步示例命令。

### sync

用途：拉取异常 Span 并落库。

命令：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target ai-service-dev
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --service ai-service-dev-celery-worker
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target ai-service-dev --window 7d
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target ai-service-dev --start "2026-06-01 00:00:00" --end "2026-06-02 00:00:00"
```

必须显式传入：

- `--target <name>` 或
- `--service <name>`

时间规则：

- `--target` 且没有时间参数：使用 target 的 `default_window`，没有则使用全局 `default_window`，再没有则 `24h`。
- `--service` 且没有时间参数：使用全局 `default_window`，再没有则 `24h`。
- `--window` 支持 `15m`、`1h`、`24h`、`7d`。
- `--start/--end` 必须成对出现，使用 Asia/Shanghai 本地时间解析。

采集流程：

1. 用 `SearchTracesByPage --IsError true` 按 service、时间窗口分页查询异常 trace/span。
2. 记录返回的 `trace_id` 和可疑异常 `span_id`。
3. 对每个 trace 调用 `GetTrace`，分页拉完整 trace。
4. 在本地只保存异常 span：
   - 返回列表中命中的 expected span。
   - span 自身有 `exception.*`、`error.*`、`celery.*`、`log.level=ERROR` 等错误标签。
   - HTTP status >= 400 的 span 作为错误候选，但聚合要优先使用异常事件。
5. 从 `LogEventList` 和 span 顶层 `TagEntryList` 抽取 `error_events`。
6. upsert `raw_spans`、`error_events`、`error_groups`、`error_occurrences`。

多 service 规则：

- `--target` 下每个 service 独立执行 sync run。
- 一个 service 失败时记录失败并继续剩余 service。
- 只要存在失败，最终退出码为 `1`。
- 输出每个 service 的 summary 和失败重试命令。

### groups

用途：查看异常聚合列表。

命令：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py groups --target ai-service-dev
python3 skills/arms-exceptions-explorer/scripts/cli.py groups --service ai-service-dev-celery-worker
python3 skills/arms-exceptions-explorer/scripts/cli.py groups --target ai-service-dev --limit 50
python3 skills/arms-exceptions-explorer/scripts/cli.py groups --target ai-service-dev --since "2026-06-01 00:00:00"
python3 skills/arms-exceptions-explorer/scripts/cli.py groups --target ai-service-dev --json
```

必须显式传入：

- `--target <name>` 或
- `--service <name>`

默认行为：

- 展示已同步到本地 SQLite 的数据。
- 按 `last_seen_ms desc, occurrence_count desc` 排序。
- message 是缩略展示。

展示字段：

- `group_id`
- `count`
- `last_seen`
- `service`
- `operation`
- `exception_type`
- `message`

### show

用途：查看单个异常组详情。

命令：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --target ai-service-dev
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --service ai-service-dev-celery-worker
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --target ai-service-dev --raw-span
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --target ai-service-dev --raw-event
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --target ai-service-dev --json
```

必须显式传入：

- `--target <name>` 或
- `--service <name>`

默认展示：

- group 摘要。
- service/operation/type/message/source。
- count/first_seen/last_seen。
- 样本 trace_id/span_id。
- 最新 occurrences。
- error_events 列表。
- 最佳样本堆栈。
- 精简 sample tags。

原始数据：

- `--raw-span`：输出样本 span 的原始 JSON。
- `--raw-event`：输出样本 error event 的 `raw_tags` JSON。
- `--json`：输出结构化 JSON，包含 group、occurrences、events、sample_span。

## SQLite 数据模型

### sync_runs

记录每次 service 同步。

关键字段：

- `id`
- `target_name`
- `service_name`
- `region`
- `start_ms`
- `end_ms`
- `status`
- `total`
- `trace_infos`
- `unique_traces`
- `fetched_traces`
- `stored_spans`
- `error_events`
- `error`
- `created_at`
- `completed_at`

### raw_spans

保存异常 span 原始数据。

关键字段：

- `trace_id`
- `span_id`
- `parent_span_id`
- `target_name`
- `service_name`
- `operation_name`
- `result_code`
- `timestamp_ms`
- `duration_ms`
- `service_ip`
- `tags_json`
- `raw_json`
- `group_key`
- `first_seen_at`
- `last_seen_at`

主键：

```text
(trace_id, span_id)
```

### error_events

保存从 span 抽取出来的异常事件。

关键字段：

- `id`
- `group_key`
- `trace_id`
- `span_id`
- `event_index`
- `timestamp_ms`
- `target_name`
- `service_name`
- `operation_name`
- `source`
- `exception_type`
- `message`
- `stacktrace`
- `top_stack_frame`
- `code_filepath`
- `code_function`
- `code_lineno`
- `log_original`
- `is_handled`
- `is_synthetic`
- `raw_tags_json`

唯一约束：

```text
(trace_id, span_id, event_index, exception_type, message)
```

### error_groups

保存 fingerprint 聚合结果。

关键字段：

- `group_key`
- `target_name`
- `service_name`
- `exception_type`
- `message`
- `top_stack_frame`
- `source`
- `occurrence_count`
- `first_seen_ms`
- `last_seen_ms`
- `sample_trace_id`
- `sample_span_id`
- `sample_event_id`
- `updated_at`

### error_occurrences

保存 group 到事件或 span 的出现关系。

关键字段：

- `id`
- `group_key`
- `event_id`
- `trace_id`
- `span_id`
- `event_index`
- `timestamp_ms`
- `target_name`
- `service_name`
- `operation_name`

唯一约束：

```text
(group_key, trace_id, span_id, event_index)
```

## 异常抽取规则

优先级：

1. `LogEventList[].TagEntryList` 中的标准异常字段。
2. span 顶层 `TagEntryList` 中的异常字段。
3. Celery fallback 字段。
4. HTTP status fallback。

错误字段：

- `exception.type`
- `exception.message`
- `exception.stacktrace`
- `error.type`
- `error.message`
- `error.stack`
- `celery.exception_type`
- `celery.einfo`
- `llm.error.type`
- `llm.error.message`
- `log.level=ERROR`
- `log.original`

source 字段候选：

- `error.capture.source`
- `otel.scope.name`
- `component`

stacktrace 字段候选：

- `exception.stacktrace`
- `celery.einfo`
- `error.stack`
- `stacktrace`
- `traceback`

## fingerprint 规则

fingerprint 输入：

```text
service_name
exception_type
normalized_message
top_stack_frame
```

hash：

```text
sha1("\n".join(parts))[:16]
```

message 归一化：

- 如果 message 是多行 traceback，取最后一行异常摘要。
- 替换内存地址：`0x[0-9a-fA-F]+` -> `0x<hex>`。
- 替换长数字：13 位以上数字 -> `<long-number>`。
- 替换 UUID -> `<uuid>`。
- 替换常见 trace/span/request id -> `<id>`。
- URL 去掉 query string。
- 压缩连续空白。
- 最大保留 500 字符。

top stack frame：

- 从 stacktrace 中优先提取第一条业务栈帧。
- 跳过明显的 site-packages、otel、celery 框架包装层。
- 格式建议：`/app/path.py:function`，不包含行号。
- 如果没有 stacktrace，fallback 为空字符串。

不参与 fingerprint：

- `trace_id`
- `span_id`
- `timestamp`
- `duration`
- `operation_name`
- `code_lineno`

## 代码迁移策略

从 POC 迁移，而不是重写：

- `aliyun_cli.py` 逻辑合并为 `AliyunCliClient`。
- `time_utils.py` 合并为时间解析函数。
- `repository.py` 合并为 `TraceRepository`。
- `aggregation.py` 合并为 span/event/fingerprint 解析函数。
- `ingestion.py` 合并为 `TraceIngestionService`。
- `cli.py` 保留 argparse 入口，但改成多命令生产 UX。

必须修复的 POC 问题：

- `aliyun_cli._optional_int()` 当前误返回 `None`，后续 `try int(...)` 死代码在 `_sanitize()` 之后；迁移时必须修复并加测试。
- POC fingerprint 当前混入 `operation_name/code_lineno`，会拆散同类异常；生产版按已确认的新规则实现。
- POC 默认 profile/service/db 是固定开发值；生产版必须改成宿主项目 config 驱动。

## 文档与 skill

### SKILL.md

路径：

```text
skills/arms-exceptions-explorer/SKILL.md
```

内容要求：

- 用中文写给 Agent。
- 明确什么时候使用这个 skill：线上/测试 ARMS 中有异常，需要拉取异常 Span、聚合、回到代码排查。
- 标准流程：
  1. `doctor`
  2. `targets`
  3. `sync --target <name>`
  4. `groups --target <name>`
  5. `show <group_id> --target <name>`
  6. 根据 stacktrace 回到宿主项目代码。
- 明确不能猜测 ARMS 状态；必须以 CLI 输出为准。
- 明确凭证失败时按错误提示安装或授权阿里云 CLI。
- 明确不要打印敏感凭证。

### references/cli.md

路径：

```text
skills/arms-exceptions-explorer/references/cli.md
```

内容要求：

- 完整命令参考。
- 配置文件示例。
- 错误处理说明。
- 常见排查案例。
- CI/Agent 环境鉴权建议。
- 数据库字段和 JSON 输出说明。

### README.md

路径：

```text
README.md
```

内容要求：

- 项目用途。
- 目录结构。
- 安装到宿主项目的说明。
- 本地开发和测试命令。
- 与 POC 的关系。

## 测试计划

所有测试使用标准库 `unittest`，不依赖 pytest。

### config 测试

覆盖：

- 空仓库未配置时，`targets/sync/groups/show` 给出可修复错误。
- `init` 非交互式创建 config。
- 同名 target 默认合并 services。
- `--replace` 清空并重建 target。
- target 支持多个 services。
- service 对象保留 `name/region/pid/app_id`。

### Aliyun CLI client 测试

覆盖：

- 构造 `SearchTraceAppByPage` 命令时不包含 `--profile`。
- 构造 `SearchTracesByPage` 命令时包含 `--IsError true`。
- 命令失败时敏感信息脱敏。
- JSON parse 失败时错误可读。
- `_optional_int()` 能正确解析数字字符串和空值。

### app list 测试

覆盖：

- `SearchTraceAppByPage` 返回 `PageBean.TraceApps[]`。
- fallback `ListTraceApps` 返回混合 `TRACE/XTRACE` 时只保留 `TRACE`。
- `apps --search` 能保留匹配项。

### aggregation 测试

覆盖：

- 从 `LogEventList` 提取 `exception.type/message/stacktrace`。
- 从 span 顶层 tags 提取 Celery `celery.exception_type/celery.einfo`。
- 从普通 exception tags 提取错误事件。
- message 归一化长数字、UUID、URL query、内存地址。
- fingerprint 不因不同 trace_id/span_id/timestamp/operation/code_lineno 改变。
- fingerprint 因 service_name 或 top_stack_frame 不同而区分。

### ingestion 测试

覆盖：

- Fake client 返回异常 trace list 后，只 `GetTrace` 相关 trace。
- 只保存异常 span，不保存正常 span。
- 保存 `raw_spans/error_events/error_groups/error_occurrences`。
- 多 service 部分失败继续执行，最终退出码为 `1`。
- `sync --target` 汇总多个 service 的结果。

### CLI 输出测试

覆盖：

- `sync` 缺少 target/service 时输出可用 target/service 和下一步命令。
- `groups` 缺少 target/service 时输出同样格式。
- `show --raw-span` 输出原始 JSON。
- `show --json` 输出结构化对象。
- table 输出 message 缩略。

## 真实验收计划

在实现后，用本机真实阿里云 CLI 做 smoke test。所有命令都不能打印敏感凭证。

准备：

```bash
cd /Users/ivan/workspace/ai/arms-exceptions
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
```

应用列表：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing --search ai-service
```

在临时宿主目录中初始化：

```bash
tmpdir=$(mktemp -d)
cd "$tmpdir"
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/arms-exceptions-explorer/scripts/cli.py init \
  --target ai-service-dev \
  --branch dev \
  --service ai-service-dev \
  --service ai-service-dev-celery-worker \
  --window 24h
```

同步：

```bash
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/arms-exceptions-explorer/scripts/cli.py sync --target ai-service-dev
```

聚合列表：

```bash
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/arms-exceptions-explorer/scripts/cli.py groups --target ai-service-dev
```

详情：

```bash
group_id=<从 groups 输出复制>
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/arms-exceptions-explorer/scripts/cli.py show "$group_id" --target ai-service-dev
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/arms-exceptions-explorer/scripts/cli.py show "$group_id" --target ai-service-dev --raw-event --json
```

验收标准：

- `doctor` 能说明 CLI/API 是否可用；失败时给出下一步。
- `apps --search ai-service` 能看到 `ai-service-dev` 和 `ai-service-dev-celery-worker`。
- `.arms-exceptions/config.json` 被正确写入，且不包含 profile/token/secret。
- `sync --target ai-service-dev` 对两个 service 分别输出 summary。
- `groups --target ai-service-dev` 能看到异常聚合。
- `show` 能看到原始错误信息或堆栈。
- SQLite 中存在 `raw_spans`，且 `raw_json` 包含 ARMS 原始 span JSON。
- 所有失败信息脱敏。

## 实施步骤

### 1. 建立项目骨架

- 创建 README、skill 目录、references、scripts。
- 创建 `.gitignore`，忽略 Python 缓存、本地 SQLite、临时输出。
- 创建初始测试文件。

验收：

```bash
find /Users/ivan/workspace/ai/arms-exceptions -maxdepth 4 -type f
```

### 2. 迁移 CLI 入口和实现模块

- 在 `scripts/cli.py` 中建立轻量入口。
- 在 `scripts/arms_exceptions/` 中实现 argparse 命令、client、repository、aggregation、ingestion、time utils。
- 保持内部类和函数边界清晰，避免把所有逻辑写进命令函数。

验收：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py --help
```

### 3. 实现配置读写

- 支持 `.arms-exceptions/config.json`。
- 支持 target 多 service。
- 支持 `init` 非交互式。
- 支持 `targets`。
- 交互式 `init` 可在基础功能稳定后实现，但第一轮实现应预留同一套 config writer。

验收：

```bash
python3 -m unittest skills/arms-exceptions-explorer/scripts/test_config.py
```

### 4. 实现阿里云 CLI client

- `doctor`。
- `apps`。
- `SearchTraceAppByPage` 主路径。
- `ListTraceApps` fallback。
- `SearchTracesByPage --IsError true`。
- `GetTrace`。
- 脱敏。

验收：

```bash
python3 -m unittest skills/arms-exceptions-explorer/scripts/test_cli.py
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor --skip-api
```

### 5. 实现 SQLite repository

- 建表。
- upsert raw spans/events/groups/occurrences。
- 查询 groups/show。
- 后续 schema 变化通过轻量 migration 兼容。

验收：

```bash
python3 -m unittest skills/arms-exceptions-explorer/scripts/test_ingestion.py
```

### 6. 实现异常抽取和聚合

- 实现通用 span tags 提取。
- 实现 LogEventList 优先的 error event 提取。
- 实现 Celery fallback。
- 实现 message/top_stack_frame/fingerprint。

验收：

```bash
python3 -m unittest skills/arms-exceptions-explorer/scripts/test_aggregation.py
```

### 7. 实现 sync

- target/service 解析。
- 时间窗口解析。
- 分页拉取异常 trace list。
- `GetTrace` 回填。
- 只保存异常 span。
- 多 service 部分失败继续。

验收：

```bash
python3 -m unittest skills/arms-exceptions-explorer/scripts/test_ingestion.py
```

### 8. 实现 groups/show

- `groups --target/--service`。
- `show <group_id> --target/--service`。
- `--raw-span`、`--raw-event`、`--json`。
- 缩略 table 输出。

验收：

```bash
python3 -m unittest skills/arms-exceptions-explorer/scripts/test_cli.py
```

### 9. 编写 skill 文档

- `SKILL.md` 写 Agent 标准流程。
- `references/cli.md` 写完整命令说明。
- `README.md` 写项目说明。

验收：

```bash
sed -n '1,220p' skills/arms-exceptions-explorer/SKILL.md
sed -n '1,260p' skills/arms-exceptions-explorer/references/cli.md
```

### 10. 真实 smoke test

- 用真实 `aliyun` 跑 `doctor/apps/init/sync/groups/show`。
- 记录命令和关键结果。
- 不记录、不输出敏感凭证。

验收：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing --search ai-service
```

## 完成标准

- 所有单元测试通过。
- CLI 无第三方 Python 依赖。
- `scripts/cli.py` 作为入口可以在宿主项目 skill 中直接运行，依赖的本地实现模块随 skill 一起安装。
- 没有 profile/token/secret 写入 config、docs 或测试 fixture。
- 真实 `apps` 能列出 `ai-service-dev` 相关应用。
- 真实 `sync` 能拉取至少一个 service 的异常数据，或者在无数据时清楚说明查询范围和下一步。
- `groups/show` 能展示程序员需要的错误 message、stacktrace、trace_id、span_id 和原始 tags/span。
- 所有用户可修复错误都包含下一步命令。

## 后续扩展

- Web UI：读取同一 SQLite，展示 groups 列表和详情。
- 定时同步：增加 cron/CI 友好的 `sync --target` 调度说明。
- 多环境聚合：按 branch/env/service 增加维度。
- 更强 fingerprint：引入可配置 ignore patterns、业务栈帧规则。
- 导出：支持 `export --json` 或 `export --markdown` 给日报/告警系统消费。
