#!/usr/bin/env bash
# shellcheck disable=SC2016 # single quotes keep literal ${...} and backticks on purpose
# Stamp ed72-s<N> task folders from the ed72/ Harbor task template.
# Only ED72_SEED (hospital service, docker-compose.yaml) and the task name
# (task.toml) differ; the seed never goes into the agent ("main") image.
set -eu

usage() {
  cat <<'USAGE'
Usage: scripts/make_seeds.sh [--check | --report] [SEEDS...]
  Creates ed72-s<N> next to ed72/ for each seed (default: 1 2 3).
  The ED72_SEED line may be a literal ("42") or the host-override form
  ("${ED72_SEED:-42}"); each copy keeps the same form with default N.
  --check  regenerate into a temp dir and diff against existing folders;
           exit 1 if any is missing or differs (for CI).
  --report print a markdown table per seed folder (default seed, task name,
           content SHA-256, source commit, Harbor oracle and nop commands),
           plus the ed72/ row. Folders that do not exist are built in a temp
           dir; nothing is written into the repo.
  ED72_ROOT overrides the repo root (used by tests).
USAGE
}

die() {
  echo "make_seeds: $*" >&2
  exit 1
}

check=0
report=0
seeds=""
for arg in "$@"; do
  case "$arg" in
    -h | --help) usage; exit 0 ;;
    --check) check=1 ;;
    --report) report=1 ;;
    -*) usage >&2; die "unknown option: $arg" ;;
    *[!0-9]* | "") die "seed must be a number: $arg" ;;
    *) seeds="$seeds $arg" ;;
  esac
done
[ "$check$report" != 11 ] || die "--check and --report are mutually exclusive"
[ -n "$seeds" ] || seeds="1 2 3"

if [ -n "${ED72_ROOT:-}" ]; then
  root=$ED72_ROOT
else
  root=$(git rev-parse --show-toplevel) || die "not inside a git repo"
fi
root=$(cd "$root" && pwd)
tpl="$root/ed72"
compose_rel="environment/docker-compose.yaml"
task_rel="task.toml"

[ -d "$tpl" ] || die "template folder missing: $tpl"
[ -f "$tpl/$compose_rel" ] || die "template lacks $compose_rel"
[ -f "$tpl/$task_rel" ] || die "template lacks $task_rel"

# stamp <dir> <seed>: rewrite the two lines in a copy, failing unless each
# file changes exactly one line.
stamp() {
  dir=$1
  seed=$2
  f="$dir/$compose_rel"
  tmp="$f.tmp"
  awk -v seed="$seed" '
    /^[ \t]*ED72_SEED:/ {
      cr = ($0 ~ /\r$/) ? "\r" : ""
      # Strip CR first: BSD awk may not treat "\r?" as optional inside an ERE.
      sub(/\r$/, "")
      if ($0 ~ /ED72_SEED:[ \t]*"\$\{ED72_SEED:-[0-9]+\}"[ \t]*$/)
        sub(/ED72_SEED:.*/, "ED72_SEED: \"${ED72_SEED:-" seed "}\"")
      else if ($0 ~ /ED72_SEED:[ \t]*"[0-9]+"[ \t]*$/)
        sub(/ED72_SEED:.*/, "ED72_SEED: \"" seed "\"")
      else
        bad = 1
      $0 = $0 cr
      n++
    }
    { print }
    END { if (n != 1 || bad) exit 3 }
  ' "$f" >"$tmp" || { rm -f "$tmp"; die "$compose_rel: expected exactly one ED72_SEED line, as \"N\" or \"\${ED72_SEED:-N}\""; }
  mv "$tmp" "$f"

  f="$dir/$task_rel"
  tmp="$f.tmp"
  awk -v seed="$seed" '
    /^\[/ { sect = $0; sub(/\r$/, "", sect) }
    sect == "[task]" && /^name[ \t]*=/ {
      cr = ($0 ~ /\r$/) ? "\r" : ""
      sub(/\r$/, "")
      if ($0 !~ /"[ \t]*$/) bad = 1
      sub(/"[ \t]*$/, "-s" seed "\"")
      $0 = $0 cr
      n++
    }
    { print }
    END { if (n != 1 || bad) exit 3 }
  ' "$f" >"$tmp" || { rm -f "$tmp"; die "$task_rel: expected exactly one quoted 'name =' line under [task]"; }
  mv "$tmp" "$f"
}

# build <outdir>: stamp every seed folder into outdir.
build() {
  out=$1
  for s in $seeds; do
    rm -rf "${out:?}/ed72-s$s"
    cp -R "$tpl" "$out/ed72-s$s"
    stamp "$out/ed72-s$s" "$s"
  done
}

# digest [file]: SHA-256 hex of a file or stdin (GNU or BSD tools).
digest() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$@" | awk '{ print $1 }'
  else
    shasum -a 256 "$@" | awk '{ print $1 }'
  fi
}

# folder_hash <dir>: SHA-256 of "<file hash>  <relative path>" lines in C-locale
# path order. Skips <dir>/.harborignore patterns plus caches and temp files.
folder_hash() {
  (
    cd "$1"
    ign=""
    if [ -f .harborignore ]; then
      ign=$(tr -d '\r' <.harborignore | sed -e 's/#.*//' -e 's/[ 	]*$//' -e 's|^/||' -e 's|/$||' | awk 'NF')
    fi
    find . -type f | sed 's|^\./||' | LC_ALL=C sort | while IFS= read -r p; do
      skip=0
      case "/$p/" in */__pycache__/* | */.pytest_cache/*) skip=1 ;; esac
      case "$p" in *.pyc | *.tmp | .DS_Store | */.DS_Store | .harborignore) skip=1 ;; esac
      for pat in $ign; do
        # shellcheck disable=SC2254
        case "$p" in $pat | $pat/* | */$pat | */$pat/*) skip=1 ;; esac
      done
      [ "$skip" = 1 ] || printf '%s  %s\n' "$(digest "$p")" "$p"
    done | digest
  )
}

# default_seed / task_name <dir>: read back what a (stamped or template) folder holds.
default_seed() {
  grep -E '^[ 	]*ED72_SEED:' "$1/$compose_rel" | tr -d '\r' | sed -E 's/.*ED72_SEED:[ 	]*"(\$\{ED72_SEED:-)?([0-9]+).*/\2/'
}
task_name() {
  awk '/^\[/ { s = $0 } s ~ /^\[task\]/ && /^name[ \t]*=/ { gsub(/^[^"]*"|"[^"]*$/, ""); print; exit }' "$1/$task_rel"
}

source_commit() {
  c=$(git -C "$root" rev-parse HEAD 2>/dev/null) || { echo unknown; return; }
  if [ -n "$(git -C "$root" status --porcelain -- ed72 2>/dev/null)" ]; then c="$c+dirty"; fi
  echo "$c"
}

if [ "$report" = 1 ]; then
  tmpd=$(mktemp -d "${TMPDIR:-/tmp}/make_seeds.XXXXXX")
  trap 'rm -rf "$tmpd"' EXIT
  harbor_cmd="${HARBOR:-uvx --python 3.12 --from harbor==0.26.0 harbor}"
  commit=$(source_commit)
  build "$tmpd"
  echo "Source commit: \`$commit\` (\`+dirty\` means uncommitted changes under ed72/ only)."
  echo "Hashes are of the checked-out bytes; .gitattributes forces LF, so they match across OSes."
  echo "Run the commands from the repo root."
  echo
  echo "| Folder | Default seed | Task name | SHA-256 (contents) | Source commit | Oracle | Nop |"
  echo "| --- | --- | --- | --- | --- | --- | --- |"
  for s in $seeds ""; do
    if [ -z "$s" ]; then
      name=ed72
      d=$tpl
    else
      name=ed72-s$s
      d=$root/$name
      [ -d "$d" ] || d=$tmpd/$name
    fi
    cmd="$harbor_cmd run -p $name -o eval/results/jobs/$name -y -n 1"
    printf '| `%s` | %s | `%s` | `%s` | `%s` | `%s` | `%s` |\n' \
      "$name" "$(default_seed "$d")" "$(task_name "$d")" "$(folder_hash "$d")" "$commit" \
      "$cmd --job-name $name-oracle -a oracle" "$cmd --job-name $name-nop -a nop"
  done
  exit 0
fi

if [ "$check" = 0 ]; then
  build "$root"
  for s in $seeds; do echo "wrote $root/ed72-s$s"; done
  exit 0
fi

tmpd=$(mktemp -d "${TMPDIR:-/tmp}/make_seeds.XXXXXX")
trap 'rm -rf "$tmpd"' EXIT
build "$tmpd"
fail=0
for s in $seeds; do
  if [ ! -d "$root/ed72-s$s" ]; then
    echo "make_seeds: ed72-s$s is missing" >&2
    fail=1
  elif ! diff -r "$tmpd/ed72-s$s" "$root/ed72-s$s" >&2; then
    echo "make_seeds: ed72-s$s differs from the template" >&2
    fail=1
  fi
done
[ "$fail" = 0 ] || die "out of date; run scripts/make_seeds.sh and commit"
echo "ed72 seed folders are up to date"
