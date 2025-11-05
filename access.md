# 9/26/2024 NOTE:
This documentation is not fully updated. We are moving from the old S3 buckets to new Amazon-sponsored open data buckets in fall 2024! Most importantly the live lossy audio data are no longer stored in `streaming-orcasound-net` but instead are streaming to `audio-orcasound-net` along with other raw data streams (e.g. lossless FLAC format for select nodes). We also intend to store data products in a second Amazon-sponsored open data bucket: `audio-deriv-orcasound-net`


# Overview

Orcasound hydrophone data are stored in publicly accessible Amazon Web Service (AWS) Simple Storage Service (S3) buckets. The buckets have both public-list and public-read enabled, which means you can use the AWS Client to connect directly to the buckets, list the available files, and download them without any special credentials. Thanks to the Amazon sponsorship of our open data archive, both the storage and egress is free!


# Browser Access
One can browse the raw data through the [Quilt Data Portal]((https://open.quiltdata.com)) (thanks, Praful!):

- [audio-orcasound-net](https://open.quiltdata.com/b/audio-orcasound-net/tree/)
- [audio-deriv-orcasound-net](https://open.quiltdata.com/b/audio-deriv-orcasound-net/tree/)

One can see that the data are organized into folders corresponding to the individual hydrophones, timestamp folders of small `.ts` files which are streaming audio files of length of approximately 10 sec.

Those two buckets are sponsored by AWS through the [Open Data Sponsorship Program](https://aws.amazon.com/opendata/open-data-sponsorship-program/). Orcasound maintains other buckets (outside of the sponsored account), including: 
1. `acoustic-sandbox` -- a place for acoustic analysis experiments, preliminary data products, draft models, etc.
2. `visual-sandbox` -- a place for experimenting with visual data that contextualizes underwater signals and noise, including photogrammetry processing and machine learning models (e.g. orca-eye-aye side-view vessel classifier). Below is a full list of buckets. You can substitute the name of the bucket in `https://open.quiltdata.com/b/[bucket-name]` to explore them.

# Available buckets

| Bucket                      | Description               |
|-----------------------------|---------------------------|
| audio-orcasound-net         | Production streaming data |
| audio-deriv-orcasound-net   | Derivative data producs   |
| dev-streaming-orcasound-net | Dev streaming data        |
| archive-orcasound-net       | Lossless compressed data  |
| dev-archive-orcasound-net   | Lossless compressed data  |
| acoustic-sandbox            | Acoustic machine learning labeled data & models  | 
| visual-sandbox              | Visual machine learning labeled data & models    | 

# AWS CLI Access
To access the data programmatically one can use the AWS client. 

## Installing AWS CLI

The recommended way to [install AWS CLI is via `pip`, which requires `python` to be installed](https://docs.aws.amazon.com/cli/latest/userguide/installing.html):

`pip install awscli`

For linux distros, you may also use a package manager such as `homebrew` or `apt-get`. Or for a friendlier UI, check out [`SAWS`](https://github.com/donnemartin/saws). Either way, if the `aws` command works then you are ready to go!

To learn how to use the AWS CLI to download Orcasound data, please see [Using Amazon S3 with the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-services-s3.html).

Here is a [shell script](https://github.com/orcasound/orcadata/blob/master/Toolbox/ts2mp3.sh) that Scott uses on OSX to grab 6-24 periods of live-streamed data] that contain [Orcasound bioacoustic bouts identified by human and/or machine detectors](https://docs.google.com/spreadsheets/d/1Js1CgbmK0Vbe3m0DfiFim1BE4lXMzC75S7GN-7QEE7Y/edit#gid=0). You need to update the bucket name in the script.

## Connecting to the buckets

No credentials are necessary to connect to the publicly accessible buckets, just use the `--no-sign-request` flag instead. For example, the command to access the lossy compressed audio stream segments (HLS format) in the `streaming-orcasound-net` bucket is:

`aws --no-sign-request s3 ls audio-orcasound-net`

*Practical example:*
If you take a look at the live stream for a particular node using the network tab of your browser's development console, you may be able to note the URL of the audio data segments. 

<img width="991" height="718" alt="Orcasound-web-app-network-console-data-URL" src="https://github.com/user-attachments/assets/82f79508-3ea6-44f9-919d-57f43cb76ad1" />

From that URL, you should be able to derive variable $1 -- the node name (one string with underscores, e.g. bush_point) and variable $2 --  the UNIX timestamp of desired S3 folder within the node's `hls` folder. Then you can construct a command like this to download all the available data for that period:

`aws --no-sign-request s3 sync s3://audio-orcasound-net/rpi_$1/hls/$2/ .` generally or in this case of Sunset Bay in the evening of 5 Nov 2025 -- 

`aws --no-sign-request s3 sync s3://audio-orcasound-net/rpi_sunset_bay/hls/1762243221/ .`


# Python Access
The `hls` streaming data can also be accessed through the [`orca-hls-utils`](https://github.com/orcasound/orca-hls-utils) package (under continuous development). It provides options to load the streaming data and convert it to the popular `.wav` for a range of time. Another package built on top of it is [`ambient-sound-analysis`](https://github.com/orcasound/ambient-sound-analysis) which directly generates power spectra for period of time and can be useful for generating training data for ML algorithms or ambient noise studies.

# Accessing machine learning resources

The AWS CLI can be used to acquire training and testing data if you're interested in developing machine learning algorithms. Please refer to the [Orcadata wiki](https://github.com/orcasound/orcadata/wiki) for further information.

** 2/8/25 NOTE: sections below are not yet updated **

The two versions of the streaming bucket support three versions of the Orcasound app (as depicted in this evolution model): dev-streaming-orcasound-net is for end-to-end tests where the audio source is stable/known; streaming-orcasound-net is *both* for beta-testing new app features with realistic audio data from existing nodes and for the public production version at live.orcasound.net

![Orcasound software evolution model](http://orcasound.net/img/orcasound-app/Orcasound-software-evolution-model.png)

