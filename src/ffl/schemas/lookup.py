from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class LicenseTypeOut(BaseModel):
    code: str
    name: str
    description: str
    activities: list[str]
    sot_class: int | None


class BusinessOut(BaseModel):
    legal_name: str
    dba_name: str | None
    phone: str | None


class AddressOut(BaseModel):
    street: str | None
    city: str | None
    state: str | None
    zip: str | None
    county: str | None
    latitude: float | None
    longitude: float | None


class LicenseOut(BaseModel):
    ffl_number: str
    status: str
    expiration_date: date | None
    region: str | None
    license_type: LicenseTypeOut | None
    business: BusinessOut | None
    address: AddressOut | None


class AddressLookupResponse(BaseModel):
    count: int
    results: list[LicenseOut]


class ZipLookupResponse(BaseModel):
    zip_code: str
    radius_miles: float
    count: int
    results: list[LicenseOut]


class ChangeEventOut(BaseModel):
    event_type: str
    changed_at: str
    license_number: str | None
    old_data: dict[str, Any] | None
    new_data: dict[str, Any] | None


class ChangesResponse(BaseModel):
    since_date: str
    expiring_within_days: int
    recent_changes: list[ChangeEventOut]
    upcoming_expirations: list[LicenseOut]
