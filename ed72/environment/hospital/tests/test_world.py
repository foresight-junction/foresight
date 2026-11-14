from ed72_sim import constants as c
from ed72_sim.world import generate_world

SEEDS = range(1, 41)


def test_same_seed_equal_and_different_seeds_differ() -> None:
    assert generate_world(7) == generate_world(7)
    assert generate_world(7) != generate_world(8)


def test_staff_roster() -> None:
    ids = [s.id for s in generate_world(1).staff]
    assert ids == [f"D{i}" for i in range(1, 7)] + [f"N{i}" for i in range(1, 10)]
    assert {s.role for s in generate_world(1).staff if s.id.startswith("D")} == {"doctor"}


def test_ids_sequential_and_sorted_by_tick() -> None:
    patients = generate_world(3).patients
    assert [p.id for p in patients] == [f"P{n:03d}" for n in range(1, len(patients) + 1)]
    ticks = [p.arrival_tick for p in patients]
    assert ticks == sorted(ticks)


def test_events_inside_windows_and_sick_nurses() -> None:
    for seed in SEEDS:
        events = {e.kind: e for e in generate_world(seed).events}
        assert list(events) == list(c.EVENTS)
        for kind, cfg in c.EVENTS.items():
            lo, hi = cfg["window"]
            assert lo <= events[kind].start_tick <= hi
            assert events[kind].duration == cfg["duration"]
            assert events[kind].warning_ticks == cfg["warning"]
        sick = events["staff_sickness"].staff
        assert len(set(sick)) == c.SICK_NURSES
        assert all(n in {f"N{i}" for i in range(1, 10)} for n in sick)
        assert list(sick) == sorted(sick)


def test_surge_patients() -> None:
    for seed in SEEDS:
        world = generate_world(seed)
        events = {e.kind: e for e in world.events}
        for source, kind, per_tick, esis in (
            ("flu", "flu_wave", c.FLU_EXTRA_PER_TICK, {3, 4, 5}),
            ("bus", "bus_crash", c.BUS_EXTRA_PER_TICK, {1, 2, 3}),
        ):
            group = [p for p in world.patients if p.source == source]
            event = events[kind]
            assert len(group) == per_tick * event.duration
            assert {p.esi for p in group} <= esis
            assert {p.arrival_tick for p in group} == set(
                range(event.start_tick, event.start_tick + event.duration)
            )


def test_patient_draws() -> None:
    for p in generate_world(2).patients:
        assert len(p.hazard_u) == c.TICKS
        assert all(0 <= u < 1 for u in p.hazard_u)
        assert 0 <= p.divert_u < 1 and 0 <= p.upgrade_ct_u < 1
        if p.esi not in c.CT_ESI:
            assert not p.needs_ct


def test_base_rate_and_ct_share() -> None:
    base_counts, high = [], []
    for seed in SEEDS:
        base = [p for p in generate_world(seed).patients if p.source == "base"]
        base_counts.append(len(base))
        high += [p for p in base if p.esi in c.CT_ESI]
    expected = c.ARRIVAL_MEAN * c.TICKS
    assert 0.85 * expected < sum(base_counts) / len(SEEDS) < 1.15 * expected
    assert 0.4 < sum(p.needs_ct for p in high) / len(high) < 0.6


def test_daily_arrival_curve() -> None:
    def base_at(seed: int, ticks: tuple[int, ...]) -> int:
        return sum(1 for p in generate_world(seed).patients if p.source == "base" and p.arrival_tick in ticks)

    # 15:00 falls on ticks 14, 62, 110; 03:00 on ticks 38, 86, 134
    assert sum(base_at(s, (14, 62, 110)) for s in SEEDS) > sum(base_at(s, (38, 86, 134)) for s in SEEDS)


def test_golden_seed_1() -> None:
    # Pinned so any silent change to draw order or stream names fails loudly.
    world = generate_world(1)
    assert len(world.patients) == 444
    first = [(p.id, p.arrival_tick, p.esi, p.needs_ct, p.source) for p in world.patients[:3]]
    assert first == [
        ("P001", 1, 4, False, "base"),
        ("P002", 1, 5, False, "base"),
        ("P003", 1, 3, False, "base"),
    ]
    assert {e.kind: e.start_tick for e in world.events} == {
        "staff_sickness": 32,
        "flu_wave": 57,
        "ct_breakdown": 71,
        "bus_crash": 105,
    }
    assert world.events[0].staff == ("N2", "N4", "N9")
