"""Command-line entry point for dll-injector-toolkit.

Parses a job spec, hands it to the pipeline service, prints a summary.
Exit codes:
    0  all targets injected successfully
    2  bad arguments / unreadable job spec
    3  one or more targets failed (partial success)
    4  elevation required but not present
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dll_injector.models.job import InjectionJob, JobResult
from dll_injector.services.pipeline import PipelineRunner
from dll_injector.utils.logging_setup import configure_logging


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dll-injector",
        description="Pipeline-style Windows DLL injector toolkit.",
    )
    p.add_argument("dll", type=Path, help="Path to the DLL to inject.")
    p.add_argument(
        "--target",
        "-t",
        action="append",
        required=True,
        help="Target process name or PID. Repeatable.",
    )
    p.add_argument("--method", "-m", default="auto", help="Injection method (default: auto).")
    p.add_argument("--timeout-ms", type=int, default=8000, help="Per-target timeout.")
    p.add_argument("--report", type=Path, default=None, help="Write JSON report here.")
    p.add_argument("--strict", action="store_true", help="Fail on first target error.")
    p.add_argument("--verbose", "-v", action="count", default=0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)

    if not args.dll.is_file():
        print(f"error: dll not found: {args.dll}", file=sys.stderr)
        return 2

    job = InjectionJob(
        dll_path=args.dll.resolve(),
        targets=tuple(args.target),
        method=args.method,
        timeout_ms=args.timeout_ms,
        strict=args.strict,
        report_path=args.report,
    )

    result: JobResult = PipelineRunner.from_config().run(job)
    print(result.summary())
    if result.all_ok:
        return 0
    if result.errors and not result.successes:
        return 3
    return 3


if __name__ == "__main__":
    raise SystemExit(main())