import pickle
from scipy.signal import welch
import numpy as np

DEBUG = 0

def write_log(txt):
    with open('log.txt', 'a') as f:
        f.write(txt + '\n')


def save_obj(obj, name):
    #    print("in save_obj_", name)
    with open(name, 'wb') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)


def load_obj(name):
    #    print("in load_obj ", os.getcwd())
    with open(name, 'rb') as f:
        return pickle.load(f)


def checkDir(theDir):  # make sure directory has a / at the end
    items = theDir.split('/')
    if items[-1] != '':
        theDir += '/'
    return theDir

class wavFileArrays():  # {'label': [label], 'start': [startSec], 'end': [endSec], 'freq_min': [f_low], 'freq_max': [f_high], 'model': ['tbd'], 'probs': [-1], 'psdAves': [-1]

    def __init__(self, wavDir, wavFile, Nfreq, Ntime, logScale, f_min, f_max, Nfft):
        self.wavDir = wavDir
        self.wavFile = wavFile
        self.f_min = f_min
        self.f_max = f_max
        self.logScale = logScale
        self.Nfreq = Nfreq
        self.Ntime = Ntime
        self.Nfft = Nfft

        self.numArrays = 0
        self.arrayList = []
        self.startSecs = []
        self.endSecs = []

    def addSpec(self, startSecs, endSecs, specGram):
        self.numArrays += 1
        self.startSecs.append(startSecs)
        self.endSecs.append(endSecs)
        self.arrayList.append(specGram)

    def printSummary(self):
        outline = 'dataNode smry: wav file = {}, number of numpy arrays = {}'.format( self.wavFile, self.numArrays)
        print(outline)
        outline = '     f_min={}, f_max={}, logScale={}'.format( self.f_min, self.f_max, self.logScale)
        print(outline)

def sortFilelist(files, labeled):  # '/home/vv/ketosToolchain/allPsds/1_Monika_Track 4_at_1011.5_psd_663_540_656.pkl'
    # sort by filename and then time in file
    fileRecs = []
    for file in files:
        items = file.split('_at_')
        thetime = float(items[1].split('_')[0])
        thefile = items[0].split('/')[-1]
        items = thefile.split('_')
        thefile = ''
        iStart = 1
        if labeled:
            iStart = 2
        for i in range(iStart, len(items)):
            thefile += items[i]
            if i < len(items) - 1:
                thefile += '_'

        fileRecs.append([thefile, thetime, file])
    fileRecs = sorted(fileRecs, key=lambda items: items[0])  # first sort on time
    fileRecs = sorted(fileRecs, key=lambda items: items[1])  # then sort of filename
    files = []
    for item in fileRecs:
        files.append(item[2])
    return files

def get_psd_values(y_values, f_s, Nfft):
    f_values, psd_values = welch(y_values, fs=f_s, nfft=Nfft, scaling='spectrum')
    if len(psd_values) < Nfft / 2:
        print("length psd", len(psd_values), "len(y_values)", len(y_values), "Nfft", Nfft)
        input("psd_values not available ... waiting in get_psd_values")
    return f_values, psd_values

def compressPsdSliceLog(freqs, psds, flow, fhigh, nbands, doLogs):
    compressedSlice = np.zeros(nbands + 1)  # totPwr in [0] and frequency of bands is flow -> fhigh in nBands steps
    #    print("Num freqs", len(freqs))
    idxPsd = 0
    idxCompressed = 0
    fbands = setupFreqBands(flow, fhigh, nbands, doLogs)
    # integrate psds into fbands
    df = (fhigh - flow) / nbands
    totPwr = 0
    while freqs[idxPsd] <= fhigh and idxCompressed < nbands:
        # find index in freqs for the first fband
        while freqs[idxPsd] < fbands[idxCompressed]:  # step through psd frequencies until greater than this fband
            idxPsd += 1
        dfband = freqs[idxPsd] - fbands[idxCompressed]  # distance of this psd frequency into this fband
        pfrac = 1 - dfband / df
        psd = pfrac * psds[idxPsd]  # put frac of first pwr in psd
        fmax = fhigh
        if idxCompressed < nbands - 1:
            fmax = fbands[idxCompressed + 1]
        while freqs[idxPsd] < fmax:
            psd += psds[idxPsd]
            idxPsd += 1
        dfband = freqs[idxPsd] - fmax
        pfrac = dfband / df
        psd += pfrac * psds[idxPsd]
        compressedSlice[idxCompressed + 1] = psd
        if DEBUG > 0:
            print(idxCompressed+1, psd)
        totPwr += psd
        idxCompressed += 1
    compressedSlice[0] = totPwr
    return compressedSlice

def setupFreqBands(flow, fhigh, nbands, doLogs):
    df = (fhigh - flow) / nbands
    fbands = np.zeros(nbands)
    if not doLogs:
        for i in range(nbands):
            fbands[i] = flow + i*df
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