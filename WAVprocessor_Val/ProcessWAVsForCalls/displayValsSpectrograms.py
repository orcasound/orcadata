#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 20 08:38:29 2020

@author: val
"""
import os

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import pickle


#### Directory where the pickled spectrograms and associated metadata will be stored
pklDirectory = "/home/val/Documents/machineLearning/NN_files/dataForNN/pklFiles/"  

def save_obj(obj, name ):
    print("in save_obj_",os.getcwd(),name)
    with open('obj/'+ name + '.pkl', 'wb') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

def load_obj(name ):
    print("Working directory is ",os.getcwd())
    with open('obj/' + name + '.pkl', 'rb') as f:
        return pickle.load(f)  
      
class acousticLabel(object):
  def __init__(self, fileline, thisClass,Nfft, sampleRate, n_bands, n_slices, flow, fhigh, dt, rmclicks, logScale, thisDate):
    if '\t' in fileline:
      items = fileline.split("\t")
    items = fileline.split(",")  
    self.objectClass = thisClass
    self.wav_filename = items[0]
    self.Nfft = Nfft,
    self.sampleRate = sampleRate
    self.start_time_s = float(items[1])
    self.duration_s = float(items[2])
    self.location = items[3]
    self.window_start_idx = 0
    self.window_stop_idx = 0
    self.spectrogramType = ""
    self.n_bands = n_bands
    self.n_slices = n_slices
    self.f_low = flow
    self.f_high = fhigh
    self.deltaT = dt
    self.logFrequencyScale = logScale
    self.removeClicks = rmclicks
    self.processingDate = thisDate
   
    

def plotArray(theTitle, z):
  global n_bands, n_slices
  y, x = np.mgrid[slice(1, n_bands + 1, 1),
                slice(1, n_slices + 1, 1)]
  z = z[:-1, :-1]
  
  # ##opening figure and axes
  fig,ax = plt.subplots()

  matplotlib.pyplot.imshow(z,origin='lower')
  ax.set_title(theTitle)    
  
  plt.show() 

####################################### EXECUTION STARTS HERE ######################
    
os.chdir(pklDirectory) 
    
signalArrayList = load_obj("spectrogramArrayList_80x80_400to10000_3.0sec")  # Note: don't include the .pkl in the file name
signalLabelList = load_obj("spectrogramLabelList_80x80_400to10000_3.0sec")  

n_bands = 80
n_slices = 80

for i in range(len(signalArrayList)):
  signal = signalArrayList[i]
  label  = signalLabelList[i]

  exStop = label.start_time_s + label.duration_s
  winStart = label.window_start_idx / label.sampleRate
  winStop =  label.window_stop_idx / label.sampleRate
  title = "%s\n%s\nExpert %0.1f,%0.1f Display %0.1f,%0.1f" % (label.wav_filename, label.spectrogramType,label.start_time_s, exStop, winStart, winStop)
  plotArray(title,signal)
  key = input("<Enter> to continue, q<Enter> to quit")
  if key == 'q' or key == 'Q':
    break
