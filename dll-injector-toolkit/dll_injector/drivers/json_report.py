"""JSON report driver — writes one job result as pretty JSON.

Schema (stable, versioned):
    {
      "schema": 1,
      "tool": "dll-injector-toolkit",
      "version": "0.6.2",
      "started_at": "2026-04-11T14:02:31Z",
      "finished_at": "...",
      "dll": {"path": "...", "sha256": "...", "arch": "x64"},
      "targets": [
        {"pid": 1234, "name": "notepad.exe", "method": "loadlibrary",
         "success": true, "detail": "...", "remote_base": 140234...}
      ]
    }
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from dll_injector import __version__
from dll_injector.models.job import JobResult

log = logging.getLogger(__name__)


def write_report(result: JobResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": 1,
        "tool": "dll-injector-toolkit",
        "version": __version__,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(result.started_at)),
        "finished_at": time