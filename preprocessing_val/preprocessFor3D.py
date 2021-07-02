import helpers_3D as d3
import os
import soundfile as sf
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

"""
  preprocessFor3D.py builds a three dimensional array
    The x axis is a time axis with Ntime time intervals over selected time for array, deltaT in sec
    The y axis is a signal frequency band axis
TBD    The z axis is an 'averaging time' axis and the units of the x axis scale with this z axis

    The y axis is set up via user choice:
      y = 0 will always be the broadband signal level in dB
      Nfreq = the number of frequency bands
      flow and fhigh are the lower and upper frequency limits
      logScale = true/false

NOTE: z axis is STILL in DEVELOPMENT so is not included now
    The z axis is set up either
      A: as averaging times log scaled from selected min to max seconds
          aveTmin, aveTmax, NaveTimes
      B: or by specifying a list of desired averaging times.
          ( aveTmin1, aveTmin2, aveTmin3, ...)

    A list of wav files to be processed is provided as a folder containing wav files
      If chronological, filenames must be such that sorting them puts them in chronological order

    The program scans the wav files calculating psd's with user selected overlap (%overlap)
      and compresses the psd's into the selected frequency bands
TBD      and for each block of data, the program updates the running averages
TBD      The final 3 dimensional matrices are stored in python's binary pickle format

    Spectral compression is done as shown below:
    psd frequency bins  | A   |     |    B|     |     | C   |     |    D|  ...
    numpy array freqs     |     bin1     |     bin2     |     bin3     |
    
    To calculate the power in bin1, the psd values from A to the end of the psd bin
    are added to the psd values in the following entire bin
    and then the fraction of psd values out to B are added to get the total power 
    in the numpy array bin1,  this procedure is carried out for bin1, bin2, bin3, ...
    For the choice of a logarithmic frequency scale, the numpy array frequencies are of 
    exponentially increasing width.
    --code is in helpers_3D.py file at:
      def compressPsdSliceLog(freqs, psds, flow, fhigh, nbands, doLogs):

"""
wavDir = d3.checkDir("/media/val/HD _ 5/NN_code/preprocessing_val/snippets")
saveDir = d3.checkDir("/media/val/HD _ 5/NN_code/preprocessing_val/snippets/products")  # this is where computed numpy arrays will be saved
showPlots = True     # set to False to omit plots
maxNumArrays = 10   # set to small number for test runs
# y-Axis
Nfreq = 150
flow = 300
fhigh = 8000
logScale = False

# z-Axis
#aveTmin = 0  #0 signifies no averaging other than that which comes with fft window
#aveTmax = 3600
#NaveTimes = 10

# x-Axis  time axis
deltaT = 3  # number if seconds in a single unaveraged spectrogram array
Ntime = 100  # number of bins spread over the deltaT time interval for unaveraged psd's
Nfft = 1024  # Number of psd frequency bins will be one half of Nfft
            #    If logScale == true, make sure Nfft is large enough for interpolation of power into the log freq bands
secsSkip = 0  # skip this many secs between spectrograms  0 for calls and clicks    something for backgrounds to speed processing
stepFrac = 1/3  # advance this fraction of deltaT for each new spectrogram
channelChoice = -1  # means if there are two channels, take the higher amplitude one
                    #   otherwise select your desired channel

bbCalDB = 20   # this hydrophone calibration factor is added to the dB value of the total power calculated from the psd
# calibration factor is not yet implemented


#############   Computation begins here ######################
wavFileList = ""
try:
  os.chdir(wavDir)
  # get list of the wav or WAV files
  wavFileList = [f for f in os.listdir('.') if any(f.endswith(ext) for ext in ['WAV', 'wav'])]  # os.listdir()  # get list of the wav files
  wavFileList.sort()
except:
  print("failed to load wavs from dir ", wavDir)
  exit()
print("Files to be processed are ", wavFileList)

theTimeNow = datetime.now()
specGram = np.zeros((Nfreq + 1, Ntime))  # computed psd's will be compressed into specGram
thisRunWavFileArrays = []
for thisWav in wavFileList:
  #  initialize wavFileArrays object to hold numpy arrays from wav file
  wfa = d3.wavFileArrays(wavDir, thisWav, Nfreq, Ntime, logScale, flow, fhigh, Nfft)
  with sf.SoundFile(wavDir + thisWav) as f:
    print("------------------------------- starting file", wavDir, thisWav)
    fPtr = 0
    m_blocksize = deltaT * f.samplerate // Ntime  # grab input from soundfile in buffers of this size
    seekDelta = int(deltaT * f.samplerate * stepFrac)
    if d3.DEBUG > 0:
      print(f.tell(), len(f), Ntime * m_blocksize, secsSkip * f.samplerate)
    while f.tell() < len(f) - Ntime * m_blocksize - secsSkip * f.samplerate:
      filePos = f.tell()
      for psdIdx in range(Ntime):
        data = f.buffer_read(m_blocksize, dtype='int16')
        if not data:
          break
        if f.channels == 2:
          if channelChoice == -1:
            ch0 = np.average(np.abs(np.frombuffer(data, dtype='int16')[0::2]))
            ch1 = np.average(np.abs(np.frombuffer(data, dtype='int16')[1::2]))
            if ch0 > ch1:
              channelChoice = 0
            else:
              channelChoice = 1

          npData = np.frombuffer(data, dtype='int16')[channelChoice::2]
        else:
          npData = np.frombuffer(data, dtype='int16')
        f_values, psd_values = d3.get_psd_values(npData, f.samplerate, Nfft)  # calculate the psd
        #                        print("psd values shape=",psd_values.shape)
#        psd_compressed = d3.compressPsdSlice(f_values, psd_values, flow, fhigh, Nfreq)
        psd_compressed = d3.compressPsdSliceLog(f_values, psd_values, flow, fhigh, Nfreq, logScale)
        specGram[:,psdIdx] = psd_compressed   # Note:  specGram[0,:] is the total power

      minPsd = np.min(np.abs(specGram[1:,:])) +1e-10  # skip the first row which is total power
      maxPsd = np.max(np.abs(specGram[1:,:]))
      if d3.DEBUG > 0:
        print(np.log10(minPsd), np.log10(maxPsd))
        print(np.log10(specGram[:,0]))
        for i in range(Ntime):
          line = ""
          for j in range(Nfreq):
            line += str(int(specGram[j][i]))+" "
          print(line)

      endSecs = f.tell() / f.samplerate
      startSecs = endSecs - deltaT
      filePos += seekDelta
      f.seek(filePos)  # advance the file pointer desired fraction of deltaT
      wfa.addSpec(startSecs, endSecs, specGram)
      wfa.printSummary()
      if wfa.numArrays >= maxNumArrays:   # this is for debugging to reduce compute time
        break
      if showPlots:
        specGram = np.flip(specGram, 0)   # flip so the total power is at the 'bottom' of the array when plotted
        plt.yticks([])
        plt.imshow(np.log10(specGram))
        plt.title('{}_{:0.1f}_{:0.1f}s'.format(thisWav, startSecs, endSecs))
        plt.show()
        input('Any key for next.')   # use this to stop processing at each plot

  # write out this wav file's numpy arrays
  outfileName = "{}{}_run_on_{}.pkl".format(saveDir, thisWav, theTimeNow)
  outfileName = outfileName.replace('.','_')
  outfileName = outfileName.replace(':', '_')
  d3.save_obj(wfa,outfileName)
  thisRunWavFileArrays.append(outfileName)

outfileName = "{}Summary_of_run_on_{}_.pkl".format(saveDir, theTimeNow)
outfileName = outfileName.replace('.', '_')
outfileName = outfileName.replace(':', '_')
d3.save_obj(thisRunWavFileArrays,outfileName)

##################################################################
#  load in the list of saved objects and print summary of each wav file's numpy arrays
print('\n_________________  Run is finished _________________')
print('check saved data by reading some in')
thisRunWavFileArrays_2 = d3.load_obj(outfileName)
print(thisRunWavFileArrays_2)
for wavFileArrayName in thisRunWavFileArrays_2:
  wavFileArray = d3.load_obj(wavFileArrayName)
  print(wavFileArrayName)
  wavFileArray.printSummary()
  print('-----')

