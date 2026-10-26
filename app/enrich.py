from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from app.config import USER_AGENT
from app.parse import comparable_name

_BAD_DESCRIPTION = (
    "fictional",
    "character",
    "surname",
    "family name",
    "given name",
    "album",
    "song",
    "film",
    "television",
    "episode",
    "genus",
    "species",
    "protein",
    "mythology",
    "algorithm",
    "statistical",
    "unit of",
    "research project",
    "disambiguation",
)
_COMPANY_WORDS = ("company", "firm", "corporation", "startup", "business", "subsidiary")
_GENERIC_INDUSTRY = {"company", "business", "enterprise", "organization", "organisation"}
_COMPANY_P31 = ("company", "business", "enterprise", "firm", "startup", "corporation")


@dataclass
class Enrichment:
    matched: bool
    label: str = ""
    team_size: int | None = None
    industry: str | None = None
    summary: str | None = None
    source_url: str | None = None
    signals: list[dict[str, str]] = field(default_factory=list)


def _get(client: httpx.Client, url: str, **kwargs: object) -> dict:
    response = client.get(url, **kwargs)
    response.raise_for_status()
    return response.json()


def _labels_for(client: httpx.Client, ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    payload = _get(
        client,
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbgetentities",
            "ids": "|".join(ids[:50]),
            "props": "labels",
            "languages": "en",
            "format": "json",
        },
    )
    labels = {}
    for qid, entity in (payload.get("entities") or {}).items():
        label = ((entity.get("labels") or {}).get("en") or {}).get("value")
        if label:
            labels[qid] = label
    return labels


def _latest_employees(claims: list[dict]) -> tuple[int | None, str | None]:
    dated: list[tuple[str, int]] = []
    undated: list[int] = []
    for claim in claims:
        amount = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("amount")
        if not amount:
            continue
        try:
            count = int(round(float(str(amount).lstrip("+"))))
        except ValueError:
            continue
        times = []
        for qualifier in (claim.get("qualifiers") or {}).get("P585", []):
            time = ((qualifier.get("datavalue") or {}).get("value") or {}).get("time")
            if time:
                times.append(str(time))
        if times:
            dated.append((max(times), count))
        else:
            undated.append(count)
    if dated:
        time, count = max(dated)
        year = time[1:5] if len(time) >= 5 else None
        return count, year
    if undated:
        return undated[-1], None
    return None, None


def _entity_is_company(description: str, p31_labels: list[str]) -> bool:
    text = description.casefold()
    if any(word in text for word in _COMPANY_WORDS):
        return True
    for label in p31_labels:
        folded = label.casefold()
        if any(word in folded for word in _COMPANY_P31):
            return True
    return False


def _industry_from(p452: list[str]) -> str | None:
    # Industry comes from Wikidata's industry property, not "instance of".
    # Instance-of labels such as "startup company" are not an industry.
    for label in p452:
        if label.casefold() not in _GENERIC_INDUSTRY:
            return label
    return None


def _tavily_signals(client: httpx.Client, label: str) -> list[dict[str, str]]:
    import os

    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        return []
    try:
        response = client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": f"{label} company overview",
                "max_results": 3,
                "search_depth": "basic",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError:
        return []
    signals = []
    for item in (payload.get("results") or [])[:3]:
        url = str(item.get("url") or "")
        snippet = " ".join(str(item.get("content") or "").split())
        title = str(item.get("title") or "Web")
        if not url or not snippet:
            continue
        signals.append({"source": title[:80] or "Web", "text": snippet[:500], "url": url})
    return signals


def lookup_company(client: httpx.Client, name: str) -> Enrichment:
    search = _get(
        client,
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "format": "json",
            "type": "item",
            "limit": 8,
        },
    )
    wanted = comparable_name(name)
    candidates = []
    for hit in search.get("search") or []:
        label = str(hit.get("label") or "")
        description = str(hit.get("description") or "")
        if not label or comparable_name(label) != wanted:
            continue
        if any(word in description.casefold() for word in _BAD_DESCRIPTION):
            continue
        candidates.append(hit)
    if not candidates:
        return Enrichment(matched=False)

    ids = [hit["id"] for hit in candidates if hit.get("id")]
    entities = (
        _get(
            client,
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbgetentities",
                "ids": "|".join(ids),
                "props": "claims|sitelinks",
                "format": "json",
            },
        ).get("entities")
        or {}
    )

    p31_ids: list[str] = []
    p452_ids: list[str] = []
    for qid in ids:
        claims = (entities.get(qid) or {}).get("claims") or {}
        for claim in claims.get("P31", []):
            target = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("id")
            if target:
                p31_ids.append(target)
        for claim in claims.get("P452", []):
            target = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("id")
            if target:
                p452_ids.append(target)
    labels = _labels_for(client, list(dict.fromkeys(p31_ids + p452_ids)))

    best: tuple[int, str, Enrichment] | None = None
    descriptions = {hit["id"]: str(hit.get("description") or "") for hit in candidates}
    labels_by_id = {hit["id"]: str(hit.get("label") or "") for hit in candidates}
    for qid in ids:
        entity = entities.get(qid) or {}
        claims = entity.get("claims") or {}
        p31_labels = []
        for claim in claims.get("P31", []):
            target = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("id")
            if target and target in labels:
                p31_labels.append(labels[target])
        p452_labels = []
        for claim in claims.get("P452", []):
            target = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("id")
            if target and target in labels:
                p452_labels.append(labels[target])
        description = descriptions.get(qid, "")
        if not _entity_is_company(description, p31_labels):
            continue
        team_size, year = _latest_employees(claims.get("P1128", []))
        industry = _industry_from(p452_labels)
        wiki_title = ((entity.get("sitelinks") or {}).get("enwiki") or {}).get("title")
        score = 0
        if any(word in description.casefold() for word in _COMPANY_WORDS):
            score += 2
        if p31_labels:
            score += 4
        if team_size:
            score += 2
        if wiki_title:
            score += 1
        enrichment = Enrichment(
            matched=True,
            label=labels_by_id.get(qid, name),
            team_size=team_size,
            industry=industry,
            source_url=f"https://www.wikidata.org/wiki/{qid}",
        )
        if team_size or industry:
            enrichment.signals.append(
                {
                    "source": "Wikidata",
                    "text": _wikidata_text(team_size, year, industry),
                    "url": enrichment.source_url or "",
                }
            )
        if wiki_title:
            summary, page = _wikipedia(client, wiki_title)
            if summary:
                enrichment.summary = summary
            if page:
                enrichment.source_url = page
        if best is None or score > best[0]:
            best = (score, qid, enrichment)
    if best is None:
        return Enrichment(matched=False)
    enrichment = best[2]
    enrichment.signals.extend(_tavily_signals(client, enrichment.label or name))
    return enrichment


def _wikidata_text(team_size: int | None, year: str | None, industry: str | None) -> str:
    bits = []
    if team_size:
        when = f" ({year})" if year else ""
        bits.append(f"About {team_size:,} employees{when}")
    if industry:
        bits.append(f"Industry: {industry}")
    if not bits:
        return "Public company record."
    return ". ".join(bits) + "."


def _wikipedia(client: httpx.Client, title: str) -> tuple[str | None, str | None]:
    from urllib.parse import quote

    try:
        payload = _get(client, f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='')}")
    except httpx.HTTPError:
        return None, None
    extract = " ".join(str(payload.get("extract") or "").split())
    page = ((payload.get("content_urls") or {}).get("desktop") or {}).get("page")
    if len(extract) > 700:
        extract = extract[:700].rsplit(" ", 1)[0] + "…"
    return (extract or None), page


def enrich_company(conn, company_id: int, *, replace: bool = False) -> dict:
    """Fill blank public facts. Network failures leave the row unchanged."""
    from app.db import dumps
    from app.parse import utcnow

    row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    if row is None:
        raise KeyError(company_id)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    try:
        with httpx.Client(timeout=12, headers=headers, follow_redirects=True) as client:
            found = lookup_company(client, row["name"])
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Public company lookup failed for {row['name']}.") from exc

    team_size = row["team_size"]
    industry = row["industry"]
    summary = row["summary"]
    if found.matched:
        if replace:
            team_size = found.team_size
            industry = found.industry
            summary = found.summary
        else:
            if team_size is None and found.team_size is not None:
                team_size = found.team_size
            if not industry and found.industry:
                industry = found.industry
            if not summary and found.summary:
                summary = found.summary
    conn.execute(
        """
        UPDATE companies
        SET team_size = ?, industry = ?, summary = ?, signals_json = ?, source_url = ?,
            enriched_at = ?, user_edited = ?
        WHERE id = ?
        """,
        (
            team_size,
            industry,
            summary,
            dumps(found.signals if found.matched else []),
            found.source_url if found.matched else row["source_url"],
            utcnow(),
            0 if replace and found.matched else row["user_edited"],
            company_id,
        ),
    )
    return {
        "matched": found.matched,
        "team_size": team_size,
        "industry": industry,
        "summary": summary,
        "signals": found.signals if found.matched else [],
    }
