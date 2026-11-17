import pytest
from app.inference import check_message
from app.scoring import verdict
from app.url_analyzer import analyze, extract_urls, registered_domain


def test_bank_suffix_and_domain_boundary():
    assert registered_domain("www.sbi.bank.in") == "sbi.bank.in"
    official = analyze("https://sbi.bank.in")
    assert official["verdict"] == "low_risk"
    assert not any("different registered domain" in reason for reason in official["reasons"])
    fake = analyze("https://sbi.bank.in.attacker.com/login/verify")
    assert fake["score"] >= 40


def test_allowlist_does_not_skip_transport_or_userinfo_checks():
    assert analyze("http://sbi.co.in")["score"] >= 10
    assert analyze("https://person@sbi.co.in")["score"] >= 30
    assert any("not been verified" in reason for reason in analyze("https://docs.google.com/evil")["reasons"])


def test_bare_domains_and_shorteners_are_extracted():
    assert extract_urls("Visit scam-example.com/login or rb.gy/abc123.") == [
        "scam-example.com/login",
        "rb.gy/abc123",
    ]
    assert extract_urls("Email person@example.com") == []
    assert extract_urls("Email person@example.co.in") == []
    assert analyze("rb.gy/abc123")["score"] >= 40


def test_bad_link_cannot_be_diluted_by_friendly_text(model):
    url = "https://hdfc-secure-verify.top/login"
    result = check_message(model, "Hey friend, here is the link for our meeting " + url)
    assert result["score"] >= analyze(url)["score"]
    assert result["verdict"] == "high_risk"


@pytest.mark.parametrize(
    "score, expected",
    [
        (0, "low_risk"),
        (39.9, "low_risk"),
        (40, "suspicious"),
        (69.9, "suspicious"),
        (70, "high_risk"),
        (100, "high_risk"),
    ],
)
def test_verdict_boundaries(score, expected):
    assert verdict(score) == expected
