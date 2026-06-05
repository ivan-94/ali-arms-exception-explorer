---
name: lark-notify
description: 通过飞书/Lark 自定义机器人 Webhook 配置、预览或发送 Agent 通知。用于用户需要把分诊报告、修复结果、MR 链接、验收摘要或其他 Agent 产物发送到飞书群，或提到飞书机器人、Lark bot、Webhook 通知。
---

```python
from skill_contract import *

skill(
    name="lark-notify",
    purpose="通过随 Skill 分发的 CLI 配置、预览或发送飞书/Lark 自定义机器人通知；只负责 Webhook 传输和通用 payload 渲染。",
)

activate_when(
    [
        "用户要求配置、检查或使用飞书/Lark 自定义机器人 Webhook",
        "用户要求把分诊报告、修复结果、MR 链接、验收摘要或其他 Agent 产物发送到飞书群",
        "用户提到飞书机器人、Lark bot、Webhook 通知、lark-notify 或 send --dry-run",
        "其他 Skill 需要把已经生成的 raw 飞书 payload 通过 Webhook 发送出去",
    ],
    match="any",
)

do_not_activate_when([
    "用户只想撰写通知文案，不需要配置、预览或发送飞书 Webhook",
    "用户需要开发通用飞书开放平台应用、读取群成员、历史消息或处理回调事件",
    "用户要求生成 ARMS、MR 或验收的业务专用卡片语义，但还没有要求发送 Webhook",
    "用户要求发送到 Slack、邮件、短信或其他非飞书/Lark 渠道",
])

inputs(
    required=[
        input(
            "notification_task",
            type=NaturalLanguage,
            description="用户关于配置、查看配置、预览、发送或排查飞书通知的请求。",
        ),
    ],
    optional=[
        input(
            "webhook_url",
            type=URL,
            description="用户明确提供并要求保存的飞书自定义机器人 Webhook；属于敏感信息。",
        ),
        input(
            "notification_title",
            type=Text,
            description="通知标题；发送 text/card 时使用。",
        ),
        input(
            "notification_body",
            type=Text | File,
            description="通知正文或正文文件路径；普通 Agent 报告优先用 body-file。",
        ),
        input(
            "raw_payload_file",
            type=File,
            description="已经由业务 Skill 构造好的飞书 JSON payload；仅配合 --format raw 使用。",
        ),
        input(
            "message_format",
            type=Text,
            description="消息格式：text、card 或 raw；默认沿用 CLI 的 card。",
            default="card",
        ),
        input(
            "send_authorization",
            type=Text,
            description="用户对真实 Webhook 发送的明确授权；dry-run 和 config --show 不需要。",
        ),
    ],
    ask_when_missing=True,
)

outputs(
    required=[
        output(
            "notification_result",
            type=Text,
            format="concise_status_with_next_step",
            description="配置、预览或发送结果；失败时包含可修复原因和下一步命令。",
            success_criteria=[
                "说明执行的是 config、dry-run 还是真实 send",
                "不包含完整 Webhook、Token、AccessKey、Authorization header、OAuth code 或签名 URL",
                "真实发送结果包含 CLI 返回状态；失败结果包含下一步修复命令",
            ],
        ),
    ],
    optional=[
        output(
            "payload_preview",
            type=Text,
            description="dry-run 或 --json dry-run 的脱敏 payload、大小和截断状态。",
        ),
    ],
)

resources(
    scripts=[
        script(
            "scripts/cli.py",
            when="需要执行 lark-notify 的任何 config、dry-run 或 send 操作时",
            interface="python3 skills/lark-notify/scripts/cli.py [--json] [--config <path>] {config,send} ...",
            run_help_first=True,
            black_box=False,
            requires=["python3"],
            outputs=["notification_result", "payload_preview"],
        ),
    ],
    references=[
        reference(
            "references/cli.md",
            when="构造命令、解释错误、处理 raw payload、真实发送或排查配置前",
            read_strategy="always",
        ),
    ],
)

environment(
    variables=[
        env(
            "ARMS_LARK_WEBHOOK_URL",
            required=False,
            secret=True,
            when="需要从环境变量读取飞书 Webhook 时；优先级低于 .arms-exceptions/lark-notify.local.json。",
        ),
    ],
    commands=["python3"],
    network="optional",
    filesystem="workspace",
)

decision_rules([
    when("用户要求查看配置状态", then="运行 config --show；需要机器可读结果时使用 config --show --json"),
    when("用户提供 webhook_url 并明确要求配置", then="运行 config --webhook-url <url>，让 CLI 写入本地忽略文件并更新 .gitignore"),
    when("用户要求预览、验证、dry-run、setup 阶段检查或尚未明确授权真实发送", then="运行 send ... --dry-run，不发送 HTTP 请求"),
    when("用户明确授权真实发送且通知内容和目的地已确定", then="先确认配置可用，再运行 send；失败后不要自行重复真实发送"),
    when("message_format 是 raw", then="只接受已经构造好的 raw_payload_file；不要改写 payload 的业务字段"),
    when("message_format 是 text 或 card", then="只做通用标题加正文渲染；card 使用通用 lark_md 文本块"),
    when("业务 Skill 已经生成 ARMS、MR 或验收专用卡片 payload", then="用 --format raw 转发该 payload，不把业务字段搬进 lark-notify"),
    when("普通 Agent 报告没有指定格式", then="优先使用 card 和 --body-file"),
    when("用户未授权真实发送", then="改为 dry-run 并报告预览结果"),
    when("Webhook 不应保存到文件", then="引导用户使用 ARMS_LARK_WEBHOOK_URL 环境变量"),
    when("业务专用卡片需求超过通用 text/card 能力", then="要求业务 Skill 生成 raw payload，再由 lark-notify 只负责发送"),
    when("未配置 Webhook 且不是 dry-run", then="停止真实发送，并提示运行 config --webhook-url <webhook> 或设置 ARMS_LARK_WEBHOOK_URL"),
    when("飞书机器人配置了关键词且 Webhook 返回拒绝", then="提示用户确认标题或正文包含机器人关键词"),
    when("text/card payload 超过 20 KB", then="让 CLI 截断正文并保留 body-file 路径；若最小 payload 仍超限则要求缩短标题或正文"),
    when("raw payload 超过 20 KB 或缺少 msg_type", then="停止发送，要求上游业务 Skill 修正 raw JSON"),
    when("CLI 或 help 不可用", then="停止执行并报告脚本路径或 Python 环境问题"),
])

workflow(
    [
        step(
            "classify_intent",
            "从 notification_task 判断本次是查看配置、保存 Webhook、dry-run 预览、真实发送还是错误排查；缺少必要标题、正文、raw_payload_file 或发送授权时只询问缺失项。",
            reads=["notification_task"],
            writes=["operation_plan"],
        ),
        step(
            "read_cli_reference",
            "读取 references/cli.md，确认 Webhook 读取优先级、命令参数、payload 格式、20 KB 限制、脱敏规则和 exit code。",
            reads=["operation_plan"],
            writes=["cli_contract"],
        ),
        step(
            "inspect_cli_help",
            f"""
            在执行前检查 CLI 当前接口，尤其是 --json、config、send、--format 和 --dry-run 是否存在。
            使用 {call_script(
                "scripts/cli.py",
                how="从宿主项目根目录运行 python3 skills/lark-notify/scripts/cli.py --help；按需继续运行 config --help 或 send --help",
                expect="help 输出显示 config 和 send 子命令以及 dry-run/send 参数",
                on_failure="停止执行并报告 lark-notify CLI 当前不可用",
            )}。
            """,
            reads=["cli_contract"],
            writes=["cli_help"],
        ),
        step(
            "show_config",
            f"""
            当用户要求检查配置时，查看本地配置状态，不打印完整 Webhook。
            使用 {call_script(
                "scripts/cli.py",
                how="从宿主项目根目录运行 python3 skills/lark-notify/scripts/cli.py config --show；Agent 消费优先加 --json",
                expect="输出配置来源、是否已配置和脱敏 Webhook",
                on_failure="报告配置不可读原因和 config --webhook-url 或 ARMS_LARK_WEBHOOK_URL 下一步",
            )}。
            """,
            reads=["operation_plan", "cli_help"],
            writes=["notification_result"],
            when="operation_plan 是查看配置或真实发送前配置检查",
        ),
        step(
            "save_webhook",
            f"""
            只有用户明确提供 webhook_url 并要求保存时才写入本地配置；不要在回复或报告中打印完整 URL。
            使用 {call_script(
                "scripts/cli.py",
                how="从宿主项目根目录运行 python3 skills/lark-notify/scripts/cli.py config --webhook-url <webhook_url>",
                expect="CLI 写入 .arms-exceptions/lark-notify.local.json，确保 .gitignore 忽略它，并只显示脱敏 Webhook",
                on_failure="报告 URL 格式或文件写入错误，并给出重试命令",
            )}。
            """,
            reads=["operation_plan", "webhook_url", "cli_help"],
            writes=["notification_result"],
            when="operation_plan 是保存 Webhook",
        ),
        step(
            "dry_run_payload",
            f"""
            在 setup、预览、未授权真实发送、命令不确定或发送前验证时执行 dry-run；dry-run 不需要 Webhook，也不会发 HTTP 请求。
            使用 {call_script(
                "scripts/cli.py",
                how="从宿主项目根目录运行 python3 skills/lark-notify/scripts/cli.py send，传入 title/body-file/json-file/format，并追加 --dry-run；需要结构化结果时追加 --json",
                expect="输出 payload 类型、大小、是否截断和脱敏后的预览",
                on_failure="报告 payload 构造、raw JSON 或大小错误，并说明下一步如何缩短或修正",
            )}。
            """,
            reads=[
                "operation_plan",
                "notification_title",
                "notification_body",
                "raw_payload_file",
                "message_format",
                "cli_help",
            ],
            writes=["notification_result", "payload_preview"],
            when="operation_plan 是 dry-run 或真实发送前验证",
        ),
        step(
            "send_notification",
            f"""
            真实发送必须有 send_authorization；发送前优先已有 dry-run 结果或先执行 dry_run_payload。
            使用 {call_script(
                "scripts/cli.py",
                how="从宿主项目根目录运行 python3 skills/lark-notify/scripts/cli.py send，传入已批准的 title/body-file/json-file/format；不要追加 --dry-run",
                expect="CLI 返回飞书通知已发送或结构化发送结果",
                on_failure="报告脱敏后的 Webhook 错误、payload 错误或飞书返回错误；不要自动重试真实发送",
            )}。
            """,
            reads=[
                "operation_plan",
                "notification_title",
                "notification_body",
                "raw_payload_file",
                "message_format",
                "send_authorization",
                "payload_preview",
            ],
            writes=["notification_result"],
            when="operation_plan 是真实发送",
            ask_user="如果用户没有明确授权真实发送，先请求确认；确认前只能 dry-run。",
        ),
        step(
            "report_result",
            "向用户简要说明执行结果、是否发送、是否截断、配置状态和下一步；所有 Webhook、Token、签名 URL 和鉴权信息必须保持脱敏。",
            reads=["notification_result", "payload_preview"],
            writes=["notification_result"],
        ),
    ],
    name="notify_with_lark_webhook",
)

quality_bar(
    must=[
        "默认面向中文 Agent 和用户，命令路径以宿主项目根目录为基准。",
        "主 Skill 保持轻量；详细 CLI 参数、payload 和故障处理只引用 references/cli.md。",
        "每次真实发送前有 dry-run 或等价的 payload 预览依据。",
        "真实 Webhook 发送前必须有用户明确授权。",
        "Webhook 读取优先级是 .arms-exceptions/lark-notify.local.json 高于 ARMS_LARK_WEBHOOK_URL。",
        ".arms-exceptions/lark-notify.local.json 必须作为本地忽略文件处理，不能提交。",
        "raw payload 必须由上游业务 Skill 构造；lark-notify 不改写业务字段。",
        "text/card/raw 的选择规则清晰，raw 与业务专用 payload 边界清晰。",
        "错误说明包含发生了什么、可能原因和可直接运行的下一步命令。",
        "所有用户可见输出都不泄露完整 Webhook 或其他凭证。",
    ],
    should=[
        "普通 Agent 报告优先使用 card 和 --body-file。",
        "Agent 消费配置或 dry-run 结果时优先加 --json。",
        "真实发送后只总结必要状态，不粘贴大段原始 payload。",
    ],
    must_not=[
        "不要让 lark-notify 成为 ARMS triage、Yunxiao MR 或 HAT 报告的业务格式权威。",
        "不要在 contract 外新增行为性 Markdown 说明。",
        "不要读取群成员、历史消息或回调事件。",
        "不要发送凭证、Authorization header、AccessKey、Secret、Token、SecurityToken、签名 URL 或 OAuth code。",
        "不要把 ARMS、MR 或验收领域语义写进通用 card 渲染。",
        "不要在 setup 阶段发送真实通知。",
        "不要在失败后自行重复真实发送。",
    ],
)
```
