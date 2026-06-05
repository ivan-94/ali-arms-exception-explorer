# setup-arms-workflow Checklist

## Triage/Fix 配置闭环

`arms-exceptions-triage` 和 `fix-arms-exception` 没有独立 CLI 配置，但 setup 必须验证它们需要的宿主配置已经完成：

- `targets --json` 中每个要分诊的 target 都有 `branch`；
- 宿主 `.gitignore` 和 `.arms-exceptions/.gitignore` 已忽略 `.arms-exceptions/worktrees/`；
- Yunxiao doctor 已通过，因为 fix 需要创建 MR；
- Lark config 已通过，因为 triage 结束必须通知；
- `skills/arms-exceptions-triage/SKILL.md` 和 `skills/fix-arms-exception/SKILL.md` 在宿主项目存在。

缺任一项时继续引导用户补齐；无法补齐时 blocked。

## Final Checklist

- `.arms-exceptions/config.json` 存在并只包含非凭证配置。
- `targets --json` 能列出确认过的 target、branch 和 services。
- Yunxiao `doctor --json` 已通过，或明确 blocked。
- Lark `config --show --json` 已通过，或明确 blocked。
- `.arms-exceptions/setup/setup-report.md` 和 `source-manifest.md` 已写入。
- `.gitignore` 和 `.arms-exceptions/.gitignore` 忽略 setup、triage、worktrees、本地 webhook 和本地数据。
- `yunxiao-mr doctor --json --skip-api` 已记录。
- Lark `config --show --json` 已记录，且没有打印完整 Webhook。
