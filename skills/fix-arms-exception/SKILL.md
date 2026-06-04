---
name: fix-arms-exception
description: 使用 DSL 契约修复已由 ARMS 分诊确认的 status=bug 异常；用于用户要求从 arms-exceptions-triage 诊断报告进入修复阶段，或父 Agent 派发 fix-arms-exception 并提供 result_path 时。
---

```python
from skill_contract import *

skill(
    name="fix-arms-exception",
    purpose="从 status=bug 的 ARMS 诊断报告出发，在隔离 worktree 中用 TDD 修复异常，经独立 review 后 push fix/arms- 分支并创建 Yunxiao MR。",
    summary="只处理 arms-exceptions-triage 已确认的可修复 bug；不能从裸 group_id、截图、日志片段或口头摘要直接开始。",
    version="0.1.0",
)

activate_when(
    [
        "用户要求修复某个已由 arms-exceptions-triage 诊断为 status=bug 的 ARMS 异常",
        "arms-exceptions-triage 父 Agent 派发 fix-arms-exception，并提供诊断报告和 result_path",
        "输入是 .arms-exceptions/triage/<run-id>/subagents/diagnose-<stable-slug>.md 这类诊断报告",
    ],
    match="any",
    strength="strong",
)

do_not_activate_when([
    "用户只提供裸 group_id、截图、日志片段、raw span 或口头摘要，且没有 status=bug 诊断报告",
    "用户要求分诊、去重、MR 覆盖判断、通知汇总或 setup，而不是执行修复",
    "诊断报告不是 status=bug，或需要产品判断、发布动作、数据迁移、外部权限、跨仓库变更才能继续",
    "用户只要求审查已有修复 diff，且没有要求执行 ARMS 异常修复 workflow",
])

inputs(
    required=[
        input(
            "diagnostic_report",
            type=File | Text,
            description="arms-exceptions-triage 生成的 status=bug 诊断报告路径或正文；必须包含异常指纹、证据、根因、建议修复范围、建议测试和 Source Manifest。",
        ),
    ],
    optional=[
        input(
            "result_path",
            type=File,
            description="父 Agent 派发时要求写入的修复结果路径，例如 .arms-exceptions/triage/<run-id>/subagents/fix-<stable-slug>.md。",
        ),
        input(
            "host_root",
            type=Directory,
            description="宿主项目根目录；缺省时从诊断报告 Source Manifest 或当前仓库上下文推断，不能跨项目猜测。",
        ),
    ],
    ask_when_missing=True,
)

outputs(
    required=[
        output(
            "repair_result",
            type=Text,
            description="最终修复结果摘要。",
            success_criteria=[
                "包含 status: fixed | blocked | needs_human",
                "包含 worktree、branch、commit、MR、变更摘要、验证命令和结果、风险、Source Manifest 更新建议",
                "当 result_path 存在时，同样内容已写入该路径，即使 blocked 或 needs_human",
            ],
        ),
    ],
    optional=[
        output(
            "result_artifact",
            type=File,
            description="父 Agent 提供的 result_path 对应文件。",
        ),
        output(
            "yunxiao_mr",
            type=Text,
            description="创建成功的 Yunxiao MR localId 和详情页 URL；blocked 或 needs_human 时可以为空。",
        ),
    ],
)

resources(
    references=[
        reference(
            "references/workflow.md",
            purpose="MR 正文模板、修复前检查、分支和 push 规则、review Sub Agent brief、失败处理和最终总结模板。",
            when="开始修复前、准备 MR 正文、处理失败或写最终总结时读取。",
            read_strategy="always",
        ),
    ],
)

environment(
    variables=[
        env(
            "YUNXIAO_ACCESS_TOKEN",
            required=False,
            secret=True,
            purpose="yunxiao-mr CLI 从环境变量读取的访问令牌；不得写入配置、日志或报告。",
        ),
    ],
    commands=["git", "python3"],
    network="required",
    filesystem="workspace",
)

workflow(
    [
        step(
            "load_diagnostic_report",
            "读取 diagnostic_report 和 Source Manifest，确认 status=bug、异常指纹、ARMS/log/code 证据、根因、建议修复范围、建议测试、target branch 和来源清单齐全；缺失时要求补齐诊断报告，不从零分诊。",
            reads=["diagnostic_report"],
            writes=["report_contract", "source_manifest"],
        ),
        step(
            "resolve_execution_context",
            "解析 HOST_ROOT、target branch、stable slug、result_path 和允许修改的仓库边界；由 triage 调度时，所有持久结果必须落在 HOST_ROOT/.arms-exceptions/triage/<run-id>/subagents/。",
            reads=["report_contract", "source_manifest"],
            writes=["fix_context"],
        ),
        step(
            "create_isolated_worktree",
            f"""
            从 target branch 创建独立 worktree 和 fix/arms-YYYYMMDD-{{short-title}} 分支，路径固定为 .arms-exceptions/worktrees/fix-{{stable-slug}}/。
            使用 {call_tool(
                "git",
                how="在 HOST_ROOT 下检查目标分支、同名 worktree/branch 和 remote，然后创建或选择安全后缀的 fix/arms- 分支；不要修改用户当前工作区",
                expect="fix_worktree 与 fix_branch 均指向本次修复专用范围",
                on_failure="停止修复并把失败原因写入 repair_result；不要继续实现或创建 MR",
            )}。
            """,
            reads=["fix_context"],
            writes=["fix_worktree", "fix_branch"],
        ),
        step(
            "write_failing_regression",
            "先复现异常或写失败回归测试；如果无法复现但诊断证据足以证明根因，写覆盖根因的回归测试；如果证据不足，转为 needs_human。",
            reads=["report_contract", "fix_worktree"],
            writes=["regression_test"],
        ),
        step(
            "implement_fix",
            "只在 fix_worktree 中实现最小修复，范围对齐诊断报告的根因和建议修复边界；不要把相邻语义、重构或产品判断并入本次修复。 使用 TDD 形式修改",
            reads=["report_contract", "fix_worktree", "regression_test"],
            writes=["fix_diff"],
        ),
        step(
            "run_verification",
            "运行 focused test；涉及共享逻辑时运行更广的相关测试。测试失败时停止，不创建 MR，并把失败命令、摘要和日志路径写入 repair_result。",
            reads=["fix_diff", "regression_test"],
            writes=["verification_evidence"],
        ),
        step(
            "draft_mr_body",
            "按 references/workflow.md 的 MR 正文模板起草 MR 描述，保留问题、归因、方案、验证、风险回滚、ARMS 证据和 Source Manifest；不要粘贴大段 raw span 或 raw logs。",
            reads=["report_contract", "source_manifest", "verification_evidence", "fix_diff"],
            writes=["mr_body_draft"],
        ),
        step(
            "run_review_subagent",
            f"""
            测试通过后、提交和 push 前，派发独立只读 review Sub Agent 审查修复 diff、测试证据和 MR 正文草稿。
            使用 {call_tool(
                "review Sub Agent",
                how="提供诊断报告路径、目标分支、修复分支、diff 摘要、测试命令和结果、MR 正文草稿路径，并要求按 P0/P1/P2 输出发现；review agent 只读 fix_worktree，不修改文件",
                expect="按 P0/P1/P2 分级的审查结果",
                on_failure="记录 review 缺口并停止，除非调用方明确接受跳过独立审查",
            )}。
            P0/P1 或验收标准未满足时，回到 implement_fix 重新修正、测试和 review；P2 由当前 Agent 判断是否立即修复，不修时写入 MR 风险或后续项。
            """,
            reads=["fix_diff", "verification_evidence", "mr_body_draft"],
            writes=["review_result"],
        ),
        step(
            "commit_and_push_fix_branch",
            f"""
            在 review 无 P0/P1 后提交修复 commit，并只允许 push 自己创建的 fix/arms- 分支。
            使用 {call_tool(
                "git",
                how="在 fix_worktree 中提交修复 commit，然后执行 git push -u origin fix/arms-YYYYMMDD-{short-title}；push 前记录 remote、branch、worktree、commit 和已执行测试",
                expect="远端存在当前 fix/arms- 分支，且没有 push 目标分支、用户当前分支或非 fix/arms- 分支",
                on_failure="不创建 MR；把 push 命令和失败原因写入 repair_result",
            )}。
            """,
            reads=["review_result", "verification_evidence"],
            writes=["fix_commit", "pushed_branch"],
        ),
        step(
            "create_yunxiao_mr",
            f"""
            用 yunxiao-mr 创建合并请求，不自动合并。
            使用 {call_skill(
                "yunxiao-mr",
                how="先运行 doctor 确认 Codeup/Yunxiao 上下文，再用 create --title ... --body-file <mr_body_draft> --json 创建 MR；解析 localId、detailUrl/webUrl 和完整 merge_request",
                mode="compose",
                expect="Yunxiao MR localId 和详情页 URL",
                on_failure="保留本地 commit 和 pushed branch 信息，按 yunxiao-mr CLI 输出记录下一步，不猜 token 或仓库 ID",
            )}。
            """,
            reads=["pushed_branch", "mr_body_draft"],
            writes=["yunxiao_mr"],
        ),
        step(
            "write_repair_result",
            "输出最终 repair_result；当 result_path 存在时必须写入该文件，即使状态是 blocked 或 needs_human。不要自行删除 fix_worktree，父 Agent 读取结果后再按 HOST_ROOT 清理。",
            reads=["fix_context", "fix_branch", "fix_commit", "yunxiao_mr", "verification_evidence", "source_manifest"],
            produces=["repair_result", "result_artifact", "yunxiao_mr"],
        ),
    ],
    name="fix_bug_from_triage_report",
)

decision_rules([
    when("diagnostic_report 缺少 status=bug、异常指纹、根因、建议测试或 Source Manifest", then="停止修复并要求补齐诊断报告；不要重新从零分诊"),
    when("诊断报告状态不是 bug", then="不执行修复，返回 needs_human 或交回 triage"),
    when("target branch 缺失", then="停止并写 blocked；不要猜默认分支"),
    when("同名 fix branch 或 worktree 已存在", then="先检查现有分支/worktree 是否属于同一诊断报告，再继续或创建安全后缀分支"),
    when("修复需要外部权限、数据迁移、发布动作、跨仓库变更或产品判断", then="改为 needs_human 并写入 triage result_path"),
    when("测试失败或无法生成可信回归测试", then="不创建 MR；把失败证据写入 repair_result"),
    when("review Sub Agent 返回 P0/P1", then="回到实现步骤修正并重新测试和 review"),
    when("Yunxiao MR 创建失败", then="保留本地 commit 和 pushed branch 信息，并按 yunxiao-mr 输出记录下一步"),
    prefer("当前诊断报告和 Source Manifest", over="聊天摘要或旧设计文档", reason="父 Agent 和下游 Agent 需要能重读原始来源"),
    prefer("focused regression test first", over="直接实现修复", reason="这个 skill 的修复证据必须能证明异常不会回归"),
])

failure_modes([
    when("required input missing", then="只询问缺失的 diagnostic_report；result_path 仅在父 Agent 派发时必填"),
    when("Source Manifest missing", then="停止并要求补齐诊断报告，不从聊天上下文补造来源清单"),
    when("worktree creation fails", then="记录目标分支、候选路径、失败原因和下一步，不修改当前工作区"),
    when("focused test unavailable", then="记录无法运行原因，并运行诊断报告建议的最接近相关测试；如果没有可信测试则 needs_human"),
    when("push fails", then="不创建 MR，记录 git push -u origin <branch> 命令和失败原因"),
    when("MR creation fails", then="不猜凭证或 repository_id，记录 yunxiao-mr CLI 给出的修复命令或下一步"),
])

fallback_strategy(
    [
        when("无法直接复现异常但诊断证据足以证明根因", then="写覆盖根因的回归测试，并在 MR 正文中说明复现限制"),
        when("同名分支确认为其他运行所有", then="创建带短后缀的新 fix/arms- 分支和 worktree"),
        when("review Sub Agent 不可用", then="停止并报告独立审查缺口；只有调用方明确接受风险后才可继续"),
    ],
    require_user_approval="when_destructive",
)

safety_policy(
    must=[
        "只从 status=bug 诊断报告开始修复",
        "在独立 fix worktree 中修改文件，不修改用户当前工作区",
        "自动 push 的唯一范围是自己创建的 fix/arms-YYYYMMDD-{short-title} 分支",
        "由 arms-exceptions-triage 调度时，即使 blocked 或 needs_human，也必须写入 result_path",
        "最终总结必须返回 worktree 路径，供父 Agent 汇总后清理",
        "MR 正文和最终总结必须保留 Source Manifest 结构",
    ],
    must_not=[
        "不要从裸 group_id、截图、日志片段或口头摘要直接开始修复",
        "不要自动合并 MR",
        "不要 push 目标分支、用户当前分支或任何非 fix/arms- 分支",
        "不要在测试失败、review 未通过或证据不足时创建 MR",
        "不要自行删除 fix worktree",
        "不要打印、保存或发送凭证、Authorization header、AccessKey、Token、SecurityToken、签名 URL 或 OAuth code",
    ],
    approval_required=[
        "外部权限、数据迁移、发布动作、跨仓库变更或产品判断",
        "跳过独立 review Sub Agent 后继续创建 MR",
        "任何会影响非 fix/arms- 分支的 git 操作",
    ],
)

quality_bar(
    must=[
        "repair_result 明确 status: fixed | blocked | needs_human",
        "fixed 结果必须包含 fix branch、worktree、commit、Yunxiao MR localId 和详情页 URL",
        "blocked 或 needs_human 必须包含阻塞原因、已执行验证和可执行下一步",
        "验证证据必须列出命令、结果和失败日志路径或通过摘要",
        "父 Agent 派发时，result_path 文件与聊天最终总结一致",
        "Source Manifest 包含 Sources、Produced artifacts、Key decisions、Verification evidence、Open questions / risks",
    ],
    should=[
        "MR 正文避免大段 raw logs，只保留摘要、诊断报告路径、ARMS show 命令、测试命令和关键代码路径",
        "分支名和 worktree slug 稳定、可读、不会泄露敏感业务数据",
        "P2 review 发现要么修复，要么写入 MR 风险或后续项",
    ],
    must_not=[
        "不要把聊天上下文当成唯一来源",
        "不要把未验证的外部控制台链接或凭证路径写入报告",
    ],
)

output_format(
    name="repair_result",
    required_sections=[
        "状态",
        "分支和 MR",
        "变更摘要",
        "验证",
        "风险",
        "Source Manifest",
    ],
)

validation(
    [
        check("diagnostic_report_contract_valid", "诊断报告为 status=bug，且包含异常指纹、证据、根因、建议修复范围、建议测试和 Source Manifest。"),
        check("isolated_worktree_only", "所有文件修改都发生在 .arms-exceptions/worktrees/fix-<stable-slug>/ 对应 worktree。"),
        check("regression_test_first", "实现修复前已新增或确认失败回归测试；无法复现时已说明证据依据。"),
        check("verification_passed_before_mr", "创建 MR 前 focused test 和必要相关测试已通过。"),
        check("review_gate_passed", "独立 review Sub Agent 已完成，且没有未解决 P0/P1。"),
        check("push_scope_valid", "push 目标只可能是 fix/arms- 分支。"),
        check("result_path_written_when_provided", "父 Agent 提供 result_path 时，fixed、blocked、needs_human 都会写入该文件。"),
        check("secrets_not_exposed", "最终总结、MR 正文、日志摘要和错误信息不包含凭证、完整签名 URL 或鉴权头。"),
    ],
    on_failure="report",
)

examples([
    example(
        user="/fix-arms-exception .arms-exceptions/triage/20260604-120000/subagents/diagnose-api-timeout.md",
        expected_behavior="读取 status=bug 诊断报告和 Source Manifest，创建 fix/arms- 分支与独立 worktree，TDD 修复、review、push 并创建 Yunxiao MR，最终输出 repair_result。",
        input_files=[".arms-exceptions/triage/<run-id>/subagents/diagnose-<stable-slug>.md"],
        output="repair_result",
    ),
    example(
        user="父 Agent 派发 fix-arms-exception，并要求写入 .arms-exceptions/triage/<run-id>/subagents/fix-api-timeout.md",
        expected_behavior="无论 fixed、blocked 还是 needs_human，都把最终总结写入 result_path，保留 worktree 路径供父 Agent 后续清理。",
        input_files=[
            ".arms-exceptions/triage/<run-id>/subagents/diagnose-<stable-slug>.md",
            ".arms-exceptions/triage/<run-id>/subagents/fix-<stable-slug>.md",
        ],
        output="result_artifact",
    ),
])
```
