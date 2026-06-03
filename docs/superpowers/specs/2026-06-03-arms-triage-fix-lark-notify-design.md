# ARMS Triage, Fix, And Lark Notify Skills Design

## Source Manifest

### Sources

- User request in this Codex thread: add three skills in `/Users/ivan/workspace/ai/arms-exceptions`: `arms-exceptions-triage`, `fix-arms-exception`, and `lark-notify`.
- User decision: `arms-exceptions-triage` and `fix-arms-exception` are orchestration-only skills in v1; `lark-notify` includes a lightweight Python CLI.
- User decision: triage accepts one `target`, or one `service` that can be uniquely resolved to a target from `arms-exceptions-explorer targets --json`.
- User decision: target branch must come from `.arms-exceptions/config.json` via `targets --json`; missing branch stops the workflow.
- User decision: triage artifacts live in the host project under `.arms-exceptions/triage/<run-id>/` and must be ignored by the host project's `.gitignore`.
- User decision: `group_id` is not stable and must not be treated as strong evidence that an existing MR covers an exception.
- User decision: existing MR matching uses stable evidence such as exception type, normalized message, top business stack frame, service/operation, root cause, and related branch.
- User decision: diagnostic sub-agents must write fixed-template reports with `status: noise | needs_human | bug`.
- User decision: `fix-arms-exception` must start from a `status=bug` diagnostic report, not from a bare group id or oral summary.
- User decision: `fix-arms-exception` may automatically push its own `fix/arms-YYYYMMDD-{title}` branch and create a Yunxiao MR, but must not automatically merge.
- User decision: `lark-notify` reads webhook config from `.arms-exceptions/lark-notify.local.json` first, then `ARMS_LARK_WEBHOOK_URL`.
- User decision: `lark-notify` v1 supports text, interactive card, and raw payload sending; not rich text, image, or share-chat convenience commands.
- User decision: Lark notifications may include detailed exception content, root cause, stack frames, and useful raw event/log excerpts, but must still never include credentials or authorization material.
- User decision: no fixed sub-agent concurrency limit; the executing parent agent decides scheduling and records the reason.
- User decision: saying only "triage" or "分诊" does not fix code; explicit "分诊并修复", "处理这些异常", or "完整流程" may proceed to fix.
- Existing project rules: `AGENTS.md`.
- Workflow policy: `~/.agents/docs/agents/workflows.md`.
- Handoff policy: `~/.agents/docs/agents/handoff-policy.md`.
- Existing ARMS skill: `skills/arms-exceptions-explorer/SKILL.md` and `skills/arms-exceptions-explorer/references/cli.md`.
- Existing Yunxiao MR skill: `skills/yunxiao-mr/SKILL.md` and `skills/yunxiao-mr/references/cli.md`.
- Existing repository README: `README.md`.
- Feishu custom bot overview: https://open.feishu.cn/document/client-docs/bot-v3/bot-overview
- Feishu/Lark custom bot usage guide: https://open.larksuite.com/document/client-docs/bot-v3/add-custom-bot?lang=zh-CN
- Feishu custom bot card sending guide: https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/quick-start/send-message-cards-with-custom-bot

### Produced artifacts

- `docs/superpowers/specs/2026-06-03-arms-triage-fix-lark-notify-design.md`

### Key decisions

- Keep exception triage and fixing as agent orchestration workflows, not rigid CLIs, because sub-agent dispatch, MR matching, diagnosis depth, and repository-specific tests require agent judgment.
- Build `lark-notify` as a testable standard-library CLI because webhook config, request formatting, signing, size checks, truncation, and dry-run behavior are mechanical and should not be reimplemented by each agent.
- Treat `.arms-exceptions/config.json` as the source of target, service, and branch mapping. Do not infer branch names from local defaults when the target branch is missing.
- Keep triage run artifacts local and ignored under `.arms-exceptions/triage/`, while still preserving Source Manifest data inside those local artifacts for downstream agents.
- Make fix work start from an explicit diagnostic report. This separates "is this actionable?" from "make the code change".
- Allow `fix-arms-exception` to push only its own created `fix/arms-...` branch because MR creation needs a remote source branch; do not extend this permission to unrelated branches.
- Do not treat local `group_id` as durable evidence. It is valid only inside a single triage run for locating ARMS details.
- Let notifications be detailed but bounded by Feishu's custom bot request-size limit and a credential redaction rule.

### Verification evidence

- Inspected current repository structure with `rg --files` and `find skills -maxdepth 3 -type f`.
- Inspected existing `arms-exceptions-explorer` and `yunxiao-mr` skill structure and README patterns.
- Inspected `arms-exceptions-explorer` CLI references and implementation to confirm `targets --json`, `sync --json`, `groups --json`, and `show --json` are available.
- Inspected `yunxiao-mr` CLI references and implementation to confirm `list --json`, branch fields, `create --json`, and MR URL fields are available.
- Read workflow and handoff policy before creating this persistent design artifact.
- Checked official Feishu/Lark custom bot documentation for supported webhook message types, one-way custom bot behavior, signature algorithm, request size, and rate limits.
- No skill files or CLI files have been implemented at design time.

### Open questions / risks

- The actual availability of resumable sub-agents depends on the host agent runner. The triage skill must describe durable input/output files so reruns remain possible even when sub-agents are single-shot.
- Feishu webhook signature secret is not in current user scope. If a future robot enables signature verification, `lark-notify` needs an explicit local secret source and matching ignore rule.
- Detailed notifications may approach the 20 KB custom bot request limit. The CLI must estimate payload size before sending and truncate predictably.
- MR matching remains heuristic. The skill should only skip fixes for strong coverage evidence; ambiguous matches stay `maybe_related`.
- Worktree creation can fail if the local repo has missing refs, uncommitted conflicts, or branch names that already exist. The skills need explicit fallback/error instructions.

## Goal

Add three installable skills that turn ARMS exception data into a complete agent workflow:

- `arms-exceptions-triage`: pull scoped ARMS exception evidence, deduplicate and classify it, dispatch deep diagnosis sub-agents, correlate with existing Yunxiao MRs, optionally dispatch fixes, and notify the team.
- `fix-arms-exception`: take one confirmed actionable ARMS bug from a triage diagnostic report, fix it with TDD in an isolated worktree, push a fix branch, and create a Yunxiao MR.
- `lark-notify`: provide a stable Feishu/Lark custom bot notification path for agents, including local webhook config, dry-run rendering, size checks, and text/card/raw sends.

The design prioritizes reliable agent execution over perfect automation. Triage and fix are workflow skills because the work needs judgment. Lark notification is a CLI because the mechanics are stable and testable.

## Non-Goals

- Do not implement a full triage CLI in v1.
- Do not implement a full fix automation CLI in v1.
- Do not create a new issue tracker workflow.
- Do not add application-robot Feishu APIs, tenant access tokens, chat discovery, message history, uploads, or interactive callback handling.
- Do not support convenience commands for image, share-chat, or rich-text post messages in `lark-notify` v1.
- Do not merge Yunxiao MRs automatically.
- Do not save credentials in committed project config.

## Project Structure

Add:

```text
skills/arms-exceptions-triage/
  SKILL.md

skills/fix-arms-exception/
  SKILL.md

skills/lark-notify/
  SKILL.md
  references/
    cli.md
  scripts/
    cli.py
    test_cli.py
```

Update:

```text
README.md
.gitignore
```

The source repository `.gitignore` should ignore local runtime artifacts that could be produced while developing or testing these skills:

```text
.arms-exceptions/triage/
.arms-exceptions/lark-notify.local.json
```

The skill docs must also instruct agents to add the same ignore entries in host projects when using triage or local webhook config.

## Skill: `arms-exceptions-triage`

### Trigger

Use this skill when a user asks an agent to triage, classify, deduplicate, investigate, summarize, or handle ARMS exceptions for one configured ARMS target or one service.

Trigger wording matters:

- "分诊", "triage", "看一下异常": triage only. Do not modify code.
- "分诊并修复", "处理这些异常", "跑完整 ARMS 异常处理": triage, then fix confirmed actionable bugs that are not covered by existing MRs.

### Input Resolution

The workflow accepts exactly one logical scope:

- `target`: process all services under that target.
- `service`: resolve the service through `targets --json`.

Rules:

- A service must map to exactly one target.
- The resolved target must have a configured `branch`.
- If the service is missing, maps to multiple targets, or the target branch is empty, stop with a clear error and a next command.
- Do not silently process all targets.
- Do not infer `main`, `master`, or `dev` when branch is not configured.

Required first commands in the host project:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor
python3 skills/arms-exceptions-explorer/scripts/cli.py targets --json
```

### Worktree

After resolving scope and branch, prefer an isolated worktree for diagnosis:

```text
.arms-exceptions/triage-worktrees/<run-id>/
```

or a repository-appropriate equivalent if the host project already has an agent worktree convention.

The skill should not require a fixed path, but it must record the chosen worktree path and branch in `source-manifest.md`.

### ARMS Sync And Evidence

Run a scoped sync:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --target <target> --json
```

or:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py sync --service <service> --json
```

Then collect groups:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py groups --target <target> --json
```

or:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py groups --service <service> --json
```

For each group that remains relevant after first-pass dedupe, use:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py show <group_id> --target <target> --json
```

or the service-scoped equivalent.

`group_id` is only an intra-run locator. It must not be used as durable MR coverage evidence.

### Triage Artifact Layout

Every run writes local artifacts under:

```text
.arms-exceptions/triage/<YYYYMMDDTHHMMSS>-<target-or-service>/
  summary.md
  source-manifest.md
  groups.json
  dedupe.json
  existing-mrs.json
  subagents/
    diagnose-<stable-slug>.md
    fix-<stable-slug>.md
```

`summary.md` is the human-facing report and Lark notification source.

`source-manifest.md` records original commands, target/service resolution, branch, worktree, sync/group/show commands, MR query commands, sub-agent prompts or report paths, verification evidence, decisions, and risks.

`groups.json` stores the raw `groups --json` output.

`dedupe.json` records the parent agent's second-pass dedupe decisions. It should include:

- original group ids for this run,
- stable fingerprint,
- merge reason,
- classification before diagnosis if any,
- selected representative group id for detail lookup.

`existing-mrs.json` stores MR search results and coverage decisions.

`subagents/` stores each deep diagnosis and fix result.

### Dedupe And Noise Filtering

The parent agent does first-pass grouping on top of local ARMS groups. It should compare:

- exception type,
- normalized core message,
- top business stack frame,
- service and operation,
- nearby stack frames,
- occurrence pattern,
- related logs when useful.

Noise examples:

- client clearly sent invalid parameters and service behaved correctly,
- third-party outage or upstream dependency returned invalid data outside this repository's control,
- bug is already fixed on the target branch but not yet released,
- duplicate of a stronger representative group in the same run.

The parent agent must preserve enough evidence in `dedupe.json` for a later agent to understand why groups were merged or dropped.

### Deep Diagnosis Sub-Agent

For each deduped candidate, the parent agent dispatches a medium-effort sub-agent. Concurrency is not fixed. The parent agent decides based on resource, conflict risk, exception count, and runner capabilities.

The parent agent should record scheduling choices and sub-agent status in `source-manifest.md`, but it does not need to enforce a numeric limit.

Each diagnostic report must use this template:

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

`status=bug` requires stable code-path evidence and a clear fix direction. If the sub-agent cannot establish that, it must use `needs_human` or `noise`.

### Existing MR Matching

After diagnosis, use `yunxiao-mr` to inspect existing MRs:

```bash
python3 skills/yunxiao-mr/scripts/cli.py doctor
python3 skills/yunxiao-mr/scripts/cli.py list --state opened --json
python3 skills/yunxiao-mr/scripts/cli.py list --state merged --json
```

The parent agent may also use `--search` when the CLI supports a useful query.

Coverage decisions:

- `covered`: opened or recently merged MR matches the same stable error fingerprint and same code path or root cause.
- `maybe_related`: only message, service, file name, or similar title matches. Do not skip fixing.
- `not_related`: no stable evidence.

Closed MRs do not count as solved unless comments clearly point to a replacement MR or released fix.

Strong evidence must not rely on `group_id`.

### Optional Fix Dispatch

Triage only by default. If the user's trigger explicitly requests fixing, dispatch `fix-arms-exception` for each:

- diagnostic status is `bug`,
- existing MR decision is not `covered`,
- the diagnostic report includes Source Manifest and suggested tests.

Each fix sub-agent result is stored in:

```text
.arms-exceptions/triage/<run-id>/subagents/fix-<stable-slug>.md
```

### Notification

At the end, call:

```bash
python3 skills/lark-notify/scripts/cli.py send \
  --title "ARMS 异常分诊: <target>" \
  --body-file .arms-exceptions/triage/<run-id>/summary.md \
  --format card
```

Notifications may include detailed exception content, but must not include credentials, tokens, Authorization headers, signed URLs, AccessKeys, or SecurityTokens.

## Skill: `fix-arms-exception`

### Trigger And Input

Use this skill when the user or triage workflow asks to fix one confirmed ARMS exception bug.

Required input is a diagnostic report path:

```bash
/fix-arms-exception .arms-exceptions/triage/<run-id>/subagents/diagnose-<stable-slug>.md
```

Rules:

- The report must have `status: bug`.
- The report must include Source Manifest, exception fingerprint, root cause, suggested fix scope, and suggested tests.
- A bare `group_id`, stack snippet, or oral summary is insufficient. Ask to generate or complete the diagnostic report first.

### Worktree And Branch

Create an isolated worktree on the target branch from the diagnostic report:

```text
fix/arms-YYYYMMDD-{title}
```

The branch slug should be short, stable, and derived from the exception type or root cause.

Rules:

- Only auto-push branches created by this workflow and prefixed `fix/arms-`.
- Do not modify the user's current working tree.
- If the target branch cannot be checked out, stop with a concrete error and next command.
- If the branch already exists, inspect it before deciding whether to continue or create a suffixed branch.

### TDD Repair

Follow TDD:

1. Reproduce the bug or create a failing regression test that captures the diagnosed root cause.
2. Implement the smallest fix consistent with the repository patterns.
3. Run the focused test.
4. Run broader relevant tests when the change touches shared logic.

The workflow must preserve:

- failing test or reproduction evidence,
- fix summary,
- verification commands and results,
- any untested risk and why it remains.

### MR Creation

After tests pass:

1. Commit the fix.
2. Push the created `fix/arms-...` branch.
3. Create a Yunxiao MR with `yunxiao-mr`.

MR body template:

```markdown
## 问题

## 归因分析

## 解决方案

## 验证

## 风险和回滚

## ARMS 证据

## Source Manifest

### Sources

### Produced artifacts

### Key decisions

### Verification evidence

### Open questions / risks
```

Rules:

- Do not paste huge raw span/log bodies into the MR.
- Link or reference the local diagnostic report and commands used to fetch evidence.
- Include MR `localId` and detail URL in the final fix summary.
- Do not merge automatically.

## Skill: `lark-notify`

### Purpose

Provide a minimal, reliable Feishu/Lark custom bot sender for agents. The CLI handles webhook discovery, payload construction, dry runs, request-size checks, truncation, sending, and sanitized output.

### Config

Webhook source priority:

1. `.arms-exceptions/lark-notify.local.json`
2. `ARMS_LARK_WEBHOOK_URL`

Config file:

```json
{
  "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/..."
}
```

The config file is local-only and must be ignored by Git.

No other config is required in v1.

### Commands

```bash
python3 skills/lark-notify/scripts/cli.py config --webhook-url <url>
python3 skills/lark-notify/scripts/cli.py config --show
python3 skills/lark-notify/scripts/cli.py send --title "..." --body-file /tmp/summary.md --format text
python3 skills/lark-notify/scripts/cli.py send --title "..." --body-file /tmp/summary.md --format card
python3 skills/lark-notify/scripts/cli.py send --json-file /tmp/payload.json --format raw
python3 skills/lark-notify/scripts/cli.py send --title "..." --body-file /tmp/summary.md --format card --dry-run
```

Options:

- `--config <path>` for tests or unusual projects.
- `--format text|card|raw`.
- `--dry-run` renders, validates, and prints sanitized metadata without sending.
- `--json` prints machine-readable command results.

### Message Formats

`text` sends:

```json
{
  "msg_type": "text",
  "content": {
    "text": "<title>\n\n<body>"
  }
}
```

`card` sends an `interactive` payload with:

- header title,
- markdown body,
- optional note if the body was truncated,
- no callback interactions.

`raw` sends the JSON payload exactly as supplied after validation and optional webhook signature fields if future signature support is added.

### Size And Truncation

Feishu custom bot request body must stay under 20 KB. The CLI should:

- serialize the final payload before sending,
- measure UTF-8 bytes,
- if too large, truncate body content and add a note that output was truncated,
- preserve title and local report path when available,
- fail if even the minimal payload cannot fit.

### Security

Rules:

- `config --show` prints only source and a masked webhook.
- Errors must not print full webhook URLs.
- The CLI must redact common credential patterns from generated notification text where feasible.
- Never print Authorization headers, AccessKeys, SecurityTokens, signatures, OAuth codes, or full webhook URLs.

### HTTP Behavior

Use Python standard library only:

- `urllib.request` for POST.
- `json` for payloads.
- stable exit codes: `0` success, `1` user-fixable error or webhook failure, `2` argument error, `130` interrupted.

When the webhook returns JSON, parse it. Treat code `0` or documented success shape as success; otherwise print a concise failure and next step.

## README Updates

Add a short section for the three new skills:

- install examples,
- what each skill does,
- how they compose,
- `lark-notify` config examples,
- testing commands.

Keep detailed workflow content in each `SKILL.md`, not in the README.

## Testing

Add `lark-notify` unit tests:

- config writes `.arms-exceptions/lark-notify.local.json`;
- config ensures `.gitignore` ignores the local file;
- `config --show` masks webhook;
- env var fallback works;
- local config has priority over env var;
- text payload shape is correct;
- card payload shape is correct;
- raw payload validates JSON object shape;
- dry-run does not call network;
- oversize payload truncates;
- full webhook is not printed in stdout/stderr;
- common credential-like text is redacted from notification body where implemented.

Existing test commands remain:

```bash
python3 -m unittest discover -s skills/arms-exceptions-explorer/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/yunxiao-mr/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/lark-notify/scripts -p 'test_*.py'
```

Smoke tests:

```bash
python3 skills/lark-notify/scripts/cli.py config --show
python3 skills/lark-notify/scripts/cli.py send --title "测试通知" --body-file /tmp/summary.md --format text --dry-run
python3 skills/lark-notify/scripts/cli.py send --title "测试通知" --body-file /tmp/summary.md --format card --dry-run
```

Real webhook sending should only run when the user has configured the webhook and explicitly allows a live notification.

## Error Handling

All skills should prefer specific next steps.

Triage examples:

- Missing ARMS config: run `arms-exceptions-explorer init`.
- Missing target branch: update `.arms-exceptions/config.json` with target branch.
- Ambiguous service: rerun with `--target`.
- MR coverage uncertain: mark `maybe_related`, do not skip fixing if full workflow was requested.

Fix examples:

- Diagnostic report is missing or not `status=bug`: stop and ask for a valid diagnostic report.
- Worktree creation fails: report exact branch/path problem.
- Tests fail after fix attempt: leave summary and do not create MR.
- Push fails: report command and branch, do not create MR.

Lark examples:

- No webhook configured: run `config --webhook-url <url>` or set `ARMS_LARK_WEBHOOK_URL`.
- Webhook rejected request: print response code/message without full URL.
- Payload too large after truncation: write local summary path and fail with next step.

## Implementation Order

1. Add `lark-notify` CLI and tests.
2. Add `lark-notify` `SKILL.md` and `references/cli.md`.
3. Add `arms-exceptions-triage/SKILL.md`.
4. Add `fix-arms-exception/SKILL.md`.
5. Update README and `.gitignore`.
6. Run unittest for all three skill script directories and `git diff --check`.

This order makes the mechanical notification path testable before the orchestration skills depend on it.

## Acceptance Criteria

- A host project can install and read all three skill entrypoints.
- `lark-notify` can configure a local webhook file, show masked config, dry-run text/card notifications, and avoid printing the full webhook.
- Triage documentation gives an agent enough instructions to resolve target/service scope, switch to the configured branch in a worktree, sync ARMS data, dedupe groups, dispatch diagnosis, compare MRs, optionally fix, write `.arms-exceptions/triage/<run-id>/` artifacts, and notify Lark.
- Fix documentation gives an agent enough instructions to start from a `status=bug` diagnostic report, create an isolated `fix/arms-...` branch, repair with TDD, push, create a Yunxiao MR, and summarize the MR.
- README mentions all three skills without duplicating long workflow documentation.
- Tests pass:

```bash
python3 -m unittest discover -s skills/arms-exceptions-explorer/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/yunxiao-mr/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/lark-notify/scripts -p 'test_*.py'
git diff --check
```
