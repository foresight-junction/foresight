"""Markdown tables built from score objects."""

from math import isclose

from ed72_analysis.loading import Run

# Mirror of ed72_sim.constants (OUTCOME_WEIGHT, LOSS_*). This project must not import the sim, so the
# numbers are copied here; they are public in HANDBOOK.md. Update both if the rules change.
WEIGHT = {1: 10.0, 2: 5.0, 3: 2.0, 4: 1.0, 5: 0.5}
LOSS = {"discharged": 0.0, "died": 1.0, "left": 1.0, "never_admitted": 1.0}
DIVERSION_LOSSES = (0.75, 0.70)  # Current and legacy rules.
IN_BED_COVERED_LOSS = 0.3
OUTCOMES = ("discharged", "in_bed_end", "diverted", "died", "left", "never_admitted")
FAILURE_CODES = tuple(f"F{i}" for i in range(1, 11))
SCORE_COLUMNS = ("score", "O", "T", "W", "B", "spend")


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _table(header: list[str], rows: list[list[str]]) -> str:
    sep = _row(["---"] * len(header))
    return "\n".join([_row(header), sep, *(_row(r) for r in rows)])


def _num(value: float) -> str:
    return f"{value:.3f}" if not float(value).is_integer() else f"{value:g}"


def score_table(runs: list[Run]) -> str:
    header = ["run", *SCORE_COLUMNS, "deaths", "faints", "ended"]
    rows = [
        [r.label, *(_num(r.score[k]) for k in SCORE_COLUMNS), *_totals(r), r.score["ended"]] for r in runs
    ]
    for group in dict.fromkeys(r.group for r in runs):
        members = [r for r in runs if r.group == group]
        if len(members) < 2:
            continue
        n = len(members)
        means = [_num(sum(r.score[k] for r in members) / n) for k in SCORE_COLUMNS]
        deaths = _num(sum(r.score["totals"]["died"] for r in members) / n)
        faints = _num(sum(r.score["totals"]["faints"] for r in members) / n)
        rows.append([f"**{group} mean (n={n})**", *means, deaths, faints, ""])
    return _table(header, rows)


def _totals(run: Run) -> list[str]:
    return [str(run.score["totals"]["died"]), str(run.score["totals"]["faints"])]


def failure_table(runs: list[Run]) -> str:
    """Only codes present in some run get a column; absent codes in one run read n/a, never 0."""
    present = [c for c in FAILURE_CODES if any(c in r.score["failures"] for r in runs)]
    rows = [[r.label, *(str(r.score["failures"].get(c, "n/a")) for c in present)] for r in runs]
    return _table(["run", *present], rows)


def _patient_loss(patient: dict) -> float:
    if patient["outcome"] == "in_bed_end":
        return IN_BED_COVERED_LOSS if patient["first_covered_tick"] is not None else 1.0
    return LOSS[patient["outcome"]]


def esi_table(run: Run) -> str:
    """Counts per outcome and each ESI level's share of the total weighted loss."""
    patients = run.score["patients"]
    losses = dict.fromkeys(WEIGHT, 0.0)
    diverted_weights = dict.fromkeys(WEIGHT, 0.0)
    for patient in patients:
        esi = patient["esi"]
        if patient["outcome"] == "diverted":
            diverted_weights[esi] += WEIGHT[esi]
        else:
            losses[esi] += WEIGHT[esi] * _patient_loss(patient)

    diverted_weight = sum(diverted_weights.values())
    total_loss = sum(losses.values())
    diversion_loss = 0.0
    if diverted_weight:
        total_weight = sum(WEIGHT[p["esi"]] for p in patients)
        outcome = run.score.get("O")
        matching_rates = [
            rate
            for rate in DIVERSION_LOSSES
            if isinstance(outcome, int | float)
            and isclose(
                1 - (total_loss + rate * diverted_weight) / total_weight,
                outcome,
                rel_tol=0.0,
                # The scorer reports six decimals. Summing by severity can shift a tie.
                abs_tol=0.5e-6 + 1e-12,
            )
        ]
        if len(matching_rates) == 1:
            diversion_loss = matching_rates[0]
            total_loss += diversion_loss * diverted_weight
        else:
            total_loss = None

    rows = []
    for level in sorted(WEIGHT):
        group = [p for p in patients if p["esi"] == level]
        loss = losses[level] + diversion_loss * diverted_weights[level]
        share = f"{loss / total_loss:.0%}" if total_loss else "n/a"
        counts = [str(sum(p["outcome"] == o for p in group)) for o in OUTCOMES]
        rows.append([f"ESI {level}", str(len(group)), *counts, share])
    table = _table(["ESI", "arrived", *OUTCOMES, "loss share"], rows)
    if total_loss is None:
        table += "\n\nLoss shares are unavailable because the recorded outcome does not establish the diversion rate."
    return table
