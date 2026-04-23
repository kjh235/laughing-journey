from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from ffl.database import get_db
from ffl.schemas.geo_reference import CountyOut, StateOut, ZipInfoOut
from ffl.services.geo_reference import get_counties_by_state, get_states, get_zip_info

router = APIRouter()


@router.get("/geo/states", response_model=list[StateOut])
async def list_states(db: AsyncSession = Depends(get_db)) -> list[StateOut]:
    """Return all US states and territories."""
    rows = await get_states(db)
    return [StateOut.model_validate(r) for r in rows]


@router.get("/geo/states/{state_usps}/counties", response_model=list[CountyOut])
async def list_counties(
    state_usps: str = Path(..., min_length=2, max_length=2, description="2-letter USPS state code"),
    db: AsyncSession = Depends(get_db),
) -> list[CountyOut]:
    """Return counties for a given state, ordered by name."""
    result = await get_counties_by_state(db, state_usps)
    if result is None:
        raise HTTPException(status_code=404, detail=f"State '{state_usps.upper()}' not found")
    return [CountyOut.model_validate(r) for r in result]


@router.get("/geo/zip/{zip_code}", response_model=ZipInfoOut)
async def get_zip(
    zip_code: str = Path(..., min_length=5, max_length=5, description="5-digit ZIP code"),
    db: AsyncSession = Depends(get_db),
) -> ZipInfoOut:
    """Return reference data (city, state, county, centroid) for a ZIP code."""
    info = await get_zip_info(db, zip_code)
    if info is None:
        raise HTTPException(status_code=404, detail=f"ZIP code '{zip_code}' not found")
    return ZipInfoOut.model_validate(info)
