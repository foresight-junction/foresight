#!/usr/bin/env bash
# Worktree + task helper for the Junction team. Works with macOS's default bash 3.2.
#
#   scripts/wt.sh init                                        once per laptop (and once per repo for labels)
#   scripts/wt.sh new <owner> <area> <task> [-i <issue>]      new task branch + worktree + context file
#   scripts/wt.sh new <owner> <area> <task> <agent>           helper branch off an existing task branch
#   scripts/wt.sh list                                        all worktrees on this laptop
#   scripts/wt.sh board                                       open GitHub issues (the team task board)
#   scripts/wt.sh status                                      is anyone working in each worktree here?
#   scripts/wt.sh status <slug|branch>                        live state of one task; exits 1 if BUSY
#   scripts/wt.sh inbox <agent-id>                            latest issue comments that mention you
#   scripts/wt.sh done <slug> [-f]                            remove a worktree (keeps the branch)
#
# Set SKIP_INSTALL=1 to skip uv sync / pnpm install in new worktrees.
# Set WT_IDLE_MIN (default 30) to change how many quiet minutes count as idle.

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
    for a in env reward ref harness train docs infra; do
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
  for f in .env frontend/.env; do
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
    local d
    for d in . backend ed72/environment/hospital eval analysis training; do
      if [ -f "$path/$d/pyproject.toml" ]; then
        (cd "$path/$d" && uv sync --quiet) || echo "warning: uv sync failed in $d (is uv installed?)" >&2
      fi
    done
    if [ -f "$path/frontend/package.json" ]; then
      (cd "$path/frontend" && pnpm install --frozen-lockfile --silent) \
        || echo "warning: pnpm install failed in frontend (is pnpm installed?)" >&2
    fi
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

# status and inbox read live git, process and issue state, because comments lag behind what agents do

IDLE_SEC=$(( ${WT_IDLE_MIN:-30} * 60 ))
NOW="$(date +%s)"

ago() {
  local s=$(( NOW - $1 ))
  if [ "$1" -le 0 ]; then echo "-"
  elif [ "$s" -lt 3600 ]; then echo "$(( s / 60 ))m"
  elif [ "$s" -lt 86400 ]; then echo "$(( s / 3600 ))h$(( s % 3600 / 60 ))m"
  else echo "$(( s / 86400 ))d"; fi
}

# GNU stat first: on Linux `stat -f` is filesystem stat and would "succeed" with junk
mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }

# This shell and its parents (the agent asking) shouldn't count as someone else working
my_pids() {
  local p=$$
  while [ -n "$p" ] && [ "$p" -gt 1 ]; do
    echo "$p"; p="$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')"
  done
}

load_procs() {
  command -v lsof >/dev/null || die "lsof not found. Install it: without it status can't see running agents."
  CWDS="$(lsof -w -d cwd -Fpn 2>/dev/null | awk '/^p/{pid=substr($0,2)} /^n/{print pid "\t" substr($0,2)}' || true)"
  # this shell always has a cwd, so an empty list means lsof failed
  [ -n "$CWDS" ] || die "lsof listed no processes, so status can't tell who is working. Check lsof works."
  MINE="$(my_pids)"
}

# Only still-alive pids: the lsof snapshot also catches this script's own short-lived subshells
procs_in() {
  local list
  list="$(printf '%s\n' "$CWDS" | awk -F'\t' -v p="$1" '$2==p || index($2, p "/")==1 {print $1}' \
    | grep -vxF "$MINE" | sort -u | paste -sd, - || true)"
  [ -z "$list" ] || ps -o pid= -p "$list" 2>/dev/null | tr -d ' ' || true
}

newest_edit() {
  local e f newest=0 t skip=0
  while IFS= read -r -d '' e; do
    # with -z a rename or copy is followed by an extra entry holding the old path
    if [ "$skip" = 1 ]; then skip=0; continue; fi
    case "${e:0:2}" in *R*|*C*) skip=1 ;; esac
    f="$1/${e:3}"
    # a deleted file has no mtime, but its folder's mtime changed when it went
    [ -e "$f" ] || f="$(dirname "$f")"
    t="$(mtime "$f")"
    if [ "$t" -gt "$newest" ]; then newest="$t"; fi
  done < <(git -C "$1" status --porcelain -z --untracked-files=all)
  echo "$newest"
}

recent() { [ "$1" -gt 0 ] && [ $(( NOW - $1 )) -lt "$IDLE_SEC" ]; }

# Fills: path, branch, ref, commit_t, remote_t, unpushed, dirty, edit_t, pids, busy
inspect() {
  path="$1"; branch="$2"; ref="$branch"
  git show-ref --verify --quiet "refs/heads/$branch" || ref="origin/$branch"
  commit_t="$(git log -1 --format=%ct "$ref" 2>/dev/null || echo 0)"
  if git show-ref --verify --quiet "refs/remotes/origin/$branch"; then
    remote_t="$(git log -1 --format=%ct "origin/$branch")"
    unpushed="$(git rev-list --count "origin/$branch..$ref" 2>/dev/null || echo "?")"
  else
    remote_t=0; unpushed="all"
  fi
  dirty="-"; edit_t=0; pids=""
  if [ -n "$path" ]; then
    dirty="$(git -C "$path" status --porcelain | wc -l | tr -d ' ')"
    edit_t="$(newest_edit "$path")"
    pids="$(procs_in "$path")"
  fi
  busy=0
  if [ -n "$pids" ]; then busy=1; fi
  local t
  for t in "$commit_t" "$remote_t" "$edit_t"; do
    if recent "$t"; then busy=1; fi
  done
}

worktree_of() {
  git worktree list --porcelain \
    | awk -v b="branch refs/heads/$1" '/^worktree /{w=substr($0,10)} $0==b {print w}'
}

cmd_status() {
  git fetch --quiet origin 2>/dev/null || echo "warning: git fetch failed, remote info may be stale" >&2
  load_procs
  if [ $# -eq 0 ]; then
    local w b
    printf '%-40s %-7s %-7s %-6s %-9s %-6s %s\n' WORKTREE COMMIT EDIT DIRTY UNPUSHED PROCS STATE
    while IFS=$'\t' read -r w b; do
      [ "$w" = "$MAIN_ROOT" ] && continue
      inspect "$w" "$b"
      printf '%-40s %-7s %-7s %-6s %-9s %-6s %s\n' "${w#"$PARENT_DIR/$REPO--"}" \
        "$(ago "$commit_t")" "$(ago "$edit_t")" "$dirty" "$unpushed" \
        "$(printf '%s' "$pids" | grep -c . || true)" "$([ "$busy" = 1 ] && echo BUSY || echo idle)"
    done < <(git worktree list --porcelain \
      | awk '/^worktree /{w=substr($0,10)} /^branch /{print w "\t" substr($0,19)}')
    echo
    echo "COMMIT/EDIT = time since last commit / newest uncommitted file change. BUSY = a process runs"
    echo "there or something changed in the last ${WT_IDLE_MIN:-30}m. wt.sh status <slug> also checks pushes and comments."
    return 0
  fi

  local arg="$1" ctx issue
  if [ -d "$PARENT_DIR/$REPO--$arg" ]; then
    path="$PARENT_DIR/$REPO--$arg"; branch="$(git -C "$path" branch --show-current)"
  else
    branch="$arg"
    # a slug for a branch that isn't checked out here: owner-area-task -> owner/area-task
    if ! git show-ref --quiet "refs/heads/$branch" "refs/remotes/origin/$branch" && [[ "$arg" != */* ]]; then
      branch="${arg/-//}"
    fi
    git show-ref --quiet "refs/heads/$branch" "refs/remotes/origin/$branch" \
      || die "no worktree, branch or remote branch called $arg"
    path="$(worktree_of "$branch")"
  fi
  inspect "$path" "$branch"

  echo "branch:        $branch"
  echo "worktree:      ${path:-not on this laptop}"
  echo "last commit:   $(ago "$commit_t") ago  $(git log -1 --format='%h %s' "$ref")"
  local push_t=0
  if [ "$remote_t" -gt 0 ] && have_gh; then
    # a commit made hours ago can be pushed a minute ago, so ask GitHub when the push happened
    push_t="$(gh api "repos/{owner}/{repo}/activity?ref=refs/heads/$branch&per_page=1" \
      --jq '.[0].timestamp // null | if . then fromdateiso8601 else 0 end' 2>/dev/null || echo 0)"
  fi
  if [ "$push_t" -gt 0 ]; then
    echo "last push:     $(ago "$push_t") ago  ($unpushed local commits not pushed)"
    if recent "$push_t"; then busy=1; fi
  elif [ "$remote_t" -gt 0 ]; then
    echo "last push:     unknown (GitHub didn't say), pushed tip was committed $(ago "$remote_t") ago"
  else
    echo "last push:     never pushed"
  fi
  if [ -n "$path" ]; then
    echo "uncommitted:   $dirty files, newest change $(ago "$edit_t") ago"
    if [ -n "$pids" ]; then
      echo "processes:"
      # shellcheck disable=SC2086
      ps -o pid=,etime=,command= -p "$(echo $pids | tr ' ' ',')" | cut -c1-110 | sed 's/^/  /' \
        || echo "  (they exited just now)"
    else
      echo "processes:     none"
    fi
  else
    echo "processes:     can't see another laptop's processes or uncommitted work"
  fi

  ctx=".context/$(echo "$branch" | tr '/' '-').md"
  issue="$( { if [ -n "$path" ] && [ -f "$path/$ctx" ]; then cat "$path/$ctx"; else git show "$ref:$ctx"; fi; } \
    2>/dev/null | sed -n 's/^- \*\*Issue:\*\* #\([0-9]*\).*/\1/p' | head -1 || true)"
  if [ -n "$issue" ] && have_gh; then
    local comments comment_t
    comments="$(gh issue view "$issue" --json comments -q '
      (.comments[-1].createdAt // null | if . then fromdateiso8601 else 0 end),
      (.comments[-3:][] | "  " + ((now - (.createdAt | fromdateiso8601)) / 60 | floor | tostring)
        + "m ago  " + (.body | split("\n")[0] | .[0:100]))')"
    comment_t="$(echo "$comments" | head -1)"
    if recent "$comment_t"; then busy=1; fi
    echo "issue #$issue latest comments:"
    echo "$comments" | tail -n +2
  fi

  echo
  if [ "$busy" = 1 ]; then
    echo "BUSY: someone is working here. Don't hand it over or take it over."
    echo "Ask on the issue (address the agent id above) and wait for a reply."
    return 1
  elif [ -z "$path" ]; then
    echo "QUIET for ${WT_IDLE_MIN:-30}m+, but it lives on another laptop: ask on the issue before taking over."
  else
    echo "IDLE: nothing running or changed for ${WT_IDLE_MIN:-30}m+. Post a handoff comment on the issue before taking over."
  fi
}

cmd_inbox() {
  [ $# -ge 1 ] || die "usage: wt.sh inbox <agent-id>"
  valid "$1"; have_gh || die "gh isn't logged in (run: gh auth login)"
  # word match so yehor-claude-3 doesn't also pick up yehor-claude-3a; skip your own comments
  gh issue list --state all --limit 30 --search "\"$1\" in:comments,body sort:updated-desc" \
    --json number,comments --jq '
      [.[] | .number as $n | .comments[]
        | select((.body | test("(^|[^a-z0-9-])'"$1"'($|[^a-z0-9-])")) and (.body | startswith("['"$1"']") | not))
        | {n: $n, at: .createdAt, body: (.body | split("\n")[0] | .[0:110])}]
      | sort_by(.at) | .[-10:][]
      | ((now - (.at | fromdateiso8601)) / 60 | floor | tostring) + "m ago  #" + (.n | tostring) + "  " + .body'
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
  status) shift; cmd_status "$@" ;;
  inbox) shift; cmd_inbox "$@" ;;
  done)  shift; cmd_done "$@" ;;
  *) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
