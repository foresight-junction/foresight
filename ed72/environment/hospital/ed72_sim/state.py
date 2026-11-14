"""Mutable episode state and the coverage rule shared by the tick loop and the observation."""

from dataclasses import dataclass, field

from ed72_sim import constants as c
from ed72_sim.model import PatientSpec, World

BED_IDS: dict[str, list[str]] = {z: [f"{c.BED_PREFIX[z]}{i + 1}" for i in range(c.BEDS[z])] for z in c.ZONES}
TIRED10 = int(c.FATIGUE_TIRED * 10)
FAINT10 = int(c.FATIGUE_FAINT * 10)
REST10 = round(c.FATIGUE_REST * 10)
GAIN10 = {z: round(v * 10) for z, v in c.FATIGUE_GAIN.items()}
TIRED_TENTHS = round(c.TIRED_COUNTS_AS * 10)


@dataclass
class PatientState:
    spec: PatientSpec
    esi: int  # current ESI; an ESI 3 that upgrades becomes 2
    needs_ct: bool
    status: str = "waiting"  # waiting | bed | discharged | died | left | diverted
    zone: str | None = None
    bed: str | None = None
    admitted_tick: int = -1
    needed: int = 0  # treatment ticks, fixed at admission
    treated: int = 0
    scanned: bool = False
    ever_covered: bool = False
    covered_now: bool = False  # set in tick step 6, read in step 7


@dataclass
class StaffState:
    id: str
    role: str
    agency: bool = False
    location: str = "rest"
    fatigue10: int = 0  # tenths of a fatigue point
    status: str = "resting"  # on_shift | resting | fainted | sick | agency_ordered | agency_left
    return_tick: int | None = None  # fainted or sick: tick whose step 1 brings them back
    arrive_tick: int | None = None  # agency_ordered: tick whose step 1 brings them in
    leave_tick: int | None = None  # agency: tick whose step 1 ends the contract

    @property
    def tired(self) -> bool:
        return self.fatigue10 > TIRED10


@dataclass
class State:
    world: World
    patients: dict[str, PatientState] = field(default_factory=dict)  # arrived patients, arrival order
    staff: list[StaffState] = field(default_factory=list)
    beds: dict[str, str | None] = field(default_factory=dict)
    ct_return_tick: int | None = None  # None = CT working
    divert_last: int = -1  # last arrival tick a diversion covers
    spent: int = 0
    agency_ordered: dict[str, int] = field(default_factory=lambda: {"doctor": 0, "nurse": 0})
    totals: dict[str, int] = field(
        default_factory=lambda: {"discharged": 0, "deaths": 0, "left": 0, "diverted": 0, "faints": 0}
    )
    last_rejected: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.staff = [StaffState(s.id, s.role) for s in self.world.staff]
        self.beds = {bed: None for ids in BED_IDS.values() for bed in ids}

    @property
    def ct_working(self) -> bool:
        return self.ct_return_tick is None

    def find_staff(self, staff_id: str) -> StaffState | None:
        return next((s for s in self.staff if s.id == staff_id), None)

    def waiting(self) -> list[PatientState]:
        return [p for p in self.patients.values() if p.status == "waiting"]

    def in_beds(self, zone: str) -> list[PatientState]:
        return [self.patients[pid] for bed in BED_IDS[zone] if (pid := self.beds[bed]) is not None]

    def on_shift(self, zone: str) -> list[StaffState]:
        return [s for s in self.staff if s.status == "on_shift" and s.location == zone]

    def zone_tired(self, zone: str) -> bool:
        """Mean on-shift fatigue above 60, in integers so the threshold is exact."""
        crew = self.on_shift(zone)
        return bool(crew) and sum(s.fatigue10 for s in crew) > TIRED10 * len(crew)

    def _beds_covered(self, zone: str, role: str) -> int:
        tenths = sum(TIRED_TENTHS if s.tired else 10 for s in self.on_shift(zone) if s.role == role)
        per = c.BEDS_PER_DOCTOR[zone] if role == "doctor" else c.BEDS_PER_NURSE[zone]
        return tenths * per // 10

    def covered_ids(self) -> list[str]:
        """Covered patients this tick: the most severe first, then the earliest admitted, then bed order."""
        covered: list[str] = []
        for zone in c.ZONES:
            occupied = self.in_beds(zone)
            slots = min(self._beds_covered(zone, "doctor"), self._beds_covered(zone, "nurse"), len(occupied))
            occupied.sort(key=lambda p: (p.esi, p.admitted_tick))  # stable: ties keep bed order
            covered.extend(p.spec.id for p in occupied[:slots])
        return covered
