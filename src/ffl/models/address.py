from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ffl.database import Base


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    street: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(50), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    zip: Mapped[str | None] = mapped_column(String(5), nullable=True)
    zip4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    county: Mapped[str | None] = mapped_column(String(50), nullable=True)
    geom: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=True
    )
    geocoded_at: Mapped[datetime | None] = mapped_column(nullable=True)
    geocode_source: Mapped[str | None] = mapped_column(String(20), nullable=True)

    licenses: Mapped[list["License"]] = relationship(back_populates="address")

    __table_args__ = (
        Index("ix_addresses_geom", "geom", postgresql_using="gist"),
        Index("ix_addresses_zip_state", "zip", "state"),
    )
