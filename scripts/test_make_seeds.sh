#!/usr/bin/env bash
# shellcheck disable=SC2016 # single quotes keep literal ${...} and backticks on purpose
# Test scripts/make_seeds.sh against a throwaway repo-shaped fixture.
set -eu

here=$(cd "$(dirname "$0")" && pwd)
fx=$(mktemp -d "${TMPDIR:-/tmp}/seedtest.XXXXXX")
trap 'rm -rf "$fx"' EXIT
mkdir -p "$fx/ed72/environment" "$fx/ed72/tests"

cat >"$fx/ed72/environment/docker-compose.yaml" <<'Y'
services:
  main:
    depends_on:
      hospital:
        condition: service_healthy

  hospital:
    expose:
      - "8000"
    environment:
      ED72_SEED: "42"
Y
cat >"$fx/ed72/task.toml" <<'T'
schema_version = "1.4"

[task]
name = "ed72/emergency-department"

[[environment.mcp_servers]]
name = "hospital"
T
echo "dummy" >"$fx/ed72/tests/dummy.txt"

export ED72_ROOT="$fx"
fail() { echo "FAIL: $*" >&2; exit 1; }

bash "$here/make_seeds.sh" >/dev/null
for n in 1 2 3; do
  d="$fx/ed72-s$n"
  [ -d "$d" ] || fail "ed72-s$n not created"
  grep -q "^      ED72_SEED: \"$n\"\$" "$d/environment/docker-compose.yaml" || fail "seed $n wrong"
  grep -q "^name = \"ed72/emergency-department-s$n\"\$" "$d/task.toml" || fail "name $n wrong"
  grep -q '^name = "hospital"$' "$d/task.toml" || fail "mcp name touched in $n"
  cmp -s "$fx/ed72/tests/dummy.txt" "$d/tests/dummy.txt" || fail "dummy differs in $n"
  grep -q 'ED72_SEED' "$d/environment/docker-compose.yaml" || fail "no seed line"
  [ "$(grep -c '^name = ' "$d/task.toml")" = 2 ] || fail "name count in $n"
done
grep -q '"42"' "$fx/ed72/environment/docker-compose.yaml" || fail "template modified"

bash "$here/make_seeds.sh" --check >/dev/null || fail "--check should pass"
bash "$here/make_seeds.sh" >/dev/null || fail "rerun (idempotent) failed"

echo tampered >>"$fx/ed72-s2/tests/dummy.txt"
if bash "$here/make_seeds.sh" --check >/dev/null 2>&1; then fail "--check should fail on tamper"; fi
bash "$here/make_seeds.sh" >/dev/null
rm -rf "$fx/ed72-s3"
if bash "$here/make_seeds.sh" --check >/dev/null 2>&1; then fail "--check should fail on missing"; fi

sed 's/ED72_SEED/OTHER/' "$fx/ed72/environment/docker-compose.yaml" >"$fx/x" && mv "$fx/x" "$fx/ed72/environment/docker-compose.yaml"
if bash "$here/make_seeds.sh" >/dev/null 2>&1; then fail "should fail without ED72_SEED"; fi


# --- override form ("${ED72_SEED:-42}"), --check and --report, bad lines ---
mkfx() { # mkfx <dir> <compose seed value>
  mkdir -p "$1/ed72/environment" "$1/ed72/tests"
  printf 'services:\n  hospital:\n    environment:\n      ED72_SEED: %s\n' "$2" >"$1/ed72/environment/docker-compose.yaml"
  printf '[task]\nname = "ed72/emergency-department"\n' >"$1/ed72/task.toml"
  echo one >"$1/ed72/tests/a.txt"
}
ms() { ED72_ROOT=$1 bash "$here/make_seeds.sh" "${@:2}"; }

ov="$fx/ov"
mkfx "$ov" '"${ED72_SEED:-42}"'
ms "$ov" >/dev/null
for n in 1 2 3; do
  grep -qF "      ED72_SEED: \"\${ED72_SEED:-$n}\"" "$ov/ed72-s$n/environment/docker-compose.yaml" || fail "override seed $n wrong"
  [ "$(grep -c ED72_SEED "$ov/ed72-s$n/environment/docker-compose.yaml")" = 1 ] || fail "override form lines in $n"
done
grep -qF '${ED72_SEED:-42}' "$ov/ed72/environment/docker-compose.yaml" || fail "override template modified"
ms "$ov" --check >/dev/null || fail "override --check should pass"
echo x >>"$ov/ed72-s1/tests/a.txt"
if ms "$ov" --check >/dev/null 2>&1; then fail "override --check should fail on tamper"; fi
ms "$ov" >/dev/null

lit="$fx/lit"
mkfx "$lit" '"42"'
ms "$lit" >/dev/null
grep -qF '      ED72_SEED: "2"' "$lit/ed72-s2/environment/docker-compose.yaml" || fail "literal seed 2 wrong"
ms "$lit" --check >/dev/null || fail "literal --check should pass"

# --report: three seed rows plus the ed72 row, with 64-hex hashes
rep=$(ms "$ov" --report) || fail "--report failed"
[ "$(printf '%s\n' "$rep" | grep -c '^| `ed72')" = 4 ] || fail "report row count"
printf '%s\n' "$rep" | grep -q '^| `ed72` | 42 | `ed72/emergency-department` | `[0-9a-f]\{64\}`' || fail "ed72 row wrong"
printf '%s\n' "$rep" | grep -q '^| `ed72-s2` | 2 | `ed72/emergency-department-s2` | `[0-9a-f]\{64\}`' || fail "s2 row wrong"
printf '%s\n' "$rep" | grep -q -- '-a oracle' || fail "no oracle command"
printf '%s\n' "$rep" | grep -q -- '-a nop' || fail "no nop command"
hash_of() { printf '%s\n' "$1" | grep "^| \`$2\`" | sed 's/^[^`]*`[^`]*`[^`]*`[^`]*`[^`]*`\([0-9a-f]*\)`.*/\1/'; }
h1=$(hash_of "$rep" ed72-s1)
h2=$(hash_of "$rep" ed72-s2)
[ "${#h1}" = 64 ] && [ "$h1" != "$h2" ] || fail "hash shape or uniqueness"
echo changed >>"$ov/ed72-s1/tests/a.txt"
h1b=$(hash_of "$(ms "$ov" --report)" ed72-s1)
[ "$h1b" != "$h1" ] || fail "hash did not change with file content"
[ "$h2" = "$(hash_of "$(ms "$ov" --report)" ed72-s2)" ] || fail "hash not stable"
# a report must also work with no folders present (built in a temp dir) and write nothing
rm -rf "$ov"/ed72-s*
ms "$ov" --report | grep -c '^| `ed72' | grep -q 4 || fail "report without folders"
[ ! -d "$ov/ed72-s1" ] || fail "report wrote a folder"
if ms "$ov" --check --report >/dev/null 2>&1; then fail "--check with --report should fail"; fi

# bad ED72_SEED lines fail loudly
bad="$fx/bad"
mkfx "$bad" '"${ED72_SEED:-42}"'
printf '      ED72_SEED: "7"\n' >>"$bad/ed72/environment/docker-compose.yaml"
if ms "$bad" >/dev/null 2>&1; then fail "duplicate ED72_SEED should fail"; fi
mkfx "$bad" '"abc"'
if ms "$bad" >/dev/null 2>&1; then fail "non-numeric ED72_SEED should fail"; fi
mkfx "$bad" '"${OTHER:-42}"'
if ms "$bad" >/dev/null 2>&1; then fail "foreign override form should fail"; fi

echo "ok: all make_seeds tests passed"
