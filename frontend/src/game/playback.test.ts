import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { Frame, PatientEntity } from "../replay/frame";
import type { Replay } from "../replay/types";
import { buildLayout } from "../world/layout";
import { fixtureReplay } from "./fixture";
import { Playback } from "./playback";

const layout = buildLayout();
const reference = JSON.parse(
  readFileSync(new URL("../../public/replays/reference-seed42.json", import.meta.url), "utf-8"),
) as Replay;

function frameAt(pb: Playback, tick: number, phase: number): Frame {
  pb.seek(tick);
  pb.phase = phase;
  return pb.frame();
}

const bedPoint = (bed: string) => ({ x: layout.beds[bed].x, y: layout.beds[bed].y });
const byId = <T extends { id: string }>(xs: T[]): Map<string, T> => new Map(xs.map((x) => [x.id, x]));

// Invariants every replay must satisfy, checked tick by tick.
function checkInvariants(replay: Replay): void {
  const pb = new Playback(replay, layout);
  for (let t = 0; t < pb.tickCount; t++) {
    const obs = replay.ticks[t].obs;
    const start = frameAt(pb, t, 0);
    const end = frameAt(pb, t, 1);

    // Phase 0 shows exactly the patients the AI observed, once each, in their bed or a seat of their own.
    const ids = start.patients.map((p) => p.id);
    expect(new Set(ids).size, `tick ${t} duplicate patient`).toBe(ids.length);
    const observed = [...obs.waiting.map((w) => w.id), ...obs.beds.flatMap((b) => (b.patient ? [b.patient] : []))];
    expect(new Set(ids), `tick ${t} patients`).toEqual(new Set(observed));
    for (const b of obs.beds) {
      if (!b.patient) continue;
      const p = start.patients.find((x) => x.id === b.patient)!;
      expect({ x: p.x, y: p.y, state: p.state }).toEqual({ ...bedPoint(b.bed), state: "in_bed" });
    }
    const seats = start.patients.filter((p) => p.state === "waiting").map((p) => `${p.x},${p.y}`);
    expect(new Set(seats).size, `tick ${t} shared seat`).toBe(seats.length);
    const spots = start.staff.filter((s) => s.status === "on_shift" || s.status === "resting").map((s) => `${s.x},${s.y}`);
    expect(new Set(spots).size, `tick ${t} shared staff spot`).toBe(spots.length);

    for (const ph of [0, 0.1, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9, 1]) {
      const f = frameAt(pb, t, ph);
      const fid = f.patients.map((p) => p.id);
      expect(new Set(fid).size, `tick ${t} phase ${ph} duplicate patient`).toBe(fid.length);
      for (const e of [...f.patients, ...f.staff]) {
        expect(Number.isFinite(e.x) && Number.isFinite(e.y)).toBe(true);
        expect(e.alpha).toBeGreaterThan(0);
        expect(e.alpha).toBeLessThanOrEqual(1);
      }
      for (const fx of f.effects) expect(fx.age >= 0 && fx.age < 1).toBe(true);
    }

    // Nobody jumps between ticks: the end of tick t is the start of tick t+1.
    if (t + 1 < pb.tickCount) {
      const nextStart = frameAt(pb, t + 1, 0);
      const endP = byId(end.patients);
      for (const p of nextStart.patients) {
        const q = endP.get(p.id);
        expect(q, `tick ${t + 1} patient ${p.id} popped in`).toBeDefined();
        expect({ x: q!.x, y: q!.y }, `tick ${t}->${t + 1} ${p.id}`).toEqual({ x: p.x, y: p.y });
      }
      const endS = byId(end.staff);
      for (const s of nextStart.staff) {
        const q = endS.get(s.id);
        expect(q, `tick ${t + 1} staff ${s.id} popped in`).toBeDefined();
        expect({ x: q!.x, y: q!.y }, `tick ${t}->${t + 1} ${s.id}`).toEqual({ x: s.x, y: s.y });
      }
    }

    // Admitted patients finish the tick in their bed (unless discharged or dead in the same tick).
    for (const e of replay.ticks[t].events) {
      if (e.event !== "admitted") continue;
      const gone = replay.ticks[t].events.some(
        (x) => (x.event === "discharged" || x.event === "death") && x.patient === e.patient,
      );
      if (gone) continue;
      const p = end.patients.find((x) => x.id === e.patient)!;
      expect({ x: p.x, y: p.y, state: p.state, bed: p.bed }).toEqual({ ...bedPoint(String(e.bed)), state: "in_bed", bed: e.bed });
    }
  }
}

describe("Playback on the hand-made fixture", () => {
  const replay = fixtureReplay();
  const pb = new Playback(replay, layout);

  it("keeps the world invariants", () => checkInvariants(replay));

  it("walks an admitted patient from the seat to the bed", () => {
    const seat = frameAt(pb, 0, 0).patients.find((p) => p.id === "P002")!;
    expect(seat.state).toBe("waiting");
    const mid = frameAt(pb, 0, 0.25).patients.find((p) => p.id === "P002")!;
    expect(mid).toMatchObject({ state: "to_bed", moving: true, bed: "R1" });
    expect(frameAt(pb, 0, 1).patients.find((p) => p.id === "P002")).toMatchObject({ ...bedPoint("R1"), state: "in_bed" });
  });

  it("keeps a waiting patient's seat while others come and go", () => {
    const at0 = frameAt(pb, 0, 0).patients.find((p) => p.id === "P001")!;
    const at1 = frameAt(pb, 1, 0).patients.find((p) => p.id === "P001")!;
    expect({ x: at1.x, y: at1.y }).toEqual({ x: at0.x, y: at0.y });
  });

  it("brings arrivals in from the entrance", () => {
    const f = frameAt(pb, 0, 0.5);
    const p = f.patients.find((x) => x.id === "P004")!;
    expect(p.state).toBe("arriving");
    expect(f.effects.some((e) => e.kind === "arrival")).toBe(true);
    expect(frameAt(pb, 0, 0.35).patients.find((x) => x.id === "P004")).toBeUndefined();
  });

  it("walks a discharged patient to the exit and fades them", () => {
    const leaving = frameAt(pb, 1, 0.6).patients.find((p) => p.id === "P003")!;
    expect(leaving).toMatchObject({ state: "leaving", bed: null, moving: true });
    expect(frameAt(pb, 1, 1).patients.find((p) => p.id === "P003")).toBeUndefined();
  });

  it("shows a diverted patient turning away", () => {
    const f = frameAt(pb, 0, 0.65);
    expect(f.patients.find((p) => p.id === "P005")).toMatchObject({ state: "leaving" });
    expect(f.effects.some((e) => e.kind === "diverted")).toBe(true);
    expect(frameAt(pb, 1, 0).patients.find((p) => p.id === "P005")).toBeUndefined();
  });

  it("lets the dead lie in place and fade", () => {
    const dead = frameAt(pb, 2, 0.8).patients.find((p) => p.id === "P002")!;
    expect(dead).toMatchObject({ ...bedPoint("R1"), state: "dead", moving: false });
    expect(dead.alpha).toBeLessThan(1);
    expect(frameAt(pb, 2, 0.7).effects.find((e) => e.kind === "death")?.text).toBe("P002 died");
    expect(frameAt(pb, 3, 0).patients.find((p) => p.id === "P002")).toBeUndefined();
  });

  it("upgrades ESI mid-tick", () => {
    expect(frameAt(pb, 0, 0.3).patients.find((p) => p.id === "P001")?.esi).toBe(3);
    const up = frameAt(pb, 0, 0.7);
    expect(up.patients.find((p) => p.id === "P001")).toMatchObject({ esi: 2, needsCt: true });
    expect(up.effects.some((e) => e.kind === "upgrade")).toBe(true);
  });

  it("drops a fainted nurse, then carries her offstage", () => {
    const fell = frameAt(pb, 1, 0.8).staff.find((s) => s.id === "N1")!;
    const before = frameAt(pb, 1, 0.35).staff.find((s) => s.id === "N1")!;
    const spinning = [0.41, 0.43, 0.46, 0.48].map((ph) => frameAt(pb, 1, ph).staff.find((s) => s.id === "N1")!.facing);
    expect(new Set(spinning).size).toBeGreaterThan(1);
    expect(fell.status).toBe("fainted");
    expect({ x: fell.x, y: fell.y }).toEqual({ x: before.x, y: before.y });
    const carried = frameAt(pb, 2, 1).staff.find((s) => s.id === "N1")!;
    expect(Math.hypot(carried.x - layout.offstage.x, carried.y - layout.offstage.y)).toBeLessThan(40);
    expect(carried.moving).toBe(false);
  });

  it("walks staff to their zone and counts coverage", () => {
    const f0 = frameAt(pb, 0, 0);
    expect(f0.zoneCoverage.resus).toBe(0);
    const f1 = frameAt(pb, 0, 1);
    expect(f1.staff.find((s) => s.id === "D1")).toMatchObject({ ...layout.staffSlot("resus", 0), location: "resus" });
    expect(f1.zoneCoverage.resus).toBeCloseTo(1.6);
  });

  it("brings agency staff in and sends them out", () => {
    expect(frameAt(pb, 1, 0).staff.find((s) => s.id === "AD1")).toBeUndefined();
    const arriving = frameAt(pb, 2, 0.55).staff.find((s) => s.id === "AD1")!;
    expect(arriving.moving).toBe(true);
    expect(frameAt(pb, 3, 0).staff.find((s) => s.id === "AD1")).toMatchObject({ ...layout.restSlot(0), status: "resting" });
    expect(frameAt(pb, 4, 0.6).staff.find((s) => s.id === "AD1")?.status).toBe("agency_left");
    expect(frameAt(pb, 5, 0).staff.find((s) => s.id === "AD1")).toBeUndefined();
  });

  it("spawns spend, rejection and event effects", () => {
    const f = frameAt(pb, 0, 0.3);
    expect(f.effects.find((e) => e.kind === "spend")?.text).toBe("-€900");
    expect(f.effects.find((e) => e.kind === "rejected")?.text).toBe("unknown_patient");
    const r3 = frameAt(pb, 3, 0.2).effects.find((e) => e.kind === "rejected")!;
    expect(r3.text).toBe("staff_unavailable");
    const start = frameAt(pb, 1, 0.7);
    expect(start.effects.find((e) => e.kind === "event_start")?.text).toBe("staff sickness");
    expect(start.activeEvents).toEqual(["staff_sickness"]);
    expect(frameAt(pb, 1, 0.3).activeEvents).toEqual([]);
    expect(frameAt(pb, 3, 0.9).effects.some((e) => e.kind === "event_end")).toBe(true);
  });

  it("lets effects run a little into the next tick", () => {
    expect(frameAt(pb, 1, 0.1).effects.some((e) => e.kind === "spend")).toBe(true);
  });

  it("exposes timeline markers and entity info", () => {
    const m = pb.timelineMarkers();
    expect(m).toHaveLength(6);
    expect(m[1]).toMatchObject({ arrivals: 1, diverted: 1, discharged: 1, left: 1, faints: 1 });
    expect(m[0]).toMatchObject({ rejected: 1, spend: 900 });
    expect(pb.entityInfo("P002")).toMatchObject({ kind: "patient", outcome: "died", cause: "uncovered_bed", bed: "R1" });
    expect(pb.entityInfo("P001")).toMatchObject({ esi: 2, arrivalEsi: 3, admittedTick: 1 });
    expect(pb.entityInfo("P005")).toMatchObject({ outcome: "diverted" });
    pb.seek(0);
    expect(pb.entityInfo("N1")).toMatchObject({ kind: "staff", status: "resting" });
    expect(pb.entityInfo("nobody")).toBeNull();
  });
});

describe("Playback speed", () => {
  it("drops the crowd stagger at 8x and above", () => {
    const pb = new Playback(fixtureReplay(), layout);
    const starts = (fast: boolean): number[] =>
      ["P001", "P003"].map((id) => {
        pb.speed = fast ? 8 : 2;
        for (let ph = 0; ph <= 1; ph += 0.005) {
          if (frameAt(pb, 1, ph).patients.find((p) => p.id === id)?.moving) return Math.round(ph * 1000) / 1000;
        }
        return -1;
      });
    const [a, b] = starts(true);
    expect(a).toBe(b);
    const [c, d] = starts(false);
    expect(Math.max(c, d)).toBeGreaterThan(a);
  });
});

describe("Playback controls", () => {
  it("advances with speed, fires onTick, and stops at the end", () => {
    const pb = new Playback(fixtureReplay(), layout);
    const seen: number[] = [];
    pb.onTick((t) => seen.push(t));
    pb.speed = 4;
    pb.play();
    pb.update(500); // 2 ticks
    expect(pb.tick).toBe(2);
    pb.speed = 1; // takes effect on the next update
    pb.update(250);
    expect(pb.tick).toBe(2);
    expect(pb.phase).toBeCloseTo(0.25);
    pb.update(100_000);
    expect(pb.tick).toBe(5);
    expect(pb.phase).toBe(1);
    expect(pb.playing).toBe(false);
    expect(seen).toEqual([1, 2, 3, 4, 5]);
    pb.toggle(); // play again from the start
    expect(pb).toMatchObject({ tick: 0, playing: true });
    pb.stepForward();
    pb.stepBack();
    pb.stepBack();
    expect(pb).toMatchObject({ tick: 0, phase: 0 });
    pb.seek(99);
    expect(pb.tick).toBe(5);
  });
});

describe("Playback on the reference replay", () => {
  it("keeps the world invariants", () => checkInvariants(reference));

  it("seeks to any tick and phase without throwing", () => {
    const pb = new Playback(reference, layout);
    for (const t of [143, 0, 77, 12, 143, 1]) {
      pb.seek(t);
      expect(pb.frame().tick).toBe(t);
    }
  });

  it("plans the replay and computes 144 frames in under 200 ms", () => {
    const t0 = performance.now();
    const pb = new Playback(reference, layout);
    let patients: PatientEntity[] = [];
    for (let t = 0; t < pb.tickCount; t++) {
      pb.seek(t);
      pb.phase = (t % 10) / 10;
      patients = pb.frame().patients;
    }
    expect(patients.length).toBeGreaterThanOrEqual(0);
    expect(performance.now() - t0).toBeLessThan(200);
  });
});

// Any extra replay, e.g. one full of deaths and faints: EXTRA_REPLAY=path/to/replay.json pnpm test
const extra = (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env.EXTRA_REPLAY;
describe.runIf(extra && existsSync(extra))("Playback on EXTRA_REPLAY", () => {
  it("keeps the world invariants", () => checkInvariants(JSON.parse(readFileSync(extra!, "utf-8")) as Replay));
});
