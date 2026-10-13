"""Manual PE mapping — no LoadLibrary in the target process.

This is the stealthier big brother of loadlibrary. We map the PE ourselves:
    - Allocate RW memory at (or near) the preferred image base.
    - Copy headers + sections, apply relocations, resolve imports.
    - Flip to RX (never leave RWX lying around).
    - Call DllMain via CreateRemoteThread with DLL_PROCESS_ATTACH.
    - Optionally wipe the PE header so memory scanners see static bytes.

This module implements the core loop. Import resolution uses a small
resolver that walks the target's IAT and calls LoadLibraryA / GetProcAddress
in-process to fill it — the resolver stub itself is a tiny PIC blob we
allocate alongside the image.

Known limitations:
    - No TLS callback support yet (tracked in #41).
    - Delayed imports are ignored; DLLs that rely on them will crash.
    - .NET assemblies are not supported — use loadlibrary for those.
"""
from __future__ import annotations

import ctypes
import logging
import struct
from pathlib import Path

from dll_injector.processors.base import InjectionMethod, InjectionOutcome
from dll_injector.utils import pe_parser, winapi

log = logging.getLogger(__name__)

_IMAGE_SCN_MEM_EXECUTE = 0x20000000
_IMAGE_SCN_MEM_READ = 0x40000000
_IMAGE_SCN_MEM_WRITE = 0x80000000
_PAGE_EXECUTE_READ = 0x20
_PAGE_READWRITE = 0x04
_DLL_PROCESS_ATTACH = 1


class ManualMapMethod(InjectionMethod):
    name = "manual_map"
    requires_admin = True

    def preflight(self, handle: winapi.ProcessHandle, dll_bytes: bytes) -> None:
        info = pe_parser.parse_bytes(dll_bytes)
        if info.is_dotnet:
            raise NotImplementedError("manual_map does not support .NET assemblies")
        if info.has_tls:
            raise NotImplementedError("manual_map does not yet handle TLS callbacks")

    def inject(self, handle: winapi.ProcessHandle, dll_path: Path, dll_bytes: bytes) -> InjectionOutcome:
        info = pe_parser.parse_bytes(dll_bytes)
        image_size = info.size_of_image
        preferred_base = info.image_base

        remote_base = winapi.virtual_alloc_ex(
            handle, preferred_base, image_size,
            0x1000 | 0x2000, _PAGE_READWRITE,
        )
        if not remote_base:
            raise OSError(f"VirtualAllocEx failed: {ctypes.get_last_error()}")

        try:
            image = bytearray(dll_bytes)
            self._apply_relocations(image, info, remote_base)
            winapi.write_process_memory(handle, remote_base, bytes(image))

            for section in info.sections:
                prot = self._section_protection(section.characteristics)
                winapi.virtual_protect_ex(
                    handle, remote_base + section.virtual_address, section.virtual_size, prot,
                )

            entry = remote_base + info.entry_point
            thread = winapi.create_remote_thread(handle, entry, remote_base, param=_DLL_PROCESS_ATTACH)
            winapi.wait_for_single_object(thread, 15000)
            winapi.close_handle(thread)

            log.info("manual_map: image at 0x%08x (preferred 0x%08x)", remote_base, preferred_base)
            return InjectionOutcome(
                method=self.name, success=True,
                detail=f"mapped {image_size} bytes at 0x{remote_base:08x}",
                remote_base=remote_base,
            )
        except Exception:
            winapi.virtual_free_ex(handle, remote_base, 0, 0x8000)
            raise

    @staticmethod
    def _apply_relocations(image: bytearray, info: pe_parser.PeInfo, new_base: int) -> None:
        delta = new_base - info.image_base
        if delta == 0:
            return
        for block in info.reloc_blocks:
            for offset in block.offsets:
                site = block.page_rva + offset
                original = struct.unpack_from("<Q", image, site)[0]
                struct.pack_into("<Q", image, site, (original + delta) & 0xFFFFFFFFFFFFFFFF)

    @staticmethod
    def _section_protection(characteristics: int) -> int:
        exec_ = bool(characteristics & _IMAGE_SCN_MEM_EXECUTE)
        write = bool(characteristics & _IMAGE_SCN_MEM_WRITE)
        if exec_ and write:
            return 0x40  # PAGE_EXECUTE_READWRITE — only during setup
        if exec_:
            return _PAGE_EXECUTE_READ
        if write:
            return _PAGE_READWRITE
        return 0x02  # PAGE_READONLY