# arms-exceptions-triage Workflow Reference

## 父/子 Agent 职责边界

父 Agent 的职责是编排，不是诊断或修复：

- 读取 target/service 配置；
- 运行 `doctor`、`targets`、`sync`、`groups` 这类范围级命令；
- 创建和清理 `.arms-exceptions/worktrees/`；
- 写入 `groups.json`、`dedupe.json`、`post-diagnosis-dedupe.json`、`summary.md`、`lark-card.json` 和 `source-manifest.md`；
- 基于 `groups` 元数据做初筛聚合；
- 派发、限流和回收 Sub Agent；
- 读取 Sub Agent 报告，做复聚合、MR 覆盖判断和通知。

父 Agent 可以消费的代码级和异常详情级信息，只能来自 Sub Agent 报告中的结构化字段和证据摘要。报告缺少代码路径、根因、修复范围、测试建议或日志证据时，父 Agent 必须派发补充诊断，不能自行打开业务代码或调用 `show/logs` 补证据。

父 Agent 禁止：

- 打开、搜索、阅读或修改业务代码文件；
- 亲自调用 `show/logs` 做异常详情探索或 stacktrace 分析；
- 亲自判断代码根因、修复方案或测试范围；
- 亲自编辑业务代码、测试、配置或迁移；
- 用父 Agent 的猜测替代 Sub Agent 的诊断报告。

Sub Agent 负责实际业务工作：

- 诊断 Sub Agent 调用 `arms-exceptions-explorer show/logs` 获取异常详情和日志；
- 诊断 Sub Agent 探索业务代码、定位根因、区分 `noise / needs_human / bug`；
- 修复 Sub Agent 调用 `fix-arms-exception`，编辑业务代码/测试、运行验证、创建 MR；
- Sub Agent 必须把证据、代码路径、命令和风险写回自己的报告。

如果父 Agent 需要任何代码级或异常详情级判断，必须派发新的 Sub Agent 或要求现有 Sub Agent 补充，不得自行完成。

## 路径和运行根目录

本 workflow 使用两个固定根目录概念：

- `HOST_ROOT`：触发 triage 的宿主项目根目录，也是最终本地产物的归属位置。
- `TRIAGE_WORKTREE_ROOT`：父 Agent 为本次 triage run 创建的独立 worktree，通常位于 `HOST_ROOT/.arms-exceptions/worktrees/triage-<run-id>/`。

规则：

- 所有 `.arms-exceptions/triage/<run-id>/...` 产物都写回 `HOST_ROOT`，不要写到 triage worktree 的相对路径里。
- `doctor` 和 `targets --json` 可以先在 `HOST_ROOT` 运行，用于确认配置和 target branch。
- `sync`、`groups`、`yunxiao-mr` 以及后续需要 target branch 上代码/配置一致性的命令，优先在 `TRIAGE_WORKTREE_ROOT` 运行。
- Sub Agent brief 必须同时给出 `HOST_ROOT`、`TRIAGE_WORKTREE_ROOT` 和输出文件的绝对或从 `HOST_ROOT` 计算的路径。
- `source-manifest.md` 必须记录每个命令在哪个 cwd 执行。

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
- trace_console_url:
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

`trace_console_url` 来自 `arms-exceptions-explorer groups/show --json` 的 `trace_console_url` 字段。该字段使用阿里云官方 `trace.console.aliyun.com` 调用链分析过滤链接格式，只有在配置能定位 service region 且 group 有 sample trace 时才会生成。Sub Agent 不得自行猜测 ARMS 控制台详情 URL；字段缺失时写明原因，并提供 `sample_trace_id` 与本地查看命令。

## Sub Agent 派发合同

父 Agent 派发 Sub Agent 时，brief 必须是可单独执行的，不依赖聊天上下文。

### 诊断 Sub Agent brief

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

诊断 Sub Agent 未能写入 `output_path`、状态不在 `noise / needs_human / bug` 里，或 `status=bug` 但缺少代码路径/根因/建议测试时，父 Agent 必须把该项标为 blocked/needs_human，或派发补充诊断 Sub Agent。

### 修复 Sub Agent brief

```markdown
# ARMS 修复任务

## 输入
- HOST_ROOT:
- diagnostic_report: .arms-exceptions/triage/<run-id>/subagents/diagnose-<stable-slug>.md
- result_path: .arms-exceptions/triage/<run-id>/subagents/fix-<stable-slug>.md
- target:
- branch:
- representative_group_id:
- covered_duplicate_group_ids:

## 必须执行
- 使用 `fix-arms-exception`，从 diagnostic_report 开始
- 在独立 `.arms-exceptions/worktrees/fix-<stable-slug>/` worktree 中修复
- TDD：先复现或写失败回归测试，再修复
- 创建 Yunxiao MR 后，把最终修复结果写入 result_path

## 禁止
- 不自动合并 MR
- 不 push 非 `fix/arms-` 分支
- 不删除自己的 worktree；父 Agent 汇总后清理
```

修复 Sub Agent 未写入 `result_path` 时，父 Agent 不得假设修复成功；必须把该项记为 blocked，并在 summary/source-manifest 中记录缺失结果路径。

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

worktree 路径必须从 `HOST_ROOT` 计算。禁止用当前 shell 的相对路径清理 worktree，除非已经确认当前 cwd 是 `HOST_ROOT`。

## 二次聚合建议

父 Agent 需要做两次聚合，但聚合只能基于 `groups` 元数据和 Sub Agent 报告，不能亲自探索业务代码或异常详情：

1. `dedupe.json`：在 Sub Agent 深度诊断前，基于 `groups --json` 中已有的 ARMS group、message、top frame 等元数据做初筛。
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
- occurrence pattern。

初筛聚合只负责减少需要深度诊断的候选项；不要因为初筛没有合并，就认为后续一定是不同 bug。父 Agent 不得为了初筛去打开业务代码或调用 `show/logs` 做详情分析。

### 诊断后复聚合

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
- `source-manifest.md` 必须记录读取的诊断报告、合并决策和未合并原因。
- 如果复聚合需要额外代码或异常详情证据，父 Agent 必须派发补充诊断 Sub Agent，不得自行探索。

噪音示例：

- 客户端明显传错参数，服务按契约返回错误；
- 第三方服务或上游依赖异常，当前仓库没有可修代码路径；
- target branch 已经修复但尚未发布；
- 同一运行中被更强代表组覆盖的重复异常。

## MR 覆盖判断

不要用 `group_id` 判定已有 MR 覆盖。`group_id` 只适合本次运行内定位。

父 Agent 做覆盖判断时可以读取：

- `post-diagnosis-dedupe.json`；
- 诊断 Sub Agent 报告；
- `yunxiao-mr list/view --json` 输出；
- MR 标题、正文、评论中与诊断报告字段匹配的摘要。

父 Agent 不得为了覆盖判断打开业务代码或直接分析 stacktrace；如果 MR 是否覆盖依赖代码 diff 或根因判断，派发补充诊断或将该 MR 记为 `maybe_related`。

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

## 修复结果报告模板

修复 Sub Agent 结果必须写入：

```text
.arms-exceptions/triage/<run-id>/subagents/fix-<stable-slug>.md
```

模板：

```markdown
# ARMS 异常修复结果

## 状态
- status: fixed | blocked | needs_human

## 输入
- diagnostic_report:
- representative_group_id:
- covered_duplicate_group_ids:

## 分支和 MR
- worktree:
- branch:
- commit:
- mr_local_id:
- mr_url:

## 变更摘要

## 验证
- command:
- result:

## Review
- reviewer:
- result:
- unresolved_findings:

## 风险

## Source Manifest

### Sources

### Produced artifacts

### Key decisions

### Verification evidence

### Open questions / risks
```

## Summary 建议

`summary.md` 面向人类阅读，必须使用中文字段和值。飞书通知不直接发送 Markdown 报告，而是由 triage 生成业务专用 `lark-card.json` raw payload，再交给 `lark-notify --format raw` 发送。

建议包含：

- target/service、窗口、branch、worktree；
- 同步结果和异常数量；
- 二次聚合前后数量；
- 中文状态统计，例如 `噪音`、`需要人工介入`、`明确 Bug`、`已有 MR 覆盖`、`修复中`、`已创建修复 MR`；
- 每个保留异常的短标题、状态、置信度、核心 message、top frame、根因摘要；
- 每个保留/代表异常的 `group`、`sample_trace_id`，以及 explorer 已生成的 `trace_console_url`（如有）；
- 相关 MR 链接；
- 修复 MR 链接；
- 本地证据路径；
- 剩余风险和下一步。

`summary.md` 字段示例：

```markdown
## 修复项

### OSS HEAD 404 导致 ARMS 异常 Span

- group: dbfd817213210b31
- sample_trace_id: 0a1b2c3d
- trace_console_url: https://trace.console.aliyun.com/#/cn-beijing/tracing-explorer?source=XTRACE&filters=...
- 状态: 已创建修复 MR
- 根因: OSS HEAD 404 被 SDK 上报为 error span
- 修复 MR: [MR #212](https://...)
```

## 飞书卡片 payload

父 Agent 负责生成：

```text
.arms-exceptions/triage/<run-id>/lark-card.json
```

这是 ARMS triage 领域专用 payload，不由 `lark-notify` 解析或改写业务字段。发送命令：

```bash
python3 skills/lark-notify/scripts/cli.py send \
  --json-file .arms-exceptions/triage/<run-id>/lark-card.json \
  --format raw
```

卡片要求：

- 使用中文标题、中文字段和值；
- 不使用 GitHub Markdown 表格作为主要内容；
- `trace_console_url` 存在时，每个代表 group 提供「查看调用链」链接；缺失时展示 `sample_trace_id` 和 `show <group_id> --json` 本地查看命令；
- MR 链接使用飞书卡片里的 URL 跳转能力；
- 卡片只包含摘要、统计、代表异常、MR 和下一步；长详情留在本地 `summary.md`；
- payload 不包含凭证、Authorization header、AccessKey、Token、SecurityToken、签名 URL 或 OAuth code。

示例结构：

```json
{
  "msg_type": "interactive",
  "card": {
    "config": {"wide_screen_mode": true},
    "header": {
      "template": "blue",
      "title": {"tag": "plain_text", "content": "ARMS 异常分诊：ai-service-dev"}
    },
    "elements": [
      {"tag": "div", "text": {"tag": "lark_md", "content": "**结论**\\n状态：已创建修复 MR\\n目标：ai-service-dev\\n分支：dev"}},
      {"tag": "hr"},
      {"tag": "div", "text": {"tag": "lark_md", "content": "**修复项**\\nOSS HEAD 404 导致 ARMS 异常 Span\\n异常组：dbfd817213210b31\\nTrace：0a1b2c3d\\n[查看调用链](https://trace.console.aliyun.com/#/cn-beijing/tracing-explorer?source=XTRACE&filters=...)"}}
    ]
  }
}
```

## Cleanup

父 Agent 汇总 fix 子 Agent 结果后，必须清理本次创建的 fix worktree：

```bash
git -C "$HOST_ROOT" worktree remove "$HOST_ROOT/.arms-exceptions/worktrees/fix-<stable-slug>"
```

如果 worktree 有未提交改动、命令失败或路径不在 `HOST_ROOT/.arms-exceptions/worktrees/` 下：

- 不要强制删除；
- 在 `summary.md` 和 `source-manifest.md` 记录路径、失败原因和建议下一步；
- 仍然发送飞书通知。

禁止清理：

- 用户当前工作区；
- 不在 `HOST_ROOT/.arms-exceptions/worktrees/` 下的路径；
- 无法确认属于本次 triage run 的 worktree。
