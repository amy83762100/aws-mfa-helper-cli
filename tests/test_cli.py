"""Smoke tests for the Typer app: help guide, --help, --version."""

from __future__ import annotations

import contextlib

import pytest
from typer.testing import CliRunner

from aws_mfa import __version__
from aws_mfa.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    """Never let CLI tests touch the real config, ~/.aws, or legacy migration."""
    monkeypatch.setenv("AWS_MFA_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setattr("aws_mfa.config.store.LEGACY_CONFIG", tmp_path / "no-legacy")
    # reset.py imports LEGACY_CONFIG by name, so patch its binding as well.
    monkeypatch.setattr("aws_mfa.commands.reset.LEGACY_CONFIG", tmp_path / "no-legacy")
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-credentials"))
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-config"))


def _all_output(result) -> str:
    out = result.output
    # stderr is separate on newer click; merged (and accessing it raises) on older
    with contextlib.suppress(ValueError, AttributeError):
        out += result.stderr
    return out


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_guide_command():
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0
    assert "First time" in result.output
    assert "setup" in result.output
    assert "Where do my secrets live" in result.output


def test_standard_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("mfa", "config", "whoami", "setup", "reset", "help"):
        assert cmd in result.output


def test_reset_removes_config_and_legacy(tmp_path, monkeypatch):
    from aws_mfa.config.models import ProfileConfig
    from aws_mfa.config.store import ConfigStore

    legacy = tmp_path / "legacy.json"
    legacy.write_text("{}")
    legacy_bak = tmp_path / "legacy.json.bak"
    monkeypatch.setattr("aws_mfa.commands.reset.LEGACY_CONFIG", legacy)

    store = ConfigStore()
    store.save(ProfileConfig(name="dev"))
    assert store.path.exists()

    result = runner.invoke(app, ["reset", "--yes"])
    assert result.exit_code == 0
    assert not store.path.exists()
    assert not legacy.exists()
    assert not legacy_bak.exists()
    assert "Removed tool config" in result.output


def test_reset_is_idempotent():
    result = runner.invoke(app, ["reset", "--yes"])
    assert result.exit_code == 0
    assert "No tool config to remove" in result.output


def test_reset_single_profile(tmp_path):
    from aws_mfa.config.models import ProfileConfig
    from aws_mfa.config.store import ConfigStore

    store = ConfigStore()
    store.save(ProfileConfig(name="dev"))
    store.save(ProfileConfig(name="staging"))

    result = runner.invoke(app, ["reset", "dev", "--yes"])
    assert result.exit_code == 0
    assert "Removed saved profile 'dev'" in result.output
    assert ConfigStore().names() == ["staging"]  # only dev removed
    assert store.path.exists()  # config file itself stays


def test_reset_unknown_profile_fails_cleanly():
    result = runner.invoke(app, ["reset", "nope", "--yes"])
    assert result.exit_code == 1
    assert "No saved profile named 'nope'" in _all_output(result)


def test_reset_interactive_menu_single_profile(monkeypatch):
    from aws_mfa.commands import reset as reset_mod
    from aws_mfa.config.models import ProfileConfig
    from aws_mfa.config.store import ConfigStore

    store = ConfigStore()
    store.save(ProfileConfig(name="dev"))
    store.save(ProfileConfig(name="staging"))

    seen = {}

    def fake_select(message, options, **kwargs):
        seen["options"] = options
        return "staging"

    monkeypatch.setattr(reset_mod.prompts, "select_one", fake_select)
    monkeypatch.setattr(reset_mod.prompts, "confirm", lambda *a, **k: True)

    result = runner.invoke(app, ["reset"])
    assert result.exit_code == 0
    assert seen["options"] == ["dev", "staging", reset_mod.RESET_ALL]
    assert ConfigStore().names() == ["dev"]


def test_reset_interactive_menu_everything(monkeypatch):
    from aws_mfa.commands import reset as reset_mod
    from aws_mfa.config.models import ProfileConfig
    from aws_mfa.config.store import ConfigStore

    store = ConfigStore()
    store.save(ProfileConfig(name="dev"))

    monkeypatch.setattr(
        reset_mod.prompts, "select_one", lambda *a, **k: reset_mod.RESET_ALL
    )
    monkeypatch.setattr(reset_mod.prompts, "confirm", lambda *a, **k: True)

    result = runner.invoke(app, ["reset"])
    assert result.exit_code == 0
    assert not store.path.exists()


def test_reset_never_touches_aws_credentials(tmp_path, monkeypatch):
    """reset must be scoped to the tool's own files — the AWS credentials
    file (including *-session profiles) stays byte-identical."""
    creds_file = tmp_path / "no-credentials"
    creds_file.write_text(
        "[default]\naws_access_key_id = AKIAX\naws_secret_access_key = s\n\n"
        "[dev-session]\naws_access_key_id = ASIAX\naws_secret_access_key = s\n"
        "aws_session_token = t\n"
    )
    before = creds_file.read_text()
    result = runner.invoke(app, ["reset", "--yes"])
    assert result.exit_code == 0
    assert creds_file.read_text() == before


# --- destination picker -------------------------------------------------


def _profile(**kwargs):
    from aws_mfa.config.models import ProfileConfig

    return ProfileConfig(name="dev", **kwargs)


def test_pick_output_defaults_to_session_profile(monkeypatch):
    from aws_mfa import cli

    seen = {}

    def fake_select(message, options, default=None):
        seen["options"], seen["default"] = options, default
        return default

    monkeypatch.setattr(cli.prompts, "select_one", fake_select)
    monkeypatch.setattr(cli.credentials, "profile_has_long_lived_keys", lambda *a, **k: False)
    assert cli._pick_output_profile(_profile(), no_input=False) == "dev-session"
    assert seen["options"] == ["dev-session", "default", cli.CUSTOM_DEST]


def test_pick_output_custom_name(monkeypatch):
    from aws_mfa import cli

    monkeypatch.setattr(cli.prompts, "select_one", lambda *a, **k: cli.CUSTOM_DEST)
    monkeypatch.setattr(cli.prompts, "text", lambda *a, **k: "work")
    monkeypatch.setattr(cli.credentials, "profile_has_long_lived_keys", lambda *a, **k: False)
    assert cli._pick_output_profile(_profile(), no_input=False) == "work"


def test_pick_output_confirms_before_overwriting_permanent_keys(monkeypatch):
    """Choosing 'default' (which holds real keys) asks; declining loops back."""
    from aws_mfa import cli

    selections = iter(["default", "dev-session"])
    monkeypatch.setattr(cli.prompts, "select_one", lambda *a, **k: next(selections))
    monkeypatch.setattr(
        cli.credentials, "profile_has_long_lived_keys", lambda name, **k: name == "default"
    )
    monkeypatch.setattr(cli.prompts, "confirm", lambda *a, **k: False)  # decline
    assert cli._pick_output_profile(_profile(), no_input=False) == "dev-session"


def test_pick_output_overwrite_accepted(monkeypatch):
    from aws_mfa import cli

    monkeypatch.setattr(cli.prompts, "select_one", lambda *a, **k: "default")
    monkeypatch.setattr(cli.credentials, "profile_has_long_lived_keys", lambda *a, **k: True)
    monkeypatch.setattr(cli.prompts, "confirm", lambda *a, **k: True)
    assert cli._pick_output_profile(_profile(), no_input=False) == "default"


def test_pick_output_skipped_in_ci_mode():
    from aws_mfa import cli

    assert cli._pick_output_profile(_profile(), no_input=True) is None


def test_pick_output_preselects_saved_choice(monkeypatch):
    from aws_mfa import cli

    seen = {}

    def fake_select(message, options, default=None):
        seen["default"] = default
        return default

    monkeypatch.setattr(cli.prompts, "select_one", fake_select)
    monkeypatch.setattr(cli.credentials, "profile_has_long_lived_keys", lambda *a, **k: False)
    result = cli._pick_output_profile(_profile(output_profile="default"), no_input=False)
    assert seen["default"] == "default"
    assert result == "default"


def test_no_input_requires_profile():
    result = runner.invoke(app, ["mfa", "--no-input"], input="123456\n")
    assert result.exit_code == 1
    assert "--profile is required" in _all_output(result)


def test_interactive_without_tty_fails_cleanly():
    """Regression: piped stdin used to crash prompt_toolkit with a raw
    OSError traceback. It must be a friendly one-liner instead."""
    result = runner.invoke(app, [])
    assert result.exit_code == 1
    out = _all_output(result)
    assert "needs a real terminal" in out
    assert "Traceback" not in out
