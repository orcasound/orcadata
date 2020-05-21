#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 21 09:08:23 2020

Read mono wav file
Read expert labeling
Create stereo channel with expert time intervals
Save as stereo file

@author: val
"""

import os

import numpy as np

import soundfile as sf

###########################   User paths and parameters ##########################################
#### Directory where the wav files are stored
wavFileDirectory = "/home/val/Documents/machineLearning/Round3_OS_09_27_2017/wav/"

#### Label file
labelFilename = "/home/val/Documents/machineLearning/Round3_OS_09_27_2017/train.tsv"

#### Directory where the data will be stored as annotated wav files
outputDirectory = "/home/val/Documents/machineLearning/NN_files/dataForNN/stereoAnnotations/"  

#####################################################################################
### Program reads the expert's label file (here a .tsv file)
### Loads the wav data
### Constructs a channel of audio data to hold the annotation info
### Puts low ampltude sin wave in the time intervals specified by the expert
### Constructs stereo data structure with wav data (left) and annotations (right)
### Stereo file is written to specified directory
#####################################################################################

expertLabelList = []
os.chdir(wavFileDirectory)
print("Working directory is set for audio INPUT files ",os.getcwd())

with open(labelFilename) as elf:
  for cnt, line in enumerate(elf):
    if cnt == 0:
      print("Label file header line = ",line)
    if cnt>0:  # skip header line
      items = line.split(",")
      if items[2] != '0':  # skip any experts' record which has a duration_s value = ZERO
        expertLabelList.append([items[0],float(items[1]),float(items[2])]) 
        
print("number of labels =",cnt)  
print("List a few labels for reference:")
for i in range(6):
  print(i, expertLabelList[i])
  
priorWavFile = ""
for i in range(len(expertLabelList)):
  expertRecord = expertLabelList[i]   # each list element looks like this: ['OS_9_27_2017_08_09_00__0002.wav', 11.6970486111111, 0.978298611111111]
  wavFile = expertRecord[0]
  items = wavFile.split(".")

  fileSufix = int(items[0].split("_")[-1])
  startTime = float(expertRecord[1])
  duration  = float(expertRecord[2])
  print("----------------------- wavFile= %s Start= %0.1f Stop= %0.1f" % (wavFile, startTime, duration))

  if wavFile != priorWavFile:
    if priorWavFile != "":  #We have finished with a wav file
      # write out stereo file now
      print("writing file")
      while expertIdx < len(expertdata):
        expertdata[expertIdx] = 0  # no annotation here
        expertIdx += 1
      stereodata = []
      for i in range(len(expertdata)):
        dat = np.array([wavdata[i],expertdata[i]])
        stereodata.append(dat)  # Note this is a python list NOT a numpy array
      stereodata = np.asarray(stereodata)
      sf.write(outputDirectory+priorWavFile+"Annotated.wav", stereodata, sampleRate)

#      input("wait...")
      
    wavdata, sampleRate = sf.read(wavFile)   # read next wav file
#    print("sampleRate", sampleRate)
    priorWavFile = wavFile
    expertdata = np.zeros(len(wavdata))    # set up the second channel with the same size as the wavdata
    expertIdx = 0
  #  run along the expertdata p to index of startTime+duration, usetting everything to -1 except when expert noted a signal
  startIdx = int(startTime * sampleRate)
  stopIdx  = int((startTime + duration) * sampleRate)
  while expertIdx < startIdx:
    expertdata[expertIdx] = 0 # no annotation here
    expertIdx += 1
  while(expertIdx < stopIdx):
    expertdata[expertIdx] = 0.01*np.sin(expertIdx*2*3.1416*5000/sampleRate)    # expert annotation here - low amp so it does not sound terrible
    expertIdx += 1    
