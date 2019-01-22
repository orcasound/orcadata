# orcasound/orcadata/AISprocessing

Python3 routines to 
	decode AIS strings
	transfer AIS data to S3 bucket
	read S3 bucket from EC2 Ubuntu instance
	find metadata for ship ids (mmsi numbers)
		check RDS mysql database (shipspecs) for ship metadata
		go out on WWW and get ship metadata
	construct summary html file and put in S3 bucket

See AWS_FlowDiagram.jpg for flow chart
