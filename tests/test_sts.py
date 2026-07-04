from __future__ import annotations

from datetime import datetime, timezone

import boto3
import pytest
from botocore.stub import Stubber

from aws_mfa.core import sts
from aws_mfa.errors import AwsMfaError, TokenError

SERIAL = "arn:aws:iam::123456789012:mfa/dev"


@pytest.mark.parametrize("bad", ["123", "1234567", "12a456", "", "  12 34 "])
def test_validate_token_rejects_bad(bad):
    with pytest.raises(TokenError):
        sts.validate_token(bad)


def test_validate_token_strips_whitespace():
    assert sts.validate_token("  123456 \n") == "123456"


def test_get_session_token_success(monkeypatch):
    client = boto3.client("sts", region_name="us-east-1")
    stubber = Stubber(client)
    expiry = datetime(2030, 1, 1, tzinfo=timezone.utc)
    stubber.add_response(
        "get_session_token",
        {
            "Credentials": {
                "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
                "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                "SessionToken": "FQoGZXIvYXdzEXAMPLEtoken",
                "Expiration": expiry,
            }
        },
        {"DurationSeconds": 43200, "SerialNumber": SERIAL, "TokenCode": "123456"},
    )
    stubber.activate()
    monkeypatch.setattr(sts, "_session", lambda *a, **k: _FakeSession(client))

    creds = sts.get_session_token(
        source_profile="dev", mfa_serial=SERIAL, token_code="123456", duration=43200
    )
    assert creds.access_key_id == "AKIAIOSFODNN7EXAMPLE"
    assert creds.expiration == expiry


def test_client_error_is_translated(monkeypatch):
    client = boto3.client("sts", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_client_error(
        "get_session_token",
        service_error_code="AccessDenied",
        service_message="not allowed",
    )
    stubber.activate()
    monkeypatch.setattr(sts, "_session", lambda *a, **k: _FakeSession(client))

    with pytest.raises(AwsMfaError) as exc:
        sts.get_session_token(
            source_profile="dev", mfa_serial=SERIAL, token_code="123456", duration=43200
        )
    assert "denied" in str(exc.value).lower()
    assert exc.value.hint is not None


class _FakeSession:
    def __init__(self, client):
        self._client = client

    def client(self, _name):
        return self._client
