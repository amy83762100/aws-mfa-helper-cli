"""Tests for credential writing — including the two original bugs."""

from __future__ import annotations

import configparser
import stat

from aws_mfa.core import credentials


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_writes_session_block(aws_home, fake_creds):
    credentials.write_session_credentials(
        "dev-session",
        fake_creds,
        credentials_file=aws_home / "credentials",
        config_file=aws_home / "config",
    )
    parser = configparser.ConfigParser()
    parser.read(aws_home / "credentials")
    assert parser["dev-session"]["aws_access_key_id"] == "AKIAFAKE"
    assert parser["dev-session"]["aws_session_token"] == "sessiontoken"


def test_credentials_file_is_chmod_600(aws_home, fake_creds):
    """Regression: original code never restricted permissions."""
    creds_file = aws_home / "credentials"
    credentials.write_session_credentials(
        "dev-session", fake_creds, credentials_file=creds_file, config_file=aws_home / "config"
    )
    assert _mode(creds_file) == 0o600
    assert _mode(aws_home) == 0o700


def test_region_written_to_config(aws_home, fake_creds):
    """Regression: original `~./.aws/config` path never expanded, so region
    copying silently did nothing. Here it must actually land."""
    config_file = aws_home / "config"
    credentials.write_session_credentials(
        "dev-session",
        fake_creds,
        region="eu-west-1",
        credentials_file=aws_home / "credentials",
        config_file=config_file,
    )
    parser = configparser.ConfigParser()
    parser.read(config_file)
    assert parser["profile dev-session"]["region"] == "eu-west-1"


def test_region_for_profile_default_section(aws_home, fake_creds):
    config_file = aws_home / "config"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("[default]\nregion = ap-southeast-1\n")
    assert credentials.region_for_profile("default", config_file) == "ap-southeast-1"


def test_write_base_profile(aws_home):
    credentials.write_base_profile(
        "dev",
        "AKIAIOSFODNN7EXAMPLE",
        "  wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY  ",  # whitespace stripped
        region="eu-central-1",
        credentials_file=aws_home / "credentials",
        config_file=aws_home / "config",
    )
    parser = configparser.ConfigParser()
    parser.read(aws_home / "credentials")
    assert parser["dev"]["aws_access_key_id"] == "AKIAIOSFODNN7EXAMPLE"
    assert parser["dev"]["aws_secret_access_key"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    assert _mode(aws_home / "credentials") == 0o600

    config = configparser.ConfigParser()
    config.read(aws_home / "config")
    assert config["profile dev"]["region"] == "eu-central-1"


def test_write_base_profile_keeps_existing_profiles(aws_home, fake_creds):
    creds_file = aws_home / "credentials"
    credentials.write_session_credentials(
        "old-session", fake_creds, credentials_file=creds_file, config_file=aws_home / "config"
    )
    credentials.write_base_profile(
        "new", "AKIAIOSFODNN7EXAMPLE", "secret",
        credentials_file=creds_file, config_file=aws_home / "config",
    )
    parser = configparser.ConfigParser()
    parser.read(creds_file)
    assert parser.has_section("old-session")
    assert parser.has_section("new")


def test_overwrite_in_place_backs_up_long_lived_keys(aws_home, fake_creds):
    """Overwriting a profile that holds permanent keys must first copy them
    to <name>-long-term — otherwise the user is locked out at expiry."""
    creds_file = aws_home / "credentials"
    credentials.write_base_profile(
        "default", "AKIAIOSFODNN7EXAMPLE", "permanentsecret",
        credentials_file=creds_file, config_file=aws_home / "config",
    )
    backup = credentials.write_session_credentials(
        "default", fake_creds, credentials_file=creds_file, config_file=aws_home / "config"
    )
    assert backup == "default-long-term"

    parser = configparser.ConfigParser()
    parser.read(creds_file)
    # Backup holds the permanent keys...
    assert parser["default-long-term"]["aws_access_key_id"] == "AKIAIOSFODNN7EXAMPLE"
    assert parser["default-long-term"]["aws_secret_access_key"] == "permanentsecret"
    # ...and the profile itself now holds the session credentials.
    assert parser["default"]["aws_access_key_id"] == "AKIAFAKE"
    assert parser["default"]["aws_session_token"] == "sessiontoken"


def test_overwrite_in_place_second_run_keeps_backup(aws_home, fake_creds):
    """A second overwrite must NOT clobber the long-term backup with the
    session credentials that now occupy the profile."""
    creds_file = aws_home / "credentials"
    credentials.write_base_profile(
        "default", "AKIAIOSFODNN7EXAMPLE", "permanentsecret",
        credentials_file=creds_file, config_file=aws_home / "config",
    )
    first = credentials.write_session_credentials(
        "default", fake_creds, credentials_file=creds_file, config_file=aws_home / "config"
    )
    second = credentials.write_session_credentials(
        "default", fake_creds, credentials_file=creds_file, config_file=aws_home / "config"
    )
    assert first == "default-long-term"
    assert second is None  # target already held session creds; no new backup

    parser = configparser.ConfigParser()
    parser.read(creds_file)
    assert parser["default-long-term"]["aws_secret_access_key"] == "permanentsecret"


def test_writing_to_session_profile_creates_no_backup(aws_home, fake_creds):
    backup = credentials.write_session_credentials(
        "dev-session", fake_creds,
        credentials_file=aws_home / "credentials", config_file=aws_home / "config",
    )
    assert backup is None


def test_profile_exists(aws_home, fake_creds):
    creds_file = aws_home / "credentials"
    assert not credentials.profile_exists("dev", credentials_file=creds_file)
    credentials.write_base_profile(
        "dev", "AKIAIOSFODNN7EXAMPLE", "s",
        credentials_file=creds_file, config_file=aws_home / "config",
    )
    assert credentials.profile_exists("dev", credentials_file=creds_file)


def test_profile_has_long_lived_keys(aws_home, fake_creds):
    creds_file = aws_home / "credentials"
    credentials.write_base_profile(
        "dev", "AKIAIOSFODNN7EXAMPLE", "s",
        credentials_file=creds_file, config_file=aws_home / "config",
    )
    credentials.write_session_credentials(
        "dev-session", fake_creds,
        credentials_file=creds_file, config_file=aws_home / "config",
    )
    assert credentials.profile_has_long_lived_keys("dev", credentials_file=creds_file)
    # Session profiles and unknown profiles must not trigger overwrite confirms.
    assert not credentials.profile_has_long_lived_keys("dev-session", credentials_file=creds_file)
    assert not credentials.profile_has_long_lived_keys("missing", credentials_file=creds_file)


def test_region_for_named_profile(aws_home):
    config_file = aws_home / "config"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("[profile dev]\nregion = us-west-2\n")
    assert credentials.region_for_profile("dev", config_file) == "us-west-2"
    assert credentials.region_for_profile("missing", config_file) is None
