from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ffl.database import Base


class RefState(Base):
    __tablename__ = "ref_states"

    fips_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    usps_code: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    counties: Mapped[list["RefCounty"]] = relationship(back_populates="state")
    zip_codes: Mapped[list["RefZipCode"]] = relationship(back_populates="state")
