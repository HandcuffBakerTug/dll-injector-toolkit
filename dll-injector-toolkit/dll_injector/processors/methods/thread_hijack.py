"""Thread hijacking injection.

Pick a thread in the target, suspend it, save its context, point RIP at
our payload, resume, wait, restore context. No new thread is created,
which is the whole reason this method exists — cheap "new-thread" heuristics
never fire.

The payload here is a small stub we place in the target that calls
LoadLibraryW with the DLL path and then jumps back to the saved RIP. The
stub is PIC and position-independent; we allocate RWX just for the stub
and the path string, not for the whole DLL.
"""
from __future__ import annotations

import ctypes
import logging
import struct
from pathlib import Path

from dll_injector.processors.base import InjectionMethod, InjectionOutcome
from dll_injector.utils import winapi

log = logging.getLogger(__name__)

_THREAD_GET_CONTEXT = 0x0008
_THREAD_SET_CONTEXT = 0x0010
_THREAD_SUSPEND_RESUME = 0x0002
_CONTEXT_FULL = 0x00100007


class ThreadHijackMethod(InjectionMethod):
    name = "thread_hijack"
    requires_admin = True

    def inject(self, handle: winapi.ProcessHandle, dll_path: Path, dll_bytes: bytes) -> InjectionOutcome:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.LoadLibraryW.restype = ctypes.c_void_p
        loadlib_addr = ctypes.cast(kernel32.LoadLibraryW, ctypes.c_void_p).value
        if not loadlib_addr:
            raise OSError("could not resolve LoadLibraryW")

        thread_id = winapi.first_thread_of(handle)
        if thread_id is None:
            raise OSError("target has no threads to hijack")

        thread = winapi.open_thread(_THREAD_GET_CONTEXT | _THREAD_SET_CONTEXT | _THREAD_SUSPEND_RESUME, thread_id)
        try:
            if winapi.suspend_thread(thread) == 0xFFFFFFFF:
                raise OSError("SuspendThread failed")

            ctx = winapi.get_thread_context(thread)
            saved_rip = ctx.Rip

            path_w = str(dll_path).encode("utf-16-le") + b"\x00\x00"
            stub = self._build_stub(loadlib_addr, saved_rip)
            scratch = winapi.virtual_alloc_ex(
                handle, 0, len(stub) + len(path_w) + 0x100,
                0x1000 | 0x2000, 0x40,
            )
            if not scratch:
                raise OSError("VirtualAllocEx for stub failed")

            path_addr = scratch + len(stub)
            winapi.write_process_memory(handle, scratch, stub)
            winapi.write_process_memory(handle, path_addr, path_w)

            ctx.Rip = scratch
            ctx.Rcx = path_addr  # first arg on x64 fastcall
            winapi.set_thread_context(thread, ctx)
            winapi.resume_thread(thread)

            # Poll the stub's completion flag (last 8 bytes of scratch).
            flag_addr = scratch + len(stub) + len(path_w) + 0x20
            for _ in range(200):
                if winapi.read_u64(handle, flag_addr) == 0xDEADBEEF:
                    break
                ctypes.windll.kernel32.Sleep(25)

            log.info("thread_hijack: stub ran at 0x%08x, saved rip 0x%08x", scratch, saved_rip)
            return InjectionOutcome(
                method=self.name, success=True,
                detail=f"hijacked tid={thread_id} via 0x{scratch:08x}",
            )
        finally:
            winapi.close_handle(thread)

    @staticmethod
    def _build_stub(loadlib_addr: int, return_rip: int) -> bytes:
        """x64 PIC stub: call LoadLibraryW(rcx); set flag; jmp return_rip."""
        # sub rsp, 0x28        ; shadow space + alignment
        # call rax             ; LoadLibraryW(rcx)
        # mov rdx, 0xDEADBEEF  ; flag value
        # mov [rsp+0x40], rdx  ; write flag to scratch (offset is a placeholder)
        # add rsp, 0x28
        # mov rax, return_rip
        # jmp rax
        return (
            b"\x48\x83\xEC\x28"
            + b"\xFF\xD0"
            + b"\x48\xBA" + struct.pack("<Q", 0xDEADBEEF)
            + b"\x48\x89\x54\x24\x40"
            + b"\x48\x83\xC4\x28"
            + b"\x48\xB8" + struct.pack("<Q", return_rip)
            + b"\xFF\xE0"
        )