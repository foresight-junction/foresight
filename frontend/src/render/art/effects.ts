// Floating effect popups: an icon (and optional text) that rises and fades as age goes 0 -> 1.
// Each kind has its own bit of motion so events read at a glance during fast playback.

import type { Effect, EffectKind } from "../../replay/frame";
import { GOLD, OUTLINE, WHITE } from "../palette";
import { drawTextCentered, FONT_HEIGHT } from "./font";
import { drawBurst, drawIcon, iconSize, type IconKind, type IconVariant } from "./icons";
import { blit, proceduralSprite, withAlpha } from "./pixmap";

const ICON_FOR: Record<EffectKind, IconKind> = {
  arrival: "ambulance",
  admitted: "plus",
  discharged: "heart",
  death: "ghost",
  left: "door_out",
  diverted: "ambulance",
  upgrade: "up",
  faint: "star",
  spend: "coin",
  rejected: "cross",
  event_start: "warning_big",
  event_end: "warning",
};

const TEXT_COLOR: Partial<Record<EffectKind, string>> = {
  spend: GOLD[0],
  rejected: "#ff9a9a",
  death: "#e4e4ee",
  diverted: "#ff9a9a",
  upgrade: "#ffc07a",
  discharged: "#a8f0a0",
  event_start: "#ffe45c",
};

export const EFFECT_KINDS = Object.keys(ICON_FOR) as EffectKind[];

const RISE = 12; // px an effect floats up over its life

export function effectAlpha(age: number): number {
  if (age <= 0.6) return 1;
  return Math.max(0, 1 - (age - 0.6) / 0.4);
}

const SHAKE = [0, -2, 2, -2, 2, -1, 1, 0];
const COIN_SPIN: IconKind[] = ["coin", "coin_mid", "coin_edge", "coin_mid"];

export function drawEffectAt(ctx: CanvasRenderingContext2D, e: Effect): void {
  const age = Math.max(0, Math.min(1, e.age));
  const tick = Math.floor(age * 24); // ~24 animation steps over an effect's life
  const cx = Math.round(e.x) + 8;
  const baseY = Math.round(e.y) + 2;
  const rise = Math.round(age * RISE);

  // death: a white flash, then the ghost floats up and wobbles
  if (e.kind === "death" && age < 0.12) {
    withAlpha(ctx, 1 - age / 0.12, () => {
      const glow = proceduralSprite("death-glow", 20, 20, (x, y) => {
        const d = Math.hypot(x + 0.5 - 10, y + 0.5 - 10);
        return d < 6 ? "rgba(255, 255, 255, 0.8)" : d < 9 ? "rgba(255, 255, 255, 0.4)" : null;
      });
      blit(ctx, glow, cx - 10, baseY - 12);
      drawBurst(ctx, cx, baseY - 2);
    });
    return;
  }

  withAlpha(ctx, effectAlpha(age), () => {
    let kind = ICON_FOR[e.kind] ?? "warning";
    let dx = 0;
    let dy = 0;
    let variant: IconVariant | undefined;
    let flip = false;

    switch (e.kind) {
      case "death":
        dx = Math.round(Math.sin(age * 14) * 2);
        dy = -Math.round(age * 8); // ghosts rise faster than other popups
        break;
      case "discharged":
        variant = "green";
        if (age < 0.12) dy = -3; // pop
        break;
      case "spend":
        kind = COIN_SPIN[tick % COIN_SPIN.length];
        break;
      case "rejected":
        dx = age < 0.4 ? SHAKE[tick % SHAKE.length] : 0;
        break;
      case "upgrade":
        dy = -Math.round(Math.abs(Math.sin(age * Math.PI * 4)) * 4);
        break;
      case "event_start":
        variant = tick % 2 ? "hot" : undefined;
        dy = rise; // stays put while it flashes
        break;
      case "event_end":
        variant = "clear";
        break;
      case "arrival":
        variant = tick % 2 ? "lights_alt" : undefined;
        break;
      case "diverted":
        variant = tick % 2 ? "lights_alt" : undefined;
        flip = true;
        dx = Math.round(age * 6); // drives off
        break;
      default:
        break;
    }

    const { w, h } = iconSize(kind);
    const top = baseY - h - rise + dy;
    const left = cx - Math.floor(w / 2) + dx;

    if (e.kind === "faint") {
      const spots = [[-5, 0], [0, -3], [5, 0], [0, 2]];
      for (let i = 0; i < 3; i++) {
        const [sx, sy] = spots[(tick + i) % spots.length];
        const k: IconKind = i === 0 ? "star" : "spark";
        const sz = iconSize(k);
        drawIcon(ctx, k, cx + sx - Math.floor(sz.w / 2), top + 4 + sy);
      }
    } else {
      drawIcon(ctx, kind, left, top, { variant, flip });
    }
    if (e.kind === "diverted") drawIcon(ctx, "cross", left + w - 6, top - 5);
    if (e.kind === "discharged" && age < 0.3) {
      // sparkles bursting outward from the heart
      const r = 4 + Math.round(age * 20);
      for (const [sx, sy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
        drawIcon(ctx, "spark", cx + sx * r - 2, top + Math.floor(h / 2) + sy * r - 2);
      }
    }

    if (e.text) {
      drawTextCentered(ctx, e.text, cx + dx, top - FONT_HEIGHT - 2, TEXT_COLOR[e.kind] ?? WHITE, OUTLINE);
    }
  });
}
