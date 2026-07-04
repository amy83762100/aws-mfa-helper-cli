"""Tests for the mfa orchestration: output override and source redirection."""

from __future__ import annotations

import configparser

import pytest

from aws_mfa.commands import mfa as mfa_cmd
from aws_mfa.config.models import ProfileConfig
from aws_mfa.core.credentials import write_base_profile


@pytest.fixture()
def fake_sts(monkeypatch, fake_creds):
    """Stub out the STS call, capturing which source profile was used."""
    calls: dict[str, str] = {}

    def _fake_get_session_token(*, source_profile, mfa_serial, token_code, duration, region=None):
        calls["source_profile"] = source_profile
        return fake_creds

    monkeypatch.setattr(mfa_cmd.sts, "get_session_token", _fake_get_session_token)
    return calls


def _profile(**kwargs) -> ProfileConfig:
    return ProfileConfig(
        name="dev",
        mfa_serial="arn:aws:iam::123456789012:mfa/dev",  # skip IAM discovery
        region="us-east-1",  # skip region resolution I/O
        **kwargs,
    )


def test_default_output_is_session_suffix(aws_home, fake_sts):
    result = mfa_cmd.execute(_profile(), "123456")
    assert result.output_profile == "dev-session"
    assert fake_sts["source_profile"] == "dev"
    assert result.long_term_backup is None


def test_output_override(aws_home, fake_sts):
    result = mfa_cmd.execute(_profile(), "123456", output_override="work")
    assert result.output_profile == "work"


def test_in_place_backs_up_and_redirects_source(aws_home, fake_sts):
    """First in-place run: keys backed up. Second run: STS uses the backup."""
    write_base_profile(
        "dev", "AKIAIOSFODNN7EXAMPLE", "secret",
        credentials_file=aws_home / "credentials", config_file=aws_home / "config",
    )
    # First run: output == source → long-lived keys get backed up.
    result = mfa_cmd.execute(_profile(), "123456", output_override="dev")
    assert result.output_profile == "dev"
    assert result.long_term_backup == "dev-long-term"
    assert fake_sts["source_profile"] == "dev"  # keys were still live here

    # Second run: [dev] now holds session creds; source must redirect.
    result2 = mfa_cmd.execute(_profile(), "123456", output_override="dev")
    assert fake_sts["source_profile"] == "dev-long-term"
    assert result2.long_term_backup is None

    parser = configparser.ConfigParser()
    parser.read(aws_home / "credentials")
    assert parser["dev-long-term"]["aws_secret_access_key"] == "secret"
    assert parser["dev"]["aws_session_token"] == "sessiontoken"


def test_saved_output_profile_in_config(aws_home, fake_sts):
    """output_profile persisted in the profile config is honored."""
    result = mfa_cmd.execute(_profile(output_profile="dev"), "123456")
    assert result.output_profile == "dev"
