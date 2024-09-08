import os
import json

CONFIG_FILE = os.path.expanduser("~/.aws_mfa_helper_cli_config")


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as file:
            return json.load(file)
    return {}


def save_config(profile, iam_account_id, device):
    config = load_config()
    config[profile] = {
        "iam_account_id": iam_account_id,
        "device": device,
    }
    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file, indent=4)
