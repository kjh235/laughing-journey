"""
Seed ref_states, ref_counties, and ref_zip_codes from millbj92/US-Zip-Codes-JSON.

Data source: https://github.com/millbj92/US-Zip-Codes-JSON
Raw URL: https://raw.githubusercontent.com/millbj92/US-Zip-Codes-JSON/master/zipcodes.json

Run via: ffl-geo-seed [--force]
  --force: truncate ref_zip_codes and ref_counties before re-seeding
           (ref_states is always managed by the Alembic migration)
"""

from __future__ import annotations

import argparse
import asyncio
import logging

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ffl.database import AsyncSessionLocal
from ffl.models.ref_county import RefCounty
from ffl.models.ref_zip_code import RefZipCode

logger = logging.getLogger(__name__)

ZIP_JSON_URL = (
    "https://raw.githubusercontent.com/millbj92/US-Zip-Codes-JSON/master/zipcodes.json"
)

# USPS code → FIPS code mapping, mirrors the ref_states seed data in migration 002
STATE_FIPS: dict[str, str] = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55",
    "WY": "56", "AS": "60", "GU": "66", "MP": "69", "PR": "72",
    "VI": "78",
}

_CHUNK_SIZE = 5_000


async def download_zip_json(url: str = ZIP_JSON_URL) -> list[dict]:
    logger.info("Downloading ZIP data from %s", url)
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    data = resp.json()
    logger.info("Downloaded %d ZIP entries", len(data))
    return data


def derive_counties(
    zip_entries: list[dict],
    state_fips_map: dict[str, str],
) -> tuple[list[dict], dict[tuple[str, str], str]]:
    """
    Build ref_county rows from unique (state_usps, county_name) pairs in the ZIP data.

    County FIPS values are assigned sequentially (sorted by name within each state)
    and are NOT official Census FIPS codes. They are stable across re-runs of this
    seeder as long as the source data does not change.

    Returns:
        county_rows: list of dicts ready for bulk insert
        county_key_to_geoid: {(state_usps, county_name): geoid} lookup for ZIP rows
    """
    # Collect unique pairs, skipping entries with missing state or county
    seen: dict[str, set[str]] = {}  # state_usps -> set of county names
    for entry in zip_entries:
        state = (entry.get("state") or "").strip().upper()
        county = (entry.get("county") or "").strip()
        if not state or not county:
            continue
        if state not in state_fips_map:
            logger.warning("Unknown state code %r in ZIP data — skipping", state)
            continue
        seen.setdefault(state, set()).add(county)

    county_rows: list[dict] = []
    county_key_to_geoid: dict[tuple[str, str], str] = {}

    for state_usps in sorted(seen):
        state_fips = state_fips_map[state_usps]
        for idx, county_name in enumerate(sorted(seen[state_usps]), start=1):
            county_fips = f"{idx:03d}"
            geoid = state_fips + county_fips
            county_rows.append(
                {
                    "geoid": geoid,
                    "state_fips": state_fips,
                    "county_fips": county_fips,
                    "name": county_name,
                    "state_usps": state_usps,
                }
            )
            county_key_to_geoid[(state_usps, county_name)] = geoid

    logger.info("Derived %d unique counties", len(county_rows))
    return county_rows, county_key_to_geoid


def derive_zip_rows(
    zip_entries: list[dict],
    county_key_to_geoid: dict[tuple[str, str], str],
    state_fips_map: dict[str, str],
) -> list[dict]:
    """Build ref_zip_code rows, resolving county_geoid via in-memory lookup."""
    rows: list[dict] = []
    seen_zips: set[str] = set()

    for entry in zip_entries:
        zip_code = str(entry.get("zip_code") or "").strip().zfill(5)[:5]
        state = (entry.get("state") or "").strip().upper()
        city = (entry.get("city") or "").strip()

        if not zip_code or not state or not city:
            continue
        if state not in state_fips_map:
            continue
        if zip_code in seen_zips:
            continue
        seen_zips.add(zip_code)

        county_name = (entry.get("county") or "").strip()
        county_geoid = county_key_to_geoid.get((state, county_name))

        try:
            lat = float(entry.get("latitude") or 0)
            lng = float(entry.get("longitude") or 0)
        except (TypeError, ValueError):
            logger.warning("Bad lat/lng for ZIP %s — skipping", zip_code)
            continue

        rows.append(
            {
                "zip_code": zip_code,
                "primary_city": city[:50],
                "state_usps": state,
                "county_geoid": county_geoid,
                "latitude": lat,
                "longitude": lng,
            }
        )

    logger.info("Derived %d ZIP rows", len(rows))
    return rows


async def seed_counties(session, county_rows: list[dict], force: bool) -> int:
    if force:
        await session.execute(RefCounty.__table__.delete())
        logger.info("Cleared ref_counties (--force)")

    inserted = 0
    for i in range(0, len(county_rows), _CHUNK_SIZE):
        chunk = county_rows[i : i + _CHUNK_SIZE]
        stmt = pg_insert(RefCounty).values(chunk).on_conflict_do_nothing(
            index_elements=["geoid"]
        )
        result = await session.execute(stmt)
        inserted += result.rowcount

    logger.info("Inserted %d county rows", inserted)
    return inserted


async def seed_zip_codes(session, zip_rows: list[dict], force: bool) -> int:
    if force:
        await session.execute(RefZipCode.__table__.delete())
        logger.info("Cleared ref_zip_codes (--force)")

    inserted = 0
    for i in range(0, len(zip_rows), _CHUNK_SIZE):
        chunk = zip_rows[i : i + _CHUNK_SIZE]
        stmt = pg_insert(RefZipCode).values(chunk).on_conflict_do_nothing(
            index_elements=["zip_code"]
        )
        result = await session.execute(stmt)
        inserted += result.rowcount

    logger.info("Inserted %d ZIP rows", inserted)
    return inserted


async def run_seeder(force: bool = False) -> dict:
    zip_entries = await download_zip_json()

    county_rows, county_key_to_geoid = derive_counties(zip_entries, STATE_FIPS)
    zip_rows = derive_zip_rows(zip_entries, county_key_to_geoid, STATE_FIPS)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            counties_inserted = await seed_counties(session, county_rows, force)
            zips_inserted = await seed_zip_codes(session, zip_rows, force)

    summary = {"counties_inserted": counties_inserted, "zips_inserted": zips_inserted}
    logger.info("Seeding complete: %s", summary)
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Seed geopolitical reference tables")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing county and ZIP rows before re-seeding",
    )
    args = parser.parse_args()

    result = asyncio.run(run_seeder(force=args.force))
    print(f"Done — counties: {result['counties_inserted']}, zips: {result['zips_inserted']}")
