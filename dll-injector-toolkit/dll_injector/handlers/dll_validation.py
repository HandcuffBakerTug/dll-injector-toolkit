"""Validate a candidate DLL before it enters the injection pipeline.

Checks performed:
    1. File exists, is a regular file, readable.
    2. PE magic present (MZ / PE\\0\\0).
    3. Machine type matches the target process arch.
    4. Optional: SHA-256 recorded for the report.

We deliberately do NOT verify signatures — the whole point of this toolkit
is to inject unsigned hobbyist DLLs. Signing is the caller's problem.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from dll_injector.models.target import Arch
from dll_injector.utils import pe_parser

log = logging.getLogger(__name__)


class DllValidationError(ValueError):
    """Raised when a DLL fails pre-flight validation."""


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(dll_path: Path, target_arch: Arch | None = None) -> pe_parser.PeInfo:
    """Validate a DLL for injection. Returns parsed PE info."""
    if not dll_path.is_file():
        raise DllValidationError(f"not a regular file: {dll_path}")

    try:
        info = pe_parser.parse(dll_path)
    except pe_parser.PeParseError as exc:
        raise DllValidationError(f"not a valid PE: {exc}") from exc

    if not info.is_dll:
        raise DllValidationError(f"{dll_path.name} is a PE but not a DLL")

    if target_arch is not None and info.arch is not target_arch:
        raise DllValidationError(
            f"arch mismatch: dll is {info.arch.name}, target is {target_arch.name}"
        )

    log.debug(
        "validated %s arch=%s entry=0x%08x exports=%d",
        dll_path.name, info.arch.name, info.entry_point, len(info.exports),
    )
    return info