# Overview

Orcasound hydrophone data is stored in publicly accessible S3 buckets. The buckets have both public list and public read enabled, which means you can use the AWS API to connect directly to the buckets, list the available files, and download them without any special credentials.

# Installing AWS CLI

The recommended way to [install AWS CLI is via `pip`, which requires `python` to be installed](https://docs.aws.amazon.com/cli/latest/userguide/installing.html):

`pip install awscli`

You may also be able to use a package manager such as `homebrew` or `apt-get`. Or for a friendlier UI, check out [`SAWS`](https://github.com/donnemartin/saws). Either way, if the `aws` command works then you are ready to go!

# Connecting to the buckets

No credentials are necessary to connect to the publicly accessible buckets, just the `--no-sign-request` flag instead. For example, the command to access `dev-streaming-orcasound-net`:

`aws --no-sign-request s3 ls dev-streaming-orcasound-net`

# Available buckets

| Bucket                      | Description               |
|-----------------------------|---------------------------|
| streaming-orcasound-net     | Production streaming data |
| dev-streaming-orcasound-net | Dev streaming data        |