---
name: arms-exceptions-triage
description: 在 CI 或 Agent 自动流程中分诊单个 ARMS target/service，编排 explorer、Yunxiao MR 与 Lark 通知，产出待人工 review 的本地 triage 报告；只有人工 review 明确通过后，才对明确 bug 且无强证据 MR 覆盖的代表项派发 fix-arms-exception。Use when 用户要求分诊、排查、汇总、处理或完整处理 ARMS 异常。
---

```python
from skill_contract import *

skill(
    name="arms-exceptions-triage",
    purpose="在 CI 或 Agent 自动流程中完整分诊一个 ARMS target/service 的异常；父 Agent 只负责编排、聚合、MR 覆盖判断、人工 review gate、获批后的修复派发和通知。",
)

activate_when(
    [
        "用户要求分诊、排查、汇总、处理或完整处理 ARMS 异常",
        "用户要求在 CI 或 Agent 自动流程中处理一个 ARMS target 或 service 的异常",
        "用户要求对 ARMS 异常做去重诊断、关联 Yunxiao MR、准备人工 review、派发已获批修复或发送 Lark 通知",
        "宿主项目需要运行 arms-exceptions-triage 编排 explorer、yunxiao-mr、fix-arms-exception 和 lark-notify",
    ],
    match="any",
)

do_not_activate_when([
    "用户只要求读取单个异常 group 的详情、stacktrace 或 raw event，应使用 arms-exceptions-explorer",
    "用户已经有 status=bug 的诊断报告并要求修复单个异常，应使用 fix-arms-exception",
    "用户只要求管理 Yunxiao/Codeup MR、类标或评论，应使用 yunxiao-mr",
    "用户只要求发送或配置飞书通知，应使用 lark-notify",
    "用户要求修改本 skill 源仓库代码，而不是在宿主项目执行 ARMS 分诊流程",
])

inputs(
    required=[
        input(
            "target_or_service",
            type=NaturalLanguage,
            description="用户给出的 ARMS target 名称或 service 名称；service 必须能从 targets --json 唯一反查 target。",
        ),
    ],
    optional=[
        input(
            "host_root",
            type=Directory,
            description="触发 triage 的宿主项目根目录；默认使用当前工作目录。",
            default="current working directory",
            required=False,
        ),
        input(
            "window",
            type=Text,
            description="同步异常的时间窗口；未提供时使用宿主项目配置或 explorer 默认值。",
            required=False,
        ),
        input(
            "execution_mode",
            type=Text,
            description="triage_only 或 review_approved_fix；默认 triage_only，只产出待人工 review 的分诊报告。只有调用方明确说明人工 review 已通过时才能使用 review_approved_fix。",
            default="triage_only",
            required=False,
        ),
        input(
            "run_id",
            type=Text,
            description="本次 triage 产物目录 ID；未提供时生成 <YYYYMMDDTHHMMSS>-<target-or-service>。",
            required=False,
        ),
        input(
            "human_review_approval",
            type=Text,
            description="人工 review 通过证据，例如用户明确批准语句、审批记录路径或 review 结论摘要；只有 execution_mode=review_approved_fix 时需要。",
            required=False,
        ),
    ],
    ask_when_missing=True,
)

outputs(
    required=[
        output(
            "triage_artifacts",
            type=Directory,
            description="HOST_ROOT/.arms-exceptions/triage/<run-id>/ 下的 groups、dedupe、post-diagnosis、MR、summary、source manifest 和通知 payload。",
            success_criteria=[
                "所有产物写在 HOST_ROOT，而不是 triage worktree 的相对路径",
                "source-manifest.md 包含 Sources、Produced artifacts、Key decisions、Verification evidence 和 Open questions / risks",
                "groups.json、dedupe.json、post-diagnosis-dedupe.json、summary.md 和 lark-card.json 路径明确",
            ],
        ),
        output(
            "summary_report",
            type=File,
            description="中文 summary.md，记录分诊结论、代表异常、重复合并、MR 覆盖、人工 review 状态、风险和下一步。",
        ),
        output(
            "notification_result",
            type=Text,
            description="lark-notify raw card 发送结果；无法发送时记录本地 payload 路径和失败原因。",
        ),
    ],
    optional=[
        output(
            "fix_results",
            type=Text,
            description="review_approved_fix 模式下 SubAgent(high) 执行 fix-arms-exception 后写回的 MR、blocked 或 needs_human 结果。",
        ),
    ],
)

resources(
    references=[
        reference(
            "references/dedupe.md",
            when="生成 dedupe.json 或 post-diagnosis-dedupe.json 时",
            read_strategy="on_demand",
        ),
        reference(
            "references/mr-coverage.md",
            when="生成 existing-mrs.json 或决定是否进入人工 review 时",
            read_strategy="on_demand",
        ),
        reference(
            "references/templates/diagnosis-brief.md",
            when="派发诊断 Sub Agent 时",
            read_strategy="on_demand",
        ),
        reference(
            "references/templates/diagnostic-report.md",
            when="校验诊断报告或要求 Sub Agent 输出报告时",
            read_strategy="on_demand",
        ),
        reference(
            "references/templates/fix-brief.md",
            when="派发 fix-arms-exception 修复 Sub Agent 时",
            read_strategy="on_demand",
        ),
        reference(
            "references/templates/fix-result.md",
            when="校验 fix result 或汇总修复结果时",
            read_strategy="on_demand",
        ),
        reference(
            "references/templates/summary.md",
            when="生成 summary.md 时",
            read_strategy="on_demand",
        ),
        reference(
            "references/templates/lark-card.json",
            when="生成 lark-card.json 时",
            read_strategy="on_demand",
        ),
    ],
)

environment(
    variables=[
        env("YUNXIAO_ACCESS_TOKEN", required=False, secret=True, when="执行 Yunxiao MR 覆盖判断或创建 MR 时；只从环境变量读取，不得写入报告。"),
        env("ARMS_LARK_WEBHOOK_URL", required=False, secret=True, when="通过 lark-notify 发送通知时；不得打印完整 URL。"),
    ],
    commands=["python3", "git", "rg"],
    network="required",
    filesystem="workspace",
)

workflow(
    [
        step(
            "resolve_scope",
            f"""
            在 HOST_ROOT 运行 doctor 和 targets，解析 target_or_service、services、branch 和窗口。
            使用 {call_skill(
                "arms-exceptions-explorer",
                how="from HOST_ROOT run doctor and targets --json; if input is a service, require targets --json to map it to exactly one target",
                mode="compose",
                expect="one target, one configured branch, and the services to process",
                on_failure="write blocked/needs_human evidence and stop without guessing target, branch, or default project",
            )}。
            """,
            reads=["target_or_service", "host_root", "window"],
            writes=["scope", "source_manifest"],
        ),
        step(
            "prepare_artifacts_and_worktree",
            f"""
            生成 run_id，创建 HOST_ROOT/.arms-exceptions/triage/<run-id>/，确认忽略 triage/worktrees 本地产物，并从 target.branch 创建 TRIAGE_WORKTREE_ROOT。
            使用 {call_tool(
                "git",
                how="create or switch to HOST_ROOT/.arms-exceptions/worktrees/triage-<run-id>/ from the configured target branch; record commands, cwd, branch, and paths in source-manifest.md",
                expect="isolated triage worktree rooted under HOST_ROOT/.arms-exceptions/worktrees/",
                on_failure="continue only when read-only triage can still run safely in HOST_ROOT; otherwise record blocked and notify",
            )}。
            """,
            reads=["scope", "run_id"],
            writes=["triage_artifacts", "triage_worktree_root", "source_manifest"],
        ),
        step(
            "sync_and_collect_groups",
            f"""
            在 TRIAGE_WORKTREE_ROOT 同步异常并保存 groups.json。
            使用 {call_skill(
                "arms-exceptions-explorer",
                how="run sync --target <target> --json or sync --service <service> --json, then groups --target <target> --json or groups --service <service> --json; write the groups output to HOST_ROOT/.arms-exceptions/triage/<run-id>/groups.json",
                mode="compose",
                expect="groups.json contains each retained group plus group/sample_trace_id and trace_console_url when explorer can derive it",
                on_failure="write sync failure details to summary/source-manifest and notify instead of continuing with stale or guessed groups",
            )}。
            """,
            reads=["scope", "triage_worktree_root"],
            writes=["groups_json", "source_manifest"],
        ),
        step(
            "initial_dedupe",
            "父 Agent 只基于 groups --json 元数据做初筛聚合，保存 dedupe.json；group_id 只作为本次运行内定位，不能作为跨运行强证据。",
            reads=["groups_json"],
            writes=["dedupe_json", "source_manifest"],
        ),
        step(
            "dispatch_diagnostics",
            f"""
            对 dedupe.json 中保留的代表异常派发 medium-effort 诊断 Sub Agent；brief 必须独立可执行，并包含 HOST_ROOT、TRIAGE_WORKTREE_ROOT、target、services、branch、group_id、related_group_ids、查看命令和 output_path。
            使用 {call_subagent(
                "arms-diagnosis",
                "diagnose each retained ARMS exception group without editing business code",
                how="spawn one or more medium-effort diagnostic Sub Agents with the reference workflow diagnostic brief; require each report at HOST_ROOT/.arms-exceptions/triage/<run-id>/subagents/diagnose-<stable-slug>.md and require Source Manifest sections",
                context="isolated diagnostic context with HOST_ROOT, TRIAGE_WORKTREE_ROOT, groups.json, dedupe.json, references/templates/diagnosis-brief.md, and references/templates/diagnostic-report.md only",
                effort="medium",
                result_path="HOST_ROOT/.arms-exceptions/triage/<run-id>/subagents/diagnose-<stable-slug>.md",
                expect="diagnostic reports with status noise | needs_human | bug, confidence, evidence, code paths when bug, repair suggestion, tests, and Source Manifest",
                on_failure="mark the item blocked/needs_human or dispatch a supplemental diagnostic Sub Agent; do not infer code-level evidence in the parent",
            )}。
            """,
            reads=["dedupe_json"],
            writes=["diagnostic_reports", "source_manifest"],
        ),
        step(
            "post_diagnosis_dedupe",
            "父 Agent 收集诊断报告后必须基于 Sub Agent 报告中的根因、代码路径、修复建议和证据复聚合，保存 post-diagnosis-dedupe.json；被合并重复项不得独立进入 MR 覆盖判断或修复派发。",
            reads=["diagnostic_reports"],
            writes=["post_diagnosis_dedupe_json", "source_manifest"],
        ),
        step(
            "check_mr_coverage",
            f"""
            只对 post-diagnosis-dedupe.json 的代表项做 Yunxiao MR 覆盖判断；不得用 group_id 单独判定 covered。
            使用 {call_skill(
                "yunxiao-mr",
                how="run list --state opened --json and targeted view/search checks as needed; compare MR title/body/comments against diagnostic report fields, root cause, code path, branch, service, operation, and normalized message",
                mode="compose",
                expect="existing-mrs.json with covered, maybe_related, or not_related decisions and evidence for each representative item",
                on_failure="record maybe_related or blocked rather than marking an item covered on weak evidence",
            )}。
            """,
            reads=["post_diagnosis_dedupe_json"],
            writes=["existing_mrs_json", "source_manifest"],
        ),
        step(
            "write_summary_and_payload",
            "生成中文 summary.md、source-manifest.md 和业务专用 lark-card.json；卡片只放摘要、统计、代表异常、MR、人工 review 状态和下一步，长详情留在本地 summary.md。",
            reads=["groups_json", "dedupe_json", "post_diagnosis_dedupe_json", "existing_mrs_json"],
            writes=["summary_report", "lark_card_json", "source_manifest"],
        ),
        step(
            "record_human_review_gate",
            "把所有 status=bug 且未被强证据 MR 覆盖的代表项标记为 pending_human_review，列出建议 review 关注点、诊断报告路径、MR 覆盖证据和获批后可执行的修复派发参数；未获人工 review 通过时必须到此停止，不创建修复 worktree、不派发 fix-arms-exception。",
            reads=["post_diagnosis_dedupe_json", "existing_mrs_json", "summary_report"],
            writes=["summary_report", "lark_card_json", "source_manifest"],
            when="execution_mode is triage_only or human review approval is not explicitly recorded",
        ),
        step(
            "dispatch_fixes",
            f"""
            review_approved_fix 模式下，且 source-manifest.md 已记录人工 review 通过证据时，对 post-diagnosis-dedupe.json 中 status=bug 且未被强证据 MR 覆盖的代表项派发 SubAgent(high) 执行 fix-arms-exception；triage_only 模式或缺少人工 review 通过证据时必须跳过修复并记录原因。
            使用 {call_subagent(
                "arms-fix",
                "run fix-arms-exception for one representative bug diagnosis and create a Yunxiao MR when fixable",
                how="after explicit human review approval, spawn high-effort fix Sub Agents with diagnostic_report, result_path, target, branch, representative_group_id, covered_duplicate_group_ids, and the recorded approval evidence; require TDD, review, MR creation when fixed, and a final report at result_path",
                context="isolated fix context anchored at HOST_ROOT plus the diagnostic report, references/templates/fix-brief.md, and references/templates/fix-result.md",
                effort="high",
                result_path="HOST_ROOT/.arms-exceptions/triage/<run-id>/subagents/fix-<stable-slug>.md",
                expect="fix result reports with status fixed | blocked | needs_human, branch, MR URL, verification, review result, risks, and Source Manifest",
                on_failure="record blocked in summary/source-manifest; do not assume the MR exists or the fix succeeded",
            )}。
            """,
            reads=["execution_mode", "human_review_approval", "post_diagnosis_dedupe_json", "existing_mrs_json", "source_manifest"],
            writes=["fix_results", "source_manifest"],
            when="execution_mode is review_approved_fix, human review approval is explicitly recorded, and at least one representative bug is not strongly covered by an MR",
        ),
        step(
            "cleanup_fix_worktrees",
            f"""
            父 Agent 汇总 fix 结果后清理本次创建的 fix worktree；只允许清理 HOST_ROOT/.arms-exceptions/worktrees/ 下且能确认属于本次运行的路径。
            使用 {call_tool(
                "git",
                how="run git -C \"$HOST_ROOT\" worktree remove \"$HOST_ROOT/.arms-exceptions/worktrees/fix-<stable-slug>\" for each completed fix worktree; never force-remove dirty, unrelated, or outside-root worktrees",
                expect="cleanup result recorded for every fix worktree",
                on_failure="leave the worktree in place and record path, reason, and suggested next command in summary/source-manifest",
            )}。
            """,
            reads=["fix_results"],
            writes=["source_manifest"],
            when="fix worktrees were created",
        ),
        step(
            "send_notification",
            f"""
            通过 lark-notify 发送 triage 生成的 raw card payload；lark-notify 只负责传输，不解析 ARMS 业务字段。
            使用 {call_skill(
                "lark-notify",
                how="run send --json-file HOST_ROOT/.arms-exceptions/triage/<run-id>/lark-card.json --format raw after checking that the payload contains no credentials or signed URLs",
                mode="compose",
                expect="notification_result records sent, dry failure, missing webhook, or other masked error",
                on_failure="keep summary.md and lark-card.json as durable local artifacts and report the masked send failure",
            )}。
            """,
            reads=["lark_card_json"],
            writes=["notification_result", "triage_artifacts"],
        ),
    ],
    name="triage_run",
)

decision_rules([
    when("target_or_service names a target", then="process all configured services under that target"),
    when("target_or_service names a service", then="resolve it to exactly one target from targets --json; otherwise stop and ask the caller to pass target"),
    when("target has no configured branch", then="stop as blocked and do not guess main/master/dev"),
    when("execution_mode is triage_only or the caller has not explicitly provided human review approval", then="skip dispatch_fixes, mark fixable uncovered bugs as pending_human_review, and record the approval gate"),
    when("execution_mode is review_approved_fix and representative item is status=bug and not strongly MR-covered", then="dispatch SubAgent(high) with fix-arms-exception only after recording the human review approval evidence"),
    when("Sub Agent report omits required status, evidence, code path for bug, or output_path", then="mark blocked/needs_human or dispatch supplemental diagnosis before MR coverage or fix"),
    when("trace_console_url is absent", then="show sample_trace_id and local show <group_id> --json command; never guess an Aliyun trace URL"),
    when("doctor, targets, sync, groups, yunxiao-mr, or lark-notify fails with a user-fixable configuration problem", then="write blocked/needs_human with what happened, likely reason, and the next command to fix it"),
    when("external API credentials or permissions are missing", then="do not print secrets; record the missing capability and notify using any available safe channel"),
    when("Sub Agent cannot complete diagnosis or fix", then="preserve its report path, status, verification evidence, and open risks; do not invent missing evidence"),
    when("cleanup cannot safely remove a worktree", then="keep the path and record the exact non-destructive cleanup recommendation"),
    when("需要持久化产物", then="始终写入 HOST_ROOT/.arms-exceptions/triage/<run-id>/，不要写到 TRIAGE_WORKTREE_ROOT 的相对路径"),
    when("诊断报告产出新根因证据", then="先做 post-diagnosis dedupe，再做 MR 覆盖判断和人工 review gate，获批后才允许 fix 派发"),
    when("TRIAGE_WORKTREE_ROOT cannot be created but read-only triage can safely run in HOST_ROOT", then="record the degraded cwd choice in source-manifest.md and continue only if it does not touch business code"),
    when("Yunxiao MR coverage cannot be queried", then="treat coverage as unknown/maybe_related and do not mark a bug as MR-covered solely because MR data is unavailable"),
    when("Lark notification cannot be sent", then="keep lark-card.json and summary.md locally, record the masked send failure, and return notification_result accordingly"),
])

quality_bar(
    must=[
        "一次只处理一个 target；service 输入必须唯一反查 target，不得静默跨多个 target",
        "父 Agent 只能协调、调度、聚合、判断和通知；不得亲自读取、搜索、分析或修改业务代码",
        "异常详情、stacktrace、日志详情、代码路径、根因、修复方案和测试范围判断必须由诊断或修复 Sub Agent 完成",
        "复聚合和 MR 覆盖判断只能使用 groups --json 元数据、Sub Agent 报告、post-diagnosis-dedupe.json 和 yunxiao-mr 输出",
        "未获人工 review 明确通过前，不得派发 fix-arms-exception、创建修复 worktree 或创建修复 MR",
        "所有 Sub Agent brief 和持久产物必须包含可重读的 Source Manifest",
        "summary.md、lark-card.json 和用户可见结论使用中文",
        "target/service、services、branch、window、HOST_ROOT、TRIAGE_WORKTREE_ROOT 和 run_id 明确记录",
        "source-manifest.md 记录 Sources、Produced artifacts、Key decisions、Verification evidence 和 Open questions / risks",
        "diagnostic Sub Agent brief 和 fix Sub Agent brief 不依赖聊天上下文即可执行",
        "post-diagnosis-dedupe.json 记录代表项、合并项、合并原因、诊断报告路径和是否进入 MR 覆盖/人工 review",
        "existing-mrs.json 区分 covered、maybe_related 和 not_related，并保留证据",
        "summary.md 展示复聚合前后数量、代表异常、重复项、MR、人工 review 状态、证据路径和剩余风险",
        "lark-card.json 不含凭证或签名 URL，且长详情留在本地 summary.md",
    ],
    should=[
        "父 Agent 自行决定 Sub Agent 并发，并在 source-manifest.md 记录调度理由",
        "blocked/needs_human 结论包含发生了什么、为什么可能发生、下一步怎么修复",
        "待人工 review 项包含建议 review 关注点、获批后可执行的修复派发参数和未解决风险",
        "获批后执行的 fix result 包含 TDD、review、MR URL 和未解决风险",
    ],
    must_not=[
        "不得用父 Agent 猜测补足 Sub Agent 未提供的根因、代码路径或测试建议",
        "不得把初筛没有合并的 group 直接视为不同 bug",
        "不得因为 maybe_related 或查询失败把明确 bug 判定为已有 MR 覆盖",
        "不要在人工 review 明确通过前派发 fix-arms-exception",
        "不要在诊断后复聚合完成前派发 fix-arms-exception",
        "不要把 group_id 当作跨运行 MR 覆盖强证据",
        "不要清理用户当前工作区、非 HOST_ROOT/.arms-exceptions/worktrees/ 路径或无法确认属于本次运行的 worktree",
        "不要打印或提交 AccessKey、Secret、Token、SecurityToken、OAuth code、Authorization header、签名 URL 或完整 webhook",
        "不要让 lark-notify 承担 ARMS 字段解释；业务卡片由 triage 生成 raw payload",
    ],
)

examples([
    example(
        user="分诊 ai-service-dev 最近 2 小时 ARMS 异常",
        expected_behavior="解析 ai-service-dev 为单个 target，默认 triage_only：sync、groups、初筛 dedupe、派发诊断、诊断后复聚合、MR 覆盖判断；对明确且未覆盖 bug 标记 pending_human_review，生成 summary/source-manifest/lark-card 并发送通知，但不派发 fix-arms-exception。",
        output="triage_artifacts",
    ),
    example(
        user="只分诊 ai-service-dev-celery-worker，不要修",
        expected_behavior="选择 triage_only：完成 sync、groups、dedupe、诊断、post-diagnosis dedupe、MR 覆盖和中文 summary，但跳过 fix SubAgent(high)，并在 summary/source-manifest 记录未进入人工 review 后修复阶段。",
        output="summary_report",
    ),
    example(
        user="人工 review 已通过，继续修复 ai-service-dev 的待修复 ARMS 异常",
        expected_behavior="选择 review_approved_fix：先重读 summary/source-manifest、post-diagnosis-dedupe.json、existing-mrs.json 和人工 review 通过证据；只对 status=bug 且未被强证据 MR 覆盖的代表项派发 fix-arms-exception。",
        output="fix_results",
    ),
    example(
        user="处理 service=api-worker 的 ARMS 异常",
        expected_behavior="先用 targets --json 唯一反查 service 所属 target；如果不能唯一定位，停止并要求改传 target，不跨多个 target 猜测执行。",
        output="summary_report",
    ),
])
```
