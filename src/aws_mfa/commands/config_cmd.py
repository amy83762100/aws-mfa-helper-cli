"""`aws-mfa config ...` subcommands: full CRUD plus import/export."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from aws_mfa.config.models import DEFAULT_DURATION, ProfileConfig
from aws_mfa.config.store import ConfigStore
from aws_mfa.errors import AwsMfaError
from aws_mfa.ui import prompts, render

config_app = typer.Typer(help="Manage saved profiles.", no_args_is_help=True)


@config_app.command("list")
def list_profiles() -> None:
    """List configured profiles."""
    render.profiles_table(ConfigStore().all_profiles())


@config_app.command("add")
def add(name: str = typer.Argument(None, help="Profile name (prompted if omitted).")) -> None:
    """Create a new profile interactively."""
    store = ConfigStore()
    try:
        name = name or prompts.text("Profile name")
        profile = _edit_interactively(ProfileConfig(name=name))
        store.save(profile)
    except prompts.Aborted:
        raise typer.Exit(code=130) from None
    except AwsMfaError as exc:
        render.error(exc)
        raise typer.Exit(code=1) from None
    render.info(f"[green]✓[/] Saved profile '[bold]{name}[/]'.")


@config_app.command("edit")
def edit(name: str) -> None:
    """Edit an existing profile."""
    store = ConfigStore()
    try:
        profile = _edit_interactively(store.get(name))
        store.save(profile)
    except prompts.Aborted:
        raise typer.Exit(code=130) from None
    except AwsMfaError as exc:
        render.error(exc)
        raise typer.Exit(code=1) from None
    render.info(f"[green]✓[/] Updated profile '[bold]{name}[/]'.")


@config_app.command("delete")
def delete(name: str) -> None:
    """Delete a saved profile."""
    store = ConfigStore()
    try:
        store.delete(name)
    except AwsMfaError as exc:
        render.error(exc)
        raise typer.Exit(code=1) from None
    render.info(f"[green]✓[/] Deleted profile '[bold]{name}[/]'.")


@config_app.command("clear")
def clear(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Remove all saved profiles."""
    if not yes and not prompts.confirm("Delete ALL saved profiles?", default=False):
        raise typer.Exit(code=130)
    ConfigStore().clear()
    render.info("[green]✓[/] All profiles cleared.")


@config_app.command("export")
def export(
    out: Path = typer.Option(None, "--out", "-o", help="Write to a file instead of stdout."),
) -> None:
    """Export all profiles as TOML."""
    text = ConfigStore().export_toml()
    if out:
        out.write_text(text)
        render.info(f"[green]✓[/] Exported to {out}.")
    else:
        sys.stdout.write(text)


@config_app.command("import")
def import_(
    path: Path = typer.Argument(..., help="TOML file to import."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace existing profiles."),
) -> None:
    """Import profiles from a TOML file."""
    try:
        added = ConfigStore().import_toml(path.read_text(), overwrite=overwrite)
    except (AwsMfaError, OSError) as exc:
        render.error(exc if isinstance(exc, AwsMfaError) else AwsMfaError(str(exc)))
        raise typer.Exit(code=1) from None
    render.info(f"[green]✓[/] Imported {len(added)} profile(s): {', '.join(added) or '—'}")


def _edit_interactively(profile: ProfileConfig) -> ProfileConfig:
    """Prompt for each field, defaulting to the current value. Blank = auto."""
    profile.mfa_serial = prompts.text(
        "MFA serial ARN (blank = auto-discover)", default=profile.mfa_serial or ""
    ) or None
    profile.region = prompts.text(
        "Default region (blank = auto)", default=profile.region or ""
    ) or None
    duration_raw = prompts.text("Session duration in seconds", default=str(profile.duration))
    profile.duration = int(duration_raw) if duration_raw.isdigit() else DEFAULT_DURATION
    profile.role_arn = prompts.text(
        "Role ARN to assume (blank = none)", default=profile.role_arn or ""
    ) or None
    profile.source_profile = prompts.text(
        "Source AWS profile (blank = same name)", default=profile.source_profile or ""
    ) or None
    profile.output_profile = prompts.text(
        "Write session credentials to (blank = <name>-session; use the profile's "
        "own name to overwrite in place)",
        default=profile.output_profile or "",
    ) or None
    return profile
