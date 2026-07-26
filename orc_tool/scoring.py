from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Union

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
    country_filter: Union[str, Iterable[str], None] = "ORC",
    family: Optional[str] = None,
) -> list[ScoringOption]:
    """Build the selectable course/scoring option catalog.

    By default only the universal `CountryId == "ORC"` options are returned
    (All Purpose, Windward/Leeward, ...). Pass a country code (or an iterable
    of codes, e.g. the countries you've loaded boats from) to also include
    that country's local scoring options (Triple Number, Single Number,
    national variants, ...); pass country_filter=None to include every
    country's options (~675 entries).
    """
    if isinstance(country_filter, str) or country_filter is None:
        allowed = {country_filter} if country_filter is not None else None
    else:
        allowed = set(country_filter)

    options = []
    seen = set()
    for o in scoring_options_json:
        if allowed is not None and o["CountryId"] not in allowed:
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


# Standard ORC wind-strength distribution for deriving a single-number ToD
# coefficient from a boat's PCS curve (see certificate "How is it calculated?").
DEFAULT_TOD_WIND_WEIGHTS: dict[float, float] = {
    6: 0.05,
    8: 0.10,
    10: 0.20,
    12: 0.30,
    14: 0.20,
    16: 0.10,
    20: 0.05,
}


def custom_tod_coefficient(
    boat: Boat, fieldname: str, weights: dict[float, float] = None
) -> float:
    """Derive a single-number ToD coefficient (s/NM) from a boat's PCS curve
    (fieldname 'WL' for Windward/Leeward, 'CR' for All Purpose) as a weighted
    average over a wind-speed distribution. Defaults to the standard ORC
    distribution; pass a custom `weights` dict (TWS -> fraction) for a
    race-specific wind forecast/history.
    """
    weights = weights or DEFAULT_TOD_WIND_WEIGHTS
    total_weight = sum(weights.values())
    weighted_sum = sum(w * boat.polar.allowance_field(tws, fieldname) for tws, w in weights.items())
    return weighted_sum / total_weight


def tod_to_tot(tod_coefficient: float, conversion_factor: float = 600.0) -> float:
    """Convert a Time-on-Distance coefficient (s/NM) to Time-on-Time (ToT = factor / ToD)."""
    return conversion_factor / tod_coefficient


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
