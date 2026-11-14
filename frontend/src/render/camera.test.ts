import { describe, expect, it } from "vitest";
import { fitZoom } from "./camera";

describe("fitZoom", () => {
  it("fills the stage instead of rounding down to a smaller integer zoom", () => {
    // 1080p minus the 400px HUD: the fit is ~1.98x, which used to round down to 1x.
    const f = fitZoom(1520, 1080, 768, 448, 1);
    expect(f.cssW).toBeCloseTo(1520);
    expect(f.cssH).toBeLessThanOrEqual(1080);
    expect(f.zoom).toBe(2);
    expect([f.pxW, f.pxH]).toEqual([1536, 896]);
    expect(f.exact).toBe(false);
  });

  it("is limited by height on a wide stage", () => {
    const f = fitZoom(3000, 896, 768, 448, 1);
    expect(f.cssH).toBeCloseTo(896);
    expect(f.cssW).toBeCloseTo(1536);
    expect(f.zoom).toBe(2);
    expect(f.exact).toBe(true);
  });

  it("draws in device pixels on high-DPI screens", () => {
    const f = fitZoom(1536, 896, 768, 448, 2);
    expect(f.zoom).toBe(4);
    expect([f.pxW, f.pxH]).toEqual([3072, 1792]);
    expect([f.cssW, f.cssH]).toEqual([1536, 896]);
    expect(f.exact).toBe(true);
  });

  it("keeps a 1x backing store on tiny stages", () => {
    const f = fitZoom(384, 224, 768, 448, 1);
    expect(f.zoom).toBe(1);
    expect(f.cssW).toBeCloseTo(384);
  });
});
