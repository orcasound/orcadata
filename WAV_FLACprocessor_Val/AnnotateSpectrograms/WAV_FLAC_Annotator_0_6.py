#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb  5 10:14:07 2019

@author: val

WAV_Annotator  V 0.1

1.  read WAV file
2.  display spectrogram (whole file or sucessive parts depending on length)
3.  play sound and move line along spectrogram
4.  draw box around interesting section
5.  open comment dialog or respond to some specified keystroke comments  e.g.  S_19  for a SRKW call # 19 etc.
6.  save comment and (f_low, ptrInWavStart, f_high, ptrInWavStop) of selection rectangle

"""
import matplotlib
import soundfile as sf
#matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector

from scipy import signal
from scipy.io import wavfile
from scipy.fftpack import fft
from scipy.signal import blackman
import numpy as np
import math
import easygui as eg
#%matplotlib qt       ##########################  this will open plot in a new window
                      ##########################     this plot window can be cosed with plt.close()
def line_select_callback(eclick, erelease):
    x1, y1 = eclick.xdata, eclick.ydata
    x2, y2 = erelease.xdata, erelease.ydata
    print("(%3.2f, %3.2f) --> (%3.2f, %3.2f)" % (x1, y1, x2, y2))

    idx1 = int(min(x1,x2)*Nskip)
    idx2 = int(max(x1,x2)*Nskip)
    print("index values",idx1,idx2)
    freq1 = int(min(y1,y2)*10*1.07)  # approximate conversion from vertical bins to frequency (hz)
    freq2 = int(max(y1,y2)*10*1.07)
    print("freq values", freq1,freq2)
    code = eg.enterbox("Enter code for sound")
    outline = "%s,%d,%d,%d,%d,%s" % (inWAV.split("/")[-1], idx1, freq1, idx2, freq2, code)
    if code != None:
        print(outline)
        logFile = open(logFilename,"a")
        logFile.write(outline + '\n')
        logFile.close()

def toggle_selector(event):
    print(' Key pressed.', event.key)
    if event.key in ['Q', 'q'] and toggle_selector.RS.active:
        print('Rect selector deactivated')
        toggle_selector.RS.active(False)
    if event.key in ['A', 'a'] and not toggle_selector.RS.active:
        print(' Rect selector activated')
        toggle_selector.RS.active(True)

###########  Read in wav or flac file

inWAV = eg.fileopenbox(default="/media/val/021109_2341/",filetypes=["*.WAV", "*.wav", "*.FLAC", "*.flac", "WAV or FLAC Files"])
#inWAV = "/media/val/021109_2303/NATURE11_09_02_21_35_5101.wav" 
print(inWAV)

logFilename = eg.fileopenbox(default="/home/val/PythonFiles/NN/WAVannotator/annotatorLogFiles/",filetypes=["*.log", "Annotator logs"])
print("selected logfile is",logFilename)
if logFilename == None:logFilename = eg.fileopenbox(default="/home/val/PythonFiles/NN/WAVannotator/annotatorLogFiles/",filetypes=["*.log", "Annotator logs"])

if logFilename == None:
    logFilename = "/home/val/PythonFiles/NN/WAVannotator/annotatorLogFiles/%s.log" % inWAV.split('/')[-1].split('.')[0] 
    logFile = open(logFilename,"w+")
else:
    logFile = open(logFilename,"a")
print("this logfile is",logFilename)
logFile.close()
data, sample_rate = sf.read(inWAV)
print("sample rate=",sample_rate)
Ndata = len(data)
#analyze data in  Nfft second chunks and skipping by Nskip chunks
Nsamples = 4096 // 2
Nfft = Nsamples//2
Nskip = Nsamples//8
NfftChunks = Ndata//Nskip +1
NfreqBins = Nsamples//4   # this will give 512 freq bins
freqValues = np.arange(0,NfreqBins)*sample_rate//(8*NfreqBins)   # this takes max freq as ~5500 hz
print("Ndata is",Ndata,"Nsamples is",Nsamples,"Nfft is",Nfft,"NfreqBins is",NfreqBins,"max display frequency is",freqValues[-1])

idx = 0
spec = np.zeros([NfreqBins,NfftChunks])
i=0
maxSpec = 0;
while idx < Ndata-Nsamples-1:
    if data.ndim == 1:
        y = data[idx:idx+Nsamples]
    else:
        y = data[idx:idx+Nsamples][0:,1]  ####  Note Bene  here we extract the first channel of 1 -> N channels
    yf = fft(y)
    idx = idx+Nskip
#    for j in range(0,5):
#        print(idx,freq[j],np.abs(yf[j]))
    for j in range(0,NfreqBins):
        jdx = NfreqBins - 1 - j;
#        spec[jdx,i] = 10*np.log10(np.abs(yf[j]))  #i*(np.sin(float(j)/50) + 1)  #
#        if spec[jdx,i] > maxSpec: maxSpec = spec[jdx,i]
        spec[j,i] = 10*np.log10(np.abs(yf[j]))  #i*(np.sin(float(j)/50) + 1)  #
        if spec[j,i] > maxSpec: maxSpec = spec[j,i]
        
    i += 1

print("maxSpec is", maxSpec)
spec = spec/maxSpec
fig, current_ax = plt.subplots(figsize = (20,4))
#fig(figsize = (30,10))
fig.suptitle(inWAV)
itm = current_ax.matshow(spec,cmap='viridis',origin='lower', aspect = 'auto') #, fignum = 1)
fig.colorbar(itm)
current_ax.get_xaxis().set_visible(False)
toggle_selector.RS = RectangleSelector(current_ax, line_select_callback, drawtype='box', useblit=True, button=[1, 3], minspanx=5, minspany=5, spancoords='pixels', interactive=True)
plt.connect('key_press_event', toggle_selector)
plt.show()



