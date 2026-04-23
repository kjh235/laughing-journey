from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ffl.database import get_db
from ffl.schemas.lookup import LicenseOut, ZipLookupResponse
from ffl.services.lookup import lookup_by_zip

router = APIRouter()


@router.get("/lookup/zip/{zip_code}", response_model=ZipLookupResponse)
async def zip_lookup(
    zip_code: str = Path(..., min_length=5, max_length=5, description="5-digit ZIP code"),
    radius_miles: float = Query(0.0, ge=0, le=500, description="Search radius in miles (0 = ZIP only)"),
    db: AsyncSession = Depends(get_db),
) -> ZipLookupResponse:
    """
    Look up active FFL licensees in or near a ZIP code.

    With `radius_miles=0` (default), returns only licensees whose premise address
    is in the given ZIP code. With `radius_miles>0`, returns all licensees within
    that radius of the ZIP code centroid, ordered by distance.
    """
    results = await lookup_by_zip(db, zip_code=zip_code, radius_miles=radius_miles)
    return ZipLookupResponse(
        zip_code=zip_code,
        radius_miles=radius_miles,
        count=len(results),
        results=[LicenseOut.model_validate(r) for r in results],
    )
