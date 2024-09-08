# AWS MFA Helper CLI

`aws-mfa-helper-cli` is a simple command-line tool that helps manage AWS MFA session tokens. It automates the process of generating a session token using MFA and stores the credentials in a separate session profile, allowing you to easily switch between your original and session profiles.

## Prerequisites

Before using this package, make sure you have the following:

1. **AWS CLI Installed**: You need to have AWS CLI installed on your machine. You can download and install it from [here](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html). 
   - After installing, configure it by running:
     ```bash
     aws configure
     ```
     Make sure you have your AWS access key ID and secret access key ready.

2. **AWS Credentials**: Ensure that your `~/.aws/credentials` file is correctly set up with your AWS profiles. The default profile is used if none is specified.

Here's an example of the AWS credentials file (`~/.aws/credentials`):

```
[default]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
```

## Installation

You can install this package using pip:

```bash
pip install aws-mfa-helper-cli
```

## Usage

### Setting Up IAM Account and Device (Optional)

Before generating an MFA session token, you can configure your IAM account ID and MFA device for a specific profile to avoid entering them every time. You can do this by running the following command:

```bash
aws-mfa-helper-cli --config --profile your-profile-name --iam-account-id 123456789012 --device your-mfa-device
```

Example:

```bash
aws-mfa-helper-cli --config --profile your-profile --iam-account-id 123456789012 --device iphone
```

This will save the IAM account ID and device name for the specified profile. The next time you use this profile, the tool will automatically use these values.

### Generating a New Session Token

To generate an MFA session token, run the following command:

```bash
aws-mfa-helper-cli --profile your-profile-name --token-code 123456
```

Example:

```bash
aws-mfa-helper-cli --profile your-profile --token-code 654321
```

The tool will use the specified profile to generate a session token using your MFA device. The session token credentials will be stored in a new profile named `<profile-name>-session`.

### Using the Session Profile

Once the session token is generated, you must use the session profile for all your subsequent AWS commands during the session period. The session profile will be named `<profile-name>-session`. For example, if you generated the session token for the profile `your-profile`, you can now use the profile `your-profile-session` for your AWS commands:

```bash
aws s3 ls --profile your-profile-session
```

The session credentials will expire after a period (usually 12 hours), after which you will need to run the `aws-mfa-helper-cli` command again to get a new session token.

### Handling the Region

If your original profile has a region specified in the `~/.aws/config` file, the region will automatically be copied over to the session profile. If not, the AWS CLI will use the default region.

## Example Workflow

1. **Set up your IAM account ID and device for a profile** (Optional but recommended):
   ```bash
   aws-mfa-helper-cli --config --profile your-profile --iam-account-id 123456789012 --device iphone
   ```

2. **Generate a session token**:
   ```bash
   aws-mfa-helper-cli --profile your-profile --token-code 654321
   ```

   This will create a session profile named `your-profile-session`.

3. **Use the session profile for AWS commands**:
   ```bash
   aws s3 ls --profile your-profile-session
   ```

## Notes

- The `aws-mfa-helper-cli` tool will create a new session profile every time you run the command. You must use this session profile for all AWS operations while the session is active.
- If your session credentials expire, simply run the `aws-mfa-helper-cli` command again to generate a new session token.

## License

This project is licensed under the MIT License.
