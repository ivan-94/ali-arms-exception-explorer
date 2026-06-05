# Repository Guidelines

开发者使用语言：中文。面向用户和 Agent 的文档、错误提示、验收说明优先使用中文；代码标识符保持英文。

## 项目定位

这个仓库维护可安装的 Agent skills 及其配套 CLI。每个 skill 应该能被安装到宿主项目中，让 Agent 通过稳定的命令、文档和本地状态完成某一类排查或操作任务。

当前已有 skill：

- `arms-exceptions-explorer`：拉取、聚合并查看阿里云 ARMS 异常 Span。
- `yunxiao-mr`：管理云效 Codeup 合并请求，包括创建、列举、查看、更新、评论、项目类标、MR 类标、关闭、重开和合并。
- `arms-exceptions-triage`：在 CI/Agent 自动流程中分诊一个 ARMS target/service 的异常，二次聚合去重、深度诊断、关联 MR，并对明确 bug 派发 SubAgent(high) 修复。
- `fix-arms-exception`：从 `status=bug` 的 ARMS 诊断报告出发，在独立 worktree 中 TDD 修复，经 review Sub Agent 审查后创建云效 MR。
- `lark-notify`：通过飞书/Lark 自定义机器人 Webhook 发送 Agent 通知。
- `setup-arms-workflow`：在宿主项目检查依赖、发现 ARMS/SLS 配置、初始化 ARMS/Yunxiao/Lark，并生成本地 setup 报告。

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

当前编排型 skill 使用：

```text
skills/arms-exceptions-triage/SKILL.md
skills/arms-exceptions-triage/references/dedupe.md
skills/arms-exceptions-triage/references/mr-coverage.md
skills/arms-exceptions-triage/references/templates/
skills/fix-arms-exception/SKILL.md
skills/fix-arms-exception/references/templates/
```

当前 `lark-notify` 使用：

```text
skills/lark-notify/SKILL.md
skills/lark-notify/references/cli.md
skills/lark-notify/scripts/cli.py
skills/lark-notify/scripts/test_*.py
```

当前 `setup-arms-workflow` 使用：

```text
skills/setup-arms-workflow/SKILL.md
skills/setup-arms-workflow/references/commands.md
skills/setup-arms-workflow/references/checklist.md
skills/setup-arms-workflow/references/ignore-rules.md
skills/setup-arms-workflow/references/templates/
```

## Skill Guidelines

- `SKILL.md` 面向 Agent，写最短可执行流程、触发条件、关键规则和必要入口；不要堆入长篇背景。
- 复杂参数、配置格式、JSON schema、故障排查细节放到 `references/`，并在 `SKILL.md` 里说明何时读取。
- 编排型 skill 的 `SKILL.md` 是流程契约权威；不要在 `references/` 里重复维护完整 workflow。可复制报告、brief、payload 和配置片段优先放到 `references/templates/`。
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

- 不要打印或提交凭证：AccessKey、Secret、Token、OAuth code、签名、Authorization header、签名 URL 等。
- `lark-notify` 允许把飞书 Webhook 保存到本地忽略文件 `.arms-exceptions/lark-notify.local.json`，但不能提交、打印完整 URL 或写入报告。
- 项目配置只保存非凭证信息，例如 target、branch、region、service、app id、默认窗口等。
- CLI 不应主动绕过官方凭证链；需要切换身份时，引导用户在对应官方工具中切换默认身份。
- 本地数据目录、SQLite 数据库、缓存和临时同步数据不能提交。
- 涉及真实生产、预发或用户数据时，最终回复只总结必要证据，不粘贴大段原始数据。

## Current CLI Notes

`arms-exceptions-explorer` 当前核心命令：

- `doctor`：检查本地工具、默认凭证和 API 连通性。
- `apps`：列出当前身份可见的应用或服务。
- `sls projects`：列出当前身份可见的 SLS Project。
- `sls logstores`：列出指定 Project/endpoint 下的 SLS Logstore。
- `init`：初始化或更新宿主项目配置。
- `targets`：列出已配置的 target/service。
- `sync`：按明确范围同步异常数据。
- `groups`：查看本地异常聚合列表。
- `show`：查看单个异常组详情、occurrence、stacktrace、raw event/span。

当前行为约束：

- `doctor` 在没有项目配置时应返回未就绪状态，并引导用户执行后续配置命令。
- `init` 应创建本地数据忽略规则，确保本地数据、setup、triage、worktrees 和本地 Webhook 不会被提交，但不要忽略可提交的项目配置。
- `sls projects/logstores` 只读发现 SLS 配置，不写入 `.arms-exceptions/config.json`。
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

`lark-notify` 当前核心命令：

- `config --webhook-url <url>`：保存飞书自定义机器人 Webhook 到 `.arms-exceptions/lark-notify.local.json`，并确保本地 `.gitignore` 忽略它。
- `config --show`：显示配置状态和脱敏 Webhook。
- `send --title ... --body-file ... --format text|card`：发送文本或卡片通知。
- `send --json-file ... --format raw`：发送已构造好的原始飞书 payload。
- `send ... --dry-run`：渲染、检查大小和截断状态，不发送请求。

当前行为约束：

- Webhook 读取优先级是 `.arms-exceptions/lark-notify.local.json` > `ARMS_LARK_WEBHOOK_URL`。
- 默认不打印完整 Webhook；错误、dry-run 和 JSON 输出都要避免泄露完整 URL。
- text/card payload 超过 20 KB 时应截断正文并保留本地报告路径；raw payload 超限直接失败。
- 真实飞书发送只有在用户已配置 Webhook 并明确要求发送时运行。

`arms-exceptions-triage` / `fix-arms-exception` 当前行为约束：

- `arms-exceptions-triage` 一次只处理一个 target；service 输入必须能从 `targets --json` 唯一反查到 target。
- target 分支必须来自 `.arms-exceptions/config.json`；缺失时停止，不猜默认分支。
- 分诊产物写入宿主项目 `.arms-exceptions/triage/<run-id>/`，并要求忽略提交。
- `group_id` 只作为本次运行内定位，不作为 MR 覆盖强证据。
- 默认面向 CI 自动完整执行；对 `status=bug` 且未被强证据 MR 覆盖的项派发 SubAgent(high) 执行 `fix-arms-exception`。只有调用方显式 triage-only/只分诊时跳过修复。
- `fix-arms-exception` 必须从 `status=bug` 的诊断报告开始，可自动 push 自己创建的 `fix/arms-...` 分支并创建 MR，但不自动合并。

`setup-arms-workflow` 当前行为约束：

- 它是编排型 skill，不新增 setup CLI。
- setup 产物写入宿主项目 `.arms-exceptions/setup/`，并要求忽略提交。
- ARMS app、target、branch、service 和 SLS project/logstore 必须由用户确认；不要从模糊搜索结果自动选择。
- Yunxiao setup 只运行 doctor；缺少 `YUNXIAO_ACCESS_TOKEN` 时引导用户设置环境变量，不保存 token。
- Lark setup 可以保存本地 Webhook，但 setup 阶段不发送真实通知。
- 不自动修改宿主 `AGENTS.md`、`CLAUDE.md` 或 CI 配置；只在报告里写建议片段。

## Testing

默认测试命令：

```bash
python3 -m unittest discover -s skills/arms-exceptions-explorer/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/yunxiao-mr/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/lark-notify/scripts -p 'test_*.py'
```

本地 smoke test：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor --skip-api
python3 skills/arms-exceptions-explorer/scripts/cli.py --help
python3 skills/arms-exceptions-explorer/scripts/cli.py show --help
python3 skills/arms-exceptions-explorer/scripts/cli.py sls projects --help
python3 skills/yunxiao-mr/scripts/cli.py doctor --json --skip-api
python3 skills/yunxiao-mr/scripts/cli.py label delete --help
python3 skills/lark-notify/scripts/cli.py config --show
python3 skills/lark-notify/scripts/cli.py send --title "测试通知" --body "hello" --format card --dry-run
```

真实外部服务 smoke test 只有在用户已授权并明确允许时运行。运行时只输出必要结果，避免泄露凭证和敏感业务数据。

## Git Hygiene

- 可能存在用户或其他 Agent 的未提交改动。修改前先看 `git status --short`，不要回滚自己没有创建的变更。
- 测试产生的 `__pycache__/`、`*.pyc`、临时数据库、本地数据目录和缓存不要提交。
- 如果需要提交，提交前至少运行相关 unittest 和 `git diff --check`。
