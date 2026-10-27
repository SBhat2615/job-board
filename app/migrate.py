"""Apply numbered files in app/migrations once, and record them."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from app.parse import utcnow

_MIGRATIONS = Path(__file__).resolve().parent / "migrations"
_FILE = re.compile(r"^(\d+)_([A-Za-z0-9_]+)\.(sql|py)$")


def _script(conn, script: str) -> None:
    run = getattr(conn, "executescript", None)
    if run is not None:
        run(script)
        return
    pending: list[str] = []
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        pending.append(line)
        if stripped.endswith(";"):
            statement = "\n".join(pending).strip().rstrip(";")
            pending = []
            if statement:
                conn.execute(statement)
    if pending:
        statement = "\n".join(pending).strip().rstrip(";")
        if statement:
            conn.execute(statement)


def _load() -> list[tuple[int, str, object]]:
    found: dict[int, tuple[str, object]] = {}
    for path in sorted(_MIGRATIONS.iterdir()):
        match = _FILE.match(path.name)
        if match is None:
            continue
        version = int(match.group(1))
        name = match.group(2)
        if version in found:
            raise RuntimeError(f"Two migrations are numbered {version}.")
        if path.suffix == ".sql":
            script = path.read_text(encoding="utf-8")

            def up(conn, sql=script) -> None:
                _script(conn, sql)

            found[version] = (name, up)
        else:
            spec = importlib.util.spec_from_file_location(f"jobboard_migration_{version}", path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Could not load {path.name}.")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            found[version] = (name, module.up)
    versions = sorted(found)
    if versions != list(range(1, len(versions) + 1)):
        raise RuntimeError("Migrations must be numbered 1, 2, 3, with no gaps.")
    return [(version, found[version][0], found[version][1]) for version in versions]


def migrate(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied = {int(row["version"]) for row in conn.execute("SELECT version FROM schema_migrations")}
    for version, name, up in _load():
        if version in applied:
            continue
        up(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (version, name, utcnow()),
        )
