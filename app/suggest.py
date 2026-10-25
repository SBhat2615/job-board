"""Suggest Greenhouse, Lever, and Ashby boards from a sample of the public registry."""

from __future__ import annotations

import re

import httpx

from app.config import USER_AGENT
from app.db import connect
from app.market import is_india, is_open_remote
from app.parse import utcnow

_MANIFEST = "https://storage.stapply.ai/jobhive/v1/manifest.json"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
_ROW = re.compile(
    r"https://(?P<host>[a-z0-9.-]+)/(?P<slug>[A-Za-z0-9][A-Za-z0-9._-]{0,80})/(?:jobs/)?[A-Za-z0-9-]+,"
    r"(?P<title>[^\"\n,]{0,180}),"
    r"(?P<company>[^\"\n,]{1,120}),"
    r"(?P<ats>greenhouse|lever|ashby),"
    r"[^,\n]{1,80},"
    r"(?:\"(?P<qloc>[^\"]{1,180})\"|(?P<loc>[^,\n]{1,120}))",
    re.I,
)
_USISH = re.compile(
    r"(?i)("
    r"\bunited states\b|\bu\.s\.a?\b|\busa\b|\bus\b|\bamerica\b|"
    r"\beu\b|\beurope\b|\bgermany\b|\bunited kingdom\b|\buk\b|\bcanada\b|"
    r"\bus-based\b|\bus based\b|\bus-remote\b|\bus remote\b|"
    r"\bnew york\b|\bsan francisco\b|\bseattle\b|\baustin\b|\bboston\b|\bchicago\b|"
    r"\blos angeles\b|\bdenver\b|"
    r"\b(al|ak|az|ar|ca|co|ct|de|fl|ga|hi|ia|id|il|ks|ky|la|ma|md|me|mi|mn|mo|ms|mt|"
    r"nc|nd|ne|nh|nj|nm|nv|ny|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|va|vt|wa|wi|wv|wy|dc)\b"
    r")"
)
_HOSTS = {
    "greenhouse": "greenhouse.io",
    "lever": "lever.co",
    "ashby": "ashbyhq.com",
}


def list_suggestions() -> list[dict]:
    with connect() as conn:
        existing = {
            (row["board_type"], row["board_token"])
            for row in conn.execute(
                "SELECT board_type, board_token FROM companies WHERE board_token IS NOT NULL AND board_token != ''"
            )
        }
        rows = conn.execute(
            """
            SELECT name, board_type, board_token, sample_location, reason
            FROM board_suggestions
            ORDER BY reason = 'India' DESC, name
            """
        ).fetchall()
    suggestions = []
    for row in rows:
        if (row["board_type"], row["board_token"]) in existing:
            continue
        suggestions.append(
            {
                "name": row["name"],
                "board_type": row["board_type"],
                "board_token": row["board_token"],
                "sample_location": row["sample_location"],
                "reason": row["reason"],
            }
        )
    return suggestions


def refresh_suggestions() -> dict:
    timeout = httpx.Timeout(25.0, connect=10.0)
    headers = {"User-Agent": USER_AGENT}
    found: dict[tuple[str, str], dict[str, str]] = {}
    try:
        with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
            manifest = client.get(_MANIFEST)
            if manifest.status_code != 200:
                raise ValueError("The company registry did not respond.")
            payload = manifest.json()
            for ats in ("greenhouse", "lever", "ashby"):
                item = (payload.get("by_ats") or {}).get(ats) or {}
                url = item.get("csv")
                size = int(item.get("size_bytes") or 0)
                if not url or size <= 0:
                    continue
                for start, end in _ranges(size):
                    _sample(client, url, start, end, found)
    except httpx.HTTPError as exc:
        raise ValueError("The company registry could not be reached.") from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The company registry could not be read.") from exc
    ranked = sorted(found.values(), key=lambda item: (item["reason"] != "India", item["name"].casefold()))[:40]
    now = utcnow()
    with connect() as conn:
        conn.execute("DELETE FROM board_suggestions")
        for item in ranked:
            conn.execute(
                """
                INSERT INTO board_suggestions (
                    name, board_type, board_token, sample_location, reason, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (item["name"], item["board_type"], item["board_token"], item["sample_location"], item["reason"], now),
            )
    return {"found": len(ranked), "suggestions": list_suggestions()}


def _ranges(size: int) -> list[tuple[int, int]]:
    width = 450_000
    if size <= width:
        return [(0, max(0, size - 1))]
    spans = []
    for point in (0.02, 0.18, 0.37, 0.55, 0.74, 0.9):
        start = min(size - 1, int(size * point))
        end = min(size - 1, start + width - 1)
        spans.append((start, end))
    return spans


def _sample(client: httpx.Client, url: str, start: int, end: int, found: dict[tuple[str, str], dict[str, str]]) -> None:
    cap = end - start + 1
    try:
        with client.stream("GET", url, headers={"Range": f"bytes={start}-{end}"}) as response:
            if response.status_code not in {200, 206}:
                return
            buf = bytearray()
            for chunk in response.iter_bytes():
                buf.extend(chunk)
                if len(buf) >= cap:
                    break
    except httpx.HTTPError:
        return
    text = bytes(buf).decode("utf-8", "replace")
    for match in _ROW.finditer(text):
        ats = match.group("ats").casefold()
        host = match.group("host").casefold()
        if _HOSTS.get(ats, "\0") not in host:
            continue
        slug = match.group("slug")
        if not _TOKEN.match(slug):
            continue
        location = (match.group("qloc") or match.group("loc") or "").strip()
        if is_india(location):
            reason = "India"
        elif is_open_remote(location) and not _USISH.search(location):
            reason = "Remote"
        else:
            continue
        company = " ".join(match.group("company").split())
        if not company or company.casefold() in {"company", "null"}:
            company = slug
        key = (ats, slug)
        current = found.get(key)
        if current and current["reason"] == "India":
            continue
        if current and reason != "India":
            continue
        found[key] = {
            "name": company[:120],
            "board_type": ats,
            "board_token": slug,
            "sample_location": location[:160],
            "reason": reason,
        }
