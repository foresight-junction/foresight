// Timeline over a Replay: which tick is showing, how far its animation is, and the Frame to draw.
// The whole replay is planned once at load (model.ts), so seeking is just an index and never replays
// animations. Owner: agent D (playback + animation).

import type { Effect, Frame, PatientEntity, StaffEntity } from "../replay/frame";
import type { Replay, ReplayTick, Staff, Zone } from "../replay/types";
import type { Layout } from "../world/layout";
import { buildModel, type PatientRecord, type ReplayModel, type TickMarkers } from "./model";
import { linearAt, poseAt, stepAt } from "./motion";

export type { PatientRecord, TickMarkers } from "./model";

export type EntityInfo =
  | ({ kind: "patient" } & PatientRecord)
  | ({ kind: "staff" } & Staff);

export class Playback {
  tick = 0;
  phase = 0; // 0..1 through the current tick
  playing = false;
  speed = 2; // ticks per second
  private listeners: ((tick: number) => void)[] = [];
  private model: ReplayModel;

  constructor(
    readonly replay: Replay,
    layout: Layout,
  ) {
    this.model = buildModel(replay, layout);
  }

  get tickCount(): number {
    return this.replay.ticks.length;
  }

  current(): ReplayTick {
    return this.replay.ticks[this.tick];
  }

  update(dtMs: number): void {
    if (!this.playing || dtMs <= 0) return;
    this.phase += (dtMs / 1000) * this.speed;
    while (this.phase >= 1) {
      if (this.tick >= this.tickCount - 1) {
        this.phase = 1;
        this.playing = false;
        break;
      }
      this.phase -= 1;
      this.setTick(this.tick + 1);
    }
  }

  seek(tick: number): void {
    this.phase = 0;
    this.setTick(Math.max(0, Math.min(this.tickCount - 1, Math.round(tick))));
  }

  // At the very end, play starts over from the first tick.
  play(): void {
    if (this.tick >= this.tickCount - 1 && this.phase >= 1) this.seek(0);
    this.playing = true;
  }

  pause(): void {
    this.playing = false;
  }

  toggle(): void {
    if (this.playing) this.pause();
    else this.play();
  }

  stepForward(): void {
    this.seek(this.tick + 1);
  }

  stepBack(): void {
    this.seek(this.tick - 1);
  }

  onTick(cb: (tick: number) => void): void {
    this.listeners.push(cb);
  }

  // Per-tick counts for the timeline scrubber (deaths, arrivals, rejections, events...).
  timelineMarkers(): TickMarkers[] {
    return this.model.markers;
  }

  // A patient's whole story (arrival, admission, outcome) or a staff member as observed this tick.
  entityInfo(id: string): EntityInfo | null {
    const p = this.model.patients.get(id);
    if (p) return { kind: "patient", ...p };
    const s = this.current().obs.staff.find((x) => x.id === id);
    return s ? { kind: "staff", ...s } : null;
  }

  frame(): Frame {
    const t = this.tick;
    const ph = this.phase;
    const tm = this.model.ticks[t];
    const patients: PatientEntity[] = [];
    for (const p of tm.patients) {
      const alpha = linearAt(p.alpha, ph);
      if (alpha <= 0) continue;
      const pose = poseAt(p.from, p.legs, ph);
      const state = stepAt(p.state, ph);
      patients.push({
        kind: "patient",
        id: p.id,
        esi: stepAt(p.esi, ph),
        state,
        bed: stepAt(p.bed, ph),
        covered: stepAt(p.covered, ph),
        waitingForCt: stepAt(p.waitingForCt, ph),
        progress: state === "in_bed" || state === "dead" ? Math.min(1, linearAt(p.progress, ph)) : 0,
        needsCt: stepAt(p.needsCt, ph),
        moving: pose.moving,
        facing: pose.facing,
        alpha,
        x: pose.x,
        y: pose.y,
      });
    }
    const zoneCoverage: Record<Zone, number> = { resus: 0, acute: 0, fast_track: 0 };
    const staff: StaffEntity[] = [];
    for (const s of tm.staff) {
      const alpha = linearAt(s.alpha, ph);
      const status = stepAt(s.status, ph);
      const location = stepAt(s.location, ph);
      if (status === "on_shift" && location !== "rest") zoneCoverage[location] += stepAt(s.countsAs, ph);
      if (alpha <= 0) continue;
      const pose = poseAt(s.from, s.legs, ph);
      staff.push({
        kind: "staff",
        id: s.id,
        role: s.role,
        agency: s.agency,
        location,
        status,
        fatigue: linearAt(s.fatigue, ph),
        moving: pose.moving,
        facing: pose.facing,
        alpha,
        x: pose.x,
        y: pose.y,
      });
    }
    for (const z of Object.keys(zoneCoverage) as Zone[]) zoneCoverage[z] = Math.round(zoneCoverage[z] * 10) / 10;
    const effects: Effect[] = [];
    for (let k = Math.max(0, t - 2); k <= t; k++) {
      for (const e of this.model.ticks[k].effects) {
        const age = (t - k + ph - e.at) / e.life;
        if (age < 0 || age >= 1) continue;
        effects.push(e.text === undefined ? { kind: e.kind, age, x: e.x, y: e.y } : { kind: e.kind, age, x: e.x, y: e.y, text: e.text });
      }
    }
    const status = stepAt(tm.status, ph);
    return {
      tick: t,
      phase: ph,
      patients,
      staff,
      effects,
      ct: { ...status.ct },
      diversion: { ...status.diversion },
      activeEvents: [...status.activeEvents],
      zoneCoverage,
    };
  }

  private setTick(tick: number): void {
    this.tick = tick;
    for (const cb of this.listeners) cb(tick);
  }
}
