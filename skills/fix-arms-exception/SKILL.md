---
name: fix-arms-exception
description: 修复已经被 ARMS 分诊确认的可修复异常，从诊断报告创建独立 fix worktree，用 TDD 修复，经 review Sub Agent 审查后通过 Yunxiao MR 提交。Use when 用户要求修复某个已诊断 ARMS 异常，或 arms-exceptions-triage 产出 status=bug 的诊断报告并进入修复阶段。
---

# 修复 ARMS 异常

## Overview

这个 skill 只处理已经确认可修复的 ARMS bug。入口必须是 `arms-exceptions-triage` 生成的诊断报告，不能从裸 `group_id`、截图、日志片段或口头摘要直接开始修。

示例：

```bash
/fix-arms-exception .arms-exceptions/triage/<run-id>/subagents/diagnose-<stable-slug>.md
```

## Input Contract

诊断报告必须包含：

- `status: bug`；
- 异常指纹：exception type、normalized message、top business frame、service、operation；
- ARMS/log/code 证据；
- 根因分析；
- 建议修复范围和建议测试；
- Source Manifest。

如果缺少这些信息，先要求补齐诊断报告，不要重新从零分诊。

## Workflow

1. 读取诊断报告和 Source Manifest，确认 target branch、异常指纹、根因和测试建议。
2. 从目标分支创建独立 worktree 和分支，worktree 放在 `.arms-exceptions/worktrees/fix-{short-title}/`：

   ```text
   fix/arms-YYYYMMDD-{short-title}
   ```

3. 确认不会修改用户当前工作区。只允许自动 push 自己创建的 `fix/arms-` 分支。
4. 先复现或写失败回归测试，再实现修复。
5. 运行 focused test；涉及共享逻辑时运行更广的相关测试。
6. 派发独立 review Sub Agent 审查修复 diff、测试证据和 MR 正文草稿；P0/P1 必须回到第 4 步修正。
7. 提交修复 commit。
8. push 当前 `fix/arms-...` 分支：

   ```bash
   git push -u origin fix/arms-YYYYMMDD-{short-title}
   ```

9. 用 `yunxiao-mr` 创建 MR：

   ```bash
   python3 skills/yunxiao-mr/scripts/cli.py doctor
   python3 skills/yunxiao-mr/scripts/cli.py create \
     --title "fix: 修复 <exception/root-cause>" \
     --body-file /tmp/arms-exception-mr.md \
     --json
   ```

10. 输出最终总结，包含 MR `localId` 和详情页 URL。

MR 正文模板、失败处理和总结模板见 `references/workflow.md`。

## Rules

- 不自动合并 MR。
- 不自动 push 非 `fix/arms-` 分支。
- 分支名已存在时，先检查现有分支/worktree，再决定继续或创建后缀分支。
- 测试失败或无法复现时，不创建 MR；把失败证据写入修复总结。
- 如果修复需要外部权限、数据迁移、发布动作、跨仓库变更或产品判断，改为 `needs_human` 并回写 triage 总结。
- 不打印、保存或发送凭证、Authorization header、AccessKey、Token、SecurityToken、签名 URL 或 OAuth code。

## Output

最终总结包含：

- 修复分支和 worktree；
- 变更摘要；
- 验证命令和结果；
- MR 链接；
- 剩余风险；
- 供父 Agent 清理的 worktree 路径；
- Source Manifest 更新建议。

## References

```text
skills/fix-arms-exception/
  SKILL.md
  references/
    workflow.md
```
