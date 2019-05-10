Observe specrograms and select and label specific calls saving the results in a log file

WAV_FLAC_Annotator_0_6.py reads an audio file and constructs a spectrogram.
The user can use the mouse to draw a box around regions that contain a call of interest
Upon completing the box, the user can enter a code to describe the call
Then the filename and the coordinates of the selection rectangle (f_low, indexStart, f_high, indexStop) and the call's code are saved in a log file.

This program should be run by:
1. cd to the folder where WAV_FLAC_Annotator_0_6.py resides
2. There must be a folder there titled annotatorLogFiles
3. Via command line enter  python3 WAV_FLAC_Annotator_0_6.py   or  ./WAV_FLAC_Annotator_0_6.py

First select the file you wish to annotate.
Then either select an existing log file
or tap Cancel and then enter a blank into the filename field and tap open.
    This will create a new log file taking its filename from the audio file selected

Wait until the spectrogram is displayed
Then draw your boxes and classify your selections.
   For call classification (C_...), I have been describing the frequency contours with letters such as:
       u or U for upward a little or upward a lot,
       d or D for downward,
       c or C for staying constant for a short period or for a long period,
       w or W for wiggling.

   One could alternatively use the Ford Call Catalog descriptors  S_1 or S_19 etc.

   For ships and boat, make up something memorable!

To quit the program, type a q or Q
