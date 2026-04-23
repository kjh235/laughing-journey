from __future__ import annotations

from pydantic import BaseModel


class StateOut(BaseModel):
    fips_code: str
    usps_code: str
    name: str


class CountyOut(BaseModel):
    geoid: str
    state_fips: str
    county_fips: str
    name: str
    state_usps: str


class ZipInfoOut(BaseModel):
    zip_code: str
    primary_city: str
    state_usps: str
    state_name: str | None
    county_geoid: str | None
    county_name: str | None
    latitude: float
    longitude: float
