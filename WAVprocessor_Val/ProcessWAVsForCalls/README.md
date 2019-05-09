My current program for detecting calls in WAV  files   --  ValVeirs --            May 7, 2019

This program detects calls by examining peaks in the power spectral density (PSD).  “Good” calls have a relatively long duration and relatively high PSD.

Reports look like this:
fileName	startidx	stopidx	lencall	f0	sigma_f0	peak	sigma_peak
NATURE11_09_02_21_23_3701	0	2048	2048	1152	161	260	29
NATURE11_09_02_21_23_3701	8192	9216	1024	0	0	175	0
NATURE11_09_02_21_23_3701	12288	13312	1024	0	0	167	0
NATURE11_09_02_21_23_3701	14336	16384	2048	0	0	168	1
NATURE11_09_02_21_23_3701	19456	59392	39936	500	376	2472	3452
NATURE11_09_02_21_23_3701	66560	67584	1024	0	0	223	0
NATURE11_09_02_21_23_3701	69632	70656	1024	0	0	159	0
NATURE11_09_02_21_23_3701	71680	72704	1024	0	0	188	0
NATURE11_09_02_21_23_3701	74752	76800	2048	0	0	178	18
NATURE11_09_02_21_23_3701	83968	90112	6144	222	497	206	20
NATURE11_09_02_21_23_3701	91136	93184	2048	818	0	211	42
NATURE11_09_02_21_23_3701	98304	102400	4096	0	0	203	46
NATURE11_09_02_21_23_3701	103424	108544	5120	167	335	183	7
NATURE11_09_02_21_23_3701	109568	111616	2048	0	0	214	28
NATURE11_09_02_21_23_3701	113664	116736	3072	631	446	202	52
NATURE11_09_02_21_23_3701	117760	119808	2048	462	462	192	2
NATURE11_09_02_21_23_3701	122880	134144	11264	634	741	252	86
NATURE11_09_02_21_23_3701	136192	137216	1024	0	0	156	0
NATURE11_09_02_21_23_3701	138240	147456	9216	291	450	317	75
NATURE11_09_02_21_23_3701	148480	150528	2048	0	0	500	4
NATURE11_09_02_21_23_3701	158720	173056	14336	805	956	241	65
NATURE11_09_02_21_23_3701	182272	183296	1024	0	0	157	0
NATURE11_09_02_21_23_3701	187392	211968	24576	733	411	709	456
NATURE11_09_02_21_23_3701	214016	219136	5120	691	565	313	100
NATURE11_09_02_21_23_3701	221184	270336	49152	558	552	21928	34971
NATURE11_09_02_21_23_3701	271360	276480	5120	447	306	1804	903
NATURE11_09_02_21_23_3701	278528	287744	9216	805	661	422	238
NATURE11_09_02_21_23_3701	291840	292864	1024	0	0	166	0
NATURE11_09_02_21_23_3701	293888	294912	1024	0	0	165	0
NATURE11_09_02_21_23_3701	295936	299008	3072	0	0	210	10


The 'best' calls seem to be the ones with a long length (lencall in samples) and strong peaks (peak)


The top level Python program is scanAudioFilesForCall.py
    1. This program sets up input directory for WAV files and for FLAC files and output directory for call report
    2. Then is calls searchForCalls for each successive wav file

searchForCall.py is the main file that scans for calls.

First, it reads in WAV file.

In a loop, it moves along the data in blocks of size Nsamples/4 (4096 is ~0.1 sec at 44,100 sample rate)

In each case the smoothed PSD for a Nsamples section of data is calculated
    1. The PSD is calculated via Welch’s method in subsets of 256 samples drawn from the Nsamples section under analysis
    2. Detrend the PSD
    3. Run savgol filter over the PSD twice
Then the smoothed background is subtracted and 
    1.  the first 25 PSD values are set to 0 (high pass filter at about 400 hz)
    2. any PSD values less than the mean of the background + 4 * standard deviation of background are set to zero
This modified PSD is now analyzed for any peaks.
    1. The indices of peaks greater than 1 standard deviation of the PSD are determined
    2. Peaks closer together than 100 samples are merged together
    3. The mean and standard deviation of the difference between successive peaks is calculated
    4. This routine (getDeltaf_PeakStats) returns the number of peaks, the mean and std. Dev. of the separation of successive peaks (this may be the fundamental of harmonic signals) and also returns the the indices of the peaks.       
Back in the main loop, the start of a ‘call’ is signified by having 1 or more peaks and a call continues while the number of peaks is greater than zero.

At the end of a ‘call’ a line is written to an output file that contains the following:
    1. Call start index
    2. Call stop index
    3. Length of call in samples (2. - 1.)
    4. Mean and std. dev. of fundamental frequency of each of the PSD’s in this call
    5. Mean and std. dev. of the maximum amplitude of each of the PSD’s in this call

At the end of each WAV file, a graph is made and saved to the Call directory.  This graph has
    1. Blue lines show the number of peaks detected at each point in the WAV file
    2. Red dots indicate the length of a detected call
    3. Blue dots indicate the maximum amplitude of peaks in the call
    4. All three of these outputs are normalized to a maximum of 1.0 so that they fit on the graph.

This program has the following free parameters:
    1. Size of fft input in samples (256)
    2. Size of block given to the Welch PSD algorithm (Nsamples= 4096)
    3. Size of step through the data (Nsamples/4)
    4. Cut for high pass filter of background subtracted and smoothed PSD (25 samples)
    5. Cut for eliminating low amplitude peaks ( < mean peak height + 4 * height std. dev)
    6. Merge any close peaks, (peak indices difference  less than 100)







