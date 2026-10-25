from __future__ import annotations

import re

# Longer phrases first so "machine learning" is recorded as itself.
CATALOG = [
    "Natural language processing",
    "Large language models",
    "Computer vision",
    "Machine learning",
    "Deep learning",
    "Feature engineering",
    "Data engineering",
    "Data science",
    "System design",
    "scikit-learn",
    "Hugging Face",
    "PostgreSQL",
    "JavaScript",
    "TypeScript",
    "Kubernetes",
    "TensorFlow",
    "PyTorch",
    "FastAPI",
    "Django",
    "Next.js",
    "Node.js",
    "Snowflake",
    "BigQuery",
    "Airflow",
    "GraphQL",
    "MongoDB",
    "Elasticsearch",
    "Transformers",
    "LangChain",
    "Microservices",
    "Power BI",
    "A/B testing",
    "CI/CD",
    "MLOps",
    "OpenCV",
    "Pandas",
    "NumPy",
    "Docker",
    "Terraform",
    "React",
    "Flask",
    "Kafka",
    "Spark",
    "Hadoop",
    "Redis",
    "Linux",
    "Scala",
    "Kotlin",
    "Python",
    "Java",
    "Rust",
    "Ruby",
    "Golang",
    "Tableau",
    "Looker",
    "dbt",
    "AWS",
    "GCP",
    "Azure",
    "SQL",
    "NLP",
    "LLM",
    "RAG",
    "YOLO",
    "Git",
    "C++",
    "C#",
]

_PATTERNS: dict[str, re.Pattern[str]] = {}


def _pattern(skill: str) -> re.Pattern[str]:
    cached = _PATTERNS.get(skill.casefold())
    if cached:
        return cached
    escaped = re.escape(skill.casefold()).replace(r"\ ", r"\s+")
    compiled = re.compile(rf"(?<!\w){escaped}(?!\w)")
    _PATTERNS[skill.casefold()] = compiled
    return compiled


def dedupe_skills(skills: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for skill in skills:
        text = " ".join(str(skill).split())
        if len(text) < 2 or len(text) > 80:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) >= 80:
            break
    return cleaned


def detect_skills(text: str) -> list[str]:
    haystack = (text or "").casefold()
    found = [skill for skill in CATALOG if _pattern(skill).search(haystack)]
    return dedupe_skills(found)


def overlapping_skills(skills: list[str], text: str) -> list[str]:
    haystack = (text or "").casefold()
    return [skill for skill in skills if _pattern(skill).search(haystack)]
