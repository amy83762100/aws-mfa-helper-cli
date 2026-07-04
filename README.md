# AWS MFA Helper CLI

A command-line tool for AWS accounts that require MFA. It exchanges your
6-digit authenticator code for temporary session credentials and writes them
to your AWS profile, in one interactive step.

[![CI](https://github.com/amy83762100/aws-mfa-helper-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/amy83762100/aws-mfa-helper-cli/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/aws-mfa-helper-cli.svg)](https://pypi.org/project/aws-mfa-helper-cli/)
[![Python](https://img.shields.io/pypi/pyversions/aws-mfa-helper-cli.svg)](https://pypi.org/project/aws-mfa-helper-cli/)

> This tool is for IAM users with virtual MFA devices. If your organization
> uses AWS SSO / IAM Identity Center, use `aws sso login` instead.

## The problem

When an AWS account enforces MFA, long-lived access keys alone are not enough
to call most APIs. You need to request temporary credentials:

```bash
aws sts get-session-token \
  --serial-number arn:aws:iam::123456789012:mfa/my-phone \
  --token-code 123456 --profile dev
```

Then copy the three values from the JSON response into `~/.aws/credentials`,
and repeat when the session expires. This tool automates the whole exchange:

```text
$ aws-mfa-helper-cli
? Select a profile
❯ dev
  staging
  + Create a new profile
? Where should the session credentials go?
❯ dev-session
  default
  Type a custom name...
? Enter MFA code  ******
✓ Session valid until 21:14 (11h 58m left).
  Use it with: --profile dev-session
```

```bash
aws s3 ls --profile dev-session
```

## Features

- Interactive prompts for profile, destination, and region. No ARNs or
  account IDs to remember: the MFA device is discovered through
  `iam:ListMFADevices`.
- Write credentials to a separate `<profile>-session` profile, to `default`,
  or to any profile you name. Overwriting a profile that holds permanent keys
  requires confirmation, and the keys are backed up to `<profile>-long-term`
  first.
- No AWS CLI dependency. All API calls go through boto3.
- MFA codes are read from a hidden prompt or stdin, never from a command-line
  argument, so they cannot end up in shell history.
- Credential files are written with `0600` permissions.
- Non-interactive mode for scripts and CI.
- Supports `sts:AssumeRole` with MFA for role-based setups.

## Installation

```bash
pip install aws-mfa-helper-cli    # or: pipx install aws-mfa-helper-cli
```

Requires Python 3.9 or newer. The AWS CLI is not required.

The command name is long on purpose (the short name is taken on PyPI by a
different project). A shell alias helps:

```bash
alias awsmfa="aws-mfa-helper-cli"   # add to ~/.zshrc or ~/.bashrc
```

## Getting started

The tool reads the same credentials file as the AWS CLI and boto3
(`~/.aws/credentials`). Installing it does not grant it any access on its own.

- If you have run `aws configure` before, no setup is needed. Run
  `aws-mfa-helper-cli` and pick your profile.
- If this machine has no AWS credentials yet, the tool detects that and offers
  a guided setup. You can also start it directly:

```bash
aws-mfa-helper-cli setup    # prompts for access key, secret, and region
```

For a short built-in guide:

```bash
aws-mfa-helper-cli help
```

## Commands

| Command | Description |
|---------|-------------|
| `aws-mfa-helper-cli` | Interactive flow: pick profile, destination, enter code |
| `aws-mfa-helper-cli mfa` | Same flow with flags for scripting (see below) |
| `aws-mfa-helper-cli setup` | Save AWS access keys without the AWS CLI |
| `aws-mfa-helper-cli whoami` | Show account, ARN, and user id for a profile |
| `aws-mfa-helper-cli config` | List, add, edit, delete, import, export saved profiles |
| `aws-mfa-helper-cli reset` | Remove one saved profile, or all tool settings |
| `aws-mfa-helper-cli help` | Built-in getting-started guide |

## Usage

### Scripting and CI

Every interactive question has a flag equivalent. In `--no-input` mode the MFA
code is read from stdin:

```bash
aws-mfa-helper-cli mfa --profile dev                  # prompts only for the code
aws-mfa-helper-cli mfa --profile dev --region eu-west-1
aws-mfa-helper-cli mfa --profile dev -o default       # write to [default]
aws-mfa-helper-cli mfa --profile dev --in-place       # write into [dev] itself
echo "$MFA_CODE" | aws-mfa-helper-cli mfa --profile dev --no-input
```

### Overwriting a profile

Some people prefer refreshing one profile in place over switching between
`dev` and `dev-session`. Choose `default`, a custom name, or `--in-place` for
that. Two safeguards apply:

- If the target currently holds permanent access keys, the tool asks before
  overwriting and copies the keys to `<profile>-long-term`. Later runs read
  the keys from the backup automatically.
- Refreshing a profile that already holds session credentials does not ask
  again.

To keep your choice, save it per profile with `config edit`; the menu will
preselect it on the next run.

### Assuming a role

Set `role_arn` on a profile (`aws-mfa-helper-cli config edit dev`). The tool
then calls `sts:AssumeRole` with your MFA code instead of
`sts:GetSessionToken`.

### Managing saved profiles

```bash
aws-mfa-helper-cli config list
aws-mfa-helper-cli config add
aws-mfa-helper-cli config edit dev
aws-mfa-helper-cli config delete dev
aws-mfa-helper-cli config export -o backup.toml
aws-mfa-helper-cli config import backup.toml
```

### Resetting

```bash
aws-mfa-helper-cli reset          # menu: pick a profile, or everything
aws-mfa-helper-cli reset dev      # remove one saved profile
aws-mfa-helper-cli reset --yes    # remove all tool settings, no prompt
```

Reset only removes this tool's own settings. It never modifies the AWS
credentials file: not your keys, and not the `*-session` profiles.

## Configuration

Settings live in `~/.config/aws-mfa/config.toml` (`$XDG_CONFIG_HOME` is
honored). The file contains no secrets, only per-profile preferences:

```toml
[profiles.dev]
mfa_serial = "arn:aws:iam::123456789012:mfa/my-phone"  # omit to auto-discover
region     = "us-east-1"                               # omit to resolve automatically
duration   = 43200                                     # session length in seconds
role_arn   = "arn:aws:iam::123456789012:role/Admin"    # optional
output_profile = "default"                             # optional destination
```

Session credentials are written to `~/.aws/credentials`. Configs from version
0.1 are migrated automatically on first run.

Region is resolved in this order: `--region` flag, saved profile setting, the
source profile's region in `~/.aws/config`, `AWS_REGION` /
`AWS_DEFAULT_REGION`, an interactive prompt, and finally `us-east-1`.

## Security

- MFA codes are never accepted as command-line arguments.
- Credential and config files are written with `0600` permissions; `~/.aws`
  is created with `0700`.
- The only network traffic is to AWS STS and IAM, over TLS, through boto3.
- Session credentials are still stored on disk in plaintext, like the AWS CLI
  stores them. If your threat model requires keychain-backed storage, consider
  [aws-vault](https://github.com/99designs/aws-vault).

## Alternatives

| Tool | Approach |
|------|----------|
| [aws-vault](https://github.com/99designs/aws-vault) | Stores keys in the OS keychain, injects credentials into a subshell |
| [granted](https://github.com/common-fate/granted) | Role and SSO assumption, browser profile integration |
| [awsume](https://github.com/trek10inc/awsume) | Exports credentials into the current shell session |

Those tools cover more scenarios (SSO, keychain storage, multi-account role
switching). This one focuses on the plain IAM-user-with-MFA case with a small
install and an interactive flow.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `AWS denied the request` | The base profile's keys are wrong or expired. Check `~/.aws/credentials`. |
| `The MFA code was not accepted` | Codes rotate every 30 seconds. Enter the next one. |
| `Multiple MFA devices found` | Pick one in the prompt, or pin it with `config edit`. |
| `No MFA device found` | Register a virtual MFA device in the IAM console, or set the serial with `config edit`. |
| Asked for a region every run | Save one with `config edit <profile>`. |
| Need the full traceback | Re-run with `--debug`. |

## Contributing

```bash
git clone https://github.com/amy83762100/aws-mfa-helper-cli
cd aws-mfa-helper-cli
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
pytest
```

Bug reports and pull requests are welcome. Please include a test with
behavior changes. See [CONTRIBUTING.md](CONTRIBUTING.md) for the project
layout and release process.

## License

MIT. See [LICENSE](LICENSE).
