"""End-to-end checks against a running local or HTTPS deployment."""

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8080"


def request(path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = Request(base + path, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, response.read().decode()
    except HTTPError as error:
        return error.code, error.read().decode()


status, html = request("/")
assert status == 200 and "ScamShield India" in html
status, body = request("/api/health")
assert status == 200 and json.loads(body)["database"] == "ok"
status, body = request("/api/check/url", {"url": "https://hdfc-secure-verify.top/login"})
assert status == 200 and json.loads(body)["verdict"] == "high_risk"
status, body = request("/api/check/message", {"text": "Please read https://[broken"})
assert status == 200 and json.loads(body)["score"] >= 40
status, body = request("/api/check/url", {"url": "not a url"})
assert status == 422
assert request("/api/history")[0] == 404
status, docs = request("/api/docs")
assert status == 200 and "/api/openapi.json" in docs
assert request("/api/openapi.json")[0] == 200
print("Smoke checks passed: UI, proxy, API, model, database, validation and privacy.")
