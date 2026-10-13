"""Elevation helper — re-launches the injector with a UAC prompt.

Used by the CLI when a chosen method declares `requires_admin = true` and
the current token is not elevated. We re-run the same argv under
ShellExecuteW "runas". The child process inherits our cwd and env.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


def is_elevated() -> bool:
    """Return True if the current process token is elevated."""
    try:
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        return bool(shell32.IsUserAnAdmin())
    except OSError:
        return False


def relaunch_elevated(argv: list[str]) -> int:
    """Re-launch argv under a UAC prompt. Returns the child's exit code."""
    if len(argv) < 1:
        raise ValueError("argv must contain at least the executable path")
    exe = sys.executable
    params = " ".join(f'"{a}"' for a in argv)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteW.restype = wintypes.HINSTANCE
    shell32.ShellExecuteW.argtypes = [
        wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int,
    ]
    rc = shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    # ShellExecuteW returns >32 on success, <=32 on failure.
    if rc <= 32:
        raise OSError(f"ShellExecuteW failed, code={rc}")
    return 0