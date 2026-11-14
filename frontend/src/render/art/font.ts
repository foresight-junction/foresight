// Tiny 3x5 bitmap font (a few glyphs are wider) so text on the map stays pixel-crisp at any zoom.
// Lowercase is drawn as uppercase; unknown characters become "?".

import { cached, newCanvas, type Sprite } from "./pixmap";

export const FONT_HEIGHT = 5;

// "#" = ink. Every row of a glyph has the same width.
export const GLYPHS: Record<string, readonly string[]> = {
  A: [".#.", "#.#", "###", "#.#", "#.#"],
  B: ["##.", "#.#", "##.", "#.#", "##."],
  C: [".##", "#..", "#..", "#..", ".##"],
  D: ["##.", "#.#", "#.#", "#.#", "##."],
  E: ["###", "#..", "##.", "#..", "###"],
  F: ["###", "#..", "##.", "#..", "#.."],
  G: [".##", "#..", "#.#", "#.#", ".##"],
  H: ["#.#", "#.#", "###", "#.#", "#.#"],
  I: ["###", ".#.", ".#.", ".#.", "###"],
  J: ["..#", "..#", "..#", "#.#", ".#."],
  K: ["#.#", "#.#", "##.", "#.#", "#.#"],
  L: ["#..", "#..", "#..", "#..", "###"],
  M: ["#...#", "##.##", "#.#.#", "#...#", "#...#"],
  N: ["#..#", "##.#", "#.##", "#..#", "#..#"],
  O: [".#.", "#.#", "#.#", "#.#", ".#."],
  P: ["##.", "#.#", "##.", "#..", "#.."],
  Q: [".#.", "#.#", "#.#", "##.", ".##"],
  R: ["##.", "#.#", "##.", "#.#", "#.#"],
  S: [".##", "#..", ".#.", "..#", "##."],
  T: ["###", ".#.", ".#.", ".#.", ".#."],
  U: ["#.#", "#.#", "#.#", "#.#", "###"],
  V: ["#.#", "#.#", "#.#", "#.#", ".#."],
  W: ["#...#", "#...#", "#.#.#", "##.##", "#...#"],
  X: ["#.#", "#.#", ".#.", "#.#", "#.#"],
  Y: ["#.#", "#.#", ".#.", ".#.", ".#."],
  Z: ["###", "..#", ".#.", "#..", "###"],
  "0": ["###", "#.#", "#.#", "#.#", "###"],
  "1": [".#.", "##.", ".#.", ".#.", "###"],
  "2": ["##.", "..#", ".#.", "#..", "###"],
  "3": ["##.", "..#", ".#.", "..#", "##."],
  "4": ["#.#", "#.#", "###", "..#", "..#"],
  "5": ["###", "#..", "##.", "..#", "##."],
  "6": [".##", "#..", "###", "#.#", "###"],
  "7": ["###", "..#", ".#.", ".#.", ".#."],
  "8": ["###", "#.#", "###", "#.#", "###"],
  "9": ["###", "#.#", "###", "..#", "##."],
  "€": [".###", "#...", "###.", "#...", ".###"],
  "-": ["...", "...", "###", "...", "..."],
  "+": ["...", ".#.", "###", ".#.", "..."],
  "=": ["...", "###", "...", "###", "..."],
  "!": ["#", "#", "#", ".", "#"],
  "?": ["##.", "..#", ".#.", "...", ".#."],
  ".": [".", ".", ".", ".", "#"],
  ",": ["..", "..", "..", ".#", "#."],
  ":": [".", "#", ".", "#", "."],
  "'": ["#", "#", ".", ".", "."],
  "/": ["..#", "..#", ".#.", "#..", "#.."],
  "%": ["#.#", "..#", ".#.", "#..", "#.#"],
  "(": [".#", "#.", "#.", "#.", ".#"],
  ")": ["#.", ".#", ".#", ".#", "#."],
  "#": ["#.#", "###", "#.#", "###", "#.#"],
  "×": ["...", "#.#", ".#.", "#.#", "..."],
  " ": ["..", "..", "..", "..", ".."],
};

function glyph(ch: string): readonly string[] {
  return GLYPHS[ch.toUpperCase()] ?? GLYPHS["?"];
}

// Width in pixels of text drawn without an outline (1 px between glyphs).
export function measureText(text: string): number {
  let w = 0;
  for (const ch of text) w += glyph(ch)[0].length + 1;
  return Math.max(0, w - 1);
}

function textSprite(text: string, color: string, outline: string | undefined): Sprite {
  return cached(`text|${text}|${color}|${outline ?? ""}`, () => {
    const pad = outline ? 1 : 0;
    const [c, ctx] = newCanvas(measureText(text) + pad * 2 || 1, FONT_HEIGHT + pad * 2);
    const ink = (col: string, dx: number, dy: number): void => {
      ctx.fillStyle = col;
      let x = pad;
      for (const ch of text) {
        const g = glyph(ch);
        g.forEach((row, y) => {
          for (let i = 0; i < row.length; i++) if (row[i] === "#") ctx.fillRect(x + i + dx, pad + y + dy, 1, 1);
        });
        x += g[0].length + 1;
      }
    };
    if (outline) {
      for (const [dx, dy] of [[-1, 0], [1, 0], [0, -1], [0, 1], [-1, -1], [1, -1], [-1, 1], [1, 1]]) {
        ink(outline, dx, dy);
      }
    }
    ink(color, 0, 0);
    return c;
  });
}

// Draws text with its top-left glyph pixel at (x, y). With an outline colour, a 1 px border is added
// around every glyph (it sits outside (x, y), so layout is the same with or without it).
export function drawText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  color: string,
  outline?: string,
): void {
  if (!text) return;
  const pad = outline ? 1 : 0;
  ctx.drawImage(textSprite(text, color, outline), Math.round(x) - pad, Math.round(y) - pad);
}

// Same as drawText but centred horizontally on cx.
export function drawTextCentered(
  ctx: CanvasRenderingContext2D,
  text: string,
  cx: number,
  y: number,
  color: string,
  outline?: string,
): void {
  drawText(ctx, text, Math.round(cx - measureText(text) / 2), y, color, outline);
}
