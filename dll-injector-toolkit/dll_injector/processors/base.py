"""InjectionMethod — abstract base for every injection strategy.

Each concrete method implements `inject(handle, dll_path, dll_bytes)` and
returns an InjectionOutcome describing what happened. Methods must be
side-effect-free on failure — if a method raises, the pipeline treats the
target as failed and moves on to the next method in the fallback chain.

Concurrency: methods are called from a single worker thread per target.
They may spawn their own threads internally (e.g. thread_hijack) but must
join them before returning.
"""
from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from pathlib import Path

from dll_injector.utils import winapi

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InjectionOutcome:
    method: str
    success: bool
    detail: str
    remote_base: int | None = None  # base address of mapped image, if known


class InjectionMethod(abc.ABC):
    """Base class for every injection strategy."""

    name: str = "unnamed"
    requires_admin: bool = False

    @abc.abstractmethod
    def inject(self, handle: winapi.ProcessHandle, dll_path: Path, dll_bytes: bytes) -> InjectionOutcome:
        """Perform the injection. Raise on hard failure, return outcome on soft."""

    def preflight(self, handle: winapi.ProcessHandle, dll_bytes: bytes) -> None:
        """Optional hook. Raise to signal the method cannot run on this target."""
        return None

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<{type(self).__name__} name={self.name} admin={self.requires_admin}>"