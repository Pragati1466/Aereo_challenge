from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# Job statuses
JOB_PENDING = "PENDING"
JOB_PROCESSING = "PROCESSING"
JOB_COMPLETED = "COMPLETED"                       # every certificate succeeded
JOB_COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"  # some succeeded, some failed
JOB_FAILED = "FAILED"                             # nothing succeeded

# Item (single certificate) statuses
ITEM_PENDING = "PENDING"
ITEM_SUCCESS = "SUCCESS"
ITEM_FAILED = "FAILED"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    event_name: Mapped[str] = mapped_column(String(200))
    issuer: Mapped[str] = mapped_column(String(200))
    issue_date: Mapped[str] = mapped_column(String(10))  # ISO date
    status: Mapped[str] = mapped_column(String(30), default=JOB_PENDING, index=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["Item"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class Item(Base):
    """One recipient / one certificate inside a job."""

    __tablename__ = "items"
    __table_args__ = (Index("ix_items_job_status", "job_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    row_index: Mapped[int] = mapped_column(Integer)  # position in the original request
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    achievement: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ITEM_PENDING)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(300), nullable=True)  # relative to storage dir

    job: Mapped[Job] = relationship(back_populates="items")
