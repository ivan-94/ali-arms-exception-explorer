---
name: setup-arms-workflow
description: 在宿主项目初始化、配置或检查 ARMS 异常自动分诊修复工作流。Use when 用户要求接入 setup-arms-workflow，闭环 arms-exceptions-explorer、arms-exceptions-triage、fix-arms-exception、yunxiao-mr 和 lark-notify 的本地配置与验证。
---

```python
from skill_contract import *

skill(
    name="setup-arms-workflow",
    purpose="在宿主项目完成 ARMS 异常分诊和修复工作流的本地配置、验证和 setup 证据归档。",
    summary="编排 arms-exceptions-explorer、arms-exceptions-triage、fix-arms-exception、yunxiao-mr 和 lark-notify；不新增 setup CLI，不自动创建 MR，不发送真实飞书通知，不运行 ARMS sync。",
    version="0.1.0",
)

activate_when(
    [
        "用户要求初始化、配置、接入或检查 ARMS 异常自动分诊修复工作流",
        "用户要求在宿主项目设置 setup-arms-workflow 或 ARMS workflow",
        "用户要求闭环 arms-exceptions-explorer、yunxiao-mr、lark-notify、triage 和 fix 的前置配置",
        "用户要求生成 .arms-exceptions/setup/ 下的 setup 报告和 Source Manifest",
    ],
    match="any",
    strength="strong",
)

do_not_activate_when([
    "用户只要求执行一次 ARMS 异常分诊，应使用 arms-exceptions-triage",
    "用户只要求从一个 status=bug 的诊断报告修复代码，应使用 fix-arms-exception",
    "用户只要求发送飞书通知，应使用 lark-notify",
    "用户只要求管理云效合并请求，应使用 yunxiao-mr",
    "用户只要求查看或同步异常数据，应使用 arms-exceptions-explorer",
])


inputs(
    required=[
        input(
            "host_project_root",
            type=Directory,
            description="要配置 ARMS 工作流的宿主项目根目录；所有命令都从这里执行。",
        ),
        input(
            "setup_request",
            type=NaturalLanguage,
            description="用户关于初始化、配置、检查或继续 setup 的具体请求。",
        ),
    ],
    optional=[
        input(
            "region_or_search_hint",
            type=Text,
            description="用于发现 ARMS app 或 SLS project 的 region、关键词或服务线索。",
        ),
        input(
            "confirmed_target",
            type=Text,
            description="用户确认的 target 名、branch、service 列表、窗口和可选 SLS 映射。",
            required=False,
        ),
        input(
            "yunxiao_token_status",
            type=Text,
            description="YUNXIAO_ACCESS_TOKEN 是否已在当前 shell 或 CI secret 中注入；不要收集 token 明文。",
            required=False,
        ),
        input(
            "lark_webhook_source",
            type=Text,
            description="飞书 Webhook 来源：本地配置、ARMS_LARK_WEBHOOK_URL 或用户明确提供的 webhook；输出必须脱敏。",
            required=False,
        ),
    ],
    ask_when_missing=True,
)

outputs(
    required=[
        output(
            "setup_report",
            type=File,
            description="宿主项目 .arms-exceptions/setup/setup-report.md。",
            success_criteria=[
                "包含 ready 或 blocked 状态",
                "覆盖 ARMS、Yunxiao、Lark、本地产物、ignore 规则和配置闭环",
                "blocker 不只写在报告里，也在最终回复中说明",
            ],
        ),
        output(
            "source_manifest",
            type=File,
            description="宿主项目 .arms-exceptions/setup/source-manifest.md。",
            success_criteria=[
                "记录来源、命令、产物、用户确认、验证证据、已闭环配置和未决风险",
                "让下游智能体能重读原始来源，而不是只依赖摘要",
            ],
        ),
        output(
            "ready_or_blocked_summary",
            type=Text,
            description="最终面向用户的 ready 或 blocked 结论、证据和下一步命令。",
            success_criteria=[
                "只有全部配置验证通过才输出 ready",
                "权限、账号、secret 注入或用户拒绝无法在当前会话解决时输出 blocked",
                "不泄露 AccessKey、Token、Webhook、Authorization header 或签名 URL",
            ],
        ),
    ],
    optional=[
        output("setup_artifacts", type=Directory, description="宿主项目 .arms-exceptions/setup/ 下保存的 JSON 检查结果和命令证据。"),
        output("host_ignore_updates", type=Text, description="宿主项目需要存在的 .gitignore 与 .arms-exceptions/.gitignore 忽略规则。"),
    ],
)

resources(
    references=[
        reference(
            "references/workflow.md",
            purpose="setup 报告模板、Source Manifest 模板、命令清单、失败处理和最终检查表。",
            when="执行 setup、续跑 setup、处理失败或生成报告时",
            read_strategy="always",
        ),
    ],
)

environment(
    variables=[
        env("YUNXIAO_ACCESS_TOKEN", required=False, secret=True, purpose="云效 API doctor 和后续 MR 创建能力验证；只从环境变量读取，不保存。"),
        env("ARMS_LARK_WEBHOOK_URL", required=False, secret=True, purpose="飞书 webhook 的可选环境变量来源；输出必须脱敏。"),
    ],
    commands=["python3", "git"],
    network="required",
    filesystem="workspace",
)

workflow(
    [
        step(
            "prepare_setup_artifacts",
            "在宿主项目根目录创建 .arms-exceptions/setup/，初始化 setup-report.md 和 source-manifest.md；先记录 user request、host repository、将要执行的命令和已知输入。",
            reads=["host_project_root", "setup_request"],
            writes=["setup_report", "source_manifest"],
        ),
        step(
            "ensure_local_ignore_rules",
            "确认宿主项目忽略 .arms-exceptions/data/、setup/、triage/、worktrees/ 和 lark-notify.local.json；不要忽略可提交的 .arms-exceptions/config.json。",
            writes=["host_ignore_updates"],
        ),
        step(
            "check_arms_doctor",
            f"""
            从宿主项目根目录运行 ARMS explorer doctor，并保存 stdout JSON 或失败证据到 setup 产物。
            使用 {call_tool(
                "shell",
                how="run python3 skills/arms-exceptions-explorer/scripts/cli.py doctor --json from the host project root and save the result as .arms-exceptions/setup/arms-doctor.json when JSON is produced",
                expect="ARMS local readiness evidence, including next steps when project config is not complete",
                on_failure="record stderr, exit code, and concrete repair command; continue checking other subsystems but do not report ready",
            )}。
            """,
            writes=["setup_artifacts"],
        ),
        step(
            "discover_arms_apps",
            f"""
            读取用户给出的 region 或搜索线索，发现 ARMS app 并保存 arms-apps.json；不得替用户自动选择 app、target、branch 或 service。
            使用 {call_tool(
                "shell",
                how="run python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region <region> --search <keyword> --json and save output to .arms-exceptions/setup/arms-apps.json",
                expect="candidate ARMS apps for user confirmation",
                on_failure="record failure and ask the user for corrected region, keyword, account, or permission setup",
            )}。
            """,
            reads=["region_or_search_hint"],
            writes=["setup_artifacts"],
            ask_user="请确认要写入的 target 名、branch、service 列表，以及多个 app 是否属于同一个 target。",
        ),
        step(
            "discover_or_skip_sls",
            f"""
            SLS 是可选增强；必须让用户明确确认 project/logstore/endpoint，或明确确认跳过 SLS。
            使用 {call_tool(
                "shell",
                how="run sls projects --json and, after the user names a project and endpoint, sls logstores --project <project> --endpoint <endpoint> --json; save outputs under .arms-exceptions/setup/",
                expect="confirmed SLS mapping or an explicit user decision to skip SLS",
                on_failure="record failure and ask whether to retry with corrected project/endpoint or skip SLS",
            )}。
            """,
            writes=["setup_artifacts", "source_manifest"],
            ask_user="请确认每个 service 的 SLS project/logstore/endpoint，或明确确认本次 setup 跳过 SLS。",
        ),
        step(
            "init_arms_config",
            f"""
            用用户确认的 target、branch、service、window 和可选 SLS 映射执行非交互 init；同名 target 需要替换时必须由用户明确确认 --replace。
            使用 {call_tool(
                "shell",
                how="run python3 skills/arms-exceptions-explorer/scripts/cli.py init --target <target> --branch <branch> --service <service> --window <window> plus confirmed SLS flags when present",
                expect=".arms-exceptions/config.json updated with non-secret configuration",
                on_failure="record the failing command and guide the user to fix the missing or ambiguous input before rerunning init",
            )}。
            """,
            reads=["confirmed_target"],
            writes=["setup_artifacts"],
            ask_user="如果要覆盖同名 target，请明确确认使用 --replace；否则默认合并。",
        ),
        step(
            "verify_targets",
            f"""
            初始化后必须重跑 targets，保存 targets.json，并确认每个要分诊的 target 都有 branch、service 且 service 能唯一归属 target。
            使用 {call_tool(
                "shell",
                how="run python3 skills/arms-exceptions-explorer/scripts/cli.py targets --json and save output to .arms-exceptions/setup/targets.json",
                expect="closed target configuration for triage and fix",
                on_failure="record failure and continue guiding the user until target configuration is complete or blocked",
            )}。
            """,
            writes=["setup_artifacts"],
        ),
        step(
            "check_yunxiao",
            f"""
            先运行 skip-api doctor 保存本地/remote 证据；如果缺 YUNXIAO_ACCESS_TOKEN，立即引导用户在当前 shell 或 CI secret 配置，配置后重跑 API doctor。
            使用 {call_tool(
                "shell",
                how="run python3 skills/yunxiao-mr/scripts/cli.py doctor --json --skip-api, then run python3 skills/yunxiao-mr/scripts/cli.py doctor --json only after YUNXIAO_ACCESS_TOKEN is available",
                expect="yunxiao-doctor-skip-api.json and yunxiao-doctor.json, or explicit blocked evidence",
                on_failure="record stderr/exit code; if remote is not Codeup-like or token is missing, give the user the exact next step and mark blocked if it cannot be fixed now",
            )}。
            """,
            writes=["setup_artifacts", "ready_or_blocked_summary"],
            ask_user="如果当前没有 YUNXIAO_ACCESS_TOKEN，请在 shell/CI secret 中配置后告诉我重跑；不要把 token 发到对话里。",
        ),
        step(
            "check_lark",
            f"""
            检查飞书 webhook 配置；如果用户提供 webhook，可以保存到本地忽略文件；随后只运行 config --show --json 验证，不发送真实通知。
            使用 {call_tool(
                "shell",
                how="optionally run python3 skills/lark-notify/scripts/cli.py config --webhook-url <webhook>, then run python3 skills/lark-notify/scripts/cli.py config --show --json and save lark-config.json",
                expect="masked Lark config status without printing the full webhook",
                on_failure="guide the user to provide a webhook or ARMS_LARK_WEBHOOK_URL; mark blocked if unavailable",
            )}。
            """,
            writes=["setup_artifacts", "ready_or_blocked_summary"],
            ask_user="如果尚未配置飞书 webhook，请提供 webhook 或确认已设置 ARMS_LARK_WEBHOOK_URL；最终输出必须脱敏。",
        ),
        step(
            "verify_triage_and_fix_closure",
            "验证 arms-exceptions-triage 和 fix-arms-exception 的前置条件：目标 skill 文件存在、target 有 branch、worktrees 被忽略、Yunxiao doctor 可用、Lark config 可用。",
            reads=["setup_artifacts", "host_ignore_updates"],
            writes=["ready_or_blocked_summary"],
        ),
        step(
            "write_final_reports",
            "按 references/workflow.md 模板写入 setup-report.md 和 source-manifest.md；Source Manifest 必须记录命令、用户决定、产物路径、闭环项、阻塞项和风险。",
            reads=["setup_artifacts", "source_manifest", "ready_or_blocked_summary"],
            produces=["setup_report", "source_manifest"],
        ),
        step(
            "respond_to_user",
            "最终回复必须直接给出 ready 或 blocked、关键验证证据、报告路径和用户下一步；不能只让用户去看 setup-report.md。",
            produces=["ready_or_blocked_summary"],
        ),
    ],
    name="setup_arms_workflow",
)

decision_rules([
    when("ARMS app、target、branch、service 或 SLS 候选不唯一", then="询问用户确认，不猜测默认值"),
    when("用户明确跳过 SLS", then="继续 setup，但在 Source Manifest 和 setup-report.md 记录跳过决定"),
    when("用户确认 SLS project/logstore/endpoint", then="把 SLS 参数写入 init 命令并在 targets --json 后验证"),
    when("doctor --json 说明项目尚未配置", then="把它当作 setup 待办并继续引导配置", else_="真实权限、账号或工具缺失才作为 blocker"),
    when("Yunxiao skip-api doctor 因 remote 不可推断失败", then="记录 stderr/exit code 并引导配置 Codeup remote；无法补齐时 blocked"),
    when("缺少 YUNXIAO_ACCESS_TOKEN 或 Lark webhook", then="在当前对话给出配置命令并等待用户补齐；无法补齐时 blocked"),
    when("所有 ARMS、Yunxiao、Lark、triage/fix 前置验证都通过", then="输出 ready", else_="输出 blocked 并列出下一步"),
    prefer("现场引导用户补齐并重跑验证", over="只把缺失项写进 setup-report.md", reason="setup 目标是闭环可运行配置，报告只是证据归档"),
    prefer("只读发现命令", over="写配置命令", reason="ARMS app、target、branch、service 和 SLS 选择必须先由用户确认"),
])

failure_modes([
    when("找不到 aliyun 或未鉴权", then="引导用户安装/配置阿里云 CLI 或 OAuth，并重跑 ARMS doctor"),
    when("ARMS 权限不足", then="说明缺少的权限或 API，允许继续检查 Yunxiao/Lark，但最终 blocked"),
    when("用户无法确认 app、target、branch、service 或 SLS 选择", then="继续询问；用户拒绝或无法确认时 blocked"),
    when("YUNXIAO_ACCESS_TOKEN 缺失", then="引导 export 或 CI secret 注入并重跑 doctor；不要保存 token"),
    when("Lark webhook 缺失", then="引导提供 webhook 或设置 ARMS_LARK_WEBHOOK_URL 并重跑 config；不要发送真实通知"),
    when("单个子系统失败", then="保留已完成配置和证据，继续可安全检查的子系统，但最终不得输出 ready"),
])

fallback_strategy(
    [
        when("某个命令无法产生 JSON", then="保存 stderr、exit code、命令和修复建议到 Source Manifest，并在最终回复说明"),
        when("无法在当前会话补齐外部权限、账号或 secret", then="完成可安全检查的部分，写 blocked 报告并列出用户下一步"),
        when("用户只要求检查现状而不写入配置", then="只运行只读检查并报告缺口；写入 init、webhook 或 ignore 规则前先取得明确同意"),
    ],
    require_user_approval="when_destructive",
)

safety_policy(
    must=[
        "入口始终是宿主项目根目录，不要在本 skill 源项目中写宿主配置",
        "持久化产物写入宿主项目 .arms-exceptions/setup/",
        "Source Manifest 必须保留原始来源、命令、用户决定、产物路径、验证证据和风险",
        "YUNXIAO_ACCESS_TOKEN 只从环境变量读取，不写入配置、日志、报告或对话",
        "Lark webhook 可以保存到 .arms-exceptions/lark-notify.local.json，但报告和最终回复只能脱敏",
        "用户可见错误必须说明发生了什么、可能原因和可直接运行的下一步命令",
    ],
    must_not=[
        "不要新增 setup CLI；本 skill 只编排现有 skills 和脚本",
        "不要自动创建 MR、类标、评论、merge 或运行真实 Codeup 写操作",
        "不要发送真实飞书通知；setup 阶段最多运行 dry-run 或 config --show",
        "不要运行 ARMS sync；setup 只做配置和 readiness 验证",
        "没有用户确认，不选择 ARMS app、target、branch、service、SLS project 或 logstore",
        "不要自动修改宿主 AGENTS.md、CLAUDE.md 或 CI 配置，只在报告里给建议片段",
        "不要打印或提交 AccessKey、Secret、Token、OAuth code、Authorization header、签名 URL 或完整 webhook",
    ],
    approval_required=[
        "写入或替换宿主 .arms-exceptions/config.json 中的 target 配置",
        "使用 --replace 覆盖同名 target",
        "保存 Lark webhook 到本地忽略文件",
        "修改宿主 .gitignore 或 .arms-exceptions/.gitignore",
        "任何真实外部写操作、通知发送、MR 创建或产生费用的操作",
    ],
)

quality_bar(
    must=[
        "setup 结果只能是 ready 或 blocked，不能留下隐含未配置状态",
        "ready 必须建立在 ARMS target、branch、services、Yunxiao API doctor、Lark config 和 triage/fix 前置条件全部通过之上",
        "blocked 必须说明阻塞项、为什么当前会话不能闭环、用户下一步命令和已完成证据",
        "setup-report.md 与 source-manifest.md 都必须写入宿主项目 .arms-exceptions/setup/",
        "所有命令证据必须可追踪到 Source Manifest，且敏感值已脱敏",
        "复杂模板和失败处理以 references/workflow.md 为细节来源",
    ],
    should=[
        "尽量继续完成不依赖阻塞权限的安全检查，避免丢失已闭环配置",
        "人类可读输出优先简洁，JSON 产物保存到 setup 目录供 Agent 复查",
        "最终回复同时给出报告路径和最短下一步，不要求用户自己从报告里找 blocker",
    ],
    must_not=[
        "不要把 setup-report.md 当作现场引导的替代品",
        "不要把未配置的 doctor 状态误报为 ready",
        "不要在报告、日志或最终回复中泄露凭证",
    ],
)

validation(
    [
        check("workflow_reference_read", "执行 setup 前已读取 references/workflow.md 的模板、失败处理和 final checklist。"),
        check("artifacts_written", "宿主项目 .arms-exceptions/setup/setup-report.md 和 source-manifest.md 已写入。"),
        check("source_manifest_complete", "Source Manifest 包含 Sources、Produced artifacts、User decisions、Commands、Verification evidence、Closed configuration 和 Open questions / risks。"),
        check("arms_targets_closed", "targets --json 已保存，且确认 target 有 branch、services，并满足 triage/fix 唯一定位要求。"),
        check("yunxiao_status_closed", "yunxiao-mr doctor --json --skip-api 已记录；API doctor 已通过或 blocked 原因和下一步明确。"),
        check("lark_status_closed", "lark-notify config --show --json 已记录；webhook 可用或 blocked 原因和下一步明确，且 webhook 脱敏。"),
        check("ignore_rules_present", "宿主 .gitignore 和 .arms-exceptions/.gitignore 忽略 data、setup、triage、worktrees 和本地 webhook。"),
        check("no_external_side_effects", "setup 阶段没有运行 ARMS sync、创建 MR、发送真实飞书通知或执行真实外部写操作。"),
        check("final_status_explicit", "最终回复直接说明 ready 或 blocked，并列出关键证据和下一步。"),
    ],
    on_failure="report",
)

output_format(
    name="setup_closeout",
    required_sections=[
        "状态：ready 或 blocked",
        "已验证",
        "报告路径",
        "下一步",
    ],
)

examples([
    example(
        user="帮这个项目接入 ARMS 自动分诊修复工作流",
        expected_behavior="从宿主项目根目录创建 .arms-exceptions/setup/，发现并确认 ARMS target/SLS，初始化配置，检查 Yunxiao 和 Lark，写入 setup-report.md 与 source-manifest.md，最终输出 ready 或 blocked。",
        output="ready_or_blocked_summary",
    ),
    example(
        user="只检查 setup 是否齐全",
        expected_behavior="运行只读 doctor、targets、yunxiao skip-api/API doctor 和 lark config 检查；除非用户明确同意，不写入新 target、webhook 或 ignore 规则。",
        output="ready_or_blocked_summary",
    ),
    example(
        user="没有 YUNXIAO_ACCESS_TOKEN",
        expected_behavior="引导用户在当前 shell 或 CI secret 中配置 token 并重跑 doctor；不能保存 token，无法补齐时输出 blocked。",
        output="ready_or_blocked_summary",
    ),
])
```
