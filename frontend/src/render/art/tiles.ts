// 16x16 floor, wall, door and void tiles. Each zone gets its own floor so areas read at a glance;
// a few variants per kind (picked by a position hash) break up the grid without animation cost.

import type { TileKind } from "../../world/layout";
import { PAGE_BG, shade } from "../palette";
import { blit, hash, proceduralSprite, type Sprite } from "./pixmap";

const T = 16;
const VARIANTS = 4;

type Paint = (x: number, y: number, v: number) => string | null;

// Deterministic speckle: true for roughly 1 in `every` pixels of variant v.
function speck(x: number, y: number, v: number, every: number): boolean {
  return hash(x, y, v) % every === 0;
}

function tiledFloor(base: string, alt: string, grout: string, fleck: string, cell: number): Paint {
  return (x, y, v) => {
    if (x % cell === cell - 1 || y % cell === cell - 1) return grout;
    const checker = (Math.floor(x / cell) + Math.floor(y / cell)) % 2 === 1;
    if (speck(x, y, v, 23)) return fleck;
    const c = checker ? alt : base;
    return x % cell === 0 || y % cell === 0 ? shade(c, 0.35) : c;
  };
}

const PAINTERS: Record<TileKind, Paint> = {
  void: (x, y, v) => (speck(x, y, v, 61) ? "#1e1e2a" : PAGE_BG),

  // Corridor: warm beige linoleum, big slabs with a light top-left edge.
  floor: (x, y, v) => {
    if (x === T - 1 || y === T - 1) return "#d4c2a2";
    if (x === 0 || y === 0) return "#f2e8d4";
    if (speck(x, y, v, 19)) return "#e0d0b2";
    return "#eadcc2";
  },

  // Waiting room: honey wood planks, 4 px tall, joints offset per plank.
  waiting_floor: (x, y, v) => {
    const plank = Math.floor(y / 4);
    if (y % 4 === 3) return "#b88c5e";
    const joint = (plank * 7 + v * 5) % T;
    if (x === joint) return "#b88c5e";
    const tone = (plank + v) % 2 === 0 ? "#dcb88c" : "#d2ac80";
    if (speck(x, y, v, 17)) return "#c89c70";
    return y % 4 === 0 ? (plank % 2 ? "#e4c49c" : "#e6c8a0") : tone;
  },

  // Resus: soft rose tiles.
  resus_floor: tiledFloor("#f2d6d2", "#ecccc8", "#d8b2ae", "#e4c0bc", 8),
  // Acute: mint tiles.
  acute_floor: tiledFloor("#d6ecdf", "#c8e4d6", "#acd0bf", "#bcdacb", 8),
  // Fast-track: pale sky tiles.
  fast_floor: tiledFloor("#d8e6f2", "#cddeee", "#b2c8de", "#c2d4e6", 8),

  // Staff rest room: cozy lavender carpet with a small diamond weave.
  rest_floor: (x, y, v) => {
    const d = (x + y) % 4 === 0 && (x - y + 32) % 4 === 0;
    if (d) return "#a894bc";
    if (speck(x, y, v, 9)) return "#b8a6ca";
    return "#c2b2d2";
  },

  // CT room: cool grey tiles with a fine grid.
  ct_floor: (x, y, v) => {
    if (x % 8 === 7 || y % 8 === 7) return "#b4bcc8";
    if (speck(x, y, v, 29)) return "#c8ced8";
    return (x % 8 === 0 || y % 8 === 0) ? "#dde2ea" : "#d2d8e2";
  },

  // Wall top cap (3/4 view): dark slate blocks with a lit lip where the face begins.
  wall: (x, y, v) => {
    if (y === 0) return "#2a2638";
    if (y === T - 1) return "#7a7294";
    if (y === T - 2) return "#5a5274";
    if (x === 0 || y === 7) return "#3a3550";
    if (y > 7 ? x === 8 : x === T - 1) return "#3a3550";
    if (speck(x, y, v, 13)) return "#524c6a";
    return y === 1 || y === 8 ? "#544e6c" : "#48425e";
  },

  // Door: open sliding glass doors over a doormat, posts on each side.
  door: (x, y) => {
    if (x <= 1 || x >= T - 2) return y <= 2 ? "#2e2a3c" : x === 0 || x === T - 1 ? "#48425e" : "#6a6282";
    if (y <= 1) return x < 5 || x > 10 ? "#a8dcec" : "#eadcc2"; // glass panels slid open
    if (y === 2) return x < 5 || x > 10 ? "#6cb4c8" : "#d4c2a2";
    if (y >= 5 && y <= 13 && x >= 3 && x <= 12) {
      if (y === 5 || y === 13 || x === 3 || x === 12) return "#5e4a3e";
      return y % 2 === 0 ? "#7a6250" : "#86705c";
    }
    return y === T - 1 ? "#d4c2a2" : "#eadcc2";
  },
};

const NO_WEAR: TileKind[] = ["void", "wall", "door"];

// Variant 3 of each floor gets a faint scuff so a room is not a perfect grid.
function worn(x: number, y: number): boolean {
  const d = Math.hypot(x - 9.5, (y - 6.5) * 1.6);
  return d > 2 && d < 4.5 && hash("wear", x, y) % 3 !== 0;
}

export function tileSprite(kind: TileKind, variant = 0): Sprite {
  const paint = PAINTERS[kind] ?? PAINTERS.floor;
  const v = variant % VARIANTS;
  const wear = v === 3 && !NO_WEAR.includes(kind);
  return proceduralSprite(`tile|${kind}|${v}`, T, T, (x, y) => {
    const c = paint(x, y, v);
    return c && wear && worn(x, y) ? shade(c, -0.05) : c;
  });
}

// Front face of a wall in 3/4 view, drawn below a wall cap: cream plaster, a wooden handrail, teal
// wainscot and a baseboard, all anchored to the bottom so any height (16 or 32) looks right.
function wallFacePaint(h: number) {
  return (x: number, y: number): string | null => {
    const b = h - 1 - y; // rows above the floor line
    if (y === 0) return "#6a6282"; // shadow under the cap lip
    if (b === 0) return "#6a6052";
    if (b <= 2) return b === 2 ? "#b8ae9a" : "#988e7c";
    if (b === 3) return "#2f8f86";
    if (b <= 7) return b === 7 ? "#8ad8cc" : x % 4 === 3 ? "#4aaca0" : "#5cbcb0";
    if (b === 8) return "#2f8f86";
    if (y === 1) return "#cfc4b2";
    if (b === 11) return "#d8a46a"; // handrail
    if (b === 10) return x % 8 === 4 ? "#6a4a2e" : "#a8743e";
    if (b === 9) return x % 8 === 4 ? "#8a8070" : "#d8cebc";
    if (hash("face", x, y) % 37 === 0) return "#e4dac8";
    return y === 2 ? "#f6eee0" : "#ece2d0";
  };
}

export function drawWallFaceAt(ctx: CanvasRenderingContext2D, x: number, y: number, height = 32): void {
  blit(ctx, proceduralSprite(`wallface|${height}`, T, height, wallFacePaint(height)), x, y);
}

export function drawTileAt(ctx: CanvasRenderingContext2D, kind: TileKind, x: number, y: number): void {
  const variant = kind === "wall" || kind === "door" ? 0 : hash(Math.round(x), Math.round(y)) % VARIANTS;
  blit(ctx, tileSprite(kind, variant), x, y);
}

export const TILE_KINDS: TileKind[] = [
  "void",
  "wall",
  "floor",
  "door",
  "waiting_floor",
  "resus_floor",
  "acute_floor",
  "fast_floor",
  "rest_floor",
  "ct_floor",
];
