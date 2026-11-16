// Small timeline primitives the per-tick plans are made of: step keys, linear keys and walking legs,
// plus the bits that give motion some character (overshoot, footstep bob, anticipation, spins).

import type { Facing, Point } from "../replay/frame";
import { pathLength, pointAlong, walkPath } from "./paths";

// A value that holds from phase `at` on (until the next key).
export interface Key<T> {
  at: number;
  v: T;
}

// One walk inside a tick: stand at `from` until t0, walk the path, stand at `to` after t1.
export interface Leg {
  t0: number;
  t1: number;
  from: Point;
  to: Point;
  lag: number; // part of t0 that is crowd stagger, dropped at high speed
  windup: number; // anticipation before t0: a small lean back, already facing the way out
  settle: boolean; // ease-out-back into the spot (a tiny overshoot)
  path?: Point[]; // resolved on first use, so loading a replay never runs the router
  len?: number;
}

export function stepAt<T>(keys: Key<T>[], phase: number): T {
  let v = keys[0].v;
  for (const k of keys) {
    if (k.at > phase) break;
    v = k.v;
  }
  return v;
}

// Piecewise linear between keys; holds the first and last value outside them.
export function linearAt(keys: Key<number>[], phase: number): number {
  if (keys.length === 0) return 1;
  if (phase <= keys[0].at) return keys[0].v;
  for (let i = 1; i < keys.length; i++) {
    const a = keys[i - 1];
    const b = keys[i];
    if (phase <= b.at) return b.at === a.at ? b.v : a.v + ((b.v - a.v) * (phase - a.at)) / (b.at - a.at);
  }
  return keys[keys.length - 1].v;
}

export const easeInOut = (u: number): number => 0.5 - Math.cos(Math.PI * u) / 2;

// Like linearAt, but eases in and out between each pair of keys (vehicles pulling away and braking).
export function easedAt(keys: Key<number>[], phase: number): number {
  if (phase <= keys[0].at) return keys[0].v;
  for (let i = 1; i < keys.length; i++) {
    const a = keys[i - 1];
    const b = keys[i];
    if (phase <= b.at) return b.at === a.at ? b.v : a.v + (b.v - a.v) * easeInOut((phase - a.at) / (b.at - a.at));
  }
  return keys[keys.length - 1].v;
}

const OVERSHOOT = 0.08;
const SETTLE_AT = 0.8;
// Ease-out-back with the back part kept short: a smooth walk that runs a little past the spot over the
// first 80%, then settles back onto it at exactly 1.
export const easeSettle = (u: number): number =>
  u < SETTLE_AT
    ? easeInOut(u / SETTLE_AT) * (1 + OVERSHOOT)
    : 1 + OVERSHOOT * (1 - easeInOut((u - SETTLE_AT) / (1 - SETTLE_AT)));

const STEP_PX = 6; // one footstep
const BOB_PX = 1;
const LEAN_PX = 1.5;
const OVERSHOOT_BASE_PX = 48; // overshoot is a fraction of this, so a long walk never flies past its seat

export interface Pose extends Point {
  moving: boolean;
  facing: Facing;
}

export function facingOf(dx: number, dy: number): Facing {
  if (Math.abs(dx) >= Math.abs(dy)) return dx >= 0 ? "right" : "left";
  return dy >= 0 ? "down" : "up";
}

function resolve(leg: Leg): { path: Point[]; len: number } {
  leg.path ??= walkPath(leg.from, leg.to);
  leg.len ??= pathLength(leg.path);
  return { path: leg.path, len: leg.len };
}

const still = (p: Point): Pose => ({ x: p.x, y: p.y, moving: false, facing: "down" });

// `fast` drops the crowd stagger: at high playback speeds it reads as lag, not as a crowd.
export function poseAt(from: Point, legs: Leg[], phase: number, fast = false): Pose {
  for (const leg of legs) {
    const t0 = fast ? leg.t0 - leg.lag : leg.t0;
    if (phase < t0) {
      const w = leg.windup;
      if (w > 0 && phase >= t0 - w && (leg.from.x !== leg.to.x || leg.from.y !== leg.to.y)) {
        const { path } = resolve(leg);
        const dx = path[1].x - path[0].x;
        const dy = path[1].y - path[0].y;
        const n = Math.hypot(dx, dy) || 1;
        const lean = Math.sin((Math.PI * (phase - (t0 - w))) / w) * LEAN_PX;
        return { x: leg.from.x - (dx / n) * lean, y: leg.from.y - (dy / n) * lean, moving: false, facing: facingOf(dx, dy) };
      }
      return still(leg.from);
    }
    if (phase <= leg.t1) {
      const { path, len } = resolve(leg);
      const u = leg.t1 > t0 ? (phase - t0) / (leg.t1 - t0) : 1;
      if (len === 0 || u >= 1) return still(leg.to);
      const f = leg.settle ? easeSettle(u) : easeInOut(u);
      const dist = Math.min(f, 1) * len;
      const p = pointAlong(path, dist);
      const a = path[p.seg - 1];
      const b = path[p.seg];
      let { x, y } = p;
      if (f > 1) {
        const last = path[path.length - 2];
        const n = Math.hypot(leg.to.x - last.x, leg.to.y - last.y) || 1;
        const over = (f - 1) * Math.min(len, OVERSHOOT_BASE_PX);
        x = leg.to.x + ((leg.to.x - last.x) / n) * over;
        y = leg.to.y + ((leg.to.y - last.y) / n) * over;
      }
      const bob = f < 1 ? Math.abs(Math.sin((Math.PI * dist) / STEP_PX)) * BOB_PX : 0;
      return { x, y: y - bob, moving: u > 0 && f < 1, facing: facingOf(b.x - a.x, b.y - a.y) };
    }
  }
  return still(legs.length ? legs[legs.length - 1].to : from);
}

const SPIN: Facing[] = ["down", "left", "up", "right"];

// Facing while spinning around before a faint: two full turns over the window.
export function spinFacing(t0: number, t1: number, phase: number): Facing | null {
  if (phase < t0 || phase >= t1) return null;
  return SPIN[Math.floor(((phase - t0) / (t1 - t0)) * 8) % 4];
}

// Deterministic 0..1 per id, so a crowd starts walking at slightly different moments on every replay load.
export function jitter(id: string): number {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) h = Math.imul(h ^ id.charCodeAt(i), 16777619);
  return ((h >>> 0) % 1000) / 1000;
}
