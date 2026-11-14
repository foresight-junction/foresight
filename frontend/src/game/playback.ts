// Timeline over a Replay: which tick is showing, how far its animation is, and the Frame to draw.
// The whole replay is planned once at load (model.ts), so seeking is just an index and never replays
// animations. Owner: agent D (playback + animation).

import type { Effect, Frame, PatientEntity, StaffEntity, VehicleEntity } from "../replay/frame";
import type { Replay, ReplayTick, Staff, Zone } from "../replay/types";
import type { Layout } from "../world/layout";
import { buildModel, type PatientRecord, type ReplayModel, type TickMarkers } from "./model";
import { easedAt, linearAt, poseAt, spinFacing, stepAt } from "./motion";

// From this speed on, crowds move in lockstep: staggering at 8x+ reads as lag.
const FAST_SPEED = 8;

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
    public replay: Replay,
    private layout: Layout,
  ) {
    this.model = buildModel(replay, layout);
  }

  get tickCount(): number {
    return this.replay.ticks.length;
  }

  // A live episode still being played: its last tick is the one the agent is deciding right now.
  get live(): boolean {
    const s = this.replay.meta.live?.state;
    return s !== undefined && s !== "done";
  }

  // Live mode: the replay grew (or its status changed). Re-plans everything, keeps the position, so a
  // viewer waiting at the live edge carries straight on into the new tick.
  setReplay(replay: Replay): void {
    this.replay = replay;
    this.model = buildModel(replay, this.layout);
    if (this.tick > this.tickCount - 1) this.setTick(this.tickCount - 1);
  }

  current(): ReplayTick {
    return this.replay.ticks[this.tick];
  }

  update(dtMs: number): void {
    if (!this.playing || dtMs <= 0) return;
    this.phase += (dtMs / 1000) * this.speed;
    // Live edge: hold the agent's current tick at its observation (phase 0) until its decision arrives.
    if (this.live && this.tick >= this.tickCount - 1) {
      this.phase = 0;
      return;
    }
    while (this.phase >= 1) {
      if (this.live && this.tick + 1 >= this.tickCount - 1) {
        this.phase = 0;
        this.setTick(this.tick + 1);
        break;
      }
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
    if (!this.live && this.tick >= this.tickCount - 1 && this.phase >= 1) this.seek(0);
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
    const fast = this.speed >= FAST_SPEED;
    const patients: PatientEntity[] = [];
    for (const p of tm.patients) {
      const alpha = linearAt(p.alpha, ph);
      if (alpha <= 0) continue;
      const pose = poseAt(p.from, p.legs, ph, fast);
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
      const pose = poseAt(s.from, s.legs, ph, fast);
      const spin = s.spin ? spinFacing(s.spin[0], s.spin[1], ph) : null;
      staff.push({
        kind: "staff",
        id: s.id,
        role: s.role,
        agency: s.agency,
        location,
        status,
        fatigue: linearAt(s.fatigue, ph),
        moving: pose.moving,
        facing: spin ?? pose.facing,
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
    const vehicles: VehicleEntity[] = [];
    for (const v of tm.vehicles) {
      if (ph < v.y[0].at || ph > v.y[v.y.length - 1].at) continue;
      const y = easedAt(v.y, ph);
      vehicles.push({
        kind: "ambulance",
        id: v.id,
        x: v.x,
        y,
        doorsOpen: Math.max(0, Math.min(1, linearAt(v.doors, ph))),
        siren: true,
        moving: Math.abs(easedAt(v.y, ph + 0.002) - y) > 0.01,
      });
    }
    const status = stepAt(tm.status, ph);
    return {
      tick: this.replay.ticks[t].tick,
      phase: ph,
      patients,
      staff,
      vehicles,
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
