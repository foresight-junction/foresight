"""Hand-built horizontal bar chart of failure counts per label."""

from xml.sax.saxutils import escape

from ed72_analysis.loading import Run
from ed72_analysis.tables import FAILURE_CODES

ROW_H = 26
LABEL_W = 170
BAR_MAX = 420
FONT = 'font-family="sans-serif" fill="#888"'


def failures_svg(runs: list[Run]) -> str:
    """Counts are summed per label. Mid grey text and a mid blue bar stay readable on light or dark."""
    totals: dict[str, int] = {}
    for r in runs:
        totals[r.label] = totals.get(r.label, 0) + sum(r.score["failures"].values())
    top = max(totals.values(), default=0) or 1
    height = ROW_H * len(totals) + 50
    width = LABEL_W + BAR_MAX + 70
    codes = ", ".join(c for c in FAILURE_CODES if any(c in r.score["failures"] for r in runs))
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="Failure counts per run">'
        ),
        (
            f'<text x="8" y="20" {FONT} font-size="14" font-weight="bold">'
            f"Failure events per run (codes {escape(codes)}; n/a codes not counted)</text>"
        ),
    ]
    for i, (label, total) in enumerate(totals.items()):
        y = 36 + i * ROW_H
        bar = round(BAR_MAX * total / top)
        parts.append(
            f'<text x="8" y="{y + 15}" {FONT} font-size="13">{escape(label)}</text>'
            f'<rect x="{LABEL_W}" y="{y}" width="{bar}" height="18" fill="#3b82f6"/>'
            f'<text x="{LABEL_W + bar + 6}" y="{y + 14}" {FONT} font-size="13">{total}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)
