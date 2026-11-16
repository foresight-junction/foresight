// Shared colours for all pixel art. Cozy 16-bit hospital: warm light floors, soft teal/mint accents,
// one dark warm outline on every character, 3-tone ramps (light, mid, dark) for materials.

import type { Esi } from "../replay/types";

export type Ramp = readonly [string, string, string]; // light, mid, dark

export const PAGE_BG = "#14141c";
export const OUTLINE = "#2a2233";
export const SHADOW = "rgba(20, 16, 32, 0.28)";
export const WHITE = "#fbfaf6";

// Triage colours, ESI 1 critical .. 5 minor.
export const ESI_RAMP: Record<Esi, Ramp> = {
  1: ["#ff8a8a", "#e8484f", "#a8283a"],
  2: ["#ffbe6a", "#f28c2c", "#b85e1c"],
  3: ["#fff08a", "#f2cc3a", "#c09420"],
  4: ["#a8ea8a", "#66c04e", "#3f8a38"],
  5: ["#9ac4ff", "#4c8ee6", "#2f5fae"],
};

export const SKINS: Ramp[] = [
  ["#ffe2c4", "#f6c8a0", "#d89a72"],
  ["#f2bf8e", "#dca070", "#b0774c"],
  ["#c88c5e", "#a8703f", "#80522c"],
  ["#946040", "#74462a", "#54301a"],
];
export const SICK_SKIN: Ramp = ["#e2f0b8", "#c4d89a", "#98b070"];
export const HAIRS: Ramp[] = [
  ["#5a4438", "#3a2a24", "#221814"],
  ["#946038", "#6e4428", "#4a2c18"],
  ["#f2d27a", "#d0a650", "#a07830"],
  ["#4a4a5c", "#2a2a36", "#16161e"],
  ["#d06a44", "#a44a2c", "#72301a"],
  ["#f0eee8", "#d0ccc4", "#a09c94"],
  ["#7a5a9a", "#54407a", "#382a56"],
];

export const COAT: Ramp = ["#ffffff", "#eceef2", "#b4bccc"]; // doctor white coat
export const COAT_PANTS: Ramp = ["#56688e", "#3e4c6e", "#2a3450"];
export const SCRUBS: Ramp = ["#72d8ca", "#2fa69c", "#1c7069"]; // nurse teal
export const CAP: Ramp = ["#b2f0e6", "#6cd2c4", "#3a9e92"];
export const GOWN: Ramp = ["#f6faff", "#d2e2f4", "#9eb4d2"]; // patient gown
export const VEST: Ramp = ["#fff27a", "#ff8a1c", "#c45a10"]; // agency hi-vis vest (stripe, mid, dark)
export const STETHOSCOPE = "#4a4a5a";

export const TEAL = "#3fb6a8";
export const MINT = ["#9edcc8", "#6cbca6"] as const;
export const METAL = ["#c8ccd8", "#9098ac", "#5e657a"] as const;
export const SHEET = ["#fbfaf6", "#dfe2ea"] as const;
export const GOOD = "#58c860";
export const BAD = "#e8484f";
export const WARN = "#f2cc3a";
export const GOLD = ["#f6d04a", "#c8962a", "#fff2a8"] as const;
export const SWEAT = "#7cc6f0";
export const STAR = "#ffe45c";
export const SMOKE = ["#8a8a96", "#b8b8c2"] as const;

function rgb(hex: string): number[] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function toHex(ch: number[]): string {
  return "#" + ch.map((c) => Math.max(0, Math.min(255, Math.round(c))).toString(16).padStart(2, "0")).join("");
}

// Lighten (amt > 0) or darken (amt < 0) a #rrggbb colour by a fraction.
export function shade(hex: string, amt: number): string {
  return toHex(rgb(hex).map((c) => (amt < 0 ? c * (1 + amt) : c + (255 - c) * amt)));
}

// Blend a toward b by t (0..1).
export function mix(a: string, b: string, t: number): string {
  const ca = rgb(a);
  const cb = rgb(b);
  return toHex(ca.map((c, i) => c + (cb[i] - c) * t));
}
