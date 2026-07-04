"""`aws-mfa-helper-cli setup`: guided first-run wizard for AWS access keys.

Installing this tool does not grant it any AWS access — it reads the same
``~/.aws/credentials`` file the official AWS CLI uses. This wizard exists so
users who have never run ``aws configure`` can get started without installing
the AWS CLI at all.
"""

from __future__ import annotations

import typer

from aws_mfa.core.credentials import write_base_profile
from aws_mfa.core.region import all_regions
from aws_mfa.ui import prompts, render


def run_setup_wizard(profile_name: str | None = None) -> str:
    """Interactively collect access keys and write them to ~/.aws/credentials.

    Returns the profile name that was set up. Raises :class:`prompts.Aborted`
    if the user cancels.
    """
    render.info(
        "[bold]Let's set up your AWS access keys.[/]\n"
        "[dim]Find them in the AWS Console: IAM → Users → your user → "
        "Security credentials → Create access key.[/]"
    )
    name = profile_name or prompts.text("Profile name", default="default")

    access_key = ""
    while not access_key:
        access_key = prompts.text("AWS Access Key ID (starts with AKIA...)")
        if access_key and not access_key.startswith(("AKIA", "ASIA")):
            render.warn("That doesn't look like a typical access key — using it anyway.")

    secret = ""
    while not secret:
        secret = prompts.password("AWS Secret Access Key (hidden)")

    regions = all_regions()
    region_input = prompts.autocomplete(
        "Default region (type to search, e.g. ca-central-1; Enter to skip)", regions
    )
    if region_input and region_input not in regions:
        render.warn(f"'{region_input}' is not a region I know — using it anyway.")
    region = region_input or None

    write_base_profile(name, access_key, secret, region=region)
    render.info(
        f"[green]✓[/] Saved profile '[bold]{name}[/]' to ~/.aws/credentials "
        "(only readable by you)."
    )
    return name


def setup(
    profile: str = typer.Argument(None, help="Profile name to set up (prompted if omitted)."),
) -> None:
    """Set up AWS access keys — no AWS CLI needed."""
    try:
        run_setup_wizard(profile)
    except prompts.Aborted:
        render.warn("Cancelled.")
        raise typer.Exit(code=130) from None
    render.info("Next step: run [bold]aws-mfa-helper-cli[/] to get your MFA session.")
