---
name: format
description: >-
  Run black and isort formatters on the Calamus codebase inside Docker,
  matching exactly what the CI format check workflow does. Use when the user
  asks to format code, run black, run isort, fix formatting, or check imports.
user-invocable: true
---

# Format Calamus code with black and isort

Calamus uses **black** for code formatting and **isort** for import sorting.
Both must be run inside Docker to match the CI environment exactly.

## Running the formatters (auto-fix)

To format all files in place, run both tools via Docker:

```bash
docker compose run --rm test sh -c "uv run black . && uv run isort ."
```

## Checking only (no changes written)

To check without modifying files — mirroring what CI does:

```bash
docker compose run --rm test sh -c "uv run black --check . && uv run isort --check-only --diff ."
```

## Important notes

- Always run **both** tools together — black first, then isort.
- Never run `black` or `isort` directly on the host; always use `docker compose run --rm test`.
- isort is configured with `profile = "black"` in `pyproject.toml` to ensure compatibility.
- If the CI `black + isort check` workflow fails, run the auto-fix command above, then commit and push.
