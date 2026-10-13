# Contributing to dll-injector-toolkit

Thanks for wanting to push code into this repo. We ship a Windows desktop
DLL injector pipeline — handlers in, processors chewing, drivers out. Keep
PRs focused, keep them boring, keep them tested.

## Ground rules

- One concern per PR. A new injection method is a new method module, not a
  patch smeared across three handlers.
- Every new method ships with a test under `tests/` and a wiring entry in
  `config/methods.toml`.
- No `print()` debugging left in. Use `utils/logging_setup.py`.
- Type hints on every public function. `mypy --strict` runs in CI.
- Ruff is the linter. `ruff check .` must be clean before review.

## Repo layout (quick map)

```
dll_injector/
  bootstrap/      # entry points, CLI, elevated launcher
  handlers/       # ingest: target discovery, dll validation
  processors/     # core: the actual injection strategies
  drivers/        # output: report writers, telemetry sinks
  services/       # orchestration: pipeline runner, scheduler
  models/         # dataclasses, enums, typed payloads
  utils/          # winapi wrappers, pe parsing, logging
config/           # runtime configuration
tests/            # pytest suites
```

## Adding a new injection method

1. Drop a module in `processors/methods/`.
2. Subclass `InjectionMethod` from `models/injection.py`.
3. Register it in `config/methods.toml` under `[methods.<name>]`.
4. Add a fixture DLL to `tests/fixtures/` and a test in
   `tests/test_processors.py`.

## Commit style

`<area>: <imperative summary>` — e.g. `processors: add manual map fallback`,
`handlers: harden pe-arch validation`.

## Reporting bugs

Open an issue with: Windows build (10/11, build number), target process
arch, the method used, and the log tail from `logs/injector.log`. Attach
`reports/last_run.json` if you have it.