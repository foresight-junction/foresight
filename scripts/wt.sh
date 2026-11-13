#!/usr/bin/env bash
# Worktree + task helper for the Junction team. Works with macOS's default bash 3.2.
#
#   scripts/wt.sh init                                        once per laptop (and once per repo for labels)
#   scripts/wt.sh new <owner> <area> <task> [-i <issue>]      new task branch + worktree + context file
#   scripts/wt.sh new <owner> <area> <task> <agent>           helper branch off an existing task branch
#   scripts/wt.sh list                                        all worktrees on this laptop
#   scripts/wt.sh board                                       open GitHub issues (the team task board)
#   scripts/wt.sh done <slug> [-f]                            remove a worktree (keeps the branch)
#
# Set SKIP_INSTALL=1 to skip pnpm install / uv sync in new worktrees.

set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }

COMMON_DIR="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" \
  || die "run this inside the repo"
MAIN_ROOT="$(dirname "$COMMON_DIR")"
REPO="$(basename "$MAIN_ROOT")"
PARENT_DIR="$(dirname "$MAIN_ROOT")"

valid() { [[ "$1" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "'$1' must be lowercase letters, numbers and hyphens"; }
have_gh() { command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; }

cmd_init() {
  # Claude reads .claude/skills, Codex reads .agents/skills: keep one copy
  if [ ! -e "$MAIN_ROOT/.claude/skills" ]; then
    mkdir -p "$MAIN_ROOT/.claude"
    ln -s ../.agents/skills "$MAIN_ROOT/.claude/skills"
    echo "linked .claude/skills -> .agents/skills (commit this)"
  fi

  if have_gh && git -C "$MAIN_ROOT" remote get-url origin >/dev/null 2>&1; then
    echo "creating GitHub labels..."
    gh label create todo     --color ededed --force >/dev/null
    gh label create doing    --color fbca04 --force >/dev/null
    gh label create review   --color 0e8a16 --force >/dev/null
    gh label create blocked  --color b60205 --force >/dev/null
    gh label create contract --color 5319e7 --force >/dev/null
    for a in fe api data ai infra docs; do
      gh label create "area:$a" --color 1d76db --force >/dev/null
    done
    if ! gh issue list --search "Contracts in:title" --state all --json number -q '.[0].number' | grep -q .; then
      n="$(gh issue create --title "Contracts" --label contract \
        --body "Pinned. Propose and announce changes to docs/CONTRACTS.md here (see the contract-change skill)." \
        | grep -oE '[0-9]+$')"
      gh issue pin "$n" >/dev/null 2>&1 || true
      echo "created and pinned Contracts issue #$n"
    fi
  else
    echo "skipped GitHub labels (gh not logged in, or no 'origin' remote yet)"
  fi
  echo "init done"
}

cmd_new() {
  [ $# -ge 3 ] || die "usage: wt.sh new <owner> <area> <task> [-i <issue>] [agent]"
  local owner="$1" area="$2" task="$3"; shift 3
  local agent="" issue=""
  while [ $# -gt 0 ]; do
    case "$1" in
      -i) [ $# -ge 2 ] || die "-i needs an issue number"; issue="$2"; shift 2 ;;
      *)  agent="$1"; shift ;;
    esac
  done
  valid "$owner"; valid "$area"; valid "$task"
  [ -z "$issue" ] || [[ "$issue" =~ ^[0-9]+$ ]] || die "issue must be a number"

  local parent branch base
  parent="$owner/$area-$task"
  if [ -n "$agent" ]; then
    valid "$agent"
    git show-ref --verify --quiet "refs/heads/$parent" \
      || die "parent branch $parent doesn't exist. Create it first without an agent."
    branch="$parent--$agent"
    base="$parent"
    # inherit the parent's issue number from its context file
    if [ -z "$issue" ]; then
      issue="$(git show "$parent:.context/$(echo "$parent" | tr '/' '-').md" 2>/dev/null \
        | sed -n 's/^- \*\*Issue:\*\* #\([0-9]*\).*/\1/p' | head -1 || true)"
    fi
  else
    branch="$parent"
    git fetch --quiet origin main 2>/dev/null || true
    if git show-ref --verify --quiet refs/remotes/origin/main; then base="origin/main"; else base="main"; fi
    parent="main"
  fi

  git show-ref --verify --quiet "refs/heads/$branch" && die "branch $branch already exists"

  local slug path
  slug="$(echo "$branch" | tr '/' '-')"
  path="$PARENT_DIR/$REPO--$slug"
  [ -e "$path" ] && die "$path already exists"

  git worktree add --quiet --no-track -b "$branch" "$path" "$base"

  # Local env files are gitignored, so copy them in
  for f in .env backend/.env frontend/.env; do
    if [ -f "$MAIN_ROOT/$f" ]; then
      mkdir -p "$(dirname "$path/$f")"; cp "$MAIN_ROOT/$f" "$path/$f"
    fi
  done

  # Branch context file, committed straight away
  local tmpl="$path/.context/TEMPLATE.md" ctx="$path/.context/$slug.md"
  if [ -f "$tmpl" ]; then
    sed -e "s|{{BRANCH}}|$branch|g" \
        -e "s|{{OWNER}}|$owner|g" \
        -e "s|{{AGENT}}|${agent:-lead}|g" \
        -e "s|{{PARENT}}|$parent|g" \
        -e "s|{{ISSUE}}|${issue:+#$issue}|g" \
        -e "s|{{DATE}}|$(date '+%a %H:%M')|g" \
        "$tmpl" > "$ctx"
    git -C "$path" add ".context/$slug.md"
    git -C "$path" commit --quiet -m "docs(context): start $branch" ${issue:+-m "Refs #$issue"}
  else
    echo "warning: no .context/TEMPLATE.md on this branch, skipped context file" >&2
  fi

  if [ "${SKIP_INSTALL:-0}" != "1" ]; then
    if [ -f "$path/frontend/package.json" ]; then (cd "$path/frontend" && pnpm install --prefer-offline --silent) || true; fi
    if [ -f "$path/backend/pyproject.toml" ]; then (cd "$path/backend" && uv sync --quiet) || true; fi
  fi

  echo
  echo "branch:   $branch"
  if [ -n "$issue" ]; then echo "issue:    #$issue"; else echo "issue:    none (claim or create one with the claim-task skill)"; fi
  echo "folder:   $path"
  echo "context:  .context/$slug.md"
  echo "slug:     $slug   (for 'wt.sh done')"
  echo
  echo "next:     cd \"$path\" && claude      (or: codex)"
}

cmd_list() { git worktree list; }

cmd_board() {
  have_gh || die "gh isn't logged in (run: gh auth login)"
  for s in doing review blocked todo; do
    echo "== $s =="
    gh issue list --state open --label "$s" --limit 50 \
      --json number,title,assignees \
      -q '.[] | "#\(.number)  \(.title)  [\([.assignees[].login] | join(","))]"'
  done
}

cmd_done() {
  [ $# -ge 1 ] || die "usage: wt.sh done <slug> [-f]"
  local path="$PARENT_DIR/$REPO--$1"
  [ -d "$path" ] || die "no worktree at $path"
  if [ "${2:-}" = "-f" ]; then
    git worktree remove --force "$path"
  else
    [ -z "$(git -C "$path" status --porcelain)" ] \
      || die "$path has uncommitted changes. Commit them, or add -f to throw them away."
    git worktree remove "$path"
  fi
  echo "removed $path (branch kept)"
}

case "${1:-}" in
  init)  shift; cmd_init "$@" ;;
  new)   shift; cmd_new "$@" ;;
  list)  shift; cmd_list "$@" ;;
  board) shift; cmd_board "$@" ;;
  done)  shift; cmd_done "$@" ;;
  *) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
