"""
Shared query/service logic used by both the REST API and MCP server.
All functions accept an AsyncSession and return plain Python dicts.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID, ST_X, ST_Y, ST_Distance
from sqlalchemy import cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ffl.models import Address, Business, ChangeLog, License, LicenseType

logger = logging.getLogger(__name__)

MILES_TO_METERS = 1609.344


def _license_to_dict(lic: License) -> dict:
    biz = lic.business
    addr = lic.address
    lt = lic.license_type
    return {
        "ffl_number": lic.license_number,
        "status": lic.status,
        "expiration_date": lic.expiration_date.isoformat() if lic.expiration_date else None,
        "region": lic.region,
        "license_type": {
            "code": lt.code,
            "name": lt.name,
            "description": lt.description,
            "activities": lt.activities,
            "sot_class": lt.sot_class,
        } if lt else None,
        "business": {
            "legal_name": biz.legal_name,
            "dba_name": biz.dba_name,
            "phone": biz.phone,
        } if biz else None,
        "address": {
            "street": addr.street,
            "city": addr.city,
            "state": addr.state,
            "zip": addr.zip,
            "county": addr.county,
            "latitude": None,   # populated below if geocoded
            "longitude": None,
        } if addr else None,
    }


async def lookup_by_address(
    session: AsyncSession,
    street: str,
    city: str,
    state: str,
    zip_code: str | None = None,
) -> list[dict]:
    """
    Find active licenses at a given address.
    First tries exact match on street/city/state/zip, then falls back
    to a spatial proximity search if the address can be roughly matched by ZIP.
    """
    q = (
        select(License)
        .join(License.address)
        .join(License.business)
        .join(License.license_type)
        .options(
            selectinload(License.address),
            selectinload(License.business),
            selectinload(License.license_type),
        )
        .where(License.status == "active")
    )

    # Normalize inputs
    street_norm = street.strip().upper()
    city_norm = city.strip().upper()
    state_norm = state.strip().upper()

    exact_q = q.where(
        func.upper(Address.street) == street_norm,
        func.upper(Address.city) == city_norm,
        func.upper(Address.state) == state_norm,
    )
    if zip_code:
        exact_q = exact_q.where(Address.zip == zip_code.strip()[:5])

    results = (await session.execute(exact_q)).scalars().all()

    if results:
        return [_license_to_dict(r) for r in results]

    # Fallback: if zip provided, return all active licenses in that ZIP
    if zip_code:
        zip_q = q.where(Address.zip == zip_code.strip()[:5])
        results = (await session.execute(zip_q)).scalars().all()

    return [_license_to_dict(r) for r in results]


async def lookup_by_zip(
    session: AsyncSession,
    zip_code: str,
    radius_miles: float = 0.0,
) -> list[dict]:
    """
    Find active licenses in a ZIP code, optionally within a radius.
    Results are ordered by distance when a radius is specified.
    """
    zip5 = zip_code.strip()[:5]

    q = (
        select(License)
        .join(License.address)
        .join(License.business)
        .join(License.license_type)
        .options(
            selectinload(License.address),
            selectinload(License.business),
            selectinload(License.license_type),
        )
        .where(License.status == "active")
    )

    if radius_miles <= 0:
        q = q.where(Address.zip == zip5)
        results = (await session.execute(q)).scalars().all()
        return [_license_to_dict(r) for r in results]

    # Compute ZIP centroid from geocoded addresses in that ZIP
    centroid = (
        await session.execute(
            select(
                func.avg(ST_X(Address.geom)).label("lng"),
                func.avg(ST_Y(Address.geom)).label("lat"),
            ).where(
                Address.zip == zip5,
                Address.geom.is_not(None),
            )
        )
    ).one_or_none()

    if not centroid or centroid.lat is None or centroid.lng is None:
        # Fallback: plain ZIP match
        q = q.where(Address.zip == zip5)
        results = (await session.execute(q)).scalars().all()
        return [_license_to_dict(r) for r in results]

    center = ST_SetSRID(ST_MakePoint(centroid.lng, centroid.lat), 4326)
    radius_m = radius_miles * MILES_TO_METERS

    q = q.where(
        ST_DWithin(
            cast(Address.geom, text("geography")),
            cast(center, text("geography")),
            radius_m,
        )
    ).order_by(
        ST_Distance(
            cast(Address.geom, text("geography")),
            cast(center, text("geography")),
        )
    ).limit(500)

    results = (await session.execute(q)).scalars().all()
    return [_license_to_dict(r) for r in results]


async def lookup_changes(
    session: AsyncSession,
    since_date: date | None = None,
    expiring_within_days: int = 90,
) -> dict:
    """
    Return recent change events and upcoming expirations.
    """
    if since_date is None:
        since_date = date.today() - timedelta(days=30)

    # Recent change events
    change_rows = (
        await session.execute(
            select(ChangeLog)
            .options(selectinload(ChangeLog.license))
            .where(ChangeLog.changed_at >= since_date)
            .order_by(ChangeLog.changed_at.desc())
            .limit(1000)
        )
    ).scalars().all()

    changes = [
        {
            "event_type": c.event_type,
            "changed_at": c.changed_at.isoformat(),
            "license_number": c.license.license_number if c.license else None,
            "old_data": c.old_data,
            "new_data": c.new_data,
        }
        for c in change_rows
    ]

    # Upcoming expirations
    cutoff = date.today() + timedelta(days=expiring_within_days)
    expiring = (
        await session.execute(
            select(License)
            .join(License.address)
            .join(License.business)
            .join(License.license_type)
            .options(
                selectinload(License.address),
                selectinload(License.business),
                selectinload(License.license_type),
            )
            .where(
                License.status == "active",
                License.expiration_date <= cutoff,
            )
            .order_by(License.expiration_date)
            .limit(500)
        )
    ).scalars().all()

    return {
        "since_date": since_date.isoformat(),
        "expiring_within_days": expiring_within_days,
        "recent_changes": changes,
        "upcoming_expirations": [_license_to_dict(lic) for lic in expiring],
    }


async def get_license_types(session: AsyncSession) -> list[dict]:
    """Return all license type reference records."""
    rows = (await session.execute(select(LicenseType).order_by(LicenseType.code))).scalars().all()
    return [
        {
            "code": lt.code,
            "name": lt.name,
            "description": lt.description,
            "activities": lt.activities,
            "sot_class": lt.sot_class,
        }
        for lt in rows
    ]
