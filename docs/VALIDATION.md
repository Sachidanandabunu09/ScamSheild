# Validation record — 1 November 2026

## Completed locally

- **32 pytest tests passed** with the locked dependencies in an isolated Python 3.13 environment.
- Ruff lint and formatting checks passed.
- JavaScript syntax check passed.
- Bash syntax and ShellCheck checks passed for deployment and backup scripts.
- Both local and standalone production Compose configurations passed validation.
- Caddy 2.11.7 validated the Caddyfile.
- A live Caddy → Uvicorn/FastAPI → SQLite smoke test passed, including model loading, counting, invalid input handling, Swagger prefix handling and removal of the history endpoint.
- Browser checks passed for scam examples, normal messages, malformed URL feedback, mode switching, and history disappearing after reload. Layout was inspected at narrow/mobile and 1,200-pixel desktop widths.
- Normalized training/evaluation overlap is zero; synthetic template IDs are disjoint.

The local preview used loopback HTTP and SQLite because Docker Desktop could not start its engine.
It does not establish that the PostgreSQL container stack or public TLS issuance has passed on this machine.
A dependency deprecation warning about Starlette's httpx test transport is present; tests pass.

## Current model evaluation

The model was rebuilt with scikit-learn 1.9.1. Model artifacts live in api/model/ and are rebuilt inside the API Docker image.

| Holdout | Size | High-risk precision | High-risk recall | High-risk F1 |
|---|---:|---:|---:|---:|
| Deduplicated UCI SMS | 1,020 | 98.15% | 88.33% | 92.98% |
| Unseen Indian template families | 21 normalized groups | 100% | 88.24% | 93.75% |

High-risk threshold: 70/100. Review threshold: 40/100.
The complete report includes both thresholds, confusion matrices, seed, dataset hash, library version and split metadata.

**Interpretation:** the synthetic holdout is tiny and has only four negative groups. These values are not a production accuracy claim.
Obtaining independent real-world Indian scam data is outside the supplied dataset and remains necessary for trustworthy deployment as a public safety service.

## Checks still requiring another environment

- Build and start all three Linux containers with PostgreSQL. The CI workflow includes this check but has not been run on GitHub here.
- Public DNS, certificate issuance and renewals on a real domain.
- EC2 deployment, health-gated rollback, and off-host backup/restore rehearsal.
- Load testing beyond this single-worker educational deployment.

No AWS resource has been provisioned and no cloud deployment has been performed. The user requested preparation because no server exists yet.

## Frontend update — 2 November 2026

The frontend now has a responsive sidebar/workspace layout, segmented message/link controls,
a circular risk indicator, distinct loading/error/empty states, a character counter,
separate in-memory drafts, tab-only history and a real API health indicator.
No frontend framework or external asset service was added.

Verified: live API smoke checks, JavaScript syntax, HTML IDs/assets, high- and low-risk
results, invalid-link feedback, draft switching, clearing history, and mobile layout without page overflow.
Browser console checks reported no JavaScript errors.

Cloud verification: the current URL is http://127.0.0.1:8090, a loopback-only local preview.
This checkout has no production .env, saved .releases/current marker, or hosted Site manifest.
.env.example still contains a placeholder domain; the GitHub workflow tests/builds but does not deploy.
No cloud deployment has been performed in this session. A separately deployed copy cannot be
verified without its URL or AWS access. Follow DEPLOY_AWS.md when a server and domain are available.
