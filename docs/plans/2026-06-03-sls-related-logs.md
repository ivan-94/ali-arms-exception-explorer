# SLS 关联日志执行计划

## Source Manifest

### Sources

- 当前对齐讨论：用户要求为 `arms-exceptions-explorer` 实现通过异常 span 关联 SLS 日志，并使用 `grill-me` 逐项对齐需求和实现方式。
- 当前对齐讨论：第一版使用 CLI 直连 SLS 查询，不把 ARMS 控制台关联配置作为运行时前提。
- 当前对齐讨论：`show` 默认聚合展示关联日志，提供 `--no-logs` 显式关闭；同时保留独立 `logs <group_id>` 命令。
- 当前对齐讨论：默认只查 1 个 occurrence，默认窗口为 occurrence 前后 2 分钟，每个 occurrence 最多 50 条日志。
- 当前对齐讨论：SLS query 默认只使用 `trace_id` 全文关键词，不做字段查询，不追加 `span_id`、service、container 过滤。
- 当前对齐讨论：SLS 是可选增强；未配置、查询失败或查空都不能破坏 `show` 的 ARMS 主证据输出。
- 当前对齐讨论：`init` 支持交互式和非交互式 SLS 配置；交互式可从 ARMS 只读导入已有 SLS 关联配置作为候选默认值，但不写回 ARMS。
- 当前对齐讨论：使用现有 `aliyun sls` OpenAPI 风格命令，不引入 `aliyunlog` 依赖。
- 代码入口：`/Users/ivan/workspace/ai/arms-exceptions/skills/arms-exceptions-explorer/scripts/cli.py`。
- 当前核心实现：`/Users/ivan/workspace/ai/arms-exceptions/skills/arms-exceptions-explorer/scripts/arms_exceptions/app.py`。
- 当前 CLI reference：`/Users/ivan/workspace/ai/arms-exceptions/skills/arms-exceptions-explorer/references/cli.md`。
- 当前 Agent skill 文档：`/Users/ivan/workspace/ai/arms-exceptions/skills/arms-exceptions-explorer/SKILL.md`。
- 当前 README：`/Users/ivan/workspace/ai/arms-exceptions/README.md`。
- 全局工作流规则：`/Users/ivan/.agents/docs/agents/workflows.md`。
- 全局交接要求：`/Users/ivan/.agents/docs/agents/handoff-policy.md`。
- 本机探索证据：`aliyun sls help` 可用，并列出 `ListProject`、`ListLogStores`、`GetLogs`、`GetLogsV2`。
- 本机探索证据：`aliyun arms help` 暴露 `GetTraceAppConfig` 和 `SaveTraceAppConfig`；日志关联配置项可通过 `GetTraceAppConfig` 只读获取，但该接口仅适用于接入应用监控的应用，不适用于可观测链路 OpenTelemetry 版。
- 阿里云文档：ARMS 日志分析配置说明 `https://help.aliyun.com/zh/arms/application-monitoring/user-guide/log-analysis`。
- 阿里云文档：SLS GetLogs CLI/API 说明 `https://www.alibabacloud.com/help/en/sls/developer-reference/get-logs`、`https://www.alibabacloud.com/help/en/sls/developer-reference/use-getlogs-to-query-logs`。

### Produced artifacts

- 本计划：`/Users/ivan/workspace/ai/arms-exceptions/docs/plans/2026-06-03-sls-related-logs.md`。

### Key decisions

- SLS 配置挂在 `ServiceConfig.sls`，不是 target 或全局配置。
- 第一版实时查询 SLS，不把业务日志落库。
- `doctor` 只做浅检查：报告 `aliyun sls` 是否可用和多少 service 已配置 SLS，不访问真实 project/logstore；SLS 结果不影响整体 ARMS status。
- `init` 非交互式的 `--sls-*` 参数应用到本次所有 `--service`；多个 service 需要不同 SLS 配置时可分多次执行 `init`。
- `init` 交互式逐个 service 配置 SLS；用户可选择、手动输入、保留、修改、清除或跳过。
- 重复 `init` 默认保留已有 SLS 配置，除非用户明确修改或清除。
- ARMS 控制台 SLS 关联配置只做 read-only import 候选，不调用 `SaveTraceAppConfig`。
- 本地配置不保存 ARMS 的 `SLS.index`，只保存 CLI 实际使用的 `project/logstore/endpoint/window/limit`。
- SLS 查询继承 `show/logs` 的 target/service scope；每条 occurrence 使用自身 service 的 SLS 配置。
- 多 occurrence 查询按 `trace_id` 去重。
- `sync` 默认刷新本次 target/service scope 的本地旧异常数据；需要保留旧数据时显式使用 `--keep-old-data`。
- 默认测试 mock SLS，不访问真实日志服务；真实 SLS 验收留给人工验收阶段。

### Verification evidence

- 已只读探索现有 CLI：`cli.py` 只转发到 `arms_exceptions.app.main()`；同步、聚合、展示逻辑在 `app.py`。
- 已只读探索现有数据模型：当前只有 `raw_spans`、`error_groups`、`error_events`、`error_occurrences` 等 ARMS trace/异常表，没有 SLS 配置和日志表。
- 已只读探索现有 ingestion：`sync` 使用 `SearchTracesByPage --IsError true` 后调用 `GetTrace`，并解析 span 内嵌 `LogEventList`。
- 已只读探索本机工具：`aliyun` 版本为 `3.3.18`；`aliyun sls` 可用；`aliyunlog` 当前不在 PATH。
- 未运行真实 SLS 查询；原因是需要真实 project/logstore、账号权限和用户允许，计划放到人工验收阶段。

### Open questions / risks

- `GetTraceAppConfig` 返回的 ARMS 配置结构可能因应用类型不同而缺失或不可用；实现必须失败降级到 SLS 列表选择或手动输入。
- SLS 全文查询依赖 Logstore 开启全文索引；CLI 无法保证用户环境已经配置。
- 业务日志可能包含敏感数据；默认输出必须限制条数、截断字段，完整 raw log 只能通过显式参数展示。
- `aliyun sls GetLogs` 的 JSON 返回形态可能随 CLI/OpenAPI 变化；日志 normalizer 需要宽松解析并保留 raw fallback。

## 目标

为 `arms-exceptions-explorer` 增加 SLS 关联日志能力，让 Agent 在查看异常组时能同时看到 ARMS 异常证据和同一 `trace_id` 的业务日志上下文。

第一版关注排查闭环，而不是做通用 SLS 查询器：

1. `show <group_id>` 默认展示关联日志。
2. `logs <group_id>` 提供独立日志查询入口。
3. SLS 缺失或失败不影响 ARMS 主流程。
4. `init` 能为 service 配置 SLS project/logstore/endpoint。
5. 默认输出对人类和 Agent 可读，结构化消费使用 `--json`。

## 非目标

- 不写回 ARMS 控制台 SLS 关联配置。
- 不自动修改应用日志采集配置、Logtail 配置或 SLS 索引。
- 不把 SLS 日志落库。
- 不引入 `aliyunlog` 或阿里云 Python SDK。
- 不实现字段查询模式、SQL 分析或分页游标。
- 不默认查询多个 service 或全部 target。

## 配置结构

在 `ServiceConfig` 增加可选 `sls` 字段：

```json
{
  "name": "ai-service-dev",
  "region": "cn-beijing",
  "pid": "xxx",
  "app_id": "xxx",
  "sls": {
    "project": "my-project",
    "logstore": "app-log",
    "endpoint": "cn-beijing.log.aliyuncs.com",
    "default_before_seconds": 120,
    "default_after_seconds": 120,
    "default_limit": 50
  }
}
```

规则：

- `sls` 可选；未配置时 ARMS 功能照常工作。
- `endpoint` 必填；交互式 init 可从 project region 推导默认值，用户可覆盖。
- `default_before_seconds`、`default_after_seconds`、`default_limit` 可缺省，代码 fallback 到 `120/120/50`。
- 不保存 `trace_id_fields`、`span_id_fields` 或 `arms_index`；第一版只做全文关键词查询。

## CLI 接口

### init

非交互式新增参数：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py init \
  --target ai-service-dev \
  --service ai-service-dev \
  --sls-project my-project \
  --sls-logstore app-log \
  --sls-endpoint cn-beijing.log.aliyuncs.com
```

行为：

- `--sls-*` 同时应用到本次命令里的所有 `--service`。
- 未传 `--sls-*` 时保留已有 service 的 SLS 配置。
- 非交互式第一版不导入 ARMS SLS 配置，也不提供 `--clear-sls`。

交互式流程：

1. 选择 ARMS service 后，逐个 service 询问是否配置 SLS。
2. 如果 service 有 `pid`，尝试 `GetTraceAppConfig` 读取 `profiler.SLS.regionId/project/logStore` 作为候选。
3. 读取失败、无 pid、无权限、非应用监控应用或返回为空时，不中断 init。
4. 尝试用 `aliyun sls ListProject`、`ListLogStores` 拉列表供用户选择。
5. 拉列表失败时降级为手动输入 project/logstore/endpoint。
6. 已有 SLS 配置时提供保留、修改、清除、跳过。

### show

新增参数：

```bash
show <group_id> --no-logs
show <group_id> --log-occurrences 3
show <group_id> --log-before 5m
show <group_id> --log-after 1m
show <group_id> --log-limit 100
show <group_id> --raw-logs
```

默认行为：

- 默认查询 1 个 occurrence 的 SLS 日志。
- 日志查询继承 `show` 的 scope。
- 对每个 occurrence 按自身 `service_name` 找 SLS 配置。
- 按 `trace_id` 去重。
- SLS query 只包含 `trace_id` 全文关键词。
- 查询失败不影响 `show` 退出码。

人类可读输出新增 `related_logs` 段：

```text
related_logs: ok
query:
  service: ai-service-dev
  project: my-project
  logstore: app-log
  endpoint: cn-beijing.log.aliyuncs.com
  trace_id: 0161403a...
  window: 2026-06-03 10:23:00 +0800 -> 2026-06-03 10:27:00 +0800
  limit: 50
logs:
- 2026-06-03 10:25:00 +0800 level=ERROR source=stderr pod=ai-service-dev-... message=...
```

状态：

- `ok`：查询成功且有日志。
- `empty`：查询成功但无日志；展示查询条件和下一步提示。
- `not_configured`：service 未配置 SLS；展示配置命令。
- `failed`：SLS 查询失败；展示脱敏后的错误和下一步提示。
- `skipped`：用户传了 `--no-logs`。

`show --json` 保持现有字段不变，新增顶层 `related_logs`：

```json
{
  "related_logs": {
    "status": "ok",
    "queries": [
      {
        "service_name": "ai-service-dev",
        "trace_id": "0161403a...",
        "project": "my-project",
        "logstore": "app-log",
        "endpoint": "cn-beijing.log.aliyuncs.com",
        "from": 1780381380,
        "to": 1780381620,
        "query": "0161403a...",
        "limit": 50,
        "items": []
      }
    ]
  }
}
```

### logs

新增独立命令：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py logs <group_id>
python3 skills/arms-exceptions-explorer/scripts/cli.py logs <group_id> --target ai-service-dev
python3 skills/arms-exceptions-explorer/scripts/cli.py logs <group_id> --occurrences 3
python3 skills/arms-exceptions-explorer/scripts/cli.py logs <group_id> --before 5m --after 1m --limit 100
python3 skills/arms-exceptions-explorer/scripts/cli.py logs <group_id> --raw
```

规则：

- scope 解析和 `show` 一致：group_id 本地唯一时可省略 scope，否则提示补 `--target` 或 `--service`。
- 查询语义和 `show` 的日志部分一致。
- 独立 `logs` 命令查询失败返回 `1`。

### doctor

默认只做浅检查：

- `aliyun` 是否可用。
- `aliyun sls help` 是否可调用。
- 当前 config 里有多少 service 配了 `sls`。

输出示例：

```text
sls_api_available: true
sls_configured_services: 2
sls_optional: true
```

SLS 检查不访问真实 project/logstore，不影响整体 `status`。

## 内部设计

### 数据模型

新增 dataclass：

```python
@dataclass(frozen=True)
class SlsConfig:
    project: str
    logstore: str
    endpoint: str
    default_before_seconds: int = 120
    default_after_seconds: int = 120
    default_limit: int = 50
```

`ServiceConfig` 增加：

```python
sls: SlsConfig | None = None
```

### SLS Client

新增 `AliyunCliClient` 方法或独立 `SlsClient`：

- `sls_available() -> bool`
- `list_sls_projects(...)`
- `list_sls_logstores(project, endpoint=None, ...)`
- `get_sls_logs(project, logstore, endpoint, from_s, to_s, query, line, reverse=True)`

调用使用现有 `aliyun`：

```bash
aliyun sls GetLogs \
  --project <project> \
  --logstore <logstore> \
  --from <from_s> \
  --to <to_s> \
  --query <trace_id> \
  --line <limit> \
  --reverse true \
  --endpoint <endpoint>
```

### 日志归一化

新增 normalizer：

- 宽松识别返回中的列表字段，例如 `logs`、`data`、`LogList`。
- 每条日志提取：
  - 时间
  - source/container/pod
  - level
  - message
  - `log.original`
  - request_id
  - trace_id
- `content` 如果是 JSON 字符串，尝试解析；解析失败则按字符串展示。
- 默认输出精简字段并截断；`--raw-logs` / `logs --raw` 才包含原始 item。

### 错误分类

SLS 错误需要给出下一步：

- `ProjectNotExist`：检查 project、endpoint、账号和区域。
- `LogStoreNotExist`：检查 logstore。
- `Unauthorized`、`Forbidden`、`NoPermission`：检查 SLS 读权限。
- 空结果：检查日志采集、全文索引、trace_id 是否写入日志、时间窗口。
- `aliyun sls` 不可用：检查阿里云 CLI 版本或插件可用性。

所有错误输出继续使用现有脱敏逻辑。

## 实现切片

1. 配置模型和解析
   - 增加 `SlsConfig`。
   - 更新 `ProjectConfig.from_dict()` / `to_dict()`。
   - 保持旧配置兼容。

2. SLS client 和日志 normalizer
   - 封装 `aliyun sls`。
   - 增加 query/window/limit 计算。
   - 增加日志返回归一化。

3. repository 查询支撑
   - 复用 group/scope 解析。
   - 为日志查询提供按 scope 过滤的 occurrences。
   - 不新增日志表。

4. CLI 命令
   - 扩展 `show` 参数和输出。
   - 新增 `logs` 命令。
   - 扩展 `doctor` 浅检查。
   - 扩展 `init` 非交互式和交互式配置。

5. 文档和测试
   - 更新 README。
   - 更新 `SKILL.md`。
   - 更新 `references/cli.md`。
   - 增加 unittest 覆盖配置、query、输出状态、错误分类。

## 测试计划

默认测试不访问真实 SLS：

```bash
python3 -m unittest discover -s skills/arms-exceptions-explorer/scripts -p 'test_*.py'
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor --skip-api
python3 skills/arms-exceptions-explorer/scripts/cli.py --help
python3 skills/arms-exceptions-explorer/scripts/cli.py show --help
python3 skills/arms-exceptions-explorer/scripts/cli.py logs --help
git diff --check
```

建议新增测试：

- `SlsConfig` 解析和序列化。
- 重复 init 保留已有 SLS 配置。
- 非交互式 `--sls-*` 应用到多个 service。
- `show` 在 SLS 未配置时输出 `related_logs: not_configured` 且返回 0。
- `show` 在 SLS 查询失败时输出 `related_logs: failed` 且返回 0。
- `logs` 在 SLS 查询失败时返回 1。
- 查空输出 `empty` 和查询条件。
- 多 occurrence 按 trace_id 去重。
- 日志 normalizer 处理顶层字段、`content` JSON 字符串和未知 raw item。

## 人工验收计划

真实 SLS 验收需要用户已授权并明确允许后执行。验收时不要粘贴大段业务日志或凭证。

前置条件：

- 本机 `aliyun` 已登录并能访问 ARMS。
- 当前账号能访问目标 SLS project/logstore。
- 目标应用日志已经采集到 SLS。
- 目标日志里能全文搜索到 ARMS trace_id。
- 有一个最近异常 group 可通过 `groups` 找到。

建议步骤：

1. 检查浅层 readiness：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
   ```

   期望：ARMS 主 status 通过；SLS optional 状态可见。

2. 初始化或更新 service 的 SLS 配置：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py init
   ```

   期望：交互式可选择或手动输入 project/logstore/endpoint；用户可跳过。

3. 同步异常：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target <target> --max-pages 1 --max-traces 5
   python3 skills/arms-exceptions-explorer/scripts/cli.py groups --target <target>
   ```

4. 查看统一视图：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --target <target>
   ```

   期望：输出 ARMS 异常详情，并出现 `related_logs` 段；如果有日志，能看到同 trace_id 的精简日志行。

5. 独立查看日志：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py logs <group_id> --target <target> --limit 20
   ```

   期望：查询条件可见，日志输出和控制台使用同 trace_id 查询结果一致。

6. 验证关闭日志：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --target <target> --no-logs
   ```

   期望：不访问 SLS，不展示日志查询结果。

7. 验证 JSON：

   ```bash
   python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --target <target> --json
   ```

   期望：顶层包含 `related_logs`，现有 `group/occurrences/events/sample_event/sample_span` 字段仍存在。

验收记录要求：

- 记录执行命令和状态结论。
- 不记录 AccessKey、Token、Authorization、签名 URL。
- 日志内容只保留必要字段和少量脱敏证据。
