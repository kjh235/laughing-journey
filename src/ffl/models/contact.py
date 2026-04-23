from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ffl.database import Base


class ContactParty(Base):
    __tablename__ = "contact_parties"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("businesses.id"), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(30), nullable=True)

    business: Mapped["Business"] = relationship(back_populates="contact_parties")
    licenses: Mapped[list["License"]] = relationship(back_populates="contact")
