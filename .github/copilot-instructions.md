# Copilot Instructions

## Branch Naming

When suggesting branch names, follow [Conventional Branch 1.1.0](https://conventionalbranch.org) best practices:

**Format:** `<type>/<description>`

**Types:**
- `feature/` (or `feat/`) — new features
- `bugfix/` (or `fix/`) — bug fixes
- `hotfix/` — urgent fixes
- `release/` — release preparation
- `chore/` — non-code tasks (deps, docs, CI, etc.)

**Rules:**
- Lowercase alphanumerics and hyphens only (no spaces, underscores, or uppercase)
- No consecutive, leading, or trailing hyphens
- Keep descriptions concise and purposeful
- Include the issue/ticket number when one exists

**Examples:**
- `feature/issue-1-add-trivy-scan`
- `bugfix/issue-42-fix-login-redirect`
- `chore/update-dependencies`
- `release/v1.2.0`
