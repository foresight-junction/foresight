// Plain-English text for the HUD: actions, rejection reasons, sim events, warnings, score parts.
// Pure functions only (no DOM) so they can be unit tested.

import type { Action, Esi, Location, Observation, ReplayTick, ScoreSummary, SimEvent, Staff, Zone } from "../replay/types";
import { BEDS_PER_DOCTOR, BEDS_PER_NURSE } from "../world/layout";

export type Tone = "good" | "bad" | "warn" | "info" | "money" | "muted";

export interface Line {
  icon: string; // key into icons.ts
  text: string;
  tone: Tone;
  esi?: Esi;
  detail?: string; // second, dimmer line
}

export interface ActionLine extends Line {
  ok: boolean;
  reason?: string; // plain-English rejection reason
}

export interface TickActions {
  lines: ActionLine[];
  kept: string[]; // staff re-assigned to where they already were (no-op assigns)
  total: number;
  rejected: number;
}

export const ZONE_NAME: Record<Location, string> = {
  resus: "Resus",
  acute: "Acute",
  fast_track: "Fast-track",
  rest: "Rest",
};

// Ticks after arrival within which an ESI 1-5 patient should get a covered bed (SPEC §6).
export const TARGET_TICKS: Record<Esi, number> = { 1: 0, 2: 1, 3: 4, 4: 8, 5: 12 };

export const EVENT_NAME: Record<string, string> = {
  staff_sickness: "Staff sickness",
  flu_wave: "Flu wave",
  ct_breakdown: "CT breakdown",
  bus_crash: "Bus crash",
};

const AGENCY_COST = { doctor: 900, nurse: 350 } as const;
const REPAIR_COST = 2000;
// Above this many real moves in one tick, assigns are grouped by destination.
const GROUP_ASSIGNS_ABOVE = 4;

export function euro(n: number): string {
  const sign = n < 0 ? "−" : "";
  const s = String(Math.round(Math.abs(n))).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${sign}€${s}`;
}

// Tick 0 is Day 1 08:00 and each tick is 30 minutes.
export function clockForTick(tick: number): string {
  const minutes = 8 * 60 + tick * 30;
  const day = Math.floor(minutes / 1440) + 1;
  const m = minutes % 1440;
  const hh = String(Math.floor(m / 60)).padStart(2, "0");
  const mm = String(m % 60).padStart(2, "0");
  return `Day ${day} ${hh}:${mm}`;
}

export function eventName(kind: string): string {
  return EVENT_NAME[kind] ?? humanize(kind);
}

function humanize(s: string): string {
  const t = s.replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

function fat(s: Staff | undefined): string {
  return s ? String(Math.round(s.fatigue)) : "?";
}

const STATUS_WORD: Record<string, string> = {
  fainted: "fainted",
  sick: "off sick",
  agency_ordered: "not arrived yet",
  resting: "resting",
  on_shift: "on shift",
};

export function patientEsi(obs: Observation, id: string): Esi | undefined {
  return obs.waiting.find((w) => w.id === id)?.esi ?? obs.beds.find((b) => b.patient === id)?.esi;
}

// Turn a CONTRACTS ActionResult reason into words, using the observation for specifics.
export function reasonText(reason: string | undefined, action: Action, obs: Observation): string {
  switch (reason) {
    case "bad_action":
      return "malformed action";
    case "unknown_patient":
      return "no such patient";
    case "not_waiting":
      return "patient is no longer waiting";
    case "zone_not_allowed": {
      if (action.type !== "admit") return "zone not allowed";
      const esi = patientEsi(obs, action.patient);
      return `${esi ? `ESI ${esi}` : "this patient"} can't be treated in ${ZONE_NAME[action.zone] ?? action.zone}`;
    }
    case "no_free_bed":
      return action.type === "admit" ? `no free bed in ${ZONE_NAME[action.zone] ?? action.zone}` : "no free bed";
    case "unknown_staff":
      return "no such staff member";
    case "staff_unavailable": {
      if (action.type !== "assign") return "staff unavailable";
      const s = obs.staff.find((x) => x.id === action.staff);
      if (s?.status === "agency_left") return `Contract ended for ${action.staff}`;
      const why = s ? STATUS_WORD[s.status] ?? s.status : "unavailable";
      return `${action.staff} is ${why}`;
    }
    case "over_hard_limit":
      return `would break the ${euro(obs.budget.hard_limit)} hard limit`;
    case "ct_not_broken":
      return "CT is working, nothing to repair";
    case "diversion_active":
      return "a diversion is already running";
    case undefined:
      return "rejected";
    default:
      return humanize(reason);
  }
}

function isNoopAssign(a: Action, obs: Observation): boolean {
  if (a.type !== "assign") return false;
  const s = obs.staff.find((x) => x.id === a.staff);
  if (!s) return false;
  if (a.to === "rest") return s.status === "resting";
  return s.status === "on_shift" && s.location === a.to;
}

function describeAction(a: Action, obs: Observation, events: SimEvent[]): Line {
  switch (a.type) {
    case "admit": {
      const w = obs.waiting.find((x) => x.id === a.patient);
      const bed = events.find((e) => e.event === "admitted" && e.patient === a.patient)?.bed;
      const zone = ZONE_NAME[a.zone] ?? String(a.zone);
      const tags: string[] = [];
      if (w) {
        if (w.waited_ticks > 0) tags.push(`waited ${plural(w.waited_ticks, "tick")}`);
        if (w.waited_ticks > TARGET_TICKS[w.esi]) tags.push("late");
        if (w.needs_ct) tags.push("needs CT");
      }
      return {
        icon: "bed",
        text: `Admit ${a.patient}${w ? ` (ESI ${w.esi})` : ""} → ${zone}${typeof bed === "string" ? ` ${bed}` : ""}`,
        tone: "info",
        esi: w?.esi,
        detail: tags.length ? tags.join(" · ") : undefined,
      };
    }
    case "assign": {
      const s = obs.staff.find((x) => x.id === a.staff);
      if (a.to === "rest") {
        return { icon: "zzz", text: `Send ${a.staff} to rest (fatigue ${fat(s)})`, tone: "info" };
      }
      const from = s && s.status === "on_shift" && s.location !== "rest" ? ` from ${ZONE_NAME[s.location]}` : "";
      return {
        icon: "arrow",
        text: `Put ${a.staff} on ${ZONE_NAME[a.to] ?? a.to}${from} (fatigue ${fat(s)})`,
        tone: "info",
      };
    }
    case "agency":
      return {
        icon: "agency",
        text: `Hire agency ${a.role} ${euro(-AGENCY_COST[a.role])}`,
        tone: "money",
        detail: `arrives at tick ${obs.tick + 4}, stays 16 ticks`,
      };
    case "repair":
      return { icon: "wrench", text: `Repair CT ${euro(-REPAIR_COST)}`, tone: "money", detail: "back within 3 ticks" };
    case "divert":
      return {
        icon: "siren",
        text: "Divert ambulances",
        tone: "warn",
        detail: "70% of arrivals turned away for 4 ticks",
      };
    default:
      return { icon: "warn", text: `Unknown action ${JSON.stringify(a)}`, tone: "muted" };
  }
}

// This tick's actions as lines. No-op assigns are counted in `kept`; when the policy moves many
// staff in one tick, the moves are grouped per destination so the list stays readable.
export function describeActions(t: ReplayTick): TickActions {
  const lines: ActionLine[] = [];
  const kept: string[] = [];
  const moves: { staff: string; to: Location }[] = [];
  let rejected = 0;
  t.actions.forEach((a, i) => {
    const r = t.results[i];
    const ok = r ? r.ok : true;
    if (!ok) {
      rejected++;
      // The detail line describes the effect, which a rejected action never had.
      lines.push({
        ...describeAction(a, t.obs, t.events),
        ok,
        tone: "bad",
        reason: reasonText(r?.reason, a, t.obs),
        detail: undefined,
      });
      return;
    }
    if (a.type === "assign") {
      if (isNoopAssign(a, t.obs)) kept.push(a.staff);
      else moves.push({ staff: a.staff, to: a.to });
      return;
    }
    lines.push({ ...describeAction(a, t.obs, t.events), ok });
  });

  const moveLines: ActionLine[] = [];
  if (moves.length > GROUP_ASSIGNS_ABOVE) {
    const order: Location[] = ["resus", "acute", "fast_track", "rest"];
    for (const to of order) {
      const ids = moves.filter((m) => m.to === to).map((m) => m.staff);
      if (!ids.length) continue;
      const who = ids.map((id) => `${id} ${fat(t.obs.staff.find((s) => s.id === id))}`).join(" · ");
      moveLines.push({
        icon: to === "rest" ? "zzz" : "arrow",
        text: to === "rest" ? `Send ${plural(ids.length, "person", "people")} to rest` : `Put ${ids.length} on ${ZONE_NAME[to]}`,
        tone: "info",
        ok: true,
        detail: `fatigue: ${who}`,
      });
    }
  } else {
    for (const m of moves) {
      moveLines.push({ ...describeAction({ type: "assign", staff: m.staff, to: m.to }, t.obs, t.events), ok: true });
    }
  }
  // Staff moves first: they are what the policy decides before admitting into the covered beds.
  return { lines: [...moveLines, ...lines], kept, total: t.actions.length, rejected };
}

function esiCounts(list: SimEvent[]): string {
  const c: Record<number, number> = {};
  for (const e of list) if (typeof e.esi === "number") c[e.esi] = (c[e.esi] ?? 0) + 1;
  return Object.keys(c)
    .map(Number)
    .sort()
    .map((k) => `ESI ${k}×${c[k]}`)
    .join(", ");
}

const DEATH_CAUSE: Record<string, string> = {
  waiting: "died in the waiting room",
  uncovered_bed: "died on an uncovered bed",
  fatigue: "died: care team too tired",
};

function esiOf(e: SimEvent, obs: Observation): Esi | undefined {
  const p = typeof e.patient === "string" ? e.patient : "";
  return (typeof e.esi === "number" ? (e.esi as Esi) : undefined) ?? patientEsi(obs, p);
}

function eventStartText(e: SimEvent): string {
  const kind = String(e.kind);
  const until = typeof e.ends_tick === "number" ? ` until tick ${e.ends_tick}` : "";
  switch (kind) {
    case "staff_sickness":
      return `Staff sickness: 2 nurses off sick${until}`;
    case "flu_wave":
      return `Flu wave begins: +2 arrivals a tick${until}`;
    case "ct_breakdown":
      return `CT scanner broke down${typeof e.ends_tick === "number" ? ` (down until tick ${e.ends_tick} unless repaired)` : ""}`;
    case "bus_crash":
      return "Bus crash: 10 casualties incoming over 2 ticks";
    default:
      return `${eventName(kind)} started${until}`;
  }
}

function eventEndText(kind: string): string {
  switch (kind) {
    case "staff_sickness":
      return "Sick nurses are back";
    case "flu_wave":
      return "Flu wave is over";
    case "ct_breakdown":
      return "CT scanner is working again";
    case "bus_crash":
      return "Bus crash casualties have all arrived";
    default:
      return `${eventName(kind)} ended`;
  }
}

// This tick's sim events in plain words, most important first.
export function describeEvents(t: ReplayTick): Line[] {
  const ev = t.events;
  const obs = t.obs;
  const of = (name: string): SimEvent[] => ev.filter((e) => e.event === name);
  const out: Line[] = [];

  for (const e of of("event_start")) out.push({ icon: "bolt", text: eventStartText(e), tone: "warn" });
  for (const e of of("death")) {
    const esi = esiOf(e, obs);
    out.push({
      icon: "skull",
      text: `${String(e.patient)}${esi ? ` (ESI ${esi})` : ""} ${DEATH_CAUSE[String(e.cause)] ?? "died"}`,
      tone: "bad",
      esi,
    });
  }
  for (const e of of("faint")) {
    out.push({ icon: "dizzy", text: `${String(e.staff)} fainted from exhaustion (out 10 ticks)`, tone: "bad" });
  }
  for (const e of of("upgrade")) {
    out.push({
      icon: "up",
      text: `${String(e.patient)} got worse: now ESI ${String(e.esi)}${e.needs_ct ? ", needs CT" : ""}`,
      tone: "warn",
      esi: typeof e.esi === "number" ? (e.esi as Esi) : undefined,
    });
  }
  for (const e of of("left")) {
    const esi = esiOf(e, obs);
    out.push({ icon: "door", text: `${String(e.patient)}${esi ? ` (ESI ${esi})` : ""} gave up and left`, tone: "warn", esi });
  }

  const arrivals = of("arrival");
  if (arrivals.length) {
    const bus = arrivals.filter((e) => e.source === "bus").length;
    const flu = arrivals.filter((e) => e.source === "flu").length;
    const extra = [bus ? `${bus} from the bus crash` : "", flu ? `${flu} with flu` : ""].filter(Boolean).join(", ");
    out.push({
      icon: "person",
      text: `${plural(arrivals.length, "arrival")}: ${esiCounts(arrivals)}`,
      tone: "info",
      detail: extra || undefined,
    });
  }
  const diverted = of("diverted");
  if (diverted.length) {
    out.push({
      icon: "siren",
      text: `${plural(diverted.length, "patient")} diverted elsewhere: ${esiCounts(diverted)}`,
      tone: "warn",
    });
  }
  const discharged = of("discharged");
  if (discharged.length) {
    out.push({ icon: "heart", text: `${plural(discharged.length, "patient")} treated and discharged`, tone: "good" });
  }
  for (const e of of("staff_fatigue")) {
    const above = Number(e.on_shift_above_60 ?? 0);
    if (above > 0) {
      out.push({
        icon: "tired",
        text: `${above} of ${String(e.on_shift)} on-shift staff above fatigue 60 (count as 0.6)`,
        tone: "warn",
      });
    }
  }
  for (const e of of("spend")) {
    if (e.item !== "agency_doctor" && e.item !== "agency_nurse" && e.item !== "repair") {
      out.push({ icon: "coin", text: `Spent ${euro(Number(e.amount))} on ${humanize(String(e.item))}`, tone: "money" });
    }
  }
  for (const e of of("event_end")) out.push({ icon: "check", text: eventEndText(String(e.kind)), tone: "good" });
  if (of("episode_start").length) out.push({ icon: "cross", text: "Day 1, 08:00: the department opens", tone: "muted" });
  if (of("episode_end").length) out.push({ icon: "flag", text: "Day 4, 08:00: episode over", tone: "muted" });
  return out;
}

// Staff changes the event log does not name (agency arrivals and exits, returns, sick calls),
// found by diffing the previous tick's observation. Faints have their own event.
export function describeStaffChanges(prev: Observation | undefined, cur: Observation): Line[] {
  if (!prev) return [];
  const before = new Map(prev.staff.map((s) => [s.id, s.status]));
  const out: Line[] = [];
  for (const s of cur.staff) {
    const was = before.get(s.id);
    if (was === s.status) continue;
    const who = s.agency ? `${s.id} (agency ${s.role})` : s.id;
    if (was === "agency_ordered" || (was === undefined && s.status !== "agency_ordered")) {
      out.push({ icon: "person", text: `${who} arrived for a 16-tick contract`, tone: "good" });
    } else if (s.status === "agency_left") {
      out.push({ icon: "door", text: `Contract ended for ${who}`, tone: "muted" });
    } else if (s.status === "sick") {
      out.push({ icon: "sick", text: `${who} called in sick`, tone: "warn" });
    } else if (was === "sick") {
      out.push({ icon: "heart", text: `${who} is back from sick leave (resting)`, tone: "good" });
    } else if (was === "fainted") {
      out.push({ icon: "heart", text: `${who} recovered from fainting (resting, fatigue ${Math.round(s.fatigue)})`, tone: "info" });
    }
  }
  return out;
}

export interface Banner {
  text: string;
  tone: "bad" | "warn" | "good";
}

const START_BANNER: Record<string, Banner> = {
  staff_sickness: { text: "STAFF SICK!", tone: "warn" },
  flu_wave: { text: "FLU WAVE!", tone: "warn" },
  ct_breakdown: { text: "CT DOWN!", tone: "bad" },
  bus_crash: { text: "BUS CRASH!", tone: "bad" },
};

// Big game-style banners for the moments that change the plan: an event starting, the CT coming
// back, or the AI switching on diversion.
export function bannersFor(t: ReplayTick): Banner[] {
  const out: Banner[] = [];
  for (const e of t.events) {
    if (e.event === "event_start") {
      out.push(START_BANNER[String(e.kind)] ?? { text: `${eventName(String(e.kind)).toUpperCase()}!`, tone: "warn" });
    } else if (e.event === "event_end" && e.kind === "ct_breakdown") {
      out.push({ text: "CT FIXED", tone: "good" });
    }
  }
  if (t.actions.some((a, i) => a.type === "divert" && t.results[i]?.ok !== false)) {
    out.push({ text: "DIVERSION ON", tone: "warn" });
  }
  return out;
}

// Announced events that have not started yet (obs.warnings stays visible until the event ends).
export function describeWarnings(obs: Observation): Line[] {
  return obs.warnings
    .filter((w) => w.start_tick > obs.tick)
    .map((w) => {
      const n = w.start_tick - obs.tick;
      return {
        icon: "warn",
        text: `${eventName(w.event)} expected at tick ${w.start_tick} (${clockForTick(w.start_tick)})`,
        tone: "warn" as Tone,
        detail: `in ${plural(n, "tick")}`,
      };
    });
}

// How many beds the zone's on-shift team can cover (SPEC §3: the smaller of doctor and nurse
// coverage, fractional coverage rounded down; tired staff count as 0.6).
export function zoneCapacity(obs: Observation, zone: Zone): number {
  let doctors = 0;
  let nurses = 0;
  for (const s of obs.staff) {
    if (s.status !== "on_shift" || s.location !== zone) continue;
    if (s.role === "doctor") doctors += s.counts_as;
    else nurses += s.counts_as;
  }
  const capacity = Math.min(doctors * BEDS_PER_DOCTOR[zone], nurses * BEDS_PER_NURSE[zone]);
  // Round away float noise (0.6 * 5 = 2.9999...) before flooring.
  return Math.floor(Math.round(capacity * 1000) / 1000);
}

export interface ScorePart {
  key: "O" | "T" | "W" | "B";
  name: string;
  value: number; // 0..1
  points: number;
  max: number;
}

// Split score = 60·O + 20·T + O·(10·W + 10·B) into its four point contributions.
export function scoreParts(s: ScoreSummary): ScorePart[] {
  return [
    { key: "O", name: "Outcome", value: s.O, points: 60 * s.O, max: 60 },
    { key: "T", name: "Timeliness", value: s.T, points: 20 * s.T, max: 20 },
    { key: "W", name: "Wellbeing", value: s.W, points: 10 * s.O * s.W, max: 10 },
    { key: "B", name: "Budget", value: s.B, points: 10 * s.O * s.B, max: 10 },
  ];
}
