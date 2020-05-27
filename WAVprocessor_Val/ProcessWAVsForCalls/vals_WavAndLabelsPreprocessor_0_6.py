#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio file processor (wav or mp3 files) creating compressed spectrograms
Version 0.5
May 27, 2020ArithmeticErrorNow includes extracting background samples between the expert annotations

@author: val
"""
import os

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

from datetime import datetime
from scipy.signal import welch

import soundfile as sf
import pydub   #  this is just to be able to read mp3 files
import pickle

import sys

###########################   User paths and parameters ##########################################
#### Directory where the wav files are stored
wavFileDirectory = "/home/val/Documents/machineLearning/Round3_OS_09_27_2017/wav/"

#### Label file
labelFilename = "/home/val/Documents/machineLearning/Round3_OS_09_27_2017/train.tsv"

#### Directory where the pickled spectrograms and associated metadata will be stored
pklDirectory = "/home/val/Documents/machineLearning/NN_files/dataForNN/pklFiles/"  
#####################################################################################

###################### User set parameters
Nfft = 512
n_slices = 80
n_bands = 80
f_low = 400
f_high  = 10000
deltaT = 3        # number if seconds in a single spectrogram array
removeClicks = False
logFrequencyScale = False
showPlots = False
pauseAtEachPlot = True
thisExpertClass = "KW"   # this should be pulled out of the Expert's labels so it can change from array to array

getBackgrounds = True
######################  End user parameters



def get_psd_values(y_values, f_s, wavPtr):
  global Nfft
  f_values, psd_values = welch(y_values, fs=f_s, nfft=Nfft, scaling = 'spectrum')
  if len(psd_values)< Nfft/2:
      print("length psd", len(psd_values),"len(y_values)", len(y_values), "Nfft", Nfft )
      input("psd_values not available ... waiting")
  return f_values, psd_values

# scipy.signal.welch(x, fs=1.0, window='hann', nperseg=None, noverlap=None, nfft=None, 
#    detrend='constant', return_onesided=True, scaling='density', axis=-1, average='mean')

def integrateIntoBand(f_bandIdx,idx, psd_slice):
  pwr = 1.0e-20
  idx1 = round(f_bandIdx[idx])
  idx2 = round(f_bandIdx[idx+1])
  for i in range(idx1, idx2):
    if i < len(psd_slice):
      pwr += psd_slice[i]
  #print(idx, f_bands[idx], f_bandIdx[idx], "pwr=", pwr)    
  return pwr  #returns the total power in band idx for this slice's multiple psd_values

def setupBands(wavData, nPsdPts, sampleRate):
  global  n_bands, f_low, f_high, n_slices, deltaT
  global f_bands, f_bandIdx, f_values, Nfft
  if DEBUG == 2:
    print("Starting to setup bands.")
  data4Psd = wavData[0:5000]

  f_values, psd_values = get_psd_values(data4Psd, sampleRate, 0)   # N.B. this psd call is to get the f_values array
  if DEBUG == 2:
    print("N of freq values=",len(f_values),"sampleRate=",sampleRate)
  if f_values[-1] < f_high:
    f_high = f_values[-1]     #  reduce the upper freq limit is sampling rate is too low
  f_bands = np.zeros(n_bands+1)
  f_bandIdx = np.zeros(n_bands+1, dtype=int)
  pwrIdx = 0
  minDfBand = pow(f_low,(1-1/n_bands))*pow(f_high,1/n_bands) - 1
  if f_values[1] - f_values[0] > minDfBand:
    print("There are too many bands or too fft window of %d points is too small or \nlower frequency limit %d is too low" % (Nfft, f_low))
    print("Nfft=",Nfft,"df=",f_values[1] - f_values[0],"f_low=",f_low,"f_high=",f_high,"minDfBand value is",minDfBand)
    sys.exit()
  for i in range(n_bands+1):
    f_bands[i] = pow(f_low,(1-i/n_bands))*pow(f_high,i/n_bands)
    while f_values[pwrIdx] < f_bands[i]:
##      print(i, pwrIdx, f_values[pwrIdx] , f_bands[i])
      pwrIdx += 1
    f_bandIdx[i] = pwrIdx
    i = i
  if DEBUG == 2:      
    print("Frequency bands have been calculated")  
    for i in range(n_bands+1):
      print(f_bands[i],f_bandIdx[i])
  return f_bands, f_bandIdx, f_values


def pydubRead(f, normalized=False):
    """MP3 to numpy array"""
    a = pydub.AudioSegment.from_mp3(f)
    y = np.array(a.get_array_of_samples())
    if a.channels == 2:
        y = y.reshape((-1, 2))
    if normalized:
        return np.float32(y) / 2**15 , a.frame_rate
    else:
        return  y, a.frame_rate

def compressArray(inAry,outAry, putInBands): # inAry must be equal to or larger than outAry
  global  n_bands, f_low, f_high, n_slices, deltaT
  global f_bands, f_bandIdx, f_values, Nfft, centerWeight  
  inRows = inAry.shape[0]
  inCols = inAry.shape[1]
  outRows = outAry.shape[0]
  outCols = outAry.shape[1]
  if DEBUG == 1: print("putintobands ",putInBands, inRows, inCols,outRows,outCols)
  if inRows < outRows or inCols < outCols:
    print("compressArray ERROR input rows and cols can't be less than output rows and cols")
    return None
  for i in range(outRows):
    for j in range(outCols):
      outAry[i][j] = 0  # clear the outAry element
      if putInBands:
        i1In = f_bandIdx[i]
        i2In = min(f_bandIdx[i+1], inRows-1)        
      else:
        i1In = int(i*inRows/outRows)
        i2In = int((i+1)*inRows/outRows)
      j1In = int(j*inCols/outCols)
      j2In = int((j+1)*inCols/outCols)
      for ii in range(i1In,i2In):
        for jj in range(j1In, j2In):
          outAry[i][j] += inAry[ii][jj]
        if j2In-j1In >0:
          outAry[i][j] /= j2In-j1In  ## average the added psw to avoid integer divides issues with indices 
  
  if DEBUG == 1: print("compress array: max min",putInBands,np.max(outAry),np.min(outAry))        
  return outAry

def normalize(pwr):
  if np.max(pwr) == np.min(pwr):
    return pwr
  pwr = (pwr - np.min(pwr)) / (np.max(pwr) - np.min(pwr))+0.01
  return pwr

def getNextArray_new(sampleRate, wavData, wavPtr, nPsdPts, nWavPts4ary):
  global  n_bands, f_low, f_high, n_slices, deltaT
  global f_bands, f_bandIdx, f_values, Nfft, centerWeight
  
  df = sampleRate/Nfft
  NrawF = int(round((f_high - f_low) / df))   # should be the number of freq bins in range returned from psd calculation
  NrawT = n_slices * 10   #These are # of time slices for RAW psd -   
                          # this 10 is pretty arbitrary -- must be at least 2, I think ???
  rawPsd  = np.zeros((NrawF,NrawT))
  sliceStep = nWavPts4ary // NrawT    # step through samples in groups that fit NrawT slices into spectrogram array time (deltaT)
  sampleStep = int(max(1.25*Nfft, sliceStep))
  if DEBUG == 1: print("Nfhttps://github.com/orcasound/orcadata/tree/master/WAVprocessor_Val/ProcessWAVsForCallsft=",Nfft,"sliceStep=",sliceStep, "num of slices", NrawT, "sampleStep",sampleStep, "wavPtr",wavPtr)
  for j in range(NrawT):
    wavPtrMax = int(min(wavData.shape[0]-1, wavPtr + sampleStep) ) ## keep from running off end of wav file
    if DEBUG == 1:
      if wavPtr + sampleStep > wavData.shape[0]:
        print(j,wavPtr,wavPtr+sampleStep, wavData.shape[0], wavPtrMax, NrawT, sampleStep)
        print("-- we have run over the end of the wav data")
    if wavPtrMax - wavPtr < Nfft:
      print("----------------------  breaking because we have fewer than Nfft samples to send to fft")
      break                        #  We have run out of samples in this wav file so exit loop    Note Bene  Check if this works properly
    psdSlice = wavData[wavPtr : wavPtrMax]
    if wavPtr < 0:
      print("wavPtrs",wavPtr,wavPtrMax)
      input("neg wavPtr")
    f_values, psd_values = get_psd_values(psdSlice, sampleRate, wavPtr)  # psd of this time slice
    
    if j == 0:  # Only need to calc these freq range indices the first time
      idx = 0
      while f_values[idx] < f_low:
        idx += 1
      iStart = idx
      while f_values[idx] < f_high:  
        idx += 1
      if f_values[idx] == f_high:  # -1 to prevent over run if f_high == sampleRate/2
        idx -= 1
      iStop = idx
      if DEBUG == 1: print("freq range is",f_low,"->",f_high,"n pts=",iStop-iStart, "rawPsd shape",rawPsd.shape)
    for i in range(iStart,iStop-1):                         #############  ???? why did I need this -1 here ????
      if i-iStart > rawPsd.shape[0] or i > len(psd_values):
        if DEBUG == 1: ("i=",i, "i-iStart",i-iStart,"iStart",iStart,"j",j)

      rawPsd[i-iStart][j] = psd_values[i]  #save psd values for desired freq range
    
    wavPtr += sliceStep

  ####################################plot the raw Psd in selected f and t ranges
  normPsd = normalize(rawPsd) # normalize to 0 -> 1
  normPsdDb = normalize(10*np.log10(normPsd))
  
  compressedPsd = np.zeros((n_bands,n_slices))
  compressedPsd = compressArray(normPsd, compressedPsd, False)#returns the total power in band idx for this slice's multiple psd_values
  
  normCompressedPsd = normalize(compressedPsd)
  normCompressedDb = np.sqrt(np.sqrt(normalize(10*np.log10(normCompressedPsd))))  ##############  Note Bene   Note Bene  double square root to flatten for plotting !!!!! ??????????????????
    
  bandedPsd  = np.zeros((n_bands,n_slices))

  bandedPsd = compressArray(normPsd, bandedPsd, True)  # True says integrate into bands
  normBandedDb = np.square(normalize(10*np.log10(normalize(bandedPsd))))
  return normPsdDb, normCompressedDb, normBandedDb   # fhigh may have been changed if samplerate is too low
#  return normPsdDb, compressedPsd, bandedPsd


#################################################################################################
def findNextPeak(y,idx,direction):   # peak detector used in click removal
  # scann forward (direction=1) or backward (direction=-1) for next peak
  gotPeak = False
  while not gotPeak:
    idx += direction
    if y[idx-1] < y[idx] and y[idx+1] < y[idx]:
      gotPeak = True
  return idx, y[idx]   

def doRemoveClicks(wavdata, filename, sampleRate):
  global DEBUG
  if DEBUG == 2:
    print("Starting to remove clicks.")
  nsd = 6   #################################   number of standard deviations to trigger reducing gain during clicks
  ave = np.mean(np.abs(wavdata))
  std = np.std(np.abs(wavdata))
  maxVal = np.max(wavdata)
  thresh = ave + std               # here we set the threshold for termining gain reduction after coming down from a high peak
  cnt = 0
  i=0
  while i < len(wavdata):
    if np.abs(wavdata[i]) > ave + nsd*std:
      cnt += 1
      #first step backwards looking at peaks in abs(wavdata) until N peaks are below a threshold
      iHighestPeak = i
      gotPeak = True
      ipeak = i
      while gotPeak:
        ipeak, y = findNextPeak(np.abs(wavdata), ipeak, -1)  # scan backwards
        if y < thresh:
          gotPeak = False
          iPrior = ipeak
      
      #now step forward looking for higher peaks and continuing until N peaks are below a threshold
      gotPeak = True
      ipeak = iHighestPeak
      yHighest = np.abs(wavdata[iHighestPeak])
      while gotPeak:
        ipeak, y = findNextPeak(np.abs(wavdata), ipeak, 1) # scan forwards
        if y > yHighest:
          iHighestPeak = ipeak
          yHighest = np.abs(wavdata[iHighestPeak])
        if y < thresh:
          gotPeak = False
          iPost = ipeak      
      #use linearly scaled gain to bring down the amplitude of this region
      for i in range(iPrior,iHighestPeak):
        pk = yHighest - (iHighestPeak - i)*(yHighest - thresh)/(iHighestPeak - iPrior)
        scaledData = wavdata[i]*thresh/pk
        
        wavdata[i] = scaledData
      for i in range(iHighestPeak,iPost):
        pk = yHighest - (iHighestPeak - i)*(yHighest - thresh)/(iPost - iHighestPeak)
        scaledData = wavdata[i]*thresh/pk
        
        wavdata[i] = scaledData


      i += iPost - iHighestPeak    # move index forward over (most of) post region
    i += 1
 
  print(cnt," clicks at ",nsd," sd have been removed", "ave", ave,"sd", std, "max", maxVal)

  return wavdata

def gotSignal(numGood, fracGood, minFrac, Ncontours, maxNcontours, maxArea, minMaxArea) :
  if numGood > 0 and fracGood > minFrac and Ncontours < maxNcontours and maxArea > minMaxArea:
    return True
  return False
def gotBackground(numGood, fracGood, backFrac, Ncontours, maxNcontours):
  if numGood >0 and fracGood < backFrac and Ncontours > maxNcontours:
    return True
  return False


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


def save_obj(obj, name ):
    print("in save_obj_",os.getcwd(),name)
    with open('obj/'+ name + '.pkl', 'wb') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

def load_obj(name ):
    print("Working directory is ",os.getcwd())
    with open('obj/' + name + '.pkl', 'rb') as f:
        return pickle.load(f)  
      
class acousticLabel(object):
  def __init__(self, filename, start, duration, loc, thisClass, Nfft, sampleRate, n_bands, n_slices, flow, fhigh, dt, rmclicks, logScale, thisDate):
    self.objectClass = thisClass
    self.wav_filename = filename
    self.Nfft = Nfft,
    self.sampleRate = sampleRate
    self.start_time_s = start
    self.duration_s = duration
    self.location = loc
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
    

##########################################################################################
def getSpectrogram(target, priorFile, theWavData):
  global nPsdPts, nWavPts4ary, deltaT, sampleRate, n_slices, n_bands, f_low, f_high, priorStartTime
  wavFile = target.wav_filename
  wavData = theWavData
  if wavFile != priorFile:
    print("Starting to read audio file: ",wavFile)
    priorStartTime = 0
    #################  Read audio file according to audio file type
    filetype = wavFile.split(".")[-1]
    if filetype == 'mp3':
      wavdata, sampleRate = pydubRead(wavFile) # pydub is needed for mp3 files
    else:  
      wavdata, sampleRate = sf.read(wavFile)   #  soundfile can read wav, ogg, flac audio formats !!!
    print("File is read.  sampleRate=",sampleRate)  
    
    ################  If file has more than one channel, use the first channel
    nChan = 1
    if len(wavdata.shape)>1:
      nChan =  wavdata.shape[1]
    if nChan == 1:
      wavData = np.array(wavdata)
    else:
      wavData = np.array(wavdata[:,0])  # extract just the first channel of audio data

    nWavPts4ary = deltaT * sampleRate   #  amount of wav used for one spectrogram data array
    nPsdPts = int(sampleRate * deltaT/n_slices)  # get number of wav data points in a single time slice
    print("Number of data points in audio file", len(wavData))
  
    #######  remove clicks if this is selected
    if removeClicks:
      wavData = doRemoveClicks(wavData,wavFile,sampleRate)
    nWavPts = len(wavData)    
  
    #######  if file is shorter than desired window, zero pad the file
    if nWavPts < nWavPts4ary:
      #  zero pad this short file
      shortWavData = wavData
      wavData = np.zeros(nWavPts4ary+1)
      j1 = nWavPts4ary//2 - nWavPts//2
      j2 = nWavPts4ary//2 + nWavPts//2
      for j in range(j1,j2):
        wavData[j] = shortWavData[j-j1]
  nWavPts = len(wavData)    
    
  ###### setup logarithmetic frequency bands psd index limits
  f_bands, f_bandIdx, f_values = setupBands(wavData, nPsdPts, sampleRate)  # f_bandIdx is array of index values into psd array freq boundaries
    
  wavPtrMidpoint = int((target.start_time_s + target.duration_s/2)* sampleRate)  ## center data arrays on midpoint expert's duration
  wavPtr = max(wavPtrMidpoint - nWavPts4ary//2, 0)   # Don't allow index to go negative
  
  if DEBUG == 1:
    print("..................file",wavFile,"Start time",target.start_time_s,"Start",wavPtr/sampleRate, "Stop",(wavPtr + nWavPts4ary)/sampleRate,"Stop time",target.start_time_s + target.duration_s)
    print("startSamples =", target.start_time_s*sampleRate, "windowStart = ", wavPtr, "Expert stop samples",(target.start_time_s + target.duration_s)*sampleRate, "windowStop", wavPtr+nWavPts4ary)

  normPsdDb, normCompressedDb, normBandedDb = getNextArray_new(sampleRate, wavData, wavPtr, nPsdPts, nWavPts4ary)
  
  if DEBUG == 1:
    print("wavPtr=", wavPtr, "normPsdDb stats",np.min(normPsdDb), np.mean(normPsdDb), np.median(normPsdDb),np.max(normPsdDb))
    print("normBandedDb stats       ",np.min(normBandedDb), np.mean(normBandedDb),np.median(normBandedDb),np.max(normBandedDb))

  if not logFrequencyScale:
    if removeClicks:
      specType= "{}: normCompressedDb - deClicked".format(target.objectClass)
      title = "{} \n{}\nNoted {:.1f},{:.1f}, Display {:.1f},{:.1f}".format(specType,wavFile,target.start_time_s, target.start_time_s+target.duration_s,wavPtr/sampleRate,(wavPtr + nWavPts4ary)/sampleRate)
    else:
      specType= "{}: normCompressedDb".format(target.objectClass)
      title = "{}\n{}\nNoted {:.1f},{:.1f}, Display {:.1f},{:.1f}".format(specType,wavFile,target.start_time_s, target.start_time_s+target.duration_s,wavPtr/sampleRate,(wavPtr + nWavPts4ary)/sampleRate)
  else:
    if removeClicks:
      specType= "{}: normBandedDb - deClicked".format(target.objectClass)
      title = "{} \n{}\nNoted {:.1f},{:.1f}, Display {:.1f},{:.1f}".format(specType,wavFile,target.start_time_s, target.start_time_s+target.duration_s,wavPtr/sampleRate,(wavPtr + nWavPts4ary)/sampleRate)
    else:
      specType= "{}: normBandedDb".format(target.objectClass)
      title = "{}\n{}\nNoted {:.1f},{:.1f}, Display {:.1f},{:.1f}".format(specType,wavFile,target.start_time_s, target.start_time_s+target.duration_s,wavPtr/sampleRate,(wavPtr + nWavPts4ary)/sampleRate)
    
  #setup signal label with specType and wav data start and stop indices
  signalLabel = target
  signalLabel.sampleRate = sampleRate
  signalLabel.spectrogramType = specType
  signalLabel.window_start_idx = wavPtr
  signalLabel.window_stop_idx  = wavPtr + nWavPts4ary
  
  if DEBUG == 1: print("set up signal label:",signalLabel.window_start_idx,signalLabel.window_stop_idx)
  if showPlots:
    plotArray(title, normCompressedDb)
    
  if not logFrequencyScale:
    return wavData, normCompressedDb, signalLabel
  else:
    return wavData, normBandedDb, signalLabel

#######################################################################################
##############  EXECUTION STARTS HERE ################################################

DEBUG = 0

nWavPts4ary = 0
nPsdPts = 0
expertLabelList = []
rightNow = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
with open(labelFilename) as elf:
  for cnt, line in enumerate(elf):
    if cnt == 0:
      print("Label file header line = ",line)
    if cnt>0:  # skip header line
      items = line.split(",")
      if items[2] != '0':  # skip any experts' record which has a duration_s value = ZERO
                                         #  filename,    start,      duration,        loc,      thisClass,   Nfft, sampleRate, n_bands, n_slices, flow, fhigh, dt, rmclicks, logScale, thisDate)        
        expertLabelList.append(acousticLabel(items[0],float(items[1]),float(items[2]),items[3], thisExpertClass,Nfft, 0, n_bands, n_slices, f_low, f_high, deltaT, removeClicks, logFrequencyScale,rightNow))
print("number of labels =",cnt)  

backgroundLabelList = []

for cnt, lbl in enumerate(expertLabelList):  # build list of background intervals between expert labels
  if cnt ==0:
    lblPrior = lbl  # initialize
  else:
    bgStart_s = lblPrior.start_time_s + lblPrior.start_time_s + lblPrior.duration_s + deltaT  # start at one window width after prior expert notation
    bgStop_s  = lbl.start_time_s - deltaT    # stop one window width before next notation
    if bgStop_s - bgStart_s > deltaT:
      if cnt< 10:
        print("background start stop",bgStart_s, bgStop_s)
      bgLbl = lbl    # initialize background label to expert lable
      bgLbl.start_time_s = (bgStop_s + bgStart_s)/2 - deltaT/2    # put background midway between expert notations
      bgLbl.duration_s   = deltaT
      bgLbl.objectClass = 'Background'
      backgroundLabelList.append(bgLbl)
      
  


###############################################################
spectrogramArrayList = []
spectrogramLabelList = []

os.chdir(wavFileDirectory)
print("Working directory is set for audio files ",os.getcwd())
thisFilename = ""
thisWavData = ""

for cnt, exLabel in enumerate(backgroundLabelList):   ##########  Main processing loop ####################################
  thisWavData, theSignal, signalLabel = getSpectrogram(exLabel,thisFilename, thisWavData) 
  thisFilename = exLabel.wav_filename
  spectrogramArrayList.append(theSignal)
  spectrogramLabelList.append(signalLabel)
  print("theSignal start stop",exLabel.objectClass,exLabel.start_time_s, exLabel.duration_s, exLabel.window_start_idx/exLabel.sampleRate, exLabel.window_stop_idx/exLabel.sampleRate)
  if showPlots and pauseAtEachPlot:
    inkey = input("Tap <Enter> to continue or q and <Enter> to quit  ")
    if inkey == 'q' or inkey == 'Q':
      break
    
  if DEBUG == 1 and cnt == 10:     ######################################  jump out of loop for debugging
    break

for cnt, exLabel in enumerate(expertLabelList):   ##########  Main processing loop ####################################
  
  thisWavData, theSignal, signalLabel = getSpectrogram(exLabel,thisFilename, thisWavData) 
  thisFilename = exLabel.wav_filename
  spectrogramArrayList.append(theSignal)
  spectrogramLabelList.append(signalLabel)

  if showPlots and pauseAtEachPlot:
    inkey = input("Tap <Enter> to continue or q and <Enter> to quit  ")
    if inkey == 'q' or inkey == 'Q':
      break
    
  if DEBUG == 1 and cnt == 10:     ######################################  jump out of loop for debugging
    break
  
if DEBUG == 1: 
  print("list start and stop signal file indices")
  for cnt, sig in enumerate(spectrogramLabelList):
    print(sig.wav_filename,sig.window_start_idx, sig.window_stop_idx)
  
os.chdir(pklDirectory) 
loc = wavFileDirectory.split('/')[-2]
if not logFrequencyScale:
  save_obj(spectrogramArrayList, "spectrogramArrayList_%dx%d_%dto%d_%0.1fsec" % (n_bands,n_slices,f_low,f_high,deltaT))
  save_obj(spectrogramLabelList, "spectrogramLabelList_%dx%d_%dto%d_%0.1fsec" % (n_bands,n_slices,f_low,f_high,deltaT))
else:
  save_obj(spectrogramArrayList, "spectrogramArrayList_%dx%d_%dto%d_%0.1fsec_logF" % (n_bands,n_slices,f_low,f_high,deltaT))
  save_obj(spectrogramLabelList, "spectrogramLabelList_%dx%d_%dto%d_%0.1fsec_logF" % (n_bands,n_slices,f_low,f_high,deltaT))  

print("Number of events: signals",len(spectrogramArrayList))
