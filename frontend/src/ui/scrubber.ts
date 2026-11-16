// Canvas timeline of the whole episode: event bands, diversion, per-tick markers, queue sparkline,
// a playhead, and click/drag to seek.

import { buildTimeline, tickSummary, type TimelineData } from "./timeline";
import type { Replay } from "../replay/types";

export const BAND_COLOR: Record<string, string> = {
  staff_sickness: "#12a594",
  flu_wave: "#8db04a",
  ct_breakdown: "#8e8ca4",
  bus_crash: "#d6409f",
  diversion: "#0090ff",
};

export const MARK_COLOR = {
  deaths: "#e5484d",
  faints: "#8e4ec6",
  rejected: "#f76b15",
  spend: "#e2b714",
} as const;

// Two event lanes: the start windows (SPEC §3) keep sickness/CT and flu/bus from overlapping.
const LANE: Record<string, number> = { staff_sickness: 0, ct_breakdown: 0, flu_wave: 1, bus_crash: 1, diversion: 2 };
const MARK_ROWS = ["deaths", "faints", "rejected", "spend"] as const;

const H = 82;
const BAND_Y = 2;
const BAND_H = 6;
const SPARK_TOP = 26;
const SPARK_BOTTOM = 50;
const MARK_Y = 52;
const MARK_H = 6;

export interface Scrubber {
  el: HTMLElement;
  data: TimelineData;
  setPosition(tickFloat: number): void;
  destroy(): void;
}

export function createScrubber(replay: Replay, onSeek: (tick: number) => void): Scrubber {
  const data = buildTimeline(replay);
  const wrap = document.createElement("div");
  wrap.className = "scrub";
  const canvas = document.createElement("canvas");
  canvas.className = "scrub-canvas";
  canvas.setAttribute("role", "slider");
  canvas.setAttribute("aria-label", "Episode timeline");
  canvas.setAttribute("aria-valuemin", "0");
  canvas.setAttribute("aria-valuemax", String(data.n - 1));
  const tip = document.createElement("div");
  tip.className = "scrub-tip";
  wrap.append(canvas, tip);

  const base = document.createElement("canvas");
  let width = 0;
  let dpr = 1;
  let pos = 0;
  let drawnX = -1;

  const xOf = (tick: number): number => (tick / data.n) * width;

  function drawBase(): void {
    width = Math.max(1, wrap.clientWidth);
    dpr = window.devicePixelRatio || 1;
    for (const c of [canvas, base]) {
      c.width = Math.round(width * dpr);
      c.height = Math.round(H * dpr);
    }
    canvas.style.height = `${H}px`;
    const g = base.getContext("2d");
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.fillStyle = "#101018";
    g.fillRect(0, 0, width, H);

    // Lane backgrounds.
    g.fillStyle = "#1a1a26";
    for (let l = 0; l < 3; l++) g.fillRect(0, BAND_Y + l * (BAND_H + 1), width, BAND_H);
    for (const b of data.bands) {
      g.fillStyle = BAND_COLOR[b.kind] ?? "#888";
      const x0 = Math.floor(xOf(b.start));
      const x1 = Math.ceil(xOf(b.end));
      g.fillRect(x0, BAND_Y + (LANE[b.kind] ?? 2) * (BAND_H + 1), Math.max(2, x1 - x0), BAND_H);
    }

    // Midnights (tick 32, 80, 128) with day labels.
    g.font = "9px ui-monospace, monospace";
    g.textBaseline = "top";
    for (let day = 1; day <= 4; day++) {
      const tick = day === 1 ? 0 : 32 + (day - 2) * 48;
      if (tick >= data.n) break;
      const x = Math.floor(xOf(tick));
      g.fillStyle = "#2a2a3a";
      if (tick > 0) g.fillRect(x, SPARK_TOP - 3, 1, H - SPARK_TOP + 3);
      g.fillStyle = "#6c6c80";
      g.fillText(`D${day}`, x + 2, SPARK_TOP - 2);
    }

    // Waiting-room queue as a stepped area.
    g.fillStyle = "#3a3a52";
    const span = SPARK_BOTTOM - SPARK_TOP - 8;
    data.marks.forEach((m, i) => {
      const h = Math.round((m.waiting / data.maxWaiting) * span);
      if (!h) return;
      const x0 = Math.floor(xOf(i));
      g.fillRect(x0, SPARK_BOTTOM - h, Math.max(1, Math.floor(xOf(i + 1)) - x0), h);
    });

    // Per-tick markers, one row each.
    g.fillStyle = "#1a1a26";
    MARK_ROWS.forEach((_, r) => g.fillRect(0, MARK_Y + r * (MARK_H + 1), width, MARK_H));
    data.marks.forEach((m, i) => {
      const cx = xOf(i + 0.5);
      const w = Math.max(3, Math.floor(xOf(i + 1) - xOf(i)));
      const x0 = Math.round(cx - w / 2);
      if (m.deaths) {
        // Deaths matter most: a faint red rule through the queue so they read at a glance.
        g.fillStyle = "rgba(229,72,77,0.45)";
        g.fillRect(Math.round(cx), SPARK_TOP - 4, 1, MARK_Y - SPARK_TOP + 4);
      }
      MARK_ROWS.forEach((k, r) => {
        if (!m[k]) return;
        g.fillStyle = MARK_COLOR[k];
        g.fillRect(x0, MARK_Y + r * (MARK_H + 1), w, MARK_H);
      });
    });
    drawnX = -1;
    paint();
  }

  function paint(): void {
    const g = canvas.getContext("2d");
    if (!g) return;
    const x = Math.round(xOf(pos));
    if (x === drawnX) return;
    drawnX = x;
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.drawImage(base, 0, 0);
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.fillStyle = "rgba(255,255,255,0.08)";
    g.fillRect(0, 0, x, H);
    g.fillStyle = "#ffffff";
    g.fillRect(x - 1, 0, 2, H);
    g.beginPath();
    g.moveTo(x - 4, 0);
    g.lineTo(x + 4, 0);
    g.lineTo(x, 5);
    g.fill();
  }

  const tickAt = (clientX: number): number => {
    const r = canvas.getBoundingClientRect();
    return Math.max(0, Math.min(data.n - 1, Math.floor(((clientX - r.left) / r.width) * data.n)));
  };

  let dragging = false;
  const showTip = (clientX: number): void => {
    const tick = tickAt(clientX);
    tip.textContent = tickSummary(data, tick);
    const r = canvas.getBoundingClientRect();
    tip.style.left = `${Math.max(0, Math.min(r.width - tip.offsetWidth, clientX - r.left - tip.offsetWidth / 2))}px`;
    tip.classList.add("on");
  };
  canvas.addEventListener("pointerdown", (e) => {
    dragging = true;
    canvas.setPointerCapture(e.pointerId);
    onSeek(tickAt(e.clientX));
    showTip(e.clientX);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (dragging) onSeek(tickAt(e.clientX));
    showTip(e.clientX);
  });
  const stop = (): void => {
    dragging = false;
  };
  canvas.addEventListener("pointerup", stop);
  canvas.addEventListener("pointercancel", stop);
  canvas.addEventListener("pointerleave", () => tip.classList.remove("on"));

  const ro = new ResizeObserver(() => {
    if (wrap.clientWidth !== width) drawBase();
  });
  ro.observe(wrap);

  return {
    el: wrap,
    data,
    setPosition(tickFloat: number) {
      if (Math.floor(tickFloat) !== Math.floor(pos) || drawnX < 0) {
        canvas.setAttribute("aria-valuenow", String(Math.floor(tickFloat)));
      }
      pos = tickFloat;
      if (width === 0 && wrap.isConnected) drawBase();
      else paint();
    },
    destroy() {
      ro.disconnect();
    },
  };
}
