"""TOML-backed, XDG-compliant configuration storage with legacy import."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import tomli_w
from platformdirs import user_config_dir

from aws_mfa.config.models import ProfileConfig
from aws_mfa.errors import ConfigError, ProfileNotFoundError

if sys.version_info >= (3, 11):  # pragma: no cover
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

APP_NAME = "aws-mfa"
LEGACY_CONFIG = Path("~/.aws_mfa_helper_cli_config").expanduser()


def config_path() -> Path:
    """Location of the TOML config, honoring ``$AWS_MFA_CONFIG`` for tests."""
    override = os.environ.get("AWS_MFA_CONFIG")
    if override:
        return Path(override)
    return Path(user_config_dir(APP_NAME)) / "config.toml"


class ConfigStore:
    """Reads and writes the aws-mfa profile configuration."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_path()

    # -- reading --------------------------------------------------------
    def _raw(self) -> dict[str, dict[str, object]]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("rb") as fh:
                data = tomllib.load(fh)
        except (OSError, ValueError) as exc:
            raise ConfigError(f"Could not read config at {self.path}: {exc}") from exc
        profiles = data.get("profiles", {})
        if not isinstance(profiles, dict):
            raise ConfigError(f"Malformed config: 'profiles' must be a table in {self.path}")
        return profiles

    def all_profiles(self) -> list[ProfileConfig]:
        return [ProfileConfig.from_toml_dict(name, d) for name, d in sorted(self._raw().items())]

    def get(self, name: str) -> ProfileConfig:
        raw = self._raw()
        if name not in raw:
            raise ProfileNotFoundError(
                f"No saved profile named '{name}'.",
                hint="Run `aws-mfa-helper-cli config list` to see configured profiles.",
            )
        return ProfileConfig.from_toml_dict(name, raw[name])

    def get_or_none(self, name: str) -> ProfileConfig | None:
        raw = self._raw()
        return ProfileConfig.from_toml_dict(name, raw[name]) if name in raw else None

    def names(self) -> list[str]:
        return sorted(self._raw().keys())

    # -- writing --------------------------------------------------------
    def save(self, profile: ProfileConfig) -> None:
        raw = self._raw()
        raw[profile.name] = profile.to_toml_dict()
        self._write(raw)

    def delete(self, name: str) -> None:
        raw = self._raw()
        if name not in raw:
            raise ProfileNotFoundError(f"No saved profile named '{name}'.")
        del raw[name]
        self._write(raw)

    def clear(self) -> None:
        self._write({})

    def _write(self, profiles: dict[str, dict[str, object]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"profiles": profiles}
        try:
            with self.path.open("wb") as fh:
                tomli_w.dump(payload, fh)
        except OSError as exc:
            raise ConfigError(f"Could not write config at {self.path}: {exc}") from exc
        # Config holds no secrets, but keep it private anyway.
        os.chmod(self.path, 0o600)

    # -- import / export ------------------------------------------------
    def export_toml(self) -> str:
        return tomli_w.dumps({"profiles": self._raw()})

    def import_toml(self, text: str, *, overwrite: bool = False) -> list[str]:
        try:
            incoming = tomllib.loads(text).get("profiles", {})
        except ValueError as exc:
            raise ConfigError(f"Invalid TOML: {exc}") from exc
        if not isinstance(incoming, dict):
            raise ConfigError("Import payload has no [profiles] table.")
        raw = self._raw()
        added: list[str] = []
        for name, data in incoming.items():
            if name in raw and not overwrite:
                continue
            raw[name] = data
            added.append(name)
        self._write(raw)
        return added

    def import_legacy(self) -> list[str]:
        """Migrate the old ~/.aws_mfa_helper_cli_config JSON, if present.

        The legacy format stored ``iam_account_id`` and ``device`` per profile;
        we synthesize the full MFA serial ARN from those. The legacy file is
        renamed to ``.bak`` afterwards so migration runs exactly once —
        otherwise clearing the config would keep resurrecting old profiles.
        """
        if not LEGACY_CONFIG.exists():
            return []
        try:
            legacy = json.loads(LEGACY_CONFIG.read_text())
        except (OSError, ValueError) as exc:
            raise ConfigError(f"Could not read legacy config: {exc}") from exc
        raw = self._raw()
        migrated: list[str] = []
        for name, data in legacy.items():
            if name in raw:
                continue
            account = data.get("iam_account_id")
            device = data.get("device")
            serial = (
                f"arn:aws:iam::{account}:mfa/{device}" if account and device else None
            )
            profile = ProfileConfig(name=name, mfa_serial=serial)
            raw[name] = profile.to_toml_dict()
            migrated.append(name)
        if migrated:
            self._write(raw)
        # One-shot: keep the old file as a backup, never re-import.
        LEGACY_CONFIG.replace(LEGACY_CONFIG.with_name(LEGACY_CONFIG.name + ".bak"))
        return migrated
