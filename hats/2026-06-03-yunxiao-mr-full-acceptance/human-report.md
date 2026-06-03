# 云效 MR CLI 完整验收报告

## 来源清单

- 用户请求：基于 `hat-copilot` 对 `yunxiao-mr` skill 做完整验收，必须覆盖新建的所有命令。
- 测试仓库：`git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git`。
- Skill 入口：`skills/yunxiao-mr/SKILL.md`。
- CLI 文档：`skills/yunxiao-mr/references/cli.md`。
- API 文档：`skills/yunxiao-mr/references/api.md`。
- CLI 实现：`skills/yunxiao-mr/scripts/cli.py`。
- 单元测试：`skills/yunxiao-mr/scripts/test_cli.py`。
- 验收产物目录：`hats/2026-06-03-yunxiao-mr-full-acceptance/artifacts/rerun-20260603104713/`。
- 项目规则：`AGENTS.md`。
- 工作流规则：`~/.agents/docs/agents/workflows.md`。
- 交接规则：`~/.agents/docs/agents/handoff-policy.md`。
- 官方 API 依据：阿里云云效 `CreateChangeRequest`、`GetChangeRequest`、`ListChangeRequests`、`CreateProjectLabel`、`GetProjectLabels` 文档。

## 结论

状态：部分通过，阻塞于 token 的写 API 权限。

本次验收覆盖了所有新命令的调用面，但真实服务只完成到 `doctor`、`label list` 和错误路径。`label create` 与 `create` 均返回云效 403：`Current token has no permission to api.`。因此依赖已创建 MR 的 `list/view/edit/label add/label remove/comment/close/reopen/merge` 无法在真实仓库继续执行。

验收过程中发现并修复了一个真实问题：CLI 原先把 Git remote 域名 `codeup.aliyun.com` 当作 OAPI base，实际会返回 HTML。已改为缓存 `api_domain`，标准 Codeup remote 默认推断为 `openapi-rdc.aliyuncs.com`。修复后 `doctor` 可成功访问云效 OAPI 并缓存 `repository_id=6936288`。

## 已执行验证

- 通过：`python3 -m unittest discover -s skills/yunxiao-mr/scripts -p 'test_*.py'`
- 通过：`python3 -m py_compile skills/yunxiao-mr/scripts/cli.py skills/yunxiao-mr/scripts/test_cli.py`
- 通过：`doctor --skip-api` 的 Codeup remote 推断，写入 `api_domain: openapi-rdc.aliyuncs.com`。
- 通过：真实测试仓库 clone。
- 通过：临时 base/head 分支创建、提交、推送。
- 通过：`doctor` 真实 API 校验，缓存仓库 ID。
- 通过：`label list --json`，返回仓库已有类标列表。
- 覆盖但失败：`label create`，云效返回 403 写 API 权限不足。
- 覆盖但失败：`create`，云效返回 403 写 API 权限不足。
- 通过：缺少 `YUNXIAO_ACCESS_TOKEN` 时返回可操作错误。
- 通过：删除临时远端分支并确认远端无残留。

## 命令覆盖状态

| 命令 | 结果 | 证据 |
| --- | --- | --- |
| `doctor` | 通过 | `doctor.status=0`，`doctor.out` 显示 `api: ok`、`repository_id: 6936288` |
| `label list --json` | 通过 | `label_list_json.status=0`，JSON 可解析 |
| `label create` | 阻塞 | `label_create_json.status=1`，403 `Current token has no permission to api.` |
| `create` | 阻塞 | `create_mr_json.status=1`，403 `Current token has no permission to api.` |
| `list` | 未到达 | 需要先有 MR；`create` 被权限阻塞 |
| `view` | 未到达 | 需要先有 MR；`create` 被权限阻塞 |
| `edit` | 未到达 | 需要先有 MR；`create` 被权限阻塞 |
| `label add` | 未到达 | 需要先有 MR；`create` 被权限阻塞 |
| `label remove` | 未到达 | 需要先有 MR；`create` 被权限阻塞 |
| `comment` | 未到达 | 需要先有 MR；`create` 被权限阻塞 |
| `close` | 未到达 | 需要先有 MR；`create` 被权限阻塞 |
| `reopen` | 未到达 | 需要先有 MR；`create` 被权限阻塞 |
| `merge` | 未到达 | 需要先有 MR；`create` 被权限阻塞 |

## 临时数据

- 临时 base 分支：`codex-yunxiao-base-20260603104714`
- 临时 head 分支：`codex-yunxiao-head-20260603104714`
- 临时类标名：`codex-yunxiao-20260603104714`
- 实际改用已有类标尝试创建 MR：`测试通过`
- MR：未创建成功。
- 清理结果：`cleanup_base.status=0`、`cleanup_head.status=0`、`verify_remote_cleanup.status=0`，远端 heads 输出为空。

## 风险与后续

- 当前 token 至少具备读仓库/读类标能力，但不具备创建 MR 或创建项目类标的 OAPI 权限。
- 要完成剩余真实验收，需要提供具备 Codeup 合并请求读写、项目类标读写权限的云效个人访问令牌，或在测试仓库中预先创建一个可操作的 MR localId。
- 获得写权限后，应从 `create` 重新开始，继续覆盖 `list/view/edit/label add/label remove/comment/close/reopen/merge`。
