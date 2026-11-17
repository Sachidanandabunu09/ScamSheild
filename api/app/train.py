"""Run from the repository root: python -m app.train (with PYTHONPATH=api)."""

import csv
import hashlib
import json
import os
import re
from pathlib import Path

import joblib
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from app.indian_data import generate_split
from app.inference import link_results
from app.scoring import HIGH_RISK, SUSPICIOUS, message_score
from app.url_analyzer import mask_urls

API_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", str(API_DIR / "data")))
OUT_DIR = Path(os.getenv("OUT_DIR", str(API_DIR / "model")))


def load_sms():
    with (DATA_DIR / "sms.tsv").open(encoding="utf-8") as file:
        rows = list(csv.reader(file, delimiter="\t"))
    if any(len(row) != 2 or row[0] not in {"ham", "spam"} for row in rows):
        raise ValueError("Dataset must contain exactly two TSV columns: ham/spam and message.")
    return [(text, int(label == "spam")) for label, text in rows]


def normalized(text):
    # Group numeric variants and URL-masked duplicates before the split.
    text = re.sub(r"\d+", "number", mask_urls(text).casefold())
    return " ".join(re.findall(r"\w+", text))


def deduplicate(rows):
    unique, conflicts = {}, set()
    for text, label in rows:
        key = normalized(text)
        if key in unique and unique[key][1] != label:
            conflicts.add(key)
        unique.setdefault(key, (text, label))
    return [row for key, row in unique.items() if key not in conflicts]


def prepare_data():
    sms = load_sms()
    unique_sms = deduplicate(sms)
    sms_train, sms_test = train_test_split(
        unique_sms,
        test_size=0.2,
        random_state=42,
        stratify=[label for _, label in unique_sms],
    )
    indian_train, indian_test, groups = generate_split()
    indian_test = deduplicate(indian_test)
    # Remove cross-source overlap too; evaluation is never fitted by the vectorizer.
    test_keys = {normalized(text) for text, _ in sms_test + indian_test}
    training = deduplicate(sms_train + indian_train)
    training = [(text, label) for text, label in training if normalized(text) not in test_keys]
    assert not ({normalized(text) for text, _ in training} & test_keys)
    return (
        training,
        {"uci_sms": sms_test, "indian_held_out_templates": indian_test},
        {
            "uci_raw_rows": len(sms),
            "uci_unique_groups": len(unique_sms),
            "training_rows": len(training),
            "normalized_train_test_overlap": 0,
            "synthetic_template_split": groups,
        },
    )


def evaluate(model, rows):
    texts, labels = zip(*rows)
    probabilities = model.predict_proba([mask_urls(text) for text in texts])[:, 1]
    scores = [message_score(float(p) * 100, link_results(text)) for text, p in zip(texts, probabilities)]
    report = {"n_test": len(rows), "positive_examples": sum(labels)}
    for name, threshold in [("high_risk", HIGH_RISK), ("flagged_for_review", SUSPICIOUS)]:
        predictions = [int(score >= threshold) for score in scores]
        report[name] = {
            "threshold": threshold,
            "accuracy": round(accuracy_score(labels, predictions), 4),
            "precision": round(precision_score(labels, predictions, zero_division=0), 4),
            "recall": round(recall_score(labels, predictions, zero_division=0), 4),
            "f1": round(f1_score(labels, predictions, zero_division=0), 4),
            "confusion_matrix_tn_fp_fn_tp": confusion_matrix(labels, predictions, labels=[0, 1])
            .ravel()
            .tolist(),
        }
    return report


def main():
    training, tests, audit = prepare_data()
    model = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, strip_accents="unicode"),
            ),
            ("clf", LogisticRegression(C=5, class_weight="balanced", max_iter=2000, random_state=42)),
        ]
    )
    model.fit([mask_urls(text) for text, _ in training], [label for _, label in training])
    report = {
        "model": "TF-IDF word/bigram features + Logistic Regression",
        "sklearn_version": sklearn.__version__,
        "split_seed": 42,
        "data_audit": audit,
        "dataset_sha256": hashlib.sha256((DATA_DIR / "sms.tsv").read_bytes()).hexdigest(),
        "evaluation": {name: evaluate(model, rows) for name, rows in tests.items()},
        "note": "Spam labels are only a proxy for scams. Synthetic template holdouts are not real-world "
        "validation. English only; no claim of calibrated probability or guaranteed safety.",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, OUT_DIR / "model.joblib")
    (OUT_DIR / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()
