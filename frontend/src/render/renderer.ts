// Draws one Frame onto the canvas: tiles, beds, CT, entities (y-sorted), effects, labels.
// Owner: agent B (map + renderer). STUB: minimal drawing so the app runs end to end.

import type { Frame } from "../replay/frame";
import { MAP_COLS, MAP_ROWS, TILE, type Layout } from "../world/layout";
import { drawBed, drawCt, drawEffect, drawPatient, drawStaff, drawTile } from "./sprites";

export class Renderer {
  private ctx: CanvasRenderingContext2D;
  private zoom = 2;

  constructor(
    private canvas: HTMLCanvasElement,
    private layout: Layout,
  ) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas not supported");
    this.ctx = ctx;
    this.resize();
  }

  // Fit the whole map into the canvas's parent at the largest integer zoom.
  resize(): void {
    const parent = this.canvas.parentElement ?? document.body;
    const w = MAP_COLS * TILE;
    const h = MAP_ROWS * TILE;
    this.zoom = Math.max(1, Math.floor(Math.min(parent.clientWidth / w, parent.clientHeight / h)));
    this.canvas.width = w * this.zoom;
    this.canvas.height = h * this.zoom;
  }

  render(frame: Frame, timeMs: number): void {
    const ctx = this.ctx;
    const anim = Math.floor(timeMs / 250);
    ctx.setTransform(this.zoom, 0, 0, this.zoom, 0, 0);
    ctx.imageSmoothingEnabled = false;
    this.layout.tiles.forEach((row, r) => row.forEach((kind, c) => drawTile(ctx, kind, c * TILE, r * TILE)));
    const occupied = new Set(frame.patients.filter((p) => p.state === "in_bed").map((p) => p.bed));
    for (const [id, at] of Object.entries(this.layout.beds)) drawBed(ctx, at.x, at.y, occupied.has(id));
    drawCt(ctx, this.layout.ct.x, this.layout.ct.y, frame.ct.working, anim);
    const people = [...frame.patients, ...frame.staff].sort((a, b) => a.y - b.y);
    for (const e of people) {
      if (e.kind === "patient") drawPatient(ctx, e, anim);
      else drawStaff(ctx, e, anim);
    }
    for (const fx of frame.effects) drawEffect(ctx, fx);
  }
}
