import datetime as dt
import uuid

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ideas.settings import Settings


class Base(DeclarativeBase):
    pass


class SuggestionCache(Base):
    __tablename__ = "suggestion_cache"
    __table_args__ = (
        UniqueConstraint(
            "kind",
            "age_band",
            "locale",
            "slot",
            "iso_week",
            "day_context",
            "catalog_version",
            name="uq_suggestion_cache_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    age_band: Mapped[str] = mapped_column(String(16), nullable=False)
    locale: Mapped[str] = mapped_column(String(2), nullable=False)
    slot: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    iso_week: Mapped[str] = mapped_column(String(16), nullable=False)
    day_context: Mapped[str] = mapped_column(String(16), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(16), nullable=False)
    body: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def make_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(settings.database_url, pool_pre_ping=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
