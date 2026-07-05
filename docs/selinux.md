# SELinux Compatibility Guide for Calamus

Fedora is the primary target platform for Calamus, and Fedora ships with
**SELinux enforcing by default**. This guide documents how to test for
compatibility, what risks exist in the codebase, and how CI enforces regression
prevention.

---

## Why SELinux Matters for Calamus

| Calamus Behavior | SELinux Context Risk |
|---|---|
| Reads/writes `~/.config/Calamus/Calamus.conf` | `user_home_t` — generally allowed, verify on first run |
| Opens/saves `.md` files from arbitrary paths | File read/write across multiple `_t` contexts |
| Exports to HTML/PDF/ODT at user-chosen paths | File creation in user-chosen directories |
| `SubprocessMermaidRenderer` calls `mmdc` | `execve()` of external binary — highest risk |
| Docker container accesses X11/Wayland socket | Container label must access display socket |
| WebKit preview loads `file://` URIs | File access under WebKit's sandbox |
| `scripts/fetch-mermaid.sh` runs `curl` | Network egress from script context |

The **`mmdc` subprocess call** is the single highest-risk item. Executing an
external binary from a Python application is a common source of SELinux AVC
denials.

---

## Testing on Fedora with SELinux Enforcing

### Step 1 — Verify SELinux is enforcing

```bash
getenforce
# Should print: Enforcing
```

### Step 2 — Run Calamus and watch for denials

In one terminal, tail the audit log:

```bash
sudo ausearch -m avc -ts recent -f
# or in real-time:
sudo tail -f /var/log/audit/audit.log | grep denied
```

In another terminal, run Calamus:

```bash
uv run calamus
```

Exercise all features: open a file, use Mermaid preview, export to PDF, print.

### Step 3 — Analyze denials with audit2allow

```bash
sudo ausearch -m avc -ts recent | audit2allow -a
```

This shows what policy rules would be needed to allow the denied actions.

### Step 4 — Run in permissive mode to surface all issues at once

```bash
sudo setenforce 0    # permissive — logs but does not block
uv run calamus       # exercise all features
sudo ausearch -m avc -ts recent | audit2allow -a
sudo setenforce 1    # re-enable enforcing when done
```

### Step 5 — Test the Mermaid subprocess path specifically

```bash
# Verify mmdc is accessible from the app's SELinux context
sudo ausearch -m avc -ts recent | grep mmdc
```

If `mmdc` execution is denied, the `SubprocessMermaidRenderer` will fall back
to `FallbackMermaidRenderer` automatically (it catches `PermissionError` and
`OSError`). This is by design — Calamus must degrade gracefully under SELinux
denial rather than crash.

---

## Docker and SELinux

When running the Docker development container on a SELinux-enabled host, volume
mounts require the `:z` (shared) or `:Z` (private) label option:

```bash
# Instead of the default docker compose up, add Z labels for SELinux hosts:
docker compose -f docker-compose.yml -f docker-compose.selinux.yml up app
```

Create `docker-compose.selinux.yml` on your Fedora development machine:

```yaml
services:
  app:
    volumes:
      - .:/app:Z
      - /tmp/.X11-unix:/tmp/.X11-unix:z
```

The `:Z` label re-labels the volume for exclusive container use.
The `:z` label marks it as shared between containers.

---

## SELinux File Contexts Used by Calamus

| Path | Expected SELinux Context | Notes |
|---|---|---|
| `~/.config/Calamus/` | `user_home_t` | Config dir — allowed by default |
| `~/.config/Calamus/Calamus.conf` | `user_home_t` | Config file |
| `calamus/resources/.mermaid-render/` | `user_tmp_t` or `user_home_t` | Temp render work dir |
| `/tmp/.X11-unix/` | `xserver_port_t` | Display socket |
| Exported files | User-chosen — varies | Verify export paths |

---

## CI Enforcement

SELinux compatibility is enforced at three tiers in CI:

### Tier 1 — Static Audit (every PR, GitHub-hosted runner)
The `selinux.yml` workflow scans the codebase for risky patterns:
- Any `subprocess` call not on the approved allowlist fails the build
- Hardcoded absolute paths outside safe contexts are flagged
- New risky patterns require explicit sign-off in PR description

### Tier 2 — Behavioral Regression Tests (every PR, GitHub-hosted runner)
`tests/test_selinux_compat.py` verifies that all code paths that could be
blocked by SELinux handle `PermissionError`, `OSError`, and
`subprocess.CalledProcessError` gracefully, so that SELinux denials never
crash the application.

### Tier 3 — Full Enforcement (self-hosted Fedora 44 runner, on demand)
A self-hosted GitHub Actions runner on Fedora 44 with SELinux enforcing can
run the full test suite in a real SELinux environment. See
`.github/workflows/selinux.yml` for the `selinux-enforcing` job that targets
the `fedora-selinux` runner label.

---

## Approved Subprocess Calls

The following subprocess invocations are approved and documented.
Any new `subprocess` usage must be added to this list and to
`tests/test_selinux_compat.py::APPROVED_SUBPROCESS_COMMANDS` before merging.

| Module | Command | Purpose | SELinux Risk | Mitigation |
|---|---|---|---|---|
| `calamus/mermaid_support.py` | `mmdc` | Render Mermaid diagrams to SVG | Medium — exec of external binary | Caught by `OSError`/`PermissionError`; falls back to `FallbackMermaidRenderer` |

---

## Contributing — SELinux Checklist

When submitting a PR that adds any of the following, include a
**SELinux review** comment explaining why it is safe:

- [ ] Any new `subprocess.run()`, `subprocess.Popen()`, or `os.system()` call
- [ ] Any new file path written outside `~/.config/Calamus/` or `/tmp/`
- [ ] Any new network call (beyond the existing `curl` in fetch scripts)
- [ ] Any new `file://` URI construction
- [ ] Any new Docker volume mount

See the PR template for the required checklist item.
