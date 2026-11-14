// Walking routes over the tile grid: Dijkstra on 4-connected tiles, then string-pulled into a few
// straight segments. Walls never pass; furniture (beds, CT, seats, desks) costs extra, so people walk
// around it unless it is where they are going. Pure and cached: same (from, to) tiles, same route.

import type { Point } from "../replay/frame";
import { buildLayout, FURNITURE, MAP_COLS, MAP_ROWS, TILE } from "./layout";

const FURNITURE_COST = 25;

interface Grid {
  wall: Uint8Array; // 1 = never walkable
  cost: Uint8Array; // step cost into the tile
}

let grid: Grid | null = null;
const cache = new Map<number, Point[]>();

function getGrid(): Grid {
  if (grid) return grid;
  const layout = buildLayout();
  const wall = new Uint8Array(MAP_COLS * MAP_ROWS);
  const cost = new Uint8Array(MAP_COLS * MAP_ROWS).fill(1);
  layout.tiles.forEach((row, r) => row.forEach((k, c) => (wall[r * MAP_COLS + c] = k === "wall" ? 1 : 0)));
  const block = (c0: number, r0: number, c1: number, r1: number): void => {
    for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) cost[r * MAP_COLS + c] = FURNITURE_COST;
  };
  for (const f of FURNITURE) if (f.blocks) block(f.c0, f.r0, f.c1, f.r1);
  for (const at of Object.values(layout.beds)) {
    const c = Math.floor(at.x / TILE);
    const r = Math.floor(at.y / TILE);
    block(c, r, c, r + 1);
  }
  const ctC = Math.floor(layout.ct.x / TILE);
  const ctR = Math.floor(layout.ct.y / TILE);
  block(ctC, ctR, Math.floor((layout.ct.x + 31) / TILE), ctR + 1);
  grid = { wall, cost };
  return grid;
}

export function isWalkable(c: number, r: number): boolean {
  if (c < 0 || r < 0 || c >= MAP_COLS || r >= MAP_ROWS) return false;
  return getGrid().wall[r * MAP_COLS + c] === 0;
}

// Tile an entity stands on: the one under the centre of its 16x16 cell, clamped onto the map.
export function tileOf(p: Point): [number, number] {
  const c = Math.floor((p.x + TILE / 2) / TILE);
  const r = Math.floor((p.y + TILE / 2) / TILE);
  return [Math.max(0, Math.min(MAP_COLS - 1, c)), Math.max(0, Math.min(MAP_ROWS - 1, r))];
}

// Nearest walkable tile (breadth-first ring search), for points that sit on a wall or off the map.
function nearestWalkable(c: number, r: number): number {
  if (isWalkable(c, r)) return r * MAP_COLS + c;
  for (let d = 1; d < MAP_COLS + MAP_ROWS; d++) {
    for (let dr = -d; dr <= d; dr++) {
      const dc = d - Math.abs(dr);
      for (const cc of dc === 0 ? [c] : [c - dc, c + dc]) {
        if (isWalkable(cc, r + dr)) return (r + dr) * MAP_COLS + cc;
      }
    }
  }
  throw new Error("map has no walkable tile");
}

// Cheapest 4-connected tile path from a to b (both indices), inclusive, or null if unreachable.
export function findTilePath(a: number, b: number): number[] | null {
  const { wall, cost } = getGrid();
  const n = MAP_COLS * MAP_ROWS;
  const dist = new Float64Array(n).fill(Infinity);
  const prev = new Int32Array(n).fill(-1);
  const heap: number[] = [];
  const heapD: number[] = [];
  const push = (idx: number, d: number): void => {
    heap.push(idx);
    heapD.push(d);
    let i = heap.length - 1;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (heapD[p] <= heapD[i]) break;
      [heap[p], heap[i]] = [heap[i], heap[p]];
      [heapD[p], heapD[i]] = [heapD[i], heapD[p]];
      i = p;
    }
  };
  const pop = (): number => {
    const top = heap[0];
    const lastI = heap.pop() as number;
    const lastD = heapD.pop() as number;
    if (heap.length > 0) {
      heap[0] = lastI;
      heapD[0] = lastD;
      let i = 0;
      for (;;) {
        const l = 2 * i + 1;
        const r = l + 1;
        let m = i;
        if (l < heap.length && heapD[l] < heapD[m]) m = l;
        if (r < heap.length && heapD[r] < heapD[m]) m = r;
        if (m === i) break;
        [heap[m], heap[i]] = [heap[i], heap[m]];
        [heapD[m], heapD[i]] = [heapD[i], heapD[m]];
        i = m;
      }
    }
    return top;
  };
  dist[a] = 0;
  push(a, 0);
  while (heap.length > 0) {
    const d0 = heapD[0];
    const cur = pop();
    if (d0 > dist[cur]) continue;
    if (cur === b) break;
    const c = cur % MAP_COLS;
    const r = (cur - c) / MAP_COLS;
    const next = [c > 0 ? cur - 1 : -1, c < MAP_COLS - 1 ? cur + 1 : -1, r > 0 ? cur - MAP_COLS : -1,
      r < MAP_ROWS - 1 ? cur + MAP_COLS : -1];
    for (const nb of next) {
      if (nb < 0 || wall[nb]) continue;
      // The goal's own furniture is free to step onto (a bed, a seat): that is where we are going.
      const step = nb === b ? 1 : cost[nb];
      const nd = d0 + step;
      if (nd < dist[nb]) {
        dist[nb] = nd;
        prev[nb] = cur;
        push(nb, nd);
      }
    }
  }
  if (dist[b] === Infinity) return null;
  const path: number[] = [];
  for (let i = b; i !== -1; i = prev[i]) path.push(i);
  return path.reverse();
}

// True when a 16x16 walker can slide straight from tile a to tile b touching only allowed tiles.
function clearLine(a: number, b: number, allowed: Set<number>): boolean {
  const ax = (a % MAP_COLS) * TILE;
  const ay = Math.floor(a / MAP_COLS) * TILE;
  const bx = (b % MAP_COLS) * TILE;
  const by = Math.floor(b / MAP_COLS) * TILE;
  const steps = Math.ceil(Math.max(Math.abs(bx - ax), Math.abs(by - ay)) / 4);
  const { wall, cost } = getGrid();
  for (let s = 0; s <= steps; s++) {
    const x = ax + ((bx - ax) * s) / steps;
    const y = ay + ((by - ay) * s) / steps;
    for (const [ox, oy] of [[2, 2], [13, 2], [2, 13], [13, 13]]) {
      const idx = Math.floor((y + oy) / TILE) * MAP_COLS + Math.floor((x + ox) / TILE);
      if (wall[idx]) return false;
      if (cost[idx] > 1 && !allowed.has(idx)) return false;
    }
  }
  return true;
}

function smooth(path: number[]): number[] {
  if (path.length <= 2) return path;
  const allowed = new Set(path);
  const out = [path[0]];
  let i = 0;
  while (i < path.length - 1) {
    let j = path.length - 1;
    while (j > i + 1 && !clearLine(path[i], path[j], allowed)) j--;
    out.push(path[j]);
    i = j;
  }
  return out;
}

// Waypoints from `from` to `to`: corner points (tile top-left pixels) and finally `to` itself.
// `from` is not included. Off-map endpoints (offstage) are reached via the nearest walkable tile.
// Never throws for reachable maps; if somehow no path exists it falls back to [to].
export function route(from: Point, to: Point): Point[] {
  const [fc, fr] = tileOf(from);
  const [tc, tr] = tileOf(to);
  const a = nearestWalkable(fc, fr);
  const b = nearestWalkable(tc, tr);
  const key = a * MAP_COLS * MAP_ROWS + b;
  let corners = cache.get(key);
  if (!corners) {
    const tiles = findTilePath(a, b);
    corners = (tiles ? smooth(tiles) : [b]).map((i) => ({ x: (i % MAP_COLS) * TILE, y: Math.floor(i / MAP_COLS) * TILE }));
    cache.set(key, corners);
  }
  // Drop the start tile and the goal tile: the walker is already near the first and ends exactly on `to`.
  const pts = corners.slice(1, -1).map((p) => ({ ...p }));
  pts.push({ x: to.x, y: to.y });
  return pts;
}
