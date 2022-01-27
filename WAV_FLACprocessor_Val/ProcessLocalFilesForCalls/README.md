My current program for detecting calls in WAV or in FLAC files   --  ValVeirs --            May 12, 2019

This version scans wav and/or flac files that are in a LOCAL directory.

This program detects calls by examining peaks in the power spectral density (PSD).  “Good” calls have a relatively long duration and relatively high PSD.

Reports look like this:

fileName    startidx    stopidx    lencall    f0    sigma_f0    peak    sigma_peak

One line for each detected call.  Other meta-data could be put in this line if we wish.

The 'best' calls seem to be the ones with a long length (lencall in samples) and strong peaks (peak)


The top-level Python program is scanLocalAudioFilesForCall.py

1. This program sets up input directory for WAV files and for FLAC files and output directory for call report
2. Typical command line: ./scanAudioFilesForCalls.py -i /home/val/callDetection/FLACs -o /home/val/callDetection/Calls
          -i for directory holding input wav or flac files  -o for the directory where call data is written
3. Then the program calls searchFileForCalls for each successive wav file

searchFileForCall.py is the main file that scans for calls.

First, it reads in WAV or FLAC file.

In a loop, it moves along the data in blocks of size Nsamples/4 (4096 is ~0.1 sec at 44,100 sample rate)

In each case, the smoothed PSD for a Nsamples section of data is calculated
1.  The PSD is calculated via Welch’s method in subsets of 256 samples drawn from the Nsamples section under analysis
2.  Detrend the PSD
3.  Run savgol filter over the PSD twice

Then the smoothed background is subtracted and 
1.  the first ~20-25 PSD values are set to 0 (high pass filter at 400 Hz)
2.  any PSD values less than the mean of the background + 4 * standard deviation of background are set to zero
3.  This modified PSD is now analyzed for any peaks.

    1. The indices of peaks greater than 1 standard deviation of the PSD are determined
    2. Peaks closer together than 100 samples are merged together
    3. The mean and standard deviation of the difference between successive peaks is calculated
    4. This routine (getDeltaf_PeakStats) returns the number of peaks, the mean and std. Dev. of the separation of successive peaks (this may be the fundamental of harmonic signals) and also returns the indices of the peaks.       

Back in the main loop, the start of a ‘call’ is signified by having 1 or more peaks and a call continues while the number of peaks is greater than zero.

At the end of a ‘call’ a line is written to an output file that contains the following:
1. Call start index
2. Call stop index
3. Length of call in samples (2. - 1.)
4. Mean and std. dev. of the fundamental frequency of each of the PSD’s in this call
5. Mean and std. dev. of the mean peak amplitude of each of the PSD’s in this call

At the end of each WAV file, a graph is made and saved to the Call directory.  This graph has
1. Blue lines show the number of peaks detected at each point in the WAV file
2. Red dots indicate the length of a detected call
3. Blue dots indicate the mean peak amplitude of data blocks in the call
4. All three of these outputs are normalized to a maximum of 1.0 so that they fit on the graph.

This program has the following free parameters:
1. Size of fft input in samples (256)
2. Size of the block given to the Welch PSD algorithm (Nsamples= 4096)
3. Size of step through the data (Nsamples/4)
4. Cut for high pass filter of background-subtracted and smoothed PSD (400 Hz)
5. Cut for eliminating low amplitude peaks ( < mean peak height + 4 * height std. dev)
6. Merge any close peaks, (peak indices difference  less than 100)







