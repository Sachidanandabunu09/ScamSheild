"""One risk scale for messages, links, evaluation and the UI."""

SUSPICIOUS = 40
HIGH_RISK = 70


def verdict(score):
    if score >= HIGH_RISK:
        return "high_risk"
    if score >= SUSPICIOUS:
        return "suspicious"
    return "low_risk"


def message_score(text_score, urls):
    # A dangerous link must never be diluted by harmless surrounding words.
    return round(max([text_score, *(u["score"] for u in urls)]), 1)
