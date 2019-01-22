#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 22 09:30:02 2019

@author: val
pip3 install smart-open  # https://pypi.org/project/smart-open/


"""
#access S3 imports
from smart_open import smart_open
import boto3
#web access
import urllib3
#mysql imports
import sys
import pymysql  # installed via:  ubuntu@ip-172-31-27-6:~/.local/bin$ ./pip3 install pymysql
import logging
# html parser
import parsePage as pp

s3client = boto3.client('s3')
s3resource = boto3.resource('s3')
bucket = s3resource.Bucket('shipnoise-net')

class ShipSpecs:
    def __init__(self,mmsi):
        self.mmsi = mmsi
        self.shipname = ""
        self.shiptype = ""
        self.yearbuild = 0
        self.shiplength = 0
        self.shipwidth = 0
        self.deadweight = 0
        self.maxspeed = 0
        self.avespeed = 0
        self.flag = ""
        self.callsign = ""
        self.IMO = 0
        self.draught = 0
        self.draughtmax = 0
        self.photolink = ""
        
class passingShip:
    def __init__(self,mmsi,timeOfDay,rangeToShip, bearingOfShip, sog, cog, rangeToClosestPt, minutesFromClosestPt):    
#    def__init__(self,mmsi):#,timeOfDay,rangeToShip, bearingOfShip, minutesFromClosestPt):
        self.mmsi = mmsi
        self.timeOfDay = timeOfDay
        self.rangeToShip = rangeToShip
        self.bearingOfShip = bearingOfShip
        self.sog = sog
        self.cog = cog
        self.rangeToClosestPt = rangeToClosestPt
        self.minutesFromClosestPt = minutesFromClosestPt
        self.shipSpecs = ShipSpecs(mmsi)

    def printShipData(self):
        print(self.mmsi,self.timeOfDay,self.rangeToShip,self.bearingOfShip,self.sog, self.cog, self.rangeToClosestPt, self.minutesFromClosestPt)
        print(self.shipSpecs.mmsi,self.shipSpecs.shipname,self.shipSpecs.shiptype,self.shipSpecs.yearbuild,self.shipSpecs.shiplength)
        
    def fill_shipSpecs(self,mmsi):
        #use data base to fill in values of ShipSpecs object
        print("mmsi=",mmsi)

def lookForPhotoOnS3(mmsi):  ## return True if mmsi number is in a photo_file
    photoFile = ""
    for obj in bucket.objects.all():
        if str(mmsi) in obj.key:
            photoFile = obj.key
    return photoFile  

def getWebPhoto(mmsi):
    page_link = "http://photos.marinetraffic.com/ais/showphoto.aspx?mmsi=%s" % str(mmsi)
    http = urllib3.PoolManager()

    thePhoto = http.request('GET', page_link)
    tmp = open("tmpFile.jpg", 'wb')
    tmp.write(thePhoto.data)
    ship_jpg = 'ship_%s.jpg' % str(mmsi)  # setup standard ship_data photo name
    s3client.upload_file("tmpFile.jpg", 'shipnoise-net', '%s/%s' % ('ship_photos',ship_jpg))
    print("uploaded file ",ship_jpg," to S3 bucket shipnoise-net/ship_photos")
    return ship_jpg
    
def getMetaData(ships):
    # try to get metadata from mysql ship_specs table
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    myhost = 'shipspecs.czrbiuwvsybh.us-west-2.rds.amazonaws.com'
    try:
        conn = pymysql.connect(myhost, user='val', passwd='xxxxxx', db='shipspecs', connect_timeout=15)
    except:
        logger.error("ERROR: Unexpected error: Could not connect to MySQL instance.")
        sys.exit()  #DO I REALLY WANT SYS.EXIT????

    missingMetadata = []
    for ship in ships:
        mmsi = ship.mmsi
        with conn.cursor() as cursor:
            sql = "SELECT * FROM ship_specs WHERE mmsi = %d" % mmsi
##            print(sql)
            cursor.execute(sql)
            rslt = cursor.fetchone()
            print("mysql fetchone returns=",rslt)
            if not isinstance(rslt, type(None)):
                db = list(rslt)
##                print("length of SELECT=",len(db), db)
                if len(db) == 16:  # we have a line of ship metadata
                    ship.shipSpecs.shipname = db[2]
                    ship.shipSpecs.shiptype = db[3]
                    ship.shipSpecs.yearbuild = int(db[4])
                    ship.shipSpecs.shiplength = int(db[5])
                    ship.shipSpecs.shipwidth = int(db[6])
                    ship.shipSpecs.deadweight = int(db[7])
                    ship.shipSpecs.maxspeed = round(float(db[8]),2)
                    ship.shipSpecs.avespeed = round(float(db[9]),2)
                    ship.shipSpecs.flag = db[10]
                    ship.shipSpecs.callsign = db[11]
                    ship.shipSpecs.IMO = int(db[12])
                    ship.shipSpecs.draught = int(db[13])
                    ship.shipSpecs.draughtmax = int(db[14])
                    ship.shipSpecs.photo = db[15]
                    ship.printShipData() 
                else:
                    missingMetadata.append(ship)
            else:
                missingMetadata.append(ship)
    if len(missingMetadata) == 0:
        missingMetadata.append(ship)  
        print("FAKING A SHIP FOR TESTING")         
    print("Number missing metadata =",len(missingMetadata))
    for ship in missingMetadata:
        mmsi = ship.mmsi
        page_link ='http://www.marinetraffic.com/en/ais/details/ships/%d' % mmsi
        (shipname, shiptype, yearbuilt, shiplength, shipwidth, deadweight,maxspeed,avespeed,flag, callsign, draught)=pp.parsePage(page_link)
        print(shipname, shiptype, yearbuilt, shiplength, shipwidth, deadweight,maxspeed,avespeed,flag, callsign, draught)
        #now get ship photo
        #first, check to see if already in S3 bucket
        photoFile = lookForPhotoOnS3(mmsi)
        print("S3 photoFile=",photoFile)
        if photoFile == "":
            photoFile = getWebPhoto(mmsi)
            print("WWW returns photoFile=",photoFile)
        #now insert meta data into ship_specs database
        


def processAIS():
    ###  download file from S3 bucket to EC2 Ubuntu instance
    ships = []
    cnt = 0
    for line in smart_open('s3://shipnoise-net/realtime_files/OS_rt.txt', encoding='utf8'):
        print(line)
        if cnt > 0 :
            itms = line.split(",")
            mmsi = int(itms[0])
            timeOfDay = itms[1]
            rangeToShip = int(itms[2])
            bearingOfShip = int(itms[3])
            sog = round(float(itms[4]),2)
            cog = int(itms[5])
            rangeToClosestPt = int(itms[7])          
            minutesFromClosestPt = int(itms[8])
            passShip = passingShip(mmsi,timeOfDay,rangeToShip, bearingOfShip, sog, cog, rangeToClosestPt, minutesFromClosestPt)
            ships.append(passShip)
        cnt += 1
    print("num ships=",len(ships))    
    getMetaData(ships)



processAIS()        
