# Read wav file, calculate calibration factor, calculate calibrated psd

## Requirements.txt list required libraries
### Install dependencies:
#### pip3 -m -r requirements.txt     OR
#### python3 -m pip3 install THE_LIBRARY for each needed library  OR
#### use an ide such as PyCharm


### Set parameters:  wav file directory, start and stop seconds for 1 khz call tone and start seconds for data to be calibrated
#### Parameters are set down around line 114

### Typical output:
#### Input wav directory is /home/val/PycharmProjects/wavs/RobErinFiles/raw data (unclipped)/

#### 6982.220728012925.wav Cal Constant 75.915, pwrMean 105.65  std 0.69

#### 6982.220729022925.wav Cal Constant 75.986, pwrMean 105.86  std 1.91

#### 6982.220730030525.wav Cal Constant 76.016, pwrMean 105.89  std 2.05
