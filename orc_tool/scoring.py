from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from orc_tool.models import Boat


class Kind(str, Enum):
    TOD = "TOD"  # time-on-distance: seconds/mile, lower = faster
    TOT = "TOT"  # time-on-time: multiplier, higher = faster
    PCS = "PCS"  # performance curve scoring: wind-speed-dependent seconds/mile


@dataclass(frozen=True)
class ScoringOption:
    name: str
    kind: Kind
    fieldname: str
    country_id: str
    families: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"{self.name} [{self.kind.value}]"


def load_options(
    scoring_options_json: list[dict],
    country_filter: Optional[str] = "ORC",
    family: Optional[str] = None,
) -> list[ScoringOption]:
    """Build the selectable course/scoring option catalog.

    By default only the universal `CountryId == "ORC"` options are returned
    (All Purpose, Windward/Leeward, ...). Pass country_filter=None to include
    every country's options (~675 entries), or a specific NatAuth code to add
    that country's local scoring options.
    """
    options = []
    seen = set()
    for o in scoring_options_json:
        if country_filter is not None and o["CountryId"] != country_filter:
            continue
        if family is not None and o.get("Families") and family not in o["Families"]:
            continue
        key = (o["Name"], o["Kind"], o["Fieldname"])
        if key in seen:
            continue
        seen.add(key)
        options.append(
            ScoringOption(
                name=o["Name"],
                kind=Kind(o["Kind"]),
                fieldname=o["Fieldname"],
                country_id=o["CountryId"],
                families=tuple(o.get("Families", [])),
            )
        )
    return options


@dataclass
class AllowanceResult:
    option: ScoringOption
    value: float  # seconds/mile for TOD/PCS, multiplier for TOT


def get_allowance(boat: Boat, option: ScoringOption, tws: Optional[float] = None) -> AllowanceResult:
    if option.kind == Kind.PCS:
        if tws is None:
            raise ValueError(f"{option.label} is wind-speed dependent; a TWS value is required")
        value = boat.polar.allowance_field(tws, option.fieldname)
    else:
        value = boat.field(option.fieldname)
        if value is None:
            raise KeyError(f"{boat.name} has no rating for {option.label} (field {option.fieldname!r})")
    return AllowanceResult(option=option, value=float(value))
