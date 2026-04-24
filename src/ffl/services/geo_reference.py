"""
Service functions for geopolitical reference data (ref_states, ref_counties, ref_zip_codes).
All functions accept an AsyncSession and return plain Python dicts.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ffl.models.ref_county import RefCounty
from ffl.models.ref_state import RefState
from ffl.models.ref_zip_code import RefZipCode


async def get_states(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(select(RefState).order_by(RefState.name))
    ).scalars().all()
    return [
        {"fips_code": r.fips_code, "usps_code": r.usps_code, "name": r.name}
        for r in rows
    ]


async def get_counties_by_state(
    session: AsyncSession,
    state_usps: str,
) -> list[dict] | None:
    """
    Return counties for a given state USPS code ordered by name.
    Returns None if the state code is not found in ref_states.
    """
    state_usps = state_usps.strip().upper()

    state_exists = (
        await session.execute(
            select(RefState.usps_code).where(RefState.usps_code == state_usps)
        )
    ).scalar_one_or_none()

    if state_exists is None:
        return None

    rows = (
        await session.execute(
            select(RefCounty)
            .where(RefCounty.state_usps == state_usps)
            .order_by(RefCounty.name)
        )
    ).scalars().all()

    return [
        {
            "geoid": r.geoid,
            "state_fips": r.state_fips,
            "county_fips": r.county_fips,
            "name": r.name,
            "state_usps": r.state_usps,
        }
        for r in rows
    ]


async def get_zip_info(
    session: AsyncSession,
    zip_code: str,
) -> dict | None:
    """
    Return ZIP reference data with joined state name and county name.
    Returns None if the ZIP is not in ref_zip_codes.
    """
    zip5 = zip_code.strip()[:5].zfill(5)

    row = (
        await session.execute(
            select(RefZipCode)
            .options(
                selectinload(RefZipCode.state),
                selectinload(RefZipCode.county),
            )
            .where(RefZipCode.zip_code == zip5)
        )
    ).scalar_one_or_none()

    if row is None:
        return None

    return {
        "zip_code": row.zip_code,
        "primary_city": row.primary_city,
        "state_usps": row.state_usps,
        "state_name": row.state.name if row.state else None,
        "county_geoid": row.county_geoid,
        "county_name": row.county.name if row.county else None,
        "latitude": float(row.latitude),
        "longitude": float(row.longitude),
    }
