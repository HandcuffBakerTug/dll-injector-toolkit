"""Resolve target specs (name or PID) into concrete TargetProcess records.

Inputs are the raw strings from the CLI --target flags. We accept:
    - "notepad.exe"        → first match by image name
    - "notepad"            → same, extension optional
    - "1234"               → treated as PID
    - "*chrome*"           → glob over image names, all matches

Returns a tuple of TargetProcess. Raises TargetNotFoundError if a spec
matches nothing and it is the only spec; otherwise we log and continue.
"""
from __future__ import annotations

import fnmatch
import logging

from dll_injector.models.target import TargetProcess
from dll_injector.utils import winapi

log = logging.getLogger(__name__)


class TargetNotFoundError(LookupError):
    """Raised when a target spec cannot be resolved to any process."""


def _iter_processes() -> list[TargetProcess]:
    return winapi.enumerate_processes()


def resolve_one(spec: str) -> list[TargetProcess]:
    spec = spec.strip()
    if not spec:
        raise TargetNotFoundError("empty target spec")

    if spec.isdigit():
        pid = int(spec)
        for proc in _iter_processes():
            if proc.pid == pid:
                return [proc]
        raise TargetNotFoundError(f"no process with pid {pid}")

    name = spec if spec.lower().endswith(".exe") else f"{spec}.exe"
    matches = [p for p in _iter_processes() if fnmatch.fnmatch(p.name.lower(), name.lower())]
    if not matches and "*" not in spec:
        # Retry as a raw glob so "*chrome*" style specs work.
        matches = [p for p in _iter_processes() if fnmatch.fnmatch(p.name.lower(), spec.lower())]
    if not matches:
        raise TargetNotFoundError(f"no process matching {spec!r}")
    return matches


def resolve_all(specs: tuple[str, ...]) -> tuple[TargetProcess, ...]:
    resolved: list[TargetProcess] = []
    seen: set[int] = set()
    for spec in specs:
        try:
            for proc in resolve_one(spec):
                if proc.pid in seen:
                    continue
                seen.add(proc.pid)
                resolved.append(proc)
        except TargetNotFoundError as exc:
            log.warning("unresolved target %r: %s", spec, exc)
    return tuple(resolved)