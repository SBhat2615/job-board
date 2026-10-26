"""Roles read from a resume, and close titles that count as the same role."""

from __future__ import annotations

import os
import re

from app.db import connect, loads
from app.match import focus_text, split_sections
from app.resume import detect_skills

# Each family is one role. A search for any phrase also matches the others.
# Phrases are matched on word boundaries after punctuation is turned into spaces,
# so "machine learning engineer" matches "AI Engineer" and "ML Engineer".
FAMILIES: tuple[dict[str, object], ...] = (
    {
        "label": "Machine learning engineer",
        "phrases": (
            "machine learning engineer",
            "ml engineer",
            "ai engineer",
            "artificial intelligence engineer",
            "ai ml engineer",
            "ml ai engineer",
            "applied machine learning engineer",
            "applied ml engineer",
            "generative ai engineer",
            "genai engineer",
            "llm engineer",
        ),
    },
    {
        "label": "Data scientist",
        "phrases": ("data scientist", "applied scientist", "machine learning scientist"),
    },
    {
        "label": "Data engineer",
        "phrases": ("data engineer", "analytics engineer"),
    },
    {
        "label": "Backend engineer",
        "phrases": ("backend engineer", "back end engineer"),
    },
    {
        "label": "Frontend engineer",
        "phrases": ("frontend engineer", "front end engineer"),
    },
    {
        "label": "Software engineer",
        "phrases": ("software engineer", "full stack engineer", "fullstack engineer"),
    },
)

_DISPLAY = {
    "machine learning engineer": "Machine learning engineer",
    "ml engineer": "ML engineer",
    "ai engineer": "AI engineer",
    "artificial intelligence engineer": "Artificial intelligence engineer",
    "ai ml engineer": "AI/ML engineer",
    "ml ai engineer": "ML/AI engineer",
    "applied machine learning engineer": "Applied machine learning engineer",
    "applied ml engineer": "Applied ML engineer",
    "generative ai engineer": "Generative AI engineer",
    "genai engineer": "GenAI engineer",
    "llm engineer": "LLM engineer",
    "sde (ai)": "SDE (AI)",
    "data scientist": "Data scientist",
    "applied scientist": "Applied scientist",
    "machine learning scientist": "Machine learning scientist",
    "data engineer": "Data engineer",
    "analytics engineer": "Analytics engineer",
    "backend engineer": "Backend engineer",
    "back end engineer": "Back end engineer",
    "frontend engineer": "Frontend engineer",
    "front end engineer": "Front end engineer",
    "software engineer": "Software engineer",
    "full stack engineer": "Full stack engineer",
    "fullstack engineer": "Full stack engineer",
}

# Used only when the resume does not already name a title.
_SKILL_ROLES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("machine learning", "deep learning", "pytorch", "tensorflow", "mlops"),
        "Machine learning engineer",
    ),
    (("natural language processing", "transformers", "langchain"), "Machine learning engineer"),
    (("data science", "pandas", "numpy"), "Data scientist"),
    (("spark", "airflow", "dbt", "snowflake", "bigquery"), "Data engineer"),
    (("react", "next.js", "javascript", "typescript"), "Frontend engineer"),
    (("django", "fastapi", "flask", "node.js"), "Backend engineer"),
)


def _fold(text: str) -> str:
    cleaned = (text or "").casefold().replace("&", " and ")
    cleaned = re.sub(r"[/_|+]+", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9+#.\s]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _has(haystack: str, phrase: str) -> bool:
    return f" {phrase} " in f" {haystack} "


def _has_title(title: str, phrase: str) -> bool:
    """Titles use the plural too, so 'ML Engineers' still counts."""
    padded = f" {title} "
    return f" {phrase} " in padded or f" {phrase}s " in padded


def _family_for(folded: str) -> dict[str, object] | None:
    if not folded:
        return None
    for family in FAMILIES:
        phrases = family["phrases"]
        assert isinstance(phrases, tuple)
        if folded in phrases or any(_has_title(folded, phrase) for phrase in phrases):
            return family
    return None


def _display(phrase: str) -> str:
    return _DISPLAY.get(phrase, phrase.title())


# Phrases a selected role matches. Similar titles are offered separately, not included here.
_OWN: dict[str, tuple[str, ...]] = {
    "machine learning engineer": ("machine learning engineer", "ml engineer"),
    "ai engineer": ("ai engineer", "artificial intelligence engineer"),
    "sde (ai)": ("sde ai", "software development engineer ai", "software engineer ai"),
    "generative ai engineer": ("generative ai engineer", "genai engineer"),
    "llm engineer": ("llm engineer",),
    "applied ml engineer": ("applied ml engineer", "applied machine learning engineer"),
    "data scientist": ("data scientist",),
    "applied scientist": ("applied scientist",),
    "machine learning scientist": ("machine learning scientist",),
    "data engineer": ("data engineer",),
    "analytics engineer": ("analytics engineer",),
    "backend engineer": ("backend engineer", "back end engineer"),
    "frontend engineer": ("frontend engineer", "front end engineer"),
    "software engineer": ("software engineer",),
    "full stack engineer": ("full stack engineer", "fullstack engineer"),
}

_RECS: dict[str, tuple[str, ...]] = {
    "machine learning engineer": (
        "AI engineer",
        "SDE (AI)",
        "Generative AI engineer",
        "LLM engineer",
        "Applied ML engineer",
    ),
    "ai engineer": ("Machine learning engineer", "SDE (AI)", "Generative AI engineer", "LLM engineer"),
    "sde (ai)": ("Machine learning engineer", "AI engineer", "Software engineer"),
    "generative ai engineer": ("Machine learning engineer", "AI engineer", "LLM engineer"),
    "llm engineer": ("Machine learning engineer", "AI engineer", "Generative AI engineer"),
    "applied ml engineer": ("Machine learning engineer", "AI engineer"),
    "data scientist": ("Machine learning engineer", "Applied scientist", "Data engineer"),
    "data engineer": ("Analytics engineer", "Backend engineer", "Data scientist"),
    "software engineer": ("Backend engineer", "Frontend engineer", "SDE (AI)"),
    "backend engineer": ("Software engineer", "Data engineer"),
    "frontend engineer": ("Software engineer",),
}


def _own_key(folded: str) -> str | None:
    if folded in _OWN:
        return folded
    for key, phrases in _OWN.items():
        if _has_title(folded, key) or any(_has_title(folded, phrase) for phrase in phrases):
            return key
    return None


def phrases_for(role: str) -> list[str]:
    folded = _fold(role)
    if not folded:
        return []
    key = _own_key(folded)
    if key:
        return list(_OWN[key])
    return [folded]


def recommendations(role: str) -> list[str]:
    key = _own_key(_fold(role))
    if not key:
        return []
    return list(_RECS.get(key, ()))


def latest_role(text: str) -> str:
    folded = _fold(text)
    padded = f" {folded} "
    best: tuple[int, str] | None = None
    for key, phrases in _OWN.items():
        label = _display(key)
        for phrase in phrases:
            index = padded.find(f" {phrase} ")
            if index >= 0 and (best is None or index < best[0]):
                best = (index, label)
    if best:
        return best[1]
    suggested = suggest_roles(text)
    return suggested[0] if suggested else ""


def also_matches(role: str) -> list[str]:
    folded = _fold(role)
    family = _family_for(folded)
    if not family:
        return []
    phrases = family["phrases"]
    assert isinstance(phrases, tuple)
    labels: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        if phrase == folded or _fold(_display(phrase)) == folded:
            continue
        label = _display(phrase)
        key = label.casefold()
        if key in seen or key == folded:
            continue
        seen.add(key)
        labels.append(label)
        if len(labels) >= 4:
            break
    return labels


def job_matches_role(role: str, title: str, description: str) -> bool:
    phrases = phrases_for(role)
    title_fold = _fold(title)
    body = _fold(description)
    for phrase in phrases:
        if _has_title(title_fold, phrase) or _has(body, phrase):
            return True
    return False


def suggest_roles(text: str) -> list[str]:
    folded = _fold(text)
    found: list[str] = []
    seen: set[str] = set()

    def add(label: str) -> None:
        key = label.casefold()
        if not label or key in seen:
            return
        seen.add(key)
        found.append(label)

    for family in FAMILIES:
        phrases = family["phrases"]
        assert isinstance(phrases, tuple)
        if any(_has_title(folded, phrase) for phrase in phrases):
            add(str(family["label"]))
    skills = {skill.casefold() for skill in detect_skills(text)}
    for needles, label in _SKILL_ROLES:
        if any(needle in skills for needle in needles):
            add(label)
        if len(found) >= 6:
            break
    return found[:6]


def compare_enabled() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def review() -> dict:
    from app.match import experience_window

    with connect() as conn:
        profile = conn.execute("SELECT roles_json, resume_text, yoe_min, yoe_max FROM profile WHERE id = 1").fetchone()
    if profile is None:
        raise KeyError(1)
    resume = profile["resume_text"] or ""
    roles = [str(item) for item in loads(profile["roles_json"], [])]
    latest = latest_role(resume)
    seen: set[str] = set()
    recs: list[str] = []
    seeds = [latest, *roles]
    for seed in seeds:
        for item in recommendations(seed):
            key = item.casefold()
            if key in seen or key == latest.casefold():
                continue
            seen.add(key)
            recs.append(item)
    window = experience_window(profile["yoe_min"], profile["yoe_max"])
    return {
        "latest": latest,
        "recommendations": recs[:8],
        "suggested": suggest_roles(resume),
        "roles": roles,
        "yoe_min": profile["yoe_min"],
        "yoe_max": profile["yoe_max"],
        "window": list(window) if window else None,
        "compare_enabled": compare_enabled(),
    }


def _role_card(role: str, rows: list, known: set[str], has_resume: bool) -> dict:
    matched = [row for row in rows if job_matches_role(role, row["title"] or "", row["description_text"] or "")]
    counts: dict[str, int] = {}
    for row in matched:
        focus = focus_text(split_sections(row["description_text"] or ""))
        for skill in detect_skills(focus):
            counts[skill] = counts.get(skill, 0) + 1
    total = len(matched)
    present: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []
    for skill, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold())):
        entry = {"skill": skill, "postings": count}
        if has_resume and skill.casefold() in known:
            present.append(entry)
        else:
            missing.append(
                {
                    **entry,
                    "note": (
                        f"Adding {skill} would cover a requirement in {count} of {total} "
                        "collected postings for this role."
                    ),
                }
            )
    return {
        "role": role,
        "also_matches": also_matches(role),
        "jobs": total,
        "present": present[:8],
        "missing": missing[:6],
    }
