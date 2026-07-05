## Summary

Brief description of what this PR does.

## Changes

- 
- 

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Chore / maintenance

## Checklist

- [ ] `uv run black --check .` passes
- [ ] `uv run isort --check-only .` passes
- [ ] `uv run pytest` passes
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] New tests added for new functionality

## SELinux Compatibility

- [ ] This PR adds **no new** `subprocess` calls, `os.system()` calls, or writes to system paths
- [ ] **If it does**: new subprocess call added to `APPROVED_SUBPROCESS_COMMANDS` in `tests/test_selinux_compat.py`
- [ ] **If it does**: documented in the Approved Subprocess Calls table in `docs/selinux.md`
- [ ] **If it does**: behavioral regression test added proving graceful failure on `PermissionError`/`OSError`

*Not sure? Read [docs/selinux.md](docs/selinux.md) before submitting.*
