# Security

This board stores a resume, drafts, and application notes in a local SQLite file, or in Turso when that database is configured.

## Reporting a problem

Use a [private security advisory](https://github.com/SBhat2615/job-board/security/advisories/new) on this repository. Do not open a public issue for it.

Leave the resume, tokens, and the contents of `data/` out of the report. A description of the request and the file involved is enough.

## What not to commit

`.env`, Turso tokens, and `data/` are gitignored. If one of those reaches a commit, say so in the advisory so the secret can be rotated.
