# 9/26/2024 NOTE:
This documentation is not fully updated. We are moving from the old S3 buckets to new Amazon-sponsored open data buckets in fall 2024! Most importantly the live lossy audio data are no longer stored in `streaming-orcasound-net` but instead are streaming to `audio-orcasound-net` along with other raw data streams (e.g. lossless FLAC format for select nodes). We also intend to store data products in a second Amazon-sponsored open data bucket: `audio-deriv-orcasound-net`

# Overview

Orcasound hydrophone data are stored in publicly accessible Amazon Web Service (AWS) Simple Storage Service (S3) buckets. The buckets have both public-list and public-read enabled, which means you can use the AWS Client to connect directly to the buckets, list the available files, and download them without any special credentials. Thanks to the Amazon sponsorship of our open data archive, both the storage and egress is free!

Orcasound maintains other buckets (outside of the sponsored account), including: 
1. acoustic-sandbox -- a place for acoustic analysis experiments, preliminary data products, draft models, etc.
2. visual-sandbox -- a place for experimenting with visual data that contextualizes underwater signals and noise, including photogrammetry processing and machine learning models (e.g. orca-eye-aye side-view vessel classifier)

** 2/8/25 NOTE: sections below are not yet updated **

The two versions of the streaming bucket support three versions of the Orcasound app (as depicted in this evolution model): dev-streaming-orcasound-net is for end-to-end tests where the audio source is stable/known; streaming-orcasound-net is *both* for beta-testing new app features with realistic audio data from existing nodes and for the public production version at live.orcasound.net

![Orcasound software evolution model](http://orcasound.net/img/orcasound-app/Orcasound-software-evolution-model.png)

# Installing AWS CLI

The recommended way to [install AWS CLI is via `pip`, which requires `python` to be installed](https://docs.aws.amazon.com/cli/latest/userguide/installing.html):

`pip install awscli`

For linux distros, you may also use a package manager such as `homebrew` or `apt-get`. Or for a friendlier UI, check out [`SAWS`](https://github.com/donnemartin/saws). Either way, if the `aws` command works then you are ready to go!

# Connecting to the buckets

No credentials are necessary to connect to the publicly accessible buckets, just use the `--no-sign-request` flag instead. For example, the command to access the lossy compressed audio stream segments (HLS format) in the `streaming-orcasound-net` bucket is:

`aws --no-sign-request s3 ls streaming-orcasound-net`

*Practical example:*
If you take a look at the live stream for a particular node using the network tab of your browser's development console, you may be able to note the URL of the audio data segments. 

![Orcasound web app network console data URL](http://orcasound.net/data/git/Orcasound-web-app-network-console-data-URL.png)

From that URL, you should be able to derive variable $1 -- the node name (one string with underscores, e.g. bush_point) and variable $2 --  the UNIX timestamp of desired S3 folder within the node's `hls` folder. Then you can construct a command like this to download all the available data for that period:

`aws s3 sync s3://streaming-orcasound-net/rpi_$1/hls/$2/ .` generally or in this case of Bush Point in the evening of 27 Sep 2020 -- 
`aws s3 sync s3://streaming-orcasound-net/rpi_bush_point/hls/1601253021/ .`

7/28/2022 note: [here is a shell script that Scott uses on OSX to grab 6-24 periods of live-streamed data](https://github.com/orcasound/orcadata/blob/master/Toolbox/ts2mp3.sh) that contain [Orcasound bioacoustic bouts identified by human and/or machine detectors](https://docs.google.com/spreadsheets/d/1Js1CgbmK0Vbe3m0DfiFim1BE4lXMzC75S7GN-7QEE7Y/edit#gid=0). There is a more programatic approach initiated by the OrcaHello realtime inference hackathon teams that was built upon by Dimtry during the 2021 Google Summer of Code. Prakruti and Valentina know the most about these efforts to improve and automate programmatic access to the Orcasound realtime data streams.

For nodes that have sufficent bandwidth, the lossless compressed audio data (FLAC format) can by found in the `archive-orcasound-net` bucket here: 

`aws --no-sign-request s3 ls archive-orcasound-net`

# Available buckets

| Bucket                      | Description               |
|-----------------------------|---------------------------|
| streaming-orcasound-net     | Production streaming data |
| dev-streaming-orcasound-net | Dev streaming data        |
| archive-orcasound-net       | Lossless compressed data  |
| dev-archive-orcasound-net   | Lossless compressed data  |
| acoustic-sandbox            | Acoustic machine learning labeled data & models  | 
| visual-sandbox              | Visual machine learning labeled data & models    | 

# AWS CLI syntax

To learn how to use the AWS CLI to download Orcasound data, please see [Using Amazon S3 with the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-services-s3.html).

# Browsing Orcasound data via Quilt

An alternative to listing the contents of Orcasound's S3 buckets via the AWS CLI is browsing the buckets via [open.quiltdata.com](https://open.quiltdata.com) (thanks, Praful!). For example, you can examine the live-streamed data via [https://open.quiltdata.com/b/streaming-orcasound-net](https://open.quiltdata.com/b/streaming-orcasound-net). Substitute other bucket names as listed above to explore all of our raw and labeled data, and other open resources.

# Accessing machine learning resources

The AWS CLI can be used to acquire training and testing data if you're interested in developing machine learning algorithms. Please refer to the [Orcadata wiki](https://github.com/orcasound/orcadata/wiki) for further information.

