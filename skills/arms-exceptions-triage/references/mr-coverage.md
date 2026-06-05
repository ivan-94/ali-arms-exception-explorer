# MR Coverage Reference

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
