import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from orc_tool.models import Boat

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"


@pytest.fixture
def fin_boat() -> Boat:
    """Real, cached certificate data (no network) for FIN-13004 / Rush."""
    data = json.loads((CACHE_DIR / "FIN_ORC.json").read_text())
    rec = next(r for r in data["rms"] if r["SailNo"] == "FIN-13004")
    return Boat.from_json(rec, country="FIN")


@pytest.fixture
def fin_boat_2() -> Boat:
    """Real, cached certificate data (no network) for FIN-12149 / Black Pearl."""
    data = json.loads((CACHE_DIR / "FIN_ORC.json").read_text())
    rec = next(r for r in data["rms"] if r["SailNo"] == "FIN-12149")
    return Boat.from_json(rec, country="FIN")
