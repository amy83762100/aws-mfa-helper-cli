"""Region resolution that degrades gracefully instead of failing."""

from __future__ import annotations

import os
from collections.abc import Callable

from aws_mfa.config.models import ProfileConfig
from aws_mfa.core import credentials

# STS is reachable from any region; this is only the last-resort fallback.
FALLBACK_REGION = "us-east-1"

# Used only if botocore's bundled endpoint data is unavailable for some reason.
_FALLBACK_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "ca-central-1", "ca-west-1", "sa-east-1",
    "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1", "eu-north-1",
    "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2",
    "ap-south-1",
]


def all_regions() -> list[str]:
    """Every region in the standard AWS partition, from botocore's local data.

    No network call — botocore ships the endpoint list. Falls back to a static
    list if that lookup ever fails.
    """
    try:
        import boto3

        regions = boto3.Session().get_available_regions("ec2")
        return sorted(regions) if regions else _FALLBACK_REGIONS
    except Exception:  # pragma: no cover - defensive
        return _FALLBACK_REGIONS


def resolve_region(
    profile: ProfileConfig,
    *,
    explicit: str | None = None,
    interactive_chooser: Callable[[], str | None] | None = None,
) -> str:
    """Resolve a region without ever hard-failing.

    Order: explicit flag -> saved profile config -> source profile's region in
    ~/.aws/config -> AWS_REGION / AWS_DEFAULT_REGION env -> interactive chooser
    (if provided) -> FALLBACK_REGION.
    """
    if explicit:
        return explicit
    if profile.region:
        return profile.region
    from_aws = credentials.region_for_profile(profile.resolved_source_profile)
    if from_aws:
        return from_aws
    env = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if env:
        return env
    if interactive_chooser is not None:
        chosen = interactive_chooser()
        if chosen:
            return chosen
    return FALLBACK_REGION
