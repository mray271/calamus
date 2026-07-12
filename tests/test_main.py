"""Tests for the calamus.__main__ entrypoint."""

from __future__ import annotations

import sys
import types


def test_main_constructs_app_and_runs_sys_argv(monkeypatch):
    import calamus.__main__ as entrypoint

    calls = []

    class FakeApplication:
        def __init__(self):
            calls.append("init")

        def run(self, argv):
            calls.append(argv)
            return 23

    fake_module = types.SimpleNamespace(CalamusApplication=FakeApplication)
    monkeypatch.setitem(sys.modules, "calamus.app", fake_module)
    monkeypatch.setattr(sys, "argv", ["calamus", "--preview"])

    assert entrypoint.main() == 23
    assert calls == ["init", ["calamus", "--preview"]]
