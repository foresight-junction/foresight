// Live mode: an agent plays an episode right now (frontend/tools/live) and streams every tick over
// Server-Sent Events. This folds the messages into a growing Replay the viewer can play like a file.
// Owner: lead.

import type { LiveMessage, Observation, Replay, ReplayMeta, ReplayTick } from "./types";

export const LIVE_URL = "live/stream";

export interface LiveState {
  meta: ReplayMeta | null;
  ticks: ReplayTick[]; // finished ticks
  head: ReplayTick | null; // the tick the agent is deciding now
  finalObs: Observation | null; // set once the episode is over
}

export const emptyLive = (): LiveState => ({ meta: null, ticks: [], head: null, finalObs: null });

export function applyLiveMessage(s: LiveState, msg: LiveMessage): LiveState {
  switch (msg.type) {
    case "snapshot":
      return { meta: msg.meta, ticks: [...msg.ticks], head: msg.head, finalObs: msg.final_obs };
    case "step": {
      // A tick the browser already has (a resent step after a reconnect) replaces the old copy.
      const ticks = s.ticks.filter((t) => t.tick < msg.tick.tick);
      ticks.push(msg.tick);
      return { ...s, meta: msg.meta, ticks, head: msg.head };
    }
    case "status":
      return { ...s, meta: msg.meta };
    case "done":
      return { ...s, meta: msg.meta, head: null, finalObs: msg.final_obs };
  }
}

// The replay to show, or null until the first observation exists. The head is the last tick (empty
// actions); its own observation stands in for the next one until the agent decides.
export function liveReplay(s: LiveState): Replay | null {
  if (!s.meta) return null;
  const ticks = s.head ? [...s.ticks, s.head] : s.ticks;
  if (!ticks.length) return null;
  const finalObs = s.finalObs ?? ticks[ticks.length - 1].obs;
  return { version: 1, meta: s.meta, ticks, final_obs: finalObs };
}

// Keeps one EventSource open (it reconnects by itself; the server answers every connect with a fresh
// snapshot) and reports each new replay.
export function connectLive(
  onReplay: (replay: Replay) => void,
  onConnection: (ok: boolean) => void,
): () => void {
  let state = emptyLive();
  const src = new EventSource(LIVE_URL);
  src.onopen = () => onConnection(true);
  src.onerror = () => onConnection(false);
  src.onmessage = (e: MessageEvent<string>) => {
    state = applyLiveMessage(state, JSON.parse(e.data) as LiveMessage);
    const replay = liveReplay(state);
    if (replay) onReplay(replay);
    if (state.meta?.live?.state === "done") src.close();
  };
  return () => src.close();
}
