"""Read a posting's own text: constraints, requirement lines, and skill overlap."""

from __future__ import annotations

import re

from app.resume import detect_skills, overlapping_skills

_HEADINGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "requirements",
        (
            "requirements",
            "qualifications",
            "what you'll need",
            "what you’ll need",
            "what you will need",
            "what we're looking for",
            "what we’re looking for",
            "what we are looking for",
            "must have",
            "must-haves",
            "must haves",
            "skills and experience",
            "your background",
            "what you bring",
            "nice to have",
            "nice-to-have",
            "minimum qualifications",
            "basic qualifications",
            "required qualifications",
            "who you are",
            "what you need",
        ),
    ),
    (
        "responsibilities",
        (
            "responsibilities",
            "what you'll do",
            "what you’ll do",
            "what you will do",
            "what you'll be doing",
            "what you’ll be doing",
            "what you will be doing",
            "about the role",
            "the role",
            "your role",
            "in this role",
            "what you'll work on",
            "what you’ll work on",
            "day to day",
        ),
    ),
    (
        "about",
        (
            "about us",
            "about the company",
            "who we are",
            "our story",
            "our mission",
            "the company",
        ),
    ),
    (
        "benefits",
        (
            "benefits",
            "perks",
            "what we offer",
            "why join",
            "why you'll love",
            "compensation and benefits",
        ),
    ),
    (
        "legal",
        (
            "equal opportunity",
            "equal employment",
            "eeo statement",
            "we are an equal",
        ),
    ),
)

_YEARS = re.compile(
    r"(?i)(?:"
    r"(?:at least|minimum(?: of)?|min\.?)\s+(\d{1,2})\s*\+?\s*years"
    r"|(\d{1,2})\s*\+\s*years"
    r"|(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\s*\+?\s*years"
    r"|(\d{1,2})\s+years?(?:\s+of\s+(?:relevant\s+)?(?:experience|exp))"
    r")"
)
_CLOSED = (
    (re.compile(r"(?i)\b(?:u\.?\s?s\.?|usa|united states)\b.{0,30}\b(?:only|citizens?|citizenship)\b"), "US only"),
    (re.compile(r"(?i)\b(?:only|citizens?|citizenship)\b.{0,30}\b(?:u\.?\s?s\.?|usa|united states)\b"), "US only"),
    (re.compile(r"(?i)\bhiring\b.{0,20}\b(?:us|u\.s\.|usa|united states)\s+only\b"), "US only"),
    (re.compile(r"(?i)\b(?:uk|u\.k\.|united kingdom)\b.{0,20}\bonly\b"), "UK only"),
    (re.compile(r"(?i)\b(?:europe|eu)\s+only\b"), "Europe only"),
    (re.compile(r"(?i)\bcanada\s+only\b"), "Canada only"),
)
_US_LOCATION = re.compile(r"(?i)\b(?:united states|u\.s\.a?\.?|usa)\b")
_OPEN = re.compile(
    r"(?i)("
    r"open to (?:anyone|candidates|applicants).{0,50}(?:world|worldwide|anywhere|global)"
    r"|anywhere in the world"
    r"|work from anywhere"
    r"|remote[- ]worldwide"
    r"|open worldwide"
    r"|globally remote"
    r"|regardless of (?:your )?location"
    r")"
)
_RELOCATE_NO = re.compile(
    r"(?i)(no relocation|without relocation|relocation not required|"
    r"not required to relocate|relocation assistance|relocation package|"
    r"relocation support|relocation bonus|relocation offered)"
)
_RELOCATE = re.compile(
    r"(?i)(must relocate|required to relocate|willing to relocate|"
    r"need to relocate|relocation is required|relocation required)"
)


def _heading_kind(line: str) -> str | None:
    text = re.sub(r"^[\s\-*•·\d.)]+", "", line).strip().rstrip(":").strip()
    if not text or len(text) > 80:
        return None
    folded = text.casefold()
    for kind, phrases in _HEADINGS:
        for phrase in phrases:
            if folded == phrase or folded.startswith(phrase + " "):
                return kind
    return None


def split_sections(text: str) -> dict[str, str]:
    buckets: dict[str, list[str]] = {
        "requirements": [],
        "responsibilities": [],
        "about": [],
        "benefits": [],
        "legal": [],
        "other": [],
    }
    current = "other"
    for line in (text or "").splitlines():
        kind = _heading_kind(line)
        if kind:
            current = kind
            continue
        buckets[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in buckets.items()}


def focus_text(sections: dict[str, str]) -> str:
    focused = "\n".join(part for key in ("requirements", "responsibilities") if (part := sections.get(key, "").strip()))
    if focused:
        return focused
    return sections.get("other", "")


def excerpt(sections: dict[str, str]) -> str:
    source = sections.get("requirements") or sections.get("responsibilities") or sections.get("other") or ""
    lines = []
    for raw in source.splitlines():
        line = raw.strip(" -\t•·")
        if len(line) < 8:
            continue
        lines.append(line)
        if len(lines) >= 3:
            break
    return " ".join(lines)[:280]


def _year_spans(text: str) -> list[tuple[int, int | None]]:
    spans: list[tuple[int, int | None]] = []
    for match in _YEARS.finditer(text or ""):
        if match.group(1):
            spans.append((int(match.group(1)), None))
        elif match.group(2):
            spans.append((int(match.group(2)), None))
        elif match.group(3) and match.group(4):
            low = int(match.group(3))
            high = int(match.group(4))
            spans.append((min(low, high), max(low, high)))
        elif match.group(5):
            spans.append((int(match.group(5)), None))
    kept: list[tuple[int, int | None]] = []
    for low, high in spans:
        if low < 1 or low > 40:
            continue
        if high is not None and (high < low or high > 40):
            continue
        kept.append((low, high))
    return kept


def years_span(text: str) -> tuple[int, int | None] | None:
    """The strictest experience range in the requirements, else in the whole posting.

    A closed range such as 3–7 stays 3–7. "5+ years" and "at least 5 years" are a minimum with no ceiling.
    """
    sections = split_sections(text or "")
    focus = focus_text(sections)
    spans = _year_spans(focus) or _year_spans(text or "")
    if not spans:
        return None
    return max(spans, key=lambda item: (item[0], item[1] if item[1] is not None else 99))


def years_required(text: str) -> int | None:
    span = years_span(text)
    if span is None:
        return None
    return span[0]


def years_label(span: tuple[int, int | None] | None) -> str:
    if span is None:
        return ""
    low, high = span
    if high is None:
        return f"{low}+ years"
    if high == low:
        return f"{low} years"
    return f"{low}–{high} years"


def experience_window(yoe_min: int | None, yoe_max: int | None) -> tuple[int, int] | None:
    if yoe_min is None and yoe_max is None:
        return None
    low = yoe_min if yoe_min is not None else yoe_max
    high = yoe_max if yoe_max is not None else yoe_min
    assert low is not None and high is not None
    return (max(0, low - 1), high + 1)


def years_fit(span: tuple[int, int | None] | None, window: tuple[int, int] | None) -> bool:
    """A posting with no stated years stays. A wider range stays when it overlaps the window."""
    if span is None or window is None:
        return True
    low, high = span
    window_low, window_high = window
    span_high = high if high is not None else 40
    return low <= window_high and span_high >= window_low


def _closed_label(text: str, location: str) -> str | None:
    blob = f"{location}\n{text}"
    for pattern, label in _CLOSED:
        if pattern.search(blob):
            return label
    if location and _US_LOCATION.search(location) and "india" not in location.casefold():
        return "US location"
    return None


def detect_flags(
    text: str, location: str, years: int | None, yoe_min: int | None, yoe_max: int | None
) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    closed = _closed_label(text, location)
    if closed:
        flags.append({"kind": "closed", "label": closed})
    if _OPEN.search(text or ""):
        flags.append({"kind": "open", "label": "Open worldwide"})
    if _RELOCATE.search(text or "") and not _RELOCATE_NO.search(text or ""):
        flags.append({"kind": "relocate", "label": "Relocation required"})
    if years is not None:
        flags.append(_years_flag(years, yoe_min, yoe_max))
    return flags


def _years_flag(years: int, yoe_min: int | None, yoe_max: int | None) -> dict[str, str]:
    label = f"{years}+ years"
    if yoe_min is None and yoe_max is None:
        return {"kind": "years", "label": label}
    ceiling = yoe_max if yoe_max is not None else yoe_min
    floor = yoe_min if yoe_min is not None else yoe_max
    assert ceiling is not None and floor is not None
    if years > ceiling:
        return {"kind": "years-high", "label": f"Asks for {years}+ years"}
    if years < floor:
        return {"kind": "years-low", "label": label}
    return {"kind": "years", "label": label}


def _hits(phrases: list[str], text: str) -> list[str]:
    folded = (text or "").casefold()
    return [phrase for phrase in phrases if phrase.casefold() in folded]


def annotate(
    description: str,
    location: str,
    skills: list[str],
    has_resume: bool,
    prefer: list[str],
    avoid: list[str],
    yoe_min: int | None,
    yoe_max: int | None,
) -> dict:
    sections = split_sections(description)
    focus = focus_text(sections)
    span = years_span(description)
    years = span[0] if span else None
    flags = detect_flags(description, location, years, yoe_min, yoe_max)
    if span:
        label = years_label(span)
        for flag in flags:
            if flag["kind"] == "years-high":
                flag["label"] = f"Asks for {label}"
            elif flag["kind"].startswith("years"):
                flag["label"] = label
    matched = overlapping_skills(skills, focus) if has_resume else []
    missing: list[str] = []
    if has_resume:
        known = {skill.casefold() for skill in skills}
        missing = [skill for skill in detect_skills(focus) if skill.casefold() not in known][:8]
    prefer_hits = _hits(prefer, focus)
    avoid_hits = _hits(avoid, f"{location}\n{description}")
    penalty = 0
    if any(flag["kind"] == "years-high" for flag in flags):
        penalty += 4
    if any(flag["kind"] == "closed" for flag in flags):
        penalty += 3
    penalty += len(avoid_hits) * 2
    return {
        "flags": flags,
        "excerpt": excerpt(sections),
        "overlapping_skills": matched,
        "missing_skills": missing,
        "prefer_hits": prefer_hits,
        "avoid_hits": avoid_hits,
        "years_required": years,
        "years_low": span[0] if span else None,
        "years_high": span[1] if span else None,
        "match_score": len(prefer_hits) * 5 + len(matched) * 2 - penalty,
    }


def evidence_sentences(resume: str, description: str) -> list[str]:
    sections = split_sections(description)
    wanted = {skill.casefold() for skill in detect_skills(focus_text(sections))}
    if not wanted:
        return []
    flat = " ".join((resume or "").split())
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", flat) if part.strip()]
    if len(parts) == 1 and len(parts[0]) > 320:
        words = parts[0].split()
        parts = []
        buf: list[str] = []
        for word in words:
            buf.append(word)
            if len(" ".join(buf)) >= 180:
                parts.append(" ".join(buf))
                buf = []
        if buf:
            parts.append(" ".join(buf))
    scored: list[tuple[int, str]] = []
    for part in parts:
        sentence = " ".join(part.split())
        if len(sentence) < 12 or len(sentence) > 320:
            continue
        shared = [skill for skill in detect_skills(sentence) if skill.casefold() in wanted]
        if shared:
            scored.append((len(shared), sentence))
    scored.sort(key=lambda item: (-item[0], item[1]))
    seen: set[str] = set()
    chosen: list[str] = []
    for _, sentence in scored:
        key = sentence.casefold()
        if key in seen:
            continue
        seen.add(key)
        chosen.append(sentence)
        if len(chosen) >= 8:
            break
    return chosen
