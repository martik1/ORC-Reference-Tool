from __future__ import annotations

from dataclasses import dataclass

from rich.table import Table

from orc_tool.models import Boat
from orc_tool.pcs import PcsEntry, PcsResult, score_pcs_race
from orc_tool.scoring import Kind, ScoringOption, get_allowance


@dataclass
class Leg:
    heading_deg: float  # true course over ground for this leg
    distance_nm: float


def leg_twa(heading_deg: float, wind_from_deg: float) -> float:
    """True wind angle (0-180) for sailing `heading_deg` with wind from `wind_from_deg`."""
    rel = (heading_deg - wind_from_deg + 180) % 360 - 180
    return abs(rel)


@dataclass
class CourseLeg:
    """A leg of a constructed course: distance, compass bearing, and the true
    wind direction expected on that leg (which may vary leg to leg)."""

    distance_nm: float
    bearing_deg: float
    wind_from_deg: float


def constructed_course_curve(boat: Boat, legs: list[CourseLeg]) -> tuple[list[float], list[float]]:
    """Build this boat's own time-allowance curve (s/NM) for a specific,
    named-mark course geometry, at each of its rated wind speeds.

    For each TWS, every leg's TWA is derived from that leg's bearing and
    wind direction, the boat's predicted leg time is summed across all legs,
    and the total is divided by total course distance -- a distance-weighted
    average allowance, exactly as PCS uses for the Windward/Leeward and All
    Purpose pre-defined courses, but for this course's actual leg geometry.
    """
    total_distance = sum(leg.distance_nm for leg in legs)
    values = []
    for tws in boat.polar.wind_speeds:
        total_seconds = 0.0
        for leg in legs:
            twa = leg_twa(leg.bearing_deg, leg.wind_from_deg)
            speed = boat.polar.speed_knots(tws, twa)
            total_seconds += (leg.distance_nm / speed) * 3600.0
        values.append(total_seconds / total_distance)
    return list(boat.polar.wind_speeds), values


def score_constructed_course(entries: list[PcsEntry], legs: list[CourseLeg]) -> list[PcsResult]:
    """Score actual race results against a constructed course using PCS:
    build each boat's course-specific curve, then apply Scoring Wind."""
    total_distance = sum(leg.distance_nm for leg in legs)
    return score_pcs_race(entries, total_distance, lambda boat: constructed_course_curve(boat, legs))


@dataclass
class CourseResult:
    boat: Boat
    elapsed_seconds: float
    corrected_seconds: float
    leg_speeds_kt: list[float]


def sail_course(
    boats: list[Boat],
    legs: list[Leg],
    wind_from_deg: float,
    tws: float,
    option: ScoringOption,
) -> list[CourseResult]:
    """Simulate elapsed time leg-by-leg (constant TWS/direction) then apply the
    chosen scoring option to rank boats on corrected time."""
    total_distance = sum(leg.distance_nm for leg in legs)
    results: list[CourseResult] = []
    for boat in boats:
        elapsed = 0.0
        leg_speeds = []
        for leg in legs:
            twa = leg_twa(leg.heading_deg, wind_from_deg)
            speed = boat.polar.speed_knots(tws, twa)
            leg_speeds.append(speed)
            elapsed += (leg.distance_nm / speed) * 3600.0

        rating = get_allowance(boat, option, tws if option.kind == Kind.PCS else None).value
        if option.kind == Kind.TOT:
            corrected = elapsed * rating
        else:
            corrected = elapsed - rating * total_distance

        results.append(
            CourseResult(boat=boat, elapsed_seconds=elapsed, corrected_seconds=corrected, leg_speeds_kt=leg_speeds)
        )

    results.sort(key=lambda r: r.corrected_seconds)
    return results


def _hms(seconds: float, signed: bool = False) -> str:
    sign = "-" if seconds < 0 else ("+" if signed else "")
    seconds = abs(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{sign}{h:d}:{m:02d}:{s:02d}"


def render_table(results: list[CourseResult], legs: list[Leg], wind_from_deg: float, tws: float) -> Table:
    total_distance = sum(leg.distance_nm for leg in legs)
    table = Table(title=f"Course: {len(legs)} legs, {total_distance:.1f} nm, wind from {wind_from_deg:g}° @ {tws:g} kt")
    table.add_column("Rank", justify="right")
    table.add_column("Boat")
    table.add_column("Elapsed")
    table.add_column("Corrected*")
    table.add_column("Gap to leader", justify="right")

    leader = results[0].corrected_seconds if results else 0.0
    for i, r in enumerate(results, start=1):
        gap = r.corrected_seconds - leader
        table.add_row(
            str(i),
            str(r.boat),
            _hms(r.elapsed_seconds),
            _hms(r.corrected_seconds, signed=True),
            "-" if i == 1 else f"+{_hms(gap)}",
        )
    table.caption = "*Corrected time is a relative scoring value (can be negative); only the ranking and gap matter."
    return table
