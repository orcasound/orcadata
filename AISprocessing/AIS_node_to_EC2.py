#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan  7 14:10:17 2019

@author: val
Give permission to access serial port:
sudoedit /etc/udev/rules.d/50-myusb.rules

Save this text:

KERNEL=="ttyUSB[0-9]*",MODE="0666"
KERNEL=="ttyACM[0-9]*",MODE="0666"

"""
import sys
sys.path.append("/usr/local/lib/python3.6/dist-packages")  # I did not get
from BitVector import BitVector             # BitVector installed properly
from datetime import datetime
import threading
import serial
import numpy as np
import math
## upload files to S3    
    
import boto3
s3 = boto3.client('s3')

nav_status_txt = (
	"Under way using engine",
	"At anchor",
	"Not under command",
	"Restricted manoeuverability",
	"Constrained by her draught",
	"Moored",
	"Aground",
	"Engaged in fishing",
	"Under way sailing",
	"Reserved for HSC",
	"Reserved for WIG",
	"Reserved",
	"Reserved",
	"Reserved",
	"Reserved",
	"Not defined",
    )

def convertToBits(sentence):
    items = sentence.split(",")
    payload = items[5]
    bits = BitVector(size = 6*len(payload))

    for i in range(len(payload)):
        for b in range(6):
            wd = ord(payload[i]) - 48
            if (wd > 40):
                wd -= 8
            thebit = bool(wd &(1<<(5-b)))
#            print(wd,b,thebit)
            idx = i*6+b
            bits[idx] = thebit
    return bits   
 
def convertBitsToInt(bits, iStart, iStop, signedNumber):
    val = 0
    gotNeg = bits[iStart]
    if not signedNumber:
        val = gotNeg
    for i in range(iStart+1,iStop):
        bit = bits[i]
        if signedNumber & gotNeg:
            bit = not bit
        val = val*2 +bit
#        print(i,bit,val,bits[i])
    if signedNumber & gotNeg: 
        val = -val
    return val    

class inRange:
    def __init__(self,mmsi,timeOfDay,rangeToShip,bearingOfShip,sog,navStatus,rangeToClosestPt,minutesToClosestPt):
        self.mmsi = mmsi
        self.timeOfDay = timeOfDay
        self.rangeToShip = rangeToShip
        self.bearingOfShip = bearingOfShip
        self.sog = sog
        self.navStatus = navStatus
        self.rangeToClosestPt = rangeToClosestPt
        self.minutesToClosestPt = minutesToClosestPt
        
def updateShip(idx,timeOfDay,rangeToShip,bearingOfShip,sog,navStatus,rangeToClosestPt,minutesToClosestPt):
    global shipsInRange
    shipsInRange[idx].timeOfDay = timeOfDay
    shipsInRange[idx].rangeToShip = rangeToShip
    shipsInRange[idx].bearingOfShip = bearingOfShip
    shipsInRange[idx].sog = sog
    shipsInRange[idx].navStatus = navStatus
    shipsInRange[idx].rangeToClosestPt = rangeToClosestPt
    shipsInRange[idx].minutesToClosestPt = minutesToClosestPt
        
def inRangeContains(mmsi): ## return index of matched ship
    global shipsInRange
    idx=-1
    for i in range(len(shipsInRange)): 
        if shipsInRange[i].mmsi == mmsi:
            idx = i
    return idx     

def updateTimerToAWS():
    global shipsInRange
    print("READY TO UPLOAD, N ships =",len(shipsInRange))
    if len(shipsInRange) >0:
        #build upload file
        f = open('/home/val/pythonFiles/upload/OS_rt.txt','w')
        f.write("mmsi,timeOfDay,rangeToShip,bearingOfShip,sog,navestatus,rangeToClosestPt,minutesToClosestPt\n")
        for ship in shipsInRange:
            outputline = "%d,%s,%d,%d,%0.2f,%s,%d,%d\n" % \
                (ship.mmsi,ship.timeOfDay,ship.rangeToShip, \
                 ship.bearingOfShip,ship.sog,navStatus,ship.rangeToClosestPt,ship.minutesToClosestPt)
            f.write(outputline)
        f.close()    
        #  upload a local file to s3 bucket (shipnoise-net) in specified folder (ship_photos)
        file_path = '/home/val/pythonFiles/upload/OS_rt.txt'
        thefile = file_path.split('/')[-1]
        s3.upload_file(file_path,'shipnoise-net', 'realtime_files/%s' % thefile)
        del f

    threading.Timer(60, updateTimerToAWS).start()  #update once each 0 seconds
##########################################################################
hydroLat  = 48 + 33.5013/60.0
hydroLong = -(123 + 10.4046/60.0)
laneLong  = -(123 + 12.388/60.0)  # lat/long of point to calculate time to closest approach
laneLat   = 48 + 33.49/60.0
rEarth = 6371000  # radius of earth in meters
rangeLimit = 10000  # distance to ship that is coming into or leaving range
ser = serial.Serial(port='/dev/ttyUSB0',baudrate=38400)  # open serial port
print(ser.name)    
        
shipsInRange = list()
updateTimerToAWS()   #  start the update time running
while True:
    line = ser.readline()
#    print(line)
    strs = str(line).split("\'")
    dta  = strs[1].split("\\")
    if dta[0].split(",")[0] == "!AIVDM":
        sentence = dta[0]
   #     print(sentence)
        thebits = convertToBits(sentence)
#        print(thebits)
        msgType = convertBitsToInt(thebits,0,6,False)
        mmsi =  convertBitsToInt(thebits,8,38,False)
#        print(msgType, mmsi)
        if msgType < 4:
            mmsi =  convertBitsToInt(thebits,8,38,False)
            sog = convertBitsToInt(thebits,50,60,False)/10.0
            longitude = convertBitsToInt(thebits,61,89,True)
            longitude = longitude / 600000.0
            longMin = abs(longitude - int(longitude))*60.0
            longDeg = int(longitude)

            latitude = convertBitsToInt(thebits,89,116,True)
            latitude = latitude / 600000.0
            latMin = abs(latitude - int(latitude))*60.0
            latDeg = int(latitude)
    
            cog = convertBitsToInt(thebits,116,128,False)/10.0
            if cog>360:
                cog -= 360      
            trueHeading = convertBitsToInt(thebits,128,137,False)
            if trueHeading>360:
                trueHeading -= 360
            navStatus = nav_status_txt[convertBitsToInt(thebits,38,41,False)]    
        
            dlat = rEarth*(latitude - hydroLat)*3.1416/180
            dlong = rEarth*(longitude - hydroLong)*math.cos(latitude*3.1416/180)*3.1416/180
            rangeToShip = np.sqrt(dlat*dlat + dlong*dlong)
            bearingOfShip = np.arctan2(dlong,dlat)*180/3.1416
            if bearingOfShip < 0:
                bearingOfShip += 360
            dlat = rEarth*(latitude - laneLat)*3.1416/180
            dlong = rEarth*(longitude - laneLong)*math.cos(latitude*3.1416/180)*3.1416/180
            rangeToClosestPt = np.sqrt(dlat*dlat + dlong*dlong)    
            minutesToClosestPt  = rangeToClosestPt/(max(sog,.01)*0.514*60)  # minutes from point of closest approach
            if (latitude < laneLat) & (cog < 270) & (cog > 90):
                minutesToClosestPt = - minutesToClosestPt
            if (latitude > laneLat) & ((cog > 270) | (cog < 90)):
                minutesToClosestPt = - minutesToClosestPt                
   #         print(round(latitude,4), round(longitude,4),'dlat',int(dlat),'dlong',int(dlong),"bearingOfShip",round(bearingOfShip,1))
            idx = inRangeContains(mmsi)
            if (rangeToClosestPt < rangeLimit) & (idx >= 0):
                updateShip(idx,datetime.now().time(),rangeToShip,bearingOfShip,sog,navStatus,rangeToClosestPt,minutesToClosestPt)  # update time for this inRange ship
                print("UPDATING THIS SHIP mmsi=",mmsi)
            if (rangeToClosestPt < rangeLimit) & (idx == -1):
                shipsInRange.append(inRange(mmsi,datetime.now().time(),rangeToShip,bearingOfShip,sog,navStatus,rangeToClosestPt,minutesToClosestPt)) # new ship has come in range
            if (rangeToClosestPt > rangeLimit) & (idx >=0):
                del shipsInRange[idx]  # ship has left range so remove from list
            print(msgType,mmsi,sog,round(longitude,3),round(latitude,3),cog,trueHeading,navStatus,int(rangeToShip),round(bearingOfShip,1),int(rangeToClosestPt),round(minutesToClosestPt,2))
        
        

        
           

    
    