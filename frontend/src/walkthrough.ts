import { Playback } from "./game/playback";
import { Renderer } from "./render/renderer";
import type { Replay } from "./replay/types";
import { buildLayout } from "./world/layout";
import "./walkthrough.css";

const moments = [
  {
    file: "reference-seed42.json",
    tick: 30,
    title: "Staff the first night",
    text: "A bed needs both doctor and nurse coverage before treatment progresses. The reference policy rotates staff to manage fatigue and keeps Resus available for critical arrivals.",
  },
  {
    file: "reference-seed42.json",
    tick: 66,
    title: "Respond to a CT outage",
    text: "The CT scanner breaks down with eight simulated hours until its scheduled return. The reference orders a €2,000 repair. The scanner is working again three ticks later.",
  },
  {
    file: "gemini-seed42.json",
    tick: 59,
    title: "Spot expired contracts",
    text: "In this replay of the Gemini policy, four agency staff assignments are rejected because the workers' contracts have ended. The agent can see which actions failed and why.",
  },
] as const;

const layout = buildLayout();
const canvas = document.querySelector<HTMLCanvasElement>("#floor")!;
const renderer = canvas.getContext("2d") ? new Renderer(canvas, layout) : null;
const map = document.querySelector<HTMLElement>("#map")!;
const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>(".chapters button"));
const title = document.querySelector<HTMLElement>("#scene-title")!;
const description = document.querySelector<HTMLElement>("#scene-text")!;
const status = document.querySelector<HTMLElement>("#scene-status")!;
const clock = document.querySelector<HTMLElement>("#clock")!;
const waiting = document.querySelector<HTMLElement>("#waiting")!;
const covered = document.querySelector<HTMLElement>("#covered")!;
const scanner = document.querySelector<HTMLElement>("#scanner")!;
const view = document.querySelector<HTMLAnchorElement>("#view-tick")!;
const replays = new Map<string, Promise<Playback>>();
let selected = 0;
let current: Playback | null = null;

function loadReplay(file: string): Promise<Playback> {
  const cached = replays.get(file);
  if (cached) return cached;
  const loading = fetch(`./replays/${file}`).then(async (response) => {
    if (!response.ok) throw new Error(`Replay returned HTTP ${response.status}`);
    return new Playback((await response.json()) as Replay, layout);
  });
  replays.set(file, loading);
  return loading;
}

function draw(): void {
  if (current && renderer) renderer.render(current.frame(), performance.now());
}

async function show(index: number): Promise<void> {
  const moment = moments[index];
  selected = index;
  buttons.forEach((button, i) => button.setAttribute("aria-pressed", String(i === index)));
  title.textContent = moment.title;
  description.textContent = moment.text;
  view.href = `./?replay=${moment.file}&tick=${moment.tick}`;
  current = null;
  canvas.hidden = true;
  clock.textContent = "Loading replay";
  waiting.textContent = covered.textContent = scanner.textContent = "—";
  status.textContent = "";

  try {
    const replay = await loadReplay(moment.file);
    if (selected !== index) return;
    replay.seek(moment.tick);
    const obs = replay.current().obs;
    clock.textContent = obs.clock;
    waiting.textContent = String(obs.waiting.length);
    covered.textContent = String(obs.beds.filter((bed) => bed.covered && bed.patient).length);
    scanner.textContent = obs.ct.working ? "Online" : "Offline";
    canvas.hidden = !renderer;
    canvas.setAttribute("aria-label", `Hospital floor at ${obs.clock}. ${obs.waiting.length} patients waiting.`);
    current = replay;
    if (renderer) {
      renderer.resize();
      draw();
    } else {
      status.textContent = "The floor plan is unavailable in this browser. You can still read the replay details.";
    }
  } catch {
    replays.delete(moment.file);
    if (selected !== index) return;
    clock.textContent = "Replay unavailable";
    status.textContent = "The floor plan could not load. Select a moment to try again, or open the full viewer.";
  }
}

buttons.forEach((button, index) => button.addEventListener("click", () => void show(index)));
new ResizeObserver(() => {
  renderer?.resize();
  draw();
}).observe(map);
void show(0);
