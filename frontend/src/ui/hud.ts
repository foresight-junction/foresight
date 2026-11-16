// Side panel styled as a pixel game HUD: replay picker and score meters, a pinned game bar
// (clock, resource counters, transport), the timeline, the AI's decisions this tick, what happened,
// department status and the episode's mistakes.

import type { Playback } from "../game/playback";
import type { LiveAgent, Observation, Replay, ReplayIndexEntry, ReplayTick, Staff, Zone } from "../replay/types";
import {
  bannersFor,
  describeActions,
  describeEvents,
  describeStaffChanges,
  describeWarnings,
  euro,
  eventName,
  scoreParts,
  zoneCapacity,
  ZONE_NAME,
  type ActionLine,
  type Banner,
  type Line,
} from "./describe";
import "./hud.css";
import { icon } from "./icons";
import { BAND_COLOR, createScrubber, MARK_COLOR } from "./scrubber";
import { findMistakes, type Band } from "./timeline";

export interface HudOptions {
  replays: ReplayIndexEntry[];
  currentFile: string | null; // null in live mode
  onSelectReplay: (file: string) => void;
  // Live mode: the agents the server can run and how to start a new run (resolves to an error or null).
  live?: { agents: LiveAgent[]; onStart: (seed: number, agent: LiveAgent) => Promise<string | null> };
}

const AGENT_LABEL: Record<LiveAgent, string> = {
  gemini: "Gemini",
  kimi: "Kimi",
  claude: "Claude",
  reference: "Reference",
  reactive: "Reactive",
};
const MAX_SEED = 2 ** 31 - 1;

export interface Hud {
  update(): void; // called every animation frame
  setReplay(replay: Replay): void; // live mode: the replay grew or its status changed
  destroy(): void;
}

const LIVE_STATE: Record<string, string> = {
  starting: "connecting to the hospital",
  thinking: "agent is thinking",
  acting: "agent is acting",
  done: "episode over",
  error: "agent error",
};

const SPEEDS = [0.25, 0.5, 1, 2, 4, 8, 16];
const ZONES: Zone[] = ["resus", "acute", "fast_track"];
const COUNT_MS = 350;
const BANNER_MS = 2000;
// At these speeds ticks change faster than the list animations, so they are switched off.
const FAST_SPEED = 8;

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function panel(title: string, cls: string, iconName?: string) {
  const root = el("section", `panel ${cls}`);
  const head = el("h2", "panel-title");
  const label = el("span", "panel-label", title);
  if (iconName) head.append(icon(iconName));
  head.append(label);
  const body = el("div", "panel-body");
  root.append(head, body);
  return { root, head, label, body };
}

// Restart a one-shot CSS animation class.
function pulse(e: HTMLElement, cls: string): void {
  e.classList.remove(cls);
  void e.offsetWidth;
  e.classList.add(cls);
}

// A number that counts to its new value over a short ease-out instead of jumping.
class Counter {
  private shown = 0;
  private from = 0;
  private to = 0;
  private t0 = 0;
  private first = true;

  constructor(
    readonly el: HTMLElement,
    private fmt: (n: number) => string,
  ) {}

  set(v: number, now: number): void {
    if (this.first) {
      this.first = false;
      this.shown = this.to = v;
      this.el.textContent = this.fmt(v);
      return;
    }
    if (v === this.to) return;
    this.from = this.shown;
    this.to = v;
    this.t0 = now;
  }

  step(now: number): void {
    if (this.shown === this.to) return;
    const k = Math.min(1, (now - this.t0) / COUNT_MS);
    this.shown = k >= 1 ? this.to : this.from + (this.to - this.from) * (1 - (1 - k) ** 3);
    this.el.textContent = this.fmt(Math.round(this.shown));
  }
}

function fatigueClass(f: number): string {
  return f >= 75 ? "fat-hi" : f > 60 ? "fat-mid" : "fat-lo";
}

function lineEl(l: Line | ActionLine, i: number): HTMLElement {
  const li = el("li", `ln tone-${l.tone}${l.esi ? ` esi-edge-${l.esi}` : ""}`);
  li.style.setProperty("--i", String(Math.min(i, 12)));
  li.append(icon(l.icon, "ln-ic"));
  const tx = el("div", "ln-tx");
  tx.append(el("div", "ln-main", l.text));
  if ("ok" in l && !l.ok) tx.append(el("div", "ln-why", l.reason ?? "rejected"));
  if (l.detail) tx.append(el("div", "ln-dt", l.detail));
  li.append(tx);
  if ("ok" in l) li.append(icon(l.ok ? "check" : "x", "ln-res"));
  return li;
}

function staffChip(s: Staff, extra?: string): HTMLElement {
  const c = el("span", `chip ${fatigueClass(s.fatigue)}${s.agency ? " agency" : ""}`);
  c.textContent = extra ? `${s.id} ${extra}` : `${s.id} ${Math.round(s.fatigue)}`;
  c.title = `${s.id}: ${s.role}${s.agency ? " (agency)" : ""}, fatigue ${s.fatigue.toFixed(1)}, ${s.status}`;
  return c;
}

function kv(label: string, value: string, cls = ""): HTMLElement {
  const row = el("div", `kv ${cls}`);
  row.append(el("span", "kv-k", label), el("span", "kv-v", value));
  return row;
}

function meter(fraction: number, cls: string): HTMLElement {
  const bar = el("div", `meter ${cls}`);
  const fill = el("div", "meter-fill");
  fill.style.width = `${Math.max(0, Math.min(1, fraction)) * 100}%`;
  bar.append(fill);
  return bar;
}

function renderStatus(body: HTMLElement, obs: Observation, active: Band[]): void {
  const out: HTMLElement[] = [];

  const wait = el("div", "esi-row");
  for (let e = 1; e <= 5; e++) {
    const n = obs.waiting.filter((w) => w.esi === e).length;
    const c = el("span", `esi-chip esi-${e}${n ? "" : " zero"}`, String(n));
    c.title = `ESI ${e}: ${n} waiting`;
    wait.append(c);
  }
  const waitRow = el("div", "kv");
  waitRow.append(el("span", "kv-k", `WAITING ${obs.waiting.length}`), wait);
  out.push(waitRow);
  if (obs.waiting.length) {
    const longest = obs.waiting.reduce((m, w) => Math.max(m, w.waited_ticks), 0);
    out.push(el("div", "sub", `longest wait ${longest} tick${longest === 1 ? "" : "s"}`));
  }

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
    if (uncovered) info.append(el("span", "bad", ` · ${uncovered} bare`));
    row.append(info);
    beds.append(row);
  }
  const bedsTitle = el("h3", "sub-title");
  bedsTitle.append(icon("bed"), document.createTextNode("BEDS"));
  out.push(bedsTitle, beds);

  const staff = el("div", "staff");
  const staffRow = (label: string, list: Staff[], opts: { stamina?: boolean; extra?: (s: Staff) => string } = {}) => {
    const row = el("div", "staff-row");
    const name = el("span", "zone-name", label);
    if (opts.stamina) {
      if (list.length) {
        const avg = list.reduce((a, s) => a + s.fatigue, 0) / list.length;
        const stamina = 1 - avg / 100;
        const m = meter(stamina, `stamina ${avg > 60 ? "low" : avg > 40 ? "mid" : ""}`);
        m.title = `stamina ${Math.round(stamina * 100)}% (average fatigue ${avg.toFixed(0)})`;
        name.append(m);
      } else name.append(meter(0, "stamina empty"));
    }
    row.append(name);
    const chips = el("span", "chips");
    if (!list.length) chips.append(el("span", "muted", "nobody"));
    for (const s of list) chips.append(staffChip(s, opts.extra?.(s)));
    row.append(chips);
    staff.append(row);
  };
  for (const z of ZONES) {
    staffRow(ZONE_NAME[z], obs.staff.filter((s) => s.status === "on_shift" && s.location === z), { stamina: true });
  }
  staffRow("Rest", obs.staff.filter((s) => s.status === "resting" || (s.status === "on_shift" && s.location === "rest")));
  const outList = obs.staff.filter((s) => s.status === "fainted" || s.status === "sick");
  if (outList.length) {
    staffRow("Out", outList, {
      extra: (s) => `${s.status === "sick" ? "sick" : "fainted"} ${s.ticks_until_change ?? "?"}t`,
    });
  }
  const ordered = obs.staff.filter((s) => s.status === "agency_ordered");
  if (ordered.length) staffRow("Coming", ordered, { extra: (s) => `in ${s.ticks_until_change ?? "?"}t` });
  const staffTitle = el("h3", "sub-title");
  staffTitle.append(icon("person"), document.createTextNode("STAFF · STAMINA & FATIGUE"));
  out.push(staffTitle, staff);

  const sys = el("div", "sys");
  const events = active.filter((b) => b.kind !== "diversion");
  sys.append(
    kv(
      "EVENTS",
      events.length ? events.map((b) => `${eventName(b.kind)} until t${b.end}`).join(", ") : "none",
      events.length ? "warn" : "",
    ),
    kv("CT SCANNER", obs.ct.working ? "working" : `DOWN · ${obs.ct.down_ticks_left} ticks left`, obs.ct.working ? "" : "bad"),
    kv(
      "DIVERSION",
      obs.diversion.active ? `ACTIVE · ${obs.diversion.ticks_left} ticks left` : "off",
      obs.diversion.active ? "warn" : "",
    ),
  );
  out.push(sys);

  body.replaceChildren(...out);
}

// Live mode: pick a seed and an agent and start a fresh episode on the live server.
function newRunForm(live: NonNullable<HudOptions["live"]>, current: Replay): HTMLElement {
  const form = el("form", "new-run");
  const seedIn = el("input", "seed-in");
  seedIn.type = "number";
  seedIn.min = "0";
  seedIn.max = String(MAX_SEED);
  seedIn.step = "1";
  seedIn.required = true;
  seedIn.value = String(current.meta.seed);
  seedIn.setAttribute("aria-label", "Seed");
  seedIn.title = "World seed: the same seed gives every agent the same patients and events";
  const agentSel = el("select", "picker");
  agentSel.setAttribute("aria-label", "Agent");
  for (const a of live.agents) {
    const o = el("option", "", AGENT_LABEL[a]);
    o.value = a;
    o.selected = a === current.meta.live?.agent;
    agentSel.append(o);
  }
  const go = el("button", "gbtn start-run", "NEW RUN");
  go.type = "submit";
  go.title = "Start a new live episode (the one playing now stops)";
  const msg = el("div", "new-run-msg");
  const random = el("button", "gbtn dice", "?");
  random.type = "button";
  random.title = "Random seed";
  random.addEventListener("click", () => {
    seedIn.value = String(Math.floor(Math.random() * 100000));
  });
  if (!live.agents.length) {
    msg.textContent = "The live server is not running: start frontend/tools/live/serve.py.";
    go.disabled = true;
  }
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const seed = Number(seedIn.value);
    if (!Number.isInteger(seed) || seed < 0 || seed > MAX_SEED) {
      msg.textContent = `Seed must be a whole number from 0 to ${MAX_SEED}.`;
      return;
    }
    go.disabled = true;
    msg.textContent = "Starting…";
    void live.onStart(seed, agentSel.value as LiveAgent).then((err) => {
      go.disabled = false;
      msg.textContent = err ? `Could not start: ${err}` : "";
    });
  });
  form.append(el("span", "new-run-l", "SEED"), seedIn, random, agentSel, go, msg);
  return form;
}

export function mountHud(root: HTMLElement, initial: Replay, playback: Playback, opts: HudOptions): Hud {
  let replay = initial;
  const hud = el("div", "hud");

  // Header: picker, label, reward and the four score meters.
  const header = el("section", "panel header");
  const pickRow = el("div", "pick-row");
  const picker = el("select", "picker");
  picker.setAttribute("aria-label", "Replay");
  const seed = initial.meta.seed;
  if (opts.currentFile === null) {
    const o = el("option", "", "● LIVE episode");
    o.value = "";
    o.selected = true;
    picker.append(o);
  } else {
    // Seed first, then the replays recorded on that seed.
    const seeds = [...new Set([seed, ...opts.replays.map((r) => r.seed)])].sort((a, b) => a - b);
    const seedSel = el("select", "picker seed-picker");
    seedSel.setAttribute("aria-label", "Seed");
    seedSel.title = "World seed: the same seed gives every policy the same patients and events";
    for (const s of seeds) {
      const o = el("option", "", `SEED ${s}`);
      o.value = String(s);
      o.selected = s === seed;
      seedSel.append(o);
    }
    seedSel.addEventListener("change", () => {
      const s = Number(seedSel.value);
      const onSeed = opts.replays.filter((r) => r.seed === s);
      const same = onSeed.find((r) => r.policy === initial.meta.policy) ?? onSeed[0];
      if (same) opts.onSelectReplay(same.file);
    });
    pickRow.append(seedSel);
    if (!opts.replays.some((r) => r.file === opts.currentFile)) {
      // A file outside the index, e.g. a saved live run.
      const r = initial.meta.reward;
      const o = el("option", "", `${initial.meta.label} · ${r === null ? "unfinished" : r.toFixed(3)}`);
      o.value = "";
      o.selected = true;
      picker.append(o);
    }
  }
  for (const r of opts.replays.filter((x) => opts.currentFile === null || x.seed === seed)) {
    const o = el("option", "", opts.currentFile === null ? `${r.label} · seed ${r.seed} · ${r.reward.toFixed(3)}` : `${r.label} · ${r.reward.toFixed(3)}`);
    o.value = r.file;
    o.selected = r.file === opts.currentFile;
    picker.append(o);
  }
  picker.addEventListener("change", () => {
    if (picker.value) opts.onSelectReplay(picker.value);
  });
  pickRow.append(picker);
  const titleRow = el("div", "title-row");
  const parts = el("div", "parts");
  header.append(pickRow);
  if (opts.live) header.append(newRunForm(opts.live, initial));
  header.append(titleRow, parts);

  function renderHeader(): void {
    const meta = replay.meta;
    const who = el("div", "who");
    who.append(el("div", "who-label", meta.label), el("div", "who-sub", `POLICY ${meta.policy} · SEED ${meta.seed}`));
    const reward = el("div", "reward");
    if (meta.reward === null || meta.score === null) {
      // Live and still running: no reward yet, a pulsing LIVE badge with the agent's state instead.
      const live = meta.live;
      reward.append(el("div", "reward-l", live?.model ?? live?.agent ?? ""), el("div", "reward-n live-badge", "● LIVE"));
      titleRow.replaceChildren(who, reward);
      const done = Math.max(0, replay.ticks.length - 1);
      const state = live ? LIVE_STATE[live.state] ?? live.state : "";
      parts.replaceChildren(
        el("div", `live-state ${live?.state ?? ""}`, live?.error ? `${state}: ${live.error}` : state),
        el("div", "parts-sum", `${done} OF 144 TICKS PLAYED · SCORE AT THE END`),
      );
      return;
    }
    reward.append(el("div", "reward-l", "FINAL REWARD"), el("div", "reward-n", meta.reward.toFixed(3)));
    titleRow.replaceChildren(who, reward);
    parts.replaceChildren();
    for (const p of scoreParts(meta.score)) {
      const row = el("div", `part part-${p.key}`);
      row.title = `${p.name} ${p.key} = ${p.value.toFixed(3)}, worth ${p.points.toFixed(1)} of ${p.max} points`;
      row.append(el("span", "part-k", p.key), el("span", "part-n", p.name.toUpperCase()), meter(p.value, "chunky"));
      row.append(el("span", "part-v", `${p.points.toFixed(1)}/${p.max}`));
      parts.append(row);
    }
    parts.append(el("div", "parts-sum", `SCORE ${meta.score.score.toFixed(1)} / 100`));
  }
  renderHeader();

  // Pinned game bar: clock, resources and transport.
  const bar = el("section", "panel gamebar");
  const banner = el("div", "banner");
  banner.setAttribute("role", "status");
  const clockRow = el("div", "clock-row");
  const time = el("div", "clock-time");
  const tickNo = el("div", "clock-tick");
  const clockLeft = el("div", "clock-left");
  clockLeft.append(icon("clock", "big"), time);
  clockRow.append(clockLeft, tickNo);

  const coinRow = el("div", "coin-row");
  const coinN = el("span", "coin-n");
  const coinBar = el("div", "coin-bar");
  const coinFill = el("div", "coin-fill");
  const coinMark = el("div", "coin-mark");
  const { budget, hard_limit } = replay.ticks[0].obs.budget;
  coinMark.style.left = `${(budget / hard_limit) * 100}%`;
  coinBar.append(coinFill, coinMark);
  coinBar.title = `Spent so far. The white notch is the ${euro(budget)} budget; the bar ends at the ${euro(hard_limit)} hard limit.`;
  coinRow.append(icon("coin", "big"), coinN, coinBar, el("span", "coin-cap", `/${euro(budget)}`));

  const res = el("div", "res-row");
  const resource = (name: string, label: string, title: string) => {
    const box = el("div", `res res-${name}`);
    box.title = title;
    const n = el("span", "res-n", "0");
    box.append(icon(name), n, el("span", "res-l", label));
    res.append(box);
    return { box, n };
  };
  const rDeaths = resource("skull", "LOST", "Patients who died");
  const rSaved = resource("heart", "SAVED", "Patients treated and discharged");
  const rFaints = resource("dizzy", "FAINTS", "Staff who fainted");
  const rLeft = resource("door", "LEFT", "Patients who gave up and left");
  const rDiv = resource("siren", "DIVERTED", "Patients turned away by diversion");
  const counters = {
    coin: new Counter(coinN, (n) => euro(n)),
    deaths: new Counter(rDeaths.n, String),
    saved: new Counter(rSaved.n, String),
    faints: new Counter(rFaints.n, String),
    left: new Counter(rLeft.n, String),
    diverted: new Counter(rDiv.n, String),
  };

  const transport = el("div", "transport");
  const btn = (iconName: string, title: string, on: () => void, cls = ""): HTMLButtonElement => {
    const b = el("button", `gbtn ${cls}`);
    b.type = "button";
    b.title = title;
    b.setAttribute("aria-label", title);
    b.append(icon(iconName));
    b.addEventListener("click", (e) => {
      on();
      // A mouse click should not leave focus on the button, or Space would press it again.
      if (e.detail > 0) b.blur();
    });
    return b;
  };
  const togglePlay = (): void => {
    if (!playback.live && !playback.playing && playback.tick >= playback.tickCount - 1) playback.seek(0);
    playback.toggle();
  };
  const playBtn = btn("play", "Play / pause (Space)", togglePlay, "play");
  transport.append(
    btn("start", "Start (Home)", () => playback.seek(0)),
    btn("stepb", "Step back (←)", () => playback.stepBack()),
    playBtn,
    btn("stepf", "Step forward (→)", () => playback.stepForward()),
    btn("end", "End (End)", () => playback.seek(playback.tickCount - 1)),
  );
  const speeds = el("div", "speeds");
  speeds.setAttribute("role", "group");
  speeds.setAttribute("aria-label", "Speed (+/-)");
  const speedBtns = SPEEDS.map((s) => {
    const b = el("button", "gbtn speed", `${s}x`);
    b.type = "button";
    b.title = `${s} ticks per second (+/-)`;
    b.addEventListener("click", (e) => {
      playback.speed = s;
      if (e.detail > 0) b.blur();
    });
    speeds.append(b);
    return b;
  });
  const controls = el("div", "controls");
  controls.append(transport, speeds);
  bar.append(banner, clockRow, coinRow, res, controls);

  // Timeline.
  const timeline = panel("Timeline", "timeline", "flag");
  let scrubber = createScrubber(replay, (t) => playback.seek(t));

  function renderTimeline(): void {
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
    timeline.body.replaceChildren(scrubber.el, legend);
  }
  renderTimeline();

  const decisions = panel("AI decisions this tick", "decisions", "cross");
  const decisionsBadge = el("span", "head-badge");
  decisions.head.append(decisionsBadge);
  const happened = panel("What happened", "happened", "bolt");
  const status = panel("Department · start of tick", "status", "bed");

  const mistakesP = panel("Mistakes", "mistakes", "skull");
  const mBadge = el("span", "head-badge");
  mistakesP.head.append(mBadge);
  let mRows: { li: HTMLElement; tick: number }[] = [];

  function renderMistakes(): void {
    const mistakes = findMistakes(replay);
    mBadge.textContent = String(mistakes.length);
    mBadge.classList.toggle("bad", mistakes.length > 0);
    const mList = el("ul", "mlist");
    mRows = mistakes.map((m) => {
      const li = el("li");
      const b = el("button", `mrow${m.esi ? ` esi-edge-${m.esi}` : ""}`);
      b.type = "button";
      b.append(el("span", "m-t", `t${m.tick}`), icon(m.icon), el("span", "m-x", m.text));
      b.addEventListener("click", () => {
        playback.pause();
        playback.seek(m.tick);
      });
      li.append(b);
      mList.append(li);
      return { li, tick: m.tick };
    });
    if (mistakes.length) mistakesP.body.replaceChildren(mList);
    else mistakesP.body.replaceChildren(el("p", "muted", "No deaths, faints or walk-outs: a clean run."));
  }
  renderMistakes();

  const help = el("p", "keys", "SPACE play · ←/→ step (SHIFT ×10) · HOME/END · +/- speed · drag the timeline");

  hud.append(header, bar, timeline.root, decisions.root, happened.root, status.root, mistakesP.root, help);
  root.replaceChildren(hud);

  let shownTick = -1;
  let shownPlaying: boolean | null = null;
  let shownSpeed = -1;
  let shownFast: boolean | null = null;
  let bannerUntil = 0;

  function showBanners(list: Banner[], now: number): void {
    if (!list.length) return;
    const worst = list.some((b) => b.tone === "bad") ? "bad" : list.some((b) => b.tone === "warn") ? "warn" : "good";
    banner.textContent = list.map((b) => b.text).join("  ");
    banner.className = `banner ${worst}`;
    pulse(banner, "show");
    bannerUntil = now + BANNER_MS;
  }

  function renderTick(now: number, first: boolean): void {
    const t = playback.current();
    const obs = t.obs;
    time.textContent = obs.clock.toUpperCase();
    tickNo.textContent = `TICK ${t.tick}/${playback.tickCount - 1}`;

    // Counters show the state after this tick's actions and outcomes, so a death and its skull
    // flash land on the same tick.
    const after = replay.ticks[t.tick + 1]?.obs ?? replay.final_obs;
    const spent = after.budget.spent;
    counters.coin.set(spent, now);
    counters.deaths.set(after.totals.deaths, now);
    counters.saved.set(after.totals.discharged, now);
    counters.faints.set(after.totals.faints, now);
    counters.left.set(after.totals.left, now);
    counters.diverted.set(after.totals.diverted, now);
    coinFill.style.width = `${Math.min(100, (spent / after.budget.hard_limit) * 100)}%`;
    coinRow.classList.toggle("over", spent > after.budget.budget);
    rDeaths.box.classList.toggle("hit", after.totals.deaths > 0);
    rFaints.box.classList.toggle("hit", after.totals.faints > 0);

    if (!first) {
      if (t.events.some((e) => e.event === "death")) pulse(rDeaths.box, "flash");
      if (t.events.some((e) => e.event === "faint")) pulse(rFaints.box, "flash");
      if (t.events.some((e) => e.event === "spend")) pulse(coinRow, "flash");
      showBanners(bannersFor(t), now);
    }

    const acts = describeActions(t);
    decisionsBadge.textContent = acts.total
      ? `${acts.total} ACTION${acts.total === 1 ? "" : "S"}${acts.rejected ? ` · ${acts.rejected} ✗` : ""}`
      : "";
    decisionsBadge.classList.toggle("bad", acts.rejected > 0);
    if (playback.live && t.tick === playback.tickCount - 1) {
      // The agent is deciding this tick right now.
      const live = replay.meta.live;
      const waiting = el("div", `thinking ${live?.state ?? ""}`);
      waiting.append(el("span", "thinking-dots"), el("span", "", live ? LIVE_STATE[live.state] ?? live.state : ""));
      decisionsBadge.textContent = "LIVE";
      decisions.body.replaceChildren(waiting);
    } else {
      renderDecisions(t, acts);
    }

    const hl = el("ul", "lines");
    const prev = replay.ticks[t.tick - 1]?.obs;
    const evs = [...describeWarnings(obs), ...describeEvents(t), ...describeStaffChanges(prev, obs)];
    evs.forEach((l, i) => hl.append(lineEl(l, i)));
    if (!evs.length) hl.append(el("li", "empty", "A quiet tick."));
    happened.body.replaceChildren(hl);

    renderStatus(
      status.body,
      obs,
      scrubber.data.bands.filter((b) => b.start <= t.tick && t.tick < b.end),
    );

    for (const r of mRows) r.li.classList.toggle("now", r.tick === t.tick);
  }

  function renderDecisions(t: ReplayTick, acts: ReturnType<typeof describeActions>): void {
    const out: HTMLElement[] = [];
    if (t.thought) {
      const q = el("blockquote", "thought");
      q.append(el("span", "thought-l", "THINKING"), el("p", "", t.thought));
      out.push(q);
    }
    const dl = el("ul", "lines");
    acts.lines.forEach((l, i) => dl.append(lineEl(l, i)));
    if (acts.kept.length) {
      dl.append(
        lineEl(
          { icon: "dot", text: `Kept ${acts.kept.length} staff where they were`, tone: "muted", detail: acts.kept.join(" ") },
          acts.lines.length,
        ),
      );
    }
    if (!acts.total) dl.append(el("li", "empty", "No actions: the AI passed this tick."));
    out.push(dl);
    decisions.body.replaceChildren(...out);
  }

  function setSpeedIndex(delta: number): void {
    let i = SPEEDS.findIndex((s) => s >= playback.speed);
    if (i < 0) i = SPEEDS.length - 1;
    playback.speed = SPEEDS[Math.max(0, Math.min(SPEEDS.length - 1, i + delta))];
  }

  const onKey = (e: KeyboardEvent): void => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const target = e.target instanceof Element ? e.target : null;
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
      const now = performance.now();
      if (playback.tick !== shownTick) {
        const first = shownTick < 0;
        shownTick = playback.tick;
        renderTick(now, first);
      }
      for (const c of Object.values(counters)) c.step(now);
      if (bannerUntil && now > bannerUntil) {
        bannerUntil = 0;
        banner.classList.remove("show");
      }
      if (playback.playing !== shownPlaying) {
        shownPlaying = playback.playing;
        playBtn.replaceChildren(icon(playback.playing ? "pause" : "play"));
        playBtn.classList.toggle("on", playback.playing);
      }
      if (playback.speed !== shownSpeed) {
        shownSpeed = playback.speed;
        speedBtns.forEach((b, i) => b.classList.toggle("on", SPEEDS[i] === playback.speed));
      }
      const fast = playback.playing && playback.speed >= FAST_SPEED;
      if (fast !== shownFast) {
        shownFast = fast;
        hud.classList.toggle("fast", fast);
      }
      scrubber.setPosition(playback.tick + (playback.playing ? Math.min(playback.phase, 1) : 0.5));
    },
    setReplay(next: Replay) {
      const grew = next.ticks.length !== replay.ticks.length;
      const oldEdge = replay.ticks.length - 1;
      replay = next;
      renderHeader();
      if (grew || !next.meta.live || next.meta.live.state === "done") {
        scrubber.destroy();
        scrubber = createScrubber(replay, (t) => playback.seek(t));
        renderTimeline();
        renderMistakes();
      }
      // Only the tick that was the live edge can change (its decision and outcomes just arrived, or the
      // agent's state changed): render it again, with the usual flashes and banners once it is played.
      // Any other tick stays as it is, so its list animations don't restart on every message.
      if (shownTick >= 0 && shownTick === playback.tick && shownTick >= oldEdge) renderTick(performance.now(), !grew);
    },
    destroy() {
      window.removeEventListener("keydown", onKey);
      scrubber.destroy();
      root.replaceChildren();
    },
  };
}
