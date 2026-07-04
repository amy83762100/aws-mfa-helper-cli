"""Caller identity and automatic MFA device discovery via boto3."""

from __future__ import annotations

from dataclasses import dataclass

import boto3
from botocore.exceptions import BotoCoreError, ClientError, ProfileNotFound

from aws_mfa.errors import AwsMfaError, MfaDeviceError


@dataclass
class CallerIdentity:
    account: str
    arn: str
    user_id: str


def _session(profile: str, region: str | None = None) -> boto3.Session:
    try:
        return boto3.Session(profile_name=profile, region_name=region)
    except ProfileNotFound as exc:
        raise AwsMfaError(
            f"AWS profile '{profile}' was not found.",
            hint="Run `aws configure --profile <name>` first.",
        ) from exc


def get_caller_identity(profile: str, region: str | None = None) -> CallerIdentity:
    client = _session(profile, region).client("sts")
    try:
        resp = client.get_caller_identity()
    except (ClientError, BotoCoreError) as exc:
        raise AwsMfaError(f"Could not determine identity for '{profile}': {exc}") from exc
    return CallerIdentity(
        account=str(resp["Account"]), arn=str(resp["Arn"]), user_id=str(resp["UserId"])
    )


def discover_mfa_serials(profile: str, region: str | None = None) -> list[str]:
    """Return the ARNs of MFA devices registered to the calling IAM user.

    Returns an empty list if the caller is not an IAM user (e.g. assumed role)
    or has no devices, rather than raising — the caller decides what to do.
    """
    client = _session(profile, region).client("iam")
    try:
        resp = client.list_mfa_devices()
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"AccessDenied", "ValidationError"}:
            return []
        raise MfaDeviceError(f"Could not list MFA devices: {exc}") from exc
    except BotoCoreError as exc:
        raise MfaDeviceError(f"Could not list MFA devices: {exc}") from exc
    return [str(d["SerialNumber"]) for d in resp.get("MFADevices", [])]


def list_aws_profiles() -> list[str]:
    """All profiles defined in ~/.aws/{credentials,config}."""
    return sorted(boto3.Session().available_profiles)
