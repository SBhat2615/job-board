"""Fetchers for public career pages. Register a new source in FETCHERS."""

from app.sources import ashby, greenhouse, lever

FETCHERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
}
