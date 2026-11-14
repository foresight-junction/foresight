// Walking paths for people in the department, behind one swappable router.
// Owner: agent D (playback + animation).

import type { Point } from "../replay/frame";
import { route } from "../world/path";

export type Router = (from: Point, to: Point) => Point[];

// An L-shaped path (horizontal, then vertical); kept for tests that run without a floor plan.
export function lPath(from: Point, to: Point): Point[] {
  return [from, { x: to.x, y: from.y }, to];
}

const ROUTER: Router = route;

const cache = new Map<string, Point[]>();

// Waypoints from `from` to `to`, always starting and ending exactly there. Cached: many walks share ends.
export function walkPath(from: Point, to: Point): Point[] {
  const key = `${from.x},${from.y}>${to.x},${to.y}`;
  let path = cache.get(key);
  if (!path) {
    path = normalize(from, to, ROUTER(from, to));
    cache.set(key, path);
  }
  return path;
}

function normalize(from: Point, to: Point, raw: Point[]): Point[] {
  const out: Point[] = [from];
  for (const p of [...raw, to]) {
    const last = out[out.length - 1];
    if (p.x !== last.x || p.y !== last.y) out.push({ x: p.x, y: p.y });
  }
  return out;
}

export function pathLength(path: Point[]): number {
  let len = 0;
  for (let i = 1; i < path.length; i++) len += Math.hypot(path[i].x - path[i - 1].x, path[i].y - path[i - 1].y);
  return len;
}

// The point `dist` pixels along the path (clamped to its ends), and the segment index it lies on.
export function pointAlong(path: Point[], dist: number): { x: number; y: number; seg: number } {
  let left = Math.max(0, dist);
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1];
    const b = path[i];
    const len = Math.hypot(b.x - a.x, b.y - a.y);
    if (left <= len && len > 0) {
      const u = left / len;
      return { x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u, seg: i };
    }
    left -= len;
  }
  const end = path[path.length - 1];
  return { x: end.x, y: end.y, seg: Math.max(1, path.length - 1) };
}
