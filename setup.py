from setuptools import setup, find_packages

setup(
    name="aws-mfa-helper-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click",
    ],
    entry_points={
        "console_scripts": [
            "aws-mfa-helper-cli=aws_mfa_helper_cli.cli:main",
        ],
    },
    author="Pei-Yi Lin",
    description="A CLI tool to manage AWS MFA session tokens easily.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/amy83762100/aws-mfa-helper-cli",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
