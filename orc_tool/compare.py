from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from rich.table import Table

from orc_tool.models import Boat
from orc_tool.scoring import Kind, ScoringOption, get_allowance

"""
Time-allowance comparison.

The "allowance" reported here answers: given a fixed baseline (a course
distance for TOD/PCS options, or the reference boat's own elapsed time for
TOT options), how much MORE elapsed time is each boat allowed (or how much
LESS must it take) to tie the reference boat on corrected time?

  TOD/PCS (rating = predicted seconds/mile, lower = faster):
      CT = ET - rating * distance
      Solve ET_boat for CT_boat == CT_ref at the same distance:
      allowance_seconds = (rating_boat - rating_ref) * distance_nm
      -> positive: boat is slower, gets that many extra seconds
      -> negative: boat is faster, must finish that many seconds sooner

  TOT (TCF = time correction factor, higher = faster):
      CT = ET * TCF
      Solve ET_boat for CT_boat == CT_ref, with ET_ref = duration_min * 60:
      allowance_seconds = ET_ref * (TCF_ref / TCF_boat - 1)
"""


@dataclass
class AllowanceRow:
    boat: Boat
    rating: float
    predicted_speed_kt: Optional[float]
    allowance_seconds: float  # vs. reference; positive = boat receives time, negative = boat gives time


def compare(
    boats: list[Boat],
    reference: Boat,
    option: ScoringOption,
    tws: Optional[float] = None,
    distance_nm: Optional[float] = None,
    duration_min: Optional[float] = None,
) -> list[AllowanceRow]:
    if option.kind in (Kind.TOD, Kind.PCS):
        if distance_nm is None:
            raise ValueError(f"{option.label} needs a course distance_nm")
    elif option.kind == Kind.TOT:
        if duration_min is None:
            raise ValueError(f"{option.label} needs a duration_min (reference boat's assumed elapsed time)")

    ref_result = get_allowance(reference, option, tws)
    rows: list[AllowanceRow] = []
    for boat in boats:
        result = get_allowance(boat, option, tws)
        if option.kind == Kind.TOT:
            baseline_seconds = duration_min * 60.0
            allowance_seconds = baseline_seconds * (ref_result.value / result.value - 1.0)
        else:
            allowance_seconds = (result.value - ref_result.value) * distance_nm

        predicted_speed_kt = 3600.0 / result.value if option.kind != Kind.TOT else None
        rows.append(
            AllowanceRow(
                boat=boat,
                rating=result.value,
                predicted_speed_kt=predicted_speed_kt,
                allowance_seconds=allowance_seconds,
            )
        )

    rows.sort(key=lambda r: r.allowance_seconds)
    return rows


def format_seconds(seconds: float) -> str:
    sign = "-" if seconds < 0 else "+" if seconds > 0 else " "
    seconds = abs(seconds)
    m, s = divmod(round(seconds), 60)
    return f"{sign}{m:d}:{s:02d}"


def render_table(rows: list[AllowanceRow], reference: Boat, option: ScoringOption, tws=None) -> Table:
    unit = "sec/mile" if option.kind in (Kind.TOD, Kind.PCS) else "TCF"
    title = f"{option.label}" + (f" @ {tws:g} kt TWS" if tws is not None else "")
    table = Table(title=title)
    table.add_column("Boat")
    table.add_column("Sail No")
    table.add_column(f"Rating ({unit})", justify="right")
    if option.kind != Kind.TOT:
        table.add_column("Pred. speed (kt)", justify="right")
    table.add_column(f"Allowance vs {reference.name}", justify="right")

    for row in rows:
        is_ref = row.boat is reference
        name = f"[bold]{row.boat.name}[/bold]" if is_ref else row.boat.name
        cells = [
            name,
            row.boat.sail_no or "",
            f"{row.rating:.2f}",
        ]
        if option.kind != Kind.TOT:
            cells.append(f"{row.predicted_speed_kt:.2f}")
        cells.append("ref" if is_ref else format_seconds(row.allowance_seconds))
        table.add_row(*cells)
    return table
