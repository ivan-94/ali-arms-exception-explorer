# yunxiao-mr CLI

入口：

```bash
python3 skills/yunxiao-mr/scripts/cli.py <command>
```

## 配置

凭证只读环境变量：

```bash
export YUNXIAO_ACCESS_TOKEN=<personal_access_token>
```

仓库缓存：

```text
.arms-exceptions/yunxiao.json
```

第一次运行会从 `git remote get-url origin` 自动推断并写入缓存。

## Commands

### doctor

```bash
python3 skills/yunxiao-mr/scripts/cli.py doctor
python3 skills/yunxiao-mr/scripts/cli.py doctor --skip-api
python3 skills/yunxiao-mr/scripts/cli.py doctor --json
```

`doctor --json` 输出 `ok`、仓库缓存字段和 `api.status`，缺 token 或 API 失败时也保持 JSON，便于 Agent 解析。

### create

```bash
python3 skills/yunxiao-mr/scripts/cli.py create \
  --title "修复异常聚合" \
  --body-file /tmp/mr.md
```

常用参数：

- `--title <text>`：必填。
- `--body <text>` / `--body-file <path>`：二选一。
- `--head <branch>`：默认当前分支。
- `--base <branch>`：默认 `.arms-exceptions/yunxiao.json` 的 `default_target_branch`。
- `--reviewer <id>`：可重复。
- `--work-item-ids <csv>`：关联工作项。
- `--label <name>`：可重复。
- `--create-missing-label`：缺少类标时自动创建。
- `--json`：输出 JSON。

`create --json` 保留完整 `merge_request`，并在顶层额外输出：

- `localId`
- `status`
- `url`：优先 MR 详情页 `detailUrl`
- `detailUrl`
- `webUrl`

### list

```bash
python3 skills/yunxiao-mr/scripts/cli.py list --state opened --limit 20
```

参数：

- `--state opened|merged|closed|all`
- `--author <id>`
- `--reviewer <id>`
- `--search <text>`
- `--label <name>`
- `--limit <n>`
- `--json`

### view

```bash
python3 skills/yunxiao-mr/scripts/cli.py view 12 --comments
```

### edit

```bash
python3 skills/yunxiao-mr/scripts/cli.py edit 12 --title "新标题" --body-file /tmp/body.md
```

云效官方 `UpdateMergeRequest` 只支持标题和描述；CLI 不支持用 `edit` 修改目标分支。

### label

```bash
python3 skills/yunxiao-mr/scripts/cli.py label list
python3 skills/yunxiao-mr/scripts/cli.py label create HAT-Ready --color "#3BA630"
python3 skills/yunxiao-mr/scripts/cli.py label add 12 HAT-Ready --create-missing-label
python3 skills/yunxiao-mr/scripts/cli.py label remove 12 HAT-Ready
python3 skills/yunxiao-mr/scripts/cli.py label delete HAT-Ready
```

`label add` 默认不创建缺失类标。需要创建时显式加 `--create-missing-label`。

`label create` 创建项目级类标，`--color` 默认是 `#3BA630`，因为云效创建类标接口要求使用云效允许的固定颜色值。

`label delete <name-or-id>` 删除项目级类标。若存在同名类标，CLI 会要求改用类标 ID。

### comment

```bash
python3 skills/yunxiao-mr/scripts/cli.py comment 12 --body-file /tmp/comment.md
```

### close / reopen

```bash
python3 skills/yunxiao-mr/scripts/cli.py close 12
python3 skills/yunxiao-mr/scripts/cli.py reopen 12
```

### merge

```bash
python3 skills/yunxiao-mr/scripts/cli.py merge 12 --method squash --delete-branch
```

`--delete-branch` 会在合并成功后删除源分支。后续清理脚本若再次删除同名远端分支，看到 `remote ref does not exist` 应视为已清理。

合并方法：

- `no-fast-forward`
- `squash`
- `rebase`
- `ff-only`

## Actual Acceptance

需要真实云效 token 和测试仓库权限：

```bash
skills/yunxiao-mr/scripts/acceptance.sh
```

默认只 clone 真实测试仓库并运行 `doctor`。需要创建不合并的 smoke MR 时：

```bash
skills/yunxiao-mr/scripts/acceptance.sh --create-smoke-mr
```

等价手工步骤：

```bash
tmpdir="$(mktemp -d)"
git clone git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git "$tmpdir/test"
cd "$tmpdir/test"
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/yunxiao-mr/scripts/cli.py doctor
```

创建不合并的 smoke MR：

```bash
stamp="$(date +%Y%m%d%H%M%S)"
branch="codex-yunxiao-mr-smoke-$stamp"
label="codex-smoke-$stamp"
git checkout -b "$branch"
printf "codex smoke %s\n" "$branch" > codex-yunxiao-mr-smoke.txt
git add codex-yunxiao-mr-smoke.txt
git commit -m "Codex Yunxiao MR smoke"
git push -u origin "$branch"
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/yunxiao-mr/scripts/cli.py create \
  --title "Codex Yunxiao MR smoke $branch" \
  --body "Automated acceptance test for yunxiao-mr skill." \
  --label "$label" \
  --create-missing-label
```

默认验收不要合并。只有明确获得允许时才对测试仓库执行：

```bash
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/yunxiao-mr/scripts/cli.py merge <localId> --method squash --delete-branch
```
