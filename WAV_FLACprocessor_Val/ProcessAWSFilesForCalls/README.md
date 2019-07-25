
Scan files in a S3 bucket for killer whale calls.

My secure shell logon looks like this:
    ssh -i "/home/val/AWS/Orcasoundpair.pem" ubuntu@ec2-54-188-56-129.us-west-2.compute.amazonaws.com


Progam (scanAWSAudioFilesForCalls.py) is run as follows from the ec2 instance directory that has the program
     cd :~/pythonFiles/readFLACs/AWS

There are three parameters:                             
1.  -b the S3 bucket                                                ( dev-archive-orcasound-net is bucket on s3 )
1.  -i the S3 path to the flac or wav files in bucket                  ( val_test directory-object on s3 )
2.  -o the local directory on ec2 where the call log file will be written ( Calls in the program's directory )

Command line:
 ./scanAWSAudioFilesForCalls.py -b dev-archive-orcasound-net -i val_test -o Calls
       # don't forget to 
            run this program from its directory
            have setup Calls directory inside this directory
