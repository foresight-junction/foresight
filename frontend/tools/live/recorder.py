"""The sim surface the hospital ToolHost serves, plus the live replay the browser watches.

LiveRecorder wraps one ed72_sim Simulation. The MCP server calls observe/step/record_call on it
exactly as it would on the bare sim, so the event log (and the score) is the real one. Each
successful step becomes a finished ReplayTick, built the way export_replay.export() builds them,
and is pushed to every subscriber as a LiveMessage (frontend/src/replay/types.ts) in compact JSON.
"""

import copy
import json
import os
import queue
import threading
from pathlib import Path
from typing import Any

from ed72_sim.engine import Simulation
from ed72_sim.scoring import score


def _encode(message: dict) -> str:
    return json.dumps(message, separators=(",", ":"))


class LiveRecorder:
    def __init__(self, sim: Simulation, meta: dict, save_path: Path | None = None) -> None:
        self.sim = sim
        self.meta = meta
        # Where the replay so far is rewritten after every tick, so a crash or Ctrl+C loses nothing.
        self.save_path = save_path
        self.ticks: list[dict] = []
        self.final_obs: dict | None = None
        # One re-entrant lock for the sim and the replay: the MCP server thread steps, the agent
        # thread sets thoughts and states, and HTTP threads take snapshots.
        self.lock = threading.RLock()
        self._by_tick: dict[int, list[dict]] = {}
        self._seen = 0
        self._thought: str | None = None
        self._subscribers: list[queue.Queue[str]] = []
        self._collect()

    # --- the Sim protocol server.ToolHost uses --------------------------------------------------

    def observe(self) -> dict:
        with self.lock:
            return self.sim.observe()

    def record_call(self, tool: str, args: dict, result: dict) -> None:
        with self.lock:
            self.sim.record_call(tool, args, result)

    def step(self, actions: list[dict]) -> dict:
        with self.lock:
            obs = self.sim.observe()
            out = self.sim.step(actions)
            thought, self._thought = self._thought, None
            if "error" in out:
                return out
            self._add_tick(obs, actions, out["results"], thought)
            if self.sim.finished:
                self._finish()
            return out

    # --- agent side -----------------------------------------------------------------------------

    def set_thought(self, thought: str | None) -> None:
        """Attach the agent's reasoning to the next step that reaches the sim."""
        with self.lock:
            self._thought = thought

    def set_state(self, state: str, error: str | None = None) -> None:
        with self.lock:
            live = self.meta["live"]
            if live["state"] == "done" or (live["state"] == state and live.get("error") == error):
                return
            live["state"] = state
            if error is not None:
                live["error"] = error
            self._publish({"type": "status", "meta": self.meta})

    def finish(self) -> None:
        """End the episode when the agent stops early (call cap, crash): the rest runs with no actions."""
        with self.lock:
            if self.final_obs is None:
                self._finish()

    # --- browser side ---------------------------------------------------------------------------

    def subscribe(self) -> tuple[queue.Queue[str], str]:
        """Register a subscriber; returns its queue and the snapshot to send first, taken atomically."""
        with self.lock:
            q: queue.Queue[str] = queue.Queue()
            self._subscribers.append(q)
            snapshot = {
                "type": "snapshot",
                "meta": self.meta,
                "ticks": self.ticks,
                "head": self._head(),
                "final_obs": self.final_obs,
            }
            return q, _encode(snapshot)

    def unsubscribe(self, q: queue.Queue[str]) -> None:
        with self.lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    # --- internals (caller holds the lock) ------------------------------------------------------

    def _collect(self) -> None:
        for e in self.sim.events[self._seen :]:
            if e.get("src") == "sim":
                self._by_tick.setdefault(e["t"], []).append(e)
        self._seen = len(self.sim.events)

    def _add_tick(self, obs: dict, actions: list[dict], results: list[dict], thought: str | None) -> None:
        self._collect()
        # After step t every line with t == tick is written: arrivals before obs, outcomes after.
        tick: dict[str, Any] = {
            "tick": obs["tick"],
            "obs": obs,
            "actions": copy.deepcopy(actions),
            "results": results,
            "events": self._by_tick.get(obs["tick"], []),
        }
        if thought is not None:
            tick["thought"] = thought
        self.ticks.append(tick)
        self._publish({"type": "step", "meta": self.meta, "tick": tick, "head": self._head()})
        self._save()

    def _head(self) -> dict | None:
        if self.sim.finished:
            return None
        self._collect()
        return {
            "tick": self.sim.tick,
            "obs": self.sim.observe(),
            "actions": [],
            "results": [],
            "events": list(self._by_tick.get(self.sim.tick, [])),
        }

    def _finish(self) -> None:
        # Same ticks Simulation.run_to_end() would run, one at a time so the replay keeps one
        # ReplayTick per sim tick. Like run_to_end it writes no agent lines, so the score is unchanged.
        while not self.sim.finished:
            obs = self.sim.observe()
            self.sim._finish_tick()
            self._add_tick(obs, [], [], None)
        self.final_obs = self.sim.observe()
        s = score(self.sim.events)
        self.meta["reward"] = s["reward"]
        self.meta["score"] = s
        self.meta["live"]["state"] = "done"
        self._publish({"type": "done", "meta": self.meta, "final_obs": self.final_obs})
        self._save()

    def _save(self) -> None:
        # A plain Replay file (frontend/src/replay/types.ts). Until the episode ends, final_obs is the
        # current observation and meta.live.state is not "done", so the viewer treats it as unfinished.
        if self.save_path is None:
            return
        replay = {
            "version": 1,
            "meta": self.meta,
            "ticks": self.ticks,
            "final_obs": self.final_obs if self.final_obs is not None else self.sim.observe(),
        }
        tmp = self.save_path.with_name(self.save_path.name + ".tmp")
        tmp.write_text(_encode(replay), encoding="utf-8")
        os.replace(tmp, self.save_path)  # atomic: a reader never sees half a file

    def _publish(self, message: dict) -> None:
        data = _encode(message)
        for q in self._subscribers:
            q.put(data)
