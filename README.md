# Agent Skills for Ali Cloud Workflows

[![skills.sh](https://skills.sh/b/ivan-94/ali-arms-exception-explorer)](https://skills.sh/ivan-94/ali-arms-exception-explorer)

这个仓库提供面向 Agent 的阿里云工作流 skills。

当前包含：

- **ARMS Exceptions Explorer**：拉取、聚合并查看阿里云 ARMS 异常调用链 Span。
- **Yunxiao MR**：在云效 Codeup 仓库创建、查看、更新、评论、打类标、关闭、重开和合并 MR。

## Yunxiao MR

在需要管理云效 Codeup 合并请求的项目里安装 skill：

```bash
npx skills@latest add ivan-94/ali-arms-exception-explorer \
  --skill yunxiao-mr \
  -a codex
```

配置云效个人访问令牌：

```bash
export YUNXIAO_ACCESS_TOKEN=<personal_access_token>
```

让 Agent 执行云效 MR 流程，或手动运行：

```bash
python3 skills/yunxiao-mr/scripts/cli.py doctor --json
python3 skills/yunxiao-mr/scripts/cli.py create --title "修复异常聚合" --body-file /tmp/mr.md --json
python3 skills/yunxiao-mr/scripts/cli.py list --state opened
python3 skills/yunxiao-mr/scripts/cli.py view <localId> --comments
python3 skills/yunxiao-mr/scripts/cli.py label add <localId> HAT-Ready --create-missing-label
python3 skills/yunxiao-mr/scripts/cli.py label delete HAT-Ready
```

第一次运行时，CLI 会从 Codeup Git remote 推断仓库信息，并把非凭证缓存写入 `.arms-exceptions/yunxiao.json`。标准 Codeup remote 会把 Git/页面域名 `codeup.aliyun.com` 和 OAPI 接入点 `openapi-rdc.aliyuncs.com` 分开缓存。凭证只从 `YUNXIAO_ACCESS_TOKEN` 读取，不写入仓库。

`create --json` 顶层会输出 `localId`、`status`、`url`、`detailUrl`、`webUrl`，方便 Agent 直接拿到 MR ID 和详情页链接。项目级临时类标可以用 `label delete <name-or-id>` 清理。

完整说明见 **[skills/yunxiao-mr](./skills/yunxiao-mr/SKILL.md)**。

## ARMS Exceptions Explorer

一个用于排查阿里云 ARMS 异常调用链的 Agent skill。它会把异常 Span 拉到代码仓库本地，按错误指纹聚合，并给 Codex 或 Claude 提供可追溯的调试证据。

线上异常不应该靠 ARMS 控制台截图传递。把这个 skill 安装到应用仓库，配置好对应环境的 ARMS service，Agent 就可以同步最近的异常 Span 到本地 SQLite，再基于异常组、堆栈和 trace/span 证据回到代码里排查。

这个项目刻意保持简单：一个 skill，一个 Python CLI，不依赖阿里云 Python SDK，也不保存凭证。

### 快速开始

1. 在需要排查的项目里安装 skill：

```bash
npx skills@latest add ivan-94/ali-arms-exception-explorer \
  --skill arms-exceptions-explorer \
  -a codex
```

2. 确认本机阿里云 CLI 可用：

```bash
brew install aliyun-cli
aliyun configure --mode OAuth
```

3. 让 Agent 执行 ARMS 调查流程，或手动运行：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing --search my-service
python3 skills/arms-exceptions-explorer/scripts/cli.py init
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target staging
python3 skills/arms-exceptions-explorer/scripts/cli.py groups --target staging
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id>
```

执行后，Agent 会拿到限定范围内的异常组、样本堆栈、`trace_id`、`span_id`、必要时的原始事件 tags，以及足够回到代码排查的上下文。

### 为什么做这个

我做这个 skill，是为了修掉 Agent 排查 ARMS 服务时反复出现的三个问题。

### #1：Agent 用不了你的 ARMS 截图

**问题**：ARMS 里有很多有用的异常数据，但 Agent 经常只能看到截图、复制片段或二手摘要。这样会丢掉 trace ID、span ID、tags、栈帧和时间信息。

**解决方式**：给 Agent 一个可以执行的读取路径：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id>
```

CLI 输出就是事实来源，不再依赖 UI 截图。

### #2：环境和 worker 容易混在一起

**问题**：一个代码仓库可能对应多个 ARMS service：Web 服务、worker、beat 进程、staging、production、test。如果 Agent 一次读完所有服务，很容易追错异常。

**解决方式**：同步和聚合列表必须有明确范围。`sync`、`groups` 都要求传 `--target` 或 `--service`；`show` 可以直接用本地唯一的 `group_id`，无法唯一定位时再按错误提示补范围。

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target production
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --service api-worker
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id>
```

### #3：原始 trace 太吵

**问题**：原始 trace 很大。大多数调试会话真正需要的是异常类型、错误信息、顶部业务栈帧、出现次数和少量 trace 证据。

**解决方式**：skill 会在本地保存原始 span，但默认先展示聚合后的异常。需要深入时再打开原始数据：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --raw-event
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --raw-span --json
```

### 它会做什么

- 发现当前 `aliyun` CLI 身份能看到的 ARMS TRACE 应用。
- 创建项目本地的 `.arms-exceptions/config.json`。
- 先调用 `SearchTracesByPage --IsError true` 查询异常 Span。
- 再调用 `GetTrace` 回填异常 trace/span 详情。
- 把本地调查数据保存到 SQLite。
- 按 service、异常类型、归一化错误信息和顶部栈帧聚合异常。
- 在缺少授权、配置或范围时输出下一步命令。

### 安全模型

这个工具把身份认证交给阿里云 CLI。

它不会保存 `AccessKey`、`AccessKeySecret`、`SecurityToken`、OAuth code、签名 URL 或 profile，也不会替你传 `--profile`。如果需要切换身份，请先在 `aliyun` 里切换：

```bash
aliyun configure switch --profile <profile>
```

项目配置通常可以提交：

```text
.arms-exceptions/config.json
```

本地 trace 数据不要提交：

```text
.arms-exceptions/data/
```

### 参考

### Skill

- **[arms-exceptions-explorer](./skills/arms-exceptions-explorer/SKILL.md)** - 从宿主项目拉取、聚合并查看阿里云 ARMS 异常 Span。

### CLI

完整 CLI 文档见 **[skills/arms-exceptions-explorer/references/cli.md](./skills/arms-exceptions-explorer/references/cli.md)**。

| 命令 | 用途 |
| --- | --- |
| `doctor` | 检查本地 `aliyun` CLI 和 ARMS API 访问。 |
| `apps` | 列出当前身份可见的 ARMS TRACE 应用。 |
| `init` | 创建或更新 `.arms-exceptions/config.json`。 |
| `targets` | 查看已配置的 target 和 service。 |
| `sync` | 为一个 target 或 service 拉取最近的异常 Span。 |
| `groups` | 从本地数据库列出异常聚合组。 |
| `show` | 查看一个异常组的样本堆栈、occurrence 和原始数据。 |

<details>
<summary>项目配置示例</summary>

```json
{
  "version": 1,
  "default_window": "24h",
  "targets": [
    {
      "name": "staging",
      "branch": "main",
      "default_window": "24h",
      "services": [
        {
          "name": "my-service-staging",
          "region": "cn-beijing",
          "pid": "hdt8ujazrm@...",
          "app_id": "7041129"
        },
        {
          "name": "my-service-staging-worker",
          "region": "cn-beijing",
          "pid": "hdt8ujazrm@...",
          "app_id": "7062380"
        }
      ]
    }
  ]
}
```

</details>

## 开发

运行测试：

```bash
python3 -m unittest discover -s skills/arms-exceptions-explorer/scripts -p 'test_*.py'
```

运行不调用 ARMS 的本地 smoke test：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor --skip-api
```

运行真实 ARMS smoke test：

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region cn-beijing --search my-service
```
