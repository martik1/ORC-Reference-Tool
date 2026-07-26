"""Print the raw, unparsed ORC API response for a single boat.

Usage:
    python tests/print_raw_boat.py --sail-no FIN1234
    python tests/print_raw_boat.py --ref-no 123456
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from config import API_BASE


def fetch_raw_boat(ref_no: str | None = None, sail_no: str | None = None) -> str:
    params = {"action": "DownBoatRMS", "ext": "json"}
    if ref_no:
        params["RefNo"] = ref_no
    if sail_no:
        params["SailNo"] = sail_no
    resp = requests.get(API_BASE, params=params, timeout=30)
    resp.raise_for_status()
    return resp.content.decode("utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref-no", help="Certificate RefNo to look up")
    parser.add_argument("--sail-no", help="Sail number to look up")
    args = parser.parse_args()

    if not args.ref_no and not args.sail_no:
        parser.error("Provide --ref-no or --sail-no")

    print(fetch_raw_boat(ref_no=args.ref_no, sail_no=args.sail_no))


if __name__ == "__main__":
    main()
