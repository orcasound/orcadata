#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import glob
from datetime import datetime
import time
import numpy as np
import searchFileForCalls as sff
import importlib
importlib.reload(sff)
import argparse
import os

"""
Command line:
 ./scanAudioFilesForCalls.py -i /home/val/callDetection/FLACs -o /home/val/callDetection/Calls
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
parser.add_argument('-i', '--input_audiopath', type=str,
                    help='path to input audio files')

args = parser.parse_args()

dirAudio = args.input_audiopath
dirOutput = args.output_logpath
theWAVs = glob.glob(os.path.join(dirAudio,"*.wav"))
theFLACs = glob.glob(os.path.join(dirAudio,"*.flac"))

print("num wavs",len(theWAVs), "num flacs", len(theFLACs))

theSoundFiles = theWAVs + theFLACs
timeNow = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')

os.makedirs(dirOutput,exist_ok=True)
audio_fname = os.path.basename(dirAudio)

outputFile = os.path.join(dirOutput,'_'.join(['callList',audio_fname,timeNow+'.txt']))
callOutput = open(outputFile, 'w')
callOutput.write("filename\tstartidx\tstopidx\tlencall\tf0\tsigma_f0\tmean_peak\tsigma_peak\n")

cnt = 0
start = time.time()
for snd in theSoundFiles:
    print("processing file",os.path.basename(snd))
    sff.searchFileForCalls(snd, callOutput, dirOutput)
    cnt += 1
#    if cnt == 3:
#        break

stop = time.time()
print("Processed ", cnt, " Audio files in", np.round(stop-start), " seconds.")
callOutput.close()
