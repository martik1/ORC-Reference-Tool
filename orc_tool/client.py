from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import requests

from config import API_BASE, CACHE_DIR, CACHE_MAX_AGE_DAYS
from orc_tool.models import Boat


class OrcApiError(RuntimeError):
    pass


def _cache_path(country_id: str, family: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{country_id.upper()}_{family}.json"


def _load_json(text: str) -> dict:
    return json.loads(text.encode("utf-8").decode("utf-8-sig") if isinstance(text, str) else text)


def _download(params: dict) -> dict:
    resp = requests.get(API_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.content.decode("utf-8-sig")
    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        raise OrcApiError(f"ORC API returned non-JSON response for {params}") from exc


def fetch_country(
    country_id: str,
    family: str = "ORC",
    max_age_days: float = CACHE_MAX_AGE_DAYS,
    force_refresh: bool = False,
) -> dict:
    """Fetch (or read from cache) the full certificate list for a country.

    Returns the raw parsed JSON dict with keys 'rms', 'Countries', 'ScoringOptions'.
    """
    path = _cache_path(country_id, family)
    if not force_refresh and path.exists():
        age_days = (time.time() - path.stat().st_mtime) / 86400
        if age_days <= max_age_days:
            with path.open(encoding="utf-8") as fh:
                return json.load(fh)

    data = _download({"action": "DownRMS", "CountryId": country_id, "Family": family, "ext": "json"})
    if not data.get("rms"):
        raise OrcApiError(
            f"No certificates returned for country {country_id!r} / family {family!r}. "
            "Check the 3-letter country code."
        )
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return data


def load_boats(country_id: str, family: str = "ORC", **kwargs) -> list[Boat]:
    data = fetch_country(country_id, family=family, **kwargs)
    return [Boat.from_json(rec, country=country_id) for rec in data["rms"]]


def scoring_options_catalog(country_id: str, family: str = "ORC", **kwargs) -> list[dict]:
    data = fetch_country(country_id, family=family, **kwargs)
    return data["ScoringOptions"]


def get_boat(ref_no: Optional[str] = None, sail_no: Optional[str] = None) -> Boat:
    """Look up a single boat directly, without pre-caching a whole country."""
    if not ref_no and not sail_no:
        raise ValueError("Provide ref_no or sail_no")
    params = {"action": "DownBoatRMS", "ext": "json"}
    if ref_no:
        params["RefNo"] = ref_no
    if sail_no:
        params["SailNo"] = sail_no
    data = _download(params)
    records = data.get("rms") or []
    if not records:
        raise OrcApiError(f"No certificate found for RefNo={ref_no!r} SailNo={sail_no!r}")
    return Boat.from_json(records[0])


def search_boats(query: str, boats: list[Boat]) -> list[Boat]:
    """Case-insensitive substring match on yacht name, sail number, or class."""
    q = query.strip().lower()
    if not q:
        return list(boats)
    return [
        b
        for b in boats
        if q in (b.name or "").lower()
        or q in (b.sail_no or "").lower()
        or q in (b.yacht_class or "").lower()
    ]
