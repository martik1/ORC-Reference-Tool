"""Print a boat's ORC certificate data as human-checkable matrices.

Fetches a single boat, then prints the Time Allowances (s/NM) and Rated Boat
Velocities (kn) tables across TWS 6-20kt / TWA beat..run, the Beat/Run VMG
angles, the APH/GPH/CDL headline numbers, and the universal (non-national)
single-number scoring options -- laid out so they can be checked by eye
against the boat's PDF certificate.

Usage:
    python tests/print_boat_report.py --sail-no FIN-13004
    python tests/print_boat_report.py --ref-no 03290004Q4Q
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table

from orc_tool import client
from orc_tool.models import Boat
from orc_tool.scoring import Kind, get_allowance, load_options

console = Console()

TWA_ORDER = ["Beat", 52, 60, 75, 90, 110, 120, 135, 150, "Run"]


def fetch_boat_and_options(ref_no: str | None, sail_no: str | None) -> tuple[Boat, list]:
    params = {"action": "DownBoatRMS", "ext": "json"}
    if ref_no:
        params["RefNo"] = ref_no
    if sail_no:
        params["SailNo"] = sail_no
    data = client._download(params)
    records = data.get("rms") or []
    if not records:
        raise client.OrcApiError(f"No certificate found for RefNo={ref_no!r} SailNo={sail_no!r}")
    boat = Boat.from_json(records[0])
    options = load_options(data["ScoringOptions"], country_filter="ORC", family=boat.family)
    return boat, options


def _twa_seconds_per_mile(boat: Boat, tws: float, twa) -> float:
    if twa == "Beat":
        return boat.polar._at_tws(tws, boat.polar.beat)
    if twa == "Run":
        return boat.polar._at_tws(tws, boat.polar.run)
    return boat.polar._at_tws(tws, boat.polar.r[float(twa)])


def render_matrix(boat: Boat, title: str, value_fn, fmt: str) -> Table:
    table = Table(title=title)
    table.add_column("TWA \\ TWS", justify="left")
    for tws in boat.polar.wind_speeds:
        table.add_column(f"{tws:g}", justify="right")
    for twa in TWA_ORDER:
        label = str(twa) if isinstance(twa, str) else f"{twa}°"
        row = [label]
        for tws in boat.polar.wind_speeds:
            row.append(fmt.format(value_fn(boat, tws, twa)))
        table.add_row(*row)
    return table


def render_vmg(boat: Boat) -> Table:
    table = Table(title="Beat / Run VMG")
    table.add_column("TWS", justify="right")
    table.add_column("Beat angle", justify="right")
    table.add_column("Beat VMG (kt)", justify="right")
    table.add_column("Run angle", justify="right")
    table.add_column("Run VMG (kt)", justify="right")
    for tws in boat.polar.wind_speeds:
        beat_angle, beat_vmg = boat.polar.optimum_upwind(tws)
        run_angle, run_vmg = boat.polar.optimum_downwind(tws)
        table.add_row(
            f"{tws:g}",
            f"{beat_angle:.1f}°",
            f"{beat_vmg:.2f}",
            f"{run_angle:.1f}°",
            f"{run_vmg:.2f}",
        )
    return table


def render_headline(boat: Boat) -> Table:
    table = Table(title="Headline numbers")
    table.add_column("Field")
    table.add_column("Value", justify="right")
    for name in ("GPH", "CDL"):
        table.add_row(name, str(boat.field(name)))
    return table


def render_single_number(boat: Boat, options) -> Table:
    table = Table(title="Single number scoring options (universal)")
    table.add_column("Option")
    table.add_column("Kind")
    table.add_column("Value", justify="right")
    for option in options:
        if option.kind == Kind.PCS:
            continue
        result = get_allowance(boat, option)
        table.add_row(option.name, option.kind.value, f"{result.value:.4f}")
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref-no", help="Certificate RefNo to look up")
    parser.add_argument("--sail-no", help="Sail number to look up")
    args = parser.parse_args()

    if not args.ref_no and not args.sail_no:
        parser.error("Provide --ref-no or --sail-no")

    boat, options = fetch_boat_and_options(args.ref_no, args.sail_no)

    console.print(f"[bold]{boat.name}[/bold] ({boat.sail_no}) - {boat.yacht_class}")
    console.print(render_headline(boat))
    console.print(render_matrix(boat, "Time Allowances (s/NM)", _twa_seconds_per_mile, "{:.1f}"))
    console.print(
        render_matrix(
            boat,
            "Rated Boat Velocities (kn)",
            lambda b, tws, twa: 3600.0 / _twa_seconds_per_mile(b, tws, twa),
            "{:.2f}",
        )
    )
    console.print(render_vmg(boat))
    console.print(render_single_number(boat, options))


if __name__ == "__main__":
    main()
