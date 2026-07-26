"""Polar Curve Scoring: turn actual race results into corrected times.

Given a boat's actual elapsed time and the course distance, its average
speed (s/NM) is looked up on its own time-allowance curve to find the wind
speed ("Scoring Wind") that would produce that average -- the boat is scored
"as if" it sailed in that much wind. The winner is whichever boat has the
highest Scoring Wind; that wind is then used to read every other boat's
rating off its own curve, producing per-boat ToD coefficients used to
compute corrected time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from orc_tool.models import Boat, _interp


def invert_curve(xs: list[float], ys: list[float], target: float) -> float:
    """Inverse of a piecewise-linear curve ys(xs): find x such that ys(x) == target.

    Interpolation only, no extrapolation -- a target outside the curve's
    value range clamps to the nearest endpoint's x, matching how Scoring
    Wind is defined below/above the curve's wind-speed range.
    """
    for i in range(len(xs) - 1):
        y0, y1 = ys[i], ys[i + 1]
        if y0 == y1:
            if target == y0:
                return xs[i]
            continue
        if (target - y0) * (target - y1) <= 0:
            frac = (target - y0) / (y1 - y0)
            return xs[i] + frac * (xs[i + 1] - xs[i])

    decreasing = ys[0] > ys[-1]
    beyond_start = target > ys[0] if decreasing else target < ys[0]
    return xs[0] if beyond_start else xs[-1]


@dataclass
class PcsEntry:
    boat: Boat
    elapsed_seconds: float


@dataclass
class PcsResult:
    boat: Boat
    elapsed_seconds: float
    avg_seconds_per_mile: float
    scoring_wind_kt: float
    rating_at_winner_tws: float
    corrected_seconds: float


def score_pcs_race(
    entries: list[PcsEntry],
    distance_nm: float,
    curve_fn: Callable[[Boat], tuple[list[float], list[float]]],
) -> list[PcsResult]:
    """Score a race with Polar Curve Scoring.

    `curve_fn(boat)` returns that boat's (wind_speeds, seconds_per_mile)
    curve -- either a certificate PCS field (see `score_pcs_certificate`) or
    a course-specific curve (see `course.constructed_course_curve`).
    """
    prelim = []
    for entry in entries:
        xs, ys = curve_fn(entry.boat)
        avg_spm = entry.elapsed_seconds / distance_nm
        scoring_wind = invert_curve(xs, ys, avg_spm)
        prelim.append((entry, xs, ys, avg_spm, scoring_wind))

    winner_tws = max(p[4] for p in prelim)

    ratings = [(entry, avg_spm, sw, _interp(winner_tws, xs, ys)) for entry, xs, ys, avg_spm, sw in prelim]
    fastest_rating = min(rating for _, _, _, rating in ratings)

    results = [
        PcsResult(
            boat=entry.boat,
            elapsed_seconds=entry.elapsed_seconds,
            avg_seconds_per_mile=avg_spm,
            scoring_wind_kt=sw,
            rating_at_winner_tws=rating,
            corrected_seconds=entry.elapsed_seconds - (rating - fastest_rating) * distance_nm,
        )
        for entry, avg_spm, sw, rating in ratings
    ]
    results.sort(key=lambda r: r.corrected_seconds)
    return results


def score_pcs_certificate(entries: list[PcsEntry], distance_nm: float, fieldname: str) -> list[PcsResult]:
    """Score using a certificate's own PCS curve (fieldname 'WL' for
    Windward/Leeward, 'CR' for All Purpose)."""
    return score_pcs_race(
        entries,
        distance_nm,
        lambda boat: (boat.polar.wind_speeds, boat.polar.extra[fieldname]),
    )
