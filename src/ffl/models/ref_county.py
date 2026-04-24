from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ffl.database import Base


class RefCounty(Base):
    __tablename__ = "ref_counties"

    # state_fips (2) + county_fips (3) — county_fips is sequential within state,
    # not official Census FIPS (which requires a separate TIGER/Line download)
    geoid: Mapped[str] = mapped_column(String(5), primary_key=True)
    state_fips: Mapped[str] = mapped_column(String(2), nullable=False)
    county_fips: Mapped[str] = mapped_column(String(3), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    state_usps: Mapped[str] = mapped_column(
        String(2),
        ForeignKey("ref_states.usps_code", ondelete="RESTRICT"),
        nullable=False,
    )

    state: Mapped["RefState"] = relationship(back_populates="counties")
    zip_codes: Mapped[list["RefZipCode"]] = relationship(back_populates="county")

    __table_args__ = (
        Index("ix_ref_counties_state_usps", "state_usps"),
        Index("ix_ref_counties_name_state", "name", "state_usps"),
    )
