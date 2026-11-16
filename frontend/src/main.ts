// Boot: load the replay list and one replay (or follow a live episode with ?live=1), then run the
// render loop. Wires src/world, src/game, src/render and src/ui together.

import { Playback } from "./game/playback";
import { Renderer } from "./render/renderer";
import { connectLive, liveAgents, startLiveRun } from "./replay/live";
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

  const params = new URLSearchParams(location.search);
  const index = await fetchJson<ReplayIndexEntry[]>(`${REPLAY_DIR}index.json`);
  let playback: Playback | null = null;
  let hud: Hud | null = null;

  function openFile(file: string): void {
    // Leaving live mode (or switching files) is a fresh page, so no stream or timers linger.
    location.search = `?replay=${encodeURIComponent(file)}`;
  }

  if (params.has("live")) {
    hudRoot.textContent = "Waiting for the live episode… start it with frontend/tools/live (see its README).";
    const agents = await liveAgents();
    let run: string | undefined;
    connectLive(
      (replay: Replay) => {
        const thisRun = replay.meta.live?.run;
        if (!playback || !hud || thisRun !== run) {
          // First episode, or a new run started (here or from another browser): fresh player and HUD,
          // keeping the speed the viewer picked.
          run = thisRun;
          const speed = playback?.speed ?? 1;
          hud?.destroy();
          playback = new Playback(replay, layout);
          playback.speed = speed;
          // Joining mid-episode: start one tick behind the agent, so you watch it decide right away.
          playback.seek(replay.ticks.length - 2);
          playback.play();
          hud = mountHud(hudRoot, replay, playback, {
            replays: index,
            currentFile: null,
            onSelectReplay: openFile,
            live: { agents, onStart: startLiveRun },
          });
          return;
        }
        playback.setReplay(replay);
        hud.setReplay(replay);
      },
      (ok) => document.body.classList.toggle("live-offline", !ok),
    );
  } else {
    const wanted = params.get("replay");
    // Saved live runs (replays/runs/, not in the index) open by name too.
    const isRun = wanted !== null && /^runs\/[\w.-]+\.json$/.test(wanted);
    const file = isRun ? wanted : (index.find((r) => r.file === wanted)?.file ?? index[0].file);
    const replay = await fetchJson<Replay>(REPLAY_DIR + file);
    playback = new Playback(replay, layout);
    hud = mountHud(hudRoot, replay, playback, { replays: index, currentFile: file, onSelectReplay: openFile });
    // ?tick=N opens the replay at that tick, e.g. to link a demo straight to the bus crash; a fraction
    // (?tick=12.45) opens part-way through the tick's animation.
    const startTick = Number(params.get("tick"));
    if (Number.isFinite(startTick) && startTick > 0) {
      playback.seek(Math.floor(startTick));
      playback.phase = startTick % 1;
    }
  }

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
