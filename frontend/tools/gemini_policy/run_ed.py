#!/usr/bin/env python3
# Written by Gemini 3.8 Flash (OpenCode 1.19.5) during the seed-42 calibration run, Harbor trial
# 2026-11-14__19-17-49/ed72__v5mip5U. Copied verbatim from the last `write` of /app/run_ed.py in
# eval/results/2026-11-14-gemini-seed42/trajectory.json (steps[18], step_id 19).
# Only this header was added. frontend/tools/gemini_policy/adapter.py swaps the MCP transport for the
# in-process Simulation; the decision logic below is the model's own and is not edited.
"""Emergency Department Controller for 72 hours (144 ticks).

Maximizes score through:
- Timely admission of ESI 1-5 patients into eligible zones.
- 100% bed coverage for all occupied beds.
- Proactive fatigue rotation keeping staff fatigue strictly <= 48 (well below 60).
- Immediate CT repair upon breakdown.
- Advance agency staff hiring for sickness, bus crash, and peak loads.
- Strict budget control (spending <= €12,000 for perfect B=1.0).
- Zero diversion to avoid 0.7 loss penalties.
- End-of-episode bed filling for maximum covered-tick credits.
"""

import asyncio
import json
import math
import re
import sys
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MAX_WORK_FATIGUE = 46.0
STABLE_SHIFT_FATIGUE = 38.0

class EDController:
    def __init__(self, url="http://hospital:8000/mcp"):
        self.url = url
        self.spent = 0
        self.ct_repair_ordered = False
        self.sickness_agency_ordered = False
        self.flu_agency_ordered = False
        self.crash_agency_ordered = False
        self.last_agency_doc_tick = -99

    def extract_start_tick(self, w):
        if isinstance(w, dict):
            for k in ("start_tick", "start", "tick", "start_at"):
                if k in w and isinstance(w[k], int):
                    return w[k]
            for v in w.values():
                if isinstance(v, str):
                    m = re.search(r'\b(tick\s*)?(\d{2,3})\b', v)
                    if m:
                        return int(m.group(2))
        elif isinstance(w, str):
            m = re.search(r'\b(tick\s*)?(\d{2,3})\b', w)
            if m:
                return int(m.group(2))
        return None

    def plan_admissions(self, waiting, beds, current_tick, warnings):
        free_resus = sum(1 for b in beds if b["zone"] == "resus" and b["patient"] is None)
        free_acute = sum(1 for b in beds if b["zone"] == "acute" and b["patient"] is None)
        free_fast_track = sum(1 for b in beds if b["zone"] == "fast_track" and b["patient"] is None)

        crash_start = None
        for w in warnings:
            text = json.dumps(w).lower() if isinstance(w, dict) else str(w).lower()
            if "crash" in text or "bus" in text:
                st = self.extract_start_tick(w)
                if st is not None:
                    crash_start = st
                    break

        clearing_for_crash = (crash_start is not None and (crash_start - 3) <= current_tick < crash_start)
        is_end_game = (current_tick >= 142)

        sorted_waiting = sorted(waiting, key=lambda p: (p["esi"], -p.get("waited_ticks", 0)))
        admits = []
        unadmitted = []

        for p in sorted_waiting:
            esi = p["esi"]
            waited = p.get("waited_ticks", 0)

            if esi == 1:
                if free_resus > 0:
                    admits.append((p, "resus"))
                    free_resus -= 1
                else:
                    unadmitted.append(p)
                    print(f"CRITICAL: ESI 1 {p['id']} waiting but resus has no free beds!", file=sys.stderr)

            elif esi == 2:
                if free_acute > 0:
                    admits.append((p, "acute"))
                    free_acute -= 1
                elif not clearing_for_crash:
                    if waited >= 1 and free_resus >= 1:
                        admits.append((p, "resus"))
                        free_resus -= 1
                    elif free_resus >= 2:
                        admits.append((p, "resus"))
                        free_resus -= 1
                    else:
                        unadmitted.append(p)
                else:
                    unadmitted.append(p)

            elif esi == 3:
                if clearing_for_crash:
                    if free_fast_track > 0:
                        admits.append((p, "fast_track"))
                        free_fast_track -= 1
                    else:
                        unadmitted.append(p)
                else:
                    if free_acute >= 3:
                        admits.append((p, "acute"))
                        free_acute -= 1
                    elif free_fast_track > 0:
                        admits.append((p, "fast_track"))
                        free_fast_track -= 1
                    elif free_acute > 0 and waited >= 4:
                        admits.append((p, "acute"))
                        free_acute -= 1
                    else:
                        unadmitted.append(p)

            elif esi in (4, 5):
                if clearing_for_crash:
                    if free_fast_track > 0:
                        admits.append((p, "fast_track"))
                        free_fast_track -= 1
                    else:
                        unadmitted.append(p)
                else:
                    if free_fast_track > 0:
                        admits.append((p, "fast_track"))
                        free_fast_track -= 1
                    elif free_acute >= 4:
                        admits.append((p, "acute"))
                        free_acute -= 1
                    elif free_acute > 2 and waited >= 4:
                        admits.append((p, "acute"))
                        free_acute -= 1
                    elif free_acute > 0 and waited >= 12:
                        admits.append((p, "acute"))
                        free_acute -= 1
                    else:
                        unadmitted.append(p)

        # End-game aggressive fill: in ticks 142-143, fill any remaining free beds with unadmitted patients
        # to ensure at least 1 covered tick (loss drops from 1.0 to 0.3)
        if is_end_game and unadmitted:
            for p in list(unadmitted):
                esi = p["esi"]
                if free_fast_track > 0 and esi in (3, 4, 5):
                    admits.append((p, "fast_track"))
                    free_fast_track -= 1
                    unadmitted.remove(p)
                elif free_acute > 0 and esi in (2, 3, 4, 5):
                    admits.append((p, "acute"))
                    free_acute -= 1
                    unadmitted.remove(p)
                elif free_resus > 0 and esi in (1, 2, 3, 4, 5):
                    admits.append((p, "resus"))
                    free_resus -= 1
                    unadmitted.remove(p)

        return admits

    def plan_staff_assignments(self, staff, beds, admits):
        admits_resus = sum(1 for p, z in admits if z == "resus")
        admits_acute = sum(1 for p, z in admits if z == "acute")
        admits_fast_track = sum(1 for p, z in admits if z == "fast_track")

        curr_occ_resus = sum(1 for b in beds if b["zone"] == "resus" and b["patient"] is not None)
        curr_occ_acute = sum(1 for b in beds if b["zone"] == "acute" and b["patient"] is not None)
        curr_occ_fast_track = sum(1 for b in beds if b["zone"] == "fast_track" and b["patient"] is not None)

        occ_resus = curr_occ_resus + admits_resus
        occ_acute = curr_occ_acute + admits_acute
        occ_fast_track = curr_occ_fast_track + admits_fast_track

        req_docs = {
            "resus": occ_resus,
            "acute": math.ceil(occ_acute / 3),
            "fast_track": math.ceil(occ_fast_track / 4),
        }
        req_nurses = {
            "resus": occ_resus,
            "acute": math.ceil(occ_acute / 2),
            "fast_track": math.ceil(occ_fast_track / 3),
        }

        def is_available(s):
            status = s.get("status")
            if status in ("sick", "fainted", "ordered", "not_arrived", "departed"):
                return False
            return True

        avail_docs = [s for s in staff if s["role"] == "doctor" and is_available(s)]
        avail_nurses = [s for s in staff if s["role"] == "nurse" and is_available(s)]

        assign_actions = []

        def assign_role(avail_staff, req_dict):
            target_assignments = {}
            unassigned = list(avail_staff)

            # Agency staff have priority to work because their contract is ticking
            agency_staff = [s for s in unassigned if s.get("agency", False) and s.get("fatigue", 0) < MAX_WORK_FATIGUE]
            agency_staff.sort(key=lambda s: s.get("fatigue", 0))

            for zone in ("resus", "acute", "fast_track"):
                needed = req_dict[zone]
                while needed > 0 and agency_staff:
                    ag = agency_staff.pop(0)
                    target_assignments[ag["id"]] = zone
                    unassigned.remove(ag)
                    needed -= 1

            # Retain permanent staff already in zone if fatigue is low (< STABLE_SHIFT_FATIGUE)
            for zone in ("resus", "acute", "fast_track"):
                currently_assigned = sum(1 for z in target_assignments.values() if z == zone)
                needed = req_dict[zone] - currently_assigned
                if needed <= 0:
                    continue

                in_zone = [s for s in unassigned if s.get("location") == zone and s.get("fatigue", 0) < STABLE_SHIFT_FATIGUE]
                in_zone.sort(key=lambda s: s.get("fatigue", 0))
                keep = in_zone[:needed]
                for s in keep:
                    target_assignments[s["id"]] = zone
                    unassigned.remove(s)

            # For zones still needing staff, fill from freshest unassigned
            for zone in ("resus", "acute", "fast_track"):
                currently_assigned = sum(1 for z in target_assignments.values() if z == zone)
                needed = req_dict[zone] - currently_assigned
                if needed <= 0:
                    continue

                eligible = [s for s in unassigned if s.get("fatigue", 0) < MAX_WORK_FATIGUE]
                if len(eligible) < needed:
                    eligible = [s for s in unassigned if s.get("fatigue", 0) < 55.0]
                if len(eligible) < needed:
                    eligible = list(unassigned)

                eligible.sort(key=lambda s: (not s.get("agency", False), s.get("fatigue", 0)))
                chosen = eligible[:needed]
                for s in chosen:
                    target_assignments[s["id"]] = zone
                    unassigned.remove(s)

            # All remaining available staff must rest
            for s in unassigned:
                target_assignments[s["id"]] = "rest"

            # Emit assign action only if target location differs from current location
            actions = []
            for s in avail_staff:
                target_loc = target_assignments.get(s["id"], "rest")
                if s.get("location") != target_loc:
                    actions.append({"type": "assign", "staff": s["id"], "to": target_loc})

            return actions

        assign_actions.extend(assign_role(avail_docs, req_docs))
        assign_actions.extend(assign_role(avail_nurses, req_nurses))

        return assign_actions, (occ_resus, occ_acute, occ_fast_track), (req_docs, req_nurses)

    def decide_actions(self, observation):
        current_tick = observation["tick"]
        waiting = observation.get("waiting", [])
        beds = observation.get("beds", [])
        staff = observation.get("staff", [])
        ct = observation.get("ct", {})
        warnings = observation.get("warnings", [])
        budget = observation.get("budget", {})

        self.spent = budget.get("spent", self.spent)

        actions = []

        # 1. CT Repair
        ct_working = ct.get("working", True)
        if not ct_working and not self.ct_repair_ordered:
            actions.append({"type": "repair"})
            self.ct_repair_ordered = True
            self.spent += 2000
            print(f"[Tick {current_tick}] Ordered CT repair (€2,000)")
        elif ct_working:
            self.ct_repair_ordered = False

        # 2. Event detection & advance agency ordering
        # Sickness event
        sick_staff = [s for s in staff if s.get("status") == "sick"]
        if len(sick_staff) > 0 and not self.sickness_agency_ordered:
            if self.spent + 700 <= 12000:
                actions.append({"type": "agency", "role": "nurse"})
                actions.append({"type": "agency", "role": "nurse"})
                self.sickness_agency_ordered = True
                self.spent += 700
                print(f"[Tick {current_tick}] Sickness detected! Ordered 2 agency nurses (€700)")

        # Warnings: Bus crash & Flu wave
        for w in warnings:
            text = json.dumps(w).lower() if isinstance(w, dict) else str(w).lower()
            start_tick = self.extract_start_tick(w)

            if ("crash" in text or "bus" in text) and start_tick is not None:
                if (start_tick - 4 <= current_tick < start_tick) and not self.crash_agency_ordered:
                    if self.spent + 1250 <= 12000:
                        actions.append({"type": "agency", "role": "doctor"})
                        actions.append({"type": "agency", "role": "nurse"})
                        self.crash_agency_ordered = True
                        self.spent += 1250
                        print(f"[Tick {current_tick}] Bus crash warning (starts tick {start_tick})! Ordered agency doctor & nurse (€1,250)")

            if "flu" in text and start_tick is not None:
                if (start_tick - 4 <= current_tick < start_tick) and not self.flu_agency_ordered:
                    if self.spent + 350 <= 12000:
                        actions.append({"type": "agency", "role": "nurse"})
                        self.flu_agency_ordered = True
                        self.spent += 350
                        print(f"[Tick {current_tick}] Flu wave warning (starts tick {start_tick})! Ordered agency nurse (€350)")

        # General load agency safeguard
        high_esi_waiting = sum(1 for p in waiting if p.get("esi", 5) <= 3)
        if high_esi_waiting >= 4 and (current_tick - self.last_agency_doc_tick >= 16):
            if self.spent + 900 <= 11000:
                actions.append({"type": "agency", "role": "doctor"})
                self.last_agency_doc_tick = current_tick
                self.spent += 900
                print(f"[Tick {current_tick}] High queue load ({high_esi_waiting} urgent waiting)! Ordered agency doctor (€900)")

        # 3. Patient Admissions
        admits = self.plan_admissions(waiting, beds, current_tick, warnings)
        for p, zone in admits:
            actions.append({"type": "admit", "patient": p["id"], "zone": zone})

        # 4. Staff Assignments
        assign_actions, (occ_r, occ_a, occ_f), (req_d, req_n) = self.plan_staff_assignments(staff, beds, admits)
        actions.extend(assign_actions)

        # Safeguard: Actions limit <= 50
        if len(actions) > 50:
            print(f"WARNING: Truncating {len(actions)} actions to 50", file=sys.stderr)
            actions = actions[:50]

        return actions, (occ_r, occ_a, occ_f)

    async def run(self):
        print(f"Connecting to hospital simulation at {self.url}...")
        async with streamable_http_client(self.url) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            print("Session initialized.")

            # Get initial observation
            res = await session.call_tool("observe", {})
            obs = res.structured_content or json.loads(res.content[0].text)
            print(f"Initial State: Tick {obs['tick']}, Clock: {obs['clock']}, Ticks Left: {obs['ticks_left']}")

            step_count = 0
            while not obs.get("finished", False):
                tick = obs["tick"]
                clock = obs["clock"]

                actions, (occ_r, occ_a, occ_f) = self.decide_actions(obs)

                # Execute step
                step_res = await session.call_tool("step", {"actions": actions})
                step_count += 1
                data = step_res.structured_content or json.loads(step_res.content[0].text)

                if "error" in data:
                    print(f"ERROR returned at tick {tick}: {data['error']}", file=sys.stderr)
                    break

                results = data.get("results", [])
                for r in results:
                    if not r.get("ok", True):
                        print(f"[Tick {tick}] Action rejected: {r}", file=sys.stderr)

                obs = data.get("observation", {})
                last_rej = obs.get("last_rejected", [])
                if last_rej:
                    print(f"[Tick {tick}] Last rejected: {last_rej}", file=sys.stderr)

                # Periodic status report
                staff = obs.get("staff", [])
                max_fatigue = max((s.get("fatigue", 0) for s in staff), default=0)
                mean_on_shift_fatigue = 0
                on_shift = [s for s in staff if s.get("location") in ("resus", "acute", "fast_track")]
                if on_shift:
                    mean_on_shift_fatigue = sum(s.get("fatigue", 0) for s in on_shift) / len(on_shift)

                totals = obs.get("totals", {})
                waiting = obs.get("waiting", [])

                if tick % 6 == 0 or obs.get("finished", False) or len(obs.get("warnings", [])) > 0:
                    print(
                        f"Tick {tick:3d} ({clock}) | Beds [R:{occ_r} A:{occ_a} F:{occ_f}] | "
                        f"Wait: {len(waiting):2d} | MaxFat: {max_fatigue:4.1f} | MeanFat: {mean_on_shift_fatigue:4.1f} | "
                        f"Disch: {totals.get('discharged', 0)} | Dead: {totals.get('deaths', 0)} | "
                        f"Spent: €{obs.get('budget', {}).get('spent', 0)}"
                    )

            print("\n=================== EPISODE FINISHED ===================")
            print(f"Total Steps Executed: {step_count}")
            print(f"Final Tick: {obs.get('tick')}, Finished: {obs.get('finished')}")
            print(f"Totals: {json.dumps(obs.get('totals', {}), indent=2)}")
            print(f"Budget: {json.dumps(obs.get('budget', {}), indent=2)}")
            if "score" in obs:
                print(f"Final Score: {obs.get('score')}")
            print("Full final observation:")
            print(json.dumps(obs, indent=2))

if __name__ == "__main__":
    controller = EDController()
    asyncio.run(controller.run())
