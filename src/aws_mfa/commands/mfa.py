"""Core MFA orchestration, independent of the CLI/prompt layer for testability."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aws_mfa.config.models import ProfileConfig, SessionCredentials
from aws_mfa.core import identity, region, sts
from aws_mfa.core.credentials import profile_exists, write_session_credentials
from aws_mfa.errors import MfaDeviceError


@dataclass
class MfaResult:
    output_profile: str
    credentials: SessionCredentials
    # Set when overwrite-in-place moved the user's long-lived keys aside.
    long_term_backup: str | None = None


def resolve_source_profile(profile: ProfileConfig) -> str:
    """The profile whose long-lived keys should call STS.

    If a ``<source>-long-term`` backup exists (created by overwrite-in-place),
    it holds the real keys — the original section now contains session
    credentials, which STS would reject.
    """
    source = profile.resolved_source_profile
    long_term = f"{source}-long-term"
    if profile_exists(long_term):
        return long_term
    return source


def resolve_mfa_serial(
    profile: ProfileConfig,
    *,
    source_profile: str | None = None,
    region_name: str | None = None,
    chooser: Callable[[list[str]], str] | None = None,
) -> str:
    """Return the MFA serial: saved value, else auto-discovered from IAM.

    If several devices exist, ``chooser`` is asked to pick one (interactive
    mode). Without a chooser, a single device is used automatically and
    multiple/none raises so non-interactive callers fail loudly.
    """
    if profile.mfa_serial:
        return profile.mfa_serial
    source = source_profile or profile.resolved_source_profile
    serials = identity.discover_mfa_serials(source, region_name)
    if len(serials) == 1:
        return serials[0]
    if not serials:
        raise MfaDeviceError(
            f"No MFA device found for profile '{profile.name}'.",
            hint="Register a virtual MFA device in IAM, or set one with "
            "`aws-mfa-helper-cli config edit`.",
        )
    if chooser is None:
        raise MfaDeviceError(
            f"Multiple MFA devices found for '{profile.name}'; cannot pick one "
            "non-interactively.",
            hint="Pin one with `aws-mfa-helper-cli config edit` or run interactively.",
        )
    return chooser(serials)


def execute(
    profile: ProfileConfig,
    token_code: str,
    *,
    region_override: str | None = None,
    output_override: str | None = None,
    region_chooser: Callable[[], str | None] | None = None,
    mfa_chooser: Callable[[list[str]], str] | None = None,
) -> MfaResult:
    """Resolve region + MFA serial, call STS, and persist the credentials.

    ``output_override`` writes the session credentials to that profile instead
    of the default ``<name>-session`` — including in place over the source
    profile itself, in which case the long-lived keys are backed up first.
    """
    output_profile = output_override or profile.resolved_output_profile
    source_profile = resolve_source_profile(profile)

    resolved_region = region.resolve_region(
        profile, explicit=region_override, interactive_chooser=region_chooser
    )
    serial = resolve_mfa_serial(
        profile,
        source_profile=source_profile,
        region_name=resolved_region,
        chooser=mfa_chooser,
    )

    if profile.role_arn:
        creds = sts.assume_role(
            source_profile=source_profile,
            role_arn=profile.role_arn,
            mfa_serial=serial,
            token_code=token_code,
            duration=min(profile.duration, 43200),  # assume-role caps at 12h
            region=resolved_region,
        )
    else:
        creds = sts.get_session_token(
            source_profile=source_profile,
            mfa_serial=serial,
            token_code=token_code,
            duration=profile.duration,
            region=resolved_region,
        )

    backup = write_session_credentials(output_profile, creds, region=resolved_region)
    return MfaResult(output_profile=output_profile, credentials=creds, long_term_backup=backup)
