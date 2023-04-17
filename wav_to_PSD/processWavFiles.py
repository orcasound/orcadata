import numpy as np
import matplotlib.pyplot as plt
import soundfile as sf
from scipy.signal import find_peaks
import math
import os
DEBUG = 0

def setupFreqBands(flow, fhigh, nbands, doLogs):
    df = (fhigh - flow) / nbands
    fbands = np.zeros(nbands+1)  # reserve [0] for the integrated psd (Broadband level)
    if not doLogs:
        for i in range(nbands):
            fbands[i+1] = flow + i*df
    else:
        dlogf = (np.log10(fhigh) - np.log10(flow)) / (nbands - 0)
        fbands[0] = flow
        for i in range(1, nbands):
            if DEBUG > 0:
                print("np.power(10,(i * dlogf))", np.power(10,(i * dlogf)))
            fbands[i] = np.power(10,np.log10(flow) + (i * dlogf))
        if DEBUG > 0:
            print("flow,fbands,fhigh",flow,fbands,fhigh)
    return fbands

def convertToNumpy(f, typedict, data):
    channelchoice = -1  # -1 to pick channel with higher amplitude
    if f.channels == 2:
        if channelchoice == -1:
            try:
                ch0 = np.average(np.abs(np.frombuffer(data, dtype=typedict[f.subtype])[0::2]))
                ch1 = np.average(np.abs(np.frombuffer(data, dtype=typedict[f.subtype])[1::2]))
                if ch0 > ch1:
                    channelchoice = 0
                else:
                    channelchoice = 1
            except:
                channelchoice = 0
        npdata = np.frombuffer(data, dtype=typedict[f.subtype])[channelchoice::2]
    else:
        npdata = np.frombuffer(data, dtype=typedict[f.subtype])
    return npdata

def getSamples(startsecs, Nsamples, WAV):
    # need to get Ntimes blocks of time series data
    channelchoice = -1  # pick channel with higher amplitude
    typedict = {}
    typedict['FLOAT'] = 'float32'
    typedict['PCM_16'] = 'int16'

    NsamplesNeeded = Nsamples
    npsamples = []
    totalSecs = 0
    while NsamplesNeeded > 0:

        with sf.SoundFile(WAV) as f:
            #            print("-------------reading wav file", WAVs[wavStartIdx], "wavStartIdx", wavStartIdx)
            availableSamples = f.seek(0, sf.SEEK_END) - int(startsecs * f.samplerate)
            #            if availableSamples < 0:
            #                print(startsecs)
            #            print("availableSamples=", availableSamples, WAVs[wavStartIdx])
            if len(npsamples) == 0:  # test for first wav file only
                if availableSamples > 0:
                    f.seek(
                        int(startsecs * f.samplerate))  # for first wav file, start at desired number of secs into file
                else:
                    f.seek(0)  # start at beginning of wav file, continuing into a new file
            while availableSamples > 0 and NsamplesNeeded > 0:
                try:
                    if availableSamples >= NsamplesNeeded:
                        data = f.buffer_read(NsamplesNeeded, dtype=typedict[f.subtype])
                        npdata = convertToNumpy(f, typedict, data)
                        NsamplesNeeded = 0
                    else:
                        data = f.buffer_read(availableSamples, dtype=typedict[f.subtype])
                        npdata = convertToNumpy(f, typedict, data)
                        NsamplesNeeded -= availableSamples
                        startsecs = 0
                        availableSamples = 0
                except Exception as e:
                    print("in get samples", e)
                if len(npsamples) == 0:
                    npsamples = npdata
                else:
                    npsamples = np.append(npsamples, npdata)
            totalSecs = f.seek(0, sf.SEEK_END) / f.samplerate
            f.close()

    #    print("n samples", len(npsamples))
    return npsamples, totalSecs

def getWavs(wavDir):
    wavfilelist = []
    try:
        os.chdir(wavDir)
        # get list of the wav or WAV files
        wavfilelist = [f for f in os.listdir('.') if
                       any(f.endswith(ext) for ext in ['WAV', 'wav'])]  # os.listdir()  # get list of the wav files
        wavfilelist.sort()
    except:
        print("failed to load wavs from dir ", wavDir)
        exit()
    return wavfilelist

def getDBs(samples, calCnst):
    pwr = np.square(samples.astype(float))
#    print("max pwr {:0.2f}, min pwr {:0.2f}".format(np.max(pwr), np.min(pwr)))
    pwrMean = np.mean(pwr)
    pwrMeanDb = calCnst + 10 * math.log10(pwrMean)
    pwrStdDb = np.std(calCnst + 10 * np.log10(pwr + 1))
#    print("{}:  mean dB {:0.2f}  +-  {:0.2f}".format(wav, pwrMeanDb, pwrStdDb))
    return pwrMeanDb, pwrStdDb

wavDir = "/home/val/PycharmProjects/wavs/RobErinFiles/raw data (unclipped)/"
print("Input wav directory is", wavDir)
startSecs = 4     # this is after the call tone sequence
startCalTone1000 = 0.2
stopCalTone1000 = 0.4
calCnSndTrap1000 = 135.5

wavfilelist = getWavs(wavDir)
for wav in wavfilelist:
    with sf.SoundFile(wav) as f:
        samplerate = f.samplerate
        n_samples = f.seek(0, sf.SEEK_END)
        # get call tone for calibration at 1000 hz
        samples, secsInWavData = getSamples(startCalTone1000, int((stopCalTone1000 - startCalTone1000) * samplerate), wav)
        Nfft = 16384
        samples = samples * np.hamming(len(samples))
        spec = np.abs(np.fft.rfft(samples, Nfft))
        f_values = np.fft.fftfreq(Nfft, d=1. / samplerate)
        f_values = f_values[0:Nfft // 2 + 1]  # drop the un-needed negative frequencies
        f_values[-1] = f_values[-2]

        # chec for cal tone at 1 khz
        peaks, _ = find_peaks(spec, width=(1,2))
        firstPeak1 = f_values[peaks][0]
#        print("1:first peak freq", f_values[peaks][0])
        peaks, _ = find_peaks(spec, prominence = 2)
        firstPeak2 = f_values[peaks][0]
#        print("2:first peak freq", f_values[peaks][0])

        fig, ax = plt.subplots(2)
        fig.tight_layout(pad=3)
        ax[0].plot(f_values[peaks], spec[peaks], "*")
        ax[0].set_xscale('log')
        ax[0].set_title("wav {}\npeak psds vs freq of peak".format(wav))
        ax[1].plot(f_values, spec)
        ax[1].set_xscale('log')
        ax[1].set_title("psds vs freq")
        plt.show()

        aveFirstPeak = (firstPeak1 + firstPeak2)/2
        if aveFirstPeak < 1000 * .95 or aveFirstPeak > 1000*1.05:
            print("wav file {} does not have proper 1 khz cal tone, {:0.2f} hz was found".format(wav, aveFirstPeak))
            print("......skipping to next wav file")
        else:
            # Calculate calibrated psd for remainder of wav  file
            pwrMeanDbUncal, pwrStdDbUncal = getDBs(samples, 0)  # use these samples to calculate received callibration tone
            # calculate calibration constant from the uncalibrated mean power
            calCnst = calCnSndTrap1000 - pwrMeanDbUncal

            samples, secsInWav = getSamples(startSecs, int(n_samples-startSecs*samplerate), wav)  # get samples from startSecs to end of file
            pwrMeanDb, pwrStdDb = getDBs(samples, calCnst)
            print("{} Cal Constant {:0.3f}, pwrMean {:0.2f}  std {:0.2f}".format(wav, calCnst,  pwrMeanDb, pwrStdDb))
