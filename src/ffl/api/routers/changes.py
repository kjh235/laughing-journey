from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ffl.database import get_db
from ffl.schemas.lookup import ChangeEventOut, ChangesResponse, LicenseOut
from ffl.services.lookup import lookup_changes

router = APIRouter()


@router.get("/lookup/changes", response_model=ChangesResponse)
async def changes_lookup(
    since_date: date | None = Query(
        None,
        description="Return changes on or after this date (ISO format). Defaults to 30 days ago.",
    ),
    expiring_within_days: int = Query(
        90,
        ge=0,
        le=3650,
        description="Include licenses expiring within this many days.",
    ),
    db: AsyncSession = Depends(get_db),
) -> ChangesResponse:
    """
    Return recent FFL license changes and upcoming expirations.

    - `recent_changes`: Change events (new, updated, expired) recorded since `since_date`.
    - `upcoming_expirations`: Active licenses with expiration dates within `expiring_within_days`.
    """
    result = await lookup_changes(
        db,
        since_date=since_date,
        expiring_within_days=expiring_within_days,
    )
    return ChangesResponse(
        since_date=result["since_date"],
        expiring_within_days=result["expiring_within_days"],
        recent_changes=[ChangeEventOut.model_validate(c) for c in result["recent_changes"]],
        upcoming_expirations=[LicenseOut.model_validate(e) for e in result["upcoming_expirations"]],
    )
