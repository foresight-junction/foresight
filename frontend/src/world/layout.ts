// Top-down map of the department: tiles and the pixel positions every entity moves between.
// Owner: agent B (map + renderer). STUB: a plain grid so the app runs end to end.

import type { Zone } from "../replay/types";
import type { Point } from "../replay/frame";

export const TILE = 16;
export const MAP_COLS = 40;
export const MAP_ROWS = 24;

export type TileKind =
  | "void"
  | "wall"
  | "floor"
  | "door"
  | "waiting_floor"
  | "resus_floor"
  | "acute_floor"
  | "fast_floor"
  | "rest_floor"
  | "ct_floor";

export interface Layout {
  tiles: TileKind[][]; // [row][col], MAP_ROWS x MAP_COLS
  beds: Record<string, Point>; // bed id (R1..R3, A1..A8, F1..F6) -> top-left pixel of the bed
  bedZone: Record<string, Zone>;
  ct: Point;
  entrance: Point; // where arriving patients appear
  exit: Point; // where discharged / left patients walk to
  morgue: Point; // where dead patients fade out
  waitingSlot(i: number): Point; // i-th waiting seat (0-based), must work for any i
  restSlot(i: number): Point; // i-th spot in the rest room
  staffSlot(zone: Zone, i: number): Point; // i-th staff spot in a zone
  offstage: Point; // fainted / sick / not-yet-arrived agency staff
  labels: { text: string; at: Point }[];
}

export function buildLayout(): Layout {
  const tiles: TileKind[][] = Array.from({ length: MAP_ROWS }, () => Array<TileKind>(MAP_COLS).fill("floor"));
  const beds: Record<string, Point> = {};
  const bedZone: Record<string, Zone> = {};
  const rows: [Zone, string, number, number][] = [
    ["resus", "R", 3, 2],
    ["acute", "A", 8, 7],
    ["fast_track", "F", 6, 12],
  ];
  for (const [zone, prefix, n, row] of rows) {
    for (let i = 0; i < n; i++) {
      const id = `${prefix}${i + 1}`;
      beds[id] = { x: (14 + i * 3) * TILE, y: row * TILE };
      bedZone[id] = zone;
    }
  }
  const zoneRow: Record<Zone, number> = { resus: 4, acute: 9, fast_track: 14 };
  return {
    tiles,
    beds,
    bedZone,
    ct: { x: 36 * TILE, y: 2 * TILE },
    entrance: { x: 1 * TILE, y: 20 * TILE },
    exit: { x: 38 * TILE, y: 22 * TILE },
    morgue: { x: 38 * TILE, y: 18 * TILE },
    waitingSlot: (i) => ({ x: (1 + (i % 10)) * TILE, y: (2 + Math.floor(i / 10)) * TILE }),
    restSlot: (i) => ({ x: (1 + (i % 8)) * TILE, y: (15 + Math.floor(i / 8)) * TILE }),
    staffSlot: (zone, i) => ({ x: (14 + i * 2) * TILE, y: zoneRow[zone] * TILE }),
    offstage: { x: 20 * TILE, y: 22 * TILE },
    labels: [],
  };
}
