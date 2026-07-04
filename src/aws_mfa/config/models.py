"""Typed data models for configuration and session credentials."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

# get-session-token allows 900s..129600s (36h); default 12h.
DEFAULT_DURATION = 43200
MIN_DURATION = 900
MAX_DURATION = 129600


@dataclass
class ProfileConfig:
    """Per-profile, non-secret configuration.

    ``name`` is the aws-mfa profile key. ``source_profile`` is the AWS profile
    whose long-lived keys are used to call STS (defaults to ``name``). The
    generated session credentials are written to ``output_profile`` (defaults
    to ``<name>-session``).
    """

    name: str
    mfa_serial: str | None = None
    region: str | None = None
    duration: int = DEFAULT_DURATION
    role_arn: str | None = None
    source_profile: str | None = None
    output_profile: str | None = None

    @property
    def resolved_source_profile(self) -> str:
        return self.source_profile or self.name

    @property
    def resolved_output_profile(self) -> str:
        return self.output_profile or f"{self.name}-session"

    def to_toml_dict(self) -> dict[str, object]:
        """Serialize, omitting keys that are None/default to keep TOML clean."""
        data = asdict(self)
        data.pop("name")
        out: dict[str, object] = {}
        for key, value in data.items():
            if value is None:
                continue
            if key == "duration" and value == DEFAULT_DURATION:
                continue
            out[key] = value
        return out

    @classmethod
    def from_toml_dict(cls, name: str, data: dict[str, object]) -> ProfileConfig:
        return cls(
            name=name,
            mfa_serial=_opt_str(data.get("mfa_serial")),
            region=_opt_str(data.get("region")),
            duration=_as_int(data.get("duration"), DEFAULT_DURATION),
            role_arn=_opt_str(data.get("role_arn")),
            source_profile=_opt_str(data.get("source_profile")),
            output_profile=_opt_str(data.get("output_profile")),
        )


@dataclass
class SessionCredentials:
    """Temporary STS credentials plus their expiry."""

    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: datetime

    @classmethod
    def from_sts_response(cls, creds: Mapping[str, object]) -> SessionCredentials:
        return cls(
            access_key_id=str(creds["AccessKeyId"]),
            secret_access_key=str(creds["SecretAccessKey"]),
            session_token=str(creds["SessionToken"]),
            expiration=_as_datetime(creds["Expiration"]),
        )

    @property
    def seconds_remaining(self) -> int:
        delta = self.expiration - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))


def _opt_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _as_int(value: object, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value))
