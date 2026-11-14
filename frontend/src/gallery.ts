// Dev page (/gallery.html): every tile, prop, sprite state and effect, animated, for art review.
// Not part of the viewer build. Owner: agent C (sprites).

import type { Effect, EffectKind, Facing, PatientEntity, StaffEntity } from "./replay/frame";
import type { Esi, StaffStatus } from "./replay/types";
import { EFFECT_KINDS } from "./render/art/effects";
import { cacheSize } from "./render/art/pixmap";
import { TILE_KINDS, tileSprite } from "./render/art/tiles";
import { PAGE_BG } from "./render/palette";
import {
  drawBed,
  drawCt,
  drawEffect,
  drawEsiBadge,
  drawIcon,
  drawMonitor,
  drawPatient,
  drawProp,
  drawStaff,
  drawText,
  drawTile,
  drawWallFace,
  ICON_KINDS,
} from "./render/sprites";
import type { TileKind } from "./world/layout";

const W = 400;
const LABEL = "#e8e8f0";
const DIM = "#8a8aa0";

const canvas = document.getElementById("gallery") as HTMLCanvasElement;
const zoomSel = document.getElementById("zoom") as HTMLSelectElement;
const paused = document.getElementById("paused") as HTMLInputElement;
const stats = document.getElementById("stats") as HTMLElement;
const ctx = canvas.getContext("2d") as CanvasRenderingContext2D;

function patient(over: Partial<PatientEntity>): PatientEntity {
  return {
    kind: "patient", id: "P001", esi: 3, state: "waiting", bed: null, covered: true, waitingForCt: false,
    progress: 0, needsCt: false, moving: false, facing: "down", alpha: 1, x: 0, y: 0, ...over,
  };
}

function staff(over: Partial<StaffEntity>): StaffEntity {
  return {
    kind: "staff", id: "D1", role: "doctor", agency: false, location: "acute", status: "on_shift", fatigue: 20,
    moving: false, facing: "down", alpha: 1, x: 0, y: 0, ...over,
  };
}

function heading(text: string, y: number): void {
  drawText(ctx, text, 4, y, LABEL);
  ctx.fillStyle = "#2a2a3a";
  ctx.fillRect(4, y + 7, W - 8, 1);
}

function caption(text: string, x: number, y: number): void {
  drawText(ctx, text, x, y, DIM);
}

const FACINGS: Facing[] = ["down", "up", "left", "right"];

function drawAll(frame: number, t: number): number {
  let y = 4;

  // ---- tiles: 4 variants of each kind in a 2x2 block
  heading("TILES (4 VARIANTS EACH)", y);
  y += 12;
  TILE_KINDS.forEach((kind, i) => {
    const x = 4 + i * 38;
    for (let v = 0; v < 4; v++) ctx.drawImage(tileSprite(kind, v), x + (v % 2) * 16, y + Math.floor(v / 2) * 16);
    caption(kind.replace("_floor", "").replace("_", " ").toUpperCase(), x, y + 34);
  });
  y += 46;

  // ---- 3/4 walls: cap row, 2-row face, door, floor
  heading("WALLS 3/4: CAP + FACE (32 AND 16)", y);
  y += 12;
  for (let c = 0; c < 10; c++) {
    const x = 4 + c * 16;
    drawTile(ctx, c === 6 ? "door" : "wall", x, y);
    if (c !== 6) drawWallFace(ctx, x, y + 16);
    else for (let r = 1; r < 3; r++) drawTile(ctx, "floor", x, y + r * 16);
    drawTile(ctx, "acute_floor", x, y + 48);
  }
  for (let c = 0; c < 8; c++) {
    const x = 180 + c * 16;
    drawTile(ctx, "wall", x, y);
    drawWallFace(ctx, x, y + 16, 16);
    drawTile(ctx, c < 4 ? "waiting_floor" : "rest_floor", x, y + 32);
    drawTile(ctx, c < 4 ? "waiting_floor" : "rest_floor", x, y + 48);
  }
  drawProp(ctx, "plant", 180, y + 32);
  drawProp(ctx, "sofa", 244, y + 34);
  drawProp(ctx, "coffee", 292, y + 30);
  y += 70;

  // ---- beds and CT
  heading("BEDS + CT", y);
  y += 22;
  const beds: [string, PatientEntity | null][] = [
    ["EMPTY", null],
    ["OK", patient({ id: "P010", esi: 2, state: "in_bed", progress: 0.6 })],
    ["ALONE", patient({ id: "P011", esi: 1, state: "in_bed", covered: false, progress: 0.3 })],
    ["CT", patient({ id: "P012", esi: 3, state: "in_bed", waitingForCt: true, progress: 0.5 })],
    ["95%", patient({ id: "P013", esi: 5, state: "in_bed", progress: 0.95 })],
    ["DEAD", patient({ id: "P014", esi: 1, state: "dead", alpha: 0.4 + 0.6 * Math.abs(Math.sin(t / 1500)) })],
  ];
  beds.forEach(([name, p], i) => {
    const x = 8 + i * 30;
    for (let r = 0; r < 2; r++) drawTile(ctx, "acute_floor", x, y + r * 16);
    drawBed(ctx, x, y, !!p && p.state !== "dead");
    if (p) drawPatient(ctx, { ...p, x, y }, frame);
    caption(name, x - 2, y + 28);
  });
  for (let r = 0; r < 2; r++) for (let c = 0; c < 6; c++) drawTile(ctx, "ct_floor", 200 + c * 16, y + r * 16 - 4);
  drawCt(ctx, 204, y - 6, true, frame);
  drawCt(ctx, 250, y - 6, false, frame);
  caption("CT OK", 206, y + 28);
  caption("CT BROKEN", 248, y + 28);
  drawMonitor(ctx, 300, y + 4, frame, false);
  drawMonitor(ctx, 312, y + 4, frame, true);
  caption("MONITORS", 296, y + 28);
  y += 40;

  // ---- patients: one row per ESI
  heading("PATIENTS: IDLE, WALK DOWN UP LEFT RIGHT, WAITING (SITTING)", y);
  y += 22;
  for (let esi = 1 as Esi; esi <= 5; esi = (esi + 1) as Esi) {
    caption(`ESI ${esi}`, 4, y + 6);
    const cols: Partial<PatientEntity>[] = [
      { state: "arriving" },
      ...FACINGS.map((facing) => ({ state: "to_bed" as const, moving: true, facing })),
      { state: "waiting" },
      { state: "leaving", alpha: 0.5 },
    ];
    cols.forEach((c, i) => drawPatient(ctx, patient({ id: `P${esi}${i}`, esi, ...c, x: 36 + i * 20, y }), frame));
    y += 26;
  }
  caption("LAST COLUMN: LEAVING AT ALPHA 0.5", 36, y - 6);
  y += 6;

  // ---- staff
  heading("STAFF: IDLE, WALK X4, FATIGUE 70 / 85, RESTING 30 / 75, FAINTED, SICK, ORDERED", y);
  y += 22;
  const kinds: [string, Partial<StaffEntity>][] = [
    ["DOCTOR", { role: "doctor" }],
    ["NURSE", { role: "nurse", id: "N3" }],
    ["AGENCY D", { role: "doctor", agency: true, id: "AD1" }],
    ["AGENCY N", { role: "nurse", agency: true, id: "AN2" }],
  ];
  for (const [name, base] of kinds) {
    caption(name, 4, y + 6);
    const cols: Partial<StaffEntity>[] = [
      {},
      ...FACINGS.map((facing) => ({ moving: true, facing })),
      { fatigue: 70 },
      { fatigue: 85 },
      { status: "resting" as StaffStatus, fatigue: 30 },
      { status: "resting" as StaffStatus, fatigue: 75 },
      { status: "fainted" as StaffStatus, fatigue: 90 },
      { status: "sick" as StaffStatus },
      { status: "agency_ordered" as StaffStatus },
    ];
    cols.forEach((c, i) => drawStaff(ctx, staff({ ...base, ...c, x: 44 + i * 22, y }), frame));
    y += 26;
  }
  y += 4;

  // ---- effects: animated loop and a static strip
  heading("EFFECTS (LOOPING AGE 0-1, THEN AGE 0.05 / 0.3 / 0.7)", y);
  y += 44;
  const texts: Partial<Record<EffectKind, string>> = {
    spend: "-€900",
    rejected: "NO BED",
    death: "P042",
    event_start: "FLU WAVE",
    event_end: "CT FIXED",
    diverted: "DIVERT",
    upgrade: "ESI 2",
  };
  const loopAge = (t % 2000) / 2000;
  EFFECT_KINDS.forEach((kind, i) => {
    const x = 4 + i * 33;
    drawTile(ctx, "floor", x + 8, y);
    const fx: Effect = { kind, age: loopAge, text: texts[kind], x: x + 8, y };
    drawEffect(ctx, fx);
    caption(kind.replace("_", " ").toUpperCase().slice(0, 8), x, y + 20);
  });
  y += 50;
  EFFECT_KINDS.forEach((kind, i) => {
    const x = 4 + i * 33;
    [0.05, 0.3, 0.7].forEach((age, j) => drawEffect(ctx, { kind, age, x: x + 8, y: y + j * 30 }));
  });
  y += 84;

  // ---- icons and badges
  heading("ICONS + ESI BADGES", y);
  y += 12;
  let ix = 4;
  for (const kind of ICON_KINDS) {
    drawIcon(ctx, kind, ix, y);
    ix += 18;
  }
  for (let esi = 1 as Esi; esi <= 5; esi = (esi + 1) as Esi) drawEsiBadge(ctx, esi, 4 + (esi - 1) * 12, y + 20);
  drawIcon(ctx, "alert", 70, y + 20, { variant: "dim" });
  drawIcon(ctx, "warning_big", 82, y + 18, { variant: "hot" });
  drawIcon(ctx, "warning", 100, y + 20, { variant: "clear" });
  drawIcon(ctx, "heart", 114, y + 20, { variant: "green" });
  y += 36;

  // ---- props
  heading("PROPS", y);
  y += 12;
  drawProp(ctx, "chair", 4, y);
  drawProp(ctx, "chair", 20, y);
  drawProp(ctx, "plant", 40, y);
  drawProp(ctx, "desk", 60, y);
  drawProp(ctx, "sofa", 100, y);
  drawProp(ctx, "coffee", 140, y);
  y += 22;

  // ---- font
  heading("FONT 3X5", y);
  y += 12;
  drawText(ctx, "ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789", 4, y, LABEL);
  drawText(ctx, "€ - + = ! ? . , : ' / % ( ) # ×  -€900 +12 P042 DIED", 4, y + 8, LABEL);
  drawText(ctx, "OUTLINED -€900", 4, y + 18, "#f6d04a", "#2a2233");
  drawText(ctx, "REJECTED: NO BED", 70, y + 18, "#ff9a9a", "#2a2233");
  y += 30;

  // ---- a tiny scene
  heading("SCENE", y);
  y += 12;
  drawScene(4, y, frame, t);
  y += 8 * 16 + 4;
  return y;
}

function drawScene(ox: number, oy: number, frame: number, t: number): void {
  const cols = 22;
  const rows = 8;
  const tile = (c: number, r: number): TileKind => {
    if (r === 0) return c === 15 ? "door" : "wall";
    if (c < 6) return "waiting_floor";
    if (c >= 18) return "ct_floor";
    return "acute_floor";
  };
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const x = ox + c * 16;
      const y = oy + r * 16;
      const k = tile(c, r);
      if (r >= 1 && r <= 2 && tile(c, 0) === "wall") {
        if (r === 1) drawWallFace(ctx, x, y);
        continue;
      }
      drawTile(ctx, k, x, y);
    }
  }
  for (let i = 0; i < 4; i++) drawProp(ctx, "chair", ox + 8 + i * 16, oy + 3 * 16);
  drawProp(ctx, "plant", ox, oy + 3 * 16);
  const bedPatients = [
    patient({ id: "P101", esi: 2, state: "in_bed", progress: ((t / 8000) % 1) }),
    patient({ id: "P102", esi: 1, state: "in_bed", covered: false, progress: 0.2 }),
    null,
    patient({ id: "P103", esi: 4, state: "in_bed", waitingForCt: true, progress: 0.4 }),
  ];
  bedPatients.forEach((p, i) => {
    const x = ox + (7 + i * 2) * 16;
    const y = oy + 3 * 16;
    drawBed(ctx, x, y, !!p);
    if (p) drawPatient(ctx, { ...p, x, y }, frame);
  });
  drawCt(ctx, ox + 18 * 16 + 8, oy + 3 * 16, Math.floor(t / 6000) % 2 === 0, frame);

  // people walking a loop, y-sorted like the renderer does
  const span = 9 * 16;
  const walker = (speed: number, row: number, start: number) => {
    const d = ((t / 1000) * speed + start) % (span * 2);
    const forward = d < span;
    return { x: ox + 6 * 16 + (forward ? d : span * 2 - d), y: oy + row * 16, facing: (forward ? "right" : "left") as Facing };
  };
  const people: (PatientEntity | StaffEntity)[] = [
    staff({ id: "D2", moving: true, ...walker(24, 5, 0) }),
    staff({ id: "N4", role: "nurse", moving: true, fatigue: 70, ...walker(18, 6, 60) }),
    staff({ id: "AN1", role: "nurse", agency: true, moving: true, ...walker(30, 6, 130) }),
    patient({ id: "P120", esi: 3, state: "to_bed", moving: true, ...walker(14, 5, 200) }),
    patient({ id: "P121", esi: 5, x: ox + 1 * 16, y: oy + 3 * 16 }),
    patient({ id: "P122", esi: 1, x: ox + 2 * 16, y: oy + 3 * 16 }),
    patient({ id: "P123", esi: 4, x: ox + 3 * 16, y: oy + 3 * 16 }),
    patient({ id: "P124", esi: 2, state: "arriving", x: ox + 2 * 16, y: oy + 5 * 16 }),
    staff({ id: "N7", role: "nurse", status: "fainted", fatigue: 92, x: ox + 1 * 16, y: oy + 6 * 16 }),
  ];
  people.sort((a, b) => a.y - b.y);
  for (const e of people) {
    if (e.kind === "patient") drawPatient(ctx, e, frame);
    else drawStaff(ctx, e, frame);
  }
  const cycle = (t % 3000) / 3000;
  drawEffect(ctx, { kind: "spend", age: cycle, text: "-€900", x: ox + 13 * 16, y: oy + 4 * 16 });
  drawEffect(ctx, { kind: "discharged", age: (cycle + 0.5) % 1, x: ox + 7 * 16, y: oy + 3 * 16 });
}

let height = 900;

function render(now: number): void {
  const zoom = Number(zoomSel.value);
  if (canvas.width !== W * zoom || canvas.height !== height * zoom) {
    canvas.width = W * zoom;
    canvas.height = height * zoom;
  }
  ctx.setTransform(zoom, 0, 0, zoom, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = PAGE_BG;
  ctx.fillRect(0, 0, W, height);
  const t = paused.checked ? 0 : now;
  const used = drawAll(Math.floor(t / 250), t);
  if (used !== height) height = used;
  stats.textContent = `cached sprites: ${cacheSize()}`;
  requestAnimationFrame(render);
}

requestAnimationFrame(render);
