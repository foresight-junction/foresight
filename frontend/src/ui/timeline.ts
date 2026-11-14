// Episode-wide timeline data for the scrubber and the mistakes list, computed from replay.ticks.
// Pure functions only. Owner: agent E (HUD).

import type { Esi, Replay } from "../replay/types";
import { clockForTick, euro, eventName, patientEsi } from "./describe";

export interface TickMarks {
  deaths: number;
  faints: number;
  rejected: number;
  spend: number; // euros spent this tick (agency + repair)
  left: number;
  waiting: number; // queue length the policy saw
}

export interface Band {
  kind: string; // staff_sickness | flu_wave | ct_breakdown | bus_crash | diversion
  start: number;
  end: number; // exclusive
}

export interface TimelineData {
  n: number;
  marks: TickMarks[];
  bands: Band[];
  maxWaiting: number;
}

const EPISODE_TICKS = 144;

export function buildTimeline(replay: Replay): TimelineData {
  // A live episode keeps the full 144-tick width, so the timeline fills in from the left as it plays.
  const n = replay.meta.live ? Math.max(EPISODE_TICKS, replay.ticks.length) : replay.ticks.length;
  const marks: TickMarks[] = replay.ticks.map((t) => {
    const m: TickMarks = { deaths: 0, faints: 0, rejected: 0, spend: 0, left: 0, waiting: t.obs.waiting.length };
    for (const e of t.events) {
      if (e.event === "death") m.deaths++;
      else if (e.event === "faint") m.faints++;
      else if (e.event === "left") m.left++;
      else if (e.event === "spend") m.spend += Number(e.amount) || 0;
    }
    m.rejected = t.results.filter((r) => !r.ok).length;
    return m;
  });

  const bands: Band[] = [];
  const open = new Map<string, Band>();
  for (const t of replay.ticks) {
    for (const e of t.events) {
      const kind = String(e.kind);
      if (e.event === "event_start") {
        const b: Band = { kind, start: t.tick, end: typeof e.ends_tick === "number" ? e.ends_tick : n };
        open.set(kind, b);
        bands.push(b);
      } else if (e.event === "event_end") {
        const b = open.get(kind);
        if (b) b.end = t.tick; // a repaired CT ends before ends_tick
        open.delete(kind);
      }
    }
  }
  for (const b of bands) b.end = Math.max(b.start + 1, Math.min(b.end, n));

  // Diversion: ticks where the observation says it is active or where arrivals were turned away.
  let runStart = -1;
  for (let i = 0; i <= n; i++) {
    const t = replay.ticks[i];
    const on = !!t && (t.obs.diversion.active || t.events.some((e) => e.event === "diverted"));
    if (on && runStart < 0) runStart = i;
    if (!on && runStart >= 0) {
      bands.push({ kind: "diversion", start: runStart, end: i });
      runStart = -1;
    }
  }

  return { n, marks, bands, maxWaiting: Math.max(1, ...marks.map((m) => m.waiting)) };
}

export interface Mistake {
  tick: number;
  icon: string;
  text: string;
  esi?: Esi;
}

const CAUSE: Record<string, string> = {
  waiting: "died waiting",
  uncovered_bed: "died on an uncovered bed",
  fatigue: "died, team too tired",
};

// The episode's avoidable harm: deaths, faints and patients who left, in tick order.
export function findMistakes(replay: Replay): Mistake[] {
  const out: Mistake[] = [];
  for (const t of replay.ticks) {
    for (const e of t.events) {
      const p = String(e.patient ?? "");
      if (e.event === "death") {
        const esi = patientEsi(t.obs, p);
        out.push({ tick: t.tick, icon: "skull", text: `${p}${esi ? ` (ESI ${esi})` : ""} ${CAUSE[String(e.cause)] ?? "died"}`, esi });
      } else if (e.event === "faint") {
        out.push({ tick: t.tick, icon: "dizzy", text: `${String(e.staff)} fainted` });
      } else if (e.event === "left") {
        const esi = patientEsi(t.obs, p);
        out.push({ tick: t.tick, icon: "door", text: `${p}${esi ? ` (ESI ${esi})` : ""} left untreated`, esi });
      }
    }
  }
  return out;
}

export function tickSummary(data: TimelineData, tick: number): string {
  const m = data.marks[tick];
  if (!m) return "";
  const parts = [`tick ${tick} · ${clockForTick(tick)}`];
  if (m.deaths) parts.push(`${m.deaths} death${m.deaths > 1 ? "s" : ""}`);
  if (m.faints) parts.push(`${m.faints} faint${m.faints > 1 ? "s" : ""}`);
  if (m.rejected) parts.push(`${m.rejected} rejected`);
  if (m.spend) parts.push(`${euro(m.spend)} spent`);
  for (const b of data.bands) {
    if (tick >= b.start && tick < b.end) parts.push(b.kind === "diversion" ? "diverting" : eventName(b.kind));
  }
  parts.push(`${m.waiting} waiting`);
  return parts.join(" · ");
}
