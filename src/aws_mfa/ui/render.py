"""Rich-based output helpers. Kept side-effect-only so logic stays testable."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from aws_mfa.config.models import ProfileConfig, SessionCredentials
from aws_mfa.errors import AwsMfaError

console = Console()
err_console = Console(stderr=True)


def _fmt_remaining(seconds: int) -> str:
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def session_success(output_profile: str, creds: SessionCredentials) -> None:
    expiry = creds.expiration.astimezone().strftime("%H:%M")
    console.print(
        f"[bold green]✓[/] Session valid until [bold]{expiry}[/] "
        f"([cyan]{_fmt_remaining(creds.seconds_remaining)}[/] left)."
    )
    if output_profile == "default":
        console.print(
            "  Written to your [bold]default[/] profile; aws commands will use it automatically."
        )
    else:
        console.print(f"  Use it with: [bold]--profile {output_profile}[/]")


def error(exc: AwsMfaError) -> None:
    err_console.print(f"[bold red]✗[/] {exc.message}")
    if exc.hint:
        err_console.print(f"  [dim]{exc.hint}[/]")


def profiles_table(profiles: list[ProfileConfig]) -> None:
    if not profiles:
        console.print("[dim]No profiles configured yet. Run `aws-mfa-helper-cli config add`.[/]")
        return
    table = Table(title="aws-mfa-helper-cli profiles")
    table.add_column("Profile", style="bold")
    table.add_column("MFA serial")
    table.add_column("Region")
    table.add_column("Duration")
    table.add_column("Role", overflow="fold")
    for p in profiles:
        table.add_row(
            p.name,
            p.mfa_serial or "[dim]auto-discover[/]",
            p.region or "[dim]auto[/]",
            f"{p.duration // 3600}h",
            p.role_arn or "[dim]—[/]",
        )
    console.print(table)


def info(message: str) -> None:
    console.print(message)


def warn(message: str) -> None:
    console.print(f"[yellow]![/] {message}")
