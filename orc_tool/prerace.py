"""Pre-race intelligence: predicted time-allowance deltas against a fleet,
computed before a race starts (as opposed to `pcs.py`, which scores actual
results after the fact).

Inshore races: a known, fixed course (club marks) plus a forecast average
wind speed/direction are run through the same distance-weighted
constructed-course curve used for post-race PCS scoring, then evaluated at
the forecast TWS to get each boat's predicted rating -- no results needed.

Offshore races: ORC's Weather Routing service publishes a single
race-specific rating per boat in advance. Those are applied like a flat ToD
coefficient, cumulatively by distance-to-mark, to show the predicted gap at
every rounding.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.table import Table

from orc_tool import client
from orc_tool.compare import format_seconds
from orc_tool.course import CourseLeg, constructed_course_curve
from orc_tool.models import Boat, _interp

KNOTS_PER_MS = 1.9438444924


def to_knots(speed: float, unit: str) -> float:
    if unit == "kt":
        return speed
    if unit == "m/s":
        return speed * KNOTS_PER_MS
    raise ValueError(f"Unknown wind speed unit {unit!r}; use 'kt' or 'm/s'")


def resolve_boats(config: dict) -> tuple[list[Boat], Boat]:
    """Load every country referenced in the config and resolve the fleet
    (by sail number) plus the reference boat. Returns (boats, reference);
    `boats` always includes the reference even if it's absent from
    `config['fleet']`."""
    all_boats: list[Boat] = []
    for cc in config["countries"]:
        all_boats.extend(client.load_boats(cc))
    by_sail_no = {b.sail_no: b for b in all_boats}

    def _find(sail_no: str) -> Boat:
        if sail_no not in by_sail_no:
            raise KeyError(f"Boat {sail_no!r} not found in countries {config['countries']}")
        return by_sail_no[sail_no]

    boats = [_find(sail_no) for sail_no in config["fleet"]]
    reference = _find(config["reference"])
    if not any(b.sail_no == reference.sail_no for b in boats):
        boats = [reference, *boats]
    return boats, reference


# ---------------------------------------------------------------------------
# Inshore: constructed course + forecast TWS/direction
# ---------------------------------------------------------------------------


@dataclass
class InshoreRow:
    boat: Boat
    rating_spm: float
    delta_seconds: float  # vs reference over the course distance; + = boat receives time


def inshore_deltas(boats: list[Boat], reference: Boat, legs: list[CourseLeg], tws_kt: float) -> list[InshoreRow]:
    total_distance = sum(leg.distance_nm for leg in legs)

    def rating_at(boat: Boat) -> float:
        xs, ys = constructed_course_curve(boat, legs)
        return _interp(tws_kt, xs, ys)

    ref_rating = rating_at(reference)
    rows = [
        InshoreRow(boat=boat, rating_spm=rating, delta_seconds=(rating - ref_rating) * total_distance)
        for boat in boats
        for rating in [rating_at(boat)]
    ]
    rows.sort(key=lambda row: row.delta_seconds)
    return rows


def render_inshore_table(reference: Boat, rows: list[InshoreRow], tws_kt: float, wind_dir_deg: float) -> Table:
    table = Table(title=f"Inshore pre-race allowances @ {tws_kt:.1f} kt / {wind_dir_deg:g}° — ref {reference.name}")
    table.add_column("Boat")
    table.add_column("Sail No")
    table.add_column("Rating (s/NM)", justify="right")
    table.add_column(f"Delta vs {reference.name}", justify="right")
    for row in rows:
        is_ref = row.boat is reference
        table.add_row(
            f"[bold]{row.boat.name}[/bold]" if is_ref else row.boat.name,
            row.boat.sail_no or "",
            f"{row.rating_spm:.2f}",
            "ref" if is_ref else format_seconds(row.delta_seconds),
        )
    return table


# ---------------------------------------------------------------------------
# Offshore: published ORC Weather Routing ratings, mark by mark
# ---------------------------------------------------------------------------


@dataclass
class OffshoreMarkRow:
    mark_name: str
    distance_nm: float  # cumulative distance from the start
    deltas: dict[str, float]  # boat sail_no -> delta seconds vs reference at this mark


def offshore_deltas(
    boats: list[Boat],
    reference: Boat,
    marks: list[dict],
    wr_ratings: dict[str, float],
) -> list[OffshoreMarkRow]:
    ref_rating = wr_ratings[reference.sail_no]
    rows = []
    for mark in marks:
        deltas = {
            boat.sail_no: (wr_ratings[boat.sail_no] - ref_rating) * mark["distance_nm"] for boat in boats
        }
        rows.append(OffshoreMarkRow(mark_name=mark["name"], distance_nm=mark["distance_nm"], deltas=deltas))
    return rows


def render_offshore_table(reference: Boat, boats: list[Boat], rows: list[OffshoreMarkRow]) -> Table:
    table = Table(title=f"Offshore Weather-Routing deltas vs {reference.name}")
    table.add_column("Mark")
    table.add_column("Cum. NM", justify="right")
    for boat in boats:
        label = f"[bold]{boat.name}[/bold]" if boat is reference else boat.name
        table.add_column(label, justify="right")
    for row in rows:
        cells = [row.mark_name, f"{row.distance_nm:.1f}"]
        for boat in boats:
            cells.append("ref" if boat is reference else format_seconds(row.deltas[boat.sail_no]))
        table.add_row(*cells)
    return table
