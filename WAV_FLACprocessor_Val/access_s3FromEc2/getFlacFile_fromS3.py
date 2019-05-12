#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""  Get a flac file from S3 bucket
xfer python up to ecs:
scp -i /home/val/AWS/Orcasoundpair.pem  getFlacFile_fromS3.py ubuntu@ec2-54-188-56-129.us-west-2.compute.$
secure shell to ec2 instance
ssh -i "/home/val/AWS/Orcasoundpair.pem" ubuntu@ec2-54-188-56-129.us-west-2.compute.amazonaws.com


Note:  a number of python modules had to be installed into the Ubuntu instance:

sudo pip3 install SoundFile
sudo apt-get install libsndfile-dev
sudo apt-get install python3-numpy
sudo apt-get install python3-scipy
sudo apt-get install python3-matplotlib

"""
import soundfile as sf
import boto3
import numpy as np
import os

client = boto3.client('s3')

# go over to S3 bucket and grap a flac file
client.download_file('dev-archive-orcasound-net', 'val_test/test_1_s3.flac', 'test_1_s3.flac')

# read the file
data, rate = sf.read('test_1_s3.flac')

print("data shape",data.shape)
print("sample rate",rate)
print("mean amplitude",np.mean(data))
print("max amplitude", np.max(data))
print("standard deviation", np.std(data))

#get rid of the file transfered in from the S3 bucket
os.remove('test_1_s3.flac')


