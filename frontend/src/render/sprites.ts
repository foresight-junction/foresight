// Pixel-art drawing for every entity, tile and effect. All art is drawn in code (no image assets):
// pixel maps in src/render/art/ are rendered once to offscreen canvases and cached, so each call here
// is a handful of drawImage calls.
// Owner: agent C (sprites).
//
// Every function draws at map-pixel coordinates (x, y) = top-left of a 16x16 cell; the renderer has
// already applied the integer zoom, and image smoothing is off. For a patient in bed, (p.x, p.y) is
// the bed's top-left (beds are 16 x 24). `frame` ticks every 250 ms.

import type { Effect, PatientEntity, StaffEntity } from "../replay/frame";
import type { TileKind } from "../world/layout";
import { drawEffectAt } from "./art/effects";
import { drawBedAt, drawCtAt } from "./art/furniture";
import { drawEsiBadge, drawIcon } from "./art/icons";
import { animPhase, lookFor, personSprite, sheetSprite, sitAnim, standAnim, type PoseSpec } from "./art/people";
import { blit, withAlpha } from "./art/pixmap";
import { drawTileAt, drawWallFaceAt } from "./art/tiles";
import { ESI_RAMP, GOOD, OUTLINE, SHADOW, WARN } from "./palette";

export { drawText, drawTextCentered, measureText, FONT_HEIGHT } from "./art/font";
export { drawIcon, drawEsiBadge, iconSize, ICON_KINDS, type IconKind } from "./art/icons";
export { drawProp, drawMonitorAt as drawMonitor } from "./art/furniture";

export function drawTile(ctx: CanvasRenderingContext2D, kind: TileKind, x: number, y: number): void {
  drawTileAt(ctx, kind, x, y);
}

// Front face of a wall (3/4 view), drawn in the cell(s) below a "wall" cap tile. Default height is
// two tile rows (32 px); pass 16 for a one-row face. Its bottom edge is the floor line.
export function drawWallFace(ctx: CanvasRenderingContext2D, x: number, y: number, height = 32): void {
  drawWallFaceAt(ctx, x, y, height);
}

export function drawBed(ctx: CanvasRenderingContext2D, x: number, y: number, occupied: boolean): void {
  drawBedAt(ctx, x, y, occupied);
}

export function drawCt(ctx: CanvasRenderingContext2D, x: number, y: number, working: boolean, frame: number): void {
  drawCtAt(ctx, x, y, working, frame);
}

function shadow(ctx: CanvasRenderingContext2D, x: number, y: number): void {
  ctx.fillStyle = SHADOW;
  ctx.fillRect(x + 4, y + 14, 8, 2);
  ctx.fillRect(x + 3, y + 15, 10, 1);
}

// ESI 1: a soft red glow pulsing under the patient.
function aura(ctx: CanvasRenderingContext2D, x: number, y: number, frame: number): void {
  const big = frame % 4 < 2;
  ctx.fillStyle = big ? "rgba(255, 60, 70, 0.22)" : "rgba(255, 60, 70, 0.14)";
  const r = big ? 1 : 0;
  ctx.fillRect(x + 1 - r, y + 11 - r, 14 + r * 2, 5 + r);
  ctx.fillRect(x + 3 - r, y + 10 - r, 10 + r * 2, 7 + r * 2);
}

const BADGE_BOB = [0, 0, -1, -1];

export function drawPatient(ctx: CanvasRenderingContext2D, p: PatientEntity, frame: number): void {
  withAlpha(ctx, p.alpha, () => {
    const x = Math.round(p.x);
    const y = Math.round(p.y);
    if (p.state === "dead") {
      blit(ctx, sheetSprite(), x + 2, y);
      return;
    }
    const look = lookFor(p.id, "patient", { esi: p.esi });
    const phase = animPhase(p.id);
    if (p.state === "in_bed") {
      drawPatientInBed(ctx, p, x, y, frame, phase);
      return;
    }
    if (p.esi === 1) aura(ctx, x, y, frame);
    shadow(ctx, x, y);
    let top: number;
    if (p.state === "waiting" && !p.moving) {
      const a = sitAnim(frame, phase);
      top = y + 2 + a.bob;
      blit(ctx, personSprite(look, a.spec), x + 2, top);
    } else {
      const a = standAnim(p.facing, p.moving, frame, phase);
      top = y + a.bob;
      blit(ctx, personSprite(look, a.spec), x + 2, top);
    }
    drawEsiBadge(ctx, p.esi, x + 4, top - 9 + BADGE_BOB[(frame + phase) % 4]);
  });
}

function drawPatientInBed(
  ctx: CanvasRenderingContext2D,
  p: PatientEntity,
  x: number,
  y: number,
  frame: number,
  phase: number,
): void {
  const look = lookFor(p.id, "patient", { esi: p.esi });
  const spec: PoseSpec = {
    pose: "bed", facing: "down", legs: "idle", squash: false, slump: false,
    blink: (frame + phase) % 17 === 0 || (frame + phase) % 17 === 1,
  };
  blit(ctx, personSprite(look, spec), x, y);
  // ESI plate on the headboard
  ctx.fillStyle = ESI_RAMP[p.esi][1];
  ctx.fillRect(x + 5, y + 1, 6, 2);
  ctx.fillStyle = ESI_RAMP[p.esi][0];
  ctx.fillRect(x + 5, y + 1, 6, 1);

  // treatment progress across the footboard
  const progress = Math.max(0, Math.min(1, p.progress));
  ctx.fillStyle = OUTLINE;
  ctx.fillRect(x + 2, y + 21, 12, 3);
  ctx.fillStyle = "#4a4458";
  ctx.fillRect(x + 3, y + 22, 10, 1);
  const fill = Math.round(progress * 10);
  if (fill > 0) {
    ctx.fillStyle = p.waitingForCt ? "#9aa0b4" : p.covered ? GOOD : WARN;
    ctx.fillRect(x + 3, y + 22, fill, 1);
  }

  drawEsiBadge(ctx, p.esi, x + 4, y - 8 + BADGE_BOB[(frame + phase) % 4]);
  if (!p.covered) drawIcon(ctx, "alert", x + 12, y - 9 - (frame % 2), { variant: frame % 2 ? "dim" : undefined });
  if (p.waitingForCt) drawIcon(ctx, "ct", x - 6, y - 8 - (frame % 4 < 2 ? 0 : 1));
}

const STATUS_ALPHA: Partial<Record<StaffEntity["status"], number>> = {
  agency_ordered: 0.5,
  agency_left: 0.35,
  sick: 0.85,
};

export function drawStaff(ctx: CanvasRenderingContext2D, s: StaffEntity, frame: number): void {
  withAlpha(ctx, s.alpha * (STATUS_ALPHA[s.status] ?? 1), () => {
    const x = Math.round(s.x);
    const y = Math.round(s.y);
    const exhausted = s.fatigue >= 80;
    const phase = animPhase(s.id);
    const look = lookFor(s.id, s.role, { agency: s.agency, exhausted, sick: s.status === "sick" });

    if (s.status === "fainted") {
      ctx.fillStyle = SHADOW;
      ctx.fillRect(x, y + 13, 16, 2);
      const spec: PoseSpec = { pose: "lie", facing: "down", legs: "idle", squash: false, slump: false, blink: true };
      blit(ctx, personSprite(look, spec), x, y + 3);
      const spots = [[0, 0], [3, -2], [6, 0], [3, 1]];
      for (let i = 0; i < 3; i++) {
        const [dx, dy] = spots[(frame + i) % spots.length];
        drawIcon(ctx, i === 0 ? "star" : "spark", x - 1 + dx, y - 4 + dy);
      }
      return;
    }

    shadow(ctx, x, y);
    if (s.status === "resting") {
      const a = sitAnim(frame, phase, exhausted);
      const top = y + 2 + a.bob;
      blit(ctx, personSprite(look, a.spec), x + 2, top);
      drawIcon(ctx, "cup", x + 9, top + 9);
      // steam curls up from the cup
      ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
      const st = (frame + phase) % 3;
      ctx.fillRect(x + 11 + (st === 1 ? 1 : 0), top + 7 - st, 1, 1);
      ctx.fillRect(x + 12 - (st === 2 ? 1 : 0), top + 5 - st, 1, 1);
      if (s.fatigue > 60) drawIcon(ctx, "zz", x + 10, top - 6 - (frame % 4 < 2 ? 0 : 1));
      return;
    }

    const a = standAnim(s.facing, s.moving, frame, phase, exhausted);
    const top = y + a.bob;
    blit(ctx, personSprite(look, a.spec), x + 2, top);
    if (s.fatigue > 60) {
      // a drop slides down the side of the head and restarts
      const t = (frame + phase) % 4;
      const left = s.facing === "right";
      drawIcon(ctx, "sweat", left ? x : x + 12, top + 1 + t, {});
    }
  });
}

export function drawEffect(ctx: CanvasRenderingContext2D, e: Effect): void {
  drawEffectAt(ctx, e);
}
