// Beds, the CT scanner and small props (chair, plant, desk, sofa, coffee machine, vitals monitor).

import { BAD, GOOD, METAL, MINT, OUTLINE, SHEET, SMOKE, STAR, shade } from "../palette";
import { blit, pixmapSprite, proceduralSprite, px, type Pal, type Pixmap } from "./pixmap";

// ---------------------------------------------------------------- bed (16 x 24, head at the top)

export const BED_PAL: Pal = {
  o: METAL[2],
  m: METAL[0],
  h: "#3f8f88",
  H: "#62b4aa",
  w: SHEET[0],
  W: SHEET[1],
  p: "#ffffff",
  P: "#c9cfdc",
  b: MINT[0],
  B: MINT[1],
  n: "#bfeadc",
  k: "#3a3546",
};

const BED_TOP = px(`
  ..oooooooooooo..
  .ohHHHHHHHHHHho.
  .ohhhhhhhhhhhho.
  .oooooooooooooo.
  .omwwPPPPPPwwmo.
  .omwPppppppPwmo.
  .omwPppppppPwmo.
  .omwWPPPPPPWwmo.
  .omwwwwwwwwwwmo.
`);

const BED_EMPTY_BOTTOM = px(`
  .omwwwwwwwwwwmo.
  .omwwwwwwwwwwmo.
  .omWwwwwwwwwwmo.
  .omwwwwwwwwwwmo.
  .omwwwwwwwwwwmo.
  .omWwwwwwwwwwmo.
  .omwwwwwwwwwwmo.
  .omWWWWWWWWWWmo.
  .ombbbbbbbbbbmo.
  .ombnnbbbbnnbmo.
  .ombbbbbbbbbbmo.
  .omBBBBBBBBBBmo.
  .oooooooooooooo.
  .ok..........ko.
  ................
`);

const BED_OCCUPIED_BOTTOM = px(`
  .omwwwwwwwwwwmo.
  .omwwwwwwwwwwmo.
  .omWWWWWWWWWWmo.
  .ombbbbbbbbbbmo.
  .ombbbbnnbbbbmo.
  .omBbbbnnbbbBmo.
  .omBbbbnnbbbBmo.
  .omBbbbnnbbbBmo.
  .omBbbnbbnbbBmo.
  .omBbbnbbnbbBmo.
  .omBbbnbbnbbBmo.
  .omBBBBBBBBBBmo.
  .oooooooooooooo.
  .ok..........ko.
  ................
`);

export const BED_EMPTY: Pixmap = [...BED_TOP, ...BED_EMPTY_BOTTOM];
export const BED_OCCUPIED: Pixmap = [...BED_TOP, ...BED_OCCUPIED_BOTTOM];

export function drawBedAt(ctx: CanvasRenderingContext2D, x: number, y: number, occupied: boolean): void {
  const s = occupied
    ? pixmapSprite("bed|occupied", BED_OCCUPIED, BED_PAL)
    : pixmapSprite("bed|empty", BED_EMPTY, BED_PAL);
  blit(ctx, s, x, y);
}

// ---------------------------------------------------------------- CT scanner (32 x 32)

const CT = {
  outline: OUTLINE,
  body: "#efece2",
  bodyLit: "#fbf9f2",
  bodyShade: "#cfd0d6",
  bodyDark: "#a9adbb",
  ring: "#3fb6a8",
  ringShade: "#2f8f86",
  rim: "#6a6f82",
  bore: "#3a3848",
  boreDeep: "#262433",
  pad: SHEET[0],
  padShade: SHEET[1],
  base: METAL[1],
  baseDark: METAL[2],
  tape: "#f2cc3a",
  tapeDark: "#2a2233",
};

function ctPaint(broken: boolean) {
  return (x: number, y: number): string | null => {
    const cx = 16;
    const cy = 10.5;
    const d = Math.hypot(x + 0.5 - cx, y + 0.5 - cy);
    // patient table: in front of the gantry and sliding into the bore
    const onPad = x >= 12 && x <= 19 && y >= 9 && y <= 26;
    if (onPad && y >= 19) {
      if (x === 12 || x === 19 || y === 26) return CT.outline;
      if (y === 25) return CT.padShade;
      return x === 13 ? CT.padShade : CT.pad;
    }
    if (x >= 14 && x <= 17 && y >= 27 && y <= 30) return x === 14 || x === 17 || y === 30 ? CT.outline : CT.base;
    if (x >= 11 && x <= 20 && y === 31) return CT.baseDark;
    // gantry housing, rounded box
    const hx = Math.min(x - 2, 29 - x);
    const hy = Math.min(y, 20 - y);
    if (hx < 0 || hy < 0 || hx + hy < 2) return null;
    if (hx === 0 || hy === 0 || hx + hy === 2) return CT.outline;
    if (d < 4.6) {
      if (onPad && x > 12 && x < 19) return y < 13 ? CT.padShade : CT.pad;
      return d < 3.2 ? CT.boreDeep : CT.bore;
    }
    if (d < 5.6) return CT.rim;
    if (d >= 7.6 && d < 8.6) return y > cy ? CT.ringShade : CT.ring;
    if (broken && y >= 17 && y <= 18) return Math.floor((x + y) / 2) % 2 ? CT.tape : CT.tapeDark;
    if (y >= 18) return CT.bodyDark;
    if (y === 1 || hx === 1) return CT.bodyLit;
    return d < 7.6 && y > cy ? CT.bodyShade : CT.body;
  };
}

export const CT_LIGHT = { x: 25, y: 3 }; // status lamp, top-right of the gantry

export function drawCtAt(ctx: CanvasRenderingContext2D, x: number, y: number, working: boolean, frame: number): void {
  const base = proceduralSprite(`ct|${working ? "ok" : "broken"}`, 32, 32, ctPaint(!working));
  ctx.fillStyle = "rgba(20, 16, 32, 0.22)";
  ctx.fillRect(Math.round(x) + 3, Math.round(y) + 21, 26, 2);
  ctx.fillRect(Math.round(x) + 11, Math.round(y) + 31, 10, 1);
  blit(ctx, base, x, y);
  const lx = Math.round(x) + CT_LIGHT.x;
  const ly = Math.round(y) + CT_LIGHT.y;
  ctx.fillStyle = OUTLINE;
  ctx.fillRect(lx - 1, ly - 1, 4, 4);
  if (working) {
    ctx.fillStyle = frame % 8 < 6 ? GOOD : shade(GOOD, -0.35);
    ctx.fillRect(lx, ly, 2, 2);
    return;
  }
  const on = frame % 2 === 0;
  ctx.fillStyle = on ? BAD : shade(BAD, -0.55);
  ctx.fillRect(lx, ly, 2, 2);
  if (on) {
    ctx.fillStyle = "rgba(232, 72, 79, 0.35)";
    ctx.fillRect(lx - 2, ly - 2, 6, 1);
    ctx.fillRect(lx - 2, ly + 3, 6, 1);
    ctx.fillRect(lx - 2, ly - 1, 1, 4);
    ctx.fillRect(lx + 3, ly - 1, 1, 4);
  }
  drawSmoke(ctx, Math.round(x) + 8, Math.round(y) + 1, frame);
  drawSmoke(ctx, Math.round(x) + 21, Math.round(y) + 2, frame + 3);
  drawSparks(ctx, Math.round(x) + 16, Math.round(y) + 11, frame);
}

// Three puffs rising and growing over a 6-frame loop.
function drawSmoke(ctx: CanvasRenderingContext2D, x: number, y: number, frame: number): void {
  for (let i = 0; i < 3; i++) {
    const t = (frame + i * 2) % 6;
    const size = 2 + Math.floor(t / 2);
    const px0 = x + (t % 2 === 0 ? 0 : 1) - Math.floor(size / 2) + (i - 1);
    const py0 = y - t * 2 - size;
    ctx.fillStyle = t > 3 ? SMOKE[1] : SMOKE[0];
    ctx.fillRect(px0, py0 + 1, size, size - 1);
    ctx.fillRect(px0 + 1, py0, size - 2 > 0 ? size - 2 : 1, 1);
  }
}

const SPARK_SPOTS = [
  [-6, -3], [5, -5], [-3, 5], [6, 3], [0, -7], [-7, 2],
];

function drawSparks(ctx: CanvasRenderingContext2D, cx: number, cy: number, frame: number): void {
  const a = SPARK_SPOTS[frame % SPARK_SPOTS.length];
  const b = SPARK_SPOTS[(frame * 5 + 2) % SPARK_SPOTS.length];
  for (const [dx, dy] of [a, b]) {
    ctx.fillStyle = STAR;
    ctx.fillRect(cx + dx, cy + dy, 1, 1);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(cx + dx - 1, cy + dy, 1, 1);
    ctx.fillRect(cx + dx + 1, cy + dy, 1, 1);
    ctx.fillRect(cx + dx, cy + dy - 1, 1, 1);
    ctx.fillRect(cx + dx, cy + dy + 1, 1, 1);
  }
}

// ---------------------------------------------------------------- props

const PROP_PAL: Pal = {
  o: OUTLINE,
  T: "#2f8f86",
  t: "#5cbcb0",
  S: "#3fa094",
  s: "#7ad2c6",
  m: METAL[1],
  M: METAL[0],
  G: "#3e8a4a",
  g: "#66b85a",
  l: "#9ad67a",
  P: "#a45a3a",
  p: "#cf7a52",
  q: "#e89a6c",
  w: "#b07a50",
  W: "#8a5a3a",
  v: "#d6a676",
  d: "#3a3546",
  b: "#6cc4e8",
  B: "#3a86b0",
  r: "#d86a4a",
  R: "#a8483a",
  c: "#f4ecdc",
  k: "#5a3a2a",
  e: GOOD,
  x: BAD,
};

export const CHAIR = px(`
  ................
  ................
  ...oooooooooo...
  ...oTTTTTTTTo...
  ...oTttttttTo...
  ...oTttttttTo...
  ...oTttttttTo...
  ...oTTTTTTTTo...
  ..oooooooooooo..
  ..oSssssssssSo..
  ..oSssssssssSo..
  ..oSSSSSSSSSSo..
  ..oooooooooooo..
  ...om......mo...
  ...oo......oo...
  ................
`);

export const PLANT = px(`
  ......oo........
  .....olgo..oo...
  ..oo.oggGooglo..
  .olgooGggGoggo..
  .oggGoGgGoGgGo..
  ..oGggGgGgggo...
  ...ooGgggGgoo...
  ..olgGgGgGGgo...
  ...oooGgGooo....
  ....oooooooo....
  ....oqqqqqqo....
  ....oppppppo....
  .....oppPPo.....
  .....oppPPo.....
  ......oooo......
  ................
`);

export const DESK = px(`
  ................................
  ..........oooooooo..............
  ..........obbbbbbo..............
  ..........obBBBBbo..............
  ..........oooooooo..............
  oooooooooooo.oo.oooooooooooooooo
  ovvvvvvvvvvvvvvvvvvvvvvvvvvvvvvo
  owwwwwwwwwwwwwwwwwwwwwwwwwwwwwwo
  oooooooooooooooooooooooooooooooo
  oWwwwwwwwwwwwwwwwwwwwwwwwwwwwwWo
  oWwwwwwwwwwwwwwwwwwwwwwwwwwwwwWo
  oTttttttttttttttttttttttttttttTo
  oTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTo
  oWwwwwwwwwwwwwwwwwwwwwwwwwwwwwWo
  oWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWo
  oooooooooooooooooooooooooooooooo
`);

export const SOFA = px(`
  ................................
  ..oooooooooooooooooooooooooooo..
  .oRrrrrrrrrrrrrrrrrrrrrrrrrrrRo.
  .oRqqqqqqqqqqqqRRqqqqqqqqqqqqRo.
  .oRrrrrrrrrrrrrRRrrrrrrrrrrrrRo.
  .oRRRRRRRRRRRRRRRRRRRRRRRRRRRRo.
  oooooooooooooooooooooooooooooooo
  oRRoqqqqqqqqqqqooqqqqqqqqqqqoRRo
  oRrorrrrrrrrrrroorrrrrrrrrrrorRo
  oRrorrrrrrrrrrroorrrrrrrrrrrorRo
  oRroRRRRRRRRRRRooRRRRRRRRRRRorRo
  oRRooooooooooooooooooooooooooRRo
  oRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRo
  oooooooooooooooooooooooooooooooo
  .ok..........................ko.
  ................................
`);

export const COFFEE_MACHINE = px(`
  ................
  ...oooooooooo...
  ...oddddddddo...
  ...odbbbbbbdo...
  ...odbeebbbdo...
  ...oddddddddo...
  ...oMMMMMMMMo...
  ...oMooooooMo...
  ...oMo....oMo...
  ...oMo.oo.oMo...
  ...oMo.co.oMo...
  ...oMoooooomo...
  ...oMMMMMMMMo...
  ...ommmmmmmmo...
  ...oooooooooo...
  ................
`);

export const MONITOR = px(`
  oooooooo
  oddddddo
  oddddddo
  oddddddo
  oddddddo
  oooooooo
  ...om...
  ...om...
  ..omMo..
  ..oooo..
`);

export function drawProp(
  ctx: CanvasRenderingContext2D,
  name: "chair" | "plant" | "desk" | "sofa" | "coffee",
  x: number,
  y: number,
): void {
  const map = { chair: CHAIR, plant: PLANT, desk: DESK, sofa: SOFA, coffee: COFFEE_MACHINE }[name];
  blit(ctx, pixmapSprite(`prop|${name}`, map, PROP_PAL), x, y);
}

// Bedside vitals monitor (8 x 10) with a scrolling heartbeat; alarm turns the trace red and blinking.
export function drawMonitorAt(ctx: CanvasRenderingContext2D, x: number, y: number, frame: number, alarm: boolean): void {
  blit(ctx, pixmapSprite("prop|monitor", MONITOR, PROP_PAL), x, y);
  if (alarm && frame % 2 === 1) return;
  ctx.fillStyle = alarm ? BAD : GOOD;
  const ox = Math.round(x) + 1;
  const oy = Math.round(y) + 1;
  // flat line with one beat (up, down) sweeping across
  const beat = frame % 8;
  for (let i = 0; i < 6; i++) ctx.fillRect(ox + i, oy + (i === beat ? 0 : i === beat + 1 ? 3 : 2), 1, 1);
}

export const PROP_PALETTE = PROP_PAL;
