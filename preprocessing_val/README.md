 # preprocessFor3D.py builds a three dimensional array
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

##    A list of wav files to be processed is provided as a folder containing wav files
      If chronological, filenames must be such that sorting them puts them in chronological order

##    The program scans the wav files calculating psd's with user selected overlap (%overlap)
      and compresses the psd's into the selected frequency bands
TBD      and for each block of data, the program updates the running averages
TBD      The final 3 dimensional matrices are stored in python's binary pickle format

##    Spectral compression is done as shown below:
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

##  User set directories and parameters are specified at the beginning of the preprocessFor3D.py file
