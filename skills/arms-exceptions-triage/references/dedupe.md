# Triage Dedupe Reference

父 Agent 需要做两次聚合，但聚合只能基于 `groups` 元数据和 Sub Agent 报告，不能亲自探索业务代码或异常详情。

## 初筛聚合

`dedupe.json` 在 Sub Agent 深度诊断前生成。记录：

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
- occurrence pattern。

初筛聚合只负责减少需要深度诊断的候选项；不要因为初筛没有合并，就认为后续一定是不同 bug。父 Agent 不得为了初筛去打开业务代码或调用 `show/logs` 做详情分析。

## 诊断后复聚合

所有 Sub Agent 诊断报告返回后，父 Agent 必须基于报告内容重新检查是否存在重复 bug，并写入：

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
- `source-manifest.md` 必须记录读取的诊断报告、合并决策和未合并原因；
- 如果复聚合需要额外代码或异常详情证据，父 Agent 必须派发补充诊断 Sub Agent，不得自行探索。

噪音示例：

- 客户端明显传错参数，服务按契约返回错误；
- 第三方服务或上游依赖异常，当前仓库没有可修代码路径；
- target branch 已经修复但尚未发布；
- 同一运行中被更强代表组覆盖的重复异常。
