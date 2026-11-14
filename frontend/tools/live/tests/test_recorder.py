import json
import queue
from pathlib import Path

import pytest
from ed72_sim.engine import Simulation
from ed72_sim.world import generate_world
from policy import ReferencePolicy
from recorder import LiveRecorder
from serve import make_meta
from server import ToolHost

from export_replay import export

SEED = 42


def drain(q: queue.Queue[str]) -> list[dict]:
    out = []
    while not q.empty():
        out.append(json.loads(q.get_nowait()))
    return out


def comparable(tick: dict) -> dict:
    """A tick without the thought and event seq numbers: the live log also holds the agent's rules and
    observe calls, so seq is offset from export_replay's log while every sim line is the same."""
    events = [{k: v for k, v in e.items() if k != "seq"} for e in tick["events"]]
    return {**{k: v for k, v in tick.items() if k != "thought"}, "events": events}


def new_recorder(tmp_path: Path) -> LiveRecorder:
    return LiveRecorder(
        Simulation(generate_world(SEED), tmp_path / "events.jsonl"), make_meta("reference", SEED, None)
    )


def play_reference(host: ToolHost, max_steps: int | None = None) -> None:
    policy = ReferencePolicy()
    host.call("rules", {})
    obs = host.call("observe", {})
    steps = 0
    while not obs["finished"] and (max_steps is None or steps < max_steps):
        obs = host.call("step", {"actions": policy.actions(obs)})["observation"]
        steps += 1


@pytest.fixture(scope="module")
def expected() -> dict:
    return export("reference", SEED)


def test_ticks_match_export_replay(tmp_path, expected):
    rec = new_recorder(tmp_path)
    play_reference(ToolHost(rec, "HANDBOOK"))
    assert len(rec.ticks) == len(expected["ticks"]) == 144
    for got, want in zip(rec.ticks, expected["ticks"], strict=True):
        assert comparable(got) == comparable(want), f"tick {want['tick']} differs"
    assert rec.final_obs == expected["final_obs"]
    assert rec.meta["reward"] == expected["meta"]["reward"]
    assert rec.meta["live"]["state"] == "done"


def test_stream_messages(tmp_path, expected):
    rec = new_recorder(tmp_path)
    q, first = rec.subscribe()
    snapshot = json.loads(first)
    assert snapshot["type"] == "snapshot"
    assert snapshot["ticks"] == [] and snapshot["final_obs"] is None
    head = snapshot["head"]
    assert head["tick"] == 0 and head["actions"] == [] and head["results"] == []
    assert head["obs"] == expected["ticks"][0]["obs"]
    assert {e["event"] for e in head["events"]} >= {"episode_start", "arrival"}

    rec.set_state("thinking")
    rec.set_state("thinking")  # unchanged: no message
    rec.set_state("acting")
    rec.set_thought("admit the ESI 2s first")
    play_reference(ToolHost(rec, "HANDBOOK"), max_steps=3)
    messages = drain(q)
    assert [m["type"] for m in messages] == ["status", "status", "step", "step", "step"]
    assert [m["meta"]["live"]["state"] for m in messages[:2]] == ["thinking", "acting"]
    steps = messages[2:]
    assert [m["tick"]["tick"] for m in steps] == [0, 1, 2]
    assert steps[0]["tick"]["thought"] == "admit the ESI 2s first"
    assert "thought" not in steps[1]["tick"]
    for i, m in enumerate(steps):
        assert comparable(m["tick"]) == comparable(expected["ticks"][i])
        nxt = expected["ticks"][i + 1]
        assert m["head"]["tick"] == i + 1 and m["head"]["obs"] == nxt["obs"]
        # Events known before the agent acts are a prefix of the finished tick's events.
        head_events = comparable(m["head"])["events"]
        assert head_events == comparable(nxt)["events"][: len(head_events)]
        assert m["meta"]["reward"] is None

    late_q, late = rec.subscribe()
    late = json.loads(late)
    assert late["ticks"] == [m["tick"] for m in steps]
    assert late["head"] == steps[-1]["head"]

    play_reference(ToolHost(rec, "HANDBOOK"))
    messages = drain(late_q)
    assert [m["type"] for m in messages] == ["step"] * 141 + ["done"]
    assert messages[-2]["head"] is None
    done = messages[-1]
    assert done["meta"]["reward"] == expected["meta"]["reward"]
    assert done["meta"]["score"]["reward"] == done["meta"]["reward"]
    assert done["meta"]["live"]["state"] == "done"
    assert done["final_obs"] == expected["final_obs"] and done["final_obs"]["finished"]

    _, after = rec.subscribe()
    after = json.loads(after)
    assert after["head"] is None and len(after["ticks"]) == 144
    assert after["final_obs"] == expected["final_obs"]
    rec.set_state("thinking")  # after done the state stays done
    assert rec.meta["live"]["state"] == "done"


def test_finish_runs_out_the_episode(tmp_path):
    rec = new_recorder(tmp_path)
    q, _ = rec.subscribe()
    play_reference(ToolHost(rec, "HANDBOOK"), max_steps=10)
    rec.set_state("error", "boom")
    rec.finish()
    rec.finish()  # idempotent
    assert len(rec.ticks) == 144
    assert all(t["actions"] == [] and t["results"] == [] for t in rec.ticks[10:])
    assert [t["tick"] for t in rec.ticks] == list(range(144))
    messages = drain(q)
    assert [m["type"] for m in messages].count("done") == 1
    assert rec.meta["live"] == {"agent": "reference", "model": None, "state": "done", "error": "boom"}
    assert rec.final_obs["finished"]
    # Only the 10 real steps reach the log as agent lines.
    steps = [e for e in rec.sim.events if e.get("src") == "agent" and e.get("tool") == "step"]
    assert len(steps) == 10


def test_saves_the_replay_after_every_tick_and_at_the_end(tmp_path):
    save = tmp_path / "run.json"
    rec = LiveRecorder(
        Simulation(generate_world(SEED), tmp_path / "events.jsonl"),
        make_meta("reference", SEED, None),
        save,
    )
    host = ToolHost(rec, "HANDBOOK")
    play_reference(host, max_steps=5)
    partial = json.loads(save.read_text(encoding="utf-8"))
    # Mid-episode: a valid Replay of the finished ticks, ending at the current observation.
    assert [t["tick"] for t in partial["ticks"]] == [0, 1, 2, 3, 4]
    assert partial["final_obs"]["tick"] == 5
    assert partial["meta"]["reward"] is None
    rec.finish()
    final = json.loads(save.read_text(encoding="utf-8"))
    assert len(final["ticks"]) == 144
    assert final["final_obs"]["finished"]
    assert final["meta"]["live"]["state"] == "done"
    assert final["meta"]["reward"] == rec.meta["reward"]
    assert not save.with_name("run.json.tmp").exists()
