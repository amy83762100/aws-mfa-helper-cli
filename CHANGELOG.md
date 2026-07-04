# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-07-03

Full rewrite around boto3 with a modern, interactive UX.

### Added
- Interactive default flow (`aws-mfa-helper-cli`) with profile picker and hidden MFA prompt
  (questionary + Rich).
- `aws-mfa-helper-cli help`: a plain-English getting-started guide (what the tool does,
  three steps, where secrets live).
- `aws-mfa-helper-cli setup`: guided wizard to save AWS access keys — works without the
  AWS CLI installed. Runs automatically on first use if no credentials exist.
- Friendly preflight checks: missing `~/.aws/credentials` or a profile without
  keys now offers setup on the spot instead of a botocore traceback.
- `aws-mfa-helper-cli reset`: interactive menu to remove one saved profile or
  everything (`reset <name>` / `reset --yes` for scripts). Deliberately
  scoped: the AWS credentials file is never touched — not access keys, not
  even the `*-session` profiles.
- Region prompts now offer the **full AWS region list** (from botocore's local
  data — includes `ca-central-1` etc.) with type-ahead search, and accept any
  manually typed region.
- **Choose where credentials go**: after picking a profile, an interactive
  menu asks whether to write to `<name>-session`, overwrite `default`, or a
  custom profile. Overwriting a profile that holds permanent keys requires
  explicit confirmation, and those keys are automatically backed up to
  `<name>-long-term` first (used as the STS source from then on) — permanent
  keys can never be destroyed. Flags for scripts: `--output-profile/-o`,
  `--in-place`; the answer can be persisted via `config edit`.
- Automatic MFA device discovery via `iam:ListMFADevices` — no more typing
  account IDs or device names.
- Automatic account-ID derivation via `sts:GetCallerIdentity` (`aws-mfa-helper-cli whoami`).
- Full config CRUD: `config list/add/edit/delete/clear/export/import`.
- TOML config at `~/.config/aws-mfa/config.toml` (XDG-compliant).
- Assume-role-with-MFA support (`role_arn` per profile).
- CI mode (`--no-input`) that reads the MFA code from stdin.
- Graceful region resolution chain (flag → config → ~/.aws/config → env →
  prompt → fallback) that never hard-fails.
- Session expiry is shown after each run.
- Shell completion (via Typer).

### Changed
- The console command is now `aws-mfa-helper-cli` only. The short `aws-mfa`
  command was dropped because another PyPI package (broamski/aws-mfa) installs
  a command with that exact name — add `alias awsmfa="aws-mfa-helper-cli"` to
  your shell if you want it short.
- Switched from shelling out to the `aws` CLI to using **boto3 directly** — the
  AWS CLI binary is no longer required.
- The v0.1 legacy config is migrated once and the old file is renamed to
  `.bak`, so cleared profiles no longer resurrect themselves.
- Config moved from `~/.aws_mfa_helper_cli_config` (JSON) to TOML; old config is
  migrated automatically on first run.
- Packaging moved from `setup.py` to `pyproject.toml` (hatchling).
- Minimum Python is now 3.9 (was 3.6).

### Fixed
- **Region copying never worked**: the config path was `~./.aws/config`, a
  literal relative path that never expanded. Now correctly reads/writes
  `~/.aws/config`.
- **Credential files are now written with `0600`** and `~/.aws` is created
  `0700` (previously permissions were left untouched).
- The MFA code can no longer be passed as a command-line flag (it used to leak
  into shell history).
- MFA token validation now strips whitespace and re-prompts instead of dead-ending.

### Security
- See README "Security notes". Highlights: no MFA codes on the command line,
  `0600` credential/config files, no AWS CLI subprocess / PATH trust.
