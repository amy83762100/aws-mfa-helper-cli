"""STS calls via boto3 (no dependency on the AWS CLI binary)."""

from __future__ import annotations

import re

import boto3
from botocore.exceptions import BotoCoreError, ClientError, ProfileNotFound

from aws_mfa.config.models import MAX_DURATION, MIN_DURATION, SessionCredentials
from aws_mfa.errors import AwsMfaError, TokenError, friendly_from_client_error

_TOKEN_RE = re.compile(r"^\d{6}$")


def validate_token(token_code: str) -> str:
    """Strip whitespace and require exactly six digits."""
    token = token_code.strip()
    if not _TOKEN_RE.match(token):
        raise TokenError(
            "The MFA code must be exactly 6 digits.",
            hint="Read it fresh from your authenticator app and retry.",
        )
    return token


def _clamp_duration(duration: int) -> int:
    return max(MIN_DURATION, min(MAX_DURATION, duration))


def _session(profile: str, region: str | None) -> boto3.Session:
    try:
        return boto3.Session(profile_name=profile, region_name=region)
    except ProfileNotFound as exc:
        raise AwsMfaError(
            f"AWS profile '{profile}' was not found in ~/.aws/credentials.",
            hint="Run `aws configure --profile <name>` to create it first.",
        ) from exc


def get_session_token(
    *,
    source_profile: str,
    mfa_serial: str,
    token_code: str,
    duration: int,
    region: str | None = None,
) -> SessionCredentials:
    """Call ``sts:GetSessionToken`` with an MFA code."""
    token = validate_token(token_code)
    client = _session(source_profile, region).client("sts")
    try:
        resp = client.get_session_token(
            DurationSeconds=_clamp_duration(duration),
            SerialNumber=mfa_serial,
            TokenCode=token,
        )
    except ClientError as exc:
        raise _translate(exc) from exc
    except BotoCoreError as exc:
        raise AwsMfaError(f"Could not reach AWS STS: {exc}") from exc
    return SessionCredentials.from_sts_response(resp["Credentials"])


def assume_role(
    *,
    source_profile: str,
    role_arn: str,
    mfa_serial: str,
    token_code: str,
    duration: int,
    region: str | None = None,
    session_name: str = "aws-mfa",
) -> SessionCredentials:
    """Call ``sts:AssumeRole`` with an MFA code (the modern IAM pattern)."""
    token = validate_token(token_code)
    client = _session(source_profile, region).client("sts")
    try:
        resp = client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            DurationSeconds=_clamp_duration(duration),
            SerialNumber=mfa_serial,
            TokenCode=token,
        )
    except ClientError as exc:
        raise _translate(exc) from exc
    except BotoCoreError as exc:
        raise AwsMfaError(f"Could not reach AWS STS: {exc}") from exc
    return SessionCredentials.from_sts_response(resp["Credentials"])


def _translate(exc: ClientError) -> AwsMfaError:
    code = str(exc.response.get("Error", {}).get("Code", ""))
    message = str(exc.response.get("Error", {}).get("Message", str(exc)))
    return friendly_from_client_error(code, message)
