// Top-down map of the department: tiles and the pixel positions every entity moves between.
//
// Plan (37 x 23 tiles, 16 px each). Outside: ambulance bay + sidewalk on the left, street at the bottom.
// Rooms are kept tight around their beds and seats: the canvas scales the whole map to the screen, so a
// smaller map shows every person and object bigger.
//
//   +---------+----+----------------+
//   | RESUS 3 | CT | ACUTE 8 beds   |
//   amb door  +----+----------------+
//   |======== main corridor =======|
//   | WAITING | FAST TRACK |hall|STAFF|
//   entrance  | 6 beds     |    +-----+
//   |         |            |lobby|MRG|
//   +---------+------------+-EXIT+---+
//   ~~~~~~~~~~~~~ street ~~~~~~~~~~~~~
//
// Every Point is the top-left pixel of a 16x16 entity cell (same convention as Frame entities).

import type { Zone } from "../replay/types";
import type { Point } from "../replay/frame";

export const TILE = 16;
export const MAP_COLS = 37;
export const MAP_ROWS = 23;

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
  entrance: Point; // where walk-in patients appear
  // Top-left of a parked ambulance (32x48 sprite) in the bay: index 0 when one ambulance comes, both
  // when two do. They drive in from above the map, so the bay must touch the top edge.
  ambulanceParks: [Point, Point, Point];
  exit: Point; // where discharged / left patients walk to
  morgue: Point; // where dead patients fade out
  waitingSlot(i: number): Point; // i-th waiting spot (0-based), must work for any i
  waitingSeats: number; // spots 0..waitingSeats-1 are chairs; the rest are standing room
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
  resus: { c0: 5, r0: 1, c1: 13, r1: 6 },
  ct: { c0: 15, r0: 1, c1: 18, r1: 6 },
  acute: { c0: 20, r0: 1, c1: 35, r1: 6 },
  corridor: { c0: 5, r0: 8, c1: 35, r1: 9 },
  waiting: { c0: 5, r0: 11, c1: 14, r1: 18 },
  fast_track: { c0: 16, r0: 11, c1: 25, r1: 18 },
  hall: { c0: 27, r0: 10, c1: 28, r1: 16 },
  lobby: { c0: 27, r0: 17, c1: 31, r1: 18 },
  rest: { c0: 30, r0: 11, c1: 35, r1: 15 },
  morgue: { c0: 33, r0: 17, c1: 35, r1: 18 },
};

// Outer shell of the building (walls included); everything outside it is open air (sidewalk, bay, street).
export const BUILDING: Rect = { c0: 4, r0: 0, c1: 36, r1: 19 };
export const AMBULANCE_BAY: Rect = { c0: 0, r0: 0, c1: 3, r1: 7 };
export const AMBULANCE_DOOR_ROW = 4; // upper of the two ambulance doors into Resus
export const ENTRANCE_ROW = 14; // upper of the two main entrance doors into Waiting
export const EXIT_COL = 28; // left of the two exit doors onto the street
export const STREET_ROW = 20; // first row of the street (sidewalk), rows below are road

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
  [4, AMBULANCE_DOOR_ROW], [4, AMBULANCE_DOOR_ROW + 1], // ambulance doors into Resus
  [4, ENTRANCE_ROW], [4, ENTRANCE_ROW + 1], // main entrance into Waiting
  [7, 7], [8, 7], // Resus
  [17, 7], // CT
  [28, 7], [29, 7], // Acute
  [10, 10], [11, 10], // Waiting -> corridor
  [24, 10], [25, 10], // Fast-track -> corridor
  [15, 14], // Waiting -> Fast-track
  [29, 12], [29, 13], // Staff room -> hall
  [32, 18], // Morgue
  [EXIT_COL, 19], [EXIT_COL + 1, 19], // Exit to the street
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
  // Waiting room: 3 rows of 7 seats (aisle at cols 10-11 under the corridor door), triage desk.
  for (const r of SEAT_ROWS) for (const c of SEAT_COLS) add("chair", c, r, c, r, true);
  add("desk", 12, 11, 14, 11);
  add("plant", 5, 18);
  add("vending", 13, 18, 14, 18);
  add("bench", 6, 18, 9, 18, false);
  add("wheelchair", 5, 11);
  // Resus: monitor at each bed head, crash cart in the corner, sink by the door.
  for (const c of RESUS_BED_COLS) add("monitor", c - 1, 2);
  add("cart", 5, 6);
  add("sink", 13, 6);
  // Acute: folded curtains between bays, sink.
  for (const c of ACUTE_BED_COLS) add("curtain", c - 1, 1, c - 1, 1, false);
  add("sink", 35, 6);
  add("plant", 20, 6);
  // CT: operator console.
  add("console", 15, 6, 16, 6);
  // Fast-track: plants.
  add("plant", 16, 18);
  add("plant", 25, 18);
  // Staff room: sofa (also rest slots), coffee, lockers, table.
  add("sofa", 30, 11, 33, 11, false);
  add("coffee", 34, 11, 35, 11);
  add("locker", 35, 13, 35, 15);
  add("table", 31, 13, 33, 13, false);
  // Morgue drawers.
  add("cabinet", 35, 17, 35, 18);
  // Corridor plants, spare wheelchairs.
  add("plant", 5, 8);
  add("plant", 35, 8);
  add("wheelchair", 33, 8);
  add("wheelchair", 31, 17);
  // Outside.
  add("lamp", 0, 9, 0, 9);
  add("lamp", 9, STREET_ROW, 9, STREET_ROW);
  add("lamp", 21, STREET_ROW, 21, STREET_ROW);
  add("lamp", 33, STREET_ROW, 33, STREET_ROW);
  return out;
}

const SEAT_ROWS = [13, 15, 17];
const SEAT_COLS = [6, 7, 8, 9, 12, 13, 14];
const STAND_ROWS = [14, 16];
const RESUS_BED_COLS = [6, 9, 12];
const ACUTE_BED_COLS = [21, 23, 25, 27, 29, 31, 33, 35];
const FAST_BED_COLS = [17, 20, 23];
const FAST_BED_ROWS = [11, 15];

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
    at(7, 4, 54), at(11, 4, 54), // Resus
    at(16, 4, 46), // CT
    at(23, 4, 54), at(28, 4, 54), at(33, 4, 54), // Acute
    ...[9, 16, 23, 30].map((c) => at(c, 8, 46)), // corridor
    at(8, 14, 60, "warm"), at(12, 16, 56, "warm"), // Waiting
    at(19, 14, 56), at(23, 14, 56), // Fast-track
    at(32, 13, 52, "warm"), // staff room
    at(27, 13, 32), at(29, 17, 36), // hall, lobby
    at(34, 17, 30, "cold"), // morgue
    // Outside: street lamps, the entrance canopy and the ambulance bay flood light.
    at(0, 9, 54, "warm", true), at(9, STREET_ROW, 58, "warm", true), at(21, STREET_ROW, 58, "warm", true),
    at(33, STREET_ROW, 58, "warm", true), at(2, ENTRANCE_ROW, 50, "warm", true), at(2, 4, 56, "cool", true),
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
  RESUS_BED_COLS.forEach((c, i) => put(`R${i + 1}`, "resus", c, 2));
  ACUTE_BED_COLS.forEach((c, i) => put(`A${i + 1}`, "acute", c, 2));
  FAST_BED_COLS.forEach((c, i) => {
    put(`F${i + 1}`, "fast_track", c, FAST_BED_ROWS[0]);
    put(`F${i + 4}`, "fast_track", c, FAST_BED_ROWS[1]);
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

// Chairs first (the model spreads patients over them), then standing room in the aisles.
const SEAT_SPOTS: [number, number][] = SEAT_ROWS.flatMap((r) => SEAT_COLS.map((c): [number, number] => [c, r]));

export const WAITING_SPOTS: [number, number][] = [
  ...SEAT_SPOTS,
  ...STAND_ROWS.flatMap((r) => SEAT_COLS.map((c): [number, number] => [c, r])),
  ...rowSpots(12, 6, 11),
  ...[13, 14, 15, 16, 17].map((r): [number, number] => [5, r]),
];

export const REST_SPOTS: [number, number][] = [
  ...rowSpots(11, 30, 33),
  ...rowSpots(12, 30, 35),
  ...rowSpots(14, 30, 34),
  ...rowSpots(15, 30, 34),
  [30, 13], [34, 13],
];

// First spots stand right beside each bed (doctors come first in obs.staff), then rows in the aisle.
export const STAFF_SPOTS: Record<Zone, [number, number][]> = {
  resus: [
    [7, 3], [10, 3], [13, 3], [5, 4], [8, 4], [11, 4],
    ...rowSpots(5, 5, 13),
    ...rowSpots(6, 6, 12),
  ],
  acute: [
    [22, 3], [26, 3], [30, 3], [34, 3], [24, 3], [28, 3], [32, 3], [20, 3],
    ...rowSpots(5, 20, 35),
    ...rowSpots(6, 21, 34),
  ],
  fast_track: [
    [18, 12], [21, 12], [24, 12], [18, 16], [21, 16], [24, 16],
    [16, 12], [19, 12], [22, 12], [16, 16], [19, 16], [22, 16],
    ...rowSpots(14, 16, 25),
    ...rowSpots(18, 17, 24),
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
    ct: { x: 16 * TILE, y: 2 * TILE },
    entrance: { x: 2 * TILE, y: ENTRANCE_ROW * TILE + 8 },
    // [one ambulance: centred, two ambulances: left, right]
    ambulanceParks: [
      { x: TILE, y: TILE },
      { x: 0, y: TILE },
      { x: 2 * TILE, y: TILE },
    ],
    exit: { x: EXIT_COL * TILE + 8, y: STREET_ROW * TILE },
    morgue: T(33, 17),
    waitingSlot: slotFn(WAITING_SPOTS),
    waitingSeats: SEAT_SPOTS.length,
    restSlot: slotFn(REST_SPOTS),
    staffSlot: (zone, i) => staffFns[zone](i),
    // Just past the right edge of the street: staff walk out of the exit and off the map.
    offstage: { x: MAP_COLS * TILE + 8, y: (STREET_ROW + 1) * TILE },
    labels: [
      // Zone signs hang on the corridor-facing wall, next to each door.
      { text: "RESUS", at: { x: 10 * TILE + 8, y: 7 * TILE + 8 } },
      { text: "CT", at: { x: 16 * TILE, y: 7 * TILE + 8 } },
      { text: "ACUTE", at: { x: 22 * TILE, y: 7 * TILE + 8 } },
      { text: "WAITING", at: { x: 7 * TILE + 8, y: 10 * TILE + 8 } },
      { text: "FAST TRACK", at: { x: 18 * TILE + 8, y: 10 * TILE + 8 } },
      { text: "STAFF ROOM", at: { x: 32 * TILE + 8, y: 10 * TILE + 8 } },
      { text: "MORGUE", at: { x: 34 * TILE, y: 16 * TILE + 8 } },
      { text: "EXIT", at: { x: 31 * TILE, y: 19 * TILE + 8 } },
      { text: "EMERGENCY", at: { x: 2 * TILE + 8, y: (ENTRANCE_ROW - 2) * TILE + 8 } },
      { text: "AMBULANCE", at: { x: 2 * TILE, y: 7 * TILE + 8 } },
    ],
  };
}
