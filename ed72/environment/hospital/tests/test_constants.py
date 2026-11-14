from ed72_sim import constants as c


def test_full_coverage_needs_more_doctors_than_the_department_has() -> None:
    doctors = sum(-(-c.BEDS[z] // c.BEDS_PER_DOCTOR[z]) for z in c.ZONES)
    nurses = sum(-(-c.BEDS[z] // c.BEDS_PER_NURSE[z]) for z in c.ZONES)
    assert (doctors, nurses) == (8, 9)
    assert c.N_DOCTORS < doctors


def test_tables_cover_every_esi() -> None:
    for table in (c.ARRIVAL_MIX, c.TREATMENT_TICKS, c.TARGET_TICKS, c.OUTCOME_WEIGHT, c.ZONE_EXTRA_TICKS):
        assert set(table) == set(c.ESI_LEVELS)
    assert abs(sum(c.ARRIVAL_MIX.values()) - 1.0) < 1e-9
    assert abs(sum(c.FLU_MIX.values()) - 1.0) < 1e-9
    assert abs(sum(c.BUS_MIX.values()) - 1.0) < 1e-9


def test_only_resus_treats_esi_1() -> None:
    assert set(c.ZONE_EXTRA_TICKS[1]) == {"resus"}
