# Architecture and explanation

## Three responsibilities

| Container | Responsibility | Public access |
|---|---|---|
| UI / Caddy | Static page, reverse proxy and HTTPS | Local 8080; cloud 80/443 |
| API / FastAPI | Validate, classify, explain and count | Internal port 8000 |
| PostgreSQL | Anonymous daily counters | Internal port 5432 |

Caddy strips the /api prefix before forwarding. Uvicorn's --root-path /api preserves the correct Swagger URLs.
Caddy overwrites the forwarded client IP; only this internal proxy can reach the container API.
Do not publish API port 8000 or put an unconfigured CDN in front of Caddy.

## A request from start to finish

1. The browser trims input and sends JSON.
2. The API enforces a 3–2,000-character input limit and 30 POST requests per client IP per minute.
3. A message has links replaced with risk tokens. TF-IDF maps words and word pairs to numeric features.
4. Logistic regression gives a text score. URL rules separately score every detected link.
5. The message score is max(text score, link scores). A dangerous link cannot be hidden by friendly surrounding words.
6. The API returns a verdict, score and explanations, then increments an anonymous daily counter.
7. The browser renders plain text using textContent. The last eight previews stay in page memory only.

The same 40/70 thresholds are used in scoring, evaluation and the UI. Model scores are not calibrated probabilities.
Feature contributions explain what affected the model; they are not proof that a message is fraudulent.

## API

| Method and path | Purpose |
|---|---|
| POST /api/check/message | JSON: {"text": "..."} |
| POST /api/check/url | JSON: {"url": "..."} |
| GET /api/health | Model + database readiness; 503 on dependency failure |
| GET /api/stats | Anonymous totals over the last 30 UTC dates |
| GET /api/model-info | Dataset audit, version, hash, thresholds and evaluation |
| GET /api/docs | Interactive API documentation |

Successful checks return score (0–100), verdict (low_risk/suspicious/high_risk), and reasons.
Message results also include text_score and urls_found.
Invalid inputs return 422; request limits return 429 with Retry-After; unavailable storage returns 503.
There is no /history endpoint and no private user resource requiring login.

## Training and evaluation

- The original UCI dataset has 5,572 rows. Spam is a useful training proxy, but is not the same label as financial fraud.
- Normalize case, URLs, numeric variants and whitespace before deduplication. Conflicting label groups are removed.
- Fit the TF-IDF vocabulary only on training data.
- Hold out entire Indian template IDs, not random messages from every template.
- Remove cross-source normalized overlap from training as well.
- Evaluate the deployed text-plus-link scoring path at 40 and 70, reporting precision, recall, F1 and confusion matrices.
- Save the metrics, split metadata, dataset SHA-256 and scikit-learn version with the model.

Deduplication makes the synthetic test set small. Its score is a diagnostic, not evidence of real-world Indian scam accuracy.
Real labelled, independently collected English/Indian-language scam messages remain necessary before real-world use.
Do not tune rules against this test set repeatedly and continue calling it an untouched evaluation set.

## Privacy and database lifecycle

The daily_counts table contains only day, kind, verdict and count.
It has one row per day/type/verdict combination; atomic upsert avoids lost increments.
Retention is applied on startup and writes; reads exclude dates outside the window even while idle.
With two check types and three verdicts, retained data is bounded to about 180 aggregate rows.

**Upgrade from v1:** initialization creates daily_counts and drops the old checks table, permanently discarding raw input history.
This is an intentional privacy migration, is idempotent, and runs inside a transaction.
Do not downgrade to v1: it restores the old privacy behavior. Saved v2 releases share the same schema.
The old raw history is not included in new counters. Existing old backups may still contain private input and must be handled separately.

For this one-table demo there is no migration framework. If new incompatible schema versions are added, add an explicit versioned migration before deploying them.
Backups and restore commands are in DEPLOY_AWS.md.

## Deliberate scope and remaining limits

- English text only; no guaranteed Hindi, Marathi, transliteration or multilingual detection.
- URL syntax and patterns only: no reputation feed, DNS check, redirect expansion, page inspection or sender verification.
- Recognized domains reduce keyword false positives but do not bypass transport/userinfo checks.
- The bundled Public Suffix List is offline; bank.in and fin.in are explicit supplements. Keep domain examples and dependencies reviewed.
- The limiter is bounded to 10,000 active clients, uses transient IP addresses in memory for one-minute windows, and resets on restart. Stale entries are removed on the next POST request; they are never persisted. Keep one API worker.
- Caddy limits request bodies to 16 KB. The API uses no access log; Caddy access logging is not enabled.
- No submitted input is persisted, but it necessarily exists in request/response memory during processing and in browser memory until reload.
- A single EC2 host and database are a demonstration architecture, not high availability. Backup off-host.
- The public counts are informational, can include automated traffic, and are not security analytics.

## Why Caddy?

It keeps static serving, reverse proxying and certificate management in one container. Public-domain HTTPS requires correct DNS and reachable ports 80/443.
See [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https) and [proxy headers](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
The bank.in/fin.in supplement follows [IDRBT registration guidance](https://registrar.idrbt.ac.in/assets/files/IDRBT%20Terms%20%26%20Conditions.pdf).
