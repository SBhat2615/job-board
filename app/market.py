"""India and remote matching for the feed filter and remote-job feeds."""

from __future__ import annotations

INDIA_MARKERS = (
    "india",
    "bengaluru",
    "bangalore",
    "mumbai",
    "bombay",
    "delhi",
    "hyderabad",
    "pune",
    "chennai",
    "noida",
    "gurgaon",
    "gurugram",
    "kolkata",
    "ahmedabad",
    "jaipur",
    "kochi",
    "chandigarh",
    "indore",
    "ncr",
    "karnataka",
    "maharashtra",
    "telangana",
    "tamil nadu",
)

REMOTE_MARKERS = (
    "remote",
    "worldwide",
    "anywhere",
    "work from home",
    "wfh",
    "global",
)

# A listing that names one of these and does not also name India is not an
# open remote role for this board.
CLOSED_MARKERS = (
    "united states only",
    "usa only",
    "us only",
    "u.s. only",
    "united kingdom only",
    "uk only",
    "europe only",
    "eu only",
    "canada only",
    "latam only",
    "north america only",
)


def _blob(*parts: str) -> str:
    return " ".join(part for part in parts if part).casefold()


def is_india(*parts: str) -> bool:
    blob = _blob(*parts)
    return any(marker in blob for marker in INDIA_MARKERS)


def is_remote(location: str, work_mode: str = "") -> bool:
    if work_mode == "remote":
        return True
    blob = _blob(location)
    return any(marker in blob for marker in REMOTE_MARKERS)


def is_open_remote(location: str) -> bool:
    """Remote listings worth keeping from a worldwide feed."""
    blob = _blob(location)
    if is_india(location):
        return True
    if any(marker in blob for marker in ("apac", "asia")):
        return True
    if any(marker in blob for marker in CLOSED_MARKERS) and not is_india(location):
        return False
    if any(marker in blob for marker in ("worldwide", "anywhere", "global")):
        return True
    if "remote" in blob and not any(
        marker in blob for marker in ("united states", "usa", "u.s.", "united kingdom", "europe", "canada", "latam")
    ):
        return True
    return False


def market_ok(location: str, work_mode: str, market: str) -> bool:
    if not market or market == "any":
        return True
    india = is_india(location)
    remote = is_remote(location, work_mode)
    if market == "india":
        return india
    if market == "remote":
        return remote
    if market == "india-remote":
        return india or remote
    return True
