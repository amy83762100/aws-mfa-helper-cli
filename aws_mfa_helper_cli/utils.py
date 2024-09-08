import subprocess
import configparser
import os
import json


def get_session_token(iam_account_id, device, token_code, profile):
    mfa_arn = f"arn:aws:iam::{iam_account_id}:mfa/{device}"
    command = [
        "aws",
        "sts",
        "get-session-token",
        "--serial-number",
        mfa_arn,
        "--token-code",
        token_code,
        "--profile",
        profile,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Error: {result.stderr}")

    return json.loads(result.stdout)["Credentials"]


def update_credentials(profile, credentials):
    credentials_file = os.path.expanduser("~/.aws/credentials")
    config_file = os.path.expanduser("~./.aws/config")

    # Load the credentials file
    cred_config = configparser.ConfigParser()
    cred_config.read(credentials_file)

    # Load the config file
    aws_config = configparser.ConfigParser()
    aws_config.read(config_file)

    session_profile = f"{profile}-session"

    if session_profile not in cred_config:
        cred_config.add_section(session_profile)

    cred_config[session_profile]["aws_access_key_id"] = credentials["AccessKeyId"]
    cred_config[session_profile]["aws_secret_access_key"] = credentials[
        "SecretAccessKey"
    ]
    cred_config[session_profile]["aws_session_token"] = credentials["SessionToken"]

    with open(credentials_file, "w") as cred_file:
        cred_config.write(cred_file)

    # Ensure the region from the original profile is copied over to the session profile in config
    original_profile_section = f"profile {profile}"

    if original_profile_section in aws_config:
        session_profile_section = f"profile {session_profile}"
        if session_profile_section not in aws_config:
            aws_config.add_section(session_profile_section)

        if "region" in aws_config[original_profile_section]:
            aws_config[session_profile_section]["region"] = aws_config[
                original_profile_section
            ]["region"]

        with open(config_file, "w") as conf_file:
            aws_config.write(conf_file)

        print(f"Region from profile '{profile}' copied to '{session_profile}'.")
    else:
        # If the profile doesn't exist, rely on the default region
        print(
            f"No region found for profile '{profile}', using default region for '{session_profile}'."
        )
