// Per-tick world model, built once per replay. Every person gets a stable place (seat, bed, zone spot,
// rest spot, infirmary) that they keep until they move, and each tick gets a short plan of who walks where.
// Phase 0 of tick t is exactly what the AI observed (obs t); phase 1 is the next observation, so a seek
// to any tick lands on the state the HUD shows. Owner: agent D (playback + animation).
//
// Within a tick (SPEC §4 order): the AI's actions play first (admits, assigns, spends, rejections), then
// treatment and outcomes (discharges, deaths, leavers, upgrades, faints), then the start of the next tick
// (staff returning or leaving, events starting or ending, new arrivals and diverted patients).

import type { EffectKind, PatientState, Point } from "../replay/frame";
import type {
  Bed,
  Esi,
  Location,
  Observation,
  Replay,
  SimEvent,
  Staff,
  StaffStatus,
  Zone,
} from "../replay/types";
import type { Layout } from "../world/layout";
import { jitter, type Key, type Leg } from "./motion";
import { pointAlong, walkPath } from "./paths";

// Phase windows inside a tick. All movement fits in the first ~70%, so at 2x-4x the department keeps
// moving and the effects linger over the quiet end of the tick into the next one.
export const PHASE = {
  windup: 0.06, // anticipation before someone gets up from a seat or bed
  act: 0.04, // admits and assigns start (after their wind-up); phase 0 stays exactly the observation
  actEnd: 0.35, // ...and have arrived
  treat: 0.15, // treatment bars fill from here...
  treatEnd: 0.45, // ...to here
  outcome: 0.38, // discharges and leavers get up, upgrades
  death: 0.5, // after a short hold from `outcome`, the patient dies...
  deathFade: 0.62, // ...and fades from here to 0.95
  spin: 0.4, // a staff member spins around...
  faint: 0.5, // ...and drops
  next: 0.4, // next tick's start: arrivals, diverted, staff returns and departures, event start/end
  moveEnd: 0.72, // every walk that ends this tick is done by here
  carryEnd: 0.3, // a person who fainted last tick is carried to the infirmary by now
} as const;

const PRE_OBS = new Set(["episode_start", "arrival", "diverted", "event_start", "event_end"]);

export interface PatientPlan {
  id: string;
  from: Point;
  legs: Leg[];
  alpha: Key<number>[];
  state: Key<PatientState>[];
  esi: Key<Esi>[];
  needsCt: Key<boolean>[];
  bed: Key<string | null>[];
  covered: Key<boolean>[];
  waitingForCt: Key<boolean>[];
  progress: Key<number>[]; // linear
}

export interface StaffPlan {
  id: string;
  role: "doctor" | "nurse";
  agency: boolean;
  from: Point;
  legs: Leg[];
  alpha: Key<number>[];
  status: Key<StaffStatus>[];
  location: Key<Location>[];
  countsAs: Key<number>[];
  fatigue: Key<number>[]; // linear
  spin: [number, number] | null; // phase window of a spin before fainting
}

export interface EffectSpec extends Point {
  kind: EffectKind;
  at: number; // phase within its tick
  life: number; // in ticks
  text?: string;
}

export interface WorldStatus {
  ct: { working: boolean; downTicksLeft: number };
  diversion: { active: boolean; ticksLeft: number };
  activeEvents: string[];
}

export interface TickModel {
  patients: PatientPlan[];
  staff: StaffPlan[];
  effects: EffectSpec[];
  status: Key<WorldStatus>[];
}

export interface TickMarkers {
  tick: number;
  arrivals: number;
  admitted: number;
  discharged: number;
  deaths: number;
  left: number;
  diverted: number;
  upgrades: number;
  faints: number;
  rejected: number;
  spend: number; // euros spent this tick
  eventsStarted: string[];
  eventsEnded: string[];
}

export type PatientOutcome = "discharged" | "died" | "left" | "diverted";

export interface PatientRecord {
  id: string;
  esi: Esi; // highest severity reached (an upgraded ESI 3 shows 2)
  arrivalEsi: Esi;
  needsCt: boolean;
  source: string | null; // base | flu | bus
  arrivedTick: number;
  admittedTick: number | null;
  zone: Zone | null;
  bed: string | null;
  outcome: PatientOutcome | null;
  outcomeTick: number | null;
  cause: string | null; // death cause
}

export interface ReplayModel {
  ticks: TickModel[];
  markers: TickMarkers[];
  patients: Map<string, PatientRecord>;
}

type Place =
  | { k: "seat" | "rest" | "off"; i: number }
  | { k: "zone"; zone: Zone; i: number }
  | { k: "bed"; bed: string }
  | { k: "gone" };

const GONE: Place = { k: "gone" };

// Lowest free index first, so the waiting room and rest room stay compact.
class Slots {
  private taken: boolean[] = [];
  take(): number {
    let i = this.taken.indexOf(false);
    if (i < 0) i = this.taken.length;
    this.taken[i] = true;
    return i;
  }
  free(i: number): void {
    this.taken[i] = false;
  }
}

const stagger = (id: string, order: number): number => jitter(id) * 0.06 + Math.min(order, 6) * 0.02;

function placeKind(s: { status: StaffStatus; location: Location }): Place["k"] {
  switch (s.status) {
    case "on_shift":
      return s.location === "rest" ? "rest" : "zone";
    case "resting":
      return "rest";
    case "fainted":
    case "sick":
      return "off";
    default:
      return "gone";
  }
}

function matches(place: Place, s: { status: StaffStatus; location: Location }): boolean {
  return place.k === placeKind(s) && (place.k !== "zone" || place.zone === s.location);
}

interface LegOpts {
  lag?: number; // crowd stagger added to the start
  windup?: boolean; // getting up from a seat or bed
  settle?: boolean; // arriving at a spot (not walking out of the building)
}

// Legs of one person never overlap: a leg starts after the previous one (and its wind-up) ends.
function addLeg(plan: { from: Point; legs: Leg[] }, w0: number, w1: number, to: Point, opts: LegOpts = {}): Leg {
  const prev = plan.legs[plan.legs.length - 1];
  const from = prev ? prev.to : plan.from;
  const windup = opts.windup ? PHASE.windup : 0;
  const base = Math.max(w0, prev ? prev.t1 + 0.02 : 0) + windup;
  const t0 = Math.min(base + (opts.lag ?? 0), 0.95);
  const t1 = Math.min(1, Math.max(w1, t0 + 0.05));
  const leg: Leg = { t0, t1, from, to, lag: Math.max(0, t0 - base), windup, settle: opts.settle ?? false };
  plan.legs.push(leg);
  return leg;
}

function endOf(plan: { from: Point; legs: Leg[] }): Point {
  return plan.legs.length ? plan.legs[plan.legs.length - 1].to : plan.from;
}

const fadeOut = (t0: number, t1: number): Key<number>[] => [
  { at: Math.max(t0, t1 - 0.12), v: 1 },
  { at: t1, v: 0 },
];

const eventLabel = (kind: string): string => kind.replace(/_/g, " ");

function worldStatus(obs: Observation, active: Set<string>): WorldStatus {
  return {
    ct: { working: obs.ct.working, downTicksLeft: obs.ct.down_ticks_left },
    diversion: { active: obs.diversion.active, ticksLeft: obs.diversion.ticks_left },
    activeEvents: [...active],
  };
}

export function buildModel(replay: Replay, layout: Layout): ReplayModel {
  const N = replay.ticks.length;
  const seats = new Slots();
  const rest = new Slots();
  const off = new Slots();
  const zones: Record<Zone, Slots> = { resus: new Slots(), acute: new Slots(), fast_track: new Slots() };
  const pPlace = new Map<string, Place>();
  const sPlace = new Map<string, Place>();
  const records = new Map<string, PatientRecord>();
  const facts = new Map<string, { esi: Esi; needsCt: boolean }>();

  const bedPoint = (bed: string): Point => {
    const at = layout.beds[bed];
    if (!at) throw new Error(`layout has no bed ${bed}`);
    // drawPatient draws an in-bed patient from the bed's top-left.
    return { x: at.x, y: at.y };
  };
  const pointOf = (place: Place): Point => {
    switch (place.k) {
      case "seat":
        return layout.waitingSlot(place.i);
      case "bed":
        return bedPoint(place.bed);
      case "zone":
        return layout.staffSlot(place.zone, place.i);
      case "rest":
        return layout.restSlot(place.i);
      case "off":
        return { x: layout.offstage.x + (place.i % 6) * 6, y: layout.offstage.y + Math.floor(place.i / 6) * 6 };
      case "gone":
        return layout.offstage;
    }
  };
  const release = (place: Place): void => {
    if (place.k === "seat") seats.free(place.i);
    else if (place.k === "rest") rest.free(place.i);
    else if (place.k === "off") off.free(place.i);
    else if (place.k === "zone") zones[place.zone].free(place.i);
  };
  const takeFor = (s: { status: StaffStatus; location: Location }): Place => {
    const k = placeKind(s);
    if (k === "zone") {
      const zone = s.location as Zone;
      return { k, zone, i: zones[zone].take() };
    }
    if (k === "rest") return { k, i: rest.take() };
    if (k === "off") return { k, i: off.take() };
    return GONE;
  };

  // Which events are running at each tick's observation (event_start/end happen before the AI observes).
  const activeAt: Set<string>[] = [];
  const running = new Set<string>();
  for (const t of replay.ticks) {
    for (const e of t.events) {
      if (e.event === "event_start") running.add(String(e.kind));
      if (e.event === "event_end") running.delete(String(e.kind));
    }
    activeAt.push(new Set(running));
  }

  const markers: TickMarkers[] = replay.ticks.map((t) => {
    const count = (name: string): number => t.events.filter((e) => e.event === name).length;
    return {
      tick: t.tick,
      arrivals: count("arrival"),
      admitted: count("admitted"),
      discharged: count("discharged"),
      deaths: count("death"),
      left: count("left"),
      diverted: count("diverted"),
      upgrades: count("upgrade"),
      faints: count("faint"),
      rejected: t.results.filter((r) => !r.ok).length,
      spend: t.events.filter((e) => e.event === "spend").reduce((sum, e) => sum + Number(e.amount ?? 0), 0),
      eventsStarted: t.events.filter((e) => e.event === "event_start").map((e) => String(e.kind)),
      eventsEnded: t.events.filter((e) => e.event === "event_end").map((e) => String(e.kind)),
    };
  });

  const recordArrival = (e: SimEvent, outcome: PatientOutcome | null): void => {
    const esi = e.esi as Esi;
    records.set(String(e.patient), {
      id: String(e.patient),
      esi,
      arrivalEsi: esi,
      needsCt: Boolean(e.needs_ct),
      source: e.source === undefined ? null : String(e.source),
      arrivedTick: e.t,
      admittedTick: null,
      zone: null,
      bed: null,
      outcome,
      outcomeTick: outcome ? e.t : null,
      cause: null,
    });
  };
  for (const t of replay.ticks) {
    for (const e of t.events) {
      if (e.event === "arrival") recordArrival(e, null);
      if (e.event === "diverted") recordArrival(e, "diverted");
    }
  }

  const ticks: TickModel[] = [];
  for (let t = 0; t < N; t++) {
    const tick = replay.ticks[t];
    const cur = tick.obs;
    const next = t + 1 < N ? replay.ticks[t + 1].obs : replay.final_obs;
    const nextPre = t + 1 < N ? replay.ticks[t + 1].events.filter((e) => PRE_OBS.has(e.event)) : [];
    const post = tick.events.filter((e) => !PRE_OBS.has(e.event));
    const effects: EffectSpec[] = [];
    const stack = new Map<string, number>();
    const fx = (kind: EffectKind, at: number, pt: Point, text?: string, life = 1): void => {
      const key = `${Math.round(pt.x)},${Math.round(pt.y)},${Math.round(at * 10)}`;
      const n = stack.get(key) ?? 0;
      stack.set(key, n + 1);
      effects.push({ kind, at, life, x: pt.x, y: pt.y - n * 8, text });
    };
    if (t === 0) {
      for (const e of tick.events) {
        if (e.event === "event_start") fx("event_start", 0, eventPoint(String(e.kind)), eventLabel(String(e.kind)), 2);
      }
    }

    // --- patients present at the observation -------------------------------------------------------
    const nextBeds = new Map<string, Bed>();
    for (const b of next.beds) if (b.patient) nextBeds.set(b.patient, b);
    const present = new Map<string, { bed: Bed | null }>();
    for (const w of cur.waiting) {
      present.set(w.id, { bed: null });
      facts.set(w.id, { esi: w.esi, needsCt: w.needs_ct });
    }
    for (const b of cur.beds) if (b.patient) present.set(b.patient, { bed: b });
    for (const [id, place] of pPlace) {
      if (!present.has(id)) {
        release(place);
        pPlace.delete(id);
      }
    }
    const pPlans = new Map<string, PatientPlan>();
    for (const [id, { bed }] of present) {
      let place = pPlace.get(id);
      if (bed && (place?.k !== "bed" || place.bed !== bed.bed)) {
        if (place) release(place);
        place = { k: "bed", bed: bed.bed };
      } else if (!bed && place?.k !== "seat") {
        if (place) release(place);
        place = { k: "seat", i: seats.take() };
      }
      pPlace.set(id, place!);
      const f = facts.get(id) ?? { esi: (bed?.esi ?? 3) as Esi, needsCt: false };
      const esi = bed?.esi ?? f.esi;
      const progress = bed ? (bed.treated_ticks ?? 0) / (bed.treatment_ticks || 1) : 0;
      pPlans.set(id, {
        id,
        from: pointOf(place!),
        legs: [],
        alpha: [],
        state: [{ at: 0, v: bed ? "in_bed" : "waiting" }],
        esi: [{ at: 0, v: esi }],
        needsCt: [{ at: 0, v: f.needsCt }],
        bed: [{ at: 0, v: bed ? bed.bed : null }],
        covered: [{ at: 0, v: Boolean(bed?.covered) }],
        waitingForCt: [{ at: 0, v: Boolean(bed?.waiting_for_ct) }],
        progress: [{ at: 0, v: progress }],
      });
    }

    // --- the AI's actions: rejections and spends ---------------------------------------------------
    tick.results.forEach((r) => {
      if (r.ok) return;
      const a = tick.actions[r.index];
      const at = Math.min(0.03 + r.index * 0.02, 0.3);
      let pt = layout.entrance;
      if (a?.type === "admit" && pPlans.has(a.patient)) pt = pPlans.get(a.patient)!.from;
      else if (a?.type === "assign" && sPlace.has(a.staff) && sPlace.get(a.staff)!.k !== "gone")
        pt = pointOf(sPlace.get(a.staff)!);
      else if (a?.type === "repair") pt = layout.ct;
      fx("rejected", at, pt, r.reason ?? "rejected", 1.6);
    });
    if (tick.results.some((r) => r.ok && tick.actions[r.index]?.type === "divert")) {
      fx("diverted", 0.1, layout.entrance, "diversion on", 1.6);
    }

    // --- treatment and outcomes --------------------------------------------------------------------
    const deferred: string[] = [];
    let admitOrder = 0;
    let outOrder = 0;
    for (const e of post) {
      const id = String(e.patient ?? "");
      const plan = pPlans.get(id);
      const rec = records.get(id);
      if (e.event === "spend") {
        const pt = e.item === "repair" ? layout.ct : layout.entrance;
        fx("spend", 0.1, pt, `-€${Number(e.amount ?? 0)}`, 1.6);
        continue;
      }
      if (!plan) continue;
      switch (e.event) {
        case "admitted": {
          const bed = String(e.bed);
          release(pPlace.get(id)!);
          pPlace.set(id, { k: "bed", bed });
          const leg = addLeg(plan, PHASE.act, PHASE.actEnd, bedPoint(bed), {
            lag: stagger(id, admitOrder++),
            windup: true,
            settle: true,
          });
          plan.state.push({ at: goAt(leg), v: "to_bed" }, { at: leg.t1, v: "in_bed" });
          plan.bed.push({ at: goAt(leg), v: bed });
          const nb = nextBeds.get(id);
          const progressed = nb ? (nb.treated_ticks ?? 0) > 0 : false;
          plan.covered.push({ at: leg.t1, v: progressed || Boolean(nb?.waiting_for_ct && nb.covered) });
          if (nb) {
            const done = (nb.treated_ticks ?? 0) / (nb.treatment_ticks || 1);
            plan.progress.push(
              { at: Math.max(PHASE.treat, leg.t1), v: 0 },
              { at: Math.max(PHASE.treatEnd, leg.t1 + 0.05), v: done },
            );
          }
          fx("admitted", leg.t1, bedPoint(bed), undefined, 1.2);
          if (rec) Object.assign(rec, { admittedTick: t, zone: e.zone as Zone, bed });
          break;
        }
        case "discharged": {
          const place = pPlace.get(id)!;
          release(place);
          pPlace.delete(id);
          const inBed = plan.legs.length ? endLegT1(plan) : 0;
          const filled = Math.max(PHASE.outcome, inBed + 0.04);
          const fillFrom = Math.min(filled - 0.02, Math.max(PHASE.treat, inBed));
          plan.progress.push({ at: fillFrom, v: lastValue(plan.progress) }, { at: filled, v: 1 });
          plan.covered.push({ at: fillFrom, v: true });
          const leg = addLeg(plan, filled, PHASE.moveEnd, layout.exit, { lag: stagger(id, outOrder++), windup: true });
          plan.state.push({ at: goAt(leg), v: "leaving" });
          plan.bed.push({ at: goAt(leg), v: null });
          plan.alpha.push(...fadeOut(leg.t0, leg.t1));
          fx("discharged", goAt(leg), endOfBefore(plan, leg), undefined, 1.2);
          if (rec) Object.assign(rec, { outcome: "discharged", outcomeTick: t });
          break;
        }
        case "death": {
          // A short, still hold while the others move, then the death beat.
          const at = Math.min(Math.max(PHASE.death, plan.legs.length ? endLegT1(plan) + 0.1 : 0), 0.8);
          plan.state.push({ at, v: "dead" });
          plan.alpha.push({ at: Math.max(PHASE.deathFade, at + 0.08), v: 1 }, { at: 0.95, v: 0 });
          fx("death", at, endOf(plan), `${id} died`, 2);
          deferred.push(id);
          if (rec) Object.assign(rec, { outcome: "died", outcomeTick: t, cause: e.cause === undefined ? null : String(e.cause) });
          break;
        }
        case "left": {
          const leg = addLeg(plan, PHASE.outcome, PHASE.moveEnd, layout.exit, { lag: stagger(id, outOrder++), windup: true });
          plan.state.push({ at: goAt(leg), v: "leaving" });
          plan.alpha.push(...fadeOut(leg.t0, leg.t1));
          fx("left", goAt(leg), leg.from, `${id} left`, 1.6);
          deferred.push(id);
          if (rec) Object.assign(rec, { outcome: "left", outcomeTick: t });
          break;
        }
        case "upgrade": {
          const esi = e.esi as Esi;
          const needsCt = Boolean(e.needs_ct);
          plan.esi.push({ at: PHASE.outcome, v: esi });
          plan.needsCt.push({ at: PHASE.outcome, v: needsCt });
          facts.set(id, { esi, needsCt });
          fx("upgrade", PHASE.outcome, endOf(plan), `ESI ${esi}`, 1.6);
          if (rec) Object.assign(rec, { esi: Math.min(rec.esi, esi) as Esi, needsCt });
          break;
        }
      }
    }
    // Patients who stay in their bed: show this tick's treatment (coverage is only known after it).
    for (const [id, { bed }] of present) {
      const nb = nextBeds.get(id);
      if (!bed || !nb || nb.bed !== bed.bed) continue;
      const plan = pPlans.get(id)!;
      const treated = (nb.treated_ticks ?? 0) > (bed.treated_ticks ?? 0);
      plan.covered.push({ at: PHASE.actEnd, v: treated || Boolean(nb.waiting_for_ct && nb.covered) });
      plan.waitingForCt.push({ at: PHASE.actEnd, v: Boolean(nb.waiting_for_ct) });
      plan.progress.push(
        { at: PHASE.treat, v: lastValue(plan.progress) },
        { at: PHASE.treatEnd, v: (nb.treated_ticks ?? 0) / (nb.treatment_ticks || 1) },
      );
    }

    // --- start of the next tick: events, arrivals, diverted -----------------------------------------
    let arriveOrder = 0;
    for (const e of nextPre) {
      const id = String(e.patient ?? "");
      if (e.event === "event_start" || e.event === "event_end") {
        const kind = String(e.kind);
        const text = e.event === "event_start" ? eventLabel(kind) : `${eventLabel(kind)} over`;
        fx(e.event, PHASE.next, eventPoint(kind), text, 2.5);
        continue;
      }
      if (e.event !== "arrival" && e.event !== "diverted") continue;
      const esi = e.esi as Esi;
      const needsCt = Boolean(e.needs_ct);
      const order = arriveOrder++;
      const plan: PatientPlan = {
        id,
        from: layout.entrance,
        legs: [],
        alpha: [
          { at: PHASE.next, v: 0 },
          { at: PHASE.next + 0.06, v: 1 },
        ],
        state: [{ at: 0, v: "arriving" }],
        esi: [{ at: 0, v: esi }],
        needsCt: [{ at: 0, v: needsCt }],
        bed: [{ at: 0, v: null }],
        covered: [{ at: 0, v: false }],
        waitingForCt: [{ at: 0, v: false }],
        progress: [{ at: 0, v: 0 }],
      };
      if (e.event === "arrival") {
        facts.set(id, { esi, needsCt });
        const seat: Place = { k: "seat", i: seats.take() };
        pPlace.set(id, seat);
        // Bus-crash victims rush in close together; flu patients shuffle in and spread out.
        const lag =
          e.source === "bus" ? order * 0.025 : e.source === "flu" ? stagger(id, order) * 1.5 : stagger(id, order);
        const w1 = e.source === "bus" ? PHASE.next + lag + 0.2 : PHASE.moveEnd;
        const leg = addLeg(plan, PHASE.next, w1, pointOf(seat), { lag, settle: true });
        plan.state.push({ at: leg.t1, v: "waiting" });
        fx("arrival", leg.t0, layout.entrance);
      } else {
        // Turned away at the door: a few steps in, then back out.
        const inside = pointAlong(walkPath(layout.entrance, layout.waitingSlot(0)), 2 * 16);
        const lag = stagger(id, order);
        const inLeg = addLeg(plan, PHASE.next, PHASE.next + lag + 0.12, { x: inside.x, y: inside.y }, { lag });
        const outLeg = addLeg(plan, inLeg.t1 + 0.04, PHASE.moveEnd, layout.entrance);
        plan.state.push({ at: outLeg.t0, v: "leaving" });
        plan.alpha.push(...fadeOut(outLeg.t0, outLeg.t1));
        fx("diverted", inLeg.t1, layout.entrance, "diverted");
      }
      pPlans.set(id, plan);
    }
    for (const id of deferred) {
      const place = pPlace.get(id);
      if (place) release(place);
      pPlace.delete(id);
    }

    // --- staff ---------------------------------------------------------------------------------------
    const sPlans = new Map<string, StaffPlan>();
    const predicted = new Map<string, { status: StaffStatus; location: Location }>();
    const newStaffPlan = (s: Staff, from: Point): StaffPlan => ({
      id: s.id,
      role: s.role,
      agency: s.agency,
      from,
      legs: [],
      alpha: [],
      status: [{ at: 0, v: s.status }],
      location: [{ at: 0, v: s.location }],
      countsAs: [{ at: 0, v: s.counts_as }],
      fatigue: [{ at: 0, v: s.fatigue }],
      spin: null,
    });
    let carryOrder = 0;
    for (const s of cur.staff) {
      let place = sPlace.get(s.id) ?? GONE;
      // Fainted at the end of last tick and still lying where they fell.
      const fallen = s.status === "fainted" && place.k !== "off" && place.k !== "gone";
      if (!fallen && !matches(place, s)) {
        release(place);
        place = takeFor(s);
        sPlace.set(s.id, place);
      }
      predicted.set(s.id, { status: s.status, location: s.location });
      if (place.k === "gone") continue;
      const plan = newStaffPlan(s, pointOf(place));
      sPlans.set(s.id, plan);
      if (fallen) {
        release(place);
        place = takeFor(s);
        sPlace.set(s.id, place);
        addLeg(plan, 0.03, PHASE.carryEnd, pointOf(place), { lag: stagger(s.id, carryOrder++) });
      }
    }
    const assigned = new Map<string, Location>();
    tick.results.forEach((r) => {
      const a = tick.actions[r.index];
      if (r.ok && a?.type === "assign") assigned.set(a.staff, a.to);
    });
    let assignOrder = 0;
    for (const [id, to] of assigned) {
      const plan = sPlans.get(id);
      if (!plan) continue;
      const target = { status: (to === "rest" ? "resting" : "on_shift") as StaffStatus, location: to };
      let at = 0.05;
      const place = sPlace.get(id) ?? GONE;
      if (!matches(place, target)) {
        release(place);
        const dest = takeFor(target);
        sPlace.set(id, dest);
        const leg = addLeg(plan, PHASE.act, PHASE.actEnd, pointOf(dest), {
          lag: stagger(id, assignOrder++),
          windup: true,
          settle: true,
        });
        at = goAt(leg);
      }
      plan.status.push({ at, v: target.status });
      plan.location.push({ at, v: to });
      predicted.set(id, target);
    }
    const fainted = new Set<string>();
    for (const e of post) {
      if (e.event !== "faint") continue;
      const id = String(e.staff);
      const plan = sPlans.get(id);
      if (!plan) continue;
      plan.spin = [PHASE.spin, PHASE.faint];
      plan.status.push({ at: PHASE.faint, v: "fainted" });
      plan.location.push({ at: PHASE.faint, v: "rest" });
      predicted.set(id, { status: "fainted", location: "rest" });
      fainted.add(id);
      fx("faint", PHASE.faint, endOf(plan), `${id} fainted`, 2);
    }
    // Whatever still differs from the next observation happened at the start of the next tick:
    // agency staff arriving or leaving, staff off sick, people back from sickness or a faint.
    let nextOrder = 0;
    for (const ns of next.staff) {
      const place = sPlace.get(ns.id) ?? GONE;
      let plan = sPlans.get(ns.id);
      const pred = predicted.get(ns.id) ?? { status: ns.status, location: ns.location };
      const liesWhereFell = fainted.has(ns.id) && ns.status === "fainted";
      if (!liesWhereFell && !matches(place, ns)) {
        const lag = stagger(ns.id, nextOrder++);
        if (!plan) {
          plan = newStaffPlan({ ...ns, status: pred.status, location: pred.location }, layout.entrance);
          plan.alpha.push({ at: PHASE.next, v: 0 }, { at: PHASE.next + 0.06, v: 1 });
          sPlans.set(ns.id, plan);
          fx("arrival", PHASE.next, layout.entrance, undefined, 1.2);
        }
        release(place);
        const dest = takeFor(ns);
        sPlace.set(ns.id, dest);
        const out = dest.k === "gone";
        const leg = addLeg(plan, PHASE.next, PHASE.moveEnd, out ? layout.exit : pointOf(dest), { lag, settle: !out });
        if (out) plan.alpha.push(...fadeOut(leg.t0, leg.t1));
        plan.status.push({ at: goAt(leg), v: ns.status });
        plan.location.push({ at: goAt(leg), v: ns.location });
      } else if (plan && (pred.status !== ns.status || pred.location !== ns.location)) {
        plan.status.push({ at: PHASE.next, v: ns.status });
        plan.location.push({ at: PHASE.next, v: ns.location });
      }
      if (plan) {
        plan.countsAs.push({ at: PHASE.next, v: ns.counts_as });
        plan.fatigue.push({ at: PHASE.act, v: plan.fatigue[0].v }, { at: 1, v: ns.fatigue });
      }
    }

    // --- department status: CT, diversion, running events ------------------------------------------
    const before = worldStatus(cur, activeAt[t]);
    const after = worldStatus(next, t + 1 < N ? activeAt[t + 1] : activeAt[t]);
    const status: Key<WorldStatus>[] = [{ at: 0, v: before }];
    const divertOk = tick.results.some((r) => r.ok && tick.actions[r.index]?.type === "divert");
    if (divertOk) status.push({ at: 0.1, v: { ...before, diversion: after.diversion } });
    status.push({ at: PHASE.next, v: after });

    for (const plan of pPlans.values()) sortKeys(plan);
    for (const plan of sPlans.values()) sortKeys(plan);
    ticks.push({ patients: [...pPlans.values()], staff: [...sPlans.values()], effects, status });
  }

  function eventPoint(kind: string): Point {
    if (kind === "ct_breakdown") return layout.ct;
    if (kind === "staff_sickness") return layout.restSlot(0);
    return layout.entrance;
  }

  return { ticks, markers, patients: records };
}

// When someone starts to go (wind-up included), with or without the crowd stagger.
function goAt(leg: Leg): number {
  return leg.t0 - leg.lag - leg.windup;
}

function lastValue(keys: Key<number>[]): number {
  return keys[keys.length - 1].v;
}

function endLegT1(plan: { legs: Leg[] }): number {
  return plan.legs[plan.legs.length - 1].t1;
}

function endOfBefore(plan: { from: Point; legs: Leg[] }, leg: Leg): Point {
  const i = plan.legs.indexOf(leg);
  return i > 0 ? plan.legs[i - 1].to : plan.from;
}

// Keys are pushed in event order; evaluation needs them sorted by phase (stable for equal phases).
function sortKeys(plan: object): void {
  for (const v of Object.values(plan)) {
    if (Array.isArray(v) && v.length > 1 && typeof v[0] === "object" && "at" in v[0]) {
      v.sort((a: Key<unknown>, b: Key<unknown>) => a.at - b.at);
    }
  }
}
