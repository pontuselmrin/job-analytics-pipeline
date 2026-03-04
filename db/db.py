"""SQLAlchemy database layer for enrichment pipeline."""

import os

from sqlalchemy import (
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

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
