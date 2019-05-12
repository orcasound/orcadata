#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import glob
from datetime import datetime
import time
import numpy as np
import searchForCalls as sff
import importlib
importlib.reload(sff)
import argparse
"""
Command line:
 ./scanAudioFilesForCalls.py -i /home/val/callDetection/FLACs -o /home/val/callDetection/Calls

"""
#dirWAVs = "/home/val/WAVsTest"#"/media/val/021109_2341/"           # folder with wav files
#dirWAVs = "/home/val/callDetection/WAVs"
dirFLACs = "/home/val/callDetection/FLACs"   # folder with flac files#


#dirOutput = "/home/val/callDetection/Calls"   # folder where output is placed

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

if dirAudio.split('/') != '':   #Make sure directory has a final /
    dirAudio += "/"
if dirOutput.split('/') != '':   #Make sure directory has a final /
    dirOutput += "/"

    
theWAVs = glob.glob(dirAudio+"*.wav")
theWAVs = theWAVs + glob.glob(dirAudio+"*.WAV")
theFLACs =  glob.glob(dirAudio+"*.flac")
print(dirFLACs,"    ",theFLACs)
theFLACs =  theFLACs + glob.glob(dirAudio+"*.FLAC")
print("num wavs",len(theWAVs), "num flacs", len(theFLACs))

theSoundFiles = theWAVs + theFLACs

timeNow = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
outputFile = dirOutput + 'callList_'+ dirAudio.replace('/','_') +"_"+ timeNow+'.txt'
callOutput = open(outputFile, 'w')  
callOutput.write("filename\tstartidx\tstopidx\tlencall\tf0\tsigma_f0\tmean_peak\tsigma_peak\n")  

cnt = 0
start = time.time()
for snd in theSoundFiles:
    print("processing file",snd)
    sff.searchFileForCalls(snd, callOutput, dirOutput)
    cnt += 1
#    if cnt == 3:
#        break

stop = time.time()    
print("Processed ", cnt, " Audio files in", np.round(stop-start), " seconds.")
callOutput.close()
