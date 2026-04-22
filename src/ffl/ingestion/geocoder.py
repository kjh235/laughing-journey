"""
Batch geocoding via US Census Geocoder.

Processes addresses in chunks (Census limit: 10,000 per batch).
Caches results in the addresses table so re-runs only geocode new/failed records.
"""

import csv
import io
import logging
import time
from dataclasses import dataclass

import censusgeocode as cg
import pandas as pd

from ffl.config import settings

logger = logging.getLogger(__name__)


@dataclass
class GeocodeResult:
    street: str
    city: str
    state: str
    zip: str
    lat: float | None
    lng: float | None
    matched: bool


def geocode_batch(addresses: pd.DataFrame) -> list[GeocodeResult]:
    """
    Geocode a DataFrame of addresses via Census batch geocoder.

    Input DataFrame must have columns: street, city, state, zip, plus an 'id' column
    used as the unique ID for each row in the Census batch request.

    Returns list of GeocodeResult in the same order as input.
    """
    chunk_size = settings.geocode_batch_size
    all_results: list[GeocodeResult] = []

    for start in range(0, len(addresses), chunk_size):
        chunk = addresses.iloc[start : start + chunk_size].copy()
        logger.info(
            "Geocoding batch %d-%d of %d",
            start,
            start + len(chunk),
            len(addresses),
        )
        chunk_results = _geocode_chunk(chunk)
        all_results.extend(chunk_results)

        # Respect Census rate limits between chunks
        if start + chunk_size < len(addresses):
            time.sleep(1)

    return all_results


def _geocode_chunk(chunk: pd.DataFrame) -> list[GeocodeResult]:
    """Geocode a single chunk via censusgeocode.addressbatch()."""
    # Build CSV in memory (id, street, city, state, zip)
    buf = io.StringIO()
    writer = csv.writer(buf)
    id_to_row: dict[str, pd.Series] = {}
    for _, row in chunk.iterrows():
        uid = str(row["id"])
        id_to_row[uid] = row
        writer.writerow([uid, row["street"] or "", row["city"] or "", row["state"] or "", row["zip"] or ""])
    buf.seek(0)

    results_by_id: dict[str, GeocodeResult] = {}

    try:
        geocoded = cg.addressbatch(buf, returntype="locations", benchmark=settings.geocode_benchmark)
        for record in geocoded:
            uid = str(record.get("id", ""))
            row = id_to_row.get(uid)
            if row is None:
                continue
            lat = record.get("lat") or record.get("latitude")
            lng = record.get("lon") or record.get("longitude")
            matched = bool(lat and lng)
            results_by_id[uid] = GeocodeResult(
                street=str(row.get("street") or ""),
                city=str(row.get("city") or ""),
                state=str(row.get("state") or ""),
                zip=str(row.get("zip") or ""),
                lat=float(lat) if lat else None,
                lng=float(lng) if lng else None,
                matched=matched,
            )
    except Exception as exc:
        logger.warning("Census geocoder error: %s — marking chunk as unmatched", exc)

    # Fill in any missing IDs as unmatched
    final: list[GeocodeResult] = []
    for _, row in chunk.iterrows():
        uid = str(row["id"])
        if uid in results_by_id:
            final.append(results_by_id[uid])
        else:
            final.append(GeocodeResult(
                street=str(row.get("street") or ""),
                city=str(row.get("city") or ""),
                state=str(row.get("state") or ""),
                zip=str(row.get("zip") or ""),
                lat=None,
                lng=None,
                matched=False,
            ))

    matched_count = sum(1 for r in final if r.matched)
    logger.info("Geocoded chunk: %d/%d matched", matched_count, len(final))
    return final
