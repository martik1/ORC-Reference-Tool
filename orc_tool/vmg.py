from __future__ import annotations

import math
from dataclasses import dataclass

from rich.table import Table

from orc_tool.models import Boat


@dataclass
class VmgRow:
    tws: float
    beat_angle: float
    beat_speed_kt: float
    beat_vmg_kt: float
    gybe_angle: float
    run_speed_kt: float
    run_vmg_kt: float


def vmg_table(boat: Boat) -> list[VmgRow]:
    rows = []
    for tws in boat.polar.wind_speeds:
        beat_angle, beat_speed = boat.polar.optimum_upwind(tws)
        gybe_angle, run_speed = boat.polar.optimum_downwind(tws)
        rows.append(
            VmgRow(
                tws=tws,
                beat_angle=beat_angle,
                beat_speed_kt=beat_speed,
                beat_vmg_kt=beat_speed * abs(math.cos(math.radians(beat_angle))),
                gybe_angle=gybe_angle,
                run_speed_kt=run_speed,
                run_vmg_kt=run_speed * abs(math.cos(math.radians(180 - gybe_angle))),
            )
        )
    return rows


def render_table(boat: Boat, rows: list[VmgRow]) -> Table:
    table = Table(title=f"VMG / target speeds — {boat}")
    table.add_column("TWS (kt)", justify="right")
    table.add_column("Beat angle", justify="right")
    table.add_column("Beat speed (kt)", justify="right")
    table.add_column("Beat VMG (kt)", justify="right")
    table.add_column("Run angle", justify="right")
    table.add_column("Run speed (kt)", justify="right")
    table.add_column("Run VMG (kt)", justify="right")
    for r in rows:
        table.add_row(
            f"{r.tws:g}",
            f"{r.beat_angle:.1f}",
            f"{r.beat_speed_kt:.2f}",
            f"{r.beat_vmg_kt:.2f}",
            f"{r.gybe_angle:.1f}",
            f"{r.run_speed_kt:.2f}",
            f"{r.run_vmg_kt:.2f}",
        )
    return table
