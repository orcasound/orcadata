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
dirWAVs = "/Users/scott/Dropbox/Sounds/SRKW-train-data"           # folder with wav files
dirOutput = "/Users/scott/Dropbox/Sounds/SRKW-train-data/labels-Vveirs"   # folder where output is placed

if dirWAVs.split('/') != '':   #Make sure directory has a final /
    dirWAVs += "/"
if dirOutput.split('/') != '':   #Make sure directory has a final /
    dirOutput += "/"
    
theWAVs = glob.glob(dirWAVs+"*.wav")
theWAVs = theWAVs + glob.glob(dirWAVs+"*.WAV")

print("num wavs",len(theWAVs))
print("in dir", dirWAVs)
print("in dir", dirOutput)
 


timeNow = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
outputFile = dirOutput + 'callList_'+timeNow+'.txt'
callOutput = open(outputFile, 'w')  
callOutput.write("fileName\tstartidx\tstopidx\tlencall\tf0\tsigma_f0\tpeak\tsigma_peak\n")  
cnt = 0
start = time.time()
for wav in theWAVs:
    sff.searchForCalls(wav,callOutput, dirOutput)
    cnt += 1
#    if cnt == 3:
#        break
stop = time.time()    
print("Processed ", cnt, " WAV files in", np.round(stop-start), " seconds.")
callOutput.close()
