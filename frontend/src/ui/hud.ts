// Side panel: replay picker, clock, timeline controls, the AI's actions this tick, events, stats.
// Owner: agent E (HUD). STUB: plain text and a play button so the app runs end to end.

import type { Playback } from "../game/playback";
import type { Replay, ReplayIndexEntry } from "../replay/types";

export interface HudOptions {
  replays: ReplayIndexEntry[];
  currentFile: string;
  onSelectReplay: (file: string) => void;
}

export interface Hud {
  update(): void; // called every animation frame
  destroy(): void;
}

export function mountHud(root: HTMLElement, replay: Replay, playback: Playback, opts: HudOptions): Hud {
  root.innerHTML = "";
  const title = document.createElement("h1");
  title.textContent = `${replay.meta.label}, seed ${replay.meta.seed}, reward ${replay.meta.reward.toFixed(3)}`;
  const button = document.createElement("button");
  button.addEventListener("click", () => playback.toggle());
  const info = document.createElement("pre");
  root.append(title, button, info);
  void opts;
  return {
    update() {
      const t = playback.current();
      button.textContent = playback.playing ? "Pause" : "Play";
      info.textContent = `${t.obs.clock} (tick ${t.tick})\n` + t.actions.map((a) => JSON.stringify(a)).join("\n");
    },
    destroy() {
      root.innerHTML = "";
    },
  };
}
