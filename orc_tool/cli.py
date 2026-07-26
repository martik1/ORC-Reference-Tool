from __future__ import annotations

import argparse
import sys

from rich.console import Console

from orc_tool import client, compare, course, courseplot, crossover, polar, prerace, vmg
from orc_tool.models import Boat
from orc_tool.scoring import Kind, ScoringOption, load_options

console = Console()


def _load_all_boats(country_ids: list[str]) -> list[Boat]:
    boats: list[Boat] = []
    for cc in country_ids:
        with console.status(f"Fetching {cc} certificates..."):
            boats.extend(client.load_boats(cc))
        console.print(f"[green]Loaded {cc}[/green]: {sum(1 for b in boats if b.country == cc)} boats")
    return boats


def _catalog(country_ids: list[str]) -> list[dict]:
    # ScoringOptions catalog is identical across countries' responses; reuse the first one.
    data = client.fetch_country(country_ids[0])
    return data["ScoringOptions"]


def _build_options(catalog: list[dict], country_ids: list[str]) -> list[ScoringOption]:
    """Universal ORC options (All Purpose, Windward/Leeward, ...) plus each loaded
    country's own local options (Triple Number, Single Number, national variants)."""
    return load_options(catalog, country_filter=["ORC", *country_ids])


def _prompt_distance_or_duration(option: ScoringOption) -> dict:
    import questionary

    if option.kind == Kind.TOT:
        minutes = float(questionary.text("Reference boat's assumed race duration (minutes):").ask())
        return {"duration_min": minutes}
    nm = float(questionary.text("Course distance (nautical miles):").ask())
    return {"distance_nm": nm}


def run_compare(boats, reference, option, tws, **kwargs):
    rows = compare.compare(boats, reference, option, tws=tws, **kwargs)
    table = compare.render_table(rows, reference, option, tws=tws)
    console.print(table)
    return rows


def interactive_main():
    import questionary

    console.print("[bold]ORC Time Allowance & Polar Tool[/bold]")
    countries_raw = questionary.text(
        "Country code(s) to load certificates from (comma-separated, e.g. FIN,SWE):"
    ).ask()
    if not countries_raw:
        console.print("[red]No countries given, exiting.[/red]")
        return
    country_ids = [c.strip().upper() for c in countries_raw.split(",") if c.strip()]
    all_boats = _load_all_boats(country_ids)
    if not all_boats:
        console.print("[red]No boats loaded.[/red]")
        return

    catalog = _catalog(country_ids)
    options = _build_options(catalog, country_ids)

    while True:
        query = questionary.text("Search boats by name/sail number (blank = show all):").ask() or ""
        matches = client.search_boats(query, all_boats)
        if not matches:
            console.print("[yellow]No matches, try again.[/yellow]")
            continue
        choices = [questionary.Choice(title=str(b), value=b) for b in matches]
        selected = questionary.checkbox("Select boats to compare:", choices=choices).ask()
        if selected:
            break
        console.print("[yellow]Pick at least one boat.[/yellow]")

    reference = questionary.select(
        "Which boat is the reference (time allowances shown relative to this boat)?",
        choices=[questionary.Choice(title=str(b), value=b) for b in selected],
    ).ask()

    option = questionary.select(
        "Course / scoring option:",
        choices=[questionary.Choice(title=o.label, value=o) for o in options],
    ).ask()

    tws = float(questionary.text("True wind speed (kt):").ask())
    extra = _prompt_distance_or_duration(option)

    rows = run_compare(selected, reference, option, tws, **extra)

    while True:
        action = questionary.select(
            "What next?",
            choices=[
                "Plot polar diagram",
                "VMG / target speed table",
                "Crossover wind speed (pick 2 boats)",
                "Multi-leg course simulator",
                "Re-run comparison with new wind speed / distance",
                "Quit",
            ],
        ).ask()

        if action == "Plot polar diagram":
            polar.plot_polar(selected, tws, highlight=reference)

        elif action == "VMG / target speed table":
            target = questionary.select(
                "Boat:", choices=[questionary.Choice(title=str(b), value=b) for b in selected]
            ).ask()
            console.print(vmg.render_table(target, vmg.vmg_table(target)))

        elif action == "Crossover wind speed (pick 2 boats)":
            if len(selected) < 2:
                console.print("[yellow]Need at least 2 boats.[/yellow]")
                continue
            pcs_options = [o for o in options if o.kind == Kind.PCS]
            a = questionary.select(
                "Boat A:", choices=[questionary.Choice(title=str(b), value=b) for b in selected]
            ).ask()
            b = questionary.select(
                "Boat B:", choices=[questionary.Choice(title=str(b), value=b) for b in selected if b is not a]
            ).ask()
            xo_option = questionary.select(
                "Course option (must be wind-speed dependent):",
                choices=[questionary.Choice(title=o.label, value=o) for o in pcs_options],
            ).ask()
            crossings = crossover.find_crossover(a, b, xo_option)
            console.print(crossover.describe(crossings, a, b, xo_option))

        elif action == "Multi-leg course simulator":
            legs = []
            console.print("Enter legs as 'heading,distance_nm', blank line to finish.")
            while True:
                raw = questionary.text(f"Leg {len(legs) + 1} (heading,distance) or blank to stop:").ask()
                if not raw:
                    break
                heading_str, dist_str = raw.split(",")
                legs.append(course.Leg(heading_deg=float(heading_str), distance_nm=float(dist_str)))
            if not legs:
                continue
            wind_from = float(questionary.text("True wind direction (deg, FROM):").ask())
            leg_option = questionary.select(
                "Scoring option for corrected results:",
                choices=[questionary.Choice(title=o.label, value=o) for o in options],
            ).ask()
            results = course.sail_course(selected, legs, wind_from, tws, leg_option)
            console.print(course.render_table(results, legs, wind_from, tws))

        elif action == "Re-run comparison with new wind speed / distance":
            tws = float(questionary.text("True wind speed (kt):").ask())
            extra = _prompt_distance_or_duration(option)
            rows = run_compare(selected, reference, option, tws, **extra)

        else:
            break


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ORC time-allowance & polar comparison tool")
    p.add_argument("--countries", help="Comma-separated country codes to load (non-interactive mode)")
    p.add_argument("--boats", help="Comma-separated search terms; first match each is selected")
    p.add_argument("--reference", help="Search term for the reference boat")
    p.add_argument("--option-name", help="Scoring option name, e.g. 'Windward/Leeward'")
    p.add_argument("--option-kind", choices=["TOD", "TOT", "PCS"], help="Scoring option kind")
    p.add_argument("--tws", type=float, help="True wind speed (kt)")
    p.add_argument("--distance", type=float, help="Course distance (nm), for TOD/PCS options")
    p.add_argument("--duration", type=float, help="Reference boat's elapsed time (min), for TOT options")
    p.add_argument("--plot", action="store_true", help="Also show a polar plot of the selected boats")
    p.add_argument("--vmg", action="store_true", help="Also print the reference boat's VMG table")

    subparsers = p.add_subparsers(dest="command")
    prerace_p = subparsers.add_parser(
        "prerace", help="Predicted time-allowance deltas against a fleet, before a race"
    )
    prerace_p.add_argument("--config", required=True, help="Path to a prerace YAML config (see prerace.example.yaml)")
    prerace_p.add_argument("--inshore", help="Name of an inshore_courses entry in the config")
    prerace_p.add_argument("--offshore", help="Name of an offshore_courses entry in the config")
    prerace_p.add_argument("--tws", type=float, help="Forecast average true wind speed (inshore only)")
    prerace_p.add_argument(
        "--wind-unit", choices=["kt", "m/s"], default="kt", help="Unit for --tws (default: kt)"
    )
    prerace_p.add_argument("--wind-dir", type=float, help="Forecast average true wind direction, FROM, in degrees (inshore only)")
    prerace_p.add_argument("--plot", action="store_true", help="Also show a diagram of the selected course")
    prerace_p.add_argument("--plot-out", help="Save the course diagram to this path instead of/as well as showing it")
    return p


def run_prerace(args: argparse.Namespace):
    import yaml

    with open(args.config, encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    with console.status("Loading fleet certificates..."):
        boats, reference = prerace.resolve_boats(config)

    if args.inshore:
        if args.tws is None or args.wind_dir is None:
            console.print("[red]--inshore requires --tws and --wind-dir[/red]")
            sys.exit(1)
        available = config.get("inshore_courses", {})
        if args.inshore not in available:
            console.print(
                f"[red]No inshore course named {args.inshore!r} in {args.config}[/red]"
                f" (available: {', '.join(sorted(available)) or 'none'})"
            )
            sys.exit(1)
        course_cfg = available[args.inshore]
        tws_kt = prerace.to_knots(args.tws, args.wind_unit)
        legs = [
            course.CourseLeg(
                distance_nm=leg["distance_nm"], bearing_deg=leg["bearing_deg"], wind_from_deg=args.wind_dir
            )
            for leg in course_cfg["legs"]
        ]
        rows = prerace.inshore_deltas(boats, reference, legs, tws_kt)
        console.print(prerace.render_inshore_table(reference, rows, tws_kt, args.wind_dir))
        if args.plot or args.plot_out:
            courseplot.plot_inshore_course(legs, show=args.plot, save_path=args.plot_out)
    elif args.offshore:
        available = config.get("offshore_courses", {})
        if args.offshore not in available:
            console.print(
                f"[red]No offshore course named {args.offshore!r} in {args.config}[/red]"
                f" (available: {', '.join(sorted(available)) or 'none'})"
            )
            sys.exit(1)
        course_cfg = available[args.offshore]
        rows = prerace.offshore_deltas(boats, reference, course_cfg["marks"], course_cfg["wr_ratings"])
        console.print(prerace.render_offshore_table(reference, boats, rows))
        if args.plot or args.plot_out:
            courseplot.plot_offshore_course(course_cfg["marks"], show=args.plot, save_path=args.plot_out)
    else:
        console.print("[red]Specify --inshore NAME or --offshore NAME[/red]")
        sys.exit(1)


def non_interactive_main(args: argparse.Namespace):
    country_ids = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
    all_boats = _load_all_boats(country_ids)

    search_terms = [s.strip() for s in args.boats.split(",") if s.strip()]
    selected = []
    for term in search_terms:
        matches = client.search_boats(term, all_boats)
        if not matches:
            console.print(f"[red]No boat matches {term!r}[/red]")
            sys.exit(1)
        selected.append(matches[0])

    ref_matches = client.search_boats(args.reference, selected)
    if not ref_matches:
        console.print(f"[red]Reference {args.reference!r} not among selected boats[/red]")
        sys.exit(1)
    reference = ref_matches[0]

    catalog = _catalog(country_ids)
    options = load_options(catalog, country_filter="ORC")
    matching_options = [
        o for o in options if o.name == args.option_name and (not args.option_kind or o.kind.value == args.option_kind)
    ]
    if not matching_options:
        console.print(f"[red]No scoring option named {args.option_name!r} (kind={args.option_kind})[/red]")
        console.print("Available: " + ", ".join(sorted({o.label for o in options})))
        sys.exit(1)
    option = matching_options[0]

    extra = {}
    if option.kind == Kind.TOT:
        extra["duration_min"] = args.duration
    else:
        extra["distance_nm"] = args.distance

    run_compare(selected, reference, option, args.tws, **extra)

    if args.vmg:
        console.print(vmg.render_table(reference, vmg.vmg_table(reference)))
    if args.plot:
        polar.plot_polar(selected, args.tws, highlight=reference)


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    if getattr(args, "command", None) == "prerace":
        run_prerace(args)
    elif args.countries and args.boats and args.reference and args.option_name and args.tws is not None:
        non_interactive_main(args)
    else:
        interactive_main()


if __name__ == "__main__":
    main()
