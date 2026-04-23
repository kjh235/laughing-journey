"""
Full ETL pipeline: download → parse → geocode → upsert → change log.
"""

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from geoalchemy2.elements import WKTElement
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ffl.database import AsyncSessionLocal
from ffl.ingestion.downloader import download_atf_data
from ffl.ingestion.geocoder import geocode_batch
from ffl.ingestion.parser import parse_atf_file
from ffl.models import Address, Business, ChangeLog, ContactParty, License, LicenseType

logger = logging.getLogger(__name__)


async def run_pipeline(local_file: Path | None = None) -> dict:
    """
    Run the full FFL data ingestion pipeline.

    Args:
        local_file: If provided, skip download and use this file.

    Returns:
        Summary dict with inserted/updated/expired/geocoded counts.
    """
    stats = {"inserted": 0, "updated": 0, "expired": 0, "geocoded": 0, "errors": 0}

    # 1. Download
    if local_file:
        data_path = local_file
    else:
        data_path = await download_atf_data()

    # 2. Parse
    df = parse_atf_file(data_path)

    async with AsyncSessionLocal() as session:
        # 3. Load license type code → id mapping
        lt_rows = (await session.execute(select(LicenseType))).scalars().all()
        lt_map = {lt.code: lt.id for lt in lt_rows}

        # 4. Upsert all records
        incoming_license_numbers: set[str] = set()

        for _, row in df.iterrows():
            try:
                await _upsert_record(session, row, lt_map, stats)
                incoming_license_numbers.add(row["license_number"])
            except Exception as exc:
                logger.error("Error processing record %s: %s", row.get("license_number"), exc)
                stats["errors"] += 1

        await session.commit()

        # 5. Mark licenses not in incoming data as expired
        all_active = (
            await session.execute(
                select(License).where(License.status == "active")
            )
        ).scalars().all()

        to_expire = [
            lic for lic in all_active
            if lic.license_number not in incoming_license_numbers
        ]
        for lic in to_expire:
            old = _license_snapshot(lic)
            lic.status = "expired"
            lic.updated_at = datetime.now(timezone.utc)
            session.add(ChangeLog(
                license_id=lic.id,
                event_type="expired",
                old_data=old,
                new_data=_license_snapshot(lic),
            ))
            stats["expired"] += 1

        await session.commit()

        # 6. Geocode addresses that lack coordinates
        await _geocode_missing(session, stats)
        await session.commit()

    logger.info("Pipeline complete: %s", stats)
    return stats


async def _upsert_record(
    session: AsyncSession,
    row: pd.Series,
    lt_map: dict[str, int],
    stats: dict,
) -> None:
    license_number = row["license_number"]
    lt_code = str(row["license_type"]).strip().zfill(2)
    lt_id = lt_map.get(lt_code)
    if lt_id is None:
        logger.warning("Unknown license type %s for %s", lt_code, license_number)
        return

    expiration_date = _parse_date(row.get("expiration_date"))
    if expiration_date is None:
        logger.warning("No expiration date for %s", license_number)
        return

    # Upsert business
    business = await _get_or_create_business(session, row)

    # Upsert contact party
    contact = await _get_or_create_contact(session, row, business.id)

    # Upsert address
    address = await _get_or_create_address(session, row)

    # Check if license exists
    existing = (
        await session.execute(
            select(License).where(License.license_number == license_number)
        )
    ).scalar_one_or_none()

    if existing is None:
        new_lic = License(
            license_number=license_number,
            license_type_id=lt_id,
            business_id=business.id,
            address_id=address.id,
            contact_id=contact.id if contact else None,
            expiration_date=expiration_date,
            status="active",
            region=str(row.get("region") or "").strip() or None,
        )
        session.add(new_lic)
        await session.flush()
        session.add(ChangeLog(
            license_id=new_lic.id,
            event_type="inserted",
            old_data=None,
            new_data=_row_snapshot(row),
        ))
        stats["inserted"] += 1
    else:
        old = _license_snapshot(existing)
        changed = False

        if existing.expiration_date != expiration_date:
            existing.expiration_date = expiration_date
            changed = True
        if existing.address_id != address.id:
            existing.address_id = address.id
            changed = True
        if existing.status != "active":
            existing.status = "active"
            changed = True

        if changed:
            existing.updated_at = datetime.now(timezone.utc)
            session.add(ChangeLog(
                license_id=existing.id,
                event_type="updated",
                old_data=old,
                new_data=_row_snapshot(row),
            ))
            stats["updated"] += 1


async def _get_or_create_business(session: AsyncSession, row: pd.Series) -> Business:
    legal_name = str(row.get("business_name") or "").strip()
    dba_name = str(row.get("dba_name") or "").strip() or None
    phone = str(row.get("phone") or "").strip() or None

    # Simple match on legal_name (could be enhanced with fuzzy matching)
    existing = (
        await session.execute(
            select(Business).where(Business.legal_name == legal_name)
        )
    ).scalar_one_or_none()

    if existing:
        return existing

    biz = Business(legal_name=legal_name, dba_name=dba_name, phone=phone)
    session.add(biz)
    await session.flush()
    return biz


async def _get_or_create_contact(
    session: AsyncSession, row: pd.Series, business_id: int
) -> ContactParty | None:
    first = str(row.get("contact_first_name") or "").strip() or None
    last = str(row.get("contact_last_name") or "").strip() or None

    if not first and not last:
        return None

    existing = (
        await session.execute(
            select(ContactParty).where(
                ContactParty.business_id == business_id,
                ContactParty.first_name == first,
                ContactParty.last_name == last,
            )
        )
    ).scalar_one_or_none()

    if existing:
        return existing

    contact = ContactParty(business_id=business_id, first_name=first, last_name=last)
    session.add(contact)
    await session.flush()
    return contact


async def _get_or_create_address(session: AsyncSession, row: pd.Series) -> Address:
    street = str(row.get("premise_street") or "").strip() or None
    city = str(row.get("premise_city") or "").strip() or None
    state = str(row.get("premise_state") or "").strip() or None
    zip_ = str(row.get("premise_zip") or "").strip() or None
    zip4 = str(row.get("premise_zip4") or "").strip() or None
    county = str(row.get("county_code") or "").strip() or None

    existing = (
        await session.execute(
            select(Address).where(
                Address.street == street,
                Address.city == city,
                Address.state == state,
                Address.zip == zip_,
            )
        )
    ).scalar_one_or_none()

    if existing:
        return existing

    addr = Address(
        street=street,
        city=city,
        state=state,
        zip=zip_,
        zip4=zip4,
        county=county,
    )
    session.add(addr)
    await session.flush()
    return addr


async def _geocode_missing(session: AsyncSession, stats: dict) -> None:
    """Geocode all addresses that don't yet have a geom."""
    ungeooded = (
        await session.execute(
            select(Address).where(Address.geom.is_(None))
        )
    ).scalars().all()

    if not ungeooded:
        return

    logger.info("Geocoding %d addresses without coordinates", len(ungeooded))

    addr_df = pd.DataFrame([
        {
            "id": addr.id,
            "street": addr.street,
            "city": addr.city,
            "state": addr.state,
            "zip": addr.zip,
        }
        for addr in ungeooded
    ])

    results = geocode_batch(addr_df)
    id_to_addr = {addr.id: addr for addr in ungeooded}

    for i, result in enumerate(results):
        addr_id = ungeooded[i].id
        addr = id_to_addr[addr_id]
        if result.matched and result.lat and result.lng:
            addr.geom = WKTElement(f"POINT({result.lng} {result.lat})", srid=4326)
            addr.geocoded_at = datetime.now(timezone.utc)
            addr.geocode_source = "census"
            stats["geocoded"] += 1


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _license_snapshot(lic: License) -> dict:
    return {
        "license_number": lic.license_number,
        "expiration_date": lic.expiration_date.isoformat() if lic.expiration_date else None,
        "status": lic.status,
        "address_id": lic.address_id,
    }


def _row_snapshot(row: pd.Series) -> dict:
    return {
        "license_number": row.get("license_number"),
        "business_name": row.get("business_name"),
        "premise_street": row.get("premise_street"),
        "premise_city": row.get("premise_city"),
        "premise_state": row.get("premise_state"),
        "premise_zip": row.get("premise_zip"),
        "expiration_date": row.get("expiration_date"),
        "license_type": row.get("license_type"),
    }
