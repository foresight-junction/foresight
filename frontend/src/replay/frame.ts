// What one rendered frame contains. Playback (src/game) produces it, Renderer (src/render) draws it,
// sprites draw each entity.

import type { Esi, Location, StaffStatus, Zone } from "./types";

export interface Point {
  x: number; // map pixels, unscaled (TILE = 16 px per tile)
  y: number;
}

export type Facing = "up" | "down" | "left" | "right";

export type PatientState = "arriving" | "waiting" | "to_bed" | "in_bed" | "leaving" | "dead";

export interface PatientEntity extends Point {
  kind: "patient";
  id: string;
  esi: Esi;
  state: PatientState;
  bed: string | null; // bed id while to_bed or in_bed
  covered: boolean; // in a bed with enough staff this tick
  waitingForCt: boolean; // treatment paused, CT down
  progress: number; // treatment 0..1 while in bed, else 0
  needsCt: boolean;
  moving: boolean;
  facing: Facing;
  alpha: number; // 0..1, fades on leaving or death
}

export interface StaffEntity extends Point {
  kind: "staff";
  id: string;
  role: "doctor" | "nurse";
  agency: boolean;
  location: Location;
  status: StaffStatus;
  fatigue: number;
  moving: boolean;
  facing: Facing;
  alpha: number;
}

// An ambulance on a drop-off run: reverses into the bay, opens its rear doors, drives off nose first.
// x, y is the top-left of its 32x48 top-down sprite (nose up); y < 0 while it is still off the map.
export interface VehicleEntity extends Point {
  kind: "ambulance";
  id: string;
  doorsOpen: number; // 0 shut .. 1 rear doors fully open
  siren: boolean; // roof lights flashing
  moving: boolean;
}

export type EffectKind =
  | "arrival"
  | "admitted"
  | "discharged"
  | "death"
  | "left"
  | "diverted"
  | "upgrade"
  | "faint"
  | "spend"
  | "rejected"
  | "event_start"
  | "event_end";

export interface Effect extends Point {
  kind: EffectKind;
  age: number; // 0 just spawned .. 1 gone
  text?: string; // e.g. "-€900", "P042 died"
}

export interface Frame {
  tick: number;
  phase: number; // 0..1 progress through the current tick's animation
  patients: PatientEntity[];
  staff: StaffEntity[];
  vehicles: VehicleEntity[];
  effects: Effect[];
  ct: { working: boolean; downTicksLeft: number };
  diversion: { active: boolean; ticksLeft: number };
  activeEvents: string[]; // kinds of events running now (flu_wave, ct_breakdown, ...)
  zoneCoverage: Record<Zone, number>; // staff count_as sum on shift per zone
}
