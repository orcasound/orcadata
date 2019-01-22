#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan  18 10:10:17 2019

@author: val

"""
###  download file from S3 bucket to EC2 Ubuntu instance
from smart_open import smart_open
lines = []
for line in smart_open('s3://shipnoise-net/realtime_files/OS_rt.txt', encoding='utf8'):
    print(line)
    lines.append(line)





 
