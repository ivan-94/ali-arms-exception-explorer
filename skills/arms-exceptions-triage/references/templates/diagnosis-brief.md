# ARMS 诊断任务

父 Agent 派发诊断 Sub Agent 时，brief 必须可单独执行，不依赖聊天上下文。

```markdown
# ARMS 诊断任务

## 输入
- HOST_ROOT:
- TRIAGE_WORKTREE_ROOT:
- run_id:
- target:
- services:
- branch:
- group_id:
- related_group_ids:
- output_path: .arms-exceptions/triage/<run-id>/subagents/diagnose-<stable-slug>.md

## 必须执行
- 在 TRIAGE_WORKTREE_ROOT 运行 `python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --json`
- 需要日志时运行 `python3 skills/arms-exceptions-explorer/scripts/cli.py logs <group_id> --json`
- 探索业务代码，定位是否为当前仓库可修问题
- 按诊断报告模板写入 output_path

## 禁止
- 不修改业务代码或测试
- 不创建 MR
- 不打印或写入凭证、Authorization header、AccessKey、Token、SecurityToken、签名 URL 或 OAuth code
```

诊断 Sub Agent 未能写入 `output_path`、状态不在 `noise / needs_human / bug` 里，或 `status=bug` 但缺少代码路径、根因、建议测试时，父 Agent 必须把该项标为 blocked/needs_human，或派发补充诊断 Sub Agent。
