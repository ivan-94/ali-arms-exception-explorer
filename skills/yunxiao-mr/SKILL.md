---
name: yunxiao-mr
description: 管理阿里云云效 Codeup 合并请求。用于 Agent 需要在云效仓库创建、列举、查看、更新、评论、打类标、关闭、重开或合并 MR/合并请求时。
---

```python
from skill_contract import *

skill(
    name="yunxiao-mr",
    purpose="通过随 skill 分发的 CLI 管理阿里云云效 Codeup 合并请求，并保持凭证和真实写操作边界清晰。",
)

activate_when(
    [
        "用户要求在云效 Codeup 仓库创建、列举、查看、更新、评论、关闭、重开或合并 MR",
        "用户要求给云效 MR 添加、移除、创建、删除或列举类标",
        "Agent 工作流需要通过云效 MR 发布修复、同步验收状态或读取 MR 评论",
        "用户提到 yunxiao-mr、Codeup MR、云效合并请求或云效类标管理",
    ],
    match="any",
)

do_not_activate_when([
    "用户只要求管理 GitHub、GitLab 或非云效平台的 PR/MR",
    "用户只要求生成 MR 描述草稿而不访问或操作云效",
    "用户要求配置 ARMS、SLS、飞书通知或异常分诊，且不涉及云效 MR 操作",
])

inputs(
    required=[
        input(
            "mr_task",
            type=NaturalLanguage,
            description="用户要执行的云效 MR 操作，例如 create、list、view、edit、label、comment、close、reopen 或 merge。",
        ),
    ],
    optional=[
        input("local_id", type=Text, description="云效 MR 的 localId；view/edit/comment/close/reopen/merge 和 MR 类标操作需要。"),
        input("title", type=Text, description="创建或更新 MR 的标题。"),
        input("body_or_body_file", type=Text, description="MR 描述或评论正文，优先用 --body-file 传递长文本。"),
        input("head_branch", type=Text, description="源分支；create 默认使用当前分支，但必须确认已推送到云效 remote。"),
        input("base_branch", type=Text, description="目标分支；默认使用本地 yunxiao 配置。"),
        input("labels", type=Text, description="要过滤、创建、删除、添加或移除的项目类标或 MR 类标。"),
        input("merge_method", type=Text, description="合并方式：no-fast-forward、squash、rebase 或 ff-only；默认 squash。"),
        input("json_required", type=Text, description="下游需要结构化消费时使用 --json，优先解析稳定字段。"),
    ],
    ask_when_missing=True,
)

outputs(
    required=[
        output(
            "operation_result",
            type=Text,
            description="CLI 的人类可读结果或 --json 结构化结果摘要。",
            success_criteria=["说明已执行的 MR 操作、关键结果和失败时的可执行下一步"],
        ),
        output(
            "next_steps",
            type=Text,
            description="需要用户或后续 Agent 执行的下一步，例如 git push、补 token、补权限、查看详情或清理临时类标。",
        ),
    ],
    optional=[
        output("mr_url", type=URL, description="MR 详情页 URL；优先使用 detailUrl，不把仓库首页当作 MR 链接。"),
    ],
)

resources(
    scripts=[
        script(
            "scripts/cli.py",
            when="执行任何云效 MR 检查、读取或写入操作时",
            interface="python3 skills/yunxiao-mr/scripts/cli.py <command> [options]",
            run_help_first=True,
            black_box=False,
            requires=["python3", "git"],
            outputs=["operation_result"],
        ),
    ],
    references=[
        reference(
            "references/cli.md",
            when="构造 yunxiao-mr 命令或确认输出字段时",
            read_strategy="on_demand",
        ),
    ],
)

environment(
    variables=[
        env(
            "YUNXIAO_ACCESS_TOKEN",
            required=False,
            secret=True,
            when="执行需要云效 API 的 doctor、读取或写入操作时；只从环境变量读取，不写入配置、日志、报告或测试产物。",
        ),
    ],
    commands=["python3", "git", "bash"],
    network="required",
    filesystem="workspace",
)

workflow(
    [
        step(
            "prepare_context",
            f"""
            读取 references/cli.md 中与当前 mr_task 直接相关的命令、参数和输出字段，然后先运行 doctor。
            使用 {call_script(
                "scripts/cli.py",
                how="从宿主项目根目录运行 python3 skills/yunxiao-mr/scripts/cli.py doctor --json；只做本地检查时加 --skip-api",
                expect="配置、remote、缓存和 API readiness 的结构化结果；失败时给出可执行下一步",
                on_failure="停止后续云效操作，按 CLI 输出提示修正 token、remote 或本地 yunxiao 配置",
            )}。
            """,
            reads=["mr_task"],
            writes=["cli_contract", "doctor_result"],
        ),
        step(
            "select_operation",
            "根据 mr_task 选择最小命令：create、list、view、edit、label list/create/delete/add/remove、comment、close、reopen 或 merge；缺少 localId、正文、标题、类标名等必要输入时只询问缺失项。",
            reads=["mr_task", "doctor_result"],
            writes=["planned_command"],
        ),
        step(
            "guard_write_operations",
            "create、edit、label create/delete/add/remove、comment、close、reopen 和 merge 都是云效写操作；只有用户当前请求明确要求该动作时才执行。merge 必须再次确认用户确实要求合并，--delete-branch 会删除源分支。",
            reads=["planned_command"],
            ask_user="当用户意图不足以证明要执行真实写操作，或要 merge/--delete-branch 时，先请求明确授权。",
        ),
        step(
            "prepare_payload",
            "创建 MR 前确认源分支已推送到云效 remote；如果未推送，只提示 git push -u origin <branch>。长正文用 --body-file。",
            reads=["planned_command", "head_branch", "body_or_body_file"],
            writes=["prepared_command"],
        ),
        step(
            "execute_operation",
            f"""
            执行选定的 yunxiao-mr 命令，stdout 读取成功结果，stderr 读取错误和下一步；结构化消费时使用 --json。
            使用 {call_script(
                "scripts/cli.py",
                how="从宿主项目根目录运行 python3 skills/yunxiao-mr/scripts/cli.py <planned_command>；保留必要 stdout/stderr 摘要，不粘贴凭证",
                expect="命令成功或返回可修复错误及下一步",
                on_failure="报告发生了什么、可能原因和 CLI 给出的可直接运行下一步，不猜测 token 或仓库 ID",
            )}。
            """,
            reads=["prepared_command", "planned_command"],
            writes=["operation_result"],
        ),
        step(
            "summarize_result",
            "向用户总结 localId、status、detailUrl/webUrl、类标变化、评论/关闭/重开/合并结果和下一步；涉及生产或真实业务数据时只保留必要证据。",
            reads=["operation_result", "doctor_result"],
            writes=["operation_result", "mr_url", "next_steps"],
        ),
    ],
    name="manage_yunxiao_mr",
)

decision_rules([
    when("只需要检查配置或权限", then="运行 doctor；Agent 解析优先 doctor --json"),
    when("创建 MR 且源分支未推送", then="停止 create 并提示 git push -u origin <branch>，不要自动 push"),
    when("create --json 成功", then="优先读取顶层 localId、status、url、detailUrl 和 webUrl，同时保留完整 merge_request"),
    when("需要展示 URL", then="优先使用 MR 详情页 detailUrl，不把仓库首页 webUrl 当成 MR 链接"),
    when("edit 被要求修改目标分支", then="停止并说明 edit 只支持标题和描述，不能修改目标分支"),
    when("label add 或 label remove", then="先读取现有 MR 类标，再覆盖式重写完整类标 ID 列表，避免删除无关类标"),
    when("label add 找不到类标", then="默认失败并提示 label create <name>；只有用户明确允许时使用 --create-missing-label"),
    when("merge 被要求执行", then="先读取 MR 详情并检查可见冲突或卡点；只有用户明确要求时才 merge"),
    when("下游 Agent 需要稳定字段或继续自动化分析", then="优先使用 --json 而不是人类表格输出"),
    when("正文或评论较长", then="优先使用 --body-file，避免 shell quoting 问题"),
    when("CLI 失败", then="保留脱敏 stderr、exit code 和 CLI 下一步，不猜测 token 或仓库 ID"),
    when("云效返回权限、仓库身份或类标错误", then="停止写操作并让用户按 CLI 下一步修正环境或权限"),
])

quality_bar(
    must=[
        "先运行 doctor，再执行任何云效 MR 读取或写入操作",
        "所有命令默认从宿主项目根目录执行：python3 skills/yunxiao-mr/scripts/cli.py <command>",
        "YUNXIAO_ACCESS_TOKEN 只从环境变量读取，任何输出、报告、日志和测试产物都必须脱敏",
        ".arms-exceptions/yunxiao.json 只能保存 domain、api_domain、organization_id、repository_identity、repository_id、default_target_branch 等非凭证缓存",
        "stdout 用于成功结果，stderr 用于错误、告警和需要用户处理的信息",
        "命令失败时说明发生了什么、为什么可能发生、下一步怎么修复",
        "结构化结果使用 --json，字段名保持稳定且不包含凭证",
        "创建 MR 时确认分支已推送，MR URL 优先使用 detailUrl",
        "类标 add/remove 保留现有无关类标",
        "最终回复只总结必要证据，不粘贴大段真实生产或业务数据",
    ],
    should=[
        "读取 references/cli.md 处理参数和输出字段",
        "用 --body-file 传递长 MR 描述或评论",
        "保留 CLI 输出中的可执行下一步命令",
    ],
    must_not=[
        "不要把历史计划或旧文档当作当前 CLI 行为权威",
        "不要在用户只要求查看或诊断时执行写操作",
        "不要绕过官方凭证链或把凭证写入项目配置",
        "不要索要、打印、提交或保存 token、AccessKey、SecurityToken、Authorization header、签名 URL 或 OAuth code",
        "不要自动 push 分支；未推送时只提示 git push -u origin <branch>",
        "不要自动合并 MR；只有用户明确要求 merge 时才执行",
        "不要让 label add/remove 只传新增或删除的单个类标 ID",
    ],
)
```
