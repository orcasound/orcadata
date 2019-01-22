# orcasound/orcadata/AISprocessing

Python3 routines to:
 
	decode AIS strings

	transfer AIS data to S3 bucket

	read S3 bucket from EC2 Ubuntu instance

	find metadata for ship ids (mmsi numbers)

		check RDS mysql database (shipspecs) for ship metadata

		go out on WWW and get ship metadata and then update mysql database

	construct summary html file and put in S3 bucket

See AWS_FlowDiagram.jpg for flow chart

(1)  Read AIS data from serial port and determine if ships are ‘in range’ and if so, upload report to S3.

Computer:  Ubuntu laptop at hydrophone node connected to AIS vhf radio receiver

Program:  AIS_node_to_EC2.py

Parameters:  Node latitude and longitude, Center of shipping lanes lat and long,  Range (m) for ship to be “in range”, (default 10000),  Port for serial port ('/dev/ttyUSB0'), S3 bucket/filename where reports are put (/home/val/pythonFiles/upload/OS_rt.txt)

(2)  From EC2, download file from S3 bucket (and print first items in file's lines)

Program:  aws_ec2_access_s3.py

Parameters: local and EC2 file names with paths


