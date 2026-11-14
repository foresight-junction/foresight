// Small outlined icons for effects and status markers. Shapes are drawn as fills; outlined() adds the
// dark 1 px border so they read on every floor colour.

import type { Esi } from "../../replay/types";
import { BAD, ESI_RAMP, GOLD, GOOD, METAL, OUTLINE, SWEAT, TEAL, WHITE } from "../palette";
import { GLYPHS } from "./font";
import { blit, cached, newCanvas, outlined, paintPixmap, pixmapSize, pixmapSprite, px, type Pal, type Pixmap } from "./pixmap";

export const ICON_PAL: Pal = {
  o: OUTLINE,
  w: WHITE,
  W: "#c8ccd8",
  k: "#3a3546",
  r: BAD,
  R: "#a8283a",
  g: GOOD,
  G: "#2f8a40",
  t: TEAL,
  a: "#f28c2c",
  A: "#b85e1c",
  y: GOLD[0],
  Y: GOLD[1],
  e: GOLD[2],
  b: "#4c8ee6",
  n: "#8a5a3a",
  N: "#a8744c",
  m: METAL[0],
  M: METAL[1],
  c: "#7a4a2a",
  s: SWEAT,
  z: "#e4ecff",
};

const FILLS = {
  skull: px(`
    .wwwww.
    wwwwwww
    wkkwkkw
    wkkwkkw
    wwwkwww
    .wwwww.
    .w.w.w.
  `),
  check: px(`
    ......gg
    .....ggG
    g...ggG.
    gg.ggG..
    GggggG..
    .GggG...
    ..GG....
  `),
  heart: px(`
    .rr.rr.
    rwrrrrr
    rrrrrrr
    .rrrrR.
    ..rrR..
    ...R...
  `),
  plus: px(`
    ..tt..
    ..tt..
    tttttt
    tttttt
    ..tt..
    ..tt..
  `),
  cross: px(`
    rr...rr
    rrr.rrr
    .rrrrr.
    ..rrr..
    .rrrrr.
    RRR.RRR
    RR...RR
  `),
  up: px(`
    ...a...
    ..aaa..
    .aaaaa.
    aaaaaaa
    ..aAa..
    ..aAa..
    ..aAa..
  `),
  star: px(`
    ...y...
    ..yyy..
    yyyeyyy
    .yyyyy.
    ..yyy..
    .yY.Yy.
    .Y...Y.
  `),
  spark: px(`
    .y.
    yey
    .y.
  `),
  coin: px(`
    .yeeyy.
    yeAAAyY
    yAyyyyY
    yAAAyyY
    yAyyyyY
    yyAAAyY
    .YYYYY.
  `),
  warning: px(`
    ....y....
    ...yky...
    ...yky...
    ..yykyy..
    .yyyyyyy.
    .yyykyyy.
    yyyyyyyyy
  `),
  ambulance: px(`
    ....rb.......
    .wwwwwwwwwwww
    wbbwwwwwwrwww
    wbbwwwwwrrrww
    wwwwwwwwwrwww
    RRRRRRRRRRRRR
    wwkkwwwwwkkww
    ..kk.....kk..
  `),
  door_out: px(`
    nnnnnn........
    nNNNNn........
    nNnnNn....g...
    nNNNNn....gg..
    nnnnyn.ggggggg
    nNNNNn....gg..
    nNnnNn....g...
    nNNNNn........
    nnnnnn........
  `),
  ct: px(`
    .mmmmm.
    mmkkkmm
    mkkkkkm
    mkkwkkm
    mmkwkmm
    .MmwmM.
    ..www..
  `),
  alert: px(`
    .rrr.
    rrwrr
    rrwrr
    rrwrr
    rrrrr
    rrwrr
    .rrr.
    ..r..
  `),
  zz: px(`
    zzzz...
    ..z....
    .z..zz.
    zzzz.z.
    .....zz
  `),
  cup: px(`
    wccw.
    wwwwW
    wwwwW
    .ww..
  `),
  sweat: px(`
    .s.
    sss
    ssw
    .s.
  `),
  ghost: px(`
    ..wwwww..
    .wwwwwww.
    wwkwwwkww
    wwkwwwkww
    wwwwwwwww
    wwwwkwwww
    Wwwwwwwww
    WWwwwwwWW
    W.WW.WW.W
  `),
  coin_mid: px(`
    .yey.
    yeAyY
    yAyyY
    yAAyY
    yAyyY
    yeAyY
    .YYY.
  `),
  coin_edge: px(`
    ye
    yY
    yY
    yY
    yY
    yY
    YY
  `),
  warning_big: px(`
    ......y......
    .....yyy.....
    .....yky.....
    ....yykyy....
    ....yykyY....
    ...yyykyyY...
    ...yyykyyY...
    ..yyyyyyyyY..
    ..yyyykyyyY..
    .yyyyyyyyyYY.
    YYYYYYYYYYYYY
  `),
};

export type IconKind = keyof typeof FILLS;
export const ICON_KINDS = Object.keys(FILLS) as IconKind[];

// Palette swaps for variants that share a shape.
export type IconVariant = "lights_alt" | "dim" | "clear" | "hot" | "green";

const VARIANTS: Record<IconVariant, Pal> = {
  lights_alt: { r: "#4c8ee6", b: BAD }, // ambulance roof lights blink
  dim: { r: "#8a2a34", w: "#e8b8bc", R: "#6a1a24" }, // blinking alert, off phase
  clear: { y: "#8fd8c4", Y: "#5cb4a2", k: "#2f8f86" }, // event over: calm teal triangle
  hot: { y: "#ff6a4a", Y: "#c8382a", k: WHITE }, // flashing warning, alternate phase
  green: { r: GOOD, R: "#2f8a40" }, // green heart
};

const iconMaps = new Map<IconKind, Pixmap>();

export function iconMap(kind: IconKind): Pixmap {
  let m = iconMaps.get(kind);
  if (!m) {
    m = outlined(FILLS[kind]);
    iconMaps.set(kind, m);
  }
  return m;
}

export function iconSize(kind: IconKind): { w: number; h: number } {
  return pixmapSize(iconMap(kind));
}

export function iconFill(kind: IconKind): Pixmap {
  return FILLS[kind];
}

// Draws an icon with its top-left at (x, y). `variant` picks a palette swap.
export function drawIcon(
  ctx: CanvasRenderingContext2D,
  kind: IconKind,
  x: number,
  y: number,
  opts: { variant?: IconVariant; flip?: boolean } = {},
): void {
  const pal = opts.variant ? { ...ICON_PAL, ...VARIANTS[opts.variant] } : ICON_PAL;
  const base = iconMap(kind);
  const map = opts.flip ? base.map((r) => [...r].reverse().join("")) : base;
  blit(ctx, pixmapSprite(`icon|${kind}|${opts.variant ?? ""}|${opts.flip ? 1 : 0}`, map, pal), x, y);
}

// Floating triage badge: a diamond in the ESI colour with the level number, 9 x 9.
const BADGE = outlined(
  px(`
    ...L...
    ..LMM..
    .LMMMM.
    LMMMMMD
    .MMMMD.
    ..MMD..
    ...D...
  `),
);

export function drawEsiBadge(ctx: CanvasRenderingContext2D, esi: Esi, x: number, y: number): void {
  const s = cached(`badge|${esi}`, () => {
    const [c, g] = newCanvas(9, 9);
    const [light, mid, dark] = ESI_RAMP[esi];
    paintPixmap(g, BADGE, { o: OUTLINE, L: light, M: mid, D: dark });
    g.fillStyle = esi === 3 || esi === 4 ? OUTLINE : WHITE;
    GLYPHS[String(esi)].forEach((row, gy) => {
      for (let gx = 0; gx < row.length; gx++) if (row[gx] === "#") g.fillRect(3 + gx, 2 + gy, 1, 1);
    });
    return c;
  });
  blit(ctx, s, x, y);
}

// White starburst for the first instant of a death, 11 x 11, centred on (cx, cy).
const BURST = px(`
  .....w.....
  .....w.....
  ..w..w..w..
  ...w.w.w...
  ....www....
  wwwwwwwwwww
  ....www....
  ...w.w.w...
  ..w..w..w..
  .....w.....
  .....w.....
`);

export function drawBurst(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
  blit(ctx, pixmapSprite("burst", BURST, { w: "#ffffff" }), cx - 5, cy - 5);
}
