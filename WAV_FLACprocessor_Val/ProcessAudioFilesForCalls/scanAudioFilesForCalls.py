#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import glob
from datetime import datetime
import time
import numpy as np
import searchForCalls as sff
import importlib
importlib.reload(sff)
"""

"""
#dirWAVs = "/home/val/WAVsTest"#"/media/val/021109_2341/"           # folder with wav files
dirWAVs = "/home/val/callDetection/WAVs"
dirFLACs = "/home/val/callDetection/FLACs"   # folder with flac files

dirOutput = "/home/val/callDetection/Calls"   # folder where output is placed

if dirWAVs.split('/') != '':   #Make sure directory has a final /
    dirWAVs += "/"
if dirFLACs.split('/') != '':   #Make sure directory has a final /
    dirFLACs += "/"
    
if dirOutput.split('/') != '':   #Make sure directory has a final /
    dirOutput += "/"
    
theWAVs = glob.glob(dirWAVs+"*.wav")
theWAVs = theWAVs + glob.glob(dirWAVs+"*.WAV")
theFLACs =  glob.glob(dirFLACs+"*.flac")
print(dirFLACs,"    ",theFLACs)
theFLACs =  theFLACs + glob.glob(dirFLACs+"*.FLAC")
print("num wavs",len(theWAVs), "num flacs", len(theFLACs))

theSoundFiles = theWAVs + theFLACs



timeNow = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
outputFile = dirOutput + 'callList_'+timeNow+'.txt'
callOutput = open(outputFile, 'w')  
callOutput.write("filename\tstartidx\tstopidx\tlencall\tf0\tsigma_f0\tpeak\tsigma_peak\n")  
cnt = 0
start = time.time()
for snd in theSoundFiles:
    print("processing file",snd)
    sff.searchForCalls(snd, callOutput, dirOutput)
    cnt += 1
#    if cnt == 3:
#        break

stop = time.time()    
print("Processed ", cnt, " WAV files in", np.round(stop-start), " seconds.")
callOutput.close()