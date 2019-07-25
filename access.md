# Overview

Orcasound hydrophone data is stored in publicly accessible S3 buckets. The buckets have both public list and public read enabled, which means you can use the AWS API to connect directly to the buckets, list the available files, and download them without any special credentials.

There are three types of buckets, two of which have live and dev versions: 
1. Streaming -- lossy compressed data for live listening (e.g. HLS and/or DASH)
1. Archive -- lossless compressed data for nodes with sufficient bandwidth (FLAC format)
1. Sandboxes -- data sets for machine learning and other analyses

The two verions of the streaming bucket support three verions of the Orcasound app (as depicted in this evolution model): dev-streaming-orcasound-net is for end-to-end tests where the audio source is stable/known; and streaming-orcasound-net is both for beta-testing new app features with realistic audio data from existing nodes and for the public production version at live.orcasound.net

![Orcasound software evolution model](http://orcasound.net/img/orcasound-app/Orcasound-software-evolution-model.png)

# Installing AWS CLI

The recommended way to [install AWS CLI is via `pip`, which requires `python` to be installed](https://docs.aws.amazon.com/cli/latest/userguide/installing.html):

`pip install awscli`

You may also be able to use a package manager such as `homebrew` or `apt-get`. Or for a friendlier UI, check out [`SAWS`](https://github.com/donnemartin/saws). Either way, if the `aws` command works then you are ready to go!

# Connecting to the buckets

No credentials are necessary to connect to the publicly accessible buckets, just use the `--no-sign-request` flag instead. For example, the command to access the lossy compressed audio stream segments in the `streaming-orcasound-net` bucket is:

`aws --no-sign-request s3 ls streaming-orcasound-net`

# Available buckets

| Bucket                      | Description               |
|-----------------------------|---------------------------|
| streaming-orcasound-net     | Production streaming data |
| dev-streaming-orcasound-net | Dev streaming data        |
| archive-orcasound-net       | Lossless compressed data  |
| dev-archive-orcasound-net   | Lossless compressed data  |
| acoustic-sandbox            | Machine learning space    | 
