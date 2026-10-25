from __future__ import annotations

WORK_MODES = ["remote", "hybrid", "onsite", "unknown"]
SENIORITY = ["intern", "junior", "mid", "senior", "staff", "unknown"]
EMPLOYMENT = ["full-time", "part-time", "contract", "intern", "unknown"]
WORK_AUTH = ["sponsorship", "authorization_required", "citizenship", "unknown"]
TEAM_SIZES = ["1-10", "11-50", "51-200", "201-1000", "1000+"]
POSTED_WITHIN = ["1", "3", "7", "30"]
SOURCES = ["greenhouse", "lever", "ashby", "import"]
DISCARD_REASONS = ["company", "role", "location", "seniority", "compensation", "visa", "other"]
CURRENCIES = ["USD", "INR", "EUR", "GBP"]

LABELS = {
    "work_mode": {
        "remote": "Remote",
        "hybrid": "Hybrid",
        "onsite": "Onsite",
        "unknown": "Unknown",
    },
    "seniority": {
        "intern": "Intern",
        "junior": "Junior",
        "mid": "Mid",
        "senior": "Senior",
        "staff": "Staff",
        "unknown": "Unknown",
    },
    "employment": {
        "full-time": "Full-time",
        "part-time": "Part-time",
        "contract": "Contract",
        "intern": "Intern",
        "unknown": "Unknown",
    },
    "work_auth": {
        "sponsorship": "Sponsorship mentioned",
        "authorization_required": "Authorization required",
        "citizenship": "Citizenship mentioned",
        "unknown": "Unknown",
    },
    "team_size": {
        "1-10": "1–10 people",
        "11-50": "11–50 people",
        "51-200": "51–200 people",
        "201-1000": "201–1,000 people",
        "1000+": "1,000+ people",
    },
    "posted_within": {
        "1": "Past day",
        "3": "Past 3 days",
        "7": "Past week",
        "30": "Past month",
    },
    "source": {
        "greenhouse": "Greenhouse",
        "lever": "Lever",
        "ashby": "Ashby",
        "import": "Import",
    },
    "discard_reason": {
        "company": "Company is wrong for me",
        "role": "Not this role",
        "location": "Wrong location",
        "seniority": "Seniority",
        "compensation": "Compensation",
        "visa": "Work authorization",
        "other": "Other",
    },
}


def vocab_payload() -> dict:
    return {
        "work_modes": WORK_MODES,
        "seniority": SENIORITY,
        "employment": EMPLOYMENT,
        "work_auth": WORK_AUTH,
        "team_sizes": TEAM_SIZES,
        "posted_within": POSTED_WITHIN,
        "sources": SOURCES,
        "discard_reasons": DISCARD_REASONS,
        "currencies": CURRENCIES,
        "labels": LABELS,
    }
