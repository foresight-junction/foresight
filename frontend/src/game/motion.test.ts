import { describe, expect, it } from "vitest";
import { easeSettle, linearAt, poseAt, stepAt, type Leg } from "./motion";

const leg = (over: Partial<Leg> = {}): Leg => ({
  t0: 0.2,
  t1: 0.6,
  from: { x: 0, y: 0 },
  to: { x: 100, y: 0 },
  lag: 0,
  windup: 0,
  settle: false,
  ...over,
});

describe("motion", () => {
  it("evaluates step and linear keys", () => {
    const keys = [
      { at: 0, v: 0 },
      { at: 0.5, v: 10 },
    ];
    expect(stepAt(keys, 0.49)).toBe(0);
    expect(stepAt(keys, 0.5)).toBe(10);
    expect(linearAt(keys, 0.25)).toBe(5);
    expect(linearAt([], 0.3)).toBe(1);
  });

  it("overshoots a little at the end and settles exactly", () => {
    const samples = Array.from({ length: 101 }, (_, i) => easeSettle(i / 100));
    expect(samples[0]).toBeCloseTo(0);
    expect(samples[100]).toBeCloseTo(1);
    expect(Math.max(...samples)).toBeGreaterThan(1);
    expect(Math.max(...samples)).toBeLessThan(1.15);
  });

  it("walks with a small bob and stands still at both ends", () => {
    const l = leg();
    expect(poseAt(l.from, [l], 0.1)).toMatchObject({ x: 0, y: 0, moving: false });
    const mid = poseAt(l.from, [l], 0.4);
    expect(mid).toMatchObject({ moving: true, facing: "right" });
    expect(mid.y).toBeLessThanOrEqual(0);
    expect(mid.y).toBeGreaterThanOrEqual(-1);
    expect(poseAt(l.from, [l], 0.7)).toMatchObject({ x: 100, y: 0, moving: false });
  });

  it("caps the overshoot to a few pixels past the spot", () => {
    const l = leg({ settle: true, to: { x: 400, y: 0 } });
    const xs = Array.from({ length: 41 }, (_, i) => poseAt(l.from, [l], 0.2 + i * 0.01).x);
    expect(Math.max(...xs)).toBeGreaterThan(400);
    expect(Math.max(...xs)).toBeLessThan(406);
  });

  it("leans back before getting up", () => {
    const l = leg({ windup: 0.1 });
    const lean = poseAt(l.from, [l], 0.15);
    expect(lean.x).toBeLessThan(0);
    expect(lean).toMatchObject({ facing: "right", moving: false });
  });

  it("starts without the stagger in fast mode", () => {
    const l = leg({ t0: 0.3, lag: 0.1 });
    expect(poseAt(l.from, [l], 0.25).moving).toBe(false);
    expect(poseAt(l.from, [l], 0.25, true).moving).toBe(true);
  });
});
