"""Shared scoring used by the API and held-out evaluation."""

from app.scoring import SUSPICIOUS, message_score, verdict
from app.url_analyzer import analyze, extract_urls, mask_urls


def link_results(text):
    results = []
    for url in extract_urls(text):
        try:
            results.append(analyze(url))
        except ValueError:
            results.append(
                {
                    "url": url,
                    "score": 40,
                    "verdict": "suspicious",
                    "reasons": ["Malformed link: its destination could not be checked."],
                }
            )
    return results


def explain(model, text, top=5):
    tfidf, classifier = model.named_steps["tfidf"], model.named_steps["clf"]
    vector = tfidf.transform([text])
    names = tfidf.get_feature_names_out()
    contributions = [
        (names[i], value * classifier.coef_[0][i]) for i, value in zip(vector.indices, vector.data)
    ]
    return [word for word, weight in sorted(contributions, key=lambda row: -row[1])[:top] if weight > 0]


def check_message(model, text):
    masked = mask_urls(text)
    text_score = float(model.predict_proba([masked])[0][1]) * 100
    urls = link_results(text)
    score = message_score(text_score, urls)
    reasons = []
    words = explain(model, masked)
    if words and text_score >= SUSPICIOUS:
        reasons.append("Wording contributing to risk: " + ", ".join(words))
    for link in urls:
        if link["score"] >= 40:
            reasons.append("Link warning: " + "; ".join(link["reasons"][:2]))
    if not reasons:
        reasons.append("No strong indicators were found; this does not establish safety.")
    reasons.append("This is a risk score, not the probability that a message is a scam.")
    return {
        "score": score,
        "verdict": verdict(score),
        "text_score": round(text_score, 1),
        "reasons": reasons,
        "urls_found": urls,
    }
