// Pixel maps: rows of characters, one per pixel, coloured through a palette ("." is transparent).
// Each map is rendered once to an offscreen canvas and cached by key, so a frame only does drawImage.

export type Pixmap = readonly string[];
export type Pal = Record<string, string>;

export type Sprite = HTMLCanvasElement;

// Multi-line pixel map literal: one trimmed line per row, blank lines ignored.
export function px(src: string): Pixmap {
  return src
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
}

const cache = new Map<string, Sprite>();

export function newCanvas(w: number, h: number): [Sprite, CanvasRenderingContext2D] {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d");
  if (!ctx) throw new Error("2D canvas not supported");
  return [c, ctx];
}

// Build once per key; the builder only runs on a cache miss.
export function cached(key: string, build: () => Sprite): Sprite {
  let s = cache.get(key);
  if (!s) {
    s = build();
    cache.set(key, s);
  }
  return s;
}

export function cacheSize(): number {
  return cache.size;
}

export function pixmapSize(map: Pixmap): { w: number; h: number } {
  return { w: Math.max(0, ...map.map((r) => r.length)), h: map.length };
}

// Characters used by a map that the palette does not colour (empty when the map is valid).
export function missingColors(map: Pixmap, pal: Pal): string[] {
  const missing = new Set<string>();
  for (const row of map) for (const ch of row) if (ch !== "." && ch !== " " && !(ch in pal)) missing.add(ch);
  return [...missing];
}

export function paintPixmap(ctx: CanvasRenderingContext2D, map: Pixmap, pal: Pal, ox = 0, oy = 0): void {
  map.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) {
      const ch = row[x];
      if (ch === "." || ch === " ") continue;
      const color = pal[ch];
      if (!color) throw new Error(`pixmap colour '${ch}' missing from palette`);
      ctx.fillStyle = color;
      ctx.fillRect(ox + x, oy + y, 1, 1);
    }
  });
}

export function pixmapSprite(key: string, map: Pixmap, pal: Pal): Sprite {
  return cached(key, () => {
    const { w, h } = pixmapSize(map);
    const [c, ctx] = newCanvas(w, h);
    paintPixmap(ctx, map, pal);
    return c;
  });
}

export function mirror(map: Pixmap): string[] {
  return map.map((r) => [...r].reverse().join(""));
}

// Adds a 1 px outline ('o') around every filled pixel, growing the map by 1 on each side.
export function outlined(map: Pixmap): string[] {
  const { w, h } = pixmapSize(map);
  const filled = (x: number, y: number): boolean => {
    const ch = map[y]?.[x];
    return ch !== undefined && ch !== "." && ch !== " ";
  };
  const out: string[] = [];
  for (let y = -1; y <= h; y++) {
    let row = "";
    for (let x = -1; x <= w; x++) {
      if (filled(x, y)) row += map[y][x];
      else {
        let near = false;
        for (let dy = -1; dy <= 1 && !near; dy++) for (let dx = -1; dx <= 1; dx++) if (filled(x + dx, y + dy)) near = true;
        row += near ? "o" : ".";
      }
    }
    out.push(row);
  }
  return out;
}

// Pixel-by-pixel procedural sprite (tiles, CT): paint(x, y) returns a colour or null.
export function proceduralSprite(
  key: string,
  w: number,
  h: number,
  paint: (x: number, y: number) => string | null,
): Sprite {
  return cached(key, () => {
    const [c, ctx] = newCanvas(w, h);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const color = paint(x, y);
        if (!color) continue;
        ctx.fillStyle = color;
        ctx.fillRect(x, y, 1, 1);
      }
    }
    return c;
  });
}

// Small deterministic hash for per-tile / per-person variation (stable across frames).
export function hash(...parts: (string | number)[]): number {
  let h = 2166136261;
  for (const ch of parts.join("|")) {
    h ^= ch.charCodeAt(0);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function blit(ctx: CanvasRenderingContext2D, s: Sprite, x: number, y: number): void {
  ctx.drawImage(s, Math.round(x), Math.round(y));
}

// Run draw with globalAlpha multiplied by alpha, restoring it afterwards.
export function withAlpha(ctx: CanvasRenderingContext2D, alpha: number, draw: () => void): void {
  if (alpha <= 0) return;
  const prev = ctx.globalAlpha;
  ctx.globalAlpha = prev * Math.min(1, alpha);
  try {
    draw();
  } finally {
    ctx.globalAlpha = prev;
  }
}
