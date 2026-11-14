// Boot: load the replay list and one replay, then run the render loop.
// Owner: lead. Wires src/world, src/game, src/render and src/ui together.

import { Playback } from "./game/playback";
import { Renderer } from "./render/renderer";
import type { Replay, ReplayIndexEntry } from "./replay/types";
import "./style.css";
import { mountHud, type Hud } from "./ui/hud";
import { buildLayout } from "./world/layout";

const REPLAY_DIR = "replays/";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

async function start(): Promise<void> {
  const canvas = document.getElementById("game") as HTMLCanvasElement;
  const hudRoot = document.getElementById("hud") as HTMLElement;
  const layout = buildLayout();
  const renderer = new Renderer(canvas, layout);
  window.addEventListener("resize", () => renderer.resize());

  const index = await fetchJson<ReplayIndexEntry[]>(`${REPLAY_DIR}index.json`);
  const wanted = new URLSearchParams(location.search).get("replay");
  let playback: Playback | null = null;
  let hud: Hud | null = null;

  async function load(file: string): Promise<void> {
    const replay = await fetchJson<Replay>(REPLAY_DIR + file);
    hud?.destroy();
    playback = new Playback(replay, layout);
    hud = mountHud(hudRoot, replay, playback, { replays: index, currentFile: file, onSelectReplay: load });
    const url = new URL(location.href);
    url.searchParams.set("replay", file);
    history.replaceState(null, "", url);
  }

  await load(index.find((r) => r.file === wanted)?.file ?? index[0].file);

  let last = performance.now();
  const loop = (now: number): void => {
    const dt = Math.min(now - last, 100);
    last = now;
    if (playback && hud) {
      playback.update(dt);
      renderer.render(playback.frame(), now);
      hud.update();
    }
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}

start().catch((err: unknown) => {
  document.body.textContent = `ED-72 replay failed to load: ${String(err)}`;
  throw err;
});
