import json

import joblib
import pytest
from app import db, main, train
from fastapi.testclient import TestClient
from sqlalchemy import create_engine


@pytest.fixture(scope="session")
def trained_model(tmp_path_factory):
    output = tmp_path_factory.mktemp("model")
    previous = train.OUT_DIR
    train.OUT_DIR = output
    try:
        train.main()
    finally:
        train.OUT_DIR = previous
    return output


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "test.db"))
    monkeypatch.setattr(db, "engine", engine)
    db.init_db()
    yield engine
    engine.dispose()


@pytest.fixture
def client(database, trained_model, monkeypatch):
    monkeypatch.setattr(main, "MODEL_PATH", trained_model / "model.joblib")
    monkeypatch.setattr(main, "limiter", main.RateLimiter(requests=100))
    with TestClient(main.app) as client:
        yield client


@pytest.fixture(scope="session")
def model(trained_model):
    return joblib.load(trained_model / "model.joblib")


@pytest.fixture(scope="session")
def metrics(trained_model):
    return json.loads((trained_model / "metrics.json").read_text())
