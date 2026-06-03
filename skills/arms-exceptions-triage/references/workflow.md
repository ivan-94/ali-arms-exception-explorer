# arms-exceptions-triage Workflow Reference

## 诊断报告模板

Sub Agent 诊断报告必须写入：

```text
.arms-exceptions/triage/<run-id>/subagents/diagnose-<stable-slug>.md
```

模板：

```markdown
# ARMS 异常诊断

## 结论
status: noise | needs_human | bug
confidence: high | medium | low

## 异常指纹
- exception_type:
- normalized_message:
- top_business_frame:
- service:
- operation:

## 证据
- ARMS:
- logs:
- code:

## 根因分析

## 修复建议
- 是否可由 Agent 修复:
- 建议修复范围:
- 建议测试:

## Source Manifest

### Sources

### Produced artifacts

### Key decisions

### Verification evidence

### Open questions / risks
```

`status=bug` 必须有稳定代码路径证据和明确修复方向；否则使用 `noise` 或 `needs_human`。

## Worktree 规则

所有本流程创建的 worktree 统一放在：

```text
.arms-exceptions/worktrees/
```

建议命名：

```text
.arms-exceptions/worktrees/triage-<run-id>/
.arms-exceptions/worktrees/fix-<stable-slug>/
```

记录到 `source-manifest.md`：

- triage worktree 路径；
- 每个 fix 子 Agent worktree 路径；
- 对应分支；
- 创建命令；
- 清理命令和结果。

## 二次聚合建议

父 Agent 需要做两次聚合：

1. `dedupe.json`：在 Sub Agent 深度诊断前，基于 ARMS group、stack、message 和日志信号做初筛。
2. `post-diagnosis-dedupe.json`：在所有探索/诊断 Sub Agent 完成后，基于诊断报告中的根因、代码路径、修复建议和证据做复聚合。

只有 `post-diagnosis-dedupe.json` 中的代表项可以进入 MR 覆盖判断和修复派发。

### 初筛聚合

父 Agent 在 `dedupe.json` 中记录：

- 本次运行内的原始 `group_id` 列表；
- 稳定异常指纹；
- 合并原因；
- 初筛分类；
- 用于 `show` 的代表性 group id。

比较维度：

- exception type；
- normalized core message；
- top business stack frame；
- service / operation；
- 附近 stack frame；
- occurrence pattern；
- 关联日志中的稳定根因信号。

初筛聚合只负责减少需要深度诊断的候选项；不要因为初筛没有合并，就认为后续一定是不同 bug。

### 诊断后复聚合

所有 Sub Agent 诊断报告返回后，父 Agent 必须重新检查是否存在重复 bug，并写入：

```text
.arms-exceptions/triage/<run-id>/post-diagnosis-dedupe.json
```

复聚合记录建议包含：

- 代表项 ID；
- 合并进代表项的 `group_id` / `dedupe` 项；
- 对应诊断报告路径；
- 诊断结论 `status` 和 `confidence`；
- 共同根因；
- 共同代码路径；
- 共同修复范围；
- 合并原因；
- 是否进入 MR 覆盖判断；
- 是否进入 `fix-arms-exception`。

复聚合比较维度：

- Sub Agent 给出的 root cause 是否相同或共享同一上游原因；
- 稳定代码路径、函数、模块或配置项是否相同；
- 建议修复范围是否会同时覆盖多个异常；
- 异常类型、normalized message 和 top business frame 是否只是同一问题的不同表现；
- service / operation 差异是否来自同一调用链、同一 worker 入口或同一共享库；
- 日志、trace、请求参数或外部依赖证据是否指向同一失败条件；
- 一个修复是否会自然消除多个诊断项。

必须合并的典型情况：

- 多个 `group_id` 指向同一个业务函数里的同一空值、类型、边界或配置问题；
- Web 和 worker 暴露不同异常形态，但根因是同一个共享库缺陷；
- 不同 message 包含不同参数值，归一化后代码路径和失败条件相同；
- 一个异常是另一个异常的后续效应，修复上游根因即可覆盖下游报错；
- 多个 Sub Agent 分别提出相同修复文件和相同测试方向。

不能合并的典型情况：

- message 相似但代码路径、根因或修复范围不同；
- 同一文件里存在两个独立 bug，需要不同测试和不同修复；
- 一个是当前仓库可修 bug，另一个是上游、数据或发布状态问题；
- 只有 `group_id`、service 名称或模糊标题相似，缺少共同根因证据。

复聚合后：

- 被合并项不再独立进入 MR 覆盖判断；
- 被合并项不再独立派发 `fix-arms-exception`；
- 代表项的 MR 覆盖判断必须把所有被合并项的异常指纹和诊断报告作为辅助证据；
- `summary.md` 必须展示复聚合前后数量、代表项和被合并重复项；
- `source-manifest.md` 必须记录读取的诊断报告、合并决策和未合并原因。

噪音示例：

- 客户端明显传错参数，服务按契约返回错误；
- 第三方服务或上游依赖异常，当前仓库没有可修代码路径；
- target branch 已经修复但尚未发布；
- 同一运行中被更强代表组覆盖的重复异常。

## MR 覆盖判断

不要用 `group_id` 判定已有 MR 覆盖。`group_id` 只适合本次运行内定位。

强证据包括：

- 异常类型 + 归一化核心 message；
- 顶部业务栈帧，允许行号轻微漂移；
- service / operation；
- MR 标题、正文或评论明确描述同一根因或代码路径；
- MR source/target branch 与 target.branch 相关。

状态：

- `covered`：opened 或 recently merged MR 命中同一错误指纹和代码路径/根因，跳过修复。
- `maybe_related`：只命中 message、service、文件名或相近标题，不跳过修复。
- `not_related`：无稳定证据。

closed MR 默认不算解决，除非评论明确指向替代 MR 或已发布修复。

## Summary 建议

`summary.md` 面向人类和飞书通知，建议包含：

- target/service、窗口、branch、worktree；
- 同步结果和异常数量；
- 二次聚合前后数量；
- `noise / needs_human / bug / covered / maybe_related / fix_started / fix_mr_created` 统计；
- 每个保留异常的短标题、状态、置信度、核心 message、top frame、根因摘要；
- 相关 MR 链接；
- 修复 MR 链接；
- 本地证据路径；
- 剩余风险和下一步。

## Cleanup

父 Agent 汇总 fix 子 Agent 结果后，必须清理本次创建的 fix worktree：

```bash
git worktree remove .arms-exceptions/worktrees/fix-<stable-slug>
```

如果 worktree 有未提交改动、命令失败或路径不在 `.arms-exceptions/worktrees/` 下：

- 不要强制删除；
- 在 `summary.md` 和 `source-manifest.md` 记录路径、失败原因和建议下一步；
- 仍然发送飞书通知。

禁止清理：

- 用户当前工作区；
- 不在 `.arms-exceptions/worktrees/` 下的路径；
- 无法确认属于本次 triage run 的 worktree。
