"""Typer entry point. Thin wiring over the command/core layers."""

from __future__ import annotations

import sys
from collections.abc import Callable

import typer

from aws_mfa import __version__
from aws_mfa.commands import mfa as mfa_cmd
from aws_mfa.commands import reset as reset_cmd
from aws_mfa.commands import setup as setup_cmd
from aws_mfa.commands.config_cmd import config_app
from aws_mfa.commands.help_cmd import help_guide
from aws_mfa.commands.whoami import whoami
from aws_mfa.config.models import ProfileConfig
from aws_mfa.config.store import ConfigStore
from aws_mfa.core import credentials, identity
from aws_mfa.errors import AwsMfaError
from aws_mfa.ui import prompts, render

CUSTOM_DEST = "Type a custom name..."

app = typer.Typer(
    help="Exchange an AWS MFA code for temporary session credentials.",
    add_completion=True,
    no_args_is_help=False,
    pretty_exceptions_enable=False,  # never dump wall-of-text tracebacks on users
)
app.add_typer(config_app, name="config")
app.command("whoami")(whoami)
app.command("setup")(setup_cmd.setup)
app.command("reset")(reset_cmd.reset)
app.command("help")(help_guide)


def _version_callback(value: bool) -> None:
    if value:
        render.info(f"aws-mfa-helper-cli {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    """Run the interactive MFA flow when called with no subcommand."""
    if ctx.invoked_subcommand is None:
        render.info(
            "[dim]aws-mfa-helper-cli · Ctrl-C to quit · `aws-mfa-helper-cli help` for a guide[/]"
        )
        _run_mfa(
            profile_name=None,
            no_input=False,
            region_override=None,
            output_override=None,
            in_place=False,
            debug=False,
        )


@app.command("mfa")
def mfa(
    profile: str = typer.Option(
        None, "--profile", "-p", help="Profile to use (interactive picker if omitted)."
    ),
    region: str = typer.Option(None, "--region", "-r", help="Override the region."),
    output_profile: str = typer.Option(
        None,
        "--output-profile",
        "-o",
        help="Write session credentials to this profile instead of <profile>-session.",
    ),
    in_place: bool = typer.Option(
        False,
        "--in-place",
        help="Overwrite the selected profile itself (no -session profile). Your "
        "long-lived keys are backed up to <profile>-long-term automatically.",
    ),
    no_input: bool = typer.Option(
        False, "--no-input", help="CI mode: read the MFA code from stdin, never prompt."
    ),
    debug: bool = typer.Option(False, "--debug", help="Show full tracebacks on error."),
) -> None:
    """Generate MFA session credentials for a profile."""
    _run_mfa(
        profile_name=profile,
        no_input=no_input,
        region_override=region,
        output_override=output_profile,
        in_place=in_place,
        debug=debug,
    )


def _read_token(no_input: bool) -> str:
    """Get the MFA code — from stdin in CI mode, else a hidden prompt.

    The code is deliberately never accepted as a command-line option so it
    cannot leak into shell history or process listings.
    """
    if no_input:
        line = sys.stdin.readline().strip()
        if not line:
            raise AwsMfaError("No MFA code received on stdin (--no-input).")
        return line
    return prompts.token()


def _pick_profile(profile_name: str | None, store: ConfigStore, no_input: bool) -> ProfileConfig:
    if profile_name:
        # Use the saved config if present; otherwise treat it as an AWS profile.
        return store.get_or_none(profile_name) or ProfileConfig(name=profile_name)
    if no_input:
        raise AwsMfaError("--profile is required with --no-input.")
    # Interactive: offer saved profiles first, then any other AWS profiles.
    saved = store.names()
    aws_profiles = [p for p in identity.list_aws_profiles() if p not in saved]
    if not saved and not aws_profiles:
        # True first run: no AWS credentials anywhere on this machine.
        render.warn("No AWS credentials found on this machine yet.")
        render.info(
            "[dim]This tool reads the same file as the AWS CLI (~/.aws/credentials). "
            "You just need to save your access keys once.[/]"
        )
        if not prompts.confirm("Set up your AWS access keys now?", default=True):
            raise AwsMfaError(
                "Nothing to do without AWS access keys.",
                hint="Run `aws-mfa-helper-cli setup` when you have them, "
                "or `aws-mfa-helper-cli help` for a guide.",
            )
        name = setup_cmd.run_setup_wizard()
        return store.get_or_none(name) or ProfileConfig(name=name)
    choice = prompts.select_profile([*saved, *aws_profiles], allow_create=True)
    if choice == prompts.CREATE_NEW:
        name = prompts.text("New profile name")
        return ProfileConfig(name=name)
    return store.get_or_none(choice) or ProfileConfig(name=choice)


def _pick_output_profile(profile: ProfileConfig, no_input: bool) -> str | None:
    """Ask where the session credentials should be written.

    Choices: the conventional ``<profile>-session``, ``default``, or a custom
    name. If the chosen target already holds *permanent* access keys, an
    explicit overwrite confirmation is required (declining loops back to the
    menu). Refreshing a profile that already holds session credentials never
    asks. Returns None in CI mode (saved config / default applies).
    """
    if no_input:
        return None
    session_name = f"{profile.name}-session"
    choices = [session_name]
    if profile.name != "default":
        choices.append("default")
    saved = profile.output_profile
    if saved and saved not in choices:
        choices.insert(0, saved)
    choices.append(CUSTOM_DEST)
    preselect = saved if saved in choices else session_name

    while True:
        choice = prompts.select_one(
            "Where should the session credentials go?", choices, default=preselect
        )
        target = choice
        if choice == CUSTOM_DEST:
            target = ""
            while not target:
                target = prompts.text("Profile name to write to")
        if credentials.profile_has_long_lived_keys(target):
            overwrite = prompts.confirm(
                f"'{target}' already exists and holds permanent access keys. "
                f"Overwrite it? (they'll be backed up to '{target}-long-term')",
                default=False,
            )
            if not overwrite:
                continue  # back to the destination menu
        return target


def _ensure_base_credentials(profile: ProfileConfig, no_input: bool) -> None:
    """Make sure the source profile has access keys before asking for an MFA code.

    Interactive mode offers the setup wizard on the spot; CI mode fails with a
    clear message instead of a botocore traceback.
    """
    source = profile.resolved_source_profile
    if source in identity.list_aws_profiles():
        return
    if no_input:
        raise AwsMfaError(
            f"AWS profile '{source}' has no access keys in ~/.aws/credentials.",
            hint="Run `aws-mfa-helper-cli setup` (or `aws configure`) "
            "on a machine with a terminal.",
        )
    render.warn(f"No AWS access keys found for profile '{source}'.")
    if not prompts.confirm(f"Set up keys for '{source}' now?", default=True):
        raise AwsMfaError(
            f"Cannot continue without access keys for '{source}'.",
            hint="Run `aws-mfa-helper-cli setup` when you have them.",
        )
    setup_cmd.run_setup_wizard(source)


def _run_mfa(
    *,
    profile_name: str | None,
    no_input: bool,
    region_override: str | None,
    output_override: str | None,
    in_place: bool,
    debug: bool,
) -> None:
    store = ConfigStore()
    try:
        # One-time, silent migration from the v0.1 JSON config.
        migrated = store.import_legacy()
        if migrated:
            render.warn(
                f"Imported {len(migrated)} profile(s) from the old v0.1 config "
                "(old file kept as ~/.aws_mfa_helper_cli_config.bak)."
            )

        profile = _pick_profile(profile_name, store, no_input)
        _ensure_base_credentials(profile, no_input)

        region_chooser = None if no_input else _make_region_chooser()
        mfa_chooser = None if no_input else _make_mfa_chooser()

        # --in-place means: write over the selected profile itself.
        if in_place:
            output_override = profile.name
        # No explicit flag: ask interactively where the credentials should go.
        if output_override is None:
            output_override = _pick_output_profile(profile, no_input)

        token = _read_token(no_input)
        result = mfa_cmd.execute(
            profile,
            token,
            region_override=region_override,
            output_override=output_override,
            region_chooser=region_chooser,
            mfa_chooser=mfa_chooser,
        )
    except prompts.Aborted:
        render.warn("Cancelled.")
        raise typer.Exit(code=130) from None
    except AwsMfaError as exc:
        if debug:
            raise
        render.error(exc)
        raise typer.Exit(code=1) from None
    except Exception as exc:  # last resort: never dump a raw traceback on users
        if debug:
            raise
        render.error(
            AwsMfaError(f"Unexpected error: {exc}", hint="Re-run with --debug for details.")
        )
        raise typer.Exit(code=1) from None

    if result.long_term_backup:
        render.warn(
            f"Your long-lived keys were backed up to '{result.long_term_backup}' "
            "— future runs will use them automatically."
        )
    render.session_success(result.output_profile, result.credentials)


def _make_region_chooser() -> Callable[[], str | None]:
    from aws_mfa.core.region import all_regions

    def chooser() -> str | None:
        regions = all_regions()
        try:
            value = prompts.autocomplete(
                "Region (type to search, e.g. ca-central-1; Enter to skip)", regions
            )
        except prompts.Aborted:
            return None
        if value and value not in regions:
            render.warn(f"'{value}' is not a region I know — using it anyway.")
        return value or None

    return chooser


def _make_mfa_chooser() -> Callable[[list[str]], str]:
    def chooser(serials: list[str]) -> str:
        return prompts.select_one("Multiple MFA devices found — pick one", serials)

    return chooser


if __name__ == "__main__":
    app()
