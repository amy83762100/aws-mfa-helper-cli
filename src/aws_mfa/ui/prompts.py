"""questionary wrappers for interactive selection and input.

All prompts raise :class:`Aborted` if the user cancels (Ctrl-C / ESC) so the
CLI can exit cleanly with a non-zero status.
"""

from __future__ import annotations

import sys

import questionary

from aws_mfa.errors import AwsMfaError

CREATE_NEW = "+ Create a new profile"


class Aborted(Exception):
    """Raised when the user cancels an interactive prompt."""


def _require(value: object) -> object:
    if value is None:
        raise Aborted()
    return value


def _ensure_tty() -> None:
    """Fail with a clear message instead of a prompt_toolkit crash when
    stdin is not a real terminal (pipes, CI, cron)."""
    if not sys.stdin.isatty():
        raise AwsMfaError(
            "This step is interactive and needs a real terminal.",
            hint="In scripts/CI use `aws-mfa-helper-cli mfa --profile <name> --no-input` "
            "with the MFA code piped to stdin.",
        )


def select_profile(names: list[str], *, allow_create: bool = True) -> str:
    _ensure_tty()
    choices = [*names]
    if allow_create:
        choices.append(CREATE_NEW)
    answer = questionary.select("Select a profile", choices=choices).ask()
    return str(_require(answer))


def select_one(message: str, options: list[str], *, default: str | None = None) -> str:
    _ensure_tty()
    preselect = default if default in options else None
    answer = questionary.select(message, choices=options, default=preselect).ask()
    return str(_require(answer))


def text(message: str, *, default: str = "") -> str:
    _ensure_tty()
    answer = questionary.text(message, default=default).ask()
    return str(_require(answer)).strip()


def token() -> str:
    """Read the MFA code with hidden input (never echoed, never in history)."""
    return password("Enter MFA code")


def password(message: str) -> str:
    """Hidden input for secrets (MFA codes, secret access keys)."""
    _ensure_tty()
    answer = questionary.password(message).ask()
    return str(_require(answer)).strip()


def confirm(message: str, *, default: bool = False) -> bool:
    _ensure_tty()
    answer = questionary.confirm(message, default=default).ask()
    return bool(_require(answer))


def autocomplete(message: str, choices: list[str], *, default: str = "") -> str:
    """Type-ahead input: suggestions filter as you type, but any value is
    accepted (e.g. a brand-new AWS region we don't know about yet)."""
    _ensure_tty()
    answer = questionary.autocomplete(
        message, choices=choices, default=default, ignore_case=True
    ).ask()
    return str(_require(answer)).strip()
