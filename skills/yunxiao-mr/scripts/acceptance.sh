#!/usr/bin/env bash
set -euo pipefail

TEST_REPO_URL="git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git"
CLI_PATH="/Users/ivan/workspace/ai/arms-exceptions/skills/yunxiao-mr/scripts/cli.py"
CREATE_SMOKE_MR=0

usage() {
  cat <<'USAGE'
Usage: skills/yunxiao-mr/scripts/acceptance.sh [--create-smoke-mr]

Runs the real Yunxiao MR acceptance path against:
  git@codeup.aliyun.com:685a564391483e233edca392/sharge-web/test.git

Default mode clones the repo and runs doctor only.
--create-smoke-mr creates a throwaway branch and label, opens a smoke MR,
labels it, comments on it, closes it, reopens it, then removes the throwaway
label and branch. It does not merge.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --create-smoke-mr)
      CREATE_SMOKE_MR=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "${YUNXIAO_ACCESS_TOKEN:-}" ]; then
  echo "YUNXIAO_ACCESS_TOKEN is required." >&2
  exit 1
fi

tmpdir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT

git clone "$TEST_REPO_URL" "$tmpdir/test"
cd "$tmpdir/test"

python3 "$CLI_PATH" doctor

if [ "$CREATE_SMOKE_MR" -eq 0 ]; then
  exit 0
fi

git config user.email "codex@example.com"
git config user.name "Codex"

stamp="$(date +%Y%m%d%H%M%S)"
branch="codex-yunxiao-mr-smoke-$stamp"
label="codex-smoke-$stamp"
git checkout -b "$branch"
printf "codex smoke %s\n" "$branch" > codex-yunxiao-mr-smoke.txt
git add codex-yunxiao-mr-smoke.txt
git commit -m "Codex Yunxiao MR smoke"
git push -u origin "$branch"

create_json="$(python3 "$CLI_PATH" create \
  --title "Codex Yunxiao MR smoke $branch" \
  --body "Automated acceptance test for yunxiao-mr skill." \
  --label "$label" \
  --create-missing-label \
  --json)"

local_id="$(printf '%s\n' "$create_json" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("localId") or data["merge_request"]["localId"])')"

python3 "$CLI_PATH" list --search "$branch"
python3 "$CLI_PATH" view "$local_id" --comments
python3 "$CLI_PATH" label remove "$local_id" "$label"
python3 "$CLI_PATH" comment "$local_id" --body "Smoke test comment."
python3 "$CLI_PATH" close "$local_id"
python3 "$CLI_PATH" reopen "$local_id"
python3 "$CLI_PATH" label delete "$label"

if git ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then
  git push origin --delete "$branch"
else
  echo "Remote branch already absent: $branch"
fi

echo "Smoke MR localId: $local_id"
