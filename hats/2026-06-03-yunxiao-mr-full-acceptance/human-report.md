# 云效 MR CLI 完整验收报告

## 来源清单

- 用户请求：基于 `hat-copilot` 对 `yunxiao-mr` skill 做完整验收，必须覆盖新建的所有命令。
- 测试仓库：`git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git`。
- Skill 入口：`skills/yunxiao-mr/SKILL.md`。
- CLI 文档：`skills/yunxiao-mr/references/cli.md`。
- API 文档：`skills/yunxiao-mr/references/api.md`。
- CLI 实现：`skills/yunxiao-mr/scripts/cli.py`。
- 单元测试：`skills/yunxiao-mr/scripts/test_cli.py`。
- 验收产物目录：`hats/2026-06-03-yunxiao-mr-full-acceptance/artifacts/rerun-20260603105659/`。
- 项目规则：`AGENTS.md`。
- 工作流规则：`~/.agents/docs/agents/workflows.md`。
- 交接规则：`~/.agents/docs/agents/handoff-policy.md`。
- 官方 API 依据：阿里云云效 `CreateChangeRequest`、`GetChangeRequest`、`ListChangeRequests`、`CreateProjectLabel`、`GetProjectLabels` 文档。

## 结论

状态：通过。

用户补齐 token 权限后，`yunxiao-mr` CLI 已在真实 Codeup 测试仓库完成完整验收。所有新建命令均已覆盖：`doctor`、`create`、`list`、`view`、`edit`、`label list`、`label create`、`label add`、`label remove`、`comment`、`close`、`reopen`、`merge`。

本次验收创建了 MR `localId=1`，随后完成标题/描述更新、类标添加与移除、评论、关闭、重开、合并。合并后 MR 状态为 `MERGED`，目标分支为临时 base 分支，源分支通过 `--delete-branch` 删除。最终远端临时分支校验为空。

## 已执行验证

- 通过：`python3 -m unittest discover -s skills/yunxiao-mr/scripts -p 'test_*.py'`
- 通过：真实测试仓库 clone。
- 通过：临时 base/head 分支创建、提交、推送。
- 通过：`doctor` 真实 API 校验，缓存仓库 ID。
- 通过：`label list --json`。
- 通过：`label create --json`，创建临时项目类标。
- 通过：`create --json`，创建 MR 并关联临时类标。
- 通过：`list --state opened --json` 与 `list --state all`。
- 通过：`view --json` 与 `view --comments`。
- 通过：`edit --json`，更新 MR 标题和描述。
- 通过：`label add --json` 与 `label remove --json`。
- 通过：`comment --json`，创建 MR 全局评论。
- 通过：`close --json` 与 `reopen --json`。
- 通过：`merge --method squash --delete-branch --json`。
- 通过：缺少 `YUNXIAO_ACCESS_TOKEN` 时返回可操作错误。
- 通过：删除临时远端分支并确认远端无残留。

## 命令覆盖状态

| 命令 | 结果 | 证据 |
| --- | --- | --- |
| `doctor` | 通过 | `doctor.status=0`，`api: ok`，`repository_id: 6936288` |
| `label list --json` | 通过 | `label_list_json.status=0` |
| `label create` | 通过 | `label_create_json.status=0` |
| `create` | 通过 | `create_mr_json.status=0`，MR `localId=1` |
| `list` | 通过 | `list_open_json.status=0`，`list_all_text.status=0` |
| `view` | 通过 | `view_json.status=0`，`view_comments_text.status=0` |
| `edit` | 通过 | `edit_json.status=0`，后续 `view_after_edit_json.status=0` |
| `label add` | 通过 | `label_add_json.status=0`，后续 `view_after_label_add_json.status=0` |
| `label remove` | 通过 | `label_remove_json.status=0`，后续 `view_after_label_remove_json.status=0` |
| `comment` | 通过 | `comment_json.status=0`，`view_comments_json.status=0`，评论数为 1 |
| `close` | 通过 | `close_json.status=0`，后续 `view_after_close_json.status=0` |
| `reopen` | 通过 | `reopen_json.status=0`，后续 `view_after_reopen_json.status=0` |
| `merge` | 通过 | `merge_json.status=0`，`view_after_merge_json.status=0`，状态 `MERGED` |

## 临时数据

- MR localId：`1`
- MR detailUrl：`https://codeup.aliyun.com/685a564391483e233edca392/sharge-web/test/change/1`
- 临时 base 分支：`codex-yunxiao-base-20260603105701`
- 临时 head 分支：`codex-yunxiao-head-20260603105701`
- 临时类标：`codex-yunxiao-20260603105701`
- 合并 revision：`cfdc869748cb575bc5bb98bb2e5cef44b4057d55`
- 清理结果：`cleanup_base.status=0`，`cleanup_head.status=1`，`verify_remote_cleanup.status=0`，`final_remote_heads.status=0`。
- 清理说明：`cleanup_head.status=1` 是预期结果，源分支已由 `merge --delete-branch` 删除；最终远端 heads 输出为空。

## 第一轮阻塞记录

第一轮验收在权限补齐前已完成读能力验证，但 `label create` 和 `create` 返回云效 403：`Current token has no permission to api.`。用户补齐权限后，第二轮 `rerun-20260603105659` 已完整通过。

## 风险与后续

- 项目类标创建能力已验收通过，但当前 CLI 没有删除项目类标命令，因此临时类标 `codex-yunxiao-20260603105701` 会保留在测试仓库中。
- MR 已合并到临时 base 分支，随后临时 base 分支已删除；不会影响测试仓库默认分支。
- 验收过程未把 token 写入配置、报告或仓库文件。
