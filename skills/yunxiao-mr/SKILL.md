---
name: yunxiao-mr
description: 管理阿里云云效 Codeup 合并请求。用于 Agent 需要在云效仓库创建、列举、查看、更新、评论、打类标、关闭、重开或合并 MR/合并请求时。
---

# 云效 MR

## Overview

这个 skill 用随仓库分发的 CLI 管理云效 Codeup 合并请求。CLI 会从当前 Git remote 推断云效组织和仓库，把非凭证缓存写到 `.arms-exceptions/yunxiao.json`，并用 `YUNXIAO_ACCESS_TOKEN` 访问云效 API。

入口始终在宿主项目根目录执行：

```bash
python3 skills/yunxiao-mr/scripts/cli.py <command>
```

## Quick Reference

| 任务 | 做法 |
| --- | --- |
| 检查配置和权限 | `doctor` |
| 创建 MR | `create --title ... --body-file ...` |
| 列举 MR | `list --state opened` |
| 查看 MR | `view <localId> --comments` |
| 更新标题/描述 | `edit <localId> --title ... --body-file ...` |
| 列举项目类标 | `label list` |
| 创建项目类标 | `label create <name>` |
| 删除项目类标 | `label delete <name-or-id>` |
| 给 MR 加类标 | `label add <localId> <name>` |
| 移除 MR 类标 | `label remove <localId> <name>` |
| 评论 MR | `comment <localId> --body-file ...` |
| 关闭/重开 MR | `close <localId>` / `reopen <localId>` |
| 合并 MR | `merge <localId> --method squash` |

完整参数、JSON 输出和 API 边界见 `references/cli.md` 与 `references/api.md`。

## Prerequisites

每次管理云效 MR 前先执行：

```bash
python3 skills/yunxiao-mr/scripts/cli.py doctor
```

如果只是检查本地 Git remote 和缓存配置，不访问云效 API：

```bash
python3 skills/yunxiao-mr/scripts/cli.py doctor --skip-api
python3 skills/yunxiao-mr/scripts/cli.py doctor --json
```

### 鉴权

CLI 只读取环境变量：

```bash
export YUNXIAO_ACCESS_TOKEN=<personal_access_token>
```

不要索要、打印或保存 token、AccessKey、SecurityToken、Authorization header、签名 URL 或任何凭证内容。

### 仓库配置

第一次运行时 CLI 会从 `origin` remote 推断仓库并写入：

```text
.arms-exceptions/yunxiao.json
```

这个文件是非凭证缓存。必要时可以人工补充 `repository_id`、`default_target_branch`、自定义 `domain` 或自定义 `api_domain`。

## Workflow

1. 检查前置条件：

   ```bash
   python3 skills/yunxiao-mr/scripts/cli.py doctor
   ```

2. 确认当前分支已经推送到云效：

   ```bash
   git push -u origin <branch>
   ```

3. 创建 MR：

   ```bash
   python3 skills/yunxiao-mr/scripts/cli.py create \
     --title "修复异常聚合" \
     --body-file /tmp/mr.md
   ```

4. 需要类标时显式添加。缺少类标默认失败；确认要新建时加 `--create-missing-label`：

   ```bash
   python3 skills/yunxiao-mr/scripts/cli.py label add <localId> HAT-Ready --create-missing-label
   ```

   临时验收类标或错误创建的项目类标可以删除：

   ```bash
   python3 skills/yunxiao-mr/scripts/cli.py label delete HAT-Ready
   ```

5. 后续状态同步：

   ```bash
   python3 skills/yunxiao-mr/scripts/cli.py view <localId> --comments
   python3 skills/yunxiao-mr/scripts/cli.py comment <localId> --body-file /tmp/comment.md
   ```

## Rules

- 先跑 `doctor`，再做任何云效 MR 操作。
- 不自动 push 分支；只在未 push 时给出 `git push -u origin <branch>`。
- 不自动合并；只有用户明确要求或执行 `merge` 时才合并。
- `label add` 和 `label remove` 必须先读取现有 MR 类标，再重写完整类标列表，避免覆盖掉无关类标。
- `--json` 用于下游工具或后续分析需要结构化数据时；`create --json` 顶层会给出 `localId`、`status`、`url`、`detailUrl`、`webUrl` 快捷字段。
- URL 展示优先使用 MR 详情页 `detailUrl`，避免把仓库首页误当 MR 链接。
- 遇到 API 失败时，先按 CLI 输出中的下一步处理，不要猜测 token 或仓库 ID。
- `.arms-exceptions/yunxiao.json` 只保存非凭证字段。

## References

```text
skills/yunxiao-mr/
  SKILL.md
  references/
    cli.md
    api.md
  scripts/
    cli.py
```

- `references/cli.md`：完整命令、参数、输出和验收步骤。
- `references/api.md`：云效 API 路径、字段和已知限制。
- `scripts/cli.py`：CLI 执行入口。
