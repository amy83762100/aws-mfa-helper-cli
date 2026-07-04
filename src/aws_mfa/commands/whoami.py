"""`aws-mfa whoami`: show the current identity for a profile."""

from __future__ import annotations

import typer

from aws_mfa.core import identity
from aws_mfa.errors import AwsMfaError
from aws_mfa.ui import render


def whoami(
    profile: str = typer.Option("default", "--profile", "-p", help="AWS profile to inspect."),
) -> None:
    """Print the AWS identity (account, ARN) for a profile."""
    try:
        ident = identity.get_caller_identity(profile)
    except AwsMfaError as exc:
        render.error(exc)
        raise typer.Exit(code=1) from None
    render.info(f"[bold]Account:[/] {ident.account}")
    render.info(f"[bold]ARN:[/]     {ident.arn}")
    render.info(f"[bold]UserId:[/]  {ident.user_id}")
