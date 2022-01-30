#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import boto3
import os

from datetime import datetime
import time
import numpy as np
from processFileForCalls_AWS import processFileForCalls
import importlib

import argparse
"""
Command line:
 ./scanAWSAudioFilesForCalls.py -b dev-archive-orcasound-net -i val_test -o Calls
       # don't forget to
            run this program from its directory
            have setup Calls directory inside this directory
"""

def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('-o', '--output_logpath', type=str,
                    help='path to output log file ')
parser.add_argument('-b', '--s3bucket', type=str)
parser.add_argument('-i', '--input_audiopath', type=str,
                    help='path to input audio files in S3 bucket')
args = parser.parse_args()
s3bucket = args.s3bucket
dirAudio = args.input_audiopath
dirOutput = args.output_logpath


if dirAudio.split('/') != '':   #Make sure directory has a final /
    dirAudio += "/"

s3client = boto3.client('s3')
#check for empty case here
audioFiles = s3client.list_objects(Bucket=s3bucket, Prefix=dirAudio)['Contents']
filedir = audioFiles[0]['Key']
inputFiles = []    #setup audio file names from s3 bucket
for i in range(1,len(audioFiles)):  #file names start at index = 1
    nextFile = audioFiles[i]['Key']
    if len(nextFile.split('.')) == 2:
        fileType = nextFile.split('.')[1]
        if fileType == 'wav' or fileType == 'WAV' or fileType == 'flac' or fileType == 'FLAC':
            inputFiles.append(audioFiles[i]['Key'])


timeNow = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')

if not os.path.exists(dirOutput):
    os.mkdir(dirOutput)

outputFile = os.path.join(dirOutput,'callList_'+ dirAudio.replace('/','_') +"_"+ timeNow+'.txt')

callOutput = open(outputFile, 'w')
callOutput.write("filename\tstartidx\tstopidx\tlencall\tf0\tsigma_f0\tmean_peak\tsigma_peak\n")


cnt = 0
start = time.time()
for snd in inputFiles:
    print("processing file",snd)
    # go over to S3 bucket and grap a flac file
    s3client.download_file(s3bucket, snd, 'working.flac')
    processFileForCalls('working.flac', snd, callOutput)
    os.remove('working.flac')
    cnt += 1
#    if cnt == 3:
#        break

stop = time.time()
print("Processed ", cnt, " Audio files in", np.round(stop-start), " seconds.")
callOutput.close()

