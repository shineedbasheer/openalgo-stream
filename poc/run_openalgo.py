#!/usr/bin/env python3
"""POC wrapper for openalgo's app.py.

Flask-SocketIO 5.x refuses to launch the Werkzeug dev server when it cannot
detect a TTY (the supervisord-spawned process has no tty), even with
FLASK_ENV=development. The clean upstream fix is allow_unsafe_werkzeug=True,
but we don't want to modify openalgo's app.py from the POC. So we monkey-patch
SocketIO.run() to inject the flag before executing app.py as __main__.
"""
import os
import runpy
import sys

# Make openalgo's local modules (utils, blueprints, ...) importable
sys.path.insert(0, "/app/openalgo")

import flask_socketio

_orig_run = flask_socketio.SocketIO.run


def _patched_run(self, app, **kwargs):
    kwargs.setdefault("allow_unsafe_werkzeug", True)
    return _orig_run(self, app, **kwargs)


flask_socketio.SocketIO.run = _patched_run

os.chdir("/app/openalgo")
runpy.run_path("/app/openalgo/app.py", run_name="__main__")
