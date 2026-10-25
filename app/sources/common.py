from __future__ import annotations

import httpx

class BoardError(LookupError):
    pass


def check_board(response: httpx.Response, token: str) -> None:
    if response.status_code == 404:
        raise BoardError(f"No public board for “{token}”.")
    if response.status_code >= 400:
        raise BoardError(f"Board “{token}” returned HTTP {response.status_code}.")


def location_name(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    if value is None:
        return ""
    return str(value).strip()
