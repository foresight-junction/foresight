import { Playback } from "./game/playback";
import { Renderer } from "./render/renderer";
import type { Replay } from "./replay/types";
import { buildLayout } from "./world/layout";
import "./walkthrough.css";

const REFERENCE = "reference-seed42.json";
const moments = [
  {
    file: REFERENCE,
    policy: "Scripted reference",
    from: 30,
    to: 34,
    title: "Staff the first night",
    text: "Treatment needs both doctor and nurse coverage. The reference policy rotates staff and keeps Resus available for the most urgent arrivals.",
  },
  {
    file: "gemini-seed42.json",
    policy: "Gemini script replay",
    from: 59,
    to: 62,
    title: "Four assignments fail",
    text: "Gemini’s script assigns two agency doctors and two agency nurses whose contracts have ended. The simulator rejects all four assignments. Step forward to see the script try them again.",
  },
  {
    file: REFERENCE,
    policy: "Scripted reference",
    from: 66,
    to: 69,
    title: "Repair the CT scanner",
    text: "The scanner is due to be down for eight simulated hours. The reference spends €2,000 on a repair and the scanner comes back three ticks later.",
  },
] as const;

const layout = buildLayout();
const canvas = document.querySelector<HTMLCanvasElement>("#floor")!;
const renderer = canvas.getContext("2d") ? new Renderer(canvas, layout) : null;
const map = document.querySelector<HTMLElement>("#map")!;
const chapters = Array.from(document.querySelectorAll<HTMLButtonElement>(".chapters button"));
const title = document.querySelector<HTMLElement>("#scene-title")!;
const description = document.querySelector<HTMLElement>("#scene-text")!;
const status = document.querySelector<HTMLElement>("#scene-status")!;
const policy = document.querySelector<HTMLElement>("#policy")!;
const clock = document.querySelector<HTMLElement>("#clock")!;
const waiting = document.querySelector<HTMLElement>("#waiting")!;
const covered = document.querySelector<HTMLElement>("#covered")!;
const scanner = document.querySelector<HTMLElement>("#scanner")!;
const rejections = document.querySelector<HTMLElement>("#rejections")!;
const rejectedCount = rejections.querySelector("dd")!;
const view = document.querySelector<HTMLAnchorElement>("#view-tick")!;
const timeline = document.querySelector<HTMLInputElement>("#timeline")!;
const play = document.querySelector<HTMLButtonElement>("#play")!;
const back = document.querySelector<HTMLButtonElement>("#back")!;
const forward = document.querySelector<HTMLButtonElement>("#forward")!;
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
const replays = new Map<string, Promise<Playback>>();
let request = 0;
let current: Playback | null = null;
let animation = 0;

function loadReplay(file: string): Promise<Playback> {
  const cached = replays.get(file);
  if (cached) return cached;
  const loading = fetch(`./replays/${file}`).then(async (response) => {
    if (!response.ok) throw new Error(`Replay returned HTTP ${response.status}`);
    return new Playback((await response.json()) as Replay, layout);
  }).catch((error: unknown) => {
    replays.delete(file);
    throw error;
  });
  replays.set(file, loading);
  return loading;
}

function draw(now = performance.now()): void {
  if (current && renderer) renderer.render(current.frame(), now);
}

function renderTick(): void {
  if (!current) return;
  const { obs, actions, results } = current.current();
  const rejected = results.filter(({ index, ok }) => !ok && actions[index]?.type === "assign").length;
  clock.textContent = obs.clock;
  waiting.textContent = String(obs.waiting.length);
  covered.textContent = String(obs.beds.filter((bed) => bed.covered && bed.patient).length);
  scanner.textContent = obs.ct.working ? "Online" : "Offline";
  rejections.hidden = rejected === 0;
  rejectedCount.textContent = String(rejected);
  timeline.value = String(current.tick);
  timeline.setAttribute("aria-valuetext", obs.clock);
  canvas.setAttribute("aria-label", `Hospital floor at ${obs.clock}. ${obs.waiting.length} patients waiting.`);
  const url = new URL(view.href);
  url.searchParams.set("tick", String(current.tick));
  view.href = url.href;
  back.disabled = current.tick === Number(timeline.min);
  forward.disabled = current.tick === Number(timeline.max);
}

function pause(): void {
  cancelAnimationFrame(animation);
  current?.pause();
  play.textContent = "Play clip";
}

function seek(tick: number): void {
  pause();
  current?.seek(tick);
  renderTick();
  draw();
}

async function show(index: number): Promise<void> {
  const moment = moments[index];
  const pending = ++request;
  pause();
  current = null;
  chapters.forEach((button, i) => button.setAttribute("aria-pressed", String(i === index)));
  policy.textContent = `${moment.policy} · Seed 42`;
  title.textContent = moment.title;
  description.textContent = moment.text;
  view.href = `./?replay=${moment.file}&tick=${moment.from}`;
  canvas.hidden = true;
  clock.textContent = "Loading replay";
  waiting.textContent = covered.textContent = scanner.textContent = "—";
  timeline.disabled = play.disabled = back.disabled = forward.disabled = true;
  status.textContent = "";
  rejections.hidden = true;

  try {
    const replay = await loadReplay(moment.file);
    if (pending !== request) return;
    current = replay;
    timeline.min = String(moment.from);
    timeline.max = String(moment.to);
    timeline.disabled = false;
    play.disabled = !renderer;
    canvas.hidden = !renderer;
    renderer?.resize();
    seek(moment.from);
    if (!renderer) status.textContent = "The floor plan is unavailable. You can still step through the replay.";
  } catch {
    if (pending !== request) return;
    clock.textContent = "Replay unavailable";
    status.textContent = "The replay could not load. Select this chapter to try again.";
  }
}

play.addEventListener("click", () => {
  if (!current) return;
  if (current.playing) {
    pause();
    return;
  }
  const end = Number(timeline.max);
  if (current.tick === end) seek(Number(timeline.min));
  current.play();
  play.textContent = "Pause clip";
  let last = performance.now();
  const loop = (now: number): void => {
    if (!current) return;
    const tick = current.tick;
    current.update(Math.min(now - last, 100));
    last = now;
    if (current.tick >= end) {
      seek(end);
      return;
    }
    if (current.tick !== tick) renderTick();
    if (!reduceMotion.matches || current.tick !== tick) draw(now);
    animation = requestAnimationFrame(loop);
  };
  animation = requestAnimationFrame(loop);
});

back.addEventListener("click", () => seek(timeline.valueAsNumber - 1));
forward.addEventListener("click", () => seek(timeline.valueAsNumber + 1));
timeline.addEventListener("input", () => seek(timeline.valueAsNumber));
chapters.forEach((button, index) => button.addEventListener("click", () => void show(index)));

new ResizeObserver(() => {
  if (!current) return;
  renderer?.resize();
  draw();
}).observe(map);
void show(0);
