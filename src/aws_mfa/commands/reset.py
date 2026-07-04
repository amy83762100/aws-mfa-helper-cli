"""`aws-mfa-helper-cli reset`: remove saved profiles or all tool settings.

Scope is deliberately narrow: only aws-mfa-helper-cli's own config is touched.
The AWS credentials/config files (``~/.aws/...``) are NEVER modified — not your
access keys, not even the ``*-session`` profiles this tool wrote.
"""

from __future__ import annotations

import typer

from aws_mfa.config.store import LEGACY_CONFIG, ConfigStore
from aws_mfa.errors import AwsMfaError
from aws_mfa.ui import prompts, render

RESET_ALL = "Everything (all tool settings)"


def reset(
    profile: str = typer.Argument(
        None, help="Saved profile to remove. Omit to choose from a menu."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Remove a saved profile — or everything. Never touches your AWS credentials."""
    store = ConfigStore()
    try:
        if profile is not None:
            _delete_one(store, profile, yes)
            return

        if yes:  # non-interactive full reset (scripts/CI)
            _reset_everything(store)
            return

        names = store.names()
        if not names:
            if store.path.exists() or LEGACY_CONFIG.exists():
                if prompts.confirm(
                    "No saved profiles, but tool config files exist. Remove them?",
                    default=True,
                ):
                    _reset_everything(store)
            else:
                render.info("[dim]Nothing to reset — no tool settings found.[/]")
            return

        choice = prompts.select_one("What do you want to reset?", [*names, RESET_ALL])
        if choice == RESET_ALL:
            if prompts.confirm(
                "Remove ALL aws-mfa-helper-cli settings? "
                "(your AWS credentials file is NOT touched)",
                default=False,
            ):
                _reset_everything(store)
            else:
                render.warn("Cancelled.")
                raise typer.Exit(code=130)
        else:
            _delete_one(store, choice, yes=False)
    except prompts.Aborted:
        render.warn("Cancelled.")
        raise typer.Exit(code=130) from None
    except AwsMfaError as exc:
        render.error(exc)
        raise typer.Exit(code=1) from None


def _delete_one(store: ConfigStore, name: str, yes: bool) -> None:
    if not yes and not prompts.confirm(f"Remove saved profile '{name}'?", default=True):
        render.warn("Cancelled.")
        raise typer.Exit(code=130)
    store.delete(name)  # raises a friendly error if the name is unknown
    render.info(f"[green]✓[/] Removed saved profile '[bold]{name}[/]'.")


def _reset_everything(store: ConfigStore) -> None:
    had_config = store.path.exists()
    store.path.unlink(missing_ok=True)
    render.info(
        f"[green]✓[/] Removed tool config ({store.path})."
        if had_config
        else "[dim]No tool config to remove.[/]"
    )
    # Remove any legacy v0.1 config (and its .bak) so nothing re-imports.
    for legacy in (LEGACY_CONFIG, LEGACY_CONFIG.with_name(LEGACY_CONFIG.name + ".bak")):
        if legacy.exists():
            legacy.unlink()
            render.info(f"[green]✓[/] Removed old v0.1 config ({legacy}).")
    render.info("Done. Run [bold]aws-mfa-helper-cli[/] to start again.")
