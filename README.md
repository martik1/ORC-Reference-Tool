# ORC Time Allowance & Polar Tool

Compares ORC-rated boats, time allowances for a chosen wind speed and
course/scoring option, plus polar-curve plots using data pulled live from
ORC's own public certificate database (data.orc.org).

## Setup

```
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Run (interactive)

```
./.venv/bin/python main.py
```

You'll be asked for:
1. Country code(s) to load certificates from (e.g. `FIN` or `FIN,SWE`) — the
   first run for a country downloads and caches its certificate list
   (`cache/<CC>_ORC.json`, refreshed automatically after 7 days).
2. A search term to find and multi-select boats (matches name/sail
   number/class), and which of them is the reference boat.
3. A course/scoring option (All Purpose or Windward/Leeward, in either
   Time-on-Distance, Time-on-Time, or Performance-Curve-Scoring form).
4. A true wind speed, and a course distance (nm) or reference elapsed time
   (min), depending on the option.

You then get a table of time allowances relative to the reference boat, and a
follow-up menu to plot polars, print a VMG/target-speed table, find the
crossover wind speed between two boats, or simulate a multi-leg course.

## Run (non-interactive / scriptable)

```
./.venv/bin/python main.py \
  --countries FIN \
  --boats "Pärlan,X-37" \
  --reference "Pärlan" \
  --option-name "Windward/Leeward" --option-kind PCS \
  --tws 12 --distance 5 \
  --plot --vmg
```

## What "allowance" means here

- **TOD / PCS** (seconds/mile, lower = faster): allowance = how many extra
  seconds a boat is allowed over the given distance to tie the reference boat
  on corrected time. Positive = boat is slower and receives time; negative =
  boat is faster and must give that much time back.
- **TOT** (time correction factor, higher = faster): allowance = how much
  extra elapsed time a boat is allowed, relative to the reference boat's
  assumed elapsed time, to tie on corrected time.

## Module map

- `orc_tool/client.py` — fetch/cache certificate data from data.orc.org.
- `orc_tool/models.py` — `Boat` / `PolarTable`, with TWS/TWA interpolation.
- `orc_tool/scoring.py` — the course/scoring-option catalog and rating lookup.
- `orc_tool/compare.py` — the N-boats-vs-reference allowance table.
- `orc_tool/polar.py` — polar-diagram plotting.
- `orc_tool/vmg.py` — VMG/target-speed table.
- `orc_tool/crossover.py` — crossover wind speed between two boats.
- `orc_tool/course.py` — multi-leg race course simulator.
- `orc_tool/cli.py` — interactive + scriptable front-end.

## Ideas not built...
