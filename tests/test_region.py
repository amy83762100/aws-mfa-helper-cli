from __future__ import annotations

from aws_mfa.config.models import ProfileConfig
from aws_mfa.core import region


def test_explicit_wins(monkeypatch):
    p = ProfileConfig(name="dev", region="eu-west-1")
    assert region.resolve_region(p, explicit="ap-south-1") == "ap-south-1"


def test_profile_region(monkeypatch):
    monkeypatch.setattr(region.credentials, "region_for_profile", lambda *_: None)
    p = ProfileConfig(name="dev", region="eu-west-1")
    assert region.resolve_region(p) == "eu-west-1"


def test_falls_back_to_aws_config(monkeypatch):
    monkeypatch.setattr(region.credentials, "region_for_profile", lambda *_: "us-west-2")
    p = ProfileConfig(name="dev")
    assert region.resolve_region(p) == "us-west-2"


def test_env_var(monkeypatch):
    monkeypatch.setattr(region.credentials, "region_for_profile", lambda *_: None)
    monkeypatch.setenv("AWS_REGION", "ca-central-1")
    p = ProfileConfig(name="dev")
    assert region.resolve_region(p) == "ca-central-1"


def test_interactive_chooser(monkeypatch):
    monkeypatch.setattr(region.credentials, "region_for_profile", lambda *_: None)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    p = ProfileConfig(name="dev")
    assert region.resolve_region(p, interactive_chooser=lambda: "sa-east-1") == "sa-east-1"


def test_all_regions_includes_canada():
    """Regression: the old hardcoded 8-region list was missing ca-central-1."""
    regions = region.all_regions()
    assert "ca-central-1" in regions
    assert "us-east-1" in regions
    assert len(regions) > 20  # full partition list, not a tiny hardcoded one


def test_ultimate_fallback(monkeypatch):
    monkeypatch.setattr(region.credentials, "region_for_profile", lambda *_: None)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    p = ProfileConfig(name="dev")
    assert region.resolve_region(p) == region.FALLBACK_REGION
