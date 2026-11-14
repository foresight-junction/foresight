// Fit the map into the stage so it fills as much of it as the aspect ratio allows. The canvas draws at
// the smallest integer zoom (in device pixels) at or above the fit, so map pixels are exact squares in
// the backing store, and CSS scales it down by less than one zoom step to fill the stage exactly.
// `exact` is true when no CSS scaling happens (the fit landed on an integer zoom).

export interface Fit {
  zoom: number; // backing-store device pixels per map pixel
  pxW: number; // canvas backing size, device pixels
  pxH: number;
  cssW: number; // canvas CSS size
  cssH: number;
  exact: boolean;
}

export function fitZoom(availCssW: number, availCssH: number, mapW: number, mapH: number, dpr: number): Fit {
  const ratio = dpr > 0 ? dpr : 1;
  const fit = Math.max(0.25, Math.min((availCssW * ratio) / mapW, (availCssH * ratio) / mapH));
  const zoom = Math.max(1, Math.ceil(fit - 1e-6));
  const pxW = Math.round(mapW * zoom);
  const pxH = Math.round(mapH * zoom);
  const cssW = (mapW * fit) / ratio;
  const cssH = (mapH * fit) / ratio;
  return { zoom, pxW, pxH, cssW, cssH, exact: Math.abs(fit - zoom) < 1e-6 };
}

// Clock for a tick: tick 0 is Day 1 08:00 and each tick is 30 minutes. Returns hours since midnight.
export function hourOfDay(tick: number, phase = 0): number {
  return (8 + (tick + phase) * 0.5) % 24;
}

// 0 in full daylight .. 1 in the dead of night, with dawn 05:00-07:30 and dusk 18:00-21:00.
export function darkness(hour: number): number {
  if (hour < 5) return 1;
  if (hour < 7.5) return 1 - (hour - 5) / 2.5;
  if (hour < 18) return 0;
  if (hour < 21) return (hour - 18) / 3;
  return 1;
}
