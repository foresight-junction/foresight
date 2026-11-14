import copy
import subprocess
import unittest
from unittest.mock import patch

from policy import ReferencePolicy, staff_plan
from reference import play, ward


def observation() -> dict:
    # MOCK: public contract fixtures are confined to tests; production always calls ward.
    return {
        "tick": 0,
        "finished": False,
        "budget": {"spent": 0, "budget": 12000, "hard_limit": 24000},
        "ct": {"working": True, "down_ticks_left": 0},
        "warnings": [],
        "waiting": [],
        "beds": [
            {"zone": zone, "bed": f"{prefix}{i}", "patient": None}
            for zone, prefix, size in (("resus", "R", 3), ("acute", "A", 8), ("fast_track", "F", 6))
            for i in range(1, size + 1)
        ],
        "staff": [
            {
                "id": f"{prefix}{i}",
                "role": role,
                "location": "rest",
                "fatigue": 0,
                "counts_as": 1,
                "status": "resting",
            }
            for role, prefix, size in (("doctor", "D", 6), ("nurse", "N", 9))
            for i in range(1, size + 1)
        ],
    }


def patient(identifier: str, esi: int, arrived: int = 0) -> dict:
    return {"id": identifier, "esi": esi, "arrived_tick": arrived, "waited_ticks": 0, "needs_ct": False}


class PolicyTests(unittest.TestCase):
    def test_severity_and_zones(self) -> None:
        obs = observation()
        obs["waiting"] = [patient("P005", 5), patient("P003", 3), patient("P001", 1), patient("P002", 2)]
        before = copy.deepcopy(obs)
        actions = ReferencePolicy().actions(obs)
        admits = [a for a in actions if a["type"] == "admit"]
        self.assertEqual([a["patient"] for a in admits], ["P001", "P002", "P003", "P005"])
        self.assertEqual([a["zone"] for a in admits], ["resus", "acute", "acute", "fast_track"])
        self.assertEqual(obs, before)

    def test_esi_two_leaves_one_resus_bed_free(self) -> None:
        obs = observation()
        obs["beds"] = [bed for bed in obs["beds"] if bed["zone"] == "resus"]
        obs["waiting"] = [patient(f"P{i}", 2) for i in range(3)]
        admits = [a for a in ReferencePolicy().actions(obs) if a["type"] == "admit"]
        self.assertEqual(len(admits), 2)
        self.assertTrue(all(a["zone"] == "resus" for a in admits))

    def test_only_coverable_patients_are_admitted(self) -> None:
        obs = observation()
        obs["staff"] = []
        obs["waiting"] = [patient("P001", 1)]
        self.assertEqual(ReferencePolicy().actions(obs), [])

    def test_sick_and_fainted_staff_never_assigned(self) -> None:
        obs = observation()
        for member in obs["staff"]:
            member["status"] = "sick" if member["role"] == "doctor" else "fainted"
        obs["waiting"] = [patient("P001", 2)]
        self.assertEqual(ReferencePolicy().actions(obs), [])

    def test_least_tired_staff_rotate_and_unused_staff_rest(self) -> None:
        obs = observation()
        obs["waiting"] = [patient("P001", 1)]
        obs["staff"][0].update(fatigue=59, location="resus", status="on_shift")
        assignments = [a for a in ReferencePolicy().actions(obs) if a["type"] == "assign"]
        self.assertIn({"type": "assign", "staff": "D1", "to": "rest"}, assignments)
        self.assertIn({"type": "assign", "staff": "D2", "to": "resus"}, assignments)

    def test_fractional_staff_coverage_rounds_down(self) -> None:
        staff = [
            {"id": "D1", "role": "doctor", "fatigue": 70, "counts_as": 0.6, "status": "resting"},
            {"id": "N1", "role": "nurse", "fatigue": 70, "counts_as": 0.6, "status": "resting"},
        ]
        _, covered = staff_plan(
            {"resus": [], "acute": [patient("P1", 2), patient("P2", 2)], "fast_track": []}, staff
        )
        self.assertEqual(covered["acute"], 1)

    def test_critical_patient_wins_when_staff_are_scarce(self) -> None:
        obs = observation()
        obs["staff"] = [obs["staff"][0], obs["staff"][6]]
        obs["waiting"] = [patient("P1", 1), patient("P2", 4), patient("P3", 4)]
        admits = [a for a in ReferencePolicy().actions(obs) if a["type"] == "admit"]
        self.assertEqual(admits, [{"type": "admit", "patient": "P1", "zone": "resus"}])

    def test_light_patients_never_block_resus(self) -> None:
        obs = observation()
        obs["waiting"] = [patient(f"P{i:03}", 4) for i in range(40)]
        actions = ReferencePolicy().actions(obs)
        self.assertFalse(any(a["type"] == "admit" and a["zone"] == "resus" for a in actions))
        self.assertLessEqual(len(actions), 50)

    def test_warning_hires_once_in_lead_window(self) -> None:
        obs = observation()
        obs["warnings"] = [{"event": "bus_crash", "start_tick": 10}]
        policy = ReferencePolicy()
        self.assertEqual(policy.actions(obs), [])
        obs["tick"] = 1
        hires = policy.actions(obs)
        self.assertEqual(len(hires), 4)
        obs["tick"] = 2
        self.assertEqual(policy.actions(obs), [])

    def test_hires_preserve_repair_reserve(self) -> None:
        obs = observation()
        obs["budget"]["spent"] = 10000
        obs["warnings"] = [{"event": "flu_wave", "start_tick": 9}]
        self.assertEqual(ReferencePolicy().actions(obs), [])

    def test_partial_warning_hires_are_not_repeated(self) -> None:
        obs = observation()
        obs["budget"]["spent"] = 9000
        obs["warnings"] = [{"event": "flu_wave", "start_tick": 9}]
        policy = ReferencePolicy()
        self.assertEqual(policy.actions(obs), [{"type": "agency", "role": "doctor"}])
        self.assertEqual(policy.actions(obs), [])

    def test_repair_order_once_and_again_for_new_breakdown(self) -> None:
        obs = observation()
        obs["ct"]["working"] = False
        policy = ReferencePolicy()
        self.assertEqual(policy.actions(obs), [{"type": "repair"}])
        obs["tick"] += 1
        self.assertEqual(policy.actions(obs), [])
        obs["ct"]["working"] = True
        policy.actions(obs)
        obs["ct"]["working"] = False
        self.assertEqual(policy.actions(obs), [{"type": "repair"}])

    def test_repair_respects_hard_limit(self) -> None:
        obs = observation()
        obs["ct"]["working"] = False
        obs["budget"]["spent"] = 23000
        self.assertEqual(ReferencePolicy().actions(obs), [])

    def test_finished_observation_is_a_noop(self) -> None:
        obs = observation()
        obs["finished"] = True
        self.assertEqual(ReferencePolicy().actions(obs), [])


class RunnerTests(unittest.TestCase):
    def test_full_144_step_contract_loop(self) -> None:
        calls = []
        obs = observation()

        def call(tool: str, arguments: dict) -> dict:
            calls.append(tool)
            if tool == "rules":
                return {"text": "MOCK: fixture rules"}
            if tool == "observe":
                return copy.deepcopy(obs)
            self.assertEqual(arguments, {"actions": []})
            if obs["tick"] == 143:
                obs["finished"] = True
            else:
                obs["tick"] += 1
            return {"results": [], "observation": copy.deepcopy(obs)}

        final = play(call)
        self.assertTrue(final["finished"])
        self.assertEqual(calls, ["rules", "observe"] + ["step"] * 144)

    def test_rejected_action_stops_runner(self) -> None:
        obs = observation()
        with self.assertRaisesRegex(RuntimeError, "rejected"):
            play(
                lambda tool, args: (
                    obs if tool == "observe" else {"results": [{"ok": False}], "observation": obs}
                )
            )

    def test_nonadvancing_tick_stops_runner(self) -> None:
        obs = observation()
        with self.assertRaisesRegex(RuntimeError, "advance"):
            play(lambda tool, args: obs if tool == "observe" else {"results": [], "observation": obs})

    def test_ward_arguments_use_argv_and_parse_json(self) -> None:
        with patch("reference.subprocess.run") as run:
            run.return_value.stdout = '{"finished": true}'
            self.assertEqual(ward("step", {"actions": []}), {"finished": True})
            self.assertEqual(run.call_args.args[0], ["ward", "step", "--json", '{"actions": []}'])
            self.assertTrue(run.call_args.kwargs["check"])

    def test_ward_nonzero_exit_includes_diagnostic(self) -> None:
        failure = subprocess.CalledProcessError(1, ["ward"], output="", stderr="hospital unavailable")
        with (
            patch("reference.subprocess.run", side_effect=failure),
            self.assertRaisesRegex(RuntimeError, "hospital unavailable"),
        ):
            ward("observe", {})

    def test_ward_tool_error_stops_runner(self) -> None:
        with patch("reference.subprocess.run") as run:
            run.return_value.stdout = '{"error": "call_cap_reached"}'
            with self.assertRaisesRegex(RuntimeError, "call_cap_reached"):
                ward("step", {"actions": []})


if __name__ == "__main__":
    unittest.main()
