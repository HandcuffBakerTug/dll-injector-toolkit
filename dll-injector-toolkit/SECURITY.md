# Security Policy

## Scope

`dll-injector-toolkit` is a hobbyist / educational Windows DLL injector.
It runs with the privileges of the caller — typically elevated — and it
loads arbitrary DLLs into arbitrary processes. That is the whole point of
the tool. Treat every run as a privileged operation.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.6.x   | yes       |
| 0.5.x   | security fixes only |
| < 0.5   | no        |

## What we consider a vulnerability

- A path where a non-elevated process can make the tool load an attacker
  DLL into a SYSTEM process.
- A parsing bug in `utils/pe_parser.py` that lets a malformed PE crash the
  injector with memory corruption.
- A TOCTOU in `handlers/dll_validation.py` where a validated DLL is swapped
  before `LoadLibrary`.
- Log files or reports that leak target memory contents unintentionally.

## What we do NOT consider a vulnerability

- The tool being used to inject into a process. That is the feature.
- Anti-cheat or EDR flagging the tool. Expected.
- Any "this could be used maliciously" report. Close it yourself.

## Reporting

Email `security@dll-injector-toolkit.dev` with steps, Windows build, and a
minimal repro. Do not open a public issue for anything on the list above.
We aim to acknowledge within 72 hours.

## Hardening notes for users

- Run from a directory you control. Never from `C:\Users\Public`.
- Keep `config/methods.toml` read-only after you settle on a method set.
- Don't ship the elevated launcher to end users without code signing.