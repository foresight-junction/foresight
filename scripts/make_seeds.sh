#!/usr/bin/env bash
# Stamp ed72-s<N> task folders from the ed72/ Harbor task template.
# Only ED72_SEED (hospital service, docker-compose.yaml) and the task name
# (task.toml) differ; the seed never goes into the agent ("main") image.
set -eu

usage() {
  cat <<'USAGE'
Usage: scripts/make_seeds.sh [--check] [SEEDS...]
  Creates ed72-s<N> next to ed72/ for each seed (default: 1 2 3).
  --check  regenerate into a temp dir and diff against existing folders;
           exit 1 if any is missing or differs (for CI).
  ED72_ROOT overrides the repo root (used by tests).
USAGE
}

die() {
  echo "make_seeds: $*" >&2
  exit 1
}

check=0
seeds=""
for arg in "$@"; do
  case "$arg" in
    -h | --help) usage; exit 0 ;;
    --check) check=1 ;;
    -*) usage >&2; die "unknown option: $arg" ;;
    *[!0-9]* | "") die "seed must be a number: $arg" ;;
    *) seeds="$seeds $arg" ;;
  esac
done
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
      sub(/ED72_SEED:.*/, "ED72_SEED: \"" seed "\"")
      $0 = $0 cr
      n++
    }
    { print }
    END { if (n != 1) exit 3 }
  ' "$f" >"$tmp" || { rm -f "$tmp"; die "$compose_rel: expected exactly one 'ED72_SEED:' line"; }
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
