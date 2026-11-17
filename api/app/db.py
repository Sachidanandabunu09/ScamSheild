"""Anonymous daily counters. Never persist submitted text, URLs or IP addresses."""

import os
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Date, Integer, String, create_engine, delete, func, inspect, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

RETENTION_DAYS = 30


def database_url():
    if os.getenv("DB_HOST"):
        return URL.create(
            "postgresql+psycopg",
            username=os.getenv("DB_USER", "scam"),
            password=os.environ["DB_PASSWORD"],
            host=os.environ["DB_HOST"],
            port=5432,
            database=os.getenv("DB_NAME", "scamshield"),
        )
    return os.getenv("DATABASE_URL", "sqlite:///./scamshield.db")


engine = create_engine(database_url(), pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


class DailyCount(Base):
    __tablename__ = "daily_counts"
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), primary_key=True)
    verdict: Mapped[str] = mapped_column(String(20), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


def cutoff():
    return datetime.now(timezone.utc).date() - timedelta(days=RETENTION_DAYS - 1)


def init_db():
    """Idempotent v2 migration: discard the old table containing private submissions.

    Old raw history is intentionally discarded, never copied into the new schema.
    See docs/ARCHITECTURE.md before upgrading an existing deployment.
    """
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
        if inspect(connection).has_table("checks"):
            connection.execute(text("DROP TABLE checks"))
        connection.execute(delete(DailyCount).where(DailyCount.day < cutoff()))


def log_check(kind, verdict):
    insert = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    statement = insert(DailyCount).values(
        day=datetime.now(timezone.utc).date(),
        kind=kind,
        verdict=verdict,
        count=1,
    )
    statement = statement.on_conflict_do_update(
        index_elements=["day", "kind", "verdict"],
        set_={"count": DailyCount.count + 1},
    )
    with Session(engine) as session:
        session.execute(statement)
        session.execute(delete(DailyCount).where(DailyCount.day < cutoff()))
        session.commit()


def stats():
    with Session(engine) as session:
        rows = session.execute(
            select(DailyCount.verdict, func.sum(DailyCount.count))
            .where(DailyCount.day >= cutoff())
            .group_by(DailyCount.verdict)
        ).all()
        counts = {verdict: int(count) for verdict, count in rows}
        return {"total_checks": sum(counts.values()), "by_verdict": counts, "retention_days": RETENTION_DAYS}


def ping():
    with engine.connect() as connection:
        connection.execute(select(1))
