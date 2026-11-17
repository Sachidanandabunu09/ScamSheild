# ScamShield India

**Explainable, privacy-first risk screening for suspicious messages and links.**

ScamShield is a small three-container cloud-computing project. A browser sends a message or URL to a FastAPI service, which combines a TF-IDF + logistic-regression text model with readable URL rules. PostgreSQL stores only anonymous daily counters.

It is an educational awareness tool: scores are risk indicators, not calibrated probabilities or proof that something is safe.

```text
Browser
   │
   ▼
Caddy (static UI + /api reverse proxy + optional HTTPS)
   │
   ▼
FastAPI (TF-IDF/logistic regression + URL rules)
   │
   ▼
PostgreSQL (anonymous daily counts only)
```

## What it does

- Screens English SMS/WhatsApp/email text for wording associated with spam and common Indian scam templates.
- Screens HTTP/HTTPS links for look-alike domains, shorteners, risky TLDs, userinfo tricks, IP literals and other patterns.
- Returns a 0–100 score, a verdict and human-readable reasons, including the words that pushed the text score upward.
- Combines text and link results with `max(text score, best link score)` so a dangerous link is not diluted by friendly surrounding words.
- Keeps the last eight previews in the current browser tab only; submitted content is never stored server-side.
- Shows an anonymous rolling 30-day count of checks, plus a live API/database health indicator.

No frontend framework, Redis, Kubernetes, user accounts or external reputation service is required, and submitted links are never opened.

## Architecture

| Container | Responsibility | Ports |
|---|---|---|
| `ui` (Caddy 2) | Serves the static page, proxies `/api/*`, handles optional automatic HTTPS | Local `127.0.0.1:8080`; production `80`/`443` |
| `api` (FastAPI) | Validates input, loads the model, scores messages/links, writes counters | Internal `8000` only |
| `db` (PostgreSQL 16) | Stores anonymous daily `daily_counts` rows | Internal `5432` only |

Caddy strips the `/api` prefix before forwarding; Uvicorn's `--root-path /api` keeps Swagger/OpenAPI URLs correct. Caddy overwrites the forwarded client IP, and the API/database ports are never published. The API runs as a non-root user with a read-only filesystem and a single Uvicorn worker (required by the in-memory limiter).

**Stack:** Python 3.13, FastAPI, Pydantic, scikit-learn, joblib, SQLAlchemy 2, psycopg 3, tldextract, PostgreSQL 16, Caddy 2, vanilla HTML/CSS/JS, Docker Compose, pytest, Ruff and GitHub Actions.

## Project structure

```text
api/
  app/
    main.py          HTTP endpoints, validation, rate limit, error handling
    inference.py     message prediction, link merge, explanations
    url_analyzer.py  URL parsing, risk rules, URL masking
    scoring.py       shared 40/70 thresholds and verdict names
    db.py            anonymous daily counters, retention, schema init
    limiter.py       bounded in-memory per-IP rate limiter
    train.py         training, deduplication and held-out evaluation
    indian_data.py   synthetic India-specific scam/legitimate templates
  tests/             32 regression tests (API, detection, data, privacy)
  data/
    sms.tsv          UCI SMS Spam Collection (5,572 rows)
    README.md        dataset attribution and caveats
  model/             generated artifacts (gitignored): model.joblib, metrics.json
  Dockerfile         trains during build, then serves as non-root user
  requirements.txt   locked runtime dependencies
  requirements-dev.txt  locked test/lint dependencies
ui/
  index.html         accessible single-page interface
  styles.css         responsive sidebar/workspace layout
  app.js             API calls, drafts, in-memory history, health widget
  Caddyfile          static files, API proxy, security headers, HTTPS
  favicon.svg
  Dockerfile
scripts/
  deploy.sh          release build, health gate, rollback
  backup.sh          PostgreSQL custom-format backup
  smoke.py           end-to-end checks against a running deployment
docs/
  ARCHITECTURE.md    request flow, API, privacy, limitations
  DEPLOY_AWS.md      EC2, DNS, HTTPS, rollback and backup guide
  START_RESTART_AWS.md  start/stop runbook for the existing demo instance
  VALIDATION.md      verified results and unverified boundaries
.github/workflows/
  ci.yml             lint, tests, Docker build and three-container smoke test
docker-compose.yml       local stack
docker-compose.prod.yml  standalone cloud stack
pyproject.toml           pytest and Ruff configuration
.env.example             configuration template
```

Generated or local-only paths such as `api/model/`, `*.db`, `.env`, `backups/` and `.releases/` are ignored by Git. `output/` holds standalone report artifacts and is not read by the running application.

## Run locally with Docker

Prerequisites: Docker Desktop or Docker Engine with Compose v2, about 2 GB of free memory, and port 8080 available. Python is not required for this path.

**PowerShell (Windows):**

```powershell
Copy-Item .env.example .env
docker compose up -d --build --wait --wait-timeout 240
```

**Bash (Linux/macOS):**

```bash
cp .env.example .env
docker compose up -d --build --wait --wait-timeout 240
```

Open **http://localhost:8080**. API documentation is at **http://localhost:8080/api/docs**.

The first image build downloads dependencies and trains the model inside the API image; later builds reuse cached layers. Local UI access is bound to `127.0.0.1`, and the API/database have no host ports.

Useful commands:

```bash
docker compose ps
python scripts/smoke.py http://localhost:8080
docker compose logs --tail=50 api
docker compose down
```

Keep the named volumes to retain counters. `docker compose down -v` deletes local database and Caddy volumes.

## Run without Docker

Python 3.13 is used in development, CI and the Docker image.

**Windows:**

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r api/requirements-dev.txt
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check api scripts/smoke.py
.venv/Scripts/ruff.exe format --check api scripts/smoke.py
```

**Linux/macOS:**

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r api/requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check api scripts/smoke.py
.venv/bin/ruff format --check api scripts/smoke.py
```

The suite currently contains **32 tests**. It retrains the model in a temporary directory, then exercises scoring, URL validation, privacy guarantees, retention, rate limiting and error handling.

To train or run the API directly with a disposable SQLite database:

```powershell
$env:PYTHONPATH = "api"
.venv/Scripts/python.exe -m app.train
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
PYTHONPATH=api .venv/bin/python -m app.train
PYTHONPATH=api .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Direct API docs are then at **http://127.0.0.1:8000/docs**. This path serves the API only; use Docker Compose for the full UI + Caddy + PostgreSQL stack. Without `DB_HOST` or `DATABASE_URL`, the API uses `./scamshield.db` (SQLite).

## API

The public paths go through Caddy at `/api`; the FastAPI routes themselves have no prefix.

| Method and path | Purpose |
|---|---|
| `POST /api/check/message` | Analyse `{"text": "..."}`; returns score, verdict, text score, reasons and link results |
| `POST /api/check/url` | Analyse `{"url": "..."}`; returns score, verdict and rule reasons |
| `GET /api/health` | Model and database readiness; `503` if either dependency is unavailable |
| `GET /api/stats` | Anonymous totals by verdict over the retained 30-day window |
| `GET /api/model-info` | Model description, dataset audit/hash, thresholds and evaluation metrics |
| `GET /api/docs` | Interactive Swagger UI |

Example:

```bash
curl -X POST http://localhost:8080/api/check/message \
  -H 'Content-Type: application/json' \
  -d '{"text":"Dear customer, your SBI account will be blocked today. Update KYC immediately: http://sbi-kyc-update221.xyz/login"}'
```

On Windows PowerShell, use `curl.exe` to invoke the real curl binary.

Representative response:

```json
{
  "score": 100,
  "verdict": "high_risk",
  "text_score": 81.7,
  "reasons": [
    "Wording contributing to risk: will be, customer, your, account, update",
    "Link warning: Does not use HTTPS.; Multiple hyphens in the domain.",
    "This is a risk score, not the probability that a message is a scam."
  ],
  "urls_found": [
    {
      "url": "http://sbi-kyc-update221.xyz/login",
      "score": 100,
      "verdict": "high_risk",
      "reasons": [
        "Does not use HTTPS.",
        "Multiple hyphens in the domain.",
        "Domain suffix is associated with common scam templates.",
        "Sensitive keywords: login, update, kyc",
        "Contains 'sbi' but uses a different registered domain: sbi-kyc-update221.xyz.",
        "The page was not opened; a low score does not establish safety."
      ]
    }
  ]
}
```

Input must be 3–2,000 characters. Invalid input returns `422`, rate limiting returns `429` with `Retry-After: 60`, and storage failures return a generic `503` without echoing user input. All responses are `Cache-Control: no-store`.

## How scoring works

Both modes share one scale:

| Score | Verdict | Meaning |
|---:|---|---|
| 0–39 | `low_risk` / Low indicators | Nothing strong was found; this does not prove safety |
| 40–69 | `suspicious` / Needs review | Some warning signs; verify independently |
| 70–100 | `high_risk` / High risk | Strong warning signs; avoid acting without verification |

**Message path**

1. Extract and mask links as `riskylink` or `ordinarylink`, so the text model learns wording rather than domains.
2. Vectorise with TF-IDF word unigrams and bigrams (`min_df=2`, sublinear TF), then classify with logistic regression (`C=5`, balanced class weights).
3. Convert the positive-class probability to a 0–100 text score.
4. Score every extracted link with the URL rule engine.
5. Return `max(text score, link scores)`.
6. Explain the text score using the top positive TF-IDF feature contributions.

**URL rules**

The server parses URLs locally and never visits them. Rules add points and a reason; the total is capped at 100:

| Signal | Points |
|---|---:|
| IP-address host | 40 |
| Private/local IP address | +20 |
| Userinfo before `@` | 30 |
| No HTTPS | 10 |
| Link longer than 120 characters | 10 |
| Four or more dots in the host | 15 |
| Two or more hyphens in the host | 10 |
| Punycode (`xn--`) host | 20 |
| Four or more digits in the host | 10 |
| Risky TLD (`.xyz`, `.top`, `.click`, `.live`, `.icu`, …) | 20 |
| URL shortener (`bit.ly`, `tinyurl.com`, …) | 40 |
| Sensitive keywords (`kyc`, `otp`, `upi`, `refund`, …) | up to 24 |
| Brand name on a different registered domain | 40 |

Known brand domains reduce keyword false positives, but do not bypass HTTPS, userinfo or IP checks. A recognised domain only means the host is known; its content and redirects are still unverified.

## Model and evaluation

The model is built from the UCI SMS Spam Collection plus synthetic India-specific templates. Evaluation uses deduplicated UCI rows and entire held-out synthetic template families, with zero normalized train/test overlap.

| Holdout | Size | Threshold | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| Deduplicated UCI SMS | 1,020 | 70 (high risk) | 98.15% | 88.33% | 92.98% |
| Unseen Indian template families | 21 | 70 (high risk) | 100% | 88.24% | 93.75% |
| Deduplicated UCI SMS | 1,020 | 40 (review) | 72.73% | 93.33% | 81.75% |
| Unseen Indian template families | 21 | 40 (review) | 89.47% | 100% | 94.44% |

Training audit: 5,572 raw UCI rows, 5,099 unique normalized groups, 4,147 training rows, zero normalized train/test overlap. The dataset SHA-256, scikit-learn version, split seed and full confusion matrices are saved in `api/model/metrics.json` and exposed at `/api/model-info`.

**Important caveat:** spam is only a proxy for scams, and the synthetic Indian holdout is tiny (21 rows, 4 negatives). These numbers are diagnostics, not a real-world accuracy claim. Independently collected, labelled Indian scam data would be required before treating this as a production safety system. See [VALIDATION.md](docs/VALIDATION.md).

## Privacy and data handling

- Submitted messages, URLs, previews and IP addresses are **never persisted**.
- The only table is `daily_counts` with `day`, `kind`, `verdict` and `count`.
- Counters use an atomic upsert and are trimmed to the last 30 UTC dates on startup and on writes.
- With two check kinds and three verdicts, retained data is bounded to roughly 180 aggregate rows.
- Recent checks exist only in the current page's JavaScript memory and disappear on reload.
- There is no history endpoint, no login and no user profile.
- API access logging is disabled; Caddy access logging is not enabled.
- The rate limiter keeps transient per-IP counters in memory (30 POSTs per minute, at most 10,000 clients) and resets on restart.
- Initialisation intentionally drops the legacy `checks` table, discarding old raw-input history. Downgrading to v1 is not supported.

## Configuration

Local Compose reads `.env`; start from `.env.example`. Never commit `.env`.

| Variable | Used by | Notes |
|---|---|---|
| `DB_PASSWORD` | Compose | Required. Use a unique value; `deploy.sh` requires at least 20 characters |
| `SITE_ADDRESS` | Caddy | Production domain without scheme/port/path. Local Compose hardcodes `:80` |
| `TAG` | Compose | Image tag. Defaults to `local`; production requires a release tag via `deploy.sh` |
| `DB_HOST` | API | Set by Compose. Its presence switches the API to PostgreSQL |
| `DB_USER` | API | Defaults to `scam` |
| `DB_NAME` | API | Defaults to `scamshield` |
| `DATABASE_URL` | API | Fallback when `DB_HOST` is unset; defaults to SQLite |
| `MODEL_PATH` | API | Defaults to `api/model/model.joblib` |
| `DATA_DIR` | Training | Defaults to `api/data` |
| `OUT_DIR` | Training | Defaults to `api/model` |

Changing `DB_PASSWORD` after PostgreSQL has initialised does not change the stored database password; rotate it through PostgreSQL before updating `.env`.

## Deploy to AWS

The reference path is one Ubuntu EC2 instance with Docker and a domain pointed at its Elastic IP. No AWS access keys, container registry or GitHub deployment secrets are used.

1. Create the server, security group (22 from your IP, 80/443 from the internet) and DNS A record.
2. Install Docker Engine and the Compose plugin.
3. Copy/clone the project, then create and edit `.env` with a strong `DB_PASSWORD` and your real `SITE_ADDRESS`.
4. Run `bash scripts/deploy.sh` on the server.

`deploy.sh` validates configuration, builds uniquely tagged API/UI images, validates the Caddyfile, starts the stack, waits for health, checks the public HTTPS endpoint and only then records the release. A failed update attempts to restore the previous release. Rollback and backup commands are documented in [DEPLOY_AWS.md](docs/DEPLOY_AWS.md); the demo-instance start/stop runbook is [START_RESTART_AWS.md](docs/START_RESTART_AWS.md).

> Note: `START_RESTART_AWS.md` refers to an optional `docker-compose.demo.yml` override that is not present in this checkout. For the standard local stack use `docker-compose.yml`; for the cloud stack use `docker-compose.prod.yml` via `scripts/deploy.sh`.

Caddy obtains and renews certificates automatically when DNS and inbound ports 80/443 are correct. Update and backup examples:

```bash
bash scripts/deploy.sh
bash scripts/deploy.sh --rollback 20261101T120000Z
bash scripts/backup.sh
```

Copy backups off the host and test restores before relying on them.

## Tests and CI

Local quality gates:

```bash
pytest -q
ruff check api scripts/smoke.py
ruff format --check api scripts/smoke.py
node --check ui/app.js
bash -n scripts/deploy.sh scripts/backup.sh
shellcheck scripts/*.sh
```

The GitHub Actions workflow runs those checks, then builds and starts the full Compose stack with a disposable password and runs `scripts/smoke.py`. Smoke coverage includes the UI, `/api` proxy, health, high-risk URL detection, malformed links, validation, Swagger and the absence of a history endpoint.

## Docs

| Document | Contents |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Request lifecycle, API details, privacy model, deliberate limitations |
| [DEPLOY_AWS.md](docs/DEPLOY_AWS.md) | EC2, DNS, HTTPS, deploy, rollback, backup and restore |
| [START_RESTART_AWS.md](docs/START_RESTART_AWS.md) | Start/stop and troubleshoot the existing demo instance |
| [VALIDATION.md](docs/VALIDATION.md) | Verified results, test record and checks still requiring another environment |

## Limitations and responsible use

- **English only.** Hindi, Marathi, transliteration, Hinglish and other languages are not guaranteed.
- **Spam is not synonymous with fraud.** The UCI labels are a training proxy, and synthetic templates are not real reports.
- **Links are never opened.** There is no reputation feed, DNS lookup, redirect expansion, page inspection or sender verification.
- **A low score is not proof of safety.** Verify unexpected requests through an official channel you already trust.
- **Scores are not calibrated probabilities.** The 40/70 thresholds are product decisions, not statistical confidence levels.
- **Single-host demo architecture.** No high availability; back up off-host and keep deployment scope modest.
- **In-memory rate limiting.** It resets on restart and assumes one API worker.
- **Public counters are informational.** They can include automated traffic and are not security analytics.
- **Not a substitute for reporting.** For suspected fraud in India, use official channels such as cybercrime.gov.in or 1930.

## Demo walkthrough

1. Show the three-container diagram and the single request path.
2. Submit `http://hdfc-secure-verify.top/login` and read the rule explanations.
3. Submit the fake SBI KYC message and explain TF-IDF, logistic regression, URL masking and the combined `max` score.
4. Show the in-tab history disappearing after reload, then the anonymous PostgreSQL counters and volume retention.
5. Open `/api/model-info` for the held-out evaluation, dataset hash and explicit caveats.

Discuss [ARCHITECTURE.md](docs/ARCHITECTURE.md) and [VALIDATION.md](docs/VALIDATION.md) before making accuracy or safety claims.

## Training data attribution

`api/data/sms.tsv` is the UCI SMS Spam Collection (5,572 rows; `ham`/`spam` plus text), preserved as supplied.

- Source: [UCI SMS Spam Collection](https://archive.ics.uci.edu/dataset/228/sms+spam+collection)
- Authors: Tiago A. Almeida and Jose Maria Gomez Hidalgo (2011)
- DOI: [10.24432/C5CC84](https://doi.org/10.24432/C5CC84)
- Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

Synthetic Indian examples come from `api/app/indian_data.py`; no user submissions are used for training. See [api/data/README.md](api/data/README.md).
