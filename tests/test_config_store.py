from __future__ import annotations

import json
import stat

import pytest

from aws_mfa.config.models import ProfileConfig
from aws_mfa.config.store import ConfigStore
from aws_mfa.errors import ProfileNotFoundError


def test_save_and_get(config_path):
    store = ConfigStore()
    store.save(ProfileConfig(name="dev", mfa_serial="arn:aws:iam::1:mfa/x", region="us-east-1"))
    loaded = store.get("dev")
    assert loaded.mfa_serial == "arn:aws:iam::1:mfa/x"
    assert loaded.region == "us-east-1"


def test_defaults_omitted_from_toml(config_path):
    store = ConfigStore()
    store.save(ProfileConfig(name="dev"))
    text = config_path.read_text()
    assert "duration" not in text  # default duration is not serialized


def test_get_missing_raises(config_path):
    with pytest.raises(ProfileNotFoundError):
        ConfigStore().get("nope")


def test_delete_and_clear(config_path):
    store = ConfigStore()
    store.save(ProfileConfig(name="a"))
    store.save(ProfileConfig(name="b"))
    store.delete("a")
    assert store.names() == ["b"]
    store.clear()
    assert store.names() == []


def test_config_file_is_chmod_600(config_path):
    ConfigStore().save(ProfileConfig(name="dev"))
    assert stat.S_IMODE(config_path.stat().st_mode) == 0o600


def test_export_import_roundtrip(config_path, tmp_path):
    store = ConfigStore()
    store.save(ProfileConfig(name="dev", region="eu-west-1"))
    exported = store.export_toml()
    store.clear()
    added = store.import_toml(exported)
    assert added == ["dev"]
    assert store.get("dev").region == "eu-west-1"


def test_import_legacy_json(config_path, tmp_path, monkeypatch):
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({"dev": {"iam_account_id": "123456789012", "device": "iphone"}}))
    monkeypatch.setattr("aws_mfa.config.store.LEGACY_CONFIG", legacy)
    migrated = ConfigStore().import_legacy()
    assert migrated == ["dev"]
    assert ConfigStore().get("dev").mfa_serial == "arn:aws:iam::123456789012:mfa/iphone"
    # Migration is one-shot: the legacy file is renamed so it can't re-import
    # (e.g. after `reset` or `config clear`).
    assert not legacy.exists()
    assert legacy.with_name(legacy.name + ".bak").exists()
    ConfigStore().clear()
    assert ConfigStore().import_legacy() == []
