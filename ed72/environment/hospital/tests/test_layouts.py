"""Issue #9 bed layouts: config/layouts/<name>.json, selected by the config's `layout` key."""

import json
from pathlib import Path

import pytest
from ed72_sim import constants as c
from ed72_sim.config import Config, load_config
from ed72_sim.engine import Simulation
from ed72_sim.rules.layouts import LAYOUT_DIR, load_layout
from ed72_sim.world import generate_world
from sim_fixtures import admit


def layout_config(tmp_path: Path, name: object) -> Config:
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"layout": name}), encoding="utf-8")
    return load_config(str(path))


def admitted_beds(sim: Simulation) -> set[str]:
    return {e["bed"] for e in sim.events if e.get("event") == "admitted"}


def test_default_layout_file_matches_the_constants() -> None:
    raw = json.loads((LAYOUT_DIR / "default.json").read_text(encoding="utf-8"))
    assert raw["beds"] == c.BEDS
    assert generate_world(1).bed_counts == tuple(c.BEDS[z] for z in c.ZONES)


def test_compact_layout_bed_counts_and_ids(tmp_path: Path) -> None:
    assert load_layout("compact") == (2, 9, 6)
    sim = Simulation(generate_world(1, layout_config(tmp_path, "compact")))
    rows = [(b["zone"], b["bed"]) for b in sim.observe()["beds"]]
    assert rows == (
        [("resus", "R1"), ("resus", "R2")]
        + [("acute", f"A{i}") for i in range(1, 10)]
        + [("fast_track", f"F{i}") for i in range(1, 7)]
    )


def test_compact_layout_fills_a9_and_never_r3(tmp_path: Path) -> None:
    sim = Simulation(generate_world(2, layout_config(tmp_path, "compact")))
    while sim.tick < 40:  # nobody on shift, so beds fill and stay full
        waiting = sim.observe()["waiting"]
        sim.step([admit(p["id"], z) for p in waiting for z in ("resus", "acute")])
    assert "A9" in admitted_beds(sim)
    assert "R3" not in admitted_beds(sim)
    assert {"R1", "R2"} <= admitted_beds(sim)


def test_compact_episode_is_deterministic(tmp_path: Path) -> None:
    def run() -> str:
        sim = Simulation(generate_world(5, layout_config(tmp_path, "compact")))
        while not sim.finished:
            sim.step([admit(p["id"], "acute") for p in sim.observe()["waiting"]])
        return json.dumps(sim.events)

    assert run() == run()


@pytest.mark.parametrize("name", ["nope", "../default", "", 3])
def test_unknown_layout_raises(tmp_path: Path, name: object) -> None:
    with pytest.raises(ValueError):
        layout_config(tmp_path, name)
