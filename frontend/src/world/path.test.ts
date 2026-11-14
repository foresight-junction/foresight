import { describe, expect, it } from "vitest";
import type { Point } from "../replay/frame";
import type { Zone } from "../replay/types";
import { buildLayout, MAP_COLS, MAP_ROWS, TILE } from "./layout";
import { findTilePath, isWalkable, route, tileOf } from "./path";

const L = buildLayout();
const ZONES: Zone[] = ["resus", "acute", "fast_track"];
const N = 120; // more than a 40-patient surge and every staff member in one zone

function onMap(p: Point): boolean {
  return p.x >= 0 && p.y >= 0 && p.x < MAP_COLS * TILE && p.y < MAP_ROWS * TILE;
}

function targets(): [string, Point][] {
  const out: [string, Point][] = [
    ["entrance", L.entrance],
    ["exit", L.exit],
    ["morgue", L.morgue],
    ["ct", L.ct],
  ];
  for (const [id, at] of Object.entries(L.beds)) {
    out.push([`bed ${id}`, at]);
    out.push([`in bed ${id}`, { x: at.x, y: at.y + 4 }]);
  }
  for (let i = 0; i < 60; i++) out.push([`waiting ${i}`, L.waitingSlot(i)]);
  for (let i = 0; i < 30; i++) out.push([`rest ${i}`, L.restSlot(i)]);
  for (const z of ZONES) for (let i = 0; i < 20; i++) out.push([`${z} ${i}`, L.staffSlot(z, i)]);
  return out;
}

describe("layout", () => {
  it("has the 17 beds of SPEC §3 in the right zones", () => {
    const ids = Object.keys(L.beds).sort();
    expect(ids).toHaveLength(17);
    const count = (z: Zone): number => Object.values(L.bedZone).filter((v) => v === z).length;
    expect([count("resus"), count("acute"), count("fast_track")]).toEqual([3, 8, 6]);
  });

  it("tile grid matches MAP_ROWS x MAP_COLS", () => {
    expect(L.tiles).toHaveLength(MAP_ROWS);
    for (const row of L.tiles) expect(row).toHaveLength(MAP_COLS);
  });

  it("slots are distinct and walkable for any i", () => {
    const slotSets: [string, (i: number) => Point][] = [
      ["waiting", L.waitingSlot],
      ["rest", L.restSlot],
      ...ZONES.map((z): [string, (i: number) => Point] => [z, (i) => L.staffSlot(z, i)]),
    ];
    const all = new Set<string>();
    for (const [name, fn] of slotSets) {
      for (let i = 0; i < N * 3; i++) {
        const p = fn(i);
        const key = `${p.x},${p.y}`;
        expect(all.has(key), `${name} ${i} duplicates ${key}`).toBe(false);
        all.add(key);
        const [c, r] = tileOf(p);
        expect(isWalkable(c, r), `${name} ${i} on a wall`).toBe(true);
      }
    }
  });

  it("bed spots, CT and slots never overlap a bed", () => {
    const bedTiles = new Set(Object.values(L.beds).flatMap((b) => [`${b.x / TILE},${b.y / TILE}`, `${b.x / TILE},${b.y / TILE + 1}`]));
    for (let i = 0; i < 100; i++) {
      for (const p of [L.waitingSlot(i), L.restSlot(i), ...ZONES.map((z) => L.staffSlot(z, i))]) {
        const [c, r] = tileOf(p);
        expect(bedTiles.has(`${c},${r}`)).toBe(false);
      }
    }
  });
});

describe("route", () => {
  it("connects the entrance to every bed, slot, exit, morgue and offstage", () => {
    for (const [name, p] of [...targets(), ["offstage", L.offstage] as [string, Point]]) {
      const [ac, ar] = tileOf(L.entrance);
      const [bc, br] = tileOf(p);
      if (onMap(p)) expect(findTilePath(ar * MAP_COLS + ac, br * MAP_COLS + bc), name).not.toBeNull();
      const pts = route(L.entrance, p);
      expect(pts.at(-1), name).toEqual(p);
    }
  });

  it("every segment of every route stays off walls", () => {
    const ts = targets();
    const starts = [L.entrance, L.exit, L.beds.R1, L.beds.A8, L.beds.F6, L.waitingSlot(39), L.restSlot(0), L.offstage];
    for (const from of starts) {
      for (const [name, to] of ts) {
        let prev = from;
        for (const p of route(from, to)) {
          const steps = Math.ceil(Math.hypot(p.x - prev.x, p.y - prev.y) / 2);
          for (let s = 1; s <= steps; s++) {
            const q = { x: prev.x + ((p.x - prev.x) * s) / steps, y: prev.y + ((p.y - prev.y) * s) / steps };
            if (!onMap(q)) continue;
            const [c, r] = tileOf(q);
            expect(isWalkable(c, r), `${name}: wall at ${c},${r}`).toBe(true);
          }
          prev = p;
        }
      }
    }
  });

  it("returns fresh arrays (callers may mutate them)", () => {
    const a = route(L.entrance, L.beds.A1);
    a[0].x = -999;
    expect(route(L.entrance, L.beds.A1)[0].x).not.toBe(-999);
  });

  it("is fast enough to call every frame once cached", () => {
    const t0 = performance.now();
    for (let i = 0; i < 2000; i++) route(L.waitingSlot(i % 40), L.beds[`A${(i % 8) + 1}`]);
    expect(performance.now() - t0).toBeLessThan(500);
  });
});
