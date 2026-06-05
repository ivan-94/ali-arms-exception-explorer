# setup-arms-workflow Ignore Rules

宿主项目根 `.gitignore` 至少忽略：

```text
.arms-exceptions/data/
.arms-exceptions/setup/
.arms-exceptions/triage/
.arms-exceptions/worktrees/
.arms-exceptions/lark-notify.local.json
```

`.arms-exceptions/.gitignore` 由 `arms-exceptions-explorer init` 维护，必须包含：

```text
data/
setup/
triage/
worktrees/
lark-notify.local.json
```
