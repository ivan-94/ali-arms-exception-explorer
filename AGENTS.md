# Repository Guidelines

开发者使用语言：中文。面向用户和 Agent 的文档、错误提示、验收说明优先使用中文；代码标识符保持英文。

## 项目定位

这个仓库维护可安装的 Agent skills 及其配套 CLI。每个 skill 应该能被安装到宿主项目中，让 Agent 通过稳定的命令、文档和本地状态完成某一类排查或操作任务。

当前已有 skill：

- `arms-exceptions-explorer`：拉取、聚合并查看阿里云 ARMS 异常 Span。
- `yunxiao-mr`：管理云效 Codeup 合并请求，包括创建、列举、查看、更新、评论、项目类标、MR 类标、关闭、重开和合并。

重要边界：

- 本仓库是 skill 源项目。不要直接修改宿主项目里的安装副本，例如 `.agents/skills/<skill-name>` 或 `skills/<skill-name>`，除非用户明确要求。
- CLI 应优先保持轻量、可分发、可测试；默认使用 Python 标准库，只有明确收益大于安装成本时才引入外部依赖。
- 鉴权、密钥和用户私有配置应交给宿主环境或官方 CLI/SDK 的默认凭证链；不要把凭证写入项目配置。

## Project Structure

通用结构：

```text
README.md                         # 人类用户入口，安装、特性、快速开始
AGENTS.md                         # Agent 维护规则
docs/plans/                       # 规划和历史执行计划
skills/<skill-name>/SKILL.md      # Agent 使用手册，保持精炼
skills/<skill-name>/references/   # 详细说明，按需读取
skills/<skill-name>/scripts/      # CLI、脚本、测试和实现代码
```

当前 `arms-exceptions-explorer` 使用：

```text
skills/arms-exceptions-explorer/SKILL.md
skills/arms-exceptions-explorer/references/cli.md
skills/arms-exceptions-explorer/scripts/cli.py
skills/arms-exceptions-explorer/scripts/arms_exceptions/app.py
skills/arms-exceptions-explorer/scripts/test_*.py
```

当前 `yunxiao-mr` 使用：

```text
skills/yunxiao-mr/SKILL.md
skills/yunxiao-mr/references/cli.md
skills/yunxiao-mr/references/api.md
skills/yunxiao-mr/scripts/cli.py
skills/yunxiao-mr/scripts/acceptance.sh
skills/yunxiao-mr/scripts/test_*.py
```

## Skill Guidelines

- `SKILL.md` 面向 Agent，写最短可执行流程、触发条件、关键规则和必要入口；不要堆入长篇背景。
- 复杂参数、配置格式、JSON schema、故障排查细节放到 `references/`，并在 `SKILL.md` 里说明何时读取。
- `scripts/` 放可执行代码和测试，优先让 Agent 运行脚本而不是重写大段逻辑。
- README 面向人类用户，解释安装、能力、安全模型和常用命令。
- 新增或修改 skill 行为时，同步检查 README、`SKILL.md`、相关 reference 和测试是否仍一致。
- `docs/plans/` 可以记录规划和历史决策，但不要把历史计划当作当前 CLI 行为的权威来源。

## Coding Guidelines

- CLI 入口文件只做参数入口和轻量转发；核心逻辑放到可测试模块中。
- 外部服务调用集中在客户端封装里，便于 mock；命令函数负责解析参数、调用服务、格式化输出。
- CLI import 不应产生副作用；所有执行入口放在 `main()` 和 `if __name__ == "__main__"` 路径下。
- 用户可见错误必须说明如何修复，并给出可直接运行的“下一步”命令。
- 命令示例里的脚本路径应动态计算或使用当前入口路径，避免固定成某个安装目录。
- 不要让命令静默跨越多个项目、环境、账号或 service；遇到不明确输入时宁可报错并列出可选项。
- 表格输出允许缩略字段，但必须提供查看完整内容的命令或参数。
- 数据库、缓存、下载内容和聚合逻辑都要可测试；新增行为优先补 `unittest`。

## CLI Best Practices

这个仓库的 CLI 主要给 Agent 使用，同时也要方便人类手动排查。实现新命令或修改现有命令时遵循这些规则：

- 默认输出面向人类，结构化消费使用 `--json`；不要让人类可读输出变成难扫的 JSON。
- `stdout` 输出成功结果；`stderr` 输出错误、告警和需要用户处理的信息。
- exit code 保持稳定：成功为 `0`，用户可修复错误为 `1`，参数解析错误为 `2`，中断为 `130`。
- 顶层无参数时打印完整 help 并返回 `0`；不要只输出 argparse 默认的“缺少 command”。
- 每个子命令都要有清晰的 description、示例和常见下一步；参数错误也要提示 `--help` 或可直接运行的修复命令。
- 用户可见错误要包含三部分：发生了什么、为什么可能发生、下一步怎么修复。
- 参数名保持直观稳定，优先使用完整单词，例如 `--target`、`--service`、`--window`、`--raw-event`；避免后续难以兼容的缩写。
- `--json` 输出应保持机器可读，字段名稳定，包含足够的错误定位信息，但不要包含凭证。
- `--verbose` 只能增加诊断信息，不能打印敏感命令、Token、签名 URL 或完整鉴权头。
- 读取外部服务时，优先在请求端过滤数据；不要把大量无关数据拉到本地后再过滤。
- 时间参数要支持明确时区；输出时间格式保持一致，避免让 Agent 在本地时区和远端服务时间之间猜测。
- 新增 raw 输出选项时，要说明用途、默认关闭，并确认不会泄露凭证。

## Security Rules

- 不要打印、保存或提交凭证：AccessKey、Secret、Token、OAuth code、签名、Authorization header、签名 URL 等。
- 项目配置只保存非凭证信息，例如 target、branch、region、service、app id、默认窗口等。
- CLI 不应主动绕过官方凭证链；需要切换身份时，引导用户在对应官方工具中切换默认身份。
- 本地数据目录、SQLite 数据库、缓存和临时同步数据不能提交。
- 涉及真实生产、预发或用户数据时，最终回复只总结必要证据，不粘贴大段原始数据。

## Current CLI Notes

`arms-exceptions-explorer` 当前核心命令：

- `doctor`：检查本地工具、默认凭证和 API 连通性。
- `apps`：列出当前身份可见的应用或服务。
- `init`：初始化或更新宿主项目配置。
- `targets`：列出已配置的 target/service。
- `sync`：按明确范围同步异常数据。
- `groups`：查看本地异常聚合列表。
- `show`：查看单个异常组详情、occurrence、stacktrace、raw event/span。

当前行为约束：

- `doctor` 在没有项目配置时应返回未就绪状态，并引导用户执行后续配置命令。
- `init` 应创建本地数据忽略规则，确保本地数据不会被提交，但不要忽略可提交的项目配置。
- `sync`、`groups` 必须显式指定范围；`show <group_id>` 可以在本地库中唯一定位时省略范围。
- `groups` 表格里的 `message` 是缩略展示；完整错误信息、堆栈和原始 tags 应通过 `show` 查看。

`yunxiao-mr` 当前核心命令：

- `doctor`：检查 Codeup remote 推断、非凭证缓存和云效 API 连通性；Agent 解析优先用 `doctor --json`。
- `create`：创建 MR；`--json` 顶层提供 `localId`、`status`、`url`、`detailUrl`、`webUrl`，并保留完整 `merge_request`。
- `list`：列举 MR，文本表格 URL 应优先展示 MR 详情页而不是仓库首页。
- `view`：查看 MR 详情，可用 `--comments` 同时读取评论。
- `edit`：只更新标题和描述，不支持修改目标分支。
- `label list/create/delete/add/remove`：管理项目级类标和 MR 类标；`add/remove` 必须覆盖式重写完整类标 ID 列表。
- `comment`：创建 MR 全局评论。
- `close` / `reopen`：关闭和重开 MR。
- `merge`：合并 MR；`--delete-branch` 会在合并成功后删除源分支。

当前行为约束：

- `.arms-exceptions/yunxiao.json` 只保存非凭证缓存：`domain`、`api_domain`、`organization_id`、`repository_identity`、`repository_id`、默认分支等。
- 标准 Codeup remote 的 Git/页面域名是 `codeup.aliyun.com`，OAPI 接入点默认是 `openapi-rdc.aliyuncs.com`，不要把二者混用。
- `YUNXIAO_ACCESS_TOKEN` 只从环境变量读取，不写入配置、日志、报告或测试产物。
- 403 错误如果表现为 `doctor`/`label list` 可读但 `create`、`label create/delete` 失败，优先判断 token 缺少 Codeup 合并请求或项目类标写权限。
- 项目类标创建后需要清理时使用 `label delete <name-or-id>`；同名类标要改用 ID。
- 真实验收脚本只能在用户明确授权真实 Codeup 仓库操作时运行。

## Testing

默认测试命令：

```bash
python3 -m unittest discover -s skills/arms-exceptions-explorer/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/yunxiao-mr/scripts -p 'test_*.py'
```

本地 smoke test：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor --skip-api
python3 skills/arms-exceptions-explorer/scripts/cli.py --help
python3 skills/arms-exceptions-explorer/scripts/cli.py show --help
python3 skills/yunxiao-mr/scripts/cli.py doctor --json --skip-api
python3 skills/yunxiao-mr/scripts/cli.py label delete --help
```

真实外部服务 smoke test 只有在用户已授权并明确允许时运行。运行时只输出必要结果，避免泄露凭证和敏感业务数据。

## Git Hygiene

- 可能存在用户或其他 Agent 的未提交改动。修改前先看 `git status --short`，不要回滚自己没有创建的变更。
- 测试产生的 `__pycache__/`、`*.pyc`、临时数据库、本地数据目录和缓存不要提交。
- 如果需要提交，提交前至少运行相关 unittest 和 `git diff --check`。
