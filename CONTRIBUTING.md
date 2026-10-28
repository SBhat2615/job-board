# Contributing

Development is halted for now. See the note in the [README](README.md). The steps below are for running the board on your own machine at `http://127.0.0.1:8765`.

## Setup

Python 3.10.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m app
```

Copy `.env.example` to `.env` only for the optional keys. Leave the Turso variables unset so the app uses `data/jobs.sqlite`.

## Before a pull request

```bash
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/pytest
```

Ruff is the formatter. Line length is 120. The GitHub check installs `requirements.lock` and runs the same three commands.

Do not commit `.env`, `data/`, or `.venv`. A resume and the job database live in `data/`.

## Pull requests

Use a short branch name, such as `fix-follow-up-date`. The description should say what changed and how you checked it. The pull-request template lists the checks.
