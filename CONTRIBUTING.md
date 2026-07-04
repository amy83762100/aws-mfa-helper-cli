# Contributing to aws-mfa-helper-cli

Bug reports and pull requests are welcome. In this project, clear error
messages and a smooth prompt flow matter as much as correctness.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Before you push

The CI runs these on Python 3.9–3.12; run them locally first:

```bash
ruff check .        # lint + import sort
ruff format .       # (optional) autoformat
mypy                # strict type checking
pytest              # unit tests
```

`pre-commit install` wires ruff + mypy to run on every commit.

## Project layout

```
src/aws_mfa/
  cli.py          Typer wiring only — keep it thin
  commands/       Orchestration (testable, no prompting logic)
  core/           AWS + filesystem (boto3, ~/.aws I/O) — no UI imports
  config/         TOML store + dataclasses
  ui/             questionary prompts + Rich rendering (the only place that
                  prints or prompts)
tests/            pytest + botocore Stubber (no live AWS calls)
```

Rules of thumb:

- **`core/` and `commands/` must not import `ui/`.** Keep logic testable without
  a terminal. Pass choosers in as callables (see `commands/mfa.execute`).
- **Never accept the MFA code as a CLI option.** Hidden prompt or stdin only.
- **Always write credential files with `0600`.** Use the helpers in
  `core/credentials.py`.
- Add a unit test for any behavior change. AWS calls are tested with
  `botocore.stub.Stubber` or `moto`, never against a real account.

## Releasing

1. Bump `__version__` in `src/aws_mfa/__init__.py`.
2. Update `CHANGELOG.md`.
3. Tag: `git tag v0.x.y && git push --tags`.
   - `vX.Y.Z` → publishes to PyPI.
   - `vX.Y.Z-test` → publishes to Test PyPI.

Publishing uses PyPI Trusted Publishing (OIDC) — no API tokens stored.
