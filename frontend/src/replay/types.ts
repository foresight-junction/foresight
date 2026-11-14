// Replay format written by frontend/tools/export_replay.py. Observation, Action, ActionResult and the
// sim events follow docs/CONTRACTS.md v1 exactly; Replay/ReplayTick/ReplayMeta are viewer-only.
// Owner: lead (leonardodadenchik-claude-1). Agents propose changes, they don't edit this file.

export type Zone = "resus" | "acute" | "fast_track";
export type Location = Zone | "rest";
export type Esi = 1 | 2 | 3 | 4 | 5;

export interface WaitingPatient {
  id: string;
  esi: Esi;
  arrived_tick: number;
  waited_ticks: number;
  needs_ct: boolean;
}

export interface Bed {
  zone: Zone;
  bed: string; // R1-R3, A1-A8, F1-F6
  patient: string | null;
  esi?: Esi;
  treated_ticks?: number;
  treatment_ticks?: number;
  covered?: boolean;
  waiting_for_ct?: boolean;
}

export type StaffStatus = "on_shift" | "resting" | "fainted" | "sick" | "agency_ordered" | "agency_left";

export interface Staff {
  id: string; // D1-D6, N1-N9, AD1.., AN1..
  role: "doctor" | "nurse";
  agency: boolean;
  location: Location;
  fatigue: number; // 0-100, faints at 90
  counts_as: number; // 1 or 0.6 above fatigue 60
  status: StaffStatus;
  ticks_until_change: number | null;
}

export interface Observation {
  tick: number;
  clock: string;
  ticks_left: number;
  finished: boolean;
  budget: { spent: number; budget: number; hard_limit: number };
  waiting: WaitingPatient[];
  beds: Bed[];
  staff: Staff[];
  ct: { working: boolean; down_ticks_left: number };
  warnings: { event: string; start_tick: number }[];
  diversion: { active: boolean; ticks_left: number };
  totals: { discharged: number; deaths: number; left: number; diverted: number; faints: number };
  last_rejected: { index: number; action: Action; reason: string }[];
}

export type Action =
  | { type: "admit"; patient: string; zone: Zone }
  | { type: "assign"; staff: string; to: Location }
  | { type: "agency"; role: "doctor" | "nurse" }
  | { type: "repair" }
  | { type: "divert" };

export interface ActionResult {
  index: number;
  ok: boolean;
  reason?: string;
}

// One line the simulator wrote during this tick (CONTRACTS "Event log", src "sim").
// event: episode_start | arrival | diverted | admitted | covered | discharged | death | upgrade |
//        left | faint | staff_fatigue | spend | event_start | event_end | episode_end
export interface SimEvent {
  seq: number;
  t: number;
  src: "sim";
  event: string;
  [field: string]: unknown;
}

export interface ReplayTick {
  tick: number;
  obs: Observation; // what the policy saw before acting (this tick's arrivals already in `waiting`)
  actions: Action[]; // what the policy chose
  results: ActionResult[]; // one per action, same order
  events: SimEvent[]; // every sim line with t === tick (arrivals before obs, outcomes after actions)
  thought?: string; // live LLM agent only: its short reasoning for this tick's actions
}

export interface ScoreSummary {
  reward: number;
  score: number;
  O: number;
  T: number;
  W: number;
  B: number;
  spend: number;
  totals: Record<string, number>;
  failures: Record<string, number>;
  [field: string]: unknown;
}

export interface ReplayMeta {
  name: string; // file stem, e.g. "reference-seed42"
  policy: string;
  label: string; // human title, e.g. "Gemini 3.8 Flash script (replayed)"
  seed: number;
  reward: number | null; // null while a live episode is still running
  score: ScoreSummary | null;
  live?: LiveStatus; // set only on a live episode streamed from frontend/tools/live
}

export interface LiveStatus {
  agent: string; // a LiveAgent; runs saved before Kimi and Claude joined say "llm" for Gemini
  model: string | null; // model id for the LLM agent
  state: "starting" | "thinking" | "acting" | "done" | "error";
  error?: string;
  run?: string; // unique per episode: a new value means the server started a new run
}

export type LiveAgent = "gemini" | "kimi" | "claude" | "reference" | "reactive";

// Server-sent events from frontend/tools/live (GET /live/stream, one JSON object per `data:` line).
// The browser keeps `ticks` (finished ticks) plus `head` (the tick the agent is deciding now: its obs
// and pre-observation events, empty actions/results) and shows Replay { ticks: [...ticks, head] }.
export type LiveMessage =
  | { type: "snapshot"; meta: ReplayMeta; ticks: ReplayTick[]; head: ReplayTick | null; final_obs: Observation | null }
  | { type: "step"; meta: ReplayMeta; tick: ReplayTick; head: ReplayTick | null }
  | { type: "status"; meta: ReplayMeta }
  | { type: "done"; meta: ReplayMeta; final_obs: Observation };

export interface Replay {
  version: 1;
  meta: ReplayMeta;
  ticks: ReplayTick[];
  final_obs: Observation; // state after the last action tick
}

// public/replays/index.json lists the available replays for the selector.
export interface ReplayIndexEntry {
  file: string; // relative to replays/, e.g. "reference-seed42.json"
  label: string;
  policy: string;
  seed: number;
  reward: number;
}
