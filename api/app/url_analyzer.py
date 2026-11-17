"""Explainable heuristic URL risk engine (no training data needed).

Each triggered rule adds points and a human-readable reason. Score 0-100.
"""

import ipaddress
import re
from urllib.parse import unquote, urlsplit

import tldextract

from app.scoring import verdict

SUSPICIOUS_TLDS = {
    "xyz",
    "top",
    "tk",
    "ml",
    "ga",
    "cf",
    "gq",
    "click",
    "link",
    "work",
    "support",
    "live",
    "icu",
    "buzz",
    "cc",
    "cam",
    "rest",
    "monster",
    "country",
}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy", "shorturl.at", "ow.ly"}
KEYWORDS = [
    "login",
    "verify",
    "update",
    "kyc",
    "secure",
    "account",
    "bank",
    "upi",
    "refund",
    "claim",
    "reward",
    "free",
    "otp",
    "suspend",
    "blocked",
    "cashback",
    "gift",
    "pan",
    "aadhaar",
]
BRANDS = {
    "sbi": {"sbi.co.in", "onlinesbi.sbi", "sbi.bank.in"},
    "hdfc": {"hdfcbank.com", "hdfc.com"},
    "icici": {"icicibank.com"},
    "axis": {"axisbank.com"},
    "paytm": {"paytm.com"},
    "phonepe": {"phonepe.com"},
    "amazon": {"amazon.in", "amazon.com"},
    "flipkart": {"flipkart.com"},
    "irctc": {"irctc.co.in"},
    "uidai": {"uidai.gov.in"},
    "incometax": {"incometax.gov.in"},
    "google": {"google.com"},
    "microsoft": {"microsoft.com"},
    "paypal": {"paypal.com"},
}

# Bundled Public Suffix List: no network lookups during inference.
# IDRBT's bank.in/fin.in namespaces may lag behind the bundled PSL snapshot.
EXTRACT = tldextract.TLDExtract(
    suffix_list_urls=(),
    cache_dir=None,
    include_psl_private_domains=True,
    extra_suffixes=["bank.in", "fin.in"],
)
URL_RE = re.compile(
    r"https?://[^\s<>]+|(?<![\w@.-])(?:www\.)?(?:[\w-]+\.)+[a-z\u0080-\uffff]{2,63}"
    r"(?::\d+)?(?:[/\?#][^\s<>]*)?",
    re.I,
)


def extract_urls(text):
    return list(dict.fromkeys(match.group(0).rstrip(".,;!?)\"'") for match in URL_RE.finditer(text)))


def registered_domain(host):
    extracted = EXTRACT(host)
    return extracted.top_domain_under_public_suffix or host


def belongs_to(host, domain):
    return host == domain or host.endswith("." + domain)


def parse_url(url):
    raw = url.strip()
    if not raw or len(raw) > 2000 or any(c.isspace() or ord(c) < 32 for c in raw) or "\\" in raw:
        raise ValueError("Enter a valid HTTP or HTTPS link without spaces.")
    if re.match(r"^[a-z][a-z0-9+.-]*:", raw, re.I) and not re.match(r"^https?://", raw, re.I):
        # Bare host:port is supported; other schemes are rejected.
        if not re.match(r"^[\w.-]+:\d+(?:/|$)", raw):
            raise ValueError("Only HTTP and HTTPS links are supported.")
    try:
        parsed = urlsplit(raw if "://" in raw else "https://" + raw)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError()
        host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        _ = parsed.port  # Validate malformed/out-of-range ports.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if (
                len(host) > 253
                or "." not in host
                or not all(
                    re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split(".")
                )
                or not EXTRACT(host).suffix
            ):
                raise ValueError()
    except (ValueError, UnicodeError):
        raise ValueError("Enter a valid HTTP or HTTPS link with a public domain or IP address.") from None
    return raw, parsed, host


def analyze(url):
    raw, parsed, host = parse_url(url)
    score, reasons = 0, []
    reg = registered_domain(host)

    def add(points, reason):
        nonlocal score
        score += points
        reasons.append(reason)

    known = any(belongs_to(host, domain) for domains in BRANDS.values() for domain in domains)
    try:
        address = ipaddress.ip_address(host)
        add(40, "Uses an IP address instead of a domain.")
        if not address.is_global:
            add(20, "Points to a private or local network address.")
    except ValueError:
        pass
    if parsed.username is not None:
        add(30, "Contains user information before @, which can obscure the destination.")
    if parsed.scheme.lower() != "https":
        add(10, "Does not use HTTPS.")
    if len(raw) > 120:
        add(10, "Unusually long link.")
    if host.count(".") >= 4:
        add(15, "Many subdomains make the destination harder to identify.")
    if host.count("-") >= 2:
        add(10, "Multiple hyphens in the domain.")
    if "xn--" in host:
        add(20, "Internationalized domain: inspect for look-alike characters.")
    if sum(c.isdigit() for c in host) >= 4:
        add(10, "Many digits in the domain.")
    if host.split(".")[-1] in SUSPICIOUS_TLDS:
        add(20, "Domain suffix is associated with common scam templates.")
    if any(belongs_to(host, domain) for domain in SHORTENERS):
        add(40, "Shortened link: the final destination has not been checked.")
    full = (host + unquote(parsed.path) + unquote(parsed.query)).lower()
    hits = [word for word in KEYWORDS if word in full]
    if hits and not known:
        add(min(8 * len(hits), 24), "Sensitive keywords: " + ", ".join(hits[:5]))
    for brand, domains in BRANDS.items():
        if brand in host and not any(belongs_to(host, domain) for domain in domains):
            add(40, f"Contains '{brand}' but uses a different registered domain: {reg}.")
            break
    if known:
        reasons.append("Recognized domain, but hosted content and redirects have not been verified.")
    if not reasons:
        reasons.append("No strong URL patterns found.")
    reasons.append("The page was not opened; a low score does not establish safety.")
    score = min(score, 100)
    return {"url": raw, "score": score, "verdict": verdict(score), "reasons": reasons}


def mask_urls(text):
    def replace(match):
        try:
            score = analyze(match.group(0).rstrip(".,;!?)\"'"))["score"]
        except ValueError:
            score = 40
        return " riskylink " if score >= 40 else " ordinarylink "

    return URL_RE.sub(replace, text)
