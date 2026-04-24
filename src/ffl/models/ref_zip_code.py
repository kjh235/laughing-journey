from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ffl.database import Base


class RefZipCode(Base):
    __tablename__ = "ref_zip_codes"

    zip_code: Mapped[str] = mapped_column(String(5), primary_key=True)
    primary_city: Mapped[str] = mapped_column(String(50), nullable=False)
    state_usps: Mapped[str] = mapped_column(
        String(2),
        ForeignKey("ref_states.usps_code", ondelete="RESTRICT"),
        nullable=False,
    )
    county_geoid: Mapped[str | None] = mapped_column(
        String(5),
        ForeignKey("ref_counties.geoid", ondelete="SET NULL"),
        nullable=True,
    )
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)

    state: Mapped["RefState"] = relationship(back_populates="zip_codes")
    county: Mapped["RefCounty | None"] = relationship(back_populates="zip_codes")

    __table_args__ = (
        Index("ix_ref_zip_codes_state_usps", "state_usps"),
        Index("ix_ref_zip_codes_county_geoid", "county_geoid"),
    )
