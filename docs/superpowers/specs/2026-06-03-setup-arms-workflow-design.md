# Setup ARMS Workflow Skill Design

## Source Manifest

### Sources

- User request in this Codex thread: add a `setup-arms-workflow` skill that configures this repository's ARMS workflow in a host project.
- User decision: use `/grill-me` alignment before implementation.
- User decision: first version is an orchestration skill, not a new setup CLI.
- User decision: setup report lives under `.arms-exceptions/setup/` and must be ignored.
- User decision: ARMS app and SLS choices must be confirmed by the user.
- User decision: current gap is missing SLS discovery commands similar to `apps`.
- User decision: add small `arms-exceptions-explorer` CLI commands for SLS discovery.
- User decision: setup should not run end-to-end smoke tests; user will test.
- User decision: Yunxiao setup runs doctor and guides `YUNXIAO_ACCESS_TOKEN` configuration, but does not create MR or labels.
- User decision: Lark setup may write `.arms-exceptions/lark-notify.local.json`, but does not send a real notification.
- User decision: setup should not edit host `AGENTS.md` or `CLAUDE.md`; it should only include suggested snippets in the local report.
- Existing project rules: `AGENTS.md`.
- Workflow policy: `~/.agents/docs/agents/workflows.md`.
- Handoff policy: `~/.agents/docs/agents/handoff-policy.md`.
- Existing ARMS explorer skill and CLI: `skills/arms-exceptions-explorer/SKILL.md`, `skills/arms-exceptions-explorer/references/cli.md`, `skills/arms-exceptions-explorer/scripts/arms_exceptions/app.py`.
- Existing Yunxiao MR skill and CLI: `skills/yunxiao-mr/SKILL.md`, `skills/yunxiao-mr/references/cli.md`, `skills/yunxiao-mr/scripts/cli.py`.
- Existing Lark notify skill and CLI: `skills/lark-notify/SKILL.md`, `skills/lark-notify/references/cli.md`, `skills/lark-notify/scripts/cli.py`.
- Existing triage/fix workflow design: `docs/superpowers/specs/2026-06-03-arms-triage-fix-lark-notify-design.md`.

### Produced artifacts

- `docs/superpowers/specs/2026-06-03-setup-arms-workflow-design.md`

### Key decisions

- Add `setup-arms-workflow` as an orchestration-only skill. It coordinates existing CLIs instead of duplicating their logic.
- Add small SLS discovery commands to `arms-exceptions-explorer`: `sls projects` and `sls logstores`.
- Keep all setup reports local under `.arms-exceptions/setup/`.
- Keep user confirmation at the ARMS app and SLS selection points.
- Do not run real ARMS sync, create Yunxiao MRs/labels, or send real Lark notifications during setup.
- Do not modify host agent instruction files automatically.

### Verification evidence

- Inspected existing `arms-exceptions-explorer` command surface and confirmed `doctor`, `apps --json`, `init`, and `targets --json` exist.
- Inspected existing ARMS implementation and confirmed it already has `AliyunCliClient.list_sls_projects()` and `list_sls_logstores()`.
- Inspected existing `yunxiao-mr` command surface and confirmed `doctor --json --skip-api` and `doctor --json` exist.
- Inspected existing `lark-notify` command surface and confirmed `config --webhook-url`, `config --show --json`, and `send --dry-run` exist.
- No implementation changes for setup or SLS commands have been made in this spec step.

### Open questions / risks

- `apps --json` and new SLS discovery commands depend on the user's current Alibaba Cloud CLI identity and permissions.
- `yunxiao-mr doctor --json --skip-api` can fail when the host repo remote is not Codeup; setup should record this without blocking ARMS/Lark configuration.
- Lark Webhook is local-only. CI environments still need their own local file or environment injection.
- The setup skill is intentionally not a full wizard CLI; if repeated runs reveal stable automation patterns, a future CLI can be added.

## Goal

Add a `setup-arms-workflow` skill that prepares a host repository to use:

- `arms-exceptions-explorer`
- `arms-exceptions-triage`
- `fix-arms-exception`
- `yunxiao-mr`
- `lark-notify`

The skill should help an Agent check dependencies, discover ARMS apps and SLS logstores, ask the user for configuration choices, run the existing init/config commands, and leave a local setup report for later CI or Agent runs.

## Non-Goals

- Do not add a full setup CLI.
- Do not auto-select ARMS apps or SLS logstores.
- Do not run ARMS sync as setup verification.
- Do not create Yunxiao MRs or labels.
- Do not send real Lark notifications.
- Do not edit host `AGENTS.md`, `CLAUDE.md`, or other agent instruction files.
- Do not save cloud credentials, tokens, AccessKeys, profile names, Authorization headers, or signed URLs.

## Project Structure

Add:

```text
skills/setup-arms-workflow/
  SKILL.md
  references/
    workflow.md
```

Modify:

```text
skills/arms-exceptions-explorer/scripts/arms_exceptions/app.py
skills/arms-exceptions-explorer/scripts/test_*.py
skills/arms-exceptions-explorer/SKILL.md
skills/arms-exceptions-explorer/references/cli.md
README.md
AGENTS.md
.gitignore
```

## SLS Discovery Commands

Add a new `sls` command group to `arms-exceptions-explorer`:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py sls projects --json
python3 skills/arms-exceptions-explorer/scripts/cli.py sls logstores --project <project> --endpoint <endpoint> --json
```

Behavior:

- `sls projects` lists accessible SLS projects using current `aliyun` CLI credentials.
- `sls logstores` lists logstores for one project and endpoint.
- Commands are read-only.
- Commands support human-readable output and `--json`.
- Failures include a direct next step, such as checking `aliyun configure get` or passing the correct endpoint.

JSON output:

```json
{
  "projects": [
    {
      "project": "example-project",
      "region": "cn-beijing"
    }
  ]
}
```

```json
{
  "project": "example-project",
  "endpoint": "cn-beijing.log.aliyuncs.com",
  "logstores": ["app-log", "worker-log"]
}
```

Implementation should reuse existing `AliyunCliClient.list_sls_projects()` and `list_sls_logstores()`.

## Setup Skill Workflow

### 1. Start Report

Create:

```text
.arms-exceptions/setup/
  setup-report.md
  source-manifest.md
  arms-doctor.json
  arms-apps.json
  sls-projects.json
  sls-logstores-<project>.json
  targets.json
  yunxiao-doctor-skip-api.json
  yunxiao-doctor.json
  lark-config.json
```

Update generated ignore rules to include:

```text
setup/
```

The setup report should explain current readiness and missing actions. The Source Manifest records every command run and every user decision.

### 2. ARMS Dependency Check

Run:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py doctor --json
```

If `aliyun` is missing or unauthenticated, give the official next step:

```bash
aliyun configure get
aliyun configure --mode OAuth
```

Do not request or print credentials.

### 3. Discover ARMS Apps

Run:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py apps --region <region> --search <keyword> --json
```

Ask the user to confirm:

- target name;
- target branch;
- selected app/service names;
- whether multiple apps belong to one target.

Do not auto-select from fuzzy names.

### 4. Discover SLS

Run:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py sls projects --json
python3 skills/arms-exceptions-explorer/scripts/cli.py sls logstores --project <project> --endpoint <endpoint> --json
```

Also use the ARMS explorer's existing init behavior that can read ARMS-associated SLS config when available.

Ask the user to confirm:

- whether to use ARMS-associated SLS config;
- or which project/logstore/endpoint to use;
- or whether to skip SLS for a service.

SLS is optional. Missing SLS should not block target configuration.

### 5. Initialize ARMS Config

Run `init` using confirmed values:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py init \
  --target <target> \
  --branch <branch> \
  --service <service> \
  --window <window>
```

When SLS is confirmed:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py init \
  --target <target> \
  --branch <branch> \
  --service <service> \
  --sls-project <project> \
  --sls-logstore <logstore> \
  --sls-endpoint <endpoint>
```

Then run:

```bash
python3 skills/arms-exceptions-explorer/scripts/cli.py targets --json
```

Save output to `.arms-exceptions/setup/targets.json`.

### 6. Initialize Yunxiao

Run:

```bash
python3 skills/yunxiao-mr/scripts/cli.py doctor --json --skip-api
```

If `YUNXIAO_ACCESS_TOKEN` is missing, guide:

```bash
export YUNXIAO_ACCESS_TOKEN=<personal_access_token>
```

If the token exists, run:

```bash
python3 skills/yunxiao-mr/scripts/cli.py doctor --json
```

Do not create MR, label, comment, or merge anything.

### 7. Initialize Lark

If user provides a Webhook, run:

```bash
python3 skills/lark-notify/scripts/cli.py config --webhook-url <webhook>
```

Then run:

```bash
python3 skills/lark-notify/scripts/cli.py config --show --json
```

Do not send a real notification. Do not print the full Webhook.

### 8. Report

`setup-report.md` should include:

- ARMS readiness;
- configured targets/services/branches;
- SLS configuration status;
- Yunxiao readiness and token guidance;
- Lark readiness;
- skipped or failed steps;
- suggested host `AGENTS.md` snippet, without applying it.

Suggested snippet should mention:

- use `arms-exceptions-triage` for CI exception triage;
- target/service must be explicit;
- worktrees live in `.arms-exceptions/worktrees/`;
- setup report path.

## Error Handling

- If one subsystem fails, continue the others when safe.
- Missing `aliyun` blocks ARMS setup but not Lark setup.
- Non-Codeup remote blocks Yunxiao setup but not ARMS/Lark setup.
- Missing `YUNXIAO_ACCESS_TOKEN` records Yunxiao as partially configured and gives the export command.
- Missing Lark Webhook records Lark as not configured but does not block ARMS/Yunxiao.
- Ambiguous app/SLS choices require user confirmation.

## Testing

Add tests for:

- `sls projects --json` output shape.
- `sls logstores --project --endpoint --json` output shape.
- human-readable `sls` output.
- error handling for missing project/endpoint.
- `.arms-exceptions/.gitignore` template includes `setup/`.

Run:

```bash
python3 -m unittest discover -s skills/arms-exceptions-explorer/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/yunxiao-mr/scripts -p 'test_*.py'
python3 -m unittest discover -s skills/lark-notify/scripts -p 'test_*.py'
git diff --check
```

## Acceptance Criteria

- `setup-arms-workflow` exists and gives an Agent an executable setup flow.
- `arms-exceptions-explorer sls projects --json` and `sls logstores --project --endpoint --json` work in tests.
- Setup report path and Source Manifest requirements are documented.
- Setup does not create MRs, labels, real notifications, or run ARMS sync.
- README and AGENTS mention the new setup skill.
- Generated `.arms-exceptions/.gitignore` ignores setup, triage, worktrees, local Lark Webhook, and local data.
