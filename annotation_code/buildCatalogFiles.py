"""
Add soundfile and numpy to Python environment   pip -m install soundfile  and pip -m install numpy
Add    mutagen         pip -m install mutagen
Add    matplotlib      pip -m iinstall matplotlib
"""

import soundfile as sf
import numpy as np
import os
import ast
import mutagen
import matplotlib.pyplot as plt

# class Parent:
#     def __init__(self, a, b, c):
#         self.a = a
#         self.b = b
#         self.c = c
#
#
# class Child(Parent):
#     def __init__(self, d, **kwargs):
#         super(Child, self).__init__(**kwargs)
#         self.d = d
#
# x = Child(a='a', b='b', c='c', d='d')
# print(x)


class extractAndAnnotateTimeseries():
    def __init__(self,sndfile, channelchoice, starttime, stoptime, fmin, fmax, data_region, data_node, annotator, sample_datetime, call_type, commentdict, outputdir, outputfiletype):
        self.sndfile = sndfile
        self.secsstart = int(starttime[0])*3600 + int(starttime[1])*60 + float(starttime[2])
        self.secsstop = int(stoptime[0]) * 3600 + int(stoptime[1]) * 60 + float(stoptime[2])
        self.fmin = fmin
        self.fmax = fmax
        self.call_type = call_type
        self.info = sf.info(sndfile)
        self.channelchoice = channelchoice
        self.outdir = outputdir
        self.outputfiletype = outputfiletype
        self.dtype = ''
        self.subtype = ''
        self.data_region = data_region
        self.data_node = data_node
        self.annotator = annotator
        self.sample_datetime = sample_datetime
        self.comments = commentdict
        self.samplerate = 0
        self.outputtimeseriesfilename = ''

        self.data = self.extractsamples()

    def getTimeseries(self):
        return self.data, self.samplerate

    def extractsamples(self):
        channelchoice = -1  # pick channel with higher amplitude
        typedict = {}
        typedict['FLOAT'] = 'float32'
        typedict['PCM_16'] = 'int16'
        nsamples = int((self.secsstop - self.secsstart)*self.info.samplerate)      #  N. B. could include ramp up and ramp down extensions
        with sf.SoundFile(self.sndfile) as f:
            f.seek(int(self.secsstart*self.info.samplerate))  # Jump to the start of the desired data
            data = f.buffer_read(nsamples, dtype=typedict[f.subtype])
            self.dtype = typedict[f.subtype]
            self.subtype = f.subtype  # save file type to use when writing out annotation sound file
            print(f.subtype, self.dtype)                 # allowable are ['float32', 'float64', 'int16', 'int32']
            npdata = self.convertToNumpy(f, typedict, data)
            self.samplerate = f.samplerate
        # write out selected sound data points
        outputtimeseriesfilename = self.sndfile.split("/")[-1].split(".")[0] + "-{:0.3f}-secs-{}.{}".format(self.secsstart, self.call_type, self.outputfiletype)

        outputfile = self.outdir + "audio/" + outputtimeseriesfilename
        self.outputtimeseriesfilename = outputtimeseriesfilename

        with sf.SoundFile(outputfile, 'w', self.info.samplerate, 1) as fout: #, self.subtype) as fout:
            fout.write(npdata) #, self.subtype)
            fout.filename = self.sndfile

        addAnnotations(outputfile, self.data_region, self.data_node, self.annotator, self.sample_datetime, self.call_type, self.comments)
        print("Save annotated acoustic outputfile: ", outputfile)
        with sf.SoundFile(outputfile, 'r') as fin:
            print(fin.extra_info)
        print(sf.info(outputfile))
        f = mutagen.File(outputfile)
        print("print keys")
        for tag in f.keys():
            print(tagDict[tag], ":", f[tag], tag)
        print("finished annotation")
        return npdata

    def convertToNumpy(self, f, typedict, data):
        channelchoice = self.channelchoice  # -1 to pick channel with higher amplitude
        if f.channels == 2:
            if channelchoice == -1:
                ch0 = np.average(np.abs(np.frombuffer(data, dtype=typedict[f.subtype])[0::2]))
                ch1 = np.average(np.abs(np.frombuffer(data, dtype=typedict[f.subtype])[1::2]))
                if ch0 > ch1:
                    channelchoice = 0
                else:
                    channelchoice = 1
            npdata = np.frombuffer(data, dtype=typedict[f.subtype])[channelchoice::2]
        else:
            npdata = np.frombuffer(data, dtype=typedict[f.subtype])
        return npdata

def editMetadata(filename, track="", album="", tracknum="", year="", genre="", comments=""):
    f = mutagen.File(filename)
    try:
        f.add_tags()
    except:
        i=0
    filetype = filename.split(".")[-1].lower()
    if track != "":
        if filetype == 'wav':
            f.tags.add(mutagen.id3.TIT2(encoding=3, text=[track]))
        if filetype == 'flac':
            f.tags['title'] = track
    if album != "":
        if filetype == 'wav':
            f.tags.add(mutagen.id3.TALB(encoding=3, text=[album]))
        if filetype == 'flac':
            f.tags['album'] = album
    if tracknum != "":
        if filetype == 'wav':
            f.tags.add(mutagen.id3.TRCK(encoding=3, text=[tracknum]))
        if filetype == 'flac':
            f.tags['tracknum'] = tracknum
    if year != "":
        if filetype == 'wav':
            f.tags.add(mutagen.id3.TDRC(encoding=3, text=[year]))
        if filetype == 'flac':
            f.tags['year'] = year
    if genre != "":
        if filetype == 'wav':
            f.tags.add(mutagen.id3.TCOM(encoding=3, text=[genre]))
        if filetype == 'flac':
            f.tags['genre'] = genre
    if comments != "":
        if filetype == 'wav':
            f.tags.add(mutagen.id3.COMM(encoding=3, text=[comments]))
        if filetype == 'flac':
            f.tags['comments'] = str(comments)
    f.save()

tagDict = {"title":"data_region", "track":"data_region", "album":"data_node", "tracknum":"annotator", \
           "year":"sample_datetime", "genre":"call_type", "comments":"comments", "composer":"call_type",\
           "TIT2":"data_region","TALB":"data_node", "TRCK":"annotator", "TDRC":"sample_datetime", "TCOM":"call_type","COMM::XXX":"Comments"}

def addAnnotations(filename, data_region, data_node, annotator, sample_datetime, call_type, comments):
    editMetadata(filename, track=data_node, album=data_region, tracknum=annotator, year=sample_datetime, genre=call_type, comments=comments)
#######################################################################
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
            fbands[i] = np.power(10,np.log10(flow) + (i * dlogf))
    return fbands

def compressPsdSliceLog(freqs, psds, flow, fhigh, nbands, doLogs):
    compressedSlice = np.zeros(nbands + 1)  # totPwr in [0] and frequency of bands is flow -> fhigh in nBands steps
    #    print("Num freqs", len(freqs))
    idxPsd = 0
    idxCompressed = 0
    fbands = setupFreqBands(flow, fhigh, nbands, doLogs)
    # integrate psds into fbands
    df = (fhigh - flow) / nbands
    totPwr = 0
    cnt = 0
    while freqs[idxPsd] <= fhigh and idxCompressed < nbands:
        # find index in freqs for the first fband
        while freqs[idxPsd] < fbands[idxCompressed]:  # step through psd frequencies until greater than this fband
            idxPsd += 1
        dfband1 = freqs[idxPsd] - fbands[idxCompressed]  # distance of this psd frequency into this fband
        pfrac1 = dfband1 / df
#        print("1  ",idxPsd,pfrac1, dfband1)
        psd = pfrac1 * psds[idxPsd - 1]  # put frac of first pwr in psd
        fmax = fhigh
        if idxCompressed < nbands - 1:
            fmax = fbands[idxCompressed + 1]
        while freqs[idxPsd +1] < fmax:
            psd += psds[idxPsd]
            idxPsd += 1
        dfband2 = fmax - freqs[idxPsd]
        pfrac2 = dfband2 / df
        psd += pfrac2 * psds[idxPsd]
#        print("2  ", idxPsd, pfrac2,dfband2)
        compressedSlice[idxCompressed + 1] = np.abs(psd)
        cnt += 1
        totPwr += psd
        idxCompressed += 1
    compressedSlice[0] = np.abs(totPwr)
    return compressedSlice


def getSpectrogram(timeseriesdata, samplerate, specFmin, specFmax, Npsds, binspersec):
    specGram = []
    totsecs = len(timeseriesdata)/samplerate
    taxisStep = samplerate/binspersec
    Ntimebins = int(len(timeseriesdata)/taxisStep)
    Nfft = 2048

    for tidx in range(Ntimebins):
        t1 = int(tidx*taxisStep)
        t2 = min(t1 + 2048, len(timeseriesdata))
        data = timeseriesdata[t1:t2]
        spec = np.abs(np.fft.rfft(data))
        f_values = np.fft.fftfreq(len(data), d=1.0/samplerate)
        spec = compressPsdSliceLog(f_values, spec, specFmin, specFmax, Npsds, False)
        specGram.append(spec)
    specGram = np.log10(np.flip(specGram) + 0.001)  # to avoid log(0)
    specGram = np.rot90(specGram, 3)
    return specGram, totsecs

def extractFromFilename(file):
    items = file.split("/")[-1].split("_")
    thisdatetime = "{}/{}/{} {}:{}:{}".format(items[3], items[1], items[2],items[4],items[5], items[6])
    return thisdatetime
###########################################################################################################
#####     Execution starts here
############################################################################################################
# User choices begin HERE
######################################################################################################
#  setup wav file and start/stop times and metadata (call type, f-low, f-high, average signal to noise ratio)
outputdir = "/home/val/pythonFiles/CallCatalog/catalogfiles/"
try:
    os.mkdir(outputdir)
    print("output will go into", outputdir)
except:
    print(outputdir, "exists")
outputfiletype = 'flac'   # must be 'flac' or 'wav'

channelchoice = -1   #  -1 signifies take the channel with the highest average amplitude
acousticfile = "/media/val/TB_5/WAVs/OS_09_02 to_11_23_2021/continuous/OS_10_28_2021_19_55_00_.wav"
annotationfile = "/home/val/pythonFiles/CallCatalog/catalogfiles/OS_10_28_2021_19_55_00_.Table.1.selections.txt"
starttime = (0, 2, 13.823)  # (hr, min, secs) into wavfile
stoptime  = (0, 2, 18.693)
fmin = 500
fmax = 1000
S2N = 12.3
sample_datetime = '2021/10/03 19:34:00'
sample_datetime = extractFromFilename(acousticfile)
print("sample_datetime is", sample_datetime)
call_type = 'WhooptyDo'
comments = 'Ship in background'

data_region='Salish Sea'
data_node = 'orcasound_lab'
annotator  = 'Emily'


##########################  User choices ABOVE this line
# open the annotation file
with open(annotationfile) as af:
    header = af.readline()
    print("heading of annotation file is:\n,", header)
    heditems = header.split("\t")
    for i in range(len(heditems)):
        print(i, heditems[i])
    maxSpecCnt = 10
    for i in range(maxSpecCnt):
        aline = af.readline()
        items = aline.split("\t")
        print("first data line:")
        for i in range(len(items)):
            print(i, heditems[i], items[i])
        starttime = (0, 0, float(items[3]))
        stoptime  = (0, 0, float(items[4]))
        fmin = float(items[5])
        fmax = float(items[6])
        AgEntropy = float(items[7])
        peakFreq = float(items[8])
        peakPwr  = float(items[9])
        S2N = float(items[10])
        call_type = items[11].replace("\n","")

        ######
        embeddedcomments = "{" + "'fmin':'{:0.1f}','fmax':'{:0.1f}', 'S2N':'{:0.2f}','comments':'{}'".format(fmin, fmax, S2N, comments)+"}"
        commentdict = ast.literal_eval(embeddedcomments)
        annotTimeseries = extractAndAnnotateTimeseries(acousticfile, channelchoice, starttime, stoptime, fmin, fmax, \
                           data_region, data_node, annotator, sample_datetime, call_type, commentdict, outputdir, outputfiletype)
        data, samplerate = annotTimeseries.getTimeseries()

        specFmin = 0
        specFmax = 10000
        Npsds = 512         # number of psds between specFmin and specFmax
        binspersec = 100    # number of spectrogram time bins per second of timeseries

        specGram, totsecs = getSpectrogram(data, samplerate, specFmin, specFmax, Npsds, binspersec)

        thisTitle = annotTimeseries.outputtimeseriesfilename.split(".")[0] + "\n" + annotTimeseries.call_type
        print("plot title is", thisTitle)
        fig = plt.figure()
        fig.suptitle(thisTitle)
        plt.xlabel('Time (sec)')
        plt.ylabel('Frequency (kHz)')
        #plt.gray()
        plt.imshow(np.square(specGram), extent=[0, totsecs, specFmin, specFmax], aspect=totsecs / specFmax)
        #plt.show()
         # drop the file image filetype
        specFilename = annotTimeseries.outputtimeseriesfilename.split(".")[0] + "-" + annotTimeseries.call_type + ".jpg"
        print("saving spectrogram", specFilename)
        plt.savefig(outputdir + "specs/" + specFilename)




print("all done")
