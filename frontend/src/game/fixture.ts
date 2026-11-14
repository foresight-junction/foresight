// A tiny hand-made 6-tick replay for tests that touches every event kind the viewer animates.
// Invented patients and staff only. Owner: agent D (playback + animation).

import type { Action, ActionResult, Bed, Observation, Replay, SimEvent, Staff, WaitingPatient } from "../replay/types";

type StaffRow = [id: string, status: Staff["status"], location: Staff["location"], fatigue?: number];

function staff(rows: StaffRow[]): Staff[] {
  return rows.map(([id, status, location, fatigue = 10]) => ({
    id,
    role: id.startsWith("D") || id.startsWith("AD") ? "doctor" : "nurse",
    agency: id.startsWith("A"),
    location,
    fatigue,
    counts_as: fatigue > 60 ? 0.6 : 1,
    status,
    ticks_until_change: null,
  }));
}

function bed(zone: Bed["zone"], id: string, patient?: [string, 1 | 2 | 3 | 4 | 5, number, number, boolean]): Bed {
  if (!patient) return { zone, bed: id, patient: null };
  const [pid, esi, treated, needed, covered] = patient;
  return { zone, bed: id, patient: pid, esi, treated_ticks: treated, treatment_ticks: needed, covered, waiting_for_ct: false };
}

function obs(tick: number, waiting: WaitingPatient[], beds: Bed[], crew: Staff[], extra: Partial<Observation> = {}): Observation {
  return {
    tick,
    clock: `Day 1 ${String(8 + tick / 2).padStart(2, "0")}:00`,
    ticks_left: 144 - tick,
    finished: false,
    budget: { spent: 0, budget: 12000, hard_limit: 24000 },
    waiting,
    beds,
    staff: crew,
    ct: { working: true, down_ticks_left: 0 },
    warnings: [],
    diversion: { active: false, ticks_left: 0 },
    totals: { discharged: 0, deaths: 0, left: 0, diverted: 0, faints: 0 },
    last_rejected: [],
    ...extra,
  };
}

const w = (id: string, esi: 1 | 2 | 3 | 4 | 5, arrived: number, now: number, needsCt = false): WaitingPatient => ({
  id,
  esi,
  arrived_tick: arrived,
  waited_ticks: now - arrived,
  needs_ct: needsCt,
});

let seq = 0;
const ev = (t: number, event: string, fields: Record<string, unknown> = {}): SimEvent => ({ seq: seq++, t, src: "sim", event, ...fields });
const ok = (n: number): ActionResult[] => Array.from({ length: n }, (_, index) => ({ index, ok: true }));

export function fixtureReplay(): Replay {
  seq = 0;
  const t0Actions: Action[] = [
    { type: "admit", patient: "P002", zone: "resus" },
    { type: "assign", staff: "D1", to: "resus" },
    { type: "assign", staff: "N1", to: "resus" },
    { type: "admit", patient: "P099", zone: "acute" },
    { type: "agency", role: "doctor" },
  ];
  const t0Results: ActionResult[] = [...ok(3), { index: 3, ok: false, reason: "unknown_patient" }, { index: 4, ok: true }];
  const t3Actions: Action[] = [
    { type: "assign", staff: "AD1", to: "acute" },
    { type: "assign", staff: "N1", to: "acute" },
  ];
  const t3Results: ActionResult[] = [{ index: 0, ok: true }, { index: 1, ok: false, reason: "staff_unavailable" }];
  return {
    version: 1,
    meta: {
      name: "fixture",
      policy: "fixture",
      label: "Hand-made fixture",
      seed: 0,
      reward: 0,
      score: { reward: 0, score: 0, O: 0, T: 0, W: 0, B: 0, spend: 900, totals: {}, failures: {} },
    },
    ticks: [
      {
        tick: 0,
        obs: obs(0, [w("P001", 3, 0, 0), w("P002", 1, 0, 0), w("P003", 5, 0, 0)], [bed("resus", "R1"), bed("acute", "A1"), bed("fast_track", "F1")],
          staff([["D1", "resting", "rest"], ["N1", "resting", "rest", 85], ["N2", "resting", "rest"]])),
        actions: t0Actions,
        results: t0Results,
        events: [
          ev(0, "episode_start", { budget: 12000, hard_limit: 24000 }),
          ev(0, "arrival", { patient: "P001", esi: 3, needs_ct: false, source: "base" }),
          ev(0, "arrival", { patient: "P002", esi: 1, needs_ct: false, source: "base" }),
          ev(0, "arrival", { patient: "P003", esi: 5, needs_ct: false, source: "base" }),
          ev(0, "admitted", { patient: "P002", zone: "resus", bed: "R1" }),
          ev(0, "spend", { item: "agency_doctor", amount: 900 }),
          ev(0, "covered", { patient: "P002" }),
          ev(0, "upgrade", { patient: "P001", esi: 2, needs_ct: true }),
          ev(0, "staff_fatigue", { on_shift_above_60: 1, on_shift: 2 }),
        ],
      },
      {
        tick: 1,
        obs: obs(1, [w("P001", 2, 0, 1, true), w("P003", 5, 0, 1), w("P004", 4, 1, 1)],
          [bed("resus", "R1", ["P002", 1, 1, 6, true]), bed("acute", "A1"), bed("fast_track", "F1")],
          staff([["D1", "on_shift", "resus"], ["N1", "on_shift", "resus", 87.2], ["N2", "resting", "rest"], ["AD1", "agency_ordered", "rest", 0]])),
        actions: [
          { type: "admit", patient: "P001", zone: "acute" },
          { type: "admit", patient: "P003", zone: "fast_track" },
          { type: "assign", staff: "N2", to: "acute" },
        ],
        results: ok(3),
        events: [
          ev(1, "arrival", { patient: "P004", esi: 4, needs_ct: false, source: "base" }),
          ev(1, "diverted", { patient: "P005", esi: 3 }),
          ev(1, "admitted", { patient: "P001", zone: "acute", bed: "A1" }),
          ev(1, "admitted", { patient: "P003", zone: "fast_track", bed: "F1" }),
          ev(1, "covered", { patient: "P003" }),
          ev(1, "discharged", { patient: "P003" }),
          ev(1, "left", { patient: "P004" }),
          ev(1, "faint", { staff: "N1" }),
        ],
      },
      {
        tick: 2,
        obs: obs(2, [], [bed("resus", "R1", ["P002", 1, 2, 6, false]), bed("acute", "A1", ["P001", 2, 0, 6, false]), bed("fast_track", "F1")],
          staff([["D1", "on_shift", "resus"], ["N1", "fainted", "rest", 86.7], ["N2", "sick", "rest"], ["AD1", "agency_ordered", "rest", 0]])),
        actions: [],
        results: [],
        events: [
          ev(2, "event_start", { kind: "staff_sickness", ends_tick: 4 }),
          ev(2, "death", { patient: "P002", cause: "uncovered_bed" }),
        ],
      },
      {
        tick: 3,
        obs: obs(3, [w("P006", 1, 3, 3)], [bed("resus", "R1"), bed("acute", "A1", ["P001", 2, 0, 6, false]), bed("fast_track", "F1")],
          staff([["D1", "on_shift", "resus"], ["N1", "fainted", "rest", 84.2], ["N2", "sick", "rest"], ["AD1", "resting", "rest", 0]])),
        actions: t3Actions,
        results: t3Results,
        events: [
          ev(3, "arrival", { patient: "P006", esi: 1, needs_ct: true, source: "bus" }),
          ev(3, "death", { patient: "P006", cause: "waiting" }),
        ],
      },
      {
        tick: 4,
        obs: obs(4, [], [bed("resus", "R1"), bed("acute", "A1", ["P001", 2, 0, 6, false]), bed("fast_track", "F1")],
          staff([["D1", "on_shift", "resus"], ["N1", "fainted", "rest", 81.7], ["N2", "resting", "rest"], ["AD1", "on_shift", "acute", 1.6]])),
        actions: [],
        results: [],
        events: [ev(4, "event_end", { kind: "staff_sickness" })],
      },
      {
        tick: 5,
        obs: obs(5, [], [bed("resus", "R1"), bed("acute", "A1", ["P001", 2, 0, 6, false]), bed("fast_track", "F1")],
          staff([["D1", "on_shift", "resus"], ["N1", "resting", "rest", 79.2], ["N2", "resting", "rest"], ["AD1", "agency_left", "rest", 3.2]])),
        actions: [],
        results: [],
        events: [ev(5, "episode_end")],
      },
    ],
    final_obs: obs(5, [], [bed("resus", "R1"), bed("acute", "A1", ["P001", 2, 0, 6, false]), bed("fast_track", "F1")],
      staff([["D1", "on_shift", "resus"], ["N1", "resting", "rest", 76.7], ["N2", "resting", "rest"], ["AD1", "agency_left", "rest", 3.2]]), { finished: true }),
  };
}
