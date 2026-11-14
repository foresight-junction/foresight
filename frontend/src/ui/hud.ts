// Side panel: replay picker and score, clock and transport, scrubber, the AI's decisions this tick,
// what happened, department status and the episode's mistakes. Owner: agent E (HUD).

import type { Playback } from "../game/playback";
import type { Observation, Replay, ReplayIndexEntry, Staff, Zone } from "../replay/types";
import {
  describeActions,
  describeEvents,
  describeWarnings,
  euro,
  eventName,
  scoreParts,
  zoneCapacity,
  ZONE_NAME,
  type ActionLine,
  type Line,
} from "./describe";
import "./hud.css";
import { BAND_COLOR, createScrubber, MARK_COLOR } from "./scrubber";
import { findMistakes, type Band } from "./timeline";

export interface HudOptions {
  replays: ReplayIndexEntry[];
  currentFile: string;
  onSelectReplay: (file: string) => void;
}

export interface Hud {
  update(): void; // called every animation frame
  destroy(): void;
}

const SPEEDS = [1, 2, 4, 8, 16];
const ZONES: Zone[] = ["resus", "acute", "fast_track"];
const TEXT = "︎"; // ask for the text (not emoji) form of media-control glyphs

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function panel(title: string, cls: string): { root: HTMLElement; head: HTMLElement; body: HTMLElement } {
  const root = el("section", `panel ${cls}`);
  const head = el("h2", "panel-title", title);
  const body = el("div", "panel-body");
  root.append(head, body);
  return { root, head, body };
}

function fatigueClass(f: number): string {
  return f >= 75 ? "fat-hi" : f > 60 ? "fat-mid" : "fat-lo";
}

function lineEl(l: Line | ActionLine): HTMLElement {
  const li = el("li", `ln tone-${l.tone}${l.esi ? ` esi-edge-${l.esi}` : ""}`);
  li.append(el("span", "ln-ic", l.icon));
  const tx = el("div", "ln-tx");
  tx.append(el("div", "ln-main", l.text));
  if ("ok" in l && !l.ok) tx.append(el("div", "ln-why", `✗ ${l.reason ?? "rejected"}`));
  if (l.detail) tx.append(el("div", "ln-dt", l.detail));
  li.append(tx);
  if ("ok" in l) li.append(el("span", l.ok ? "ln-ok" : "ln-no", l.ok ? "✓" : "✗"));
  return li;
}

function staffChip(s: Staff, extra?: string): HTMLElement {
  const c = el("span", `chip ${fatigueClass(s.fatigue)}${s.agency ? " agency" : ""}`);
  c.textContent = extra ? `${s.id} ${extra}` : `${s.id} ${Math.round(s.fatigue)}`;
  c.title = `${s.id}: ${s.role}${s.agency ? " (agency)" : ""}, fatigue ${s.fatigue.toFixed(1)}, ${s.status}`;
  return c;
}

function kv(label: string, value: string | HTMLElement, cls = ""): HTMLElement {
  const row = el("div", `kv ${cls}`);
  row.append(el("span", "kv-k", label));
  const v = typeof value === "string" ? el("span", "kv-v", value) : value;
  v.classList.add("kv-v");
  row.append(v);
  return row;
}

function renderStatus(body: HTMLElement, obs: Observation, active: Band[]): void {
  const out: HTMLElement[] = [];

  const { spent, budget, hard_limit } = obs.budget;
  const b = el("div", "budget");
  const track = el("div", "budget-track");
  const fill = el("div", `budget-fill ${spent > budget ? (spent > budget + (hard_limit - budget) / 2 ? "hot" : "over") : ""}`);
  fill.style.width = `${Math.min(100, (spent / hard_limit) * 100)}%`;
  const mark = el("div", "budget-mark");
  mark.style.left = `${(budget / hard_limit) * 100}%`;
  track.append(fill, mark);
  const left = budget - spent;
  b.append(
    kv("Budget", left >= 0 ? `${euro(spent)} spent · ${euro(left)} left` : `${euro(spent)} · ${euro(-left)} over`),
    track,
    el("div", "budget-scale", `| marks the ${euro(budget)} budget · bar ends at the ${euro(hard_limit)} limit`),
  );
  out.push(b);

  const wait = el("div", "esi-row");
  for (let e = 1; e <= 5; e++) {
    const n = obs.waiting.filter((w) => w.esi === e).length;
    const c = el("span", `esi-chip esi-${e}${n ? "" : " zero"}`, `${e}:${n}`);
    c.title = `ESI ${e}: ${n} waiting`;
    wait.append(c);
  }
  const longest = obs.waiting.reduce((m, w) => Math.max(m, w.waited_ticks), 0);
  out.push(kv(`Waiting ${obs.waiting.length}`, wait));
  if (obs.waiting.length) out.push(el("div", "sub", `longest wait ${longest} tick${longest === 1 ? "" : "s"}`));

  const beds = el("div", "zones");
  for (const z of ZONES) {
    const zb = obs.beds.filter((x) => x.zone === z);
    const used = zb.filter((x) => x.patient).length;
    const uncovered = zb.filter((x) => x.patient && x.covered === false).length;
    const row = el("div", "zone-row");
    row.append(el("span", "zone-name", ZONE_NAME[z]));
    const cells = el("span", "bed-cells");
    for (const bed of zb) {
      const c = el("span", "bed");
      if (bed.patient && bed.esi) {
        c.classList.add(`esi-${bed.esi}`);
        if (bed.covered === false) c.classList.add("uncov");
        if (bed.waiting_for_ct) c.classList.add("ct");
        c.title = `${bed.bed}: ${bed.patient} ESI ${bed.esi}, ${bed.treated_ticks ?? 0}/${bed.treatment_ticks ?? "?"} ticks${bed.covered === false ? ", NOT covered" : ""}${bed.waiting_for_ct ? ", waiting for CT" : ""}`;
      } else c.title = `${bed.bed}: empty`;
      cells.append(c);
    }
    row.append(cells);
    const info = el("span", "zone-info", `${used}/${zb.length} · cover ${zoneCapacity(obs, z)}`);
    if (uncovered) info.append(el("span", "bad", ` · ${uncovered} uncovered`));
    row.append(info);
    beds.append(row);
  }
  out.push(el("h3", "sub-title", "Beds"), beds);

  const staff = el("div", "staff");
  const staffRow = (label: string, list: Staff[], extra?: (s: Staff) => string): void => {
    const row = el("div", "staff-row");
    row.append(el("span", "zone-name", label));
    const chips = el("span", "chips");
    if (!list.length) chips.append(el("span", "muted", "none"));
    for (const s of list) chips.append(staffChip(s, extra?.(s)));
    row.append(chips);
    staff.append(row);
  };
  for (const z of ZONES) {
    staffRow(ZONE_NAME[z], obs.staff.filter((s) => s.status === "on_shift" && s.location === z));
  }
  staffRow("Rest", obs.staff.filter((s) => s.status === "resting" || (s.status === "on_shift" && s.location === "rest")));
  const outList = obs.staff.filter((s) => s.status === "fainted" || s.status === "sick");
  if (outList.length) {
    staffRow("Out", outList, (s) => `${s.status === "sick" ? "sick" : "fainted"} ${s.ticks_until_change ?? "?"}t`);
  }
  const ordered = obs.staff.filter((s) => s.status === "agency_ordered");
  if (ordered.length) staffRow("Coming", ordered, (s) => `in ${s.ticks_until_change ?? "?"}t`);
  out.push(el("h3", "sub-title", "Staff (fatigue)"), staff);

  const sys = el("div", "sys");
  const events = active.filter((b) => b.kind !== "diversion");
  sys.append(
    kv(
      "Events",
      events.length ? events.map((b) => `${eventName(b.kind)} until t${b.end}`).join(", ") : "none",
      events.length ? "warn" : "",
    ),
    kv("CT scanner", obs.ct.working ? "working" : `DOWN · ${obs.ct.down_ticks_left} ticks left`, obs.ct.working ? "" : "bad"),
    kv("Diversion", obs.diversion.active ? `ACTIVE · ${obs.diversion.ticks_left} ticks left` : "off", obs.diversion.active ? "warn" : ""),
  );
  out.push(sys);

  const t = obs.totals;
  const totals = el("div", "totals");
  const cell = (label: string, n: number, cls: string): void => {
    const c = el("div", `tot ${n ? cls : ""}`);
    c.append(el("div", "tot-n", String(n)), el("div", "tot-l", label));
    totals.append(c);
  };
  cell("discharged", t.discharged, "good");
  cell("deaths", t.deaths, "bad");
  cell("left", t.left, "warn");
  cell("diverted", t.diverted, "warn");
  cell("faints", t.faints, "bad");
  out.push(totals);

  body.replaceChildren(...out);
}

export function mountHud(root: HTMLElement, replay: Replay, playback: Playback, opts: HudOptions): Hud {
  const meta = replay.meta;
  const hud = el("div", "hud");

  // Header: picker, label, reward and the four score parts.
  const header = el("section", "panel header");
  const picker = el("select", "picker");
  picker.setAttribute("aria-label", "Replay");
  for (const r of opts.replays) {
    const o = el("option", "", `${r.label} · seed ${r.seed} · ${r.reward.toFixed(3)}`);
    o.value = r.file;
    o.selected = r.file === opts.currentFile;
    picker.append(o);
  }
  picker.addEventListener("change", () => opts.onSelectReplay(picker.value));
  const titleRow = el("div", "title-row");
  const who = el("div", "who");
  who.append(el("div", "who-label", meta.label), el("div", "who-sub", `policy ${meta.policy} · seed ${meta.seed}`));
  const reward = el("div", "reward");
  reward.append(el("div", "reward-n", meta.reward.toFixed(3)), el("div", "reward-l", `reward · ${meta.score.score.toFixed(1)}/100`));
  titleRow.append(who, reward);
  const parts = el("div", "parts");
  for (const p of scoreParts(meta.score)) {
    const row = el("div", `part part-${p.key}`);
    row.title = `${p.name} ${p.key} = ${p.value.toFixed(3)}, worth ${p.points.toFixed(1)} of ${p.max} points`;
    const bar = el("div", "part-bar");
    const fill = el("div", "part-fill");
    fill.style.width = `${Math.max(0, Math.min(1, p.value)) * 100}%`;
    bar.append(fill);
    row.append(el("span", "part-k", p.key), bar, el("span", "part-v", `${p.points.toFixed(1)}/${p.max}`));
    parts.append(row);
  }
  header.append(picker, titleRow, parts);

  // Clock, transport, speed and scrubber stay pinned at the top while the panel scrolls.
  const clock = el("section", "panel clock");
  const clockRow = el("div", "clock-row");
  const time = el("div", "clock-time");
  const tickNo = el("div", "clock-tick");
  clockRow.append(time, tickNo);
  const transport = el("div", "transport");
  const btn = (label: string, title: string, on: () => void, cls = ""): HTMLButtonElement => {
    const b = el("button", `tbtn ${cls}`, label);
    b.type = "button";
    b.title = title;
    b.setAttribute("aria-label", title);
    b.addEventListener("click", (e) => {
      on();
      // A mouse click should not leave focus on the button, or Space would press it again.
      if (e.detail > 0) b.blur();
    });
    return b;
  };
  const togglePlay = (): void => {
    if (!playback.playing && playback.tick >= playback.tickCount - 1) playback.seek(0);
    playback.toggle();
  };
  const playBtn = btn("", "Play / pause (Space)", togglePlay, "play");
  transport.append(
    btn(`⏮${TEXT}`, "Start (Home)", () => playback.seek(0)),
    btn("◀", "Step back (←)", () => playback.stepBack()),
    playBtn,
    btn("▶", "Step forward (→)", () => playback.stepForward()),
    btn(`⏭${TEXT}`, "End (End)", () => playback.seek(playback.tickCount - 1)),
  );
  const speeds = el("div", "speeds");
  speeds.setAttribute("role", "group");
  speeds.setAttribute("aria-label", "Speed (+/-)");
  const speedBtns = SPEEDS.map((s) => {
    const b = btn(`${s}x`, `${s} ticks per second`, () => (playback.speed = s), "speed");
    speeds.append(b);
    return b;
  });
  const scrubber = createScrubber(replay, (t) => playback.seek(t));
  const legend = el("div", "legend");
  const legendItem = (color: string, label: string): void => {
    const i = el("span", "lg");
    const sw = el("span", "lg-sw");
    sw.style.background = color;
    i.append(sw, document.createTextNode(label));
    legend.append(i);
  };
  legendItem(MARK_COLOR.deaths, "death");
  legendItem(MARK_COLOR.faints, "faint");
  legendItem(MARK_COLOR.rejected, "rejected");
  legendItem(MARK_COLOR.spend, "spend");
  legendItem("#3a3a52", "queue");
  const kinds = new Set(scrubber.data.bands.map((b) => b.kind));
  for (const [k, label] of [
    ["staff_sickness", "sickness"],
    ["flu_wave", "flu"],
    ["ct_breakdown", "CT down"],
    ["bus_crash", "bus crash"],
    ["diversion", "diversion"],
  ]) {
    if (kinds.has(k)) legendItem(BAND_COLOR[k], label);
  }
  const controls = el("div", "controls");
  controls.append(transport, speeds);
  clock.append(clockRow, controls, scrubber.el, legend);

  const decisions = panel("AI decisions this tick", "decisions");
  const happened = panel("What happened", "happened");
  const status = panel("Department (start of tick)", "status");

  const mistakesP = panel("", "mistakes");
  const mistakes = findMistakes(replay);
  mistakesP.head.textContent = `Mistakes this episode (${mistakes.length})`;
  const mList = el("ul", "mlist");
  const mRows = mistakes.map((m) => {
    const li = el("li");
    const b = el("button", `mrow${m.esi ? ` esi-edge-${m.esi}` : ""}`);
    b.type = "button";
    b.append(el("span", "m-t", `t${m.tick}`), el("span", "ln-ic", m.icon), el("span", "m-x", m.text));
    b.addEventListener("click", () => {
      playback.pause();
      playback.seek(m.tick);
    });
    li.append(b);
    mList.append(li);
    return { li, tick: m.tick };
  });
  if (mistakes.length) mistakesP.body.append(mList);
  else mistakesP.body.append(el("p", "muted", "No deaths, faints or walk-outs: a clean run."));

  const help = el(
    "p",
    "keys",
    "Space play/pause · ←/→ step (Shift ×10) · Home/End · +/- speed · click or drag the timeline",
  );

  hud.append(header, clock, decisions.root, happened.root, status.root, mistakesP.root, help);
  root.replaceChildren(hud);

  let shownTick = -1;
  let shownPlaying: boolean | null = null;
  let shownSpeed = -1;

  function renderTick(): void {
    const t = playback.current();
    const obs = t.obs;
    time.textContent = obs.clock;
    tickNo.textContent = `tick ${t.tick} / ${playback.tickCount - 1}`;

    const acts = describeActions(t);
    decisions.head.textContent = "AI decisions this tick";
    if (acts.total) {
      decisions.head.append(
        el("span", `head-badge${acts.rejected ? " bad" : ""}`, `${acts.total} action${acts.total === 1 ? "" : "s"}${acts.rejected ? ` · ${acts.rejected} ✗` : ""}`),
      );
    }
    const dl = el("ul", "lines");
    for (const l of acts.lines) dl.append(lineEl(l));
    if (acts.kept.length) {
      dl.append(
        lineEl({
          icon: "·",
          text: `Kept ${acts.kept.length} staff where they were`,
          tone: "muted",
          detail: acts.kept.join(" "),
        }),
      );
    }
    if (!acts.total) dl.append(el("li", "empty", "No actions: the AI passed this tick."));
    decisions.body.replaceChildren(dl);

    const hl = el("ul", "lines");
    const evs = [...describeWarnings(obs), ...describeEvents(t)];
    for (const l of evs) hl.append(lineEl(l));
    if (!evs.length) hl.append(el("li", "empty", "A quiet tick."));
    happened.body.replaceChildren(hl);

    renderStatus(
      status.body,
      obs,
      scrubber.data.bands.filter((b) => b.start <= t.tick && t.tick < b.end),
    );

    for (const r of mRows) r.li.classList.toggle("now", r.tick === t.tick);
  }

  function setSpeedIndex(delta: number): void {
    let i = SPEEDS.findIndex((s) => s >= playback.speed);
    if (i < 0) i = SPEEDS.length - 1;
    playback.speed = SPEEDS[Math.max(0, Math.min(SPEEDS.length - 1, i + delta))];
  }

  const onKey = (e: KeyboardEvent): void => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const target = e.target as HTMLElement | null;
    if (target?.closest("input, select, textarea, [contenteditable]")) return;
    const onButton = !!target?.closest("button");
    switch (e.key) {
      case " ":
        if (onButton) return; // keyboard users pressing a focused button
        togglePlay();
        break;
      case "ArrowLeft":
        playback.seek(playback.tick - (e.shiftKey ? 10 : 1));
        break;
      case "ArrowRight":
        playback.seek(playback.tick + (e.shiftKey ? 10 : 1));
        break;
      case "Home":
        playback.seek(0);
        break;
      case "End":
        playback.seek(playback.tickCount - 1);
        break;
      case "+":
      case "=":
        setSpeedIndex(1);
        break;
      case "-":
      case "_":
        setSpeedIndex(-1);
        break;
      default:
        return;
    }
    e.preventDefault();
  };
  window.addEventListener("keydown", onKey);

  return {
    update() {
      if (playback.tick !== shownTick) {
        shownTick = playback.tick;
        renderTick();
      }
      if (playback.playing !== shownPlaying) {
        shownPlaying = playback.playing;
        playBtn.textContent = playback.playing ? `⏸${TEXT}` : "▶";
        playBtn.classList.toggle("on", playback.playing);
      }
      if (playback.speed !== shownSpeed) {
        shownSpeed = playback.speed;
        speedBtns.forEach((b, i) => b.classList.toggle("on", SPEEDS[i] === playback.speed));
      }
      scrubber.setPosition(playback.tick + (playback.playing ? Math.min(playback.phase, 1) : 0.5));
    },
    destroy() {
      window.removeEventListener("keydown", onKey);
      scrubber.destroy();
      root.replaceChildren();
    },
  };
}
