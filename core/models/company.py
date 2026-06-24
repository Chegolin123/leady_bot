import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tariff: Mapped[str] = mapped_column(String(50), nullable=False, default="base")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    users = relationship("User", back_populates="company")
    deals = relationship("Deal", back_populates="company")
    clients = relationship("Client", back_populates="company")
    tasks = relationship("Task", back_populates="company")
    licenses = relationship("License", back_populates="company")
    bots = relationship("Bot", back_populates="company")
    settings = relationship("CompanySettings", back_populates="company", uselist=False)
