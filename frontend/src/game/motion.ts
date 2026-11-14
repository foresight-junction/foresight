// Small timeline primitives the per-tick plans are made of: step keys, linear keys and walking legs.
// Owner: agent D (playback + animation).

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

export interface Pose extends Point {
  moving: boolean;
  facing: Facing;
}

export function facingOf(dx: number, dy: number): Facing {
  if (Math.abs(dx) >= Math.abs(dy)) return dx >= 0 ? "right" : "left";
  return dy >= 0 ? "down" : "up";
}

export function poseAt(from: Point, legs: Leg[], phase: number): Pose {
  for (const leg of legs) {
    if (phase < leg.t0) return { x: leg.from.x, y: leg.from.y, moving: false, facing: "down" };
    if (phase <= leg.t1) {
      leg.path ??= walkPath(leg.from, leg.to);
      leg.len ??= pathLength(leg.path);
      const u = leg.t1 > leg.t0 ? (phase - leg.t0) / (leg.t1 - leg.t0) : 1;
      if (leg.len === 0 || u >= 1) return { x: leg.to.x, y: leg.to.y, moving: false, facing: "down" };
      const p = pointAlong(leg.path, easeInOut(u) * leg.len);
      const a = leg.path[p.seg - 1];
      const b = leg.path[p.seg];
      return { x: p.x, y: p.y, moving: u > 0, facing: facingOf(b.x - a.x, b.y - a.y) };
    }
  }
  const end = legs.length ? legs[legs.length - 1].to : from;
  return { x: end.x, y: end.y, moving: false, facing: "down" };
}

// Deterministic 0..1 per id, so a crowd starts walking at slightly different moments on every replay load.
export function jitter(id: string): number {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) h = Math.imul(h ^ id.charCodeAt(i), 16777619);
  return ((h >>> 0) % 1000) / 1000;
}
