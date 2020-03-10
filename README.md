# orcadata
This repository is for the development of bioacoustic analytical tools for both humans (citizen/scientists) and machines (algorithms) to process Orcasound data -- either post-processing of archived raw FLAC files or real-time analysis of the lossy stream and/or FLAC files. The long-term goals are to characterize underwater noise in real-time and promote a friendly competition between humans and machines that leads to synergistic real-time, cloud-based processing of bioacoustic data.

## How to access Orcasound acoustic data
Each node of the Orcasound hydrophone network streams audio data to AWS S3 data buckets, all of which are open-access. If you would like [to access data, read the access.md file](https://github.com/orcasound/orcadata/blob/master/access.md).

## Resources:
* [Orcasound orcadata wiki](https://github.com/orcasound/orcadata/wiki) - updated activity & resources maintained by the community
* [Data for Good tarball of sound samples](http://orcasound.net/data4good)

## Resources to develop:

Archive of signals, noise, and empirical data for machine learning and teaching human listeners
* Example of Orcasound FLAC files (48, 96, 192 kHz)
* Guidance on how to access S3 buckets (CLI and/or Cloud9)
  * [AWS CLI set-up and syntax](https://github.com/orcasound/orcadata/blob/master/access.md) -- access public Orcasound S3 buckets

## Experiments in cloud-based bio/acoustic analysis
* AWS EC2 - Val set up scripts to upload AIS data from Orcasound Lab and build ship data set in RDS
** Lamba - Erika considered using it to deploy her ML model
** Cloud9 IDE
** Batch
** ECS
* Azure
** Pod.Cast pulls archived data to a Blob for labeling app

## Other related open-source projects, and tools for testing tools (e.g. algorithms) with Orcasound data

* Demonstrate how to run a Pamguard module on Orcasound data (archived first; then real-time)
* Ishmael?
* Triton?




