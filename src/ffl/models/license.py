from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ffl.database import Base


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    license_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    license_type_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("license_types.id"), nullable=False, index=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.id"), nullable=False, index=True)
    address_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("addresses.id"), nullable=False, index=True)
    contact_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("contact_parties.id"), nullable=True)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    region: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    license_type: Mapped["LicenseType"] = relationship(back_populates="licenses")
    business: Mapped["Business"] = relationship(back_populates="licenses")
    address: Mapped["Address"] = relationship(back_populates="licenses")
    contact: Mapped["ContactParty | None"] = relationship(back_populates="licenses")
    change_logs: Mapped[list["ChangeLog"]] = relationship(back_populates="license")
