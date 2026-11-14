import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { Playback } from "../game/playback";
import { buildLayout } from "../world/layout";
import { applyLiveMessage, emptyLive, liveReplay, type LiveState } from "./live";
import type { LiveMessage, Replay, ReplayMeta, ReplayTick } from "./types";

const reference = JSON.parse(
  readFileSync(new URL("../../public/replays/reference-seed42.json", import.meta.url), "utf-8"),
) as Replay;
const layout = buildLayout();
const PRE_OBS = new Set(["episode_start", "arrival", "diverted", "event_start", "event_end"]);

const meta = (state: "thinking" | "done"): ReplayMeta => ({
  ...reference.meta,
  reward: state === "done" ? reference.meta.reward : null,
  score: state === "done" ? reference.meta.score : null,
  live: { agent: "reference", model: null, state },
});

// What the live server sends for tick k while the agent decides: obs and pre-observation events only.
const headOf = (k: number): ReplayTick => ({
  ...reference.ticks[k],
  actions: [],
  results: [],
  events: reference.ticks[k].events.filter((e) => PRE_OBS.has(e.event)),
});

function liveUpTo(k: number): LiveState {
  // Finished ticks 0..k-1, head k.
  let s = applyLiveMessage(emptyLive(), {
    type: "snapshot",
    meta: meta("thinking"),
    ticks: [],
    head: headOf(0),
    final_obs: null,
  });
  for (let t = 0; t < k; t++) {
    const head = t + 1 < reference.ticks.length ? headOf(t + 1) : null;
    s = applyLiveMessage(s, { type: "step", meta: meta("thinking"), tick: reference.ticks[t], head });
  }
  return s;
}

describe("live messages", () => {
  it("shows nothing until the first observation", () => {
    const s = applyLiveMessage(emptyLive(), { type: "snapshot", meta: meta("thinking"), ticks: [], head: null, final_obs: null });
    expect(liveReplay(s)).toBeNull();
  });

  it("grows a replay of finished ticks plus the head", () => {
    const r = liveReplay(liveUpTo(10))!;
    expect(r.ticks).toHaveLength(11);
    expect(r.ticks[9]).toBe(reference.ticks[9]);
    expect(r.ticks[10].actions).toEqual([]);
    expect(r.final_obs).toBe(reference.ticks[10].obs);
  });

  it("replaces a resent tick instead of duplicating it", () => {
    let s = liveUpTo(5);
    const again: LiveMessage = { type: "step", meta: meta("thinking"), tick: reference.ticks[4], head: headOf(5) };
    s = applyLiveMessage(s, again);
    expect(s.ticks.map((t) => t.tick)).toEqual([0, 1, 2, 3, 4]);
  });

  it("ends with the final observation and no head", () => {
    let s = liveUpTo(reference.ticks.length);
    s = applyLiveMessage(s, { type: "done", meta: meta("done"), final_obs: reference.final_obs });
    const r = liveReplay(s)!;
    expect(r.ticks).toHaveLength(reference.ticks.length);
    expect(r.final_obs).toBe(reference.final_obs);
    expect(new Playback(r, layout).live).toBe(false);
  });
});

describe("Playback at the live edge", () => {
  it("holds the agent's tick at its observation, then plays on when the decision arrives", () => {
    const pb = new Playback(liveReplay(liveUpTo(3))!, layout);
    expect(pb.live).toBe(true);
    pb.seek(2);
    pb.play();
    pb.update(5000); // far more than one tick at 2x
    expect([pb.tick, pb.phase, pb.playing]).toEqual([3, 0, true]);
    expect(pb.frame().vehicles).toHaveLength(0);

    pb.setReplay(liveReplay(liveUpTo(4))!);
    pb.update(250); // half a tick at 2x
    expect(pb.tick).toBe(3);
    expect(pb.phase).toBeCloseTo(0.5);
    pb.update(5000);
    expect([pb.tick, pb.phase]).toEqual([4, 0]);
  });

  it("plans the head tick of a live replay like the same tick of the file", () => {
    // Tick 9 is finished in both; its animation needs tick 10's arrivals, which the head carries.
    const live = new Playback(liveReplay(liveUpTo(10))!, layout);
    const file = new Playback(reference, layout);
    for (const pb of [live, file]) {
      pb.seek(9);
      pb.phase = 0.6;
    }
    const ids = (pb: Playback) => pb.frame().patients.map((p) => `${p.id}@${Math.round(p.x)},${Math.round(p.y)}`).sort();
    expect(ids(live)).toEqual(ids(file));
  });
});
