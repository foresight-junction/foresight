// Patients and staff: chibi people, 12 x 16 px, big heads (9 rows) on small bodies (7 rows).
// One set of templates; an outfit palette turns it into a patient (pale gown, ESI wristband, bare legs,
// slippers), a doctor (white coat, stethoscope, navy trousers) or a nurse (teal scrubs and cap).
// Agency staff wear a bright orange vest with a reflective stripe over their outfit.
//
// Template characters (3-tone ramps: light / mid / dark):
//   o outline
//   + s S    skin            ~ u U  cap (nurse) or hair      ^ h H  hair
//   w e      eye glint, eye  m mouth  p cheek  y under-eye (skin, or dark bags when exhausted)
//   * c C    top             a A    sleeve / arm               q wrist (ESI band on patients)
//   v V =    vest (agency) or top    x stethoscope (doctor) or top
//   g G      hem / coat skirt         l L    legs              k shoes        . transparent

import type { Facing } from "../../replay/frame";
import type { Esi } from "../../replay/types";
import {
  CAP,
  COAT,
  COAT_PANTS,
  ESI_RAMP,
  GOWN,
  HAIRS,
  mix,
  OUTLINE,
  SCRUBS,
  SHEET,
  SICK_SKIN,
  SKINS,
  STETHOSCOPE,
  VEST,
  shade,
  type Ramp,
} from "../palette";
import { hash, mirror, pixmapSprite, px, type Pal, type Pixmap, type Sprite } from "./pixmap";

export const PERSON_W = 12;
export const PERSON_H = 16;

const HEAD_FRONT = px(`
  ...oooooo...
  ..ou~~uuuo..
  .ou~uuuuuUo.
  .ohhhhhhhHo.
  .oh+sssssHo.
  .oswessweso.
  .oseesseeSo.
  .opyymmyypo.
  ..oSSSSSSo..
`);

const HEAD_BACK = px(`
  ...oooooo...
  ..ou~~uuuo..
  .ou~uuuuuUo.
  .ohhhhhhhHo.
  .oh^hhhhhHo.
  .ohhhhhhhHo.
  .oHhhhhhhHo.
  .oHHhhhhHHo.
  ..oSSSSSSo..
`);

const HEAD_SIDE = px(`
  ...oooooo...
  ..ou~~uuuo..
  .ou~uuuuuUo.
  .ohhhhhhhHo.
  .o+sshhhhHo.
  .oswesshhHo.
  .oseesShhHo.
  .opyysshHHo.
  ..oSSSSSSo..
`);

const BODY_FRONT = px(`
  .oavxccxvAo.
  .oav*xxcVAo.
  .oq======qo.
  .osvccxcVso.
  ..ogggggGo..
`);

const BODY_BACK = px(`
  .oavccccvAo.
  .oav*cccVAo.
  .oq======qo.
  .osvcccCVso.
  ..ogggggGo..
`);

const BODY_SIDE = px(`
  ..ovccccVo..
  ..ov*aacVo..
  ..o==aA==o..
  ..ovcqqcVo..
  ..oggssgGo..
`);

const LEGS = {
  front: px(`
    ..olLoolLo..
    ..okkookko..
  `),
  frontStepA: px(`
    ..olLookko..
    ..okko.oo...
  `),
  frontStepB: px(`
    ..okkoolLo..
    ...oo.okko..
  `),
  side: px(`
    ...olllLo...
    ..okkkkko...
  `),
  sideStride: px(`
    ..olLoolLo..
    .okko..okko.
  `),
};

// Rows 11-15 of a seated person (hands on lap, knees, feet).
const SIT_LOWER = px(`
  .osgggggGso.
  .olLllllLLo.
  ..okkookko..
`);

// Below the head of a patient lying in bed: shoulders, arms on the blanket (16 wide).
const BED_BODY = px(`
  ..oaccccccccAo..
  ..oao......oAo..
  ..oqo......oqo..
  ..oso......oso..
  ...o........o...
`);

// A body under a sheet (patient who died), 12 x 16.
export const SHEET_BODY = px(`
  ...oooooo...
  ..owwwwwwo..
  .owwwwwwwWo.
  .owwwwwwwWo.
  .oWwwwwwWWo.
  ..oWWWWWWo..
  .owwwwwwwWo.
  owwwwwwwwwWo
  owwwwwwwwwWo
  oWwwwwwwwWWo
  oWwwwwwwwWWo
  oWwwWwwwwWWo
  .oWwWwwwWWo.
  .oWwWwwwWWo.
  .oWWoWWoWWo.
  ..oo.oo.oo..
`);

export const SHEET_PAL: Pal = { o: OUTLINE, w: SHEET[1], W: "#b4b8c8" };

// ------------------------------------------------------------------ outfits

export interface Look {
  outfit: "patient" | "doctor" | "nurse";
  esi?: Esi;
  agency?: boolean;
  skin: number;
  hair: number;
  exhausted?: boolean;
  sick?: boolean;
}

export function lookFor(id: string, outfit: Look["outfit"], extra: Partial<Look> = {}): Look {
  const h = hash(id);
  return { outfit, skin: h % SKINS.length, hair: (h >>> 8) % HAIRS.length, ...extra };
}

export function personPalette(look: Look): Pal {
  const skin: Ramp = look.sick ? SICK_SKIN : SKINS[look.skin];
  const hair = HAIRS[look.hair];
  const p: Pal = {
    o: OUTLINE,
    "+": skin[0], s: skin[1], S: skin[2],
    "^": hair[0], h: hair[1], H: hair[2],
    "~": hair[0], u: hair[1], U: hair[2],
    w: "#ffffff", e: "#2a2233", m: mix(skin[2], "#a03040", 0.35), p: mix(skin[1], "#ff6a7a", 0.3),
    y: look.exhausted ? mix(skin[2], "#4a2a5a", 0.55) : skin[1],
  };
  let top: Ramp;
  if (look.outfit === "doctor") {
    top = COAT;
    Object.assign(p, { a: COAT[1], A: COAT[2], q: COAT[1], x: STETHOSCOPE, g: COAT[1], G: COAT[2] });
    Object.assign(p, { l: COAT_PANTS[1], L: COAT_PANTS[2], k: "#4a3a34" });
  } else if (look.outfit === "nurse") {
    top = SCRUBS;
    Object.assign(p, { a: skin[1], A: skin[2], q: skin[1], x: SCRUBS[1], g: SCRUBS[2], G: shade(SCRUBS[2], -0.2) });
    Object.assign(p, { l: SCRUBS[1], L: SCRUBS[2], k: "#eceef4", "~": CAP[0], u: CAP[1], U: CAP[2] });
  } else {
    top = GOWN;
    const band = ESI_RAMP[look.esi ?? 3][1];
    Object.assign(p, { a: skin[1], A: skin[2], q: band, x: GOWN[2], g: GOWN[1], G: GOWN[2] });
    Object.assign(p, { l: skin[1], L: skin[2], k: "#e8e0d2" });
  }
  Object.assign(p, { "*": top[0], c: top[1], C: top[2] });
  if (look.agency) Object.assign(p, { v: VEST[1], V: VEST[2], "=": VEST[0] });
  else Object.assign(p, { v: look.outfit === "doctor" ? top[0] : top[1], V: top[2], "=": top[1] });
  return p;
}

// ------------------------------------------------------------------ poses

export type Legs = "idle" | "stepA" | "stepB" | "stride";

export interface PoseSpec {
  pose: "stand" | "sit" | "lie" | "bed";
  facing: Facing;
  legs: Legs;
  squash: boolean; // breathing / landing: head and shoulders drop 1 px, feet stay
  slump: boolean; // exhausted: head sinks onto the shoulders
  blink: boolean;
}

function standing(facing: Facing, legs: Legs): string[] {
  if (facing === "left" || facing === "right") {
    const l = legs === "idle" ? LEGS.side : LEGS.sideStride;
    const map = [...HEAD_SIDE, ...BODY_SIDE, ...l];
    return facing === "right" ? mirror(map) : map;
  }
  const head = facing === "up" ? HEAD_BACK : HEAD_FRONT;
  const body = facing === "up" ? BODY_BACK : BODY_FRONT;
  const l = legs === "stepA" || legs === "stride" ? LEGS.frontStepA : legs === "stepB" ? LEGS.frontStepB : LEGS.front;
  return [...head, ...body, ...l];
}

// Close the eyes: the glint row turns to skin, the lower eye row stays as a lash line.
function closeEyes(map: string[]): string[] {
  const row = map.findIndex((r) => r.includes("w"));
  if (row < 0) return map;
  return map.map((r, i) => (i === row ? r.replace(/[we]/g, "s") : r));
}

// Drop one row at `at`, pad the top: everything above `at` moves down 1 px.
function dropRow(map: string[], at: number): string[] {
  return [".".repeat(map[0].length), ...map.slice(0, at), ...map.slice(at + 1)];
}

// Quarter turn counter-clockwise: the head ends up on the left (someone lying on the floor).
function rotateCcw(map: Pixmap): string[] {
  const w = map[0].length;
  const out: string[] = [];
  for (let y = 0; y < w; y++) {
    let row = "";
    for (let x = 0; x < map.length; x++) row += map[x][w - 1 - y];
    out.push(row);
  }
  return out;
}

export function poseMap(spec: PoseSpec): string[] {
  if (spec.pose === "bed") {
    const head = (spec.blink ? closeEyes([...HEAD_FRONT]) : HEAD_FRONT).map((r) => `..${r}..`);
    return [".".repeat(16), ".".repeat(16), ...head, ...BED_BODY];
  }
  let map: string[];
  if (spec.pose === "sit") map = [...HEAD_FRONT, ...BODY_FRONT.slice(0, 2), ...SIT_LOWER];
  else if (spec.pose === "lie") map = [...HEAD_FRONT, ...BODY_FRONT, ...LEGS.front];
  else map = standing(spec.facing, spec.legs);
  if (spec.blink || spec.pose === "lie") map = closeEyes(map);
  if (spec.pose === "lie") return rotateCcw(map);
  if (spec.slump) map = dropRow(map, 8); // lose the chin row
  if (spec.squash) map = dropRow(map, 10);
  return map;
}

export function personSprite(look: Look, spec: PoseSpec): Sprite {
  const key = [
    "person", look.outfit, look.esi ?? 0, look.agency ? 1 : 0, look.skin, look.hair,
    look.exhausted ? 1 : 0, look.sick ? 1 : 0,
    spec.pose, spec.facing, spec.legs, spec.squash ? 1 : 0, spec.slump ? 1 : 0, spec.blink ? 1 : 0,
  ].join("|");
  return pixmapSprite(key, poseMap(spec), personPalette(look));
}

export function sheetSprite(): Sprite {
  return pixmapSprite("sheet-body", SHEET_BODY, SHEET_PAL);
}

// ------------------------------------------------------------------ animation timing

export interface Anim {
  spec: PoseSpec;
  bob: number; // extra y offset in px (negative = up)
}

// Per-entity phase so a crowd doesn't breathe, blink or step in sync.
export function animPhase(id: string): number {
  return hash("anim", id) % 64;
}

// Blink for one 250 ms frame roughly every 4 s.
export function isBlinking(frame: number, phase: number): boolean {
  return (frame + phase) % 17 === 0;
}

export function standAnim(facing: Facing, moving: boolean, frame: number, phase: number, tired = false): Anim {
  const f = frame + phase;
  const base = { pose: "stand" as const, facing, slump: tired, blink: !moving && isBlinking(frame, phase) };
  if (moving) {
    // 4-frame walk: contact, pass (up), contact, pass (up)
    const step = f % 4;
    const side = facing === "left" || facing === "right";
    const legs: Legs = step % 2 === 1 ? "idle" : side ? "stride" : step === 0 ? "stepA" : "stepB";
    return { spec: { ...base, legs, squash: false }, bob: step % 2 === 1 ? -1 : 0 };
  }
  // idle breathing: 4 frames (8 when exhausted, so the bob is slower)
  const period = tired ? 8 : 4;
  return { spec: { ...base, legs: "idle", squash: f % period >= period / 2 }, bob: 0 };
}

export function sitAnim(frame: number, phase: number, tired = false): Anim {
  const period = tired ? 8 : 4;
  const f = frame + phase;
  return {
    spec: { pose: "sit", facing: "down", legs: "idle", squash: f % period >= period / 2, slump: tired, blink: isBlinking(frame, phase) },
    bob: 0,
  };
}
