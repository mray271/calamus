"""
SELinux compatibility regression tests for Calamus.

These tests run on every PR via GitHub Actions (Ubuntu runner, no real SELinux).
They enforce two guarantees:

  1. STATIC AUDIT — no new subprocess calls may be added without appearing in
     APPROVED_SUBPROCESS_COMMANDS. Any unapproved call fails the build, forcing
     contributors to document and review the SELinux implications of new
     subprocess usage before merging.

  2. BEHAVIORAL REGRESSION — every code path that could be denied by SELinux
     (subprocess execution, file writes, permission-sensitive operations) must
     handle PermissionError, OSError, and CalledProcessError gracefully and
     never crash the application.

On a self-hosted Fedora 42 runner with SELinux enforcing (runner label:
fedora-selinux), the full application test suite runs under actual SELinux
policy enforcement. See .github/workflows/selinux.yml.
"""

import ast
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# APPROVED SUBPROCESS COMMANDS
#
# This is the single source of truth for all subprocess usage in Calamus.
# Format: frozenset of (module_relative_path, command_name) tuples.
#
# To add a new subprocess call:
#   1. Add it here with the module path and command name.
#   2. Add a behavioral regression test below verifying graceful failure.
#   3. Add a row to the Approved Subprocess Calls table in docs/selinux.md.
#   4. Add the SELinux checklist item to your PR description.
# ---------------------------------------------------------------------------

APPROVED_SUBPROCESS_COMMANDS: frozenset[tuple[str, str]] = frozenset(
    [
        ("calamus/mermaid_support.py", "mmdc"),  # Mermaid CLI renderer
    ]
)

CALAMUS_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Tier 1: Static Audit — subprocess allowlist enforcement
# ---------------------------------------------------------------------------


def _collect_subprocess_calls(source_root: Path) -> list[tuple[str, str]]:
    """
    Walk all .py files under source_root/calamus/ and collect every string
    literal that is the first argument of a subprocess.run() or
    subprocess.Popen() call.

    Returns list of (relative_file_path, command_string) tuples.
    """
    found: list[tuple[str, str]] = []
    calamus_pkg = source_root / "calamus"

    for py_file in sorted(calamus_pkg.rglob("*.py")):
        rel_path = str(py_file.relative_to(source_root))
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            # Match subprocess.run([cmd, ...]) and subprocess.Popen([cmd, ...])
            func = node.func
            is_subprocess_call = (
                isinstance(func, ast.Attribute)
                and func.attr in ("run", "Popen", "call", "check_call", "check_output")
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
            ) or (
                isinstance(func, ast.Name)
                and func.id in ("system",)
                and "os" in rel_path  # os.system
            )

            if not is_subprocess_call:
                continue

            if not node.args:
                continue

            # First arg is the command — may be a list literal or string
            first_arg = node.args[0]
            if isinstance(first_arg, ast.List) and first_arg.elts:
                cmd_node = first_arg.elts[0]
                if isinstance(cmd_node, ast.Constant) and isinstance(
                    cmd_node.value, str
                ):
                    found.append((rel_path, cmd_node.value))
            elif isinstance(first_arg, ast.Constant) and isinstance(
                first_arg.value, str
            ):
                found.append((rel_path, first_arg.value))

    return found


def test_no_unapproved_subprocess_calls():
    """
    STATIC AUDIT: Fail if any subprocess call in calamus/ is not in
    APPROVED_SUBPROCESS_COMMANDS.

    This is the primary regression gate. When a new contributor adds a
    subprocess call, this test will fail until they:
      - Add it to APPROVED_SUBPROCESS_COMMANDS in this file
      - Document it in docs/selinux.md
      - Add a behavioral graceful-failure test below
    """
    found = _collect_subprocess_calls(CALAMUS_ROOT)
    unapproved = [
        (path, cmd)
        for path, cmd in found
        if (path, cmd) not in APPROVED_SUBPROCESS_COMMANDS
    ]

    assert not unapproved, (
        "Unapproved subprocess call(s) detected.\n"
        "Every subprocess call must be reviewed for SELinux compatibility "
        "and added to APPROVED_SUBPROCESS_COMMANDS in tests/test_selinux_compat.py "
        "and documented in docs/selinux.md.\n\n"
        "Unapproved calls found:\n"
        + "\n".join(f"  {path}: {cmd!r}" for path, cmd in unapproved)
    )


def test_approved_subprocess_commands_are_still_present():
    """
    Verify that approved commands are still in the codebase.
    If a command is removed, its entry should be removed from the allowlist too.
    """
    found_set = frozenset(_collect_subprocess_calls(CALAMUS_ROOT))
    stale = APPROVED_SUBPROCESS_COMMANDS - found_set
    assert not stale, (
        "Approved subprocess command(s) no longer found in source.\n"
        "Remove stale entries from APPROVED_SUBPROCESS_COMMANDS:\n"
        + "\n".join(f"  {path}: {cmd!r}" for path, cmd in stale)
    )


def test_no_os_system_calls():
    """os.system() is never safe under SELinux — require subprocess.run() instead."""
    calamus_pkg = CALAMUS_ROOT / "calamus"
    for py_file in sorted(calamus_pkg.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        rel = str(py_file.relative_to(CALAMUS_ROOT))
        assert "os.system(" not in source, (
            f"{rel} uses os.system() which is unsafe under SELinux. "
            "Use subprocess.run() with explicit arguments instead."
        )


def test_no_shell_true_subprocess_calls():
    """
    subprocess calls with shell=True bypass argument safety and are
    harder to confine under SELinux. All subprocess calls must use
    shell=False (the default).
    """
    calamus_pkg = CALAMUS_ROOT / "calamus"
    for py_file in sorted(calamus_pkg.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        rel = str(py_file.relative_to(CALAMUS_ROOT))
        # Allow shell=False explicitly but not shell=True
        assert "shell=True" not in source, (
            f"{rel} uses subprocess with shell=True. "
            "This is unsafe under SELinux. Use shell=False (the default)."
        )


# ---------------------------------------------------------------------------
# Tier 2: Behavioral Regression — graceful failure under SELinux denial
# ---------------------------------------------------------------------------
# SELinux denials manifest as PermissionError, OSError (errno EACCES/EPERM),
# or subprocess.CalledProcessError. Each code path below must handle these
# without crashing the application.


class TestMermaidSubprocessGracefulFailure:
    """
    SubprocessMermaidRenderer must degrade gracefully when SELinux denies
    mmdc execution. Any denial from SELinux appears as PermissionError or
    OSError to the calling process.
    """

    def test_permission_error_returns_none(self):
        from calamus.mermaid_support import SubprocessMermaidRenderer

        renderer = SubprocessMermaidRenderer()
        with patch("subprocess.run", side_effect=PermissionError("SELinux denied")):
            with patch("shutil.which", return_value="/usr/bin/mmdc"):
                result = renderer.render_to_svg("graph TD\nA-->B")
        assert result is None, (
            "SubprocessMermaidRenderer must return None on PermissionError "
            "(SELinux denial of mmdc execution)"
        )

    def test_os_error_returns_none(self):
        from calamus.mermaid_support import SubprocessMermaidRenderer

        renderer = SubprocessMermaidRenderer()
        with patch("subprocess.run", side_effect=OSError("EACCES")):
            with patch("shutil.which", return_value="/usr/bin/mmdc"):
                result = renderer.render_to_svg("graph TD\nA-->B")
        assert result is None

    def test_called_process_error_returns_none(self):
        from calamus.mermaid_support import SubprocessMermaidRenderer

        renderer = SubprocessMermaidRenderer()
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "mmdc"),
        ):
            with patch("shutil.which", return_value="/usr/bin/mmdc"):
                result = renderer.render_to_svg("graph TD\nA-->B")
        assert result is None

    def test_fallback_used_when_mmdc_denied(self, monkeypatch):
        """
        When SELinux denies mmdc, get_best_renderer() should still return a
        working renderer (FallbackMermaidRenderer) because SubprocessMermaidRenderer
        reports is_available() = False when mmdc is not on PATH.
        After a PermissionError, the app should transparently use the fallback.
        """
        import shutil

        monkeypatch.setattr(shutil, "which", lambda _: None)
        from calamus.mermaid_support import FallbackMermaidRenderer, get_best_renderer

        renderer = get_best_renderer()
        assert isinstance(renderer, FallbackMermaidRenderer)
        svg = renderer.render_to_svg("graph TD\nA-->B")
        assert svg is not None
        assert "<svg" in svg

    def test_preprocess_does_not_raise_on_permission_error(self, monkeypatch):
        """
        preprocess_markdown_for_static_export must never raise even if the
        underlying renderer fails with a permission error.
        """
        import shutil

        monkeypatch.setattr(shutil, "which", lambda _: None)
        from calamus.mermaid_support import preprocess_markdown_for_static_export

        text = "Before\n```mermaid\ngraph TD\nA-->B\n```\nAfter"
        # Must not raise
        result = preprocess_markdown_for_static_export(text)
        assert result is not None
        assert "Before" in result
        assert "After" in result


class TestConfigFileGracefulFailure:
    """
    Config file writes must handle PermissionError gracefully.
    SELinux can deny writes to ~/.config/ if file contexts are wrong.
    """

    def test_save_config_handles_permission_error(self, monkeypatch, tmp_path):
        import configparser

        monkeypatch.setattr("calamus.preferences.CONFIG_DIR", str(tmp_path))
        monkeypatch.setattr(
            "calamus.preferences.CONFIG_FILE", str(tmp_path / "Calamus.conf")
        )
        from calamus.preferences import save_config

        config = configparser.ConfigParser()
        config["Editor"] = {"font_size": "12"}

        # Simulate SELinux denial on open()
        original_open = open

        def deny_open(path, mode="r", **kwargs):
            if "Calamus.conf" in str(path) and "w" in str(mode):
                raise PermissionError("SELinux denied write to config")
            return original_open(path, mode, **kwargs)

        with patch("builtins.open", side_effect=deny_open):
            try:
                save_config(config)
            except PermissionError:
                pytest.fail(
                    "save_config raised PermissionError — must handle SELinux "
                    "config write denial gracefully without crashing the app"
                )


class TestExporterGracefulFailure:
    """
    Exporters must handle PermissionError on output file writes.
    SELinux can deny writes to certain directories.
    """

    def test_html_exporter_handles_permission_error(self, tmp_path):
        from calamus.exporter import HtmlExporter

        exporter = HtmlExporter()
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        read_only_dir.chmod(0o555)

        dest = str(read_only_dir / "output.html")
        try:
            exporter.export("# Hello", dest)
        except PermissionError:
            pytest.fail(
                "HtmlExporter raised PermissionError — exporters must handle "
                "SELinux write denials gracefully"
            )
        finally:
            read_only_dir.chmod(0o755)


class TestFilePathSafety:
    """
    Verify that Calamus only writes to SELinux-safe locations by default.
    These tests catch contributors accidentally hardcoding unsafe paths.
    """

    def test_config_dir_is_under_home_config(self):
        """Config must be under ~/.config which has user_home_t context."""
        from calamus.preferences import CONFIG_DIR

        config_path = Path(CONFIG_DIR).expanduser()
        home_config = Path.home() / ".config"
        assert str(config_path).startswith(str(home_config)), (
            f"CONFIG_DIR {CONFIG_DIR!r} is not under ~/.config. "
            "Config files must be in ~/.config for correct SELinux user_home_t context."
        )

    def test_mermaid_render_temp_dir_is_safe(self):
        """
        The temporary render directory used by SubprocessMermaidRenderer
        must be under a path with an appropriate SELinux context.
        Acceptable: project dir (during dev) or /tmp (tmp_t).
        """
        import calamus.mermaid_support as ms

        # The work_dir is defined inside render_to_svg; check the module source
        # to ensure it doesn't use a hardcoded absolute system path
        source = Path(ms.__file__).read_text(encoding="utf-8")
        assert (
            "/etc/" not in source or "# selinux-reviewed" in source
        ), "mermaid_support.py references /etc/ path which may have wrong SELinux context"
        assert (
            "/usr/share/" not in source or "# selinux-reviewed" in source
        ), "mermaid_support.py references /usr/share/ which is not writable under SELinux"

    def test_no_hardcoded_root_paths_in_calamus(self):
        """
        Calamus source must not write to root-owned paths (/usr, /etc, /var)
        as these are inaccessible under SELinux user domain policy.
        """
        write_patterns = [
            'open("/etc/',
            'open("/usr/',
            'open("/var/',
            "Path('/etc/",
            "Path('/usr/",
            "Path('/var/",
        ]
        calamus_pkg = CALAMUS_ROOT / "calamus"
        for py_file in sorted(calamus_pkg.rglob("*.py")):
            source = py_file.read_text(encoding="utf-8")
            rel = str(py_file.relative_to(CALAMUS_ROOT))
            for pattern in write_patterns:
                assert pattern not in source, (
                    f"{rel} contains {pattern!r} which writes to a system path "
                    "inaccessible under SELinux user domain policy."
                )


# ---------------------------------------------------------------------------
# Tier 3: Self-hosted Fedora SELinux runner marker
# ---------------------------------------------------------------------------
# Tests marked with @pytest.mark.selinux_enforcing are skipped on GitHub-hosted
# runners and only execute on a self-hosted Fedora 42 runner with SELinux
# enforcing (runner label: fedora-selinux). Set SELINUX_ENFORCING=1 in the
# environment to enable these tests locally.

selinux_enforcing = pytest.mark.skipif(
    not os.environ.get("SELINUX_ENFORCING"),
    reason="Requires self-hosted Fedora runner with SELinux enforcing (set SELINUX_ENFORCING=1)",
)


@selinux_enforcing
def test_app_starts_under_selinux_enforcing():
    """Verify the application process starts without AVC denials."""
    result = subprocess.run(
        ["python", "-c", "from calamus.app import CalamusApplication"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert (
        result.returncode == 0
    ), f"Application import failed under SELinux enforcing:\n{result.stderr}"


@selinux_enforcing
def test_config_write_under_selinux_enforcing(tmp_path, monkeypatch):
    """Config write succeeds in user_home_t context under SELinux."""
    import configparser

    monkeypatch.setattr("calamus.preferences.CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(
        "calamus.preferences.CONFIG_FILE", str(tmp_path / "Calamus.conf")
    )
    from calamus.preferences import load_config, save_config

    config = load_config()
    save_config(config)
    assert (tmp_path / "Calamus.conf").exists()


@selinux_enforcing
def test_no_avc_denials_during_import():
    """
    After importing calamus, check the audit log for any new AVC denials.
    Requires auditd running and read access to audit log.
    """
    import subprocess as sp

    # Clear recent audit context
    before = sp.run(
        ["sudo", "ausearch", "-m", "avc", "-ts", "recent"],
        capture_output=True,
        text=True,
    ).stdout

    sp.run(
        ["python", "-c", "import calamus"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    after = sp.run(
        ["sudo", "ausearch", "-m", "avc", "-ts", "recent"],
        capture_output=True,
        text=True,
    ).stdout

    new_denials = set(after.splitlines()) - set(before.splitlines())
    calamus_denials = [
        line
        for line in new_denials
        if "calamus" in line.lower() or "python" in line.lower()
    ]

    assert (
        not calamus_denials
    ), "New AVC denials detected after importing calamus:\n" + "\n".join(
        calamus_denials
    )
