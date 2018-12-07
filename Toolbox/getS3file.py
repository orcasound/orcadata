#!/usr/bin/env python3
# 
# Usage: Call routine with S3 bucket, desired S3 file, and name for local copy of this file, e.g.:
# ./getS3file.py 'streaming-orcasound-net' 'rpi_orcasound_lab/hls/1541027406/live000.ts' 'xfer/live000.ts'
#
#  S3 bucket is  streaming-orcasound-net
#  S3 file is  rpi_orcasound_lab/hls/1541027406/live000.ts
#  Local dir/file is  xfer/live000.ts
#
# Code by Val Veirs, Dec 2018

import sys
import boto3
import botocore

print("S3 bucket is ", str(sys.argv[1]))
print("S3 file is ", str(sys.argv[2]))
print("Local file is ", str(sys.argv[3]))

BUCKET_NAME = sys.argv[1]
KEY = sys.argv[2]       
LOCALFILE = sys.argv[3] 

s3 = boto3.resource('s3')

try:
   s3.Bucket(BUCKET_NAME).download_file(KEY, LOCALFILE)
except botocore.exceptions.ClientError as e:
   if e.response['Error']['Code'] == "404":
       print("The object does not exist.")
   else:
    raise
