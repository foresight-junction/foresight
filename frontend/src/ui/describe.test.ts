import { describe, expect, it } from "vitest";
import type { Observation, Replay, ReplayTick, ScoreSummary, SimEvent, Staff } from "../replay/types";
import {
  bannersFor,
  clockForTick,
  describeActions,
  describeEvents,
  describeStaffChanges,
  describeWarnings,
  euro,
  reasonText,
  scoreParts,
  zoneCapacity,
} from "./describe";
import { buildTimeline, findMistakes, tickSummary } from "./timeline";

function staff(id: string, over: Partial<Staff> = {}): Staff {
  return {
    id,
    role: id.startsWith("D") || id.startsWith("AD") ? "doctor" : "nurse",
    agency: id.startsWith("A"),
    location: "rest",
    fatigue: 10,
    counts_as: 1,
    status: "resting",
    ticks_until_change: null,
    ...over,
  };
}

function obs(over: Partial<Observation> = {}): Observation {
  return {
    tick: 10,
    clock: clockForTick(10),
    ticks_left: 134,
    finished: false,
    budget: { spent: 0, budget: 12000, hard_limit: 24000 },
    waiting: [
      { id: "P042", esi: 2, arrived_tick: 8, waited_ticks: 2, needs_ct: true },
      { id: "P043", esi: 4, arrived_tick: 10, waited_ticks: 0, needs_ct: false },
    ],
    beds: [
      { zone: "resus", bed: "R1", patient: "P030", esi: 1, treated_ticks: 1, treatment_ticks: 6, covered: true },
      { zone: "resus", bed: "R2", patient: null },
    ],
    staff: [
      staff("D1", { status: "on_shift", location: "resus", fatigue: 40 }),
      staff("N1", { status: "on_shift", location: "resus", fatigue: 30 }),
      staff("N3", { status: "on_shift", location: "acute", fatigue: 72.4, counts_as: 0.6 }),
      staff("N2", { status: "fainted", fatigue: 80, ticks_until_change: 6 }),
      staff("D2"),
    ],
    ct: { working: true, down_ticks_left: 0 },
    warnings: [],
    diversion: { active: false, ticks_left: 0 },
    totals: { discharged: 0, deaths: 0, left: 0, diverted: 0, faints: 0 },
    last_rejected: [],
    ...over,
  };
}

let seq = 0;
function ev(t: number, event: string, fields: Record<string, unknown> = {}): SimEvent {
  return { seq: seq++, t, src: "sim", event, ...fields };
}

function tick(over: Partial<ReplayTick> = {}): ReplayTick {
  return { tick: 10, obs: obs(), actions: [], results: [], events: [], ...over };
}

describe("format helpers", () => {
  it("formats euros with thousands separators", () => {
    expect(euro(2000)).toBe("€2,000");
    expect(euro(-350)).toBe("−€350");
    expect(euro(24000)).toBe("€24,000");
  });

  it("maps ticks to the episode clock", () => {
    expect(clockForTick(0)).toBe("Day 1 08:00");
    expect(clockForTick(30)).toBe("Day 1 23:00");
    expect(clockForTick(32)).toBe("Day 2 00:00");
    expect(clockForTick(143)).toBe("Day 4 07:30");
  });
});

describe("describeActions", () => {
  it("describes each action type in plain English with obs details", () => {
    const t = tick({
      actions: [
        { type: "admit", patient: "P042", zone: "resus" },
        { type: "assign", staff: "N3", to: "rest" },
        { type: "agency", role: "nurse" },
        { type: "repair" },
        { type: "divert" },
      ],
      results: [0, 1, 2, 3, 4].map((index) => ({ index, ok: true })),
      events: [ev(10, "admitted", { patient: "P042", zone: "resus", bed: "R2" })],
    });
    const texts = describeActions(t).lines.map((l) => l.text);
    expect(texts).toEqual([
      "Send N3 to rest (fatigue 72)",
      "Admit P042 (ESI 2) → Resus R2",
      "Hire agency nurse −€350",
      "Repair CT −€2,000",
      "Divert ambulances",
    ]);
    const admit = describeActions(t).lines[1];
    expect(admit.esi).toBe(2);
    expect(admit.detail).toBe("waited 2 ticks · late · needs CT");
  });

  it("marks rejections with a plain reason and counts them", () => {
    const t = tick({
      actions: [
        { type: "admit", patient: "P043", zone: "fast_track" },
        { type: "admit", patient: "P042", zone: "fast_track" },
        { type: "assign", staff: "N2", to: "acute" },
      ],
      results: [
        { index: 0, ok: true },
        { index: 1, ok: false, reason: "zone_not_allowed" },
        { index: 2, ok: false, reason: "staff_unavailable" },
      ],
    });
    const r = describeActions(t);
    expect(r.rejected).toBe(2);
    expect(r.total).toBe(3);
    const bad = r.lines.filter((l) => !l.ok);
    expect(bad.map((l) => l.reason)).toEqual(["ESI 2 can't be treated in Fast-track", "N2 is fainted"]);
    expect(bad.every((l) => l.tone === "bad")).toBe(true);
  });

  it("folds no-op assigns into kept and groups many moves", () => {
    const o = obs({
      staff: ["D1", "D2", "D3", "N1", "N2", "N3", "N4"].map((id) => staff(id)),
    });
    o.staff[0] = staff("D1", { status: "on_shift", location: "acute" });
    const t = tick({
      obs: o,
      actions: [
        { type: "assign", staff: "D1", to: "acute" }, // already there
        { type: "assign", staff: "D2", to: "resus" },
        { type: "assign", staff: "D3", to: "acute" },
        { type: "assign", staff: "N1", to: "resus" },
        { type: "assign", staff: "N2", to: "acute" },
        { type: "assign", staff: "N3", to: "acute" },
        { type: "assign", staff: "N4", to: "rest" }, // already resting
      ],
      results: [0, 1, 2, 3, 4, 5, 6].map((index) => ({ index, ok: true })),
    });
    const r = describeActions(t);
    expect(r.kept).toEqual(["D1", "N4"]);
    expect(r.lines.map((l) => l.text)).toEqual(["Put 2 on Resus", "Put 3 on Acute"]);
    expect(r.lines[0].detail).toBe("fatigue: D2 10 · N1 10");
  });

  it("lists a few moves individually with where they came from", () => {
    const t = tick({ actions: [{ type: "assign", staff: "D1", to: "acute" }], results: [{ index: 0, ok: true }] });
    expect(describeActions(t).lines[0].text).toBe("Put D1 on Acute from Resus (fatigue 40)");
  });

  it("handles an empty tick", () => {
    expect(describeActions(tick())).toEqual({ lines: [], kept: [], total: 0, rejected: 0 });
  });
});

describe("reasonText", () => {
  const o = obs();
  it.each([
    ["bad_action", { type: "divert" }, "malformed action"],
    ["unknown_patient", { type: "admit", patient: "P999", zone: "acute" }, "no such patient"],
    ["not_waiting", { type: "admit", patient: "P030", zone: "acute" }, "patient is no longer waiting"],
    ["no_free_bed", { type: "admit", patient: "P042", zone: "acute" }, "no free bed in Acute"],
    ["unknown_staff", { type: "assign", staff: "X1", to: "acute" }, "no such staff member"],
    ["over_hard_limit", { type: "agency", role: "doctor" }, "would break the €24,000 hard limit"],
    ["ct_not_broken", { type: "repair" }, "CT is working, nothing to repair"],
    ["diversion_active", { type: "divert" }, "a diversion is already running"],
    ["something_new", { type: "divert" }, "Something new"],
  ] as const)("%s", (reason, action, text) => {
    expect(reasonText(reason, action, o)).toBe(text);
  });
});

describe("describeEvents", () => {
  it("summarises arrivals, deaths, faints, upgrades and event changes", () => {
    const t = tick({
      events: [
        ev(10, "arrival", { patient: "P043", esi: 4, source: "base" }),
        ev(10, "arrival", { patient: "P044", esi: 1, source: "bus" }),
        ev(10, "arrival", { patient: "P045", esi: 4, source: "bus" }),
        ev(10, "discharged", { patient: "P001" }),
        ev(10, "discharged", { patient: "P002" }),
        ev(10, "death", { patient: "P042", cause: "waiting" }),
        ev(10, "faint", { staff: "N2" }),
        ev(10, "upgrade", { patient: "P020", esi: 2, needs_ct: true }),
        ev(10, "left", { patient: "P043" }),
        ev(10, "staff_fatigue", { on_shift_above_60: 1, on_shift: 3 }),
        ev(10, "event_start", { kind: "bus_crash", ends_tick: 12 }),
        ev(10, "event_end", { kind: "ct_breakdown" }),
        ev(10, "diverted", { patient: "P046", esi: 2 }),
      ],
    });
    const texts = describeEvents(t).map((l) => l.text);
    expect(texts).toEqual([
      "Bus crash: 10 casualties incoming over 2 ticks",
      "P042 (ESI 2) died in the waiting room",
      "N2 fainted from exhaustion (out 10 ticks)",
      "P020 got worse: now ESI 2, needs CT",
      "P043 (ESI 4) gave up and left",
      "3 arrivals: ESI 1×1, ESI 4×2",
      "1 patient diverted elsewhere: ESI 2×1",
      "2 patients treated and discharged",
      "1 of 3 on-shift staff above fatigue 60 (count as 0.6)",
      "CT scanner is working again",
    ]);
    expect(describeEvents(t)[5].detail).toBe("2 from the bus crash");
  });

  it("returns nothing for a quiet tick", () => {
    expect(describeEvents(tick({ events: [ev(10, "staff_fatigue", { on_shift_above_60: 0, on_shift: 3 })] }))).toEqual(
      [],
    );
  });
});

describe("describeStaffChanges", () => {
  it("reports arrivals, exits, sick calls and returns but not faints", () => {
    const prev = obs({
      staff: [
        staff("AN1", { status: "agency_ordered", ticks_until_change: 1 }),
        staff("AD1", { status: "on_shift", location: "resus" }),
        staff("N4", { status: "on_shift", location: "acute" }),
        staff("N5", { status: "sick" }),
        staff("N6", { status: "fainted" }),
        staff("N7", { status: "on_shift", location: "acute" }),
      ],
    });
    const cur = obs({
      staff: [
        staff("AN1"),
        staff("AD1", { status: "agency_left" }),
        staff("N4", { status: "sick" }),
        staff("N5"),
        staff("N6", { fatigue: 65.2 }),
        staff("N7", { status: "fainted" }),
        staff("AN2", { status: "agency_ordered" }),
      ],
    });
    expect(describeStaffChanges(prev, cur).map((l) => l.text)).toEqual([
      "AN1 (agency nurse) arrived for a 16-tick contract",
      "Contract ended for AD1 (agency doctor)",
      "N4 called in sick",
      "N5 is back from sick leave (resting)",
      "N6 recovered from fainting (resting, fatigue 65)",
    ]);
    expect(describeStaffChanges(undefined, cur)).toEqual([]);
  });
});

describe("bannersFor", () => {
  it("announces event starts, a fixed CT and a successful diversion", () => {
    const t = tick({
      events: [
        ev(10, "event_start", { kind: "bus_crash", ends_tick: 12 }),
        ev(10, "event_end", { kind: "ct_breakdown" }),
        ev(10, "event_end", { kind: "flu_wave" }),
      ],
      actions: [{ type: "divert" }],
      results: [{ index: 0, ok: true }],
    });
    expect(bannersFor(t).map((b) => b.text)).toEqual(["BUS CRASH!", "CT FIXED", "DIVERSION ON"]);
    expect(bannersFor(tick({ actions: [{ type: "divert" }], results: [{ index: 0, ok: false }] }))).toEqual([]);
  });
});

describe("describeWarnings", () => {
  it("shows only announced events that have not started", () => {
    const o = obs({
      warnings: [
        { event: "bus_crash", start_tick: 18 },
        { event: "flu_wave", start_tick: 5 },
      ],
    });
    const w = describeWarnings(o);
    expect(w).toHaveLength(1);
    expect(w[0].text).toBe("Bus crash expected at tick 18 (Day 1 17:00)");
    expect(w[0].detail).toBe("in 8 ticks");
  });
});

describe("zoneCapacity", () => {
  it("takes the smaller of doctor and nurse coverage, tired staff at 0.6", () => {
    const o = obs({
      staff: [
        staff("D1", { status: "on_shift", location: "acute" }),
        staff("N1", { status: "on_shift", location: "acute", counts_as: 0.6 }),
        staff("N2", { status: "on_shift", location: "acute" }),
      ],
    });
    expect(zoneCapacity(o, "acute")).toBe(3); // doctors 1×3 = 3, nurses 1.6×2 = 3.2
    expect(zoneCapacity(o, "resus")).toBe(0);
  });
});

describe("scoreParts", () => {
  it("splits the score formula into points", () => {
    const s = { reward: 0.9, score: 90, O: 0.9, T: 0.5, W: 1, B: 0.5, spend: 0, totals: {}, failures: {} } as ScoreSummary;
    const p = scoreParts(s);
    expect(p.map((x) => +x.points.toFixed(2))).toEqual([54, 10, 9, 4.5]);
    expect(p.map((x) => x.max)).toEqual([60, 20, 10, 10]);
  });
});

function replayOf(ticks: ReplayTick[]): Replay {
  const score = { reward: 0, score: 0, O: 0, T: 0, W: 0, B: 0, spend: 0, totals: {}, failures: {} } as ScoreSummary;
  return {
    version: 1,
    meta: { name: "test", policy: "test", label: "Test", seed: 1, reward: 0, score },
    ticks,
    final_obs: ticks[ticks.length - 1].obs,
  };
}

describe("timeline", () => {
  const ticks: ReplayTick[] = Array.from({ length: 12 }, (_, i) =>
    tick({ tick: i, obs: obs({ tick: i, diversion: { active: i >= 6 && i < 9, ticks_left: 9 - i } }) }),
  );
  ticks[1].events = [ev(1, "event_start", { kind: "ct_breakdown", ends_tick: 10 })];
  ticks[4].events = [
    ev(4, "event_end", { kind: "ct_breakdown" }),
    ev(4, "spend", { item: "repair", amount: 2000 }),
    ev(4, "death", { patient: "P042", cause: "waiting" }),
    ev(4, "faint", { staff: "N3" }),
  ];
  ticks[5].events = [ev(5, "event_start", { kind: "bus_crash", ends_tick: 7 }), ev(5, "left", { patient: "P043" })];
  ticks[5].actions = [{ type: "repair" }];
  ticks[5].results = [{ index: 0, ok: false, reason: "ct_not_broken" }];
  ticks[11].events = [ev(11, "event_start", { kind: "flu_wave", ends_tick: 20 })];
  const r = replayOf(ticks);

  it("builds bands from event_start/end, clipped to the episode, plus diversion runs", () => {
    const d = buildTimeline(r);
    expect(d.bands).toEqual([
      { kind: "ct_breakdown", start: 1, end: 4 },
      { kind: "bus_crash", start: 5, end: 7 },
      { kind: "flu_wave", start: 11, end: 12 },
      { kind: "diversion", start: 6, end: 9 },
    ]);
    expect(d.marks[4]).toMatchObject({ deaths: 1, faints: 1, spend: 2000 });
    expect(d.marks[5]).toMatchObject({ rejected: 1, left: 1 });
    expect(tickSummary(d, 4)).toBe("tick 4 · Day 1 10:00 · 1 death · 1 faint · €2,000 spent · 2 waiting");
  });

  it("lists mistakes in tick order", () => {
    expect(findMistakes(r).map((m) => `${m.tick} ${m.text}`)).toEqual([
      "4 P042 (ESI 2) died waiting",
      "4 N3 fainted",
      "5 P043 (ESI 4) left untreated",
    ]);
  });
});
