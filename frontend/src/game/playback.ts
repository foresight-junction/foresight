// Timeline over a Replay: which tick is showing, how far its animation is, and the Frame to draw.
// Owner: agent D (playback + animation). STUB: snaps everyone to their slot, no walking or effects.

import type { Frame, PatientEntity, StaffEntity } from "../replay/frame";
import type { Observation, Replay, ReplayTick, Zone } from "../replay/types";
import type { Layout } from "../world/layout";

export class Playback {
  tick = 0;
  phase = 0; // 0..1 through the current tick
  playing = false;
  speed = 2; // ticks per second
  private listeners: ((tick: number) => void)[] = [];

  constructor(
    readonly replay: Replay,
    private layout: Layout,
  ) {}

  get tickCount(): number {
    return this.replay.ticks.length;
  }

  current(): ReplayTick {
    return this.replay.ticks[this.tick];
  }

  update(dtMs: number): void {
    if (!this.playing) return;
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

  play(): void {
    this.playing = true;
  }

  pause(): void {
    this.playing = false;
  }

  toggle(): void {
    this.playing = !this.playing;
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

  frame(): Frame {
    const obs: Observation = this.current().obs;
    const L = this.layout;
    const patients: PatientEntity[] = [];
    obs.waiting.forEach((w, i) => {
      const at = L.waitingSlot(i);
      patients.push({ kind: "patient", id: w.id, esi: w.esi, state: "waiting", bed: null, covered: false,
        waitingForCt: false, progress: 0, needsCt: w.needs_ct, moving: false, facing: "down", alpha: 1, ...at });
    });
    for (const b of obs.beds) {
      if (!b.patient || !b.esi) continue;
      const at = L.beds[b.bed];
      patients.push({ kind: "patient", id: b.patient, esi: b.esi, state: "in_bed", bed: b.bed,
        covered: !!b.covered, waitingForCt: !!b.waiting_for_ct,
        progress: (b.treated_ticks ?? 0) / (b.treatment_ticks || 1), needsCt: false, moving: false,
        facing: "down", alpha: 1, x: at.x, y: at.y + 4 });
    }
    const perZone: Record<string, number> = {};
    let resting = 0;
    const staff: StaffEntity[] = obs.staff.map((s) => {
      let at = L.offstage;
      if (s.status === "on_shift" && s.location !== "rest") {
        const i = perZone[s.location] ?? 0;
        perZone[s.location] = i + 1;
        at = L.staffSlot(s.location, i);
      } else if (s.status === "resting") {
        at = L.restSlot(resting++);
      }
      return { kind: "staff", id: s.id, role: s.role, agency: s.agency, location: s.location, status: s.status,
        fatigue: s.fatigue, moving: false, facing: "down", alpha: 1, ...at };
    });
    const zoneCoverage: Record<Zone, number> = { resus: 0, acute: 0, fast_track: 0 };
    for (const s of obs.staff) {
      if (s.status === "on_shift" && s.location !== "rest") zoneCoverage[s.location] += s.counts_as;
    }
    return {
      tick: obs.tick,
      phase: this.phase,
      patients,
      staff,
      effects: [],
      ct: { working: obs.ct.working, downTicksLeft: obs.ct.down_ticks_left },
      diversion: { active: obs.diversion.active, ticksLeft: obs.diversion.ticks_left },
      activeEvents: [],
      zoneCoverage,
    };
  }

  private setTick(tick: number): void {
    this.tick = tick;
    for (const cb of this.listeners) cb(tick);
  }
}
