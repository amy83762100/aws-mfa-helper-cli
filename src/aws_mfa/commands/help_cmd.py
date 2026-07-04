"""`aws-mfa-helper-cli help`: a plain-English getting-started guide (friendlier than --help)."""

from __future__ import annotations

from rich.panel import Panel

from aws_mfa.ui.render import console


def help_guide() -> None:
    """Show a friendly guide: what this tool does and how to use it."""
    console.print(
        Panel(
            "Your AWS account requires an MFA code for security. This tool turns\n"
            "that code into temporary credentials and saves them, so your normal\n"
            "AWS commands work again:\n\n"
            "  [bold]aws s3 ls --profile <your-profile>-session[/]",
            title="What does aws-mfa-helper-cli do?",
            border_style="cyan",
        )
    )
    console.print(
        Panel(
            "[bold]1.[/] Have AWS access keys? If you've ever run `aws configure`,\n"
            "   you're already done — this tool reads the same file.\n"
            "   If not: run [bold cyan]aws-mfa-helper-cli setup[/] and paste your keys "
            "(one time).\n\n"
            "[bold]2.[/] Run [bold cyan]aws-mfa-helper-cli[/] — pick your profile, type the "
            "6-digit\n"
            "   code from your authenticator app.\n\n"
            "[bold]3.[/] Use the session profile it prints, e.g.\n"
            "   [bold]aws s3 ls --profile default-session[/]\n\n"
            "When the session expires (about 12 hours), run it again.",
            title="First time? Three steps",
            border_style="green",
        )
    )
    console.print(
        Panel(
            "[bold cyan]aws-mfa-helper-cli[/]              get session credentials (interactive)\n"
            "[bold cyan]aws-mfa-helper-cli setup[/]        save your AWS access keys (first run)\n"
            "[bold cyan]aws-mfa-helper-cli whoami[/]       show which AWS identity a profile is\n"
            "[bold cyan]aws-mfa-helper-cli config list[/]  see saved profiles "
            "(also: add / edit / delete / clear)\n"
            "[bold cyan]aws-mfa-helper-cli reset[/]        remove this tool's settings "
            "(never your AWS keys)\n"
            "[bold cyan]aws-mfa-helper-cli <cmd> --help[/] details for any command",
            title="Commands",
            border_style="magenta",
        )
    )
    console.print(
        Panel(
            "• Your keys stay in [bold]~/.aws/credentials[/] — the standard AWS\n"
            "  location, readable only by you (0600). Nothing is sent anywhere\n"
            "  except AWS itself.\n"
            "• Your MFA code is never saved and never appears in shell history.\n"
            "• Tool settings live in [bold]~/.config/aws-mfa/config.toml[/].",
            title="Where do my secrets live?",
            border_style="yellow",
        )
    )
