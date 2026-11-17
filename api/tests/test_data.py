from datetime import timedelta

from app import db, train
from app.limiter import RateLimiter
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session


def test_no_normalized_overlap_or_shared_templates(metrics):
    training, tests, audit = train.prepare_data()
    train_keys = {train.normalized(text) for text, _ in training}
    for rows in tests.values():
        assert not train_keys & {train.normalized(text) for text, _ in rows}
    for groups in audit["synthetic_template_split"].values():
        assert not set(groups["train"]) & set(groups["test"])
    assert metrics["data_audit"]["normalized_train_test_overlap"] == 0


def test_password_is_not_interpreted_as_a_connection_url(monkeypatch):
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_PASSWORD", "strong@pass/word#?%")
    url = db.database_url()
    assert url.host == "db"
    assert url.password == "strong@pass/word#?%"


def test_daily_counts_retention_and_atomic_increment(database):
    with Session(database) as session:
        session.add(
            db.DailyCount(day=db.cutoff() - timedelta(days=1), kind="url", verdict="high_risk", count=10)
        )
        session.commit()
    assert db.stats()["total_checks"] == 0
    db.log_check("url", "high_risk")
    db.log_check("url", "high_risk")
    assert db.stats()["total_checks"] == 2
    with Session(database) as session:
        rows = session.scalars(select(db.DailyCount)).all()
        assert len(rows) == 1 and rows[0].count == 2


def test_legacy_private_history_removed_idempotently(database):
    with database.begin() as connection:
        connection.execute(text("CREATE TABLE checks (id INTEGER PRIMARY KEY, input_preview TEXT)"))
        connection.execute(text("INSERT INTO checks VALUES (1, 'private OTP')"))
    db.init_db()
    db.init_db()
    assert "checks" not in inspect(database).get_table_names()


def test_rate_limiter_is_bounded_and_expires(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr("app.limiter.time.monotonic", lambda: clock[0])
    limiter = RateLimiter(requests=2, window=60, max_clients=2)
    assert limiter.allow("a") and limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")
    assert not limiter.allow("c")
    clock[0] += 61
    assert limiter.allow("c")
    assert len(limiter.clients) == 1
