from __future__ import annotations

from dataclasses import dataclass

from orc_tool.models import Boat
from orc_tool.scoring import Kind, ScoringOption


@dataclass
class Crossover:
    tws: float
    favored_below: Boat  # faster (lower sec/mile) boat for TWS just below this crossing
    favored_above: Boat


def find_crossover(
    boat_a: Boat,
    boat_b: Boat,
    option: ScoringOption,
    step: float = 0.1,
) -> list[Crossover]:
    """Scan wind speed for where the corrected-time advantage flips between two boats.

    Only meaningful for wind-speed-dependent (PCS) course options such as
    Windward/Leeward or All Purpose, since flat TOD/TOT ratings don't vary
    with wind speed and can never cross.
    """
    if option.kind != Kind.PCS:
        raise ValueError(
            f"{option.label} is a fixed rating (not wind-speed dependent); "
            "pick a PCS course option (e.g. Windward/Leeward, All Purpose) for crossover analysis"
        )

    lo = max(boat_a.polar.tws_range[0], boat_b.polar.tws_range[0])
    hi = min(boat_a.polar.tws_range[1], boat_b.polar.tws_range[1])
    if lo >= hi:
        return []

    def delta(tws: float) -> float:
        # rating_a - rating_b; negative means A is faster (fewer sec/mile)
        return boat_a.polar.allowance_field(tws, option.fieldname) - boat_b.polar.allowance_field(
            tws, option.fieldname
        )

    n_steps = max(2, int(round((hi - lo) / step)))
    samples = [lo + i * (hi - lo) / n_steps for i in range(n_steps + 1)]
    deltas = [delta(t) for t in samples]

    crossings: list[Crossover] = []
    for i in range(1, len(samples)):
        d0, d1 = deltas[i - 1], deltas[i]
        if d0 == 0:
            continue
        if (d0 < 0) != (d1 < 0):
            t0, t1 = samples[i - 1], samples[i]
            frac = d0 / (d0 - d1)
            tws_cross = t0 + frac * (t1 - t0)
            favored_below = boat_a if d0 < 0 else boat_b
            favored_above = boat_b if d0 < 0 else boat_a
            crossings.append(Crossover(tws=tws_cross, favored_below=favored_below, favored_above=favored_above))
    return crossings


def describe(crossings: list[Crossover], boat_a: Boat, boat_b: Boat, option: ScoringOption) -> str:
    if not crossings:
        lo_delta = None
        return (
            f"No crossover found for {option.label} in the {boat_a.polar.tws_range}-{boat_b.polar.tws_range} "
            "overlap: one boat is favored across the whole range."
        )
    lines = [f"Crossover wind speed(s) for {option.label}, {boat_a.name} vs {boat_b.name}:"]
    for c in crossings:
        lines.append(
            f"  ~{c.tws:.2f} kt TWS — below: {c.favored_below.name} favored, "
            f"above: {c.favored_above.name} favored"
        )
    return "\n".join(lines)
