# Yunxiao MR Skill Design

## Source Manifest

### Sources

- User request in this Codex thread: create a Yunxiao MR agent skill in `/Users/ivan/workspace/ai/arms-exceptions`, covering create, update, label, create label, view, list, and related MR workflow commands.
- User decision: use REST/OAPI with `YUNXIAO_ACCESS_TOKEN`, not Alibaba Cloud CLI credentials.
- User decision: CLI should be single-purpose and invoked as `python3 skills/yunxiao-mr/scripts/cli.py <command>`, without `pr` or `mr` command grouping.
- User decision: default repository context should be inferred from the current Git remote and cached.
- User decision: configuration cache lives at `.arms-exceptions/yunxiao.json`.
- User decision: missing labels should not be auto-created by default; `--create-missing-label` is required.
- User-provided actual acceptance repository: `git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git`.
- Existing project pattern: `README.md` and `skills/arms-exceptions-explorer/SKILL.md` use a skill plus optional `references/` and `scripts/cli.py` structure.
- Workflow policy: `~/.agents/docs/agents/workflows.md`.
- Handoff policy: `~/.agents/docs/agents/handoff-policy.md`.
- Yunxiao create MR API: https://help.aliyun.com/zh/yunxiao/developer-reference/api-devops-2021-06-25-createmergerequest/
- Yunxiao update MR API: https://help.aliyun.com/zh/yunxiao/developer-reference/api-devops-2021-06-25-updatemergerequest/
- Yunxiao list MR API: https://help.aliyun.com/zh/yunxiao/developer-reference/api-devops-2021-06-25-listmergerequests/
- Yunxiao link MR label API: https://help.aliyun.com/zh/yunxiao/developer-reference/api-devops-2021-06-25-linkmergerequestlabel/
- Yunxiao list project labels API: https://help.aliyun.com/zh/yunxiao/developer-reference/api-devops-2021-06-25-listprojectlabels/
- Yunxiao merge MR API: https://help.aliyun.com/zh/yunxiao/developer-reference/api-devops-2021-06-25-mergemergerequest/
- Yunxiao create change request comment API: https://help.aliyun.com/zh/yunxiao/developer-reference/createchangerequestcomment

### Produced artifacts

- `docs/superpowers/specs/2026-06-03-yunxiao-mr-skill-design.md`

### Key decisions

- Build a thin Python REST CLI and agent-facing skill documentation instead of relying on `aliyun devops` or asking agents to assemble curl commands.
- Keep credentials out of repo files. `YUNXIAO_ACCESS_TOKEN` is the only supported credential source in v1.
- Cache only non-secret repository context in `.arms-exceptions/yunxiao.json`.
- Align command names and options with `gh pr` where useful, but keep the CLI single-purpose.
- Treat label association carefully: adding or removing labels must read the existing MR labels and rewrite the full desired label list because Yunxiao's link label API is overwrite-style.
- Include one real Codeup acceptance path using `git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git`.

### Verification evidence

- Current repository structure was inspected with `find . -maxdepth 3 -type f`.
- Existing ARMS skill entrypoint and security model were inspected in `README.md` and `skills/arms-exceptions-explorer/SKILL.md`.
- Yunxiao OpenAPI metadata was queried for MR and label operations, confirming create, update, list, get, close, reopen, merge, project label create/list/update/delete, MR label link/list, and MR comment list coverage.
- No implementation or live Yunxiao mutation has been performed at design time.

### Open questions / risks

- Some APIs use `repositoryId` path parameters while label APIs use `repositoryIdentity` query parameters. The CLI must normalize this and cache numeric `repository_id` only if a specific endpoint rejects the encoded repository path.
- Comment creation appears in the newer ChangeRequest OAPI. Implementation must verify the exact path and response shape before exposing `comment` as stable.
- Actual acceptance mutates the provided test repository; it must require a real `YUNXIAO_ACCESS_TOKEN` with Codeup permissions and should clean up or clearly identify test MRs and labels.

## Goal

Create a new `yunxiao-mr` agent skill for Yunxiao Codeup merge requests. The skill should give agents a stable, executable path for creating, listing, viewing, updating, labeling, commenting, closing, reopening, and merging MR records without requiring agents to re-derive Yunxiao API details each time.

The first version optimizes for agent reliability and low setup cost:

- Infer repository context from the current Git remote.
- Cache inferred non-secret context in `.arms-exceptions/yunxiao.json`.
- Read credentials only from `YUNXIAO_ACCESS_TOKEN`.
- Provide one Python CLI entrypoint with `gh pr`-like command behavior.
- Keep documentation concise in `SKILL.md` and move full command/API detail into references.

## Non-Goals

- Do not implement full Yunxiao work item management.
- Do not implement Flow pipeline management.
- Do not implement automatic code review or approval workflows.
- Do not automatically push branches or automatically merge after creating an MR.
- Do not save tokens, AccessKeys, profile names, Authorization headers, or signed URLs.
- Do not depend on non-standard Python packages in v1.

## Project Structure

Add a sibling skill next to the existing ARMS skill:

```text
skills/yunxiao-mr/
  SKILL.md
  references/
    cli.md
    api.md
  scripts/
    cli.py
    test_*.py
```

`SKILL.md` is the agent entrypoint. It should cover trigger conditions, safety rules, the required `doctor` first step, and the common MR workflow.

`references/cli.md` contains full command examples, arguments, JSON output notes, and troubleshooting.

`references/api.md` records the Yunxiao API assumptions and endpoint-specific quirks, especially mixed `repositoryId` versus `repositoryIdentity` usage and overwrite-style label linking.

`scripts/cli.py` is the only executable entrypoint. It owns Git context discovery, config cache handling, HTTP calls, output formatting, and command dispatch.

## CLI Commands

The CLI is single-purpose. It does not add `pr` or `mr` subcommand grouping:

```bash
python3 skills/yunxiao-mr/scripts/cli.py doctor
python3 skills/yunxiao-mr/scripts/cli.py create
python3 skills/yunxiao-mr/scripts/cli.py list
python3 skills/yunxiao-mr/scripts/cli.py view <localId>
python3 skills/yunxiao-mr/scripts/cli.py edit <localId>
python3 skills/yunxiao-mr/scripts/cli.py label list
python3 skills/yunxiao-mr/scripts/cli.py label create <name>
python3 skills/yunxiao-mr/scripts/cli.py label add <localId> <name>
python3 skills/yunxiao-mr/scripts/cli.py label remove <localId> <name>
python3 skills/yunxiao-mr/scripts/cli.py comment <localId>
python3 skills/yunxiao-mr/scripts/cli.py close <localId>
python3 skills/yunxiao-mr/scripts/cli.py reopen <localId>
python3 skills/yunxiao-mr/scripts/cli.py merge <localId>
```

Common options:

- `--json`: output machine-readable JSON.
- `--debug`: output sanitized request path and response summary.
- `--remote <name>`: override the default `origin` remote.
- `--config <path>`: override `.arms-exceptions/yunxiao.json` for tests or unusual repos.

## Repository Context And Config

The config path is:

```text
.arms-exceptions/yunxiao.json
```

This file is a cache and override file. It must not contain credentials.

On the first command that requires repository context, the CLI reads `git remote get-url origin` and infers Codeup context. For example:

```text
git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git
```

is parsed as:

```json
{
  "version": 1,
  "domain": "codeup.aliyun.com",
  "organization_id": "685a564391483e233edca392",
  "repository_path": "685a564391483e233edca392/sharge-web/test",
  "repository_identity": "685a564391483e233edca392%2Fsharge-web%2Ftest",
  "default_remote": "origin",
  "default_target_branch": "main"
}
```

Default base branch inference:

1. `origin/HEAD`.
2. `main`.
3. `master`.
4. Fail with a clear message requiring `--base` or a manual config edit.

If an API requires a numeric repository ID, the CLI should resolve it through a repository query endpoint and cache it as:

```json
{
  "repository_id": 123456
}
```

Manual config edits are allowed for custom domains, unusual remote layouts, non-default branches, and cached repository IDs.

## Authentication

The only supported credential source is:

```bash
YUNXIAO_ACCESS_TOKEN
```

Rules:

- `doctor` checks whether the variable exists but never prints its value.
- Commands never accept token values as CLI arguments.
- Token values are never written to `.arms-exceptions/yunxiao.json`.
- Debug output must redact tokens, Authorization headers, AccessKeys, SecurityTokens, signatures, and signed URLs.

## Command Behavior

### `doctor`

Checks:

- Python version is usable.
- Current directory is inside a Git repository.
- The configured remote exists.
- The remote is parseable as Codeup SSH or HTTPS.
- `.arms-exceptions/yunxiao.json` can be read or generated.
- `YUNXIAO_ACCESS_TOKEN` exists.
- A lightweight Yunxiao API call succeeds unless `--skip-api` is passed.

Expected failure messages must include the next command or config field needed to continue.

### `create`

Example:

```bash
python3 skills/yunxiao-mr/scripts/cli.py create \
  --title "修复异常聚合" \
  --body-file /tmp/mr.md \
  --label HAT-Ready \
  --create-missing-label
```

Defaults:

- `--head`: current Git branch.
- `--base`: `default_target_branch` from `.arms-exceptions/yunxiao.json`.
- Description: empty unless `--body` or `--body-file` is provided.

Before creating the MR, the CLI checks whether the head branch exists on the configured remote. If not, it fails with:

```bash
git push -u origin <branch>
```

Supported options:

- `--title <text>`: required.
- `--body <text>` or `--body-file <path>`: optional and mutually exclusive.
- `--base <branch>`: override target branch.
- `--head <branch>`: override source branch.
- `--reviewer <id>`: repeatable.
- `--work-item-ids <csv>`: pass-through for Yunxiao work item linkage.
- `--label <name>`: repeatable.
- `--create-missing-label`: create missing project labels before associating them.
- `--json`: print JSON.

Success output includes `localId`, `webUrl`, source branch, target branch, and status.

### `list`

Defaults to open MRs.

Supported options:

- `--state opened|merged|closed|all`.
- `--author <id>`.
- `--reviewer <id>`.
- `--search <text>`.
- `--label <name>`.
- `--limit <n>`.
- `--json`.

Text output should be compact and familiar to agents used to `gh pr list`:

```text
localId  title                         source -> target   status   webUrl
12       修复异常聚合                   fix/x -> main      opened   https://...
```

### `view <localId>`

Shows:

- title
- state/status
- author
- reviewers if present
- source and target branches
- labels
- web URL
- description summary

Options:

- `--comments`: include MR comments.
- `--json`: output normalized JSON.

### `edit <localId>`

Updates only explicitly provided fields:

- `--title <text>`
- `--body <text>`
- `--body-file <path>`
- `--base <branch>`

### `label list`

Lists project labels.

Options:

- `--search <text>`
- `--limit <n>`
- `--json`

### `label create <name>`

Creates a project label.

Options:

- `--color <hex>`
- `--description <text>`
- `--json`

### `label add <localId> <name>`

Algorithm:

1. List project labels and find the requested label by exact name.
2. If missing and `--create-missing-label` is present, create it.
3. If missing and `--create-missing-label` is absent, fail and suggest `label create` or `--create-missing-label`.
4. List current MR labels.
5. Build the union of current label IDs and requested label ID.
6. Call `LinkMergeRequestLabel` with the full desired ID list.

This command is idempotent.

### `label remove <localId> <name>`

Algorithm:

1. List current MR labels.
2. If the requested label is not present, print a no-op success.
3. Build the current label ID list minus the requested label.
4. Call `LinkMergeRequestLabel` with the full desired ID list.

This command exists because Yunxiao label linking is overwrite-style; it should not rely on a nonexistent unlink endpoint.

### `comment <localId>`

Creates a comment on the MR.

Options:

- `--body <text>`
- `--body-file <path>`
- `--json`

Implementation must verify the newer ChangeRequest comment OAPI path and response shape. If the endpoint is unavailable for the configured domain, the command should fail with a clear message and the MR web URL.

### `close <localId>` and `reopen <localId>`

Call the corresponding Yunxiao APIs and print the resulting state and web URL.

### `merge <localId>`

Requires an explicit command; nothing auto-merges after `create`.

Options:

- `--method no-fast-forward|squash|rebase|ff-only`.
- `--delete-branch`.
- `--json`.

Before merging, `merge` calls `view` or `GetMergeRequest` and checks conflict or requirement fields when present. If the API indicates conflict or failed requirements, the command fails before calling merge.

## Internal Design

Keep v1 in one Python file for portability, but preserve clear units:

```text
argparse command handlers
  -> YunxiaoContext
  -> YunxiaoClient
  -> output formatters
```

`YunxiaoContext` responsibilities:

- Read and write `.arms-exceptions/yunxiao.json`.
- Parse Codeup SSH and HTTPS remotes.
- Infer current branch and default base branch.
- Check whether a branch exists on the remote.
- Provide repository identity fields to commands.

`YunxiaoClient` responsibilities:

- Build URLs and query/body payloads.
- Read `YUNXIAO_ACCESS_TOKEN` from the environment.
- Execute HTTP requests with standard library APIs.
- Parse JSON responses and normalize common errors.
- Redact secrets in debug output.

Command handlers should be thin: validate arguments, call context/client methods, and format results.

## Error Handling

Required behavior:

- Missing token: say `YUNXIAO_ACCESS_TOKEN` is required.
- Non-Codeup remote: show the current remote and the expected SSH/HTTPS shapes.
- Remote parse failure: suggest manual `.arms-exceptions/yunxiao.json` fields.
- 401/403: say token or Codeup permission is invalid.
- 404: suggest checking `organization_id`, `repository_identity`, and `domain`.
- Missing label: suggest `label create` or `--create-missing-label`.
- Branch not pushed: suggest `git push -u origin <branch>`.
- Unexpected response shape: show a concise error; only `--debug` shows sanitized details.

The CLI should never print raw token-bearing request URLs.

## Tests

Use `unittest` and Python standard library only.

Unit tests:

- SSH Codeup remote parsing.
- HTTPS Codeup remote parsing.
- repository path URL encoding.
- first-run config write to `.arms-exceptions/yunxiao.json`.
- manual config override preservation.
- default base inference.
- branch push check behavior.
- `create` args to API body conversion.
- `list` filter conversion.
- `label add` reads existing labels and rewrites the full desired label list.
- `label remove` rewrites the full desired label list.
- token redaction in error/debug paths.
- missing token and invalid remote errors.

Local smoke tests:

```bash
python3 skills/yunxiao-mr/scripts/cli.py --help
python3 skills/yunxiao-mr/scripts/cli.py doctor --skip-api
python3 -m unittest discover -s skills/yunxiao-mr/scripts -p 'test_*.py'
```

Actual Yunxiao acceptance test:

```bash
tmpdir="$(mktemp -d)"
git clone git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git "$tmpdir/test"
cd "$tmpdir/test"
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/yunxiao-mr/scripts/cli.py doctor
```

Then, using a throwaway branch:

```bash
branch="codex-yunxiao-mr-smoke-$(date +%Y%m%d%H%M%S)"
git checkout -b "$branch"
printf "codex smoke %s\n" "$branch" > codex-yunxiao-mr-smoke.txt
git add codex-yunxiao-mr-smoke.txt
git commit -m "Codex Yunxiao MR smoke"
git push -u origin "$branch"
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/yunxiao-mr/scripts/cli.py create \
  --title "Codex Yunxiao MR smoke $branch" \
  --body "Automated acceptance test for yunxiao-mr skill." \
  --label codex-smoke \
  --create-missing-label
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/yunxiao-mr/scripts/cli.py list --search "$branch"
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/yunxiao-mr/scripts/cli.py view <localId> --comments
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/yunxiao-mr/scripts/cli.py label remove <localId> codex-smoke
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/yunxiao-mr/scripts/cli.py comment <localId> --body "Smoke test comment."
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/yunxiao-mr/scripts/cli.py close <localId>
python3 /Users/ivan/workspace/ai/arms-exceptions/skills/yunxiao-mr/scripts/cli.py reopen <localId>
```

Do not run `merge` in the default acceptance test unless the user explicitly approves merging the smoke branch. If merge is approved, use `--method squash --delete-branch` against the test repository only.

## Implementation Phases

1. Add `SKILL.md`, references, and CLI scaffold with `doctor --skip-api`.
2. Implement Git remote parsing and `.arms-exceptions/yunxiao.json` cache behavior with tests.
3. Implement `YunxiaoClient` and read-only commands: `doctor`, `list`, `view`, `label list`.
4. Implement mutating MR commands: `create`, `edit`, `close`, `reopen`.
5. Implement label commands with overwrite-safe add/remove behavior.
6. Implement `comment` after verifying the ChangeRequest comment API path.
7. Implement `merge` with pre-merge status checks.
8. Run local tests and the actual acceptance test against the provided test repository when credentials are available.

## Success Criteria

- A new agent can read `skills/yunxiao-mr/SKILL.md` and know the safe MR workflow without reading the whole implementation.
- `doctor --skip-api` works without credentials and validates local Git context.
- With `YUNXIAO_ACCESS_TOKEN`, `doctor` validates Codeup API access.
- On a Codeup repo, first run writes `.arms-exceptions/yunxiao.json` from the Git remote.
- `create` can open an MR from a pushed branch and print `localId` plus `webUrl`.
- `label add` and `label remove` preserve unrelated existing labels.
- No command prints or stores the Yunxiao token.
- Local unit tests pass.
- The actual acceptance repository can be used to create and inspect a throwaway MR without merging by default.
