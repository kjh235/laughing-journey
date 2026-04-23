from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ffl.database import get_db
from ffl.schemas.lookup import AddressLookupResponse, LicenseOut
from ffl.services.lookup import lookup_by_address

router = APIRouter()


@router.get("/lookup/address", response_model=AddressLookupResponse)
async def address_lookup(
    street: str = Query(..., description="Street address"),
    city: str = Query(..., description="City"),
    state: str = Query(..., min_length=2, max_length=2, description="2-letter state code"),
    zip: str | None = Query(None, min_length=5, max_length=5, description="5-digit ZIP code"),
    db: AsyncSession = Depends(get_db),
) -> AddressLookupResponse:
    """
    Look up active FFL licensees at a given US address.

    Returns exact matches first. If no exact match is found and a ZIP code is
    provided, returns all active licensees in that ZIP code as a fallback.
    """
    results = await lookup_by_address(db, street=street, city=city, state=state, zip_code=zip)
    return AddressLookupResponse(
        count=len(results),
        results=[LicenseOut.model_validate(r) for r in results],
    )
