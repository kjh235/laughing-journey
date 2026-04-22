from sqlalchemy import ARRAY, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ffl.database import Base


class LicenseType(Base):
    __tablename__ = "license_types"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(2), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sot_class: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    activities: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    licenses: Mapped[list["License"]] = relationship(back_populates="license_type")
