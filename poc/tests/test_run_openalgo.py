"""
Unit tests for openalgo-stream/poc/run_openalgo.py

The wrapper (27 lines) does three things:
  1. Inserts /app/openalgo at sys.path[0] so openalgo's local modules are importable.
  2. Monkey-patches flask_socketio.SocketIO.run() to inject allow_unsafe_werkzeug=True
     via kwargs.setdefault() — caller-supplied values are NOT overwritten.
  3. Delegates to runpy.run_path("/app/openalgo/app.py", run_name="__main__").

Strategy: we stub out flask_socketio, runpy, AND os.chdir so the module can be
executed in-process without a real openalgo installation and without needing
/app/openalgo to exist on the build host.

Test matrix:
  T1 — sys.path[0] is /app/openalgo after the wrapper is executed
  T2 — SocketIO.run() is replaced with _patched_run (not the original)
  T3 — Calling _patched_run without allow_unsafe_werkzeug → flag defaults to True
  T4 — Calling _patched_run with allow_unsafe_werkzeug=False → caller value preserved
       (setdefault must NOT overwrite an explicitly-supplied False)
"""
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

_WRAPPER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "run_openalgo.py"))


def _build_stubs():
    """Return fresh (fake_socketio_mod, orig_run_mock, fake_runpy) stubs."""
    fake_socketio_mod = types.ModuleType("flask_socketio")
    orig_run_mock = MagicMock(name="SocketIO.run_original")

    class FakeSocketIO:
        run = orig_run_mock  # class-level attribute

    fake_socketio_mod.SocketIO = FakeSocketIO

    fake_runpy = MagicMock(name="runpy_stub")
    return fake_socketio_mod, orig_run_mock, fake_runpy


def _exec_wrapper(fake_socketio_mod, fake_runpy):
    """
    Execute run_openalgo.py source in a controlled namespace, stubbing:
      - flask_socketio  → fake_socketio_mod
      - runpy           → fake_runpy
      - os.chdir        → no-op (path /app/openalgo does not exist on build host)
    Returns the namespace dict after execution.
    """
    with open(_WRAPPER_PATH) as fh:
        source = fh.read()

    ns = {"__name__": "__main__", "__file__": _WRAPPER_PATH}

    saved_path = sys.path[:]
    try:
        with patch.dict(
            sys.modules,
            {
                "flask_socketio": fake_socketio_mod,
                "runpy": fake_runpy,
            },
        ):
            with patch("os.chdir"):  # stub out chdir — /app/openalgo won't exist on host
                exec(compile(source, _WRAPPER_PATH, "exec"), ns)  # noqa: S102
    finally:
        # Restore sys.path to avoid cross-test pollution (the wrapper inserts at [0])
        sys.path[:] = saved_path

    return ns


class TestSysPathInsertion(unittest.TestCase):
    """T1: sys.path[0] must be /app/openalgo immediately after the wrapper executes."""

    def test_app_openalgo_is_first_on_syspath(self):
        fake_sm, _, fake_runpy = _build_stubs()
        saved = sys.path[:]
        try:
            # The wrapper calls sys.path.insert(0, "/app/openalgo") at module level.
            # We capture the state inside the patch context before _exec_wrapper
            # restores sys.path, by inspecting what happened inside the exec.

            # Instead of inspecting after restoration, keep the path temporarily.
            # _exec_wrapper restores sys.path in its finally block; so we snapshot
            # what sys.path looked like *just after* exec by running the exec inline.
            with open(_WRAPPER_PATH) as fh:
                source = fh.read()
            ns = {"__name__": "__main__", "__file__": _WRAPPER_PATH}
            with patch.dict(
                sys.modules,
                {"flask_socketio": fake_sm, "runpy": fake_runpy},
            ):
                with patch("os.chdir"):
                    exec(compile(source, _WRAPPER_PATH, "exec"), ns)  # noqa: S102
                    # Inside this block sys.path is still modified
                    path_inside = sys.path[:]

            self.assertEqual(
                path_inside[0],
                "/app/openalgo",
                "Wrapper must insert '/app/openalgo' at sys.path[0]. "
                f"Actual sys.path[0]: {path_inside[0]}",
            )
        finally:
            sys.path[:] = saved


class TestMonkeyPatch(unittest.TestCase):
    """T2: flask_socketio.SocketIO.run must be replaced with _patched_run after exec."""

    def test_socketio_run_is_not_the_original_mock(self):
        fake_sm, orig_run_mock, fake_runpy = _build_stubs()
        _exec_wrapper(fake_sm, fake_runpy)

        patched = fake_sm.SocketIO.run
        self.assertIsNot(
            patched,
            orig_run_mock,
            "After exec, SocketIO.run must be the patched function, not the original mock.",
        )
        self.assertTrue(callable(patched), "SocketIO.run must remain callable after patching.")

    def test_socketio_run_is_a_different_callable(self):
        fake_sm, orig_run_mock, fake_runpy = _build_stubs()
        before = fake_sm.SocketIO.run  # == orig_run_mock
        _exec_wrapper(fake_sm, fake_runpy)
        after = fake_sm.SocketIO.run

        self.assertIsNot(before, after, "run must have been replaced by the wrapper.")


class TestPatchedRunDefaultsToAllowUnsafe(unittest.TestCase):
    """T3: _patched_run defaults allow_unsafe_werkzeug=True when caller omits it."""

    def test_allow_unsafe_werkzeug_defaults_to_true(self):
        fake_sm, orig_run_mock, fake_runpy = _build_stubs()
        _exec_wrapper(fake_sm, fake_runpy)

        patched_run = fake_sm.SocketIO.run
        fake_self = MagicMock(name="socketio_instance")
        fake_app = MagicMock(name="flask_app")

        patched_run(fake_self, fake_app)  # no allow_unsafe_werkzeug supplied

        self.assertTrue(
            orig_run_mock.called,
            "_patched_run must delegate to the original SocketIO.run.",
        )
        _, kwargs_forwarded = orig_run_mock.call_args
        self.assertIn(
            "allow_unsafe_werkzeug",
            kwargs_forwarded,
            "_patched_run must inject allow_unsafe_werkzeug into kwargs.",
        )
        self.assertIs(
            kwargs_forwarded["allow_unsafe_werkzeug"],
            True,
            "Default injected value must be True (not truthy — exactly True). "
            f"Actual: {kwargs_forwarded['allow_unsafe_werkzeug']}",
        )


class TestPatchedRunPreservesCallerValue(unittest.TestCase):
    """T4: _patched_run must NOT overwrite allow_unsafe_werkzeug=False supplied by caller."""

    def test_explicit_false_is_preserved(self):
        fake_sm, orig_run_mock, fake_runpy = _build_stubs()
        _exec_wrapper(fake_sm, fake_runpy)

        patched_run = fake_sm.SocketIO.run
        fake_self = MagicMock(name="socketio_instance")
        fake_app = MagicMock(name="flask_app")

        # Caller explicitly passes False — setdefault must NOT overwrite it
        patched_run(fake_self, fake_app, allow_unsafe_werkzeug=False)

        self.assertTrue(orig_run_mock.called, "_patched_run must delegate to original run.")
        _, kwargs_forwarded = orig_run_mock.call_args
        self.assertIs(
            kwargs_forwarded.get("allow_unsafe_werkzeug"),
            False,
            "When caller explicitly passes allow_unsafe_werkzeug=False, "
            "_patched_run must forward it unchanged (setdefault must not overwrite). "
            f"Actual kwargs forwarded: {kwargs_forwarded}",
        )


if __name__ == "__main__":
    unittest.main()
