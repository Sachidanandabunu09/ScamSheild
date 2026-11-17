import pytest
from app import db, main
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "https://[broken",
        "javascript:alert(1)",
        "ftp://example.com",
        "https://example.com:99999",
        "https://example.com\\@evil.com",
        "https://-bad.com",
    ],
)
def test_invalid_url_is_a_client_error(client, url):
    response = client.post("/check/url", json={"url": url})
    assert response.status_code == 422
    assert db.stats()["total_checks"] == 0


@pytest.mark.parametrize("text", ["   ", "ab", "x" * 2001])
def test_message_validation(client, text):
    response = client.post("/check/message", json={"text": text})
    assert response.status_code == 422
    assert "input" not in response.text


def test_malformed_link_in_message_is_not_a_server_error(client):
    response = client.post("/check/message", json={"text": "Please read https://[broken"})
    assert response.status_code == 200
    assert response.json()["score"] >= 40


def test_private_input_is_not_persisted_or_exposed(client, database):
    response = client.post("/check/message", json={"text": "My private OTP is 739201"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/history").status_code == 404
    assert db.stats()["total_checks"] == 1
    assert set(inspect(database).get_table_names()) == {"daily_counts"}
    assert {c["name"] for c in inspect(database).get_columns("daily_counts")} == {
        "day",
        "kind",
        "verdict",
        "count",
    }
    assert "739201" not in client.get("/stats").text


def test_dependency_failure_returns_503(client, monkeypatch):
    def fail():
        raise OperationalError("connection failed", {}, Exception())

    monkeypatch.setattr(db, "ping", fail)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


def test_missing_model_is_not_healthy(client, monkeypatch):
    monkeypatch.delitem(main.state, "model")
    assert client.get("/health").status_code == 503


def test_database_write_failure_is_controlled(client, monkeypatch):
    def fail(*args):
        raise OperationalError("private query", {}, Exception())

    monkeypatch.setattr(db, "log_check", fail)
    response = client.post("/check/url", json={"url": "https://example.com"})
    assert response.status_code == 503
    assert "private query" not in response.text


def test_rate_limit_and_readiness_independence(client, monkeypatch):
    monkeypatch.setattr(main, "limiter", main.RateLimiter(requests=2))
    for _ in range(2):
        assert client.post("/check/url", json={"url": "https://example.com"}).status_code == 200
    response = client.post("/check/url", json={"url": "https://example.com"})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert client.get("/health").status_code == 200


def test_model_info_includes_real_evaluation(client):
    data = client.get("/model-info").json()
    assert data["data_audit"]["normalized_train_test_overlap"] == 0
    assert data["evaluation"]["uci_sms"]["high_risk"]["threshold"] == 70
