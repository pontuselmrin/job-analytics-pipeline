"""SQLAlchemy database layer for enrichment pipeline."""

import os
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://{user}:{password}@localhost:5432/{db}".format(
        user=os.environ.get("POSTGRES_USER", "scrape"),
        password=os.environ.get("POSTGRES_PASSWORD", "scrape"),
        db=os.environ.get("POSTGRES_DB", "scrape"),
    ),
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Organization(Base):
    __tablename__ = "organizations"

    org_abbrev = Column(String, primary_key=True)
    org_name = Column(String, nullable=False)
    enriched_at = Column(DateTime(timezone=True))


class Job(Base):
    __tablename__ = "jobs"

    url = Column(String, primary_key=True)
    org_abbrev = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content_type = Column(String, nullable=False, server_default="")
    description = Column(Text, nullable=False, server_default="")
    pdf_path = Column(String, nullable=False, server_default="")
    enriched_at = Column(DateTime(timezone=True))
    enrich_error = Column(String, nullable=False, server_default="")
    enrich_status = Column(String, nullable=False, server_default="")
    status_reason = Column(String, nullable=False, server_default="")
    fetch_method = Column(String, nullable=False, server_default="")
    fetch_seconds = Column(Float, nullable=False, server_default="0.0")


class BoilerplateSentence(Base):
    __tablename__ = "boilerplate_sentences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_abbrev = Column(String, nullable=False)
    sentence = Column(Text, nullable=False)
    frequency = Column(Float, nullable=False)

    __table_args__ = (UniqueConstraint("org_abbrev", "sentence"),)


class FetchFailure(Base):
    __tablename__ = "fetch_failures"

    url = Column(String, primary_key=True)
    org_abbrev = Column(String, nullable=False)
    title = Column(String, nullable=False, server_default="")
    fail_count = Column(Integer, nullable=False, server_default="1")
    last_error = Column(String, nullable=False, server_default="")
    last_status = Column(String, nullable=False, server_default="")
    last_reason = Column(String, nullable=False, server_default="")
    first_failed = Column(DateTime(timezone=True))
    last_failed = Column(DateTime(timezone=True))


@contextmanager
def get_session():
    """Yield a SQLAlchemy session, committing on success or rolling back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def upsert_org(session: Session, org_abbrev: str, org_name: str) -> None:
    """Insert or update an organization row."""
    org = session.get(Organization, org_abbrev)
    if org:
        org.org_name = org_name
        org.enriched_at = datetime.now(timezone.utc)
    else:
        session.add(
            Organization(
                org_abbrev=org_abbrev,
                org_name=org_name,
                enriched_at=datetime.now(timezone.utc),
            )
        )


def upsert_jobs(session: Session, org_abbrev: str, jobs: list[dict]) -> None:
    """Bulk upsert jobs using (org_abbrev, url) as the unique key."""
    for job in jobs:
        existing = session.get(Job, job["url"])
        if existing:
            for key in (
                "title",
                "content_type",
                "description",
                "pdf_path",
                "enriched_at",
                "enrich_error",
                "enrich_status",
                "status_reason",
                "fetch_method",
                "fetch_seconds",
            ):
                if key in job:
                    setattr(existing, key, job[key])
        else:
            session.add(
                Job(
                    org_abbrev=org_abbrev,
                    title=job.get("title", ""),
                    url=job["url"],
                    content_type=job.get("content_type", ""),
                    description=job.get("description", ""),
                    pdf_path=job.get("pdf_path", ""),
                    enriched_at=job.get("enriched_at"),
                    enrich_error=job.get("enrich_error", ""),
                    enrich_status=job.get("enrich_status", ""),
                    status_reason=job.get("status_reason", ""),
                    fetch_method=job.get("fetch_method", ""),
                    fetch_seconds=job.get("fetch_seconds", 0.0),
                )
            )


def load_enriched_jobs(session: Session, org_abbrev: str) -> list[dict]:
    """Query all enriched jobs for an org, returning dicts matching load_output() shape."""
    rows = session.query(Job).filter_by(org_abbrev=org_abbrev).all()
    return [
        {
            "title": r.title,
            "url": r.url,
            "content_type": r.content_type,
            "description": r.description,
            "pdf_path": r.pdf_path,
            "enriched_at": r.enriched_at.isoformat() if r.enriched_at else "",
            "enrich_error": r.enrich_error,
            "enrich_status": r.enrich_status,
            "status_reason": r.status_reason,
            "fetch_method": r.fetch_method,
            "fetch_seconds": r.fetch_seconds,
        }
        for r in rows
    ]


def get_failed_urls(
    session: Session, org_abbrev: str, max_failures: int = 2
) -> set[str]:
    """Return URLs that have failed >= max_failures times for an org."""
    rows = (
        session.query(FetchFailure.url)
        .filter_by(org_abbrev=org_abbrev)
        .filter(FetchFailure.fail_count >= max_failures)
        .all()
    )
    return {r[0] for r in rows}


def record_fetch_failure(
    session: Session,
    url: str,
    org_abbrev: str,
    title: str,
    error: str,
    status: str,
    reason: str,
) -> None:
    """Insert or increment a fetch failure record."""
    now = datetime.now(timezone.utc)
    existing = session.get(FetchFailure, url)
    if existing:
        existing.fail_count += 1
        existing.last_error = error
        existing.last_status = status
        existing.last_reason = reason
        existing.last_failed = now
    else:
        session.add(
            FetchFailure(
                url=url,
                org_abbrev=org_abbrev,
                title=title,
                fail_count=1,
                last_error=error,
                last_status=status,
                last_reason=reason,
                first_failed=now,
                last_failed=now,
            )
        )


def clear_fetch_failure(session: Session, url: str) -> None:
    """Remove a failure record when a job succeeds."""
    existing = session.get(FetchFailure, url)
    if existing:
        session.delete(existing)
