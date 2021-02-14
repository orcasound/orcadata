#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May  7 09:28:01 2019

    flac files: To load soundfile first:  conda install -c conda-forge pysoundfile
@author: val
"""
import numpy as np
import os
import soundfile as sf
from scipy.fftpack import fft, ifft, rfft
from scipy.signal import  hann, find_peaks, peak_widths, peak_prominences
from scipy import signal
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter, detrend


safediv = lambda x,y : x if y == 0 else x/y

def updateBackground(psd):
    global backgroundPSD
    global backgroundMean
    global backgroundSigma
    global backgroundPeak
    backgroundPSD = 0.99*backgroundPSD + 0.01*psd
    backgroundPSD[0:25:1] = 0
    backgroundMean = np.mean(backgroundPSD)
    backgroundSigma = np.std(backgroundPSD)
    backgroundPeak = np.max(backgroundPSD)

def getSmoothedPSD(idx1, idx2):
    global ampData
    y = ampData[idx1:idx2]
    f, Pxx_den = signal.welch(y, sampleRate, nperseg=1024)
    Pxx_denX = detrend(savgol_filter(Pxx_den, 11,3) ) #smoother
    Pxx_denX = savgol_filter(Pxx_denX, 11,3)          #TWO SMOOTHING PASSES
#    plt.figure()
#    plt.plot(f, Pxx_den)
#    plt.plot(f, Pxx_denX,color='red')
#    plt.xlabel('frequency [Hz]')
#    plt.ylabel('PSD spectrum')
#    plt.show()
    return f, Pxx_den


def getDeltaf_PeakStats(y):
    global f

#    print("llllllllllllllllll",len(y),np.mean(y),np.std(y), np.max(y))
    peaksIds, _ = signal.find_peaks(y, height=[np.std(y),None])
    compressedIds = []
    if DEBUG == 2:
        print("----------len(y)",len(y), "len(peaksIds)",len(peaksIds),f[peaksIds])
    if len(peaksIds) == 1:
        compressedIds.append(peaksIds[0])   # this puts in single peak
    deltas = []
    for i in range(len(peaksIds)-1):   # run over the peaks and calculate deltas etc.
        if DEBUG == 2:
            print("i=",i,"len peaksIds=",len(peaksIds))
        delta = f[peaksIds[i+1]] - f[peaksIds[i]]
        if DEBUG == 2:
            print("i delta",i,delta)

        if delta > 100:
            if len(deltas) == 0:
                deltas.append(delta)
                compressedIds.append(peaksIds[i])
                compressedIds.append(peaksIds[i+1])
            else:
                if DEBUG == 2:
                    print("deltas=",deltas)
                    print("last and new",deltas[-1],"delta=",delta)
                    print(i,len(f),len(peaksIds))
                    print(f[peaksIds[i+1]] , f[peaksIds[i]])

                deltas.append(delta)
                compressedIds.append(peaksIds[i+1])

    if DEBUG == 2:
        print("deltas",deltas)
        print("compressedIds",compressedIds)
    deltasMean = 0
    deltasStd  = 0
    if len(deltas) > 0:
         deltasMean = np.mean(deltas)
         deltasStd  = np.std(deltas)
    return len(compressedIds),deltasMean,deltasStd,compressedIds


def searchFileForCalls(thisAudioFile, callOutput, dirOutput):
    global ampData
    global sampleRate
    global backgroundPSD
    global f
    global DEBUG

    DEBUG = 0

    Nsamples = 4096   #  anylize data in Nsamples chunks of 256 size fft groups (averages lots of noise out!)
    outFileName = os.path.splitext(os.path.basename(thisAudioFile))[0]   # save base WAV filename for outputs
#  Read in WAV or FLAC data

    audioData, sampleRate = sf.read(thisAudioFile)

    ampData = []

    if len(audioData.shape) > 1:
        nChannels = audioData.shape[1]
        ampData = audioData[:,0]  # select channel 0 (left or mono)
    else:
        nChannels = 1
        ampData = audioData
    meanAmpData = np.mean(np.fabs(ampData))
    stdAmpData = np.std(np.fabs(ampData))
    if DEBUG > 1:
        print("processing",thisAudioFile)
        print("Sample rate",sampleRate)
        print("shape",audioData.shape)
        print("meanAmp",meanAmpData,"stdDev",stdAmpData)

#initialize background PSD    Note Bene this could be done in a way to insure not using a possible call
    f, backgroundPSD = getSmoothedPSD(5000, 10000)
    backgroundPSD[1:25:1] = 0
    backgroundMean = np.mean(backgroundPSD)
    backgroundSigma = np.std(backgroundPSD)
    backgroundPeak = np.max(backgroundPSD)
    if DEBUG == 2:
        print("back Peak Mean Sigma",backgroundPeak, backgroundMean, backgroundSigma, "f High pass",f[25])

    idx = 0

#loop through the wav file
    cnt = 0

    callPeaks = []
    callF0s = []

    xplot = []
    yNpeaks = []
    ycallLen = []
    ycallPeak = []
    done = False
    callStartIdx = 0
    gotCall = False   # this flag will start a call when Npeaks > 0 and stop the call when Npeaks = 0,
    while not done:   #               then writing the start and stop indices to disk for this all
        if DEBUG > 1:
            print("idx is", idx,'of',len(ampData))
        f,psdraw = getSmoothedPSD(idx,idx+Nsamples)
        psd = psdraw - backgroundPSD
        psd[0:25:1] = 0
        psd[psd < backgroundMean + 4*backgroundSigma] = 0

        N_peaks, deltaf_PeakMean, deltaf_PeakStd, peaksIds = getDeltaf_PeakStats(psd)
        if DEBUG > 1:
            print("Npeaks =", N_peaks)
        ratio = 0
        if deltaf_PeakStd > 0:
            ratio = deltaf_PeakMean/deltaf_PeakStd
        if DEBUG == 1:
            print(idx, "N_peaks=",N_peaks, ratio, gotCall, deltaf_PeakMean, callStartIdx,"....................")
        if N_peaks > 0:
            if not gotCall:
                gotCall = True
                callStartIdx = idx
                callPeaks.clear()
                callF0s.clear()
            #print("idx=",idx,"N_peaks", N_peaks, "delta f=", deltaf_PeakMean, deltaf_PeakStd, "RATIO",ratio)
            #print(f[peaksIds])
            if DEBUG >0:
                plt.plot(f,psd,color="blue")
                plt.xlim([0,8000])
                plt.show()
        if gotCall and N_peaks >0:
            #print('gotCall and max psd is',10*np.log10(np.max(psd[peaksIds])))
            callPeaks.append(np.max(psd[peaksIds]))
            callF0s.append(deltaf_PeakMean)
        if gotCall and N_peaks == 0:
            if DEBUG == 1:
                print("=================Write to file",callStartIdx,idx,idx-callStartIdx)
            stdCallPeaks = 0
            if len(callPeaks) > 1:
                stdCallPeaks = 10*np.log10(np.std(callPeaks))
            callOutput.write("%s\t%s\t%s\t%s\t%d\t%d\t%d\t%d\n" % (outFileName,callStartIdx,idx,
                  idx-callStartIdx, np.mean(callF0s), np.std(callF0s),
                  10*np.log10(np.mean(callPeaks)), stdCallPeaks))
            gotCall = False
            ycallLen.append(idx-callStartIdx)
            ycallPeak.append(np.mean(callPeaks))
        else:
            ycallLen.append(0)
            ycallPeak.append(0)
        if N_peaks == 0:
            updateBackground(psdraw)
        xplot.append(idx)
        yNpeaks.append(N_peaks)

        idx += Nsamples//4
        if idx > len(ampData)-Nsamples//4:
            done = True
    #    if idx > 300000:
    #        done = True    plt.scatter(xplot,xplot/np.max(xplot))



    fig = plt.figure(figsize=(14,8))
    plt.plot(xplot,safediv(yNpeaks,np.max(yNpeaks)), color = 'blue')
    plt.scatter(xplot,safediv(ycallLen,np.max(ycallLen)),color='red')
    plt.scatter(xplot,safediv(ycallPeak,np.max(ycallPeak)),color='black')
    #plt.ylim(0.8,1.1)
    plt.title(outFileName +" blue=N peaks, red = length of call, black = max peak amp -- all normalized to 1")
    outFileName = os.path.join(dirOutput,outFileName+".png")
    fig.savefig(outFileName)
    plt.close(fig)

