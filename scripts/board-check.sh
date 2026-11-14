#!/usr/bin/env bash
# Read-only consistency checks for the GitHub task board (#39, #41). Uses gh, git and python only;
# never writes to GitHub. Usage: scripts/board-check.sh [ref]   (PLAN.md and AGENTS.md are read at ref; default origin/main)
set -u
cd "$(git rev-parse --show-toplevel)"
PLAN_REF="${1:-origin/main}"
PY="$(command -v python3 || command -v python)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
# Windows Python cannot open MSYS paths like /tmp/...; cygpath converts when it exists.
PYTMP="$TMP"; command -v cygpath >/dev/null && PYTMP="$(cygpath -m "$TMP")"

git fetch -q origin 2>/dev/null || true
gh issue list --state open --limit 200 --json number,title,body,labels,assignees > "$TMP/open.json" || exit 1
gh issue view 39 --json body --jq .body > "$TMP/order.md" || exit 1
gh issue list --state closed --limit 300 --json title,stateReason > "$TMP/closed.json" || exit 1
gh pr view 43 --json state --jq .state > "$TMP/pr43" || exit 1
git ls-remote --heads origin | awk '{sub("refs/heads/","",$2); print $2}' > "$TMP/branches"
git show "$PLAN_REF:docs/PLAN.md" > "$TMP/plan.md" || { echo "no docs/PLAN.md at $PLAN_REF" >&2; exit 1; }
cp scripts/bootstrap-board.sh "$TMP/bootstrap.sh"
git show "$PLAN_REF:AGENTS.md" > "$TMP/agents.md" || exit 1

# Claim comments are fetched only for doing/review issues, to keep the gh call count low.
"$PY" - "$PYTMP" <<'EOF' > "$TMP/claimed"
import json, sys
for i in json.load(open(sys.argv[1] + "/open.json", encoding="utf-8")):
    if {l["name"] for l in i["labels"]} & {"doing", "review"}:
        print(i["number"])
EOF
for n in $(tr -d '\r' < "$TMP/claimed"); do
  gh issue view "$n" --json comments --jq '[.comments[].body]' > "$TMP/c$n.json" || exit 1
done

PLAN_REF="$PLAN_REF" PYTHONIOENCODING=utf-8 "$PY" - "$PYTMP" <<'EOF'
import json, os, re, sys
T = sys.argv[1]
rd = lambda f: open(os.path.join(T, f), encoding="utf-8").read()
issues = {i["number"]: i for i in json.load(open(os.path.join(T, "open.json"), encoding="utf-8"))}
# Tasks carry a code in the title ("[env] A1: ..."); #1 Contracts, #39 and legacy issues like #2 do not.
tasks = {n: i for n, i in issues.items() if re.match(r"\[[a-z]+\] [A-DW]\d+:", i["title"])}
others = sorted(n for n in issues if n not in tasks)
labels = {n: [l["name"] for l in i["labels"]] for n, i in tasks.items()}
branches = set(rd("branches").split())
fails = 0

def report(ok: bool, msg: str) -> None:
    global fails
    fails += not ok
    print(("  ok   " if ok else "  FAIL ") + msg)

def code_of(title: str) -> str | None:
    m = re.match(r"\[[a-z]+\] ([A-DW]\d+):", title)
    return m.group(1) if m else None

def wave_of(n: int) -> int | None:
    w = [l for l in labels.get(n, []) if l.startswith("wave:")]
    return int(w[0][5:]) if len(w) == 1 else None

print(f"1. Labels and claims (not tasks, skipped: {['#%d' % n for n in others]})")
for n in sorted(tasks):
    L = labels[n]
    counts = {
        "status": sum(l in ("todo", "doing", "review", "blocked") for l in L),
        "area": sum(l.startswith("area:") for l in L),
        "priority": sum(l in ("p0", "p1", "p2") for l in L),
        "wave": sum(l.startswith("wave:") for l in L),
    }
    bad = [f"{k}={v}" for k, v in counts.items() if v != 1]
    report(not bad, f"#{n} labels" + (f": {', '.join(bad)}" if bad else ""))
    if set(L) & {"doing", "review"}:
        comments = json.load(open(os.path.join(T, f"c{n}.json"), encoding="utf-8"))
        claim = [c for c in comments if re.search(r"\bclaimed\b", c)]
        named = set(re.findall(r"[Bb]ranch:?\s*`?([\w./-]+?)`?[\s.,)]", " ".join(claim) + " "))
        pushed = sorted(b for b in named if b in branches)
        report(bool(tasks[n]["assignees"]), f"#{n} has an assignee")
        report(bool(claim), f"#{n} has a claim comment")
        report(bool(pushed), f"#{n} claim branch pushed: {pushed or sorted(named) or 'none named'}")

print("\n2. Task codes")
title_codes = {code_of(i["title"]) for i in tasks.values()} - {None}
# Finished tasks keep their code in PLAN.md and the bootstrap script; not-planned ones are retired.
done_codes = {
    code_of(i["title"]) for i in json.load(open(os.path.join(T, "closed.json"), encoding="utf-8"))
    if i.get("stateReason") == "COMPLETED"
} - {None}
open_codes = {c for c in title_codes if not c.startswith("W")}
known_codes = open_codes | {c for c in done_codes if not c.startswith("W")}
sources = {
    "PLAN.md (" + os.environ["PLAN_REF"] + ")": set(re.findall(r"\b([A-D]\d+)\b", rd("plan.md"))),
    "bootstrap-board.sh": set(re.findall(r"^mk ([A-D]\d+) ", rd("bootstrap.sh"), re.M)),
    "#39 table": {
        c for n, c in re.findall(r"^\|[^|]*\|\s*#(\d+) ([A-DW]\d+)\b", rd("order.md"), re.M) if int(n) in tasks
    },
}
for name, codes in sources.items():
    # Every open code must appear; every listed code must be open or completed.
    need, allowed = (title_codes, title_codes | done_codes) if name == "#39 table" else (open_codes, known_codes)
    missing, extra = sorted(need - codes), sorted(codes - allowed)
    report(not missing and not extra, f"{name} vs task titles: missing open {missing}, unknown or retired {extra}")

print("\n3. Waves against dependencies (#39 table; '(stub)' and 'agree' dependencies are soft)")
deps: dict[int, list[int]] = {}
table_wave: dict[int, int] = {}
for w, n, dep in re.findall(r"^\|\s*(\d+)\s*\|\s*#(\d+)[^|]*\|[^|]*\|([^|]*)\|", rd("order.md"), re.M):
    w, n = int(w), int(n)
    table_wave[n] = w
    # "#4 (stub)" is soft; other parentheticals such as "(start on #17)" are notes, not dependencies.
    hard = [d for d, tail in re.findall(r"#(\d+)(\s*\((?:stub|agree)[^)]*\))?", dep) if not tail]
    notes = set(re.findall(r"#(\d+)", " ".join(re.findall(r"\([^)]*\)", dep))))
    deps[n] = [] if "agree with" in dep else [int(d) for d in hard if d not in notes]
for n, w in sorted(table_wave.items()):
    if n in tasks:  # closed issues may stay in the table as history
        report(wave_of(n) == w, f"#{n} table wave {w} = label wave {wave_of(n)}")
for n, ds in sorted(deps.items()):
    for d in ds:
        if d in table_wave:
            report(table_wave[d] < table_wave[n], f"#{n} (wave {table_wave[n]}) depends on #{d} (wave {table_wave[d]})")
seen: set[int] = set()
stack: list[int] = []
cycles: list[list[int]] = []
def dfs(n: int) -> None:
    if n in stack:
        cycles.append(stack[stack.index(n):] + [n])
        return
    if n in seen:
        return
    seen.add(n)
    stack.append(n)
    for d in deps.get(n, []):
        dfs(d)
    stack.pop()
for n in deps:
    dfs(n)
report(not cycles, f"no dependency cycles {cycles if cycles else ''}")
missing = sorted(n for n in tasks if n not in table_wave)
report(not missing, f"every open task is in the #39 table (missing: {missing})")

print("\n4. File ownership (the 'Files you own' line of each body)")
owns: dict[int, list[str]] = {}
for n, i in tasks.items():
    m = re.search(r"\*\*Files you own:\*\*(.*?)(?:\n\*\*|\n\n|$)", i["body"] or "", re.S)
    if m:
        claimed = re.split(r"\bexcept\b", m.group(1))[0]  # "ed72_sim/ except world.py" carves files out
        owns[n] = [p.rstrip("/") for p in re.findall(r"`([^`\s]+)`", claimed) if "/" in p or "." in p]
        if claimed != m.group(1):
            owns[n] = [p for p in owns[n] if not p.endswith("ed72_sim")] + [f"{p}/*" for p in owns[n] if p.endswith("ed72_sim")]
overlaps = 0
for a in sorted(owns):
    for b in sorted(owns):
        if a < b:
            for pa in owns[a]:
                for pb in owns[b]:
                    if pa == pb or pa.startswith(pb + "/") or pb.startswith(pa + "/"):
                        overlaps += 1
                        report(False, f"#{a} `{pa}` overlaps #{b} `{pb}`")
report(overlaps == 0, f"{overlaps} ownership overlap(s)")
print(f"  info no 'Files you own' line: {sorted(n for n in tasks if n not in owns)}")

print("\n5. PR #29 terms in open issue bodies (each match needs a reason)")
pat = re.compile(r"advance\(|H_anchor|H_floor|wrong triage|\bassess\b|15-min|\bM[1-4]\b|handover tail")
for n in sorted(tasks):
    body = tasks[n]["body"] or ""
    hits = list(pat.finditer(body))
    for m in hits:
        print(f"  #{n}: ...{body[max(0, m.start() - 60): m.end() + 40]}...".replace("\n", " "))
    report(not hits, f"#{n} body has no PR #29 terms" + (f" ({len(hits)} match(es) above)" if hits else ""))

print("\n6. Scored rules appear in an issue and in the agent-visible rules task (A5)")
a5 = next((i for i in tasks.values() if code_of(i["title"]) == "A5"), None)
RULES = {
    "score formula (rulebook §11)": r"60\s*[·*]\s*O|O, T, W, B|score formula",
    "reward = score / 100": r"score\s*/\s*100",
    "§13 fix: T from the first covered tick": r"first covered tick",
    "§13 fix: in-bed-at-end 0.3 only if covered": r"0\.3",
    "hard spend limit €24 000": r"24[\s ]?000",
}
for name, rx in RULES.items():
    where = sorted(n for n, i in tasks.items() if re.search(rx, i["body"] or ""))
    report(bool(where), f"{name}: in issues {where}")
    report(bool(a5 and re.search(rx, a5["body"] or "")), f"{name}: in the A5 (handbook) body")

print("\n7. AGENTS.md section 10 against the rulebook baselines (§12) and the agent interface")
agents = rd("agents.md")
stale = sorted(set(re.findall(r"FCFS-by-label|discharge-all|transfer-all|call-in-everyone", agents)))
report(not stale, f"rule 5 lists no PR #29 baselines {stale if stale else ''}")
report("reactive proxy" in agents.lower(), "rule 5 names the reactive proxy and stop-early baselines")
report("`ward` CLI" in agents, "rule 1 matches SPEC §9 (main image: handbook and the ward CLI)")

print("\n8. Realignment note in AGENTS.md")
pr43 = rd("pr43").strip()
still = "Realignment in progress" in agents
report(not (still and pr43 == "MERGED"), f"PR #43 is {pr43}; 'Realignment in progress' line present: {still}")

print(f"\n{fails} failing check(s)")
sys.exit(1 if fails else 0)
EOF
