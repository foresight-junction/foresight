// Top-down map of the department: tiles and the pixel positions every entity moves between.
// Owner: agent B (map + renderer).
//
// Plan (48 x 28 tiles, 16 px each). Outside: ambulance bay + sidewalk on the left, street at the bottom.
//
//   +-------------+--------+----------------------+
//   | RESUS  3    |   CT   |  ACUTE  8 beds       |
//   amb door      +--------+----------------------+
//   |============ main corridor =================|
//   | WAITING     | FAST TRACK  |hall| STAFF ROOM |
//   entrance      | 6 beds      |    +------------+
//   |             |             |lobby  | MORGUE |
//   +-------------+-------------+--EXIT-+--------+
//   ~~~~~~~~~~~~~~~~~~~~~~ street ~~~~~~~~~~~~~~~~~
//
// Every Point is the top-left pixel of a 16x16 entity cell (same convention as Frame entities).

import type { Zone } from "../replay/types";
import type { Point } from "../replay/frame";

export const TILE = 16;
export const MAP_COLS = 48;
export const MAP_ROWS = 28;

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

// Inclusive tile bounds of a rectangle.
export interface Rect {
  c0: number;
  r0: number;
  c1: number;
  r1: number;
}

export type RoomId =
  | "resus"
  | "ct"
  | "acute"
  | "corridor"
  | "waiting"
  | "fast_track"
  | "hall"
  | "lobby"
  | "rest"
  | "morgue";

// Interior floor of every room (walls excluded). The renderer uses these for tints and overlays.
export const ROOMS: Record<RoomId, Rect> = {
  resus: { c0: 6, r0: 1, c1: 17, r1: 8 },
  ct: { c0: 19, r0: 1, c1: 25, r1: 8 },
  acute: { c0: 27, r0: 1, c1: 46, r1: 8 },
  corridor: { c0: 6, r0: 10, c1: 46, r1: 11 },
  waiting: { c0: 6, r0: 13, c1: 18, r1: 23 },
  fast_track: { c0: 20, r0: 13, c1: 32, r1: 23 },
  hall: { c0: 34, r0: 12, c1: 35, r1: 20 },
  lobby: { c0: 34, r0: 21, c1: 40, r1: 23 },
  rest: { c0: 37, r0: 13, c1: 46, r1: 19 },
  morgue: { c0: 42, r0: 21, c1: 46, r1: 23 },
};

// Outer shell of the building (walls included); everything outside it is open air (sidewalk, bay, street).
export const BUILDING: Rect = { c0: 5, r0: 0, c1: 47, r1: 24 };
export const AMBULANCE_BAY: Rect = { c0: 0, r0: 0, c1: 4, r1: 10 };
export const STREET_ROW = 25; // first row of the street (sidewalk), rows below are road

const ROOM_FLOOR: Record<RoomId, TileKind> = {
  resus: "resus_floor",
  ct: "ct_floor",
  acute: "acute_floor",
  corridor: "floor",
  waiting: "waiting_floor",
  fast_track: "fast_floor",
  hall: "floor",
  lobby: "floor",
  rest: "rest_floor",
  morgue: "floor",
};

const DOORS: [number, number][] = [
  [5, 5], [5, 6], // ambulance doors into Resus
  [5, 18], [5, 19], // main entrance into Waiting
  [11, 9], [12, 9], // Resus
  [22, 9], // CT
  [36, 9], [37, 9], // Acute
  [13, 12], [14, 12], // Waiting -> corridor
  [30, 12], [31, 12], // Fast-track -> corridor
  [19, 17], // Waiting -> Fast-track
  [36, 15], [36, 16], // Staff room -> hall
  [41, 22], // Morgue
  [37, 24], [38, 24], // Exit to the street
];

// Furniture is drawn by the renderer; `blocks` furniture is avoided by route() unless it is the goal.
export type FurnitureKind =
  | "chair" // waiting seat
  | "desk" // triage counter
  | "plant"
  | "vending"
  | "monitor" // bedside monitor
  | "cart" // crash cart
  | "curtain" // folded bay curtain
  | "console" // CT operator desk
  | "sofa"
  | "coffee"
  | "locker"
  | "table"
  | "cabinet" // morgue drawers
  | "sink"
  | "bench"
  | "ambulance"
  | "wheelchair"
  | "lamp"; // street lamp

export interface Furniture extends Rect {
  kind: FurnitureKind;
  blocks: boolean;
}

function T(c: number, r: number): Point {
  return { x: c * TILE, y: r * TILE };
}

function furniture(): Furniture[] {
  const out: Furniture[] = [];
  const add = (kind: FurnitureKind, c0: number, r0: number, c1 = c0, r1 = r0, blocks = true): void => {
    out.push({ kind, c0, r0, c1, r1, blocks });
  };
  // Waiting room: 4 rows of 10 seats (aisle at col 13 lines up with the corridor door), triage desk.
  for (const r of SEAT_ROWS) for (const c of SEAT_COLS) add("chair", c, r, c, r, true);
  add("desk", 15, 13, 18, 13);
  add("plant", 6, 23);
  add("vending", 17, 23, 18, 23);
  add("bench", 8, 23, 11, 23, false);
  // Resus: monitor at each bed head, crash cart in the corner, sink by the door.
  for (const c of [8, 12, 16]) add("monitor", c - 1, 2);
  add("cart", 6, 7);
  add("sink", 17, 7);
  // Acute: folded curtains between bays, sink.
  for (let i = 0; i < 8; i++) add("curtain", 29 + 2 * i - 1, 1, 29 + 2 * i - 1, 1, false);
  add("sink", 46, 7);
  add("plant", 27, 7);
  // CT: operator console.
  add("console", 19, 7, 20, 7);
  // Fast-track: plants.
  add("plant", 20, 23);
  add("plant", 32, 23);
  // Staff room: sofa (also rest slots), coffee, lockers, table.
  add("sofa", 38, 13, 44, 13, false);
  add("coffee", 45, 13, 46, 13);
  add("locker", 46, 15, 46, 19);
  add("table", 40, 16, 43, 16, false);
  // Morgue drawers.
  add("cabinet", 46, 21, 46, 23);
  // Corridor plants, spare wheelchairs.
  add("plant", 6, 10);
  add("plant", 46, 10);
  add("wheelchair", 44, 10);
  add("wheelchair", 17, 14);
  add("wheelchair", 39, 22);
  // Outside.
  add("ambulance", 1, 1, 2, 3);
  add("lamp", 0, 12, 0, 12);
  add("lamp", 12, STREET_ROW, 12, STREET_ROW);
  add("lamp", 28, STREET_ROW, 28, STREET_ROW);
  add("lamp", 44, STREET_ROW, 44, STREET_ROW);
  return out;
}

const SEAT_ROWS = [15, 17, 19, 21];
const SEAT_COLS = [8, 9, 10, 11, 12, 14, 15, 16, 17, 18];
const STAND_ROWS = [16, 18, 20, 22];

export const FURNITURE: Furniture[] = furniture();

// Ceiling lamps and street lamps (centre pixel, light radius in px). The renderer cuts light pools
// out of the ambient darkness here; "cold" is the morgue's blue strip light.
export interface Light {
  x: number;
  y: number;
  r: number;
  tone: "warm" | "cool" | "cold";
  outdoor: boolean;
}

function lights(): Light[] {
  const at = (c: number, r: number, radius: number, tone: Light["tone"] = "cool", outdoor = false): Light => ({
    x: c * TILE + 8,
    y: r * TILE + 8,
    r: radius,
    tone,
    outdoor,
  });
  return [
    at(9, 4, 60), at(15, 4, 60), // Resus
    at(22, 5, 52), // CT
    at(31, 4, 56), at(37, 4, 56), at(43, 4, 56), // Acute
    ...[9, 17, 25, 33, 41].map((c) => at(c, 10, 46)), // corridor
    at(10, 17, 64, "warm"), at(15, 20, 60, "warm"), // Waiting
    at(24, 17, 58), at(29, 17, 58), // Fast-track
    at(41, 16, 60, "warm"), // staff room
    at(35, 16, 34), at(37, 22, 40), // hall, lobby
    at(44, 22, 34, "cold"), // morgue
    // Outside: street lamps, the entrance canopy and the ambulance bay flood light.
    at(0, 12, 54, "warm", true), at(12, 25, 58, "warm", true), at(28, 25, 58, "warm", true),
    at(44, 25, 58, "warm", true), at(3, 18, 50, "warm", true), at(2, 5, 56, "cool", true),
  ];
}

export const LIGHTS: Light[] = lights();

export const ZONE_LABEL: Record<Zone, string> = { resus: "RESUS", acute: "ACUTE", fast_track: "FAST TRACK" };

// Beds per doctor / per nurse (SPEC §3): the renderer derives each zone's coverable beds from these.
export const BEDS_PER_DOCTOR: Record<Zone, number> = { resus: 1, acute: 3, fast_track: 4 };
export const BEDS_PER_NURSE: Record<Zone, number> = { resus: 1, acute: 2, fast_track: 3 };

function bedLayout(): { beds: Record<string, Point>; bedZone: Record<string, Zone> } {
  const beds: Record<string, Point> = {};
  const bedZone: Record<string, Zone> = {};
  const put = (id: string, zone: Zone, c: number, r: number): void => {
    beds[id] = T(c, r);
    bedZone[id] = zone;
  };
  [8, 12, 16].forEach((c, i) => put(`R${i + 1}`, "resus", c, 2));
  for (let i = 0; i < 8; i++) put(`A${i + 1}`, "acute", 29 + 2 * i, 2);
  [22, 26, 30].forEach((c, i) => {
    put(`F${i + 1}`, "fast_track", c, 14);
    put(`F${i + 4}`, "fast_track", c, 19);
  });
  return { beds, bedZone };
}

function rowSpots(r: number, c0: number, c1: number): [number, number][] {
  const out: [number, number][] = [];
  for (let c = c0; c <= c1; c++) out.push([c, r]);
  return out;
}

// Spots past the hand-placed list reuse it with a small pixel nudge per lap, so every i stays distinct
// and stays on the same walkable tile.
function slotFn(spots: [number, number][]): (i: number) => Point {
  const pts = spots.map(([c, r]) => T(c, r));
  return (i) => {
    const n = Math.max(0, Math.floor(i));
    const base = pts[n % pts.length];
    const lap = Math.floor(n / pts.length);
    if (lap === 0) return { ...base };
    // dx is never 0 and (dx, dy) repeats only every 21 laps, so overflow spots never land on lap 0.
    const dx = ((lap * 3) % 9) - 4;
    const dy = ((lap * 5) % 7) - 3;
    return { x: base.x + dx, y: base.y + dy };
  };
}

export const WAITING_SPOTS: [number, number][] = [
  ...SEAT_ROWS.flatMap((r) => SEAT_COLS.map((c): [number, number] => [c, r])),
  ...STAND_ROWS.flatMap((r) => SEAT_COLS.map((c): [number, number] => [c, r])),
  ...rowSpots(14, 6, 13),
  ...[15, 16, 17, 20, 21, 22, 23].map((r): [number, number] => [7, r]),
];

export const REST_SPOTS: [number, number][] = [
  ...rowSpots(13, 38, 44),
  ...rowSpots(15, 38, 45),
  ...rowSpots(17, 38, 45),
  ...rowSpots(19, 38, 45),
  ...rowSpots(14, 38, 45),
  ...rowSpots(18, 38, 45),
];

// First spots stand right beside each bed (doctors come first in obs.staff), then rows in the aisle.
export const STAFF_SPOTS: Record<Zone, [number, number][]> = {
  resus: [
    [9, 3], [13, 3], [17, 3], [7, 4], [11, 3], [15, 3],
    ...rowSpots(5, 7, 17),
    ...rowSpots(6, 7, 17),
    ...rowSpots(7, 7, 16),
  ],
  acute: [
    [30, 3], [34, 3], [38, 3], [42, 3], [32, 3], [36, 3], [40, 3], [44, 3], [28, 3],
    ...rowSpots(5, 28, 45),
    ...rowSpots(6, 28, 45),
  ],
  fast_track: [
    [23, 15], [27, 15], [31, 15], [23, 20], [27, 20], [31, 20],
    [21, 15], [25, 15], [29, 15], [21, 20], [25, 20], [29, 20],
    ...rowSpots(17, 21, 32),
    ...rowSpots(22, 21, 31),
  ],
};

let tilesCache: TileKind[][] | null = null;

export function buildTiles(): TileKind[][] {
  if (tilesCache) return tilesCache.map((row) => row.slice());
  const tiles: TileKind[][] = Array.from({ length: MAP_ROWS }, () => Array<TileKind>(MAP_COLS).fill("void"));
  const fill = (r: Rect, kind: TileKind): void => {
    for (let row = r.r0; row <= r.r1; row++) for (let c = r.c0; c <= r.c1; c++) tiles[row][c] = kind;
  };
  fill(BUILDING, "wall");
  for (const id of Object.keys(ROOMS) as RoomId[]) fill(ROOMS[id], ROOM_FLOOR[id]);
  for (const [c, r] of DOORS) tiles[r][c] = "door";
  tilesCache = tiles;
  return tiles.map((row) => row.slice());
}

export function buildLayout(): Layout {
  const { beds, bedZone } = bedLayout();
  const staffFns: Record<Zone, (i: number) => Point> = {
    resus: slotFn(STAFF_SPOTS.resus),
    acute: slotFn(STAFF_SPOTS.acute),
    fast_track: slotFn(STAFF_SPOTS.fast_track),
  };
  return {
    tiles: buildTiles(),
    beds,
    bedZone,
    ct: { x: 21 * TILE + 8, y: 3 * TILE },
    entrance: { x: 2 * TILE, y: 18 * TILE + 8 },
    exit: { x: 37 * TILE + 8, y: STREET_ROW * TILE },
    morgue: T(44, 22),
    waitingSlot: slotFn(WAITING_SPOTS),
    restSlot: slotFn(REST_SPOTS),
    staffSlot: (zone, i) => staffFns[zone](i),
    // Just past the right edge of the street: staff walk out of the exit and off the map.
    offstage: { x: MAP_COLS * TILE + 8, y: (STREET_ROW + 1) * TILE },
    labels: [
      // Zone signs hang on the corridor-facing wall, next to each door.
      { text: "RESUS", at: { x: 7 * TILE + 8, y: 9 * TILE + 8 } },
      { text: "CT", at: { x: 24 * TILE + 8, y: 9 * TILE + 8 } },
      { text: "ACUTE", at: { x: 31 * TILE, y: 9 * TILE + 8 } },
      { text: "WAITING", at: { x: 9 * TILE + 8, y: 12 * TILE + 8 } },
      { text: "FAST TRACK", at: { x: 22 * TILE + 8, y: 12 * TILE + 8 } },
      { text: "STAFF ROOM", at: { x: 41 * TILE + 8, y: 12 * TILE + 8 } },
      { text: "MORGUE", at: { x: 44 * TILE + 8, y: 20 * TILE + 8 } },
      { text: "EXIT", at: { x: 40 * TILE + 8, y: 24 * TILE + 8 } },
      { text: "EMERGENCY", at: { x: 2 * TILE + 8, y: 16 * TILE + 8 } },
      { text: "AMBULANCE", at: { x: 2 * TILE + 8, y: 9 * TILE + 8 } },
    ],
  };
}
