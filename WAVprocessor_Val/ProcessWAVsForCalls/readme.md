# vals_WavAndLabelsPreprocessor_0_5.py
## Version 0.5 - May 20, 2020

## Val’s WAV and Labels Preprocessor demonstrates selecting labeled segments of WAV files, calculating the power spectral density for these segments, compressing the frequency spectrum into a selected range with a selected spectral resolution.  The amplitude to the psd in the final compressed spectrogram is normalized to a maximum of 1.  The frequency scale can be linear or may be set to be logarithmic.  The time axis is sampled to cover as selected time interval with a selected number of power spectral density segments.

### To be added
Each labeled segment is sampled at a selected number of time intervals close to the labeled time.  This generates spectrograms with the signal at a number of randomly selected times close to the labeled time.
### To be added
In addition, an equal number of ‘background’ spectrograms are computed at times randomly selected between the times of labeled segments.
 
The final spectrograms are stored (pickled) in binary form as numpy arrays.
	Note: these are stored in the obj folder in the pkl directory

# Python script:  ValsWavAndLabelsPreprocessor_0.5.py

Here are parameters users may set:

Input data files:

### Directory where the wav files are stored
wavFileDirectory = "/home/val/Documents/machineLearning/Round3_OS_09_27_2017/wav/"

### these files were downloaded from the aws s3 link in the orcassound Pod.Cast data archive:
### https://github.com/orcasound/orcadata/wiki/Pod.Cast-data-archive

### Label file
labelFilename = "/home/val/Documents/machineLearning/Round3_OS_09_27_2017/train.tsv"

### Directory where the pickled spectrograms and associated metadata will be stored
pklDirectory = "/home/val/Documents/machineLearning/NN_files/dataForNN/pklFiles/"  
####				Note that the pkl files are stored in the obj folder in here

## User parameters:
`Nfft = 512		#resolution of initial psd calculation
n_slices = 80		#number of time segments in spectrogram (number of ‘pixels’ along the x-axis)
n_bands = 80		#number of frequency segments in spectrogram (number of ‘pixels’ along y)
f_low = 400		#low frequency cutoff 
f_high  = 8000		#high frequency cutoff
deltaT = 3		#number of seconds along the x-axis of spectrogram
n_specsPerLabel = 4	#number of spectrograms randomly calculated around labelled time
logFrequency = False 	#True here integrates psd into n_bands logarithmic between f_low and f_high
removeClicks = True  	#simple click remover is applied to wav file data before psd calculation
showPlots = True        #show spectrograms 
pauseAtEachPlot = True  #wait for user after each plot`


# Python script:  displayValsSpectrograms.py 
A program to display image representations of stored spectrograms.

