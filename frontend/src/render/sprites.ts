// Pixel-art drawing for every entity, tile and effect. All art is drawn in code (no image assets).
// Owner: agent C (sprites). STUB: flat rectangles so the app runs end to end.
// Every function draws at map-pixel coordinates (x, y) = top-left of a 16x16 cell; the renderer
// has already applied the integer zoom, and image smoothing is off.

import type { Effect, PatientEntity, StaffEntity } from "../replay/frame";
import type { TileKind } from "../world/layout";

export function drawTile(ctx: CanvasRenderingContext2D, kind: TileKind, x: number, y: number): void {
  ctx.fillStyle = kind === "wall" ? "#333" : kind === "void" ? "#000" : "#ccc";
  ctx.fillRect(x, y, 16, 16);
}

export function drawBed(ctx: CanvasRenderingContext2D, x: number, y: number, occupied: boolean): void {
  ctx.fillStyle = occupied ? "#88a" : "#eef";
  ctx.fillRect(x + 1, y + 1, 14, 22);
}

export function drawCt(ctx: CanvasRenderingContext2D, x: number, y: number, working: boolean, frame: number): void {
  ctx.fillStyle = working ? "#9ab" : frame % 2 ? "#a33" : "#733";
  ctx.fillRect(x, y, 32, 32);
}

const ESI_COLOR = ["", "#d22", "#e80", "#ed2", "#3b3", "#38d"];

export function drawPatient(ctx: CanvasRenderingContext2D, p: PatientEntity, frame: number): void {
  void frame;
  ctx.globalAlpha = p.alpha;
  ctx.fillStyle = ESI_COLOR[p.esi];
  ctx.fillRect(p.x + 4, p.y + 2, 8, 12);
  ctx.globalAlpha = 1;
}

export function drawStaff(ctx: CanvasRenderingContext2D, s: StaffEntity, frame: number): void {
  void frame;
  ctx.globalAlpha = s.alpha;
  ctx.fillStyle = s.role === "doctor" ? "#fff" : "#3ac";
  ctx.fillRect(s.x + 4, s.y + 2, 8, 12);
  ctx.globalAlpha = 1;
}

export function drawEffect(ctx: CanvasRenderingContext2D, e: Effect): void {
  if (!e.text) return;
  ctx.globalAlpha = 1 - e.age;
  ctx.fillStyle = "#000";
  ctx.font = "8px monospace";
  ctx.fillText(e.text, e.x, e.y - e.age * 12);
  ctx.globalAlpha = 1;
}
