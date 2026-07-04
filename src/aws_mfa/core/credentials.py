"""Read/write the AWS credentials/config files safely.

Paths honor the standard ``AWS_SHARED_CREDENTIALS_FILE`` / ``AWS_CONFIG_FILE``
environment variables (like boto3 does), falling back to ``~/.aws/...``.

Fixes two bugs from the original implementation:
  * the config path was ``~./.aws/config`` (a literal relative path that never
    expanded), so region copying silently never worked;
  * the credentials file was rewritten without restricting permissions.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from aws_mfa.config.models import SessionCredentials
from aws_mfa.errors import ConfigError


def credentials_file_path() -> Path:
    """Where boto3/AWS CLI read credentials from — env override or ~/.aws."""
    env = os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
    return Path(env).expanduser() if env else Path("~/.aws/credentials").expanduser()


def config_file_path() -> Path:
    env = os.environ.get("AWS_CONFIG_FILE")
    return Path(env).expanduser() if env else Path("~/.aws/config").expanduser()


def profile_exists(name: str, *, credentials_file: Path | None = None) -> bool:
    """True if the credentials file has a section for this profile."""
    parser = _read_ini(credentials_file or credentials_file_path())
    return parser.has_section(name)


def profile_has_long_lived_keys(name: str, *, credentials_file: Path | None = None) -> bool:
    """True if this profile holds permanent access keys (no session token).

    Used to decide when overwriting needs an explicit confirmation — refreshing
    a profile that already holds session credentials never asks.
    """
    parser = _read_ini(credentials_file or credentials_file_path())
    return (
        parser.has_section(name)
        and parser.has_option(name, "aws_access_key_id")
        and not parser.has_option(name, "aws_session_token")
    )


def _read_ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    if path.exists():
        parser.read(path)
    return parser


def _write_ini(parser: configparser.ConfigParser, path: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Create with 0600 from the start to avoid a race where the file is briefly
    # world-readable between creation and chmod.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as fh:
            parser.write(fh)
    except OSError as exc:
        raise ConfigError(f"Could not write {path}: {exc}") from exc
    os.chmod(path, 0o600)


def region_for_profile(profile: str, config_file: Path | None = None) -> str | None:
    """Look up a profile's region in the AWS config file.

    There the default profile is ``[default]`` and others are
    ``[profile <name>]``.
    """
    parser = _read_ini(config_file or config_file_path())
    section = "default" if profile == "default" else f"profile {profile}"
    if parser.has_section(section) and parser.has_option(section, "region"):
        return parser.get(section, "region")
    return None


def write_base_profile(
    profile: str,
    access_key_id: str,
    secret_access_key: str,
    *,
    region: str | None = None,
    credentials_file: Path | None = None,
    config_file: Path | None = None,
) -> None:
    """Write long-lived access keys for a profile (first-run setup wizard).

    Same guarantees as session writes: 0600 files, 0700 parent directory.
    """
    credentials_file = credentials_file or credentials_file_path()
    cred_ini = _read_ini(credentials_file)
    if not cred_ini.has_section(profile):
        cred_ini.add_section(profile)
    cred_ini[profile]["aws_access_key_id"] = access_key_id.strip()
    cred_ini[profile]["aws_secret_access_key"] = secret_access_key.strip()
    _write_ini(cred_ini, credentials_file)

    if region:
        config_file = config_file or config_file_path()
        config_ini = _read_ini(config_file)
        section = "default" if profile == "default" else f"profile {profile}"
        if not config_ini.has_section(section):
            config_ini.add_section(section)
        config_ini[section]["region"] = region
        _write_ini(config_ini, config_file)


def write_session_credentials(
    output_profile: str,
    creds: SessionCredentials,
    *,
    region: str | None = None,
    credentials_file: Path | None = None,
    config_file: Path | None = None,
) -> str | None:
    """Persist session credentials to the AWS credentials file (mode 0600).

    If ``region`` is given, also write it to the matching profile block in
    the AWS config file so the session profile is fully usable on its own.

    Safety: if the target section currently holds **long-lived** keys (no
    ``aws_session_token``), they are first copied to ``<name>-long-term`` so
    overwrite-in-place can never destroy a user's permanent credentials.
    Returns the backup profile name if one was created, else None.
    """
    credentials_file = credentials_file or credentials_file_path()
    cred_ini = _read_ini(credentials_file)
    backup_created: str | None = None
    if (
        cred_ini.has_section(output_profile)
        and cred_ini.has_option(output_profile, "aws_access_key_id")
        and not cred_ini.has_option(output_profile, "aws_session_token")
    ):
        backup = f"{output_profile}-long-term"
        if not cred_ini.has_section(backup):
            cred_ini.add_section(backup)
            for key, value in cred_ini.items(output_profile):
                cred_ini[backup][key] = value
            backup_created = backup
    if not cred_ini.has_section(output_profile):
        cred_ini.add_section(output_profile)
    cred_ini[output_profile]["aws_access_key_id"] = creds.access_key_id
    cred_ini[output_profile]["aws_secret_access_key"] = creds.secret_access_key
    cred_ini[output_profile]["aws_session_token"] = creds.session_token
    _write_ini(cred_ini, credentials_file)

    if region:
        config_file = config_file or config_file_path()
        config_ini = _read_ini(config_file)
        section = "default" if output_profile == "default" else f"profile {output_profile}"
        if not config_ini.has_section(section):
            config_ini.add_section(section)
        config_ini[section]["region"] = region
        _write_ini(config_ini, config_file)
    return backup_created
