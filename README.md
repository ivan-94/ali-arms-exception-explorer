# Ali ARMS Exception Agent Skills

[![skills.sh](https://skills.sh/b/ivan-94/ali-arms-exception-explorer)](https://skills.sh/ivan-94/ali-arms-exception-explorer)

这个仓库提供一组给 Agent 使用的阿里云工作流 skills。安装到宿主项目后，Agent 可以通过稳定的 skill 文档和随附 CLI 完成 ARMS 异常读取、分诊、修复、云效 MR 管理和飞书通知。

README 只保留人类需要知道的入口和边界；具体执行步骤在各 skill 的 `SKILL.md` 和 `references/` 中。

## 安装

在需要接入的宿主项目根目录运行：

```bash
npx skills@latest add ivan-94/ali-arms-exception-explorer
```

安装后，把任务交给 Agent，例如：

```text
使用 setup-arms-workflow 配置当前项目的 ARMS 异常工作流
```

```text
使用 arms-exceptions-triage 分诊 production 的 ARMS 异常
```

## 包含的 Skills

| Skill | 用途 |
| --- | --- |
| [`setup-arms-workflow`](./skills/setup-arms-workflow/SKILL.md) | 在宿主项目检查依赖、发现 ARMS/SLS/Yunxiao/Lark 配置，并生成本地 setup 报告。 |
| [`arms-exceptions-explorer`](./skills/arms-exceptions-explorer/SKILL.md) | 从宿主项目拉取、聚合并查看阿里云 ARMS 异常 Span，为 Agent 提供可追溯的异常证据。 |
| [`arms-exceptions-triage`](./skills/arms-exceptions-triage/SKILL.md) | 针对一个 ARMS target/service 自动分诊异常，去重诊断、关联云效 MR，并在明确是 bug 时调度修复。 |
| [`fix-arms-exception`](./skills/fix-arms-exception/SKILL.md) | 从 `status=bug` 的诊断报告出发，在独立 worktree 中 TDD 修复异常，并创建云效 MR。 |
| [`yunxiao-mr`](./skills/yunxiao-mr/SKILL.md) | 管理云效 Codeup 合并请求，包括创建、列举、查看、更新、评论、类标、关闭、重开和合并。 |
| [`lark-notify`](./skills/lark-notify/SKILL.md) | 通过飞书/Lark 自定义机器人 Webhook 发送 Agent 通知，例如分诊报告、修复结果和 MR 链接。 |

## 人类需要知道的边界

- 这个仓库是 skill 源项目；日常使用时应安装到具体宿主项目，再让 Agent 在宿主项目里执行。
- 凭证交给宿主环境或官方工具处理：阿里云走 `aliyun` CLI 默认凭证链，云效走 `YUNXIAO_ACCESS_TOKEN`，飞书 Webhook 保存在本地忽略文件或环境变量中。
- 不要提交本地调查数据、setup 报告、triage 产物、worktree、缓存、SQLite 数据库或 Webhook 文件。
- `fix-arms-exception` 可以创建修复分支和云效 MR，但不会自动合并 MR。
- 真实 ARMS、云效或飞书操作需要宿主项目已有权限和用户明确授权。

## 维护

本仓库里的文档和 CLI 主要面向 Agent。新增或修改 skill 行为时，请同步检查：

- `README.md`
- `skills/<skill-name>/SKILL.md`
- `skills/<skill-name>/references/`
- `skills/<skill-name>/scripts/test_*.py`

默认本地测试：

```bash
python3 -m unittest discover -s skills/arms-exceptions-explorer/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/yunxiao-mr/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/lark-notify/scripts -p 'test_*.py'
```
