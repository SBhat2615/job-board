from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SUFFIX = re.compile(
    r"\b(incorporated|inc|llc|ltd|limited|corp|corporation|co|company|technologies|technology|labs|lab)\b"
)


@dataclass
class Salary:
    low: int
    high: int
    currency: str
    interval: str | None


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def comparable_name(value: str) -> str:
    base = normalize(value)
    stripped = " ".join(_SUFFIX.sub(" ", base).split())
    return stripped or base


def phrase_key(value: str) -> str:
    return " ".join((value or "").casefold().split())


def url_key(url: str | None) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ""
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True) if not key.lower().startswith("utm_")]
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def coerce_datetime(value: object) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d+)?", str(value).strip())):
        number = int(float(str(value).strip()))
        if number > 10_000_000_000:
            number = int(number / 1000)
        if number < 1_000_000_000:
            return None
        return datetime.fromtimestamp(number, timezone.utc).replace(microsecond=0).isoformat()
    text = str(value).strip().replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        match = re.match(r"(\d{4}-\d{2}-\d{2})", text)
        return match.group(1) if match else None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def detect_seniority(title: str) -> str:
    text = (title or "").casefold()
    if re.search(r"\b(intern|internship|co-op|coop)\b", text):
        return "intern"
    if re.search(r"\b(principal|staff|distinguished|fellow|director|vice president|head of)\b", text) or re.search(r"\bvp\b", text):
        return "staff"
    if re.search(r"\b(senior|sr\.?)\b", text) or re.search(r"\blead\b", text):
        return "senior"
    if re.search(r"\b(junior|jr\.?|entry[- ]level|new grad|associate)\b", text):
        return "junior"
    if re.search(r"\b(mid[- ]level|intermediate)\b", text):
        return "mid"
    return "unknown"


def detect_employment(explicit: str | None, title: str, text: str = "") -> str:
    explicit_text = (explicit or "").casefold().replace("_", " ").replace("-", " ")
    if explicit_text:
        if "intern" in explicit_text:
            return "intern"
        if "part" in explicit_text and "time" in explicit_text:
            return "part-time"
        if any(word in explicit_text for word in ("contract", "temporary", "temp")):
            return "contract"
        if "full" in explicit_text or "regular" in explicit_text or "permanent" in explicit_text:
            return "full-time"
    title_text = (title or "").casefold()
    if re.search(r"\bintern", title_text):
        return "intern"
    if "contract" in title_text:
        return "contract"
    blob = (text or "")[:2500].casefold()
    if re.search(r"\bpart[- ]time\b", blob):
        return "part-time"
    if re.search(r"\bfull[- ]time\b", blob):
        return "full-time"
    if re.search(r"\bintern(ship)?\b", blob):
        return "intern"
    return "unknown"


def detect_work_mode(location: str, text: str, workplace: str | None, is_remote: bool | None) -> str:
    workplace_text = (workplace or "").casefold().replace("_", " ")
    if "hybrid" in workplace_text:
        return "hybrid"
    if any(word in workplace_text for word in ("remote", "work from home")):
        return "remote"
    if any(word in workplace_text for word in ("on site", "onsite", "in office", "in person")):
        return "onsite"
    if is_remote is True:
        return "remote"

    loc = (location or "").casefold()
    has_remote = any(word in loc for word in ("remote", "work from home", "wfh"))
    has_hybrid = "hybrid" in loc
    has_onsite = any(word in loc for word in ("on-site", "onsite", "on site", "in-office", "in office"))
    if has_hybrid or (has_remote and has_onsite):
        return "hybrid"
    if has_remote:
        return "remote"
    if has_onsite:
        return "onsite"
    if loc.strip():
        return "onsite"

    head = (text or "")[:2000].casefold()
    if "hybrid" in head:
        return "hybrid"
    if "remote" in head or "work from home" in head:
        return "remote"
    if any(word in head for word in ("on-site", "onsite", "in-office", "in office")):
        return "onsite"
    return "unknown"


_CITIZENSHIP = re.compile(
    r"\b(citizenship required|must be a (?:us |u\.s\. )?citizen|u\.s\. citizenship|us citizenship|security clearance)\b",
    re.I,
)
_NO_SPONSOR = re.compile(
    r"(?i)("
    r"\b(?:no|not|cannot|can't|unable|without|don't|do not|doesn't|does not)\b.{0,40}\bsponsor(?:ship|ed|ing)?\b"
    r"|"
    r"\bsponsor(?:ship)?\b.{0,40}\b(?:not available|unavailable|not offered)\b"
    r"|"
    r"\bmust be (?:legally )?authorized to work\b"
    r"|"
    r"\bmust have .{0,40}\b(?:right|authorization|authorisation) to work\b"
    r")"
)
_SPONSOR = re.compile(
    r"(?i)("
    r"\b(?:visa|immigration)\b.{0,40}\bsponsor(?:ship|ed|ing)?\b"
    r"|"
    r"\bsponsor(?:ship|ed|ing)?\b.{0,40}\b(?:visa|immigration)\b"
    r"|"
    r"\bwill sponsor\b"
    r"|"
    r"\bwe sponsor\b"
    r"|"
    r"\bsponsorship (?:is )?available\b"
    r")"
)


def detect_work_auth(text: str) -> str:
    blob = text or ""
    if _CITIZENSHIP.search(blob):
        return "citizenship"
    if _NO_SPONSOR.search(blob):
        return "authorization_required"
    if _SPONSOR.search(blob):
        return "sponsorship"
    return "unknown"


_MONEY = re.compile(
    r"(?ix)"
    r"(?P<cur>USD|INR|EUR|GBP|₹|€|£|\$)?"
    r"\s*"
    r"(?P<num>\d{1,3}(?:[, ]\d{2,3})+|\d+(?:\.\d+)?)"
    r"\s*"
    r"(?P<k>[kK])?"
    r"(?:\s*(?P<unit>lpa|lakhs?|lacs?))?"
)
_RANGE_GAP = re.compile(r"^\s*(?:-|–|—|to)\s*$", re.I)
_SALARY_WORD = re.compile(r"salary|compensation|\bpay\b|wage", re.I)
_INTERVAL_WORD = re.compile(r"hour|annual|annum|per year|/year|/yr|a year|monthly|per month|/month", re.I)


def _scale_amount(num: str, k: str | None, unit: str | None) -> int | None:
    digits = num.replace(",", "").replace(" ", "")
    try:
        value = float(digits)
    except ValueError:
        return None
    if k:
        value *= 1000
    if unit:
        word = unit.casefold()
        if word == "lpa" or word.startswith("lakh") or word.startswith("lac"):
            value *= 100_000
    rounded = int(round(value))
    if rounded <= 0:
        return None
    return rounded


def _currency_of(token: str | None, unit: str | None) -> str | None:
    if unit and unit.casefold() in {"lpa", "lakh", "lakhs", "lac", "lacs"}:
        forced = "INR"
    else:
        forced = None
    if not token:
        return forced
    mapping = {"$": "USD", "USD": "USD", "€": "EUR", "EUR": "EUR", "£": "GBP", "GBP": "GBP", "₹": "INR", "INR": "INR"}
    return mapping.get(token.upper(), mapping.get(token, forced))


def _interval_of(window: str, unit: str | None) -> str | None:
    if unit:
        return "year"
    text = window.casefold()
    if re.search(r"hour|/hr|\bhr\b", text):
        return "hour"
    if re.search(r"month|/mo\b", text):
        return "month"
    if re.search(r"year|annual|annum|/yr|a year|p\.a", text):
        return "year"
    return None


def parse_salary(text: str) -> Salary | None:
    if not text:
        return None
    tokens = []
    for match in _MONEY.finditer(text):
        amount = _scale_amount(match.group("num"), match.group("k"), match.group("unit"))
        if amount is None:
            continue
        tokens.append(match)
    if not tokens:
        return None

    best: tuple[int, Salary] | None = None
    index = 0
    while index < len(tokens):
        current = tokens[index]
        nxt = tokens[index + 1] if index + 1 < len(tokens) else None
        end = current.end()
        use_next = False
        if nxt and nxt.start() - current.end() <= 16 and _RANGE_GAP.match(text[current.end():nxt.start()]):
            use_next = True
            end = nxt.end()
        window_before = text[max(0, current.start() - 80):current.start()]
        window_after = text[end:end + 40]
        unit = current.group("unit") or (nxt.group("unit") if use_next and nxt else None)
        has_currency = bool(current.group("cur") or (use_next and nxt and nxt.group("cur")))
        has_marker = bool(current.group("k") or current.group("unit") or "," in current.group("num"))
        if use_next and nxt:
            has_marker = has_marker or bool(nxt.group("k") or "," in nxt.group("num"))
        salary_word = bool(_SALARY_WORD.search(window_before))
        interval_word = bool(_INTERVAL_WORD.search(window_after))
        if unit:
            ok = True
        elif has_currency and (has_marker or interval_word or salary_word or use_next):
            ok = True
        elif salary_word and has_marker:
            ok = True
        else:
            ok = False
        if ok:
            low = _scale_amount(current.group("num"), current.group("k"), current.group("unit"))
            high = low
            if use_next and nxt:
                high = _scale_amount(nxt.group("num"), nxt.group("k"), nxt.group("unit")) or low
            if low is None or high is None:
                index += 2 if use_next else 1
                continue
            if high < low:
                low, high = high, low
            currency = _currency_of(current.group("cur"), unit) or (
                _currency_of(nxt.group("cur"), unit) if use_next and nxt else None
            ) or "USD"
            interval = _interval_of(window_after, unit)
            # A bare $80-$85 with no period is too small to treat as pay.
            if interval is None and high < 1000 and not unit:
                ok = False
            if ok:
                score = 0
                score += 4 if has_currency else 0
                score += 4 if salary_word else 0
                score += 4 if unit else 0
                score += 2 if use_next else 0
                score += 2 if has_marker else 0
                score += 2 if interval else 0
                salary = Salary(low=low, high=high, currency=currency, interval=interval)
                if best is None or score > best[0]:
                    best = (score, salary)
        index += 2 if use_next else 1
    if best is None or best[0] < 6:
        return None
    return best[1]


def annual_ceiling(low: int | None, high: int | None, interval: str | None) -> int | None:
    amount = high if high is not None else low
    if amount is None:
        return None
    if interval == "hour":
        return amount * 2080
    if interval == "month":
        return amount * 12
    if interval == "year":
        if amount < 1000:
            return None
        return amount
    if amount >= 10000:
        return amount
    return None


def format_salary(low: int | None, high: int | None, currency: str | None, interval: str | None) -> str | None:
    if low is None and high is None:
        return None
    symbols = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}
    symbol = symbols.get((currency or "").upper(), "")

    def one(value: int) -> str:
        rendered = f"{symbol}{value:,}"
        if not symbol and currency:
            return f"{rendered} {currency.upper()}"
        return rendered

    if low and high and low != high:
        text = f"{one(low)}–{one(high)}"
    else:
        text = one(low or high or 0)
    suffix = {"year": "/year", "hour": "/hour", "month": "/month"}.get(interval or "", "")
    return text + suffix


def normalize_interval(value: str | None) -> str | None:
    if not value:
        return None
    text = value.casefold()
    if "hour" in text:
        return "hour"
    if "month" in text:
        return "month"
    if "year" in text or "annual" in text:
        return "year"
    return None
