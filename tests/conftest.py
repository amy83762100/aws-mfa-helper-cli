from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aws_mfa.config.models import SessionCredentials


@pytest.fixture()
def config_path(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    monkeypatch.setenv("AWS_MFA_CONFIG", str(path))
    return path


@pytest.fixture()
def fake_creds():
    return SessionCredentials(
        access_key_id="AKIAFAKE",
        secret_access_key="secretkey",
        session_token="sessiontoken",
        expiration=datetime.now(timezone.utc) + timedelta(hours=12),
    )


@pytest.fixture()
def aws_home(tmp_path, monkeypatch):
    """Point the AWS credential/config files at a temp dir via the standard
    env vars (the same ones boto3 honors)."""
    aws_dir = tmp_path / ".aws"
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(aws_dir / "credentials"))
    monkeypatch.setenv("AWS_CONFIG_FILE", str(aws_dir / "config"))
    return aws_dir
