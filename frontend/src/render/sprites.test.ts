// Pixel maps are hand-typed strings, so check they are rectangular, the right size, and fully coloured.
// Pure data checks: no canvas needed.

import { describe, expect, it } from "vitest";
import type { Facing } from "../replay/frame";
import { FONT_HEIGHT, GLYPHS, measureText } from "./art/font";
import { BED_EMPTY, BED_OCCUPIED, BED_PAL, CHAIR, COFFEE_MACHINE, DESK, MONITOR, PLANT, PROP_PALETTE, SOFA } from "./art/furniture";
import { ICON_KINDS, ICON_PAL, iconMap } from "./art/icons";
import { lookFor, personPalette, poseMap, SHEET_BODY, SHEET_PAL, type Legs, type PoseSpec } from "./art/people";
import { missingColors, outlined, pixmapSize, type Pixmap } from "./art/pixmap";
import { mix, shade } from "./palette";

function rectangular(map: Pixmap): boolean {
  return map.every((r) => r.length === map[0].length);
}

describe("furniture maps", () => {
  const cases: [string, Pixmap, number, number, Record<string, string>][] = [
    ["bed empty", BED_EMPTY, 16, 24, BED_PAL],
    ["bed occupied", BED_OCCUPIED, 16, 24, BED_PAL],
    ["chair", CHAIR, 16, 16, PROP_PALETTE],
    ["plant", PLANT, 16, 16, PROP_PALETTE],
    ["desk", DESK, 32, 16, PROP_PALETTE],
    ["sofa", SOFA, 32, 16, PROP_PALETTE],
    ["coffee", COFFEE_MACHINE, 16, 16, PROP_PALETTE],
    ["monitor", MONITOR, 8, 10, PROP_PALETTE],
  ];
  it.each(cases)("%s is rectangular, sized and coloured", (_name, map, w, h, pal) => {
    expect(rectangular(map)).toBe(true);
    expect(pixmapSize(map)).toEqual({ w, h });
    expect(missingColors(map, pal)).toEqual([]);
  });
});

describe("people", () => {
  const facings: Facing[] = ["down", "up", "left", "right"];
  const legs: Legs[] = ["idle", "stepA", "stepB", "stride"];
  const looks = [
    lookFor("P001", "patient", { esi: 1 }),
    lookFor("D1", "doctor"),
    lookFor("AN1", "nurse", { agency: true, exhausted: true }),
  ];

  it("standing poses are 12 x 16 in every facing and step", () => {
    for (const facing of facings) {
      for (const l of legs) {
        for (const squash of [false, true]) {
          const spec: PoseSpec = { pose: "stand", facing, legs: l, squash, slump: false, blink: false };
          const map = poseMap(spec);
          expect(rectangular(map), `${facing} ${l}`).toBe(true);
          expect(pixmapSize(map)).toEqual({ w: 12, h: 16 });
        }
      }
    }
  });

  it("every pose is coloured by every outfit", () => {
    const specs: PoseSpec[] = [
      { pose: "stand", facing: "down", legs: "stepA", squash: true, slump: true, blink: true },
      { pose: "stand", facing: "left", legs: "stride", squash: false, slump: false, blink: false },
      { pose: "stand", facing: "up", legs: "idle", squash: false, slump: false, blink: false },
      { pose: "sit", facing: "down", legs: "idle", squash: true, slump: false, blink: false },
      { pose: "lie", facing: "down", legs: "idle", squash: false, slump: false, blink: true },
      { pose: "bed", facing: "down", legs: "idle", squash: false, slump: false, blink: false },
    ];
    for (const look of looks) {
      for (const spec of specs) {
        const map = poseMap(spec);
        expect(rectangular(map), spec.pose).toBe(true);
        expect(missingColors(map, personPalette(look)), `${look.outfit} ${spec.pose}`).toEqual([]);
      }
    }
  });

  it("lying in bed fits the 16-wide bed", () => {
    const map = poseMap({ pose: "bed", facing: "down", legs: "idle", squash: false, slump: false, blink: false });
    expect(pixmapSize(map).w).toBe(16);
    expect(map.length).toBeLessThanOrEqual(24);
  });

  it("blinking closes the eyes", () => {
    const open = poseMap({ pose: "stand", facing: "down", legs: "idle", squash: false, slump: false, blink: false });
    const shut = poseMap({ pose: "stand", facing: "down", legs: "idle", squash: false, slump: false, blink: true });
    expect(open.join("")).toContain("w");
    expect(shut.join("")).not.toContain("w");
  });

  it("agency staff get the vest colour, others keep their outfit", () => {
    const plain = personPalette(lookFor("N1", "nurse"));
    const agency = personPalette(lookFor("AN1", "nurse", { agency: true }));
    expect(plain.v).toBe(plain.c);
    expect(agency.v).not.toBe(agency.c);
  });

  it("the death sheet is coloured", () => {
    expect(rectangular(SHEET_BODY)).toBe(true);
    expect(missingColors(SHEET_BODY, SHEET_PAL)).toEqual([]);
  });
});

describe("icons", () => {
  it.each(ICON_KINDS)("%s is rectangular and coloured", (kind) => {
    const map = iconMap(kind);
    expect(rectangular(map)).toBe(true);
    expect(missingColors(map, ICON_PAL)).toEqual([]);
  });

  it("outlined grows a map by one pixel on each side", () => {
    expect(outlined(["x"])).toEqual(["ooo", "oxo", "ooo"]);
  });
});

describe("font", () => {
  it("has every glyph the viewer needs, 5 rows of equal width", () => {
    for (const ch of "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789€-+!?") expect(GLYPHS[ch], ch).toBeDefined();
    for (const [ch, g] of Object.entries(GLYPHS)) {
      expect(g.length, ch).toBe(FONT_HEIGHT);
      expect(rectangular(g), ch).toBe(true);
    }
  });

  it("measures text with 1 px spacing", () => {
    expect(measureText("")).toBe(0);
    expect(measureText("1")).toBe(3);
    expect(measureText("-€900")).toBe(3 + 1 + 4 + 1 + 3 + 1 + 3 + 1 + 3);
    expect(measureText("abc")).toBe(measureText("ABC"));
  });
});

describe("palette helpers", () => {
  it("shades and mixes hex colours", () => {
    expect(shade("#808080", -0.5)).toBe("#404040");
    expect(shade("#000000", 1)).toBe("#ffffff");
    expect(mix("#000000", "#ffffff", 0.5)).toBe("#808080");
  });
});
