from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ffl.database import Base


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dba_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(10), nullable=True)

    licenses: Mapped[list["License"]] = relationship(back_populates="business")
    contact_parties: Mapped[list["ContactParty"]] = relationship(back_populates="business")
