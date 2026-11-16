// Draws one Frame onto the canvas. Layers: a cached static map (floors, outdoor art, furniture, 3/4
// walls, signs) -> wall monitors, beds, CT -> shadows and y-sorted people -> lighting (ambient dark
// with light pools, alarm glows) -> particles, effects -> live overlays (zone coverage, CT down,
// diversion) -> vignette and flash. Screen shake offsets the whole map.
// Sprites come from sprites.ts. The renderer draws furniture, outdoor art and signs.

import type { EffectKind, Frame, PatientEntity, StaffEntity, VehicleEntity } from "../replay/frame";
import type { Zone } from "../replay/types";
import {
  AMBULANCE_BAY,
  AMBULANCE_DOOR_ROW,
  BEDS_PER_DOCTOR,
  BEDS_PER_NURSE,
  BUILDING,
  ENTRANCE_ROW,
  EXIT_COL,
  FURNITURE,
  type Furniture,
  type Light,
  LIGHTS,
  MAP_COLS,
  MAP_ROWS,
  ROOMS,
  type Rect,
  STREET_ROW,
  TILE,
  ZONE_LABEL,
  type Layout,
} from "../world/layout";
import { newCanvas } from "./art/pixmap";
import { darkness, fitZoom, hourOfDay } from "./camera";
import { type Burst, Particles } from "./particles";
import { drawBed, drawCt, drawEffect, drawPatient, drawStaff, drawTile, drawWallFace } from "./sprites";

const MAP_W = MAP_COLS * TILE;
const MAP_H = MAP_ROWS * TILE;
const ZONES: Zone[] = ["resus", "acute", "fast_track"];

const COL = {
  navy: "#23283a",
  navyEdge: "#3c4460",
  ink: "#2b2f45",
  text: "#eef0f6",
  muted: "#6a7088",
  teal: "#3aa7a3",
  tealDark: "#2c7f7c",
  mint: "#9ad8c8",
  mintDark: "#76bfae",
  red: "#e05a5a",
  redDark: "#b23a3a",
  orange: "#f08c3a",
  amber: "#f2c14e",
  green: "#5cc878",
  greenDark: "#2f8f5b",
  wood: "#c49a6c",
  woodDark: "#8e6a45",
  steel: "#b8c2cc",
  steelDark: "#7d8794",
  white: "#f4f2ec",
  screen: "#12333a",
  glass: "#8fc4dc",
  asphalt: "#4a4e5c",
  asphaltDark: "#3e424e",
  sidewalk: "#cfc7b8",
  sidewalkSeam: "#b9b1a2",
  grass: "#6aa85e",
  grassDark: "#568f4c",
};

const ZONE_COLOR: Record<Zone, string> = { resus: COL.red, acute: COL.teal, fast_track: COL.green };

// 3x5 pixel font: crisp at any integer zoom, unlike canvas text.

// Five rows of three pixels each, top to bottom.
const GLYPH_ROWS: Record<string, string> = {
  A: ".#. #.# ### #.# #.#", B: "##. #.# ##. #.# ##.", C: ".## #.. #.. #.. .##", D: "##. #.# #.# #.# ##.",
  E: "### #.. ##. #.. ###", F: "### #.. ##. #.. #..", G: ".## #.. #.# #.# .##", H: "#.# #.# ### #.# #.#",
  I: "### .#. .#. .#. ###", J: "..# ..# ..# #.# .#.", K: "#.# #.# ##. #.# #.#", L: "#.. #.. #.. #.. ###",
  M: "#.# ### ### #.# #.#", N: "##. #.# #.# #.# #.#", O: ".#. #.# #.# #.# .#.", P: "##. #.# ##. #.. #..",
  Q: ".#. #.# #.# ##. .##", R: "##. #.# ##. #.# #.#", S: ".## #.. .#. ..# ##.", T: "### .#. .#. .#. .#.",
  U: "#.# #.# #.# #.# ###", V: "#.# #.# #.# #.# .#.", W: "#.# #.# ### ### #.#", X: "#.# #.# .#. #.# #.#",
  Y: "#.# #.# .#. .#. .#.", Z: "### ..# .#. #.. ###",
  "0": "### #.# #.# #.# ###", "1": ".#. ##. .#. .#. ###", "2": "##. ..# .#. #.. ###", "3": "##. ..# .#. ..# ##.",
  "4": "#.# #.# ### ..# ..#", "5": "### #.. ##. ..# ##.", "6": ".## #.. ### #.# ###", "7": "### ..# .#. .#. .#.",
  "8": "### #.# ### #.# ###", "9": "### #.# ### ..# ##.",
  " ": "... ... ... ... ...", ".": "... ... ... ... .#.", "-": "... ... ### ... ...", ":": "... .#. ... .#. ...",
  "/": "..# ..# .#. #.. #..", "!": ".#. .#. .#. ... .#.", "+": "... .#. ### .#. ...", "%": "#.# ..# .#. #.. #.#",
};
const GLYPHS: Record<string, string> = Object.fromEntries(
  Object.entries(GLYPH_ROWS).map(([k, v]) => [k, v.replace(/ /g, "")]),
);

function textWidth(s: string): number {
  return Math.max(0, s.length * 4 - 1);
}

function drawText(ctx: CanvasRenderingContext2D, s: string, x: number, y: number, color: string): void {
  ctx.fillStyle = color;
  const up = s.toUpperCase();
  for (let i = 0; i < up.length; i++) {
    const g = GLYPHS[up[i]] ?? GLYPHS[" "];
    for (let b = 0; b < 15; b++) if (g[b] === "#") ctx.fillRect(x + i * 4 + (b % 3), y + Math.floor(b / 3), 1, 1);
  }
}

function plaque(ctx: CanvasRenderingContext2D, text: string, cx: number, cy: number, accent: string): void {
  const w = textWidth(text) + 8;
  const x = Math.round(cx - w / 2);
  const y = Math.round(cy - 5);
  ctx.fillStyle = COL.navyEdge;
  ctx.fillRect(x - 1, y - 1, w + 2, 12);
  ctx.fillStyle = COL.navy;
  ctx.fillRect(x, y, w, 10);
  ctx.fillStyle = accent;
  ctx.fillRect(x, y, 2, 10);
  drawText(ctx, text, x + 5, y + 3, COL.text);
}

// Static art: outdoor ground, wall shadows, furniture, bed bays, signs.

function px(r: Rect): { x: number; y: number; w: number; h: number } {
  return { x: r.c0 * TILE, y: r.r0 * TILE, w: (r.c1 - r.c0 + 1) * TILE, h: (r.r1 - r.r0 + 1) * TILE };
}

function inside(r: Rect, c: number, row: number): boolean {
  return c >= r.c0 && c <= r.c1 && row >= r.r0 && row <= r.r1;
}

function drawOutdoors(ctx: CanvasRenderingContext2D, layout: Layout): void {
  for (let r = 0; r < MAP_ROWS; r++) {
    for (let c = 0; c < MAP_COLS; c++) {
      if (layout.tiles[r][c] !== "void") continue;
      const x = c * TILE;
      const y = r * TILE;
      if (r > STREET_ROW) {
        ctx.fillStyle = COL.asphalt;
        ctx.fillRect(x, y, TILE, TILE);
        ctx.fillStyle = COL.asphaltDark;
        ctx.fillRect(x + ((c * 7 + r * 3) % 13), y + ((c * 5 + r) % 11), 2, 1);
      } else if (inside(AMBULANCE_BAY, c, r)) {
        ctx.fillStyle = COL.asphalt;
        ctx.fillRect(x, y, TILE, TILE);
        ctx.fillStyle = COL.asphaltDark;
        ctx.fillRect(x + ((c * 7 + r * 3) % 13), y + ((c * 5 + r) % 11), 2, 1);
      } else if (c === 0 && r > AMBULANCE_BAY.r1 + 2 && r < STREET_ROW) {
        ctx.fillStyle = COL.grass;
        ctx.fillRect(x, y, TILE, TILE);
        ctx.fillStyle = COL.grassDark;
        ctx.fillRect(x + 3 + (r % 3) * 3, y + 4, 1, 2);
        ctx.fillRect(x + 10 - (r % 2) * 4, y + 11, 1, 2);
      } else {
        ctx.fillStyle = COL.sidewalk;
        ctx.fillRect(x, y, TILE, TILE);
        ctx.fillStyle = COL.sidewalkSeam;
        ctx.fillRect(x, y + 15, TILE, 1);
        ctx.fillRect(x + 15, y, 1, TILE);
      }
    }
  }
  // Road centre line and kerb.
  ctx.fillStyle = "#e9e3d2";
  for (let x = 4; x < MAP_W; x += 24) ctx.fillRect(x, (STREET_ROW + 2) * TILE - 1, 12, 2);
  ctx.fillStyle = "#8c867a";
  ctx.fillRect(0, (STREET_ROW + 1) * TILE - 2, MAP_W, 2);
  // Ambulance bay: yellow box and hatched no-parking lane in front of the ambulance doors.
  const bay = px(AMBULANCE_BAY);
  ctx.fillStyle = COL.amber;
  ctx.fillRect(bay.x + 4, bay.y + 4, bay.w - 8, 1);
  ctx.fillRect(bay.x + 4, bay.y + 4, 1, 60);
  ctx.fillRect(bay.x + bay.w - 5, bay.y + 4, 1, 60);
  ctx.fillRect(bay.x + 4, bay.y + 64, bay.w - 8, 1);
  for (let x = bay.x + 12; x + 4 <= bay.x + bay.w - 6; x += 10) ctx.fillRect(x, AMBULANCE_DOOR_ROW * TILE + 2, 4, 28);
  // Kerb between bay and sidewalk.
  ctx.fillStyle = "#8c867a";
  ctx.fillRect(0, (AMBULANCE_BAY.r1 + 1) * TILE - 2, (AMBULANCE_BAY.c1 + 1) * TILE, 2);
  // Doormats at the entrance and the exit.
  ctx.fillStyle = "#5a5f73";
  ctx.fillRect((BUILDING.c0 - 1) * TILE + 4, ENTRANCE_ROW * TILE + 1, 10, 30);
  ctx.fillRect(EXIT_COL * TILE + 1, STREET_ROW * TILE + 1, 30, 6);
}

function drawWallShadows(ctx: CanvasRenderingContext2D, layout: Layout): void {
  for (let r = 1; r < MAP_ROWS; r++) {
    for (let c = 0; c < MAP_COLS; c++) {
      const k = layout.tiles[r][c];
      if (k === "wall") continue;
      if (layout.tiles[r - 1][c] === "wall") {
        // Soft two-step shadow cast by the wall's front face onto the floor in front of it.
        ctx.fillStyle = "rgba(15, 12, 30, 0.30)";
        ctx.fillRect(c * TILE, r * TILE, TILE, 3);
        ctx.fillStyle = "rgba(15, 12, 30, 0.14)";
        ctx.fillRect(c * TILE, r * TILE + 3, TILE, 3);
      }
      if (inside(BUILDING, c, r) && c > 0 && layout.tiles[r][c - 1] === "wall") {
        ctx.fillStyle = "rgba(15, 12, 30, 0.16)";
        ctx.fillRect(c * TILE, r * TILE, 3, TILE);
      }
    }
  }
}

const CAP = 6; // how far a wall's top cap rises above its face, in px

// Top cap: sprites' wall tile, darkened so it reads as the dark top of a thick wall.
function wallCap(ctx: CanvasRenderingContext2D, x: number, y: number, h: number): void {
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, TILE, h);
  ctx.clip();
  drawTile(ctx, "wall", x, y);
  ctx.fillStyle = "rgba(22, 18, 40, 0.62)";
  ctx.fillRect(x, y, TILE, h);
  ctx.restore();
}

// 3/4 walls: a wall tile with floor in front of it shows its front face, with the cap rising CAP px
// into the tile behind; wall tiles inside a run show only the cap.
function drawWalls(ctx: CanvasRenderingContext2D, layout: Layout): void {
  const at = (c: number, r: number): string => layout.tiles[r]?.[c] ?? "void";
  const solid = (c: number, r: number): boolean => at(c, r) === "wall" || at(c, r) === "door";
  for (let r = 0; r < MAP_ROWS; r++) {
    for (let c = 0; c < MAP_COLS; c++) {
      const k = at(c, r);
      const x = c * TILE;
      const y = r * TILE;
      const front = at(c, r + 1) !== "wall";
      if (k === "wall") {
        if (!front) {
          wallCap(ctx, x, y, TILE);
          continue;
        }
        drawWallFace(ctx, x, y, TILE);
        if (r === 0) wallCap(ctx, x, y, 4);
        else wallCap(ctx, x, y - CAP, CAP);
        ctx.fillStyle = "#6b6390";
        ctx.fillRect(x, r === 0 ? y + 4 : y, TILE, 1);
      } else if (k === "door" && solid(c - 1, r) && solid(c + 1, r) && at(c, r - 1) !== "wall") {
        // Doorway in a horizontal wall: lintel cap above the opening plus dark jambs on the faces.
        wallCap(ctx, x, y - CAP, CAP);
        ctx.fillStyle = "#6b6390";
        ctx.fillRect(x, y, TILE, 1);
      }
    }
  }
  // Jambs: darken the face pixels right beside every horizontal doorway.
  for (let r = 0; r < MAP_ROWS; r++) {
    for (let c = 0; c < MAP_COLS; c++) {
      if (at(c, r) !== "door" || at(c - 1, r) === "door" || at(c - 1, r) !== "wall") continue;
      let e = c;
      while (at(e + 1, r) === "door") e++;
      if (at(e + 1, r) !== "wall" || at(c, r - 1) === "wall") continue;
      ctx.fillStyle = "#4e6a62";
      ctx.fillRect(c * TILE - 2, r * TILE, 2, TILE);
      ctx.fillRect((e + 1) * TILE, r * TILE, 2, TILE);
    }
  }
}

function drawBays(ctx: CanvasRenderingContext2D, layout: Layout): void {
  for (const [id, at] of Object.entries(layout.beds)) {
    const zone = layout.bedZone[id];
    const color = ZONE_COLOR[zone];
    const [bx, by, bw, bh] = zone === "resus" ? [at.x - 12, at.y - 6, 40, 42] : [at.x - 7, at.y - 4, 30, 38];
    ctx.globalAlpha = 0.12;
    ctx.fillStyle = color;
    ctx.fillRect(bx, by, bw, bh);
    ctx.globalAlpha = 0.7;
    for (let x = bx; x < bx + bw; x += 4) {
      ctx.fillRect(x, by, 2, 1);
      ctx.fillRect(x, by + bh - 1, 2, 1);
    }
    for (let y = by; y < by + bh; y += 4) {
      ctx.fillRect(bx, y, 1, 2);
      ctx.fillRect(bx + bw - 1, y, 1, 2);
    }
    ctx.globalAlpha = 1;
    drawText(ctx, id, at.x + 8 - Math.floor(textWidth(id) / 2), at.y + 25, "#5a5f73");
  }
}

function drawCorridorGuides(ctx: CanvasRenderingContext2D): void {
  // Coloured floor lines from the waiting-room door to each zone's door, as in real EDs.
  const y = ROOMS.corridor.r1 * TILE; // clear of the next wall's cap

  const from = 11 * TILE;
  const lines: [string, number, number][] = [
    [COL.red, 8 * TILE, y - 4],
    [COL.teal, 29 * TILE, y - 1],
    [COL.green, 25 * TILE, y + 2],
  ];
  for (const [color, to, ly] of lines) {
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.55;
    ctx.fillRect(Math.min(from, to), ly, Math.abs(to - from) + 8, 2);
    ctx.globalAlpha = 1;
  }
}

function drawFurniture(ctx: CanvasRenderingContext2D, f: Furniture): void {
  const { x, y, w, h } = px(f);
  switch (f.kind) {
    case "chair":
      ctx.fillStyle = COL.tealDark;
      ctx.fillRect(x + 2, y + 2, 12, 4);
      ctx.fillStyle = COL.teal;
      ctx.fillRect(x + 2, y + 6, 12, 8);
      ctx.fillStyle = "#62bdb6";
      ctx.fillRect(x + 3, y + 7, 10, 2);
      ctx.fillStyle = COL.ink;
      ctx.fillRect(x + 3, y + 14, 2, 1);
      ctx.fillRect(x + 11, y + 14, 2, 1);
      break;
    case "desk":
      ctx.fillStyle = COL.woodDark;
      ctx.fillRect(x, y + 11, w, 4);
      ctx.fillStyle = COL.wood;
      ctx.fillRect(x, y + 2, w, 10);
      ctx.fillStyle = "#d8b388";
      ctx.fillRect(x + 1, y + 3, w - 2, 1);
      ctx.fillStyle = COL.white;
      ctx.fillRect(x + 4, y + 5, 7, 5);
      drawText(ctx, "TRIAGE", x + 15, y + 5, COL.woodDark);
      ctx.fillStyle = COL.ink;
      ctx.fillRect(x + w - 13, y, 10, 8);
      ctx.fillStyle = COL.glass;
      ctx.fillRect(x + w - 12, y + 1, 8, 5);
      break;
    case "plant":
      ctx.fillStyle = "#c97b5c";
      ctx.fillRect(x + 3, y + 9, 10, 2);
      ctx.fillStyle = "#b5654a";
      ctx.fillRect(x + 4, y + 11, 8, 4);
      ctx.fillStyle = "#4f9a5a";
      ctx.fillRect(x + 2, y + 3, 12, 7);
      ctx.fillStyle = "#67b56f";
      ctx.fillRect(x + 5, y + 1, 6, 4);
      ctx.fillRect(x + 3, y + 4, 3, 2);
      ctx.fillStyle = "#8fd18f";
      ctx.fillRect(x + 6, y + 2, 2, 1);
      ctx.fillRect(x + 10, y + 5, 2, 1);
      break;
    case "vending":
      ctx.fillStyle = "#a83e48";
      ctx.fillRect(x + 1, y + 13, w - 2, 2);
      ctx.fillStyle = "#d0505a";
      ctx.fillRect(x + 1, y + 1, w - 2, 12);
      ctx.fillStyle = COL.glass;
      ctx.fillRect(x + 3, y + 3, w - 14, 8);
      for (let i = 0; i < 4; i++) {
        ctx.fillStyle = [COL.amber, COL.green, COL.white, COL.orange][i];
        ctx.fillRect(x + 5 + i * 4, y + 5, 2, 2);
        ctx.fillRect(x + 5 + i * 4, y + 8, 2, 2);
      }
      ctx.fillStyle = COL.ink;
      ctx.fillRect(x + w - 9, y + 3, 6, 8);
      break;
    case "monitor":
      ctx.fillStyle = COL.steelDark;
      ctx.fillRect(x + 7, y + 8, 2, 7);
      ctx.fillRect(x + 4, y + 14, 8, 2);
      ctx.fillStyle = COL.ink;
      ctx.fillRect(x + 2, y + 1, 12, 8);
      ctx.fillStyle = COL.screen;
      ctx.fillRect(x + 3, y + 2, 10, 6);
      ctx.fillStyle = COL.green;
      for (const [dx, dy] of [[0, 3], [1, 3], [2, 3], [3, 1], [4, 5], [5, 3], [6, 3], [7, 2], [8, 3], [9, 3]]) {
        ctx.fillRect(x + 3 + dx, y + 2 + dy, 1, 1);
      }
      break;
    case "cart":
      ctx.fillStyle = COL.redDark;
      ctx.fillRect(x + 2, y + 3, 12, 11);
      ctx.fillStyle = COL.red;
      ctx.fillRect(x + 2, y + 2, 12, 3);
      ctx.fillStyle = "#f3b0b0";
      ctx.fillRect(x + 3, y + 7, 10, 1);
      ctx.fillRect(x + 3, y + 10, 10, 1);
      ctx.fillStyle = COL.ink;
      ctx.fillRect(x + 3, y + 14, 2, 2);
      ctx.fillRect(x + 11, y + 14, 2, 2);
      break;
    case "curtain":
      ctx.fillStyle = COL.steelDark;
      ctx.fillRect(x, y + 1, w, 1);
      ctx.fillStyle = COL.mint;
      ctx.fillRect(x + 10, y + 1, 6, 13);
      ctx.fillStyle = COL.mintDark;
      ctx.fillRect(x + 11, y + 2, 1, 12);
      ctx.fillRect(x + 14, y + 2, 1, 12);
      break;
    case "console":
      ctx.fillStyle = COL.steelDark;
      ctx.fillRect(x, y + 12, w, 3);
      ctx.fillStyle = "#d8dde6";
      ctx.fillRect(x, y + 4, w, 9);
      for (const sx of [3, 17]) {
        ctx.fillStyle = COL.ink;
        ctx.fillRect(x + sx, y, 11, 8);
        ctx.fillStyle = COL.glass;
        ctx.fillRect(x + sx + 1, y + 1, 9, 5);
      }
      break;
    case "sofa":
      ctx.fillStyle = "#a8554a";
      ctx.fillRect(x, y + 1, w, 5);
      ctx.fillStyle = "#c86b5a";
      ctx.fillRect(x + 3, y + 5, w - 6, 9);
      ctx.fillStyle = "#a8554a";
      ctx.fillRect(x, y + 1, 3, 14);
      ctx.fillRect(x + w - 3, y + 1, 3, 14);
      for (let sx = x + 16; sx < x + w - 3; sx += 16) ctx.fillRect(sx, y + 6, 1, 8);
      break;
    case "coffee":
      ctx.fillStyle = "#a99e8e";
      ctx.fillRect(x, y + 12, w, 3);
      ctx.fillStyle = "#cfc6b8";
      ctx.fillRect(x, y + 2, w, 11);
      ctx.fillStyle = COL.ink;
      ctx.fillRect(x + 3, y + 1, 10, 10);
      ctx.fillStyle = COL.red;
      ctx.fillRect(x + 10, y + 3, 1, 1);
      ctx.fillStyle = "#6b4a33";
      ctx.fillRect(x + 6, y + 7, 3, 3);
      ctx.fillStyle = COL.white;
      ctx.fillRect(x + 18, y + 6, 3, 3);
      ctx.fillStyle = COL.teal;
      ctx.fillRect(x + 23, y + 7, 3, 3);
      break;
    case "locker":
      for (let ty = y; ty < y + h; ty += TILE) {
        ctx.fillStyle = "#5d7a99";
        ctx.fillRect(x + 2, ty, 13, 16);
        ctx.fillStyle = "#6f8fb0";
        ctx.fillRect(x + 3, ty + 1, 11, 14);
        ctx.fillStyle = "#dfe6ee";
        ctx.fillRect(x + 4, ty + 7, 1, 3);
        ctx.fillStyle = "#5d7a99";
        ctx.fillRect(x + 8, ty + 3, 4, 1);
        ctx.fillRect(x + 8, ty + 5, 4, 1);
      }
      break;
    case "table":
      ctx.fillStyle = "#a07850";
      ctx.fillRect(x + 2, y + 12, w - 4, 2);
      ctx.fillStyle = "#b98a5a";
      ctx.fillRect(x + 2, y + 3, w - 4, 10);
      ctx.fillStyle = "#d1a676";
      ctx.fillRect(x + 3, y + 4, w - 6, 1);
      ctx.fillStyle = COL.white;
      ctx.fillRect(x + 10, y + 6, 3, 3);
      ctx.fillStyle = COL.mint;
      ctx.fillRect(x + 30, y + 6, 8, 5);
      ctx.fillStyle = COL.amber;
      ctx.fillRect(x + 48, y + 7, 3, 3);
      break;
    case "cabinet":
      for (let ty = y; ty < y + h; ty += TILE) {
        ctx.fillStyle = COL.steelDark;
        ctx.fillRect(x + 1, ty, 15, 16);
        ctx.fillStyle = COL.steel;
        ctx.fillRect(x + 2, ty + 1, 13, 14);
        ctx.fillStyle = "#6b7480";
        ctx.fillRect(x + 3, ty + 6, 1, 4);
      }
      break;
    case "sink":
      ctx.fillStyle = "#c4d0d8";
      ctx.fillRect(x + 2, y + 3, 12, 10);
      ctx.fillStyle = "#9fbccc";
      ctx.fillRect(x + 4, y + 5, 8, 6);
      ctx.fillStyle = COL.steelDark;
      ctx.fillRect(x + 7, y + 2, 2, 4);
      break;
    case "bench":
      ctx.fillStyle = COL.woodDark;
      ctx.fillRect(x + 1, y + 11, w - 2, 2);
      ctx.fillStyle = COL.wood;
      ctx.fillRect(x + 1, y + 5, w - 2, 7);
      for (let sx = x + 6; sx < x + w - 2; sx += 8) {
        ctx.fillStyle = COL.woodDark;
        ctx.fillRect(sx, y + 5, 1, 7);
      }
      break;
    case "wheelchair":
      ctx.fillStyle = "rgba(15,12,30,0.25)";
      ctx.fillRect(x + 3, y + 13, 11, 2);
      ctx.fillStyle = "#3a3f55";
      ctx.fillRect(x + 2, y + 5, 2, 9); // wheels
      ctx.fillRect(x + 12, y + 5, 2, 9);
      ctx.fillStyle = "#8a93a6";
      ctx.fillRect(x + 2, y + 8, 2, 2);
      ctx.fillRect(x + 12, y + 8, 2, 2);
      ctx.fillStyle = "#3f7fbf";
      ctx.fillRect(x + 4, y + 3, 8, 3); // backrest
      ctx.fillStyle = "#5b9ad6";
      ctx.fillRect(x + 4, y + 6, 8, 5); // seat
      ctx.fillStyle = COL.steelDark;
      ctx.fillRect(x + 5, y + 11, 1, 3);
      ctx.fillRect(x + 10, y + 11, 1, 3);
      break;
    case "lamp":
      ctx.fillStyle = "rgba(20,20,40,0.25)";
      ctx.fillRect(x + 6, y + 10, 6, 3);
      ctx.fillStyle = COL.ink;
      ctx.fillRect(x + 7, y + 6, 2, 6);
      ctx.fillStyle = "#e9dca0";
      ctx.fillRect(x + 5, y + 3, 6, 4);
      ctx.fillStyle = COL.ink;
      ctx.fillRect(x + 5, y + 2, 6, 1);
      break;
  }
}

const AMB_W = 32;
const AMB_H = 48;

// Top-down ambulance, nose up. `flash` 0/1 alternates the roof lights (-1 = off); open rear doors stand
// out behind it at right angles.
function drawAmbulance(ctx: CanvasRenderingContext2D, v: VehicleEntity, flash: number): void {
  const x = Math.round(v.x);
  const y = Math.round(v.y);
  const w = AMB_W;
  const h = AMB_H;
  ctx.fillStyle = "rgba(20,20,40,0.3)";
  ctx.fillRect(x + 4, y + 4, w - 4, h - 2);
  const door = Math.round(10 * v.doorsOpen);
  if (door > 0) {
    ctx.fillStyle = "rgba(20,20,40,0.25)";
    ctx.fillRect(x + 4, y + h - 2, 3, door + 1);
    ctx.fillRect(x + w - 5, y + h - 2, 3, door + 1);
  }
  ctx.fillStyle = "#d9d9d4";
  ctx.fillRect(x + 2, y + 2, w - 4, h - 4);
  ctx.fillStyle = COL.white;
  ctx.fillRect(x + 3, y + 3, w - 6, h - 7);
  ctx.fillStyle = COL.glass;
  ctx.fillRect(x + 5, y + 4, w - 10, 6);
  ctx.fillStyle = "#6fa3c4";
  ctx.fillRect(x + 5, y + 9, w - 10, 1);
  const red = flash === 0 ? "#ff5a5a" : COL.red;
  const blue = flash === 1 ? "#7fb2ff" : "#3a6fd9";
  ctx.fillStyle = flash < 0 ? "#8a3a40" : red;
  ctx.fillRect(x + 6, y + 13, (w - 12) / 2, 3);
  ctx.fillStyle = flash < 0 ? "#34507a" : blue;
  ctx.fillRect(x + w / 2, y + 13, (w - 12) / 2, 3);
  if (flash >= 0) {
    // Bright core on whichever half is lit.
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(flash === 0 ? x + 9 : x + w / 2 + 4, y + 14, 3, 1);
  }
  ctx.fillStyle = COL.red;
  ctx.fillRect(x + 2, y + 30, w - 4, 3);
  ctx.fillRect(x + w / 2 - 1, y + 19, 2, 8);
  ctx.fillRect(x + w / 2 - 4, y + 22, 8, 2);
  ctx.fillStyle = COL.ink;
  ctx.fillRect(x + 1, y + 8, 1, 6);
  ctx.fillRect(x + w - 2, y + 8, 1, 6);
  ctx.fillRect(x + 1, y + h - 14, 1, 6);
  ctx.fillRect(x + w - 2, y + h - 14, 1, 6);
  // Tail lights, and the dark cabin plus both door leaves once the rear doors open.
  ctx.fillStyle = "#c8323c";
  ctx.fillRect(x + 3, y + h - 4, 2, 1);
  ctx.fillRect(x + w - 5, y + h - 4, 2, 1);
  if (door > 0) {
    ctx.fillStyle = "#2a2a3a";
    ctx.fillRect(x + 5, y + h - 5, w - 10, 3);
    for (const dx of [2, w - 5]) {
      ctx.fillStyle = COL.ink;
      ctx.fillRect(x + dx, y + h - 3, 3, door);
      ctx.fillStyle = COL.white;
      ctx.fillRect(x + dx + 1, y + h - 3, 1, door - 1);
    }
  }
}

// Red lit box sign on two posts over the walk-in entrance.
function emergencySign(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
  const text = "EMERGENCY";
  const w = textWidth(text) + 10;
  const x = Math.round(cx - w / 2);
  const y = Math.round(cy - 6);
  ctx.fillStyle = "rgba(15,12,30,0.3)";
  ctx.fillRect(x + 2, y + 14, w, 3);
  ctx.fillStyle = COL.ink;
  ctx.fillRect(x + 3, y + 12, 2, 6);
  ctx.fillRect(x + w - 5, y + 12, 2, 6);
  ctx.fillStyle = "#7a1c24";
  ctx.fillRect(x - 1, y - 1, w + 2, 14);
  ctx.fillStyle = "#d63a44";
  ctx.fillRect(x, y, w, 12);
  ctx.fillStyle = "#ef6a72";
  ctx.fillRect(x, y, w, 1);
  drawText(ctx, text, x + 5, y + 4, "#fff4f4");
  // Small white cross badge on the left end.
  ctx.fillStyle = "#fff4f4";
  ctx.fillRect(x + 1, y + 5, 3, 1);
  ctx.fillRect(x + 2, y + 4, 1, 3);
}

function buildStatic(layout: Layout): HTMLCanvasElement {
  const [canvas, ctx] = newCanvas(MAP_W, MAP_H);
  ctx.imageSmoothingEnabled = false;
  layout.tiles.forEach((row, r) => row.forEach((kind, c) => drawTile(ctx, kind, c * TILE, r * TILE)));
  drawOutdoors(ctx, layout);
  const morgue = px(ROOMS.morgue);
  ctx.fillStyle = "rgba(110, 150, 200, 0.18)";
  ctx.fillRect(morgue.x, morgue.y, morgue.w, morgue.h);
  // Rug under the staff-room seating, before furniture so people and the table sit on it.
  ctx.fillStyle = "rgba(150, 110, 170, 0.22)";
  ctx.fillRect(30 * TILE + 4, 12 * TILE + 4, 5 * TILE - 8, 3 * TILE - 8);
  drawBays(ctx, layout);
  drawCorridorGuides(ctx);
  drawWallShadows(ctx, layout);
  // Furniture before walls: a wall's cap rises over whatever stands right behind it.
  for (const f of FURNITURE) drawFurniture(ctx, f);
  drawWalls(ctx, layout);
  // Exit chevrons in the lobby.
  ctx.fillStyle = COL.greenDark;
  for (let i = 0; i < 2; i++) {
    const cx = (EXIT_COL + 1) * TILE;
    const cy = 17 * TILE + 6 + i * 8;
    for (let d = 0; d < 4; d++) {
      ctx.fillRect(cx - 4 + d, cy + d, 1, 1);
      ctx.fillRect(cx + 3 - d, cy + d, 1, 1);
    }
  }
  for (const l of layout.labels) {
    if (l.text === "AMBULANCE") {
      drawText(ctx, l.text, Math.round(l.at.x - textWidth(l.text) / 2), l.at.y - 2, COL.amber);
      continue;
    }
    if (l.text === "EMERGENCY") {
      emergencySign(ctx, l.at.x, l.at.y);
      continue;
    }
    const zone = ZONES.find((z) => ZONE_LABEL[z] === l.text);
    const accent = zone ? ZONE_COLOR[zone] : l.text === "EXIT" ? COL.green : COL.mint;
    plaque(ctx, l.text, l.at.x, l.at.y, accent);
  }
  return canvas;
}

function fmt(n: number): string {
  const r = Math.round(n * 10) / 10;
  return Number.isInteger(r) ? String(r) : r.toFixed(1);
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

// Beds a zone can treat this tick: min(doctor cover, nurse cover), each person 0.6 above fatigue 60.
function zoneCapacity(staff: StaffEntity[], zone: Zone): number {
  let d = 0;
  let n = 0;
  for (const s of staff) {
    if (s.status !== "on_shift" || s.location !== zone) continue;
    const w = s.fatigue > 60 ? 0.6 : 1;
    if (s.role === "doctor") d += w;
    else n += w;
  }
  return Math.floor(Math.min(d * BEDS_PER_DOCTOR[zone], n * BEDS_PER_NURSE[zone]) + 1e-9);
}

// One ECG beat as y offsets; the wall monitors scroll it.
const BEAT = [0, 0, 0, 0, 0, -1, 0, 0, 1, -4, 3, 0, 0, 0, -1, -1, 0, 0, 0, 0];

const TONE: Record<Light["tone"], [number, number, number]> = {
  warm: [255, 186, 110],
  cool: [190, 225, 255],
  cold: [110, 160, 255],
};

const EFFECT_BURST: Partial<Record<EffectKind, Burst>> = {
  arrival: "arrival",
  admitted: "admit",
  discharged: "sparkle",
  death: "blood",
  left: "dust",
  diverted: "dust",
  upgrade: "upgrade",
  faint: "faint",
  spend: "coins",
};

type Person = PatientEntity | StaffEntity;

export class Renderer {
  /** Entity or bed id to outline (set by the HUD, e.g. from pick()). */
  selected: string | null = null;

  private ctx: CanvasRenderingContext2D;
  private zoom = 2;
  private cssW = MAP_W;
  private staticLayer: HTMLCanvasElement;
  private dark: [HTMLCanvasElement, CanvasRenderingContext2D];
  private glow: [HTMLCanvasElement, CanvasRenderingContext2D];
  private vignette: CanvasGradient;
  private zoneSign: Record<Zone, { x: number; y: number }>;
  private particles = new Particles();
  private lastFrame: Frame | null = null;

  // Transition effects and state carried between frames.
  private lastTime = -1;
  private lastTick = -1;
  private seenFx = new Set<string>();
  private wasMoving = new Map<string, boolean>();
  private wasDead = new Set<string>();
  private prevEvents = new Set<string>();
  private shake = { start: 0, dur: 0, amp: 0 };
  private flashAt = -1e9;

  constructor(
    private canvas: HTMLCanvasElement,
    private layout: Layout,
  ) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas not supported");
    this.ctx = ctx;
    this.staticLayer = buildStatic(layout);
    this.dark = newCanvas(MAP_W, MAP_H);
    this.glow = newCanvas(MAP_W, MAP_H);
    const v = ctx.createRadialGradient(MAP_W / 2, MAP_H / 2, MAP_H * 0.42, MAP_W / 2, MAP_H / 2, MAP_W * 0.62);
    v.addColorStop(0, "rgba(8, 6, 20, 0)");
    v.addColorStop(1, "rgba(8, 6, 20, 0.55)");
    this.vignette = v;
    this.zoneSign = {} as Record<Zone, { x: number; y: number }>;
    for (const z of ZONES) {
      const l = layout.labels.find((lb) => lb.text === ZONE_LABEL[z]);
      const at = l?.at ?? { x: 0, y: 0 };
      this.zoneSign[z] = { x: Math.round(at.x + (textWidth(ZONE_LABEL[z]) + 8) / 2) + 3, y: Math.round(at.y) };
    }
    this.resize();
    const parent = canvas.parentElement;
    if (parent && typeof ResizeObserver !== "undefined") new ResizeObserver(() => this.resize()).observe(parent);
  }

  // Fill the canvas's parent with the whole map: draw at an integer zoom, CSS-scale to the exact fit.
  resize(): void {
    const parent = this.canvas.parentElement ?? document.body;
    const fit = fitZoom(parent.clientWidth, parent.clientHeight, MAP_W, MAP_H, window.devicePixelRatio || 1);
    if (this.canvas.width !== fit.pxW || this.canvas.height !== fit.pxH) {
      this.canvas.width = fit.pxW;
      this.canvas.height = fit.pxH;
    }
    this.canvas.style.width = `${fit.cssW}px`;
    this.canvas.style.height = `${fit.cssH}px`;
    // Nearest-neighbour only at an exact integer fit; when shrinking a little, smooth sampling avoids
    // dropped pixel rows.
    this.canvas.style.imageRendering = fit.exact ? "pixelated" : "auto";
    this.zoom = fit.zoom;
    this.cssW = fit.cssW;
  }

  // Entity id (patient or staff) or bed id under a point given in canvas CSS pixels
  // (e.g. MouseEvent.offsetX/offsetY), or null.
  pick(x: number, y: number): string | null {
    const s = MAP_W / this.cssW;
    const mx = x * s;
    const my = y * s;
    const f = this.lastFrame;
    if (f) {
      for (const e of this.sorted(f).reverse()) {
        if (e.alpha > 0.01 && mx >= e.x + 2 && mx < e.x + 14 && my >= e.y && my < e.y + 16) return e.id;
      }
    }
    for (const [id, at] of Object.entries(this.layout.beds)) {
      if (mx >= at.x && mx < at.x + 16 && my >= at.y && my < at.y + 24) return id;
    }
    return null;
  }

  render(frame: Frame, timeMs: number): void {
    const dt = this.lastTime < 0 ? 0 : Math.min(100, Math.max(0, timeMs - this.lastTime)) / 1000;
    this.lastTime = timeMs;
    this.lastFrame = frame;
    this.trackChanges(frame, timeMs);
    if (!frame.ct.working && Math.random() < dt * 5) {
      this.particles.emit("sparks", this.layout.ct.x + 6 + Math.random() * 20, this.layout.ct.y + 8);
    }
    for (const v of frame.vehicles) {
      // Exhaust puffs from the tailpipe while an ambulance drives.
      if (v.moving && v.y > -AMB_H && Math.random() < dt * 9) this.particles.emit("dust", v.x + 6, v.y + AMB_H - 6);
    }
    this.particles.update(dt);

    const ctx = this.ctx;
    const anim = Math.floor(timeMs / 250);
    const blink = Math.floor(timeMs / 400) % 2 === 0;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "#14141c";
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    const [sx, sy] = this.shakeOffset(timeMs);
    ctx.setTransform(this.zoom, 0, 0, this.zoom, sx * this.zoom, sy * this.zoom);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.staticLayer, 0, 0);

    const inBed = new Map<string, PatientEntity>();
    for (const p of frame.patients) if (p.state === "in_bed" && p.bed) inBed.set(p.bed, p);
    this.drawWallMonitors(inBed, timeMs);
    for (const [id, at] of Object.entries(this.layout.beds)) {
      ctx.fillStyle = "rgba(15, 12, 30, 0.28)";
      ctx.fillRect(at.x + 3, at.y + 22, 14, 3);
      ctx.fillRect(at.x + 15, at.y + 4, 2, 19);
      drawBed(ctx, at.x, at.y, inBed.has(id));
    }
    ctx.fillStyle = "rgba(15, 12, 30, 0.28)";
    ctx.fillRect(this.layout.ct.x + 2, this.layout.ct.y + 30, 32, 4);
    drawCt(ctx, this.layout.ct.x, this.layout.ct.y, frame.ct.working, anim);
    const siren = Math.floor(timeMs / 180) % 2;
    for (const v of frame.vehicles) drawAmbulance(ctx, v, v.siren ? siren : -1);

    const people = this.sorted(frame).filter((e) => e.alpha > 0.01);
    for (const e of people) {
      if (e.kind === "patient" && e.state === "in_bed") continue;
      this.footShadow(e);
    }
    for (const e of people) {
      if (e.kind === "patient") drawPatient(ctx, e, anim);
      else drawStaff(ctx, e, anim);
    }
    ctx.globalAlpha = 1;
    this.drawBedStatus(inBed, blink);
    this.drawSelection(frame, timeMs);

    this.drawLighting(frame, inBed, timeMs);
    this.particles.draw(ctx);
    for (const fx of frame.effects) drawEffect(ctx, fx);
    ctx.globalAlpha = 1;
    this.drawZoneCoverage(frame, inBed, blink);
    if (!frame.ct.working) this.drawCtDownSign(frame, blink);
    if (frame.diversion.active) this.drawDiversion(frame, blink);

    ctx.fillStyle = this.vignette;
    ctx.fillRect(-8, -8, MAP_W + 16, MAP_H + 16);
    const flash = 1 - (timeMs - this.flashAt) / 350;
    if (flash > 0) {
      ctx.fillStyle = `rgba(255, 255, 255, ${0.75 * flash})`;
      ctx.fillRect(-8, -8, MAP_W + 16, MAP_H + 16);
    }
  }

  private sorted(frame: Frame): Person[] {
    // Ties: patients first, so staff standing level with a bed draw over it.
    return [...frame.patients, ...frame.staff].sort(
      (a, b) => a.y - b.y || (a.kind === b.kind ? 0 : a.kind === "patient" ? -1 : 1),
    );
  }

  private footShadow(e: Person): void {
    const ctx = this.ctx;
    const x = Math.round(e.x);
    const y = Math.round(e.y);
    ctx.fillStyle = `rgba(15, 12, 30, ${0.3 * e.alpha})`;
    ctx.fillRect(x + 4, y + 13, 8, 1);
    ctx.fillRect(x + 3, y + 14, 10, 2);
    ctx.fillRect(x + 4, y + 16, 8, 1);
  }

  // Spawn particles and juice for whatever changed since the previous frame. A seek (tick jump)
  // just re-baselines, so scrubbing the timeline doesn't fire a storm of bursts.
  private trackChanges(frame: Frame, timeMs: number): void {
    const live = this.lastTick >= 0 && Math.abs(frame.tick - this.lastTick) <= 1;
    if (!live) this.particles.clear();
    this.lastTick = frame.tick;

    const fxKeys = new Set<string>();
    let deathFx = false;
    for (const fx of frame.effects) {
      const key = `${fx.kind}|${fx.text ?? ""}|${Math.floor(fx.x / TILE)}|${Math.floor(fx.y / TILE)}`;
      fxKeys.add(key);
      if (!live || this.seenFx.has(key)) continue;
      const burst = EFFECT_BURST[fx.kind];
      if (burst) this.particles.emit(burst, fx.x + 8, fx.y + 8);
      if (fx.kind === "death") {
        deathFx = true;
        this.kick(timeMs, 2.5, 380);
      }
      if (fx.kind === "faint") this.kick(timeMs, 1.5, 250);
      if (fx.kind === "event_start" && /bus/i.test(fx.text ?? "")) this.busCrash(timeMs);
    }
    this.seenFx = fxKeys;

    const dead = new Set<string>();
    for (const p of frame.patients) {
      if (p.state !== "dead") continue;
      dead.add(p.id);
      if (live && !deathFx && !this.wasDead.has(p.id)) {
        this.particles.emit("blood", p.x + 8, p.y + 8);
        this.kick(timeMs, 2.5, 380);
      }
    }
    this.wasDead = dead;

    const moving = new Map<string, boolean>();
    for (const e of [...frame.patients, ...frame.staff]) {
      moving.set(e.id, e.moving);
      if (live && e.moving && this.wasMoving.get(e.id) === false && e.alpha > 0.3) {
        this.particles.emit("dust", e.x + 8, e.y + 15);
      }
    }
    this.wasMoving = moving;

    const events = new Set(frame.activeEvents);
    if (live && events.has("bus_crash") && !this.prevEvents.has("bus_crash")) this.busCrash(timeMs);
    if (live && events.has("ct_breakdown") && !this.prevEvents.has("ct_breakdown")) this.kick(timeMs, 1.5, 300);
    this.prevEvents = events;
  }

  private busCrash(timeMs: number): void {
    if (timeMs - this.flashAt < 1000) return; // the effect and activeEvents both report it
    this.flashAt = timeMs;
    this.kick(timeMs, 5, 650);
  }

  private kick(timeMs: number, amp: number, dur: number): void {
    const t = this.shake.dur > 0 ? (timeMs - this.shake.start) / this.shake.dur : 1;
    const left = t < 1 ? this.shake.amp * (1 - t) : 0;
    if (amp < left) return;
    this.shake = { start: timeMs, dur, amp };
  }

  private shakeOffset(timeMs: number): [number, number] {
    if (this.shake.dur <= 0) return [0, 0];
    const t = (timeMs - this.shake.start) / this.shake.dur;
    if (t < 0 || t >= 1) return [0, 0];
    const a = this.shake.amp * (1 - t) * (1 - t);
    return [Math.round((Math.random() * 2 - 1) * a), Math.round((Math.random() * 2 - 1) * a)];
  }

  // Heart monitors on the wall behind Resus and Acute beds, scrolling an ECG trace.
  private drawWallMonitors(inBed: Map<string, PatientEntity>, timeMs: number): void {
    const ctx = this.ctx;
    for (const [id, at] of Object.entries(this.layout.beds)) {
      if (this.layout.bedZone[id] === "fast_track") continue;
      const x = at.x + 2;
      const y = at.y - 2 * TILE + 5; // on the face of the wall two tiles behind the bed head
      ctx.fillStyle = "#3a3f55";
      ctx.fillRect(x - 1, y - 1, 14, 10);
      ctx.fillStyle = "#0c1a20";
      ctx.fillRect(x, y, 12, 8);
      const p = inBed.get(id);
      if (!p) {
        ctx.fillStyle = "#2a4a40";
        ctx.fillRect(x + 1, y + 5, 10, 1);
        continue;
      }
      const color = p.waitingForCt ? COL.amber : p.covered ? "#5cf08a" : COL.red;
      const bpm = p.esi <= 2 ? 120 : 80;
      const head = Math.floor((timeMs / 1000) * (bpm / 60) * BEAT.length);
      ctx.fillStyle = color;
      for (let i = 0; i < 11; i++) {
        const v = BEAT[(head - 10 + i + BEAT.length * 1000) % BEAT.length];
        ctx.fillRect(x + 1 + i, y + 5 + Math.max(-4, Math.min(2, v)), 1, 1);
      }
    }
  }

  private drawBedStatus(inBed: Map<string, PatientEntity>, blink: boolean): void {
    const ctx = this.ctx;
    for (const [id, at] of Object.entries(this.layout.beds)) {
      const p = inBed.get(id);
      if (!p) continue;
      const prog = Math.max(0, Math.min(1, p.progress));
      ctx.fillStyle = COL.ink;
      ctx.fillRect(at.x + 1, at.y + 31, 14, 3);
      ctx.fillStyle = p.waitingForCt ? COL.amber : p.covered ? COL.green : blink ? COL.red : COL.muted;
      ctx.fillRect(at.x + 2, at.y + 32, Math.round(12 * prog), 1);
    }
  }

  private drawSelection(frame: Frame, timeMs: number): void {
    if (!this.selected) return;
    const ctx = this.ctx;
    ctx.fillStyle = Math.floor(timeMs / 150) % 2 ? "#ffe066" : "#fff6c2";
    const ring = (x: number, y: number, w: number, h: number): void => {
      ctx.fillRect(x, y, w, 1);
      ctx.fillRect(x, y + h - 1, w, 1);
      ctx.fillRect(x, y, 1, h);
      ctx.fillRect(x + w - 1, y, 1, h);
    };
    const e = [...frame.patients, ...frame.staff].find((p) => p.id === this.selected);
    if (e) ring(Math.round(e.x), Math.round(e.y) - 2, 16, 19);
    const bed = this.layout.beds[this.selected];
    if (bed) ring(bed.x - 2, bed.y - 2, 20, 28);
  }

  // Ambient darkness with light pools cut out of it (destination-out), then additive coloured glow:
  // lamp light, the Resus alarm when a bed there is uncovered, and a flickering red CT room while broken.
  private drawLighting(frame: Frame, inBed: Map<string, PatientEntity>, timeMs: number): void {
    const d = darkness(hourOfDay(frame.tick, frame.phase));
    const [darkC, dc] = this.dark;
    const [glowC, gc] = this.glow;
    const b = px(BUILDING);

    dc.globalCompositeOperation = "source-over";
    dc.clearRect(0, 0, MAP_W, MAP_H);
    dc.fillStyle = `rgba(10, 12, 38, ${lerp(0.06, 0.72, d)})`;
    dc.fillRect(0, 0, MAP_W, MAP_H);
    dc.clearRect(b.x, b.y, b.w, b.h);
    dc.fillStyle = `rgba(${Math.round(lerp(28, 12, d))}, ${Math.round(lerp(20, 12, d))}, 44, ${lerp(0.24, 0.62, d)})`;
    dc.fillRect(b.x, b.y, b.w, b.h);
    dc.globalCompositeOperation = "destination-out";
    for (const l of LIGHTS) {
      const s = l.outdoor ? 0.95 * d : 0.92;
      if (s <= 0.01) continue;
      const g = dc.createRadialGradient(l.x, l.y, 0, l.x, l.y, l.r);
      g.addColorStop(0, `rgba(0,0,0,${s})`);
      g.addColorStop(0.55, `rgba(0,0,0,${s * 0.6})`);
      g.addColorStop(1, "rgba(0,0,0,0)");
      dc.fillStyle = g;
      dc.fillRect(l.x - l.r, l.y - l.r, l.r * 2, l.r * 2);
    }

    gc.globalCompositeOperation = "source-over";
    gc.clearRect(0, 0, MAP_W, MAP_H);
    const pool = (x: number, y: number, r: number, rgb: [number, number, number], a: number): void => {
      if (a <= 0.005) return;
      const g = gc.createRadialGradient(x, y, 0, x, y, r);
      g.addColorStop(0, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${a})`);
      g.addColorStop(1, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0)`);
      gc.fillStyle = g;
      gc.fillRect(x - r, y - r, r * 2, r * 2);
    };
    for (const l of LIGHTS) {
      const a = l.outdoor ? 0.22 * d : l.tone === "warm" ? lerp(0.07, 0.16, d) : lerp(0.04, 0.1, d);
      pool(l.x, l.y, l.r * 0.8, TONE[l.tone], a);
    }
    const sign = this.layout.labels.find((l) => l.text === "EMERGENCY");
    if (sign) pool(sign.at.x, sign.at.y, 34, [255, 60, 70], lerp(0.12, 0.35, d));
    // Ambulance roof lights wash the bay red and blue in turn, strongest at night.
    const flash = Math.floor(timeMs / 180) % 2;
    for (const v of frame.vehicles) {
      if (!v.siren) continue;
      const lx = v.x + (flash === 0 ? 10 : AMB_W - 10);
      pool(lx, v.y + 14, 40, flash === 0 ? [255, 50, 60] : [70, 120, 255], lerp(0.25, 0.55, d));
    }
    const alarm = Object.entries(this.layout.beds).some(([id]) => {
      const p = inBed.get(id);
      return this.layout.bedZone[id] === "resus" && !!p && !p.covered;
    });
    if (alarm) {
      const resus = px(ROOMS.resus);
      const a = 0.18 + 0.22 * (0.5 + 0.5 * Math.sin(timeMs / 160));
      pool(resus.x + resus.w / 2, resus.y + resus.h / 2, resus.w * 0.75, [255, 40, 40], a);
    }
    if (!frame.ct.working) {
      const ct = px(ROOMS.ct);
      // Hash of a coarse time step: an irregular flicker rather than a smooth pulse.
      const step = Math.floor(timeMs / 70);
      const h = (Math.imul(step, 2654435761) >>> 0) / 4294967296;
      const a = h < 0.25 ? 0.05 : 0.22 + 0.25 * h;
      pool(ct.x + ct.w / 2, ct.y + ct.h / 2, ct.w * 0.9, [255, 30, 30], a);
    }

    const ctx = this.ctx;
    ctx.drawImage(darkC, 0, 0);
    ctx.globalCompositeOperation = "lighter";
    ctx.drawImage(glowC, 0, 0);
    ctx.globalCompositeOperation = "source-over";
  }

  private drawCtDownSign(frame: Frame, blink: boolean): void {
    const ctx = this.ctx;
    const r = px(ROOMS.ct);
    const text = frame.ct.downTicksLeft > 0 ? `CT DOWN ${frame.ct.downTicksLeft}` : "CT DOWN";
    const w = textWidth(text) + 8;
    const x = Math.round(r.x + (r.w - w) / 2);
    const y = r.y + 3 * TILE + 12; // just below the scanner, clear of the console
    ctx.fillStyle = blink ? COL.red : COL.redDark;
    ctx.fillRect(x - 1, y - 1, w + 2, 11);
    ctx.fillStyle = "#3a1418";
    ctx.fillRect(x, y, w, 9);
    drawText(ctx, text, x + 4, y + 2, blink ? "#ffd0d0" : COL.text);
  }

  private drawZoneCoverage(frame: Frame, inBed: Map<string, PatientEntity>, blink: boolean): void {
    const ctx = this.ctx;
    for (const zone of ZONES) {
      const beds = Object.keys(this.layout.beds).filter((id) => this.layout.bedZone[id] === zone);
      const patients = beds.map((id) => inBed.get(id)).filter((p): p is PatientEntity => !!p);
      const covered = patients.filter((p) => p.covered).length;
      const occupied = patients.length;
      const cap = zoneCapacity(frame.staff, zone);
      const staffText = fmt(frame.zoneCoverage[zone] ?? 0);
      const { x, y } = this.zoneSign[zone];
      const w = beds.length * 5 + 4 + textWidth(staffText) + 4;
      ctx.fillStyle = COL.navyEdge;
      ctx.fillRect(x - 1, y - 6, w + 2, 12);
      ctx.fillStyle = COL.navy;
      ctx.fillRect(x, y - 5, w, 10);
      // One pip per bed: filled = occupied (green covered / red uncovered); outlined green = staff
      // on shift could cover one more patient; grey = nobody to cover that bed.
      for (let i = 0; i < beds.length; i++) {
        const pxX = x + 2 + i * 5;
        const pyY = y - 3;
        if (i < occupied) {
          ctx.fillStyle = i < covered ? COL.green : blink ? COL.red : COL.redDark;
          ctx.fillRect(pxX, pyY, 4, 6);
        } else {
          ctx.fillStyle = i < cap ? COL.green : "#4a5068";
          ctx.fillRect(pxX, pyY, 4, 1);
          ctx.fillRect(pxX, pyY + 5, 4, 1);
          ctx.fillRect(pxX, pyY, 1, 6);
          ctx.fillRect(pxX + 3, pyY, 1, 6);
        }
      }
      drawText(ctx, staffText, x + 4 + beds.length * 5, y - 2, cap < occupied ? COL.orange : COL.text);
    }
  }

  private drawDiversion(frame: Frame, blink: boolean): void {
    const ctx = this.ctx;
    // Barrier across the ambulance bay mouth.
    const by = (AMBULANCE_BAY.r1 + 1) * TILE - 8;
    for (let x = 0; x < (AMBULANCE_BAY.c1 + 1) * TILE; x += 8) {
      ctx.fillStyle = (x / 8) % 2 ? COL.white : COL.red;
      ctx.fillRect(x, by, 8, 4);
    }
    // Sign board on the sidewalk by the entrance.
    const text = frame.diversion.ticksLeft > 0 ? `DIVERT ${frame.diversion.ticksLeft}` : "DIVERT";
    const w = Math.max(textWidth(text) + 10, 44);
    const x = 2 * TILE + 8 - Math.floor(w / 2);
    const y = (AMBULANCE_BAY.r1 + 2) * TILE + 2;
    ctx.fillStyle = COL.ink;
    ctx.fillRect(x + 4, y + 13, 2, 4);
    ctx.fillRect(x + w - 6, y + 13, 2, 4);
    ctx.fillStyle = COL.amber;
    ctx.fillRect(x - 1, y - 1, w + 2, 15);
    ctx.fillStyle = "#2a2418";
    ctx.fillRect(x, y, w, 13);
    drawText(ctx, "ER FULL", x + Math.floor((w - textWidth("ER FULL")) / 2), y + 1, COL.amber);
    drawText(ctx, text, x + Math.floor((w - textWidth(text)) / 2), y + 7, COL.text);
    ctx.fillStyle = blink ? COL.orange : "#6a4a20";
    ctx.fillRect(x - 2, y - 3, 3, 3);
    ctx.fillStyle = blink ? "#6a4a20" : COL.orange;
    ctx.fillRect(x + w - 1, y - 3, 3, 3);
  }
}
