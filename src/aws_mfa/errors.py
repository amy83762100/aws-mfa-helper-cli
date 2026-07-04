"""Typed exceptions and friendly mapping of AWS error codes."""

from __future__ import annotations


class AwsMfaError(Exception):
    """Base class for all user-facing errors.

    The message is safe to print directly to the terminal. ``hint`` is an
    optional second line suggesting what the user can do about it.
    """

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ConfigError(AwsMfaError):
    """Raised for problems reading or writing the aws-mfa-helper-cli config."""


class ProfileNotFoundError(AwsMfaError):
    """Raised when a requested profile is not configured."""


class MfaDeviceError(AwsMfaError):
    """Raised when an MFA device cannot be discovered or resolved."""


class TokenError(AwsMfaError):
    """Raised for malformed MFA token input (before hitting AWS)."""


# Friendly messages for the botocore error codes we expect to see, keyed by
# the ``Error.Code`` string botocore returns. Kept here so the AWS layer can
# stay thin and the CLI layer can present a clean message.
_FRIENDLY: dict[str, tuple[str, str]] = {
    "AccessDenied": (
        "AWS denied the request.",
        "Your base profile's access keys may be wrong, expired, or lack "
        "permission to call STS. Check ~/.aws/credentials.",
    ),
    "ValidationError": (
        "AWS rejected the request as invalid.",
        "Double-check the MFA device ARN and duration.",
    ),
    "AccessDeniedException": (
        "AWS denied the request.",
        "Check that the MFA serial number is correct and belongs to this user.",
    ),
    "InvalidClientTokenId": (
        "The access keys for this profile are not valid.",
        "Re-run `aws configure --profile <name>` with fresh keys.",
    ),
    "SignatureDoesNotMatch": (
        "The secret access key for this profile is wrong.",
        "Re-check the secret key in ~/.aws/credentials.",
    ),
    "ExpiredToken": (
        "The credentials used to make this request have expired.",
        "Run aws-mfa-helper-cli again against your *base* profile, not the -session one.",
    ),
}


def friendly_from_client_error(code: str, raw_message: str) -> AwsMfaError:
    """Translate a botocore ClientError code into an :class:`AwsMfaError`."""
    if code in _FRIENDLY:
        message, hint = _FRIENDLY[code]
        return AwsMfaError(message, hint)
    # "MultiFactorAuthentication failed ..." has no stable code; match text.
    if "MultiFactorAuthentication" in raw_message:
        return AwsMfaError(
            "The MFA code was not accepted.",
            "Codes expire every ~30s — wait for the next one and try again.",
        )
    return AwsMfaError(raw_message)
