// Live mode: an agent plays an episode right now (frontend/tools/live) and streams every tick over
// Server-Sent Events. This folds the messages into a growing Replay the viewer can play like a file.
// Owner: lead.

import type { LiveAgent, LiveMessage, Observation, Replay, ReplayMeta, ReplayTick } from "./types";

export const LIVE_URL = "live/stream";

// The agents the live server can run (each model only with its key), or [] if it is not running.
export async function liveAgents(): Promise<LiveAgent[]> {
  try {
    const res = await fetch("live/health");
    return res.ok ? ((await res.json()) as { agents?: LiveAgent[] }).agents ?? [] : [];
  } catch {
    return [];
  }
}

// Asks the live server for a new episode; resolves to an error message, or null once it is accepted.
// The new run then arrives on the stream as a snapshot with a new meta.live.run.
export async function startLiveRun(seed: number, agent: LiveAgent): Promise<string | null> {
  try {
    const res = await fetch("live/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seed, agent }),
    });
    if (res.ok) return null;
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    return body.error ?? `HTTP ${res.status}`;
  } catch {
    return "the live server is not running";
  }
}

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
// snapshot) and reports each new replay. It stays open after an episode ends, so a new run started
// from any browser shows up here too.
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
  };
  return () => src.close();
}
