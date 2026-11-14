// Tiny pixel particle system: square particles at integer positions, simple gravity and drag.
// Purely cosmetic, so it uses Math.random. Owner: agent B (map + renderer).

export interface Particle {
  x: number;
  y: number;
  vx: number; // map px per second
  vy: number;
  gravity: number; // px / s^2
  drag: number; // fraction of velocity kept per second (0..1)
  life: number; // seconds left
  maxLife: number;
  size: number; // 1 or 2 map px
  colors: string[]; // picked by remaining life, first = young
}

export type Burst = "dust" | "sparkle" | "blood" | "coins" | "sparks" | "arrival" | "upgrade" | "faint" | "admit";

const MAX = 700;

const rand = (a: number, b: number): number => a + Math.random() * (b - a);

export class Particles {
  private list: Particle[] = [];

  get count(): number {
    return this.list.length;
  }

  clear(): void {
    this.list.length = 0;
  }

  emit(kind: Burst, x: number, y: number): void {
    switch (kind) {
      case "dust":
        for (let i = 0; i < 4; i++) {
          this.add(x + rand(-3, 3), y, rand(-14, 14), rand(-10, -2), 0, 0.05, rand(0.25, 0.45), 1, ["#e6dccb", "#c9bea8"]);
        }
        break;
      case "sparkle":
        for (let i = 0; i < 14; i++) {
          const a = rand(0, Math.PI * 2);
          const s = rand(10, 34);
          this.add(x, y, Math.cos(a) * s, Math.sin(a) * s - 20, 30, 0.2, rand(0.6, 1.1), i % 4 === 0 ? 2 : 1,
            ["#ffffff", "#b6f5c4", "#5cc878", "#2f8f5b"]);
        }
        break;
      case "blood":
        for (let i = 0; i < 22; i++) {
          const a = rand(0, Math.PI * 2);
          const s = rand(20, 60);
          this.add(x, y, Math.cos(a) * s, Math.sin(a) * s - 15, 90, 0.08, rand(0.5, 0.9), i % 3 === 0 ? 2 : 1,
            ["#ff8a8a", "#e05a5a", "#b23a3a", "#6a1a1a"]);
        }
        break;
      case "coins":
        for (let i = 0; i < 8; i++) {
          this.add(x + rand(-4, 4), y, rand(-22, 22), rand(-70, -40), 160, 0.6, rand(0.7, 1.0), 2,
            ["#fff2a8", "#f2c14e", "#c8952a"]);
        }
        break;
      case "sparks":
        for (let i = 0; i < 5; i++) {
          this.add(x + rand(-2, 2), y, rand(-40, 40), rand(-60, -15), 140, 0.3, rand(0.2, 0.45), 1,
            ["#ffffff", "#fff2a8", "#f08c3a", "#b23a3a"]);
        }
        break;
      case "arrival":
        for (let i = 0; i < 8; i++) {
          this.add(x + rand(-5, 5), y + rand(-2, 2), rand(-16, 16), rand(-14, 0), 0, 0.05, rand(0.3, 0.6), 1,
            ["#ffffff", "#9ad8c8", "#76bfae"]);
        }
        break;
      case "admit":
        for (let i = 0; i < 8; i++) {
          this.add(x + rand(-6, 6), y + rand(0, 6), 0, rand(-26, -12), 0, 0.4, rand(0.4, 0.7), 1,
            ["#ffffff", "#9ad8c8", "#3aa7a3"]);
        }
        break;
      case "upgrade":
        for (let i = 0; i < 10; i++) {
          this.add(x + rand(-5, 5), y + rand(-2, 4), rand(-6, 6), rand(-34, -16), 0, 0.3, rand(0.4, 0.8), 1,
            ["#ffe0b0", "#f08c3a", "#b25a1a"]);
        }
        break;
      case "faint":
        for (let i = 0; i < 6; i++) {
          const a = (i / 6) * Math.PI * 2;
          this.add(x + Math.cos(a) * 5, y + Math.sin(a) * 2, Math.cos(a) * 10, -6, 0, 0.3, 0.9, 1,
            ["#ffffff", "#bcd0ff", "#6f8fd8"]);
        }
        break;
    }
  }

  update(dtSec: number): void {
    const dt = Math.max(0, Math.min(0.1, dtSec));
    let w = 0;
    for (const p of this.list) {
      p.life -= dt;
      if (p.life <= 0) continue;
      const keep = Math.pow(p.drag, dt);
      p.vx *= keep;
      p.vy = p.vy * keep + p.gravity * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      this.list[w++] = p;
    }
    this.list.length = w;
  }

  draw(ctx: CanvasRenderingContext2D): void {
    for (const p of this.list) {
      const t = 1 - p.life / p.maxLife;
      ctx.fillStyle = p.colors[Math.min(p.colors.length - 1, Math.floor(t * p.colors.length))];
      ctx.fillRect(Math.round(p.x), Math.round(p.y), p.size, p.size);
    }
  }

  private add(x: number, y: number, vx: number, vy: number, gravity: number, drag: number, life: number,
    size: number, colors: string[]): void {
    if (this.list.length >= MAX) this.list.shift();
    this.list.push({ x, y, vx, vy, gravity, drag, life, maxLife: life, size, colors });
  }
}
