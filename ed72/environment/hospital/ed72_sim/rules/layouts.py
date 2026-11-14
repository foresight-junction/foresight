"""Bed layouts (issue #9): config/layouts/<name>.json gives the bed count per zone.

Bed ids stay R/A/F-numbered, so the observation keeps its shape; only the number of rows changes.
"""

import json
from pathlib import Path

from ed72_sim import constants as c

LAYOUT_DIR = Path(__file__).resolve().parents[2] / "config" / "layouts"
DEFAULT_LAYOUT = "default"
DEFAULT_BEDS: tuple[int, ...] = tuple(c.BEDS[z] for z in c.ZONES)


def load_layout(name: str) -> tuple[int, ...]:
    """Bed counts in c.ZONES order. Raises ValueError on an unknown name or a bad file."""
    if name == DEFAULT_LAYOUT:
        return DEFAULT_BEDS
    if not isinstance(name, str) or not name.replace("_", "").isalnum():
        raise ValueError(f"layout must be a plain name, got {name!r}")
    path = LAYOUT_DIR / f"{name}.json"
    if not path.is_file():
        raise ValueError(f"unknown layout {name!r}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    beds = raw.get("beds") if isinstance(raw, dict) else None
    if not isinstance(beds, dict) or set(beds) != set(c.ZONES):
        raise ValueError(f"layout {name!r}: beds must name exactly {list(c.ZONES)}")
    counts = tuple(beds[z] for z in c.ZONES)
    if not all(isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= 99 for n in counts):
        raise ValueError(f"layout {name!r}: bed counts must be integers 1..99")
    return counts
