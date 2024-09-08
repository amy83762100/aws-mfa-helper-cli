import click
from .config import load_config, save_config
from .utils import get_session_token, update_credentials


@click.command()
@click.option("--profile", default="default", prompt=True, help="AWS profile name.")
@click.option("--token-code", prompt=False, help="MFA token code.")
@click.option("--iam-account-id", default=None, help="IAM account ID.")
@click.option("--device", default=None, help="MFA device name.")
@click.option("--config", is_flag=True, help="Use this flag to set default config.")
def main(profile, token_code, iam_account_id, device, config):
    if config:
        save_config(profile, iam_account_id, device)
        click.echo("Configuration saved.")
        return

    if not iam_account_id or not device:
        conf = load_config()
        iam_account_id = iam_account_id or conf.get(profile, {}).get("iam_account_id")
        device = device or conf.get(profile, {}).get("device")

    if not iam_account_id:
        iam_account_id = click.prompt("Enter IAM account ID")

    if not device:
        device = click.prompt("Enter MFA device name")

    if not token_code:
        token_code = click.prompt("Enter MFA token code", hide_input=True)

    # Validate token code length
    if len(token_code) != 6:
        click.echo("Error: The token code must be exactly 6 digits.")
        return

    try:
        session_token_data = get_session_token(
            iam_account_id, device, token_code, profile
        )
        update_credentials(profile, session_token_data)
        click.echo(
            f"Credentials for profile '{profile}' have been updated successfully."
        )
    except Exception as e:
        click.echo(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()
