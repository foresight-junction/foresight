#!/usr/bin/env bash
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

echo "ok: all make_seeds tests passed"
